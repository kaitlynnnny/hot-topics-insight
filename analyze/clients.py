"""
LLM client wrappers — Claude + GPT + DeepSeek + Gemini + Qwen.
Supports role-based personas for multi-perspective debate.
"""

import json
import os
from typing import Optional

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI
from google import genai

# Web search
try:
    from ddgs import DDGS
    _HAS_SEARCH = True
except ImportError:
    _HAS_SEARCH = False

# ── Persona-based system prompts ───────────────────────

DEEPSEEK_PERSONA = """You are a strategic growth analyst. You focus on OPPORTUNITIES: long-term positive developments, technological breakthroughs, market expansion, and constructive trends emerging from this news. Your lens is optimistic but grounded in data. You see the upside that others miss.

IMPORTANT: The news has been verified by multiple credible sources. Do NOT question whether it happened. Focus entirely on the positive implications and growth potential."""

QWEN_PERSONA = """You are a risk and compliance analyst. You focus on THREATS: regulatory risks, geopolitical tensions, supply chain vulnerabilities, security concerns, and potential downsides. Your lens is skeptical toward rosy narratives — you find the hidden costs and unintended consequences.

IMPORTANT: The news has been verified by multiple credible sources. Do NOT question whether it happened. Your skepticism is directed at overly optimistic interpretations of the event, not the event itself."""

GEMINI_PERSONA = """You are a macro-economic and geopolitical strategist. You focus on STRUCTURAL FORCES: how this news fits into broader economic cycles, shifts in the global order, institutional changes, and long-wave trends. Your lens connects the dots between this event and the bigger picture.

IMPORTANT: The news has been verified by multiple credible sources. Do NOT question whether it happened. Focus on how this event interacts with macro-level structural dynamics."""

SYNTHESIZER_SYSTEM = """You are a chief analyst. Three specialists have analyzed a verified news event from different angles. Your job is to synthesize their reports.

Output JSON:
{
  "final_agreement": "The synthesized key takeaway — what this event MEANS when all perspectives are considered (2-3 sentences)",
  "agreement_level": "high" | "partial" | "low",
  "key_tension": "Where do the optimist, risk analyst, and macro strategist disagree? (1 sentence)",
  "bottom_line": "One-line bottom line for a busy reader",
  "deepseek_justification": "The optimist's core position in 1 sentence",
  "qwen_justification": "The risk analyst's core position in 1 sentence",
  "gemini_justification": "The macro strategist's core position in 1 sentence"
}"""


def search_web(query: str, max_results: int = 5) -> str:
    """Search the web for fact-checking context."""
    if not _HAS_SEARCH:
        return "[Web search unavailable]"
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(f"{query}", max_results=max_results))
            if not results:
                return "[No search results found]"
            lines = []
            for i, r in enumerate(results, 1):
                title = r.get("title", "")[:120]
                body = r.get("body", "")[:200]
                href = r.get("href", "")[:150]
                lines.append(f"{i}. {title}\n   {body}\n   URL: {href}")
            return "\n".join(lines)
    except Exception as e:
        return f"[Search error: {e}]"


def _parse_json(text: str) -> Optional[dict]:
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


async def _ask_openai_compatible(client, model, system, prompt, label="LLM") -> Optional[dict]:
    resp = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=1024,
    )
    return _parse_json(resp.choices[0].message.content.strip())


class LLMClients:
    def __init__(self):
        self.anthropic: Optional[AsyncAnthropic] = None
        if os.getenv("ANTHROPIC_API_KEY"):
            self.anthropic = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        self.openai: Optional[AsyncOpenAI] = None
        if os.getenv("OPENAI_API_KEY"):
            self.openai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        self.deepseek: Optional[AsyncOpenAI] = None
        if os.getenv("DEEPSEEK_API_KEY"):
            self.deepseek = AsyncOpenAI(
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                base_url="https://api.deepseek.com",
            )

        self.qwen: Optional[AsyncOpenAI] = None
        if os.getenv("QWEN_API_KEY"):
            self.qwen = AsyncOpenAI(
                api_key=os.getenv("QWEN_API_KEY"),
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )

        self.gemini_client: Optional[genai.Client] = None
        if os.getenv("GEMINI_API_KEY"):
            self.gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    # ── Claude ──
    async def ask_claude(self, system: str, prompt: str, model: str = "claude-sonnet-4-6") -> Optional[dict]:
        if not self.anthropic:
            return None
        try:
            resp = await self.anthropic.messages.create(
                model=model, max_tokens=1024, system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            return _parse_json(resp.content[0].text)
        except Exception as e:
            print(f"  [Claude] {e}")
            return None

    # ── GPT ──
    async def ask_gpt(self, system: str, prompt: str, model: str = "gpt-4o-mini") -> Optional[dict]:
        if not self.openai:
            return None
        try:
            return await _ask_openai_compatible(self.openai, model, system, prompt, "GPT")
        except Exception as e:
            print(f"  [GPT] {e}")
            return None

    # ── DeepSeek ──
    async def ask_deepseek(self, system: str, prompt: str, model: str = "deepseek-chat") -> Optional[dict]:
        if not self.deepseek:
            return None
        try:
            return await _ask_openai_compatible(self.deepseek, model, system, prompt, "DeepSeek")
        except Exception as e:
            print(f"  [DeepSeek] {e}")
            return None

    # ── Qwen ──
    async def ask_qwen(self, system: str, prompt: str, model: str = "qwen-plus") -> Optional[dict]:
        if not self.qwen:
            return None
        try:
            return await _ask_openai_compatible(self.qwen, model, system, prompt, "Qwen")
        except Exception as e:
            print(f"  [Qwen] {e}")
            return None

    # ── Gemini ──
    async def ask_gemini(self, system: str, prompt: str, model: str = "gemini-3.5-flash") -> Optional[dict]:
        if not self.gemini_client:
            return None
        try:
            full = f"{system}\n\n{prompt}"
            resp = await self.gemini_client.aio.models.generate_content(
                model=model, contents=full,
                config={"temperature": 0.7, "max_output_tokens": 1024},
            )
            return _parse_json(resp.text)
        except Exception as e:
            print(f"  [Gemini] {e}")
            return None
