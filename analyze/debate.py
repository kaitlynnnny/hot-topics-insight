import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

"""
Multi-LLM debate engine v4 — Role-based blind analysis + Synthesizer.

  Stage 1: Each model analyzes independently with a fixed persona
           (DeepSeek=Optimist, Qwen=Risk, Gemini=Macro)
           All see the same verified news + source metadata.
  Stage 2: A Synthesizer merges the 3 independent reports.
           No cross-review — no model sees another's output.
"""

import asyncio
from dataclasses import dataclass, field

from analyze.clients import (
    LLMClients,
    DEEPSEEK_PERSONA,
    QWEN_PERSONA,
    GEMINI_PERSONA,
    SYNTHESIZER_SYSTEM,
)


@dataclass
class TopicInsight:
    title: str
    source_str: str
    url: str
    news_summary: str = ""

    # Stage 1: Persona-based independent analyses
    deepseek_analysis: dict | None = None
    qwen_analysis: dict | None = None
    gemini_analysis: dict | None = None
    claude_analysis: dict | None = None
    gpt_analysis: dict | None = None

    # Stage 2: Synthesis
    final_agreement: str = ""
    agreement_level: str = "unknown"
    key_tension: str = ""
    bottom_line: str = ""
    deepseek_justification: str = ""
    qwen_justification: str = ""
    gemini_justification: str = ""

    error: str = ""

    @property
    def active_models(self) -> list[str]:
        models = []
        if self.deepseek_analysis: models.append("DeepSeek")
        if self.qwen_analysis: models.append("Qwen")
        if self.gemini_analysis: models.append("Gemini")
        if self.claude_analysis: models.append("Claude")
        if self.gpt_analysis: models.append("GPT")
        return models


def _build_analysis_prompt(topic: dict) -> str:
    """Build prompt with factual anchor: source list, count, heat, snippets."""
    sources = topic.get("source", "unknown")
    source_count = topic.get("num_comments", 1)
    heat = topic.get("score", 0)
    title = topic["title"]
    snippets = topic.get("related_queries", "")
    evidence = topic.get("verification_evidence", "")

    # Extract domain names cleanly from verification evidence
    verified_by = ""
    if "Verified by:" in evidence:
        verified_by = evidence.split("Verified by:")[1].split("\n")[0].strip()

    return f"""【VERIFIED NEWS EVENT — DO NOT QUESTION ITS FACTUALITY】

This event has been confirmed by {source_count} independent media sources.
Verification: cross-referenced with {verified_by}

HEADLINE: {title}

SOURCES ({source_count} outlets): {sources}

HEAT SCORE: {heat} (higher = more outlets covering this story)

CONTEXT FROM MULTIPLE ARTICLES:
{snippets if snippets else 'See headline above.'}

VERIFICATION EVIDENCE:
{evidence[:400] if evidence else 'Verified by multiple credible news organizations.'}

---
Analyze what this event MEANS through your specific analytical lens.
Respond with JSON:
{{
  "summary": "One-sentence factual summary of the event",
  "significance": "Why this matters — through YOUR assigned analytical lens (1-2 sentences)",
  "key_insight": "Your most important original insight about this event (1 sentence)"
}}"""


def _build_synthesis_prompt(topic: dict, analyses: dict) -> str:
    """Build prompt for the Synthesizer: merge 3 independent reports."""
    title = topic["title"]
    parts = [f'Topic: "{title}"\n\nThree specialists analyzed this verified event independently. Merge their reports.\n']

    for model, a in analyses.items():
        if a:
            parts.append(
                f"[{model}] Summary: {a.get('summary', '?')}\n"
                f"  Significance: {a.get('significance', '?')}\n"
                f"  Key Insight: {a.get('key_insight', '?')}\n"
            )
        else:
            parts.append(f"[{model}] No analysis available.\n")

    parts.append(
        "\nSynthesize: find common ground across all perspectives, "
        "note where they disagree, and produce a unified bottom line."
    )
    return "\n".join(parts)


# ── Model → persona mapping ──
PERSONAS = {
    "DeepSeek": DEEPSEEK_PERSONA,
    "Qwen": QWEN_PERSONA,
    "Gemini": GEMINI_PERSONA,
}
# Fallback: other models get generic analyst persona
FALLBACK_PERSONA = "You are an expert global affairs analyst. Analyze what this verified news event means and its broader implications."


async def analyze_topic(clients: LLMClients, topic: dict) -> TopicInsight:
    title = topic["title"][:200]
    source_str = topic.get("source", "")
    url = topic.get("url", "")
    news_summary = topic.get("related_queries", "") or topic.get("summary", "")

    insight = TopicInsight(title=title, source_str=source_str, url=url, news_summary=news_summary)
    prompt = _build_analysis_prompt(topic)

    # ── Stage 1: Parallel independent analysis with fixed personas ──
    tasks = [
        clients.ask_deepseek(DEEPSEEK_PERSONA, prompt),
        clients.ask_qwen(QWEN_PERSONA, prompt),
        clients.ask_gemini(GEMINI_PERSONA, prompt),
        # Claude/GPT as extras if available
        clients.ask_claude(FALLBACK_PERSONA, prompt),
        clients.ask_gpt(FALLBACK_PERSONA, prompt),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    insight.deepseek_analysis = results[0] if not isinstance(results[0], Exception) else None
    insight.qwen_analysis = results[1] if not isinstance(results[1], Exception) else None
    insight.gemini_analysis = results[2] if not isinstance(results[2], Exception) else None
    insight.claude_analysis = results[3] if not isinstance(results[3], Exception) else None
    insight.gpt_analysis = results[4] if not isinstance(results[4], Exception) else None

    analyses = {
        "DeepSeek (Optimist/Growth)": insight.deepseek_analysis,
        "Qwen (Risk/Compliance)": insight.qwen_analysis,
        "Gemini (Macro/Structural)": insight.gemini_analysis,
    }

    if not any(analyses.values()):
        insight.error = "All models failed"
        return insight

    # ── Stage 2: Synthesizer merges independent reports ──
    synth_prompt = _build_synthesis_prompt(topic, analyses)
    synth = None
    for ask_fn in [clients.ask_gemini, clients.ask_deepseek, clients.ask_qwen,
                    clients.ask_claude, clients.ask_gpt]:
        if synth is None:
            try:
                synth = await ask_fn(SYNTHESIZER_SYSTEM, synth_prompt)
            except Exception:
                continue

    if synth:
        insight.final_agreement = synth.get("final_agreement", "")
        insight.agreement_level = synth.get("agreement_level", "unknown")
        insight.key_tension = synth.get("key_tension", "")
        insight.bottom_line = synth.get("bottom_line", "")
        insight.deepseek_justification = synth.get("deepseek_justification", "")
        insight.qwen_justification = synth.get("qwen_justification", "")
        insight.gemini_justification = synth.get("gemini_justification", "")
    else:
        insight.error = "Synthesis failed"

    return insight


async def analyze_topics(clients, topics, max_concurrent=2):
    semaphore = asyncio.Semaphore(max_concurrent)

    async def analyze_one(topic):
        async with semaphore:
            print(f"  Analyzing: {topic['title'][:80]}...")
            result = await analyze_topic(clients, topic)
            models = "+".join(result.active_models) if result.active_models else "NONE"
            agree = result.agreement_level or "?"
            print(f"  OK [{models}] [{agree}] {result.bottom_line or result.final_agreement[:80]}")
            return result

    return await asyncio.gather(*[analyze_one(t) for t in topics])
