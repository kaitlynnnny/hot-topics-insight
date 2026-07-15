#!/usr/bin/env python3
"""
Hot Topics Insight -- Multi-LLM Global Trend Analyzer

Fetches hot topics from Reddit + Google Trends, then runs a multi-LLM
(Claude + GPT + DeepSeek) cross-review debate to produce synthesized insights.

Usage:
    python main.py [--topics N] [--concurrent N] [--output path]

Environment:
    ANTHROPIC_API_KEY  -- Claude API key
    OPENAI_API_KEY     -- GPT API key
    DEEPSEEK_API_KEY   -- DeepSeek API key
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).resolve().parent / ".env")

from ingest.reddit import fetch_hot_posts
from ingest.trends import fetch_trending
from analyze.clients import LLMClients
from analyze.debate import analyze_topics
from output.render import render_report


def merge_and_rank(
    reddit_posts: list[dict], trends: list[dict], top_n: int = 10
) -> list[dict]:
    """
    Merge Reddit and Google Trends topics, deduplicate by simple keyword overlap,
    and rank by combined heat.
    """
    scored = []

    # Score Reddit posts: normalize score + comment count
    max_score = max((p["score"] for p in reddit_posts), default=1)
    for p in reddit_posts:
        heat = (p["score"] / max_score) * 50 + min(p["num_comments"] / 100, 50)
        scored.append((heat, p))

    # Score Google Trends: assign moderate heat since they're trending
    for t in trends:
        scored.append((35, t))

    # Sort by heat descending
    scored.sort(key=lambda x: x[0], reverse=True)

    # Simple dedup: skip topics whose title substantially overlaps with an earlier one
    def title_words(title: str) -> set:
        return set(title.lower().split())

    selected = []
    seen_words: list[set] = []

    for heat, topic in scored:
        words = title_words(topic["title"])
        if len(words) < 2:
            continue
        is_dup = False
        for prev in seen_words:
            overlap = len(words & prev) / min(len(words), len(prev))
            if overlap > 0.55:
                is_dup = True
                break
        if not is_dup:
            selected.append(topic)
            seen_words.append(words)
        if len(selected) >= top_n:
            break

    return selected


def _mock_analyze(topics: list[dict]) -> list:
    """Generate simulated LLM analysis for testing the full pipeline offline."""
    from analyze.debate import TopicInsight

    mock_insights = []
    perspectives = [
        ("high", "Growth Optimist sees opportunity, Risk Analyst flags vulnerabilities, Macro Strategist notes systemic shift."),
        ("partial", "Optimist bullish on upside, Risk skeptical about timeline, Macro sees mixed signals."),
        ("high", "Strong consensus on significance, minor divergence on pace of impact."),
        ("partial", "Optimist sees quick gains, Risk warns of hidden costs, Macro calls for patience."),
        ("low", "Sharp disagreement: Optimist sees paradigm shift, Risk calls it noise, Macro is conflicted."),
    ]

    for i, topic in enumerate(topics):
        title = topic["title"]
        agree_level, tension_text = perspectives[i % len(perspectives)]
        source_str = topic.get("source", "")
        if topic.get("subreddit"):
            source_str += f" (r/{topic['subreddit']})"

        ins = TopicInsight(
            title=title,
            source_str=source_str,
            url=topic.get("url", ""),
            deepseek_analysis={"summary": f"[MOCK] {title}", "significance": "Growth opportunity with long-term upside.", "angle": "Growth Optimist", "confidence": "high"},
            qwen_analysis={"summary": f"[MOCK] {title}", "significance": "Risk factors need closer scrutiny.", "angle": "Risk & Compliance", "confidence": "medium"},
            gemini_analysis={"summary": f"[MOCK] {title}", "significance": "Part of a broader structural pattern.", "angle": "Macro Strategist", "confidence": "high"},
            final_agreement=f"[MOCK] Synthesized insight: {title}",
            agreement_level=agree_level,
            key_tension=tension_text,
            bottom_line=f"[MOCK] Bottom line for: {title[:80]}",
            deepseek_justification="Growth angle: positive long-term implications and market expansion opportunities.",
            qwen_justification="Risk angle: regulatory exposure and compliance gaps require attention.",
            gemini_justification="Macro angle: fits into larger structural realignment of global systems.",
        )
        mock_insights.append(ins)
        print(f"  [mock] {title[:80]}... -> {agree_level} agreement")

    return mock_insights


async def main():
    parser = argparse.ArgumentParser(description="Hot Topics Insight")
    parser.add_argument("--topics", type=int, default=8, help="Number of topics to analyze (default: 8)")
    parser.add_argument("--concurrent", type=int, default=3, help="Max concurrent LLM analyses (default: 3)")
    parser.add_argument("--output", type=str, default=None, help="Output HTML path (default: output/report.html)")
    parser.add_argument("--skip-ingest", action="store_true", help="Skip data fetching (uses cached topics)")
    parser.add_argument("--mock-llm", action="store_true", help="Use mock LLM responses for testing without API keys")
    args = parser.parse_args()

    # Check API keys
    has_any_key = any(os.getenv(k) for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY"))
    if not has_any_key:
        print("[!] No API keys found (ANTHROPIC/OPENAI/DEEPSEEK).")
        print("    Set at least one in .env or environment variables.\n")

    # Step 1: Fetch topics
    print("=" * 60)
    print(">> STEP 1: Fetching hot topics from Reddit + Google Trends...")
    print("=" * 60)

    reddit_posts, trends = [], []
    if not args.skip_ingest:
        print("  Fetching Reddit hot posts...")
        reddit_posts = await fetch_hot_posts()
        print(f"  -> {len(reddit_posts)} posts from Reddit")

        print("  Fetching Google Trends...")
        trends = fetch_trending()
        print(f"  -> {len(trends)} trending searches from Google")
    else:
        print("  Skipping ingest (--skip-ingest)")

    if not reddit_posts and not trends:
        print("[ERROR] No topics fetched. Check your network connection and try again.")
        sys.exit(1)

    # Step 2: Merge, dedup, rank
    print(f"\n>> STEP 2: Merging, deduplicating, ranking -> top {args.topics}...")
    topics = merge_and_rank(reddit_posts, trends, top_n=args.topics)
    print(f"  -> {len(topics)} unique topics selected")
    for i, t in enumerate(topics, 1):
        src = t.get("source", "?")
        if t.get("subreddit"):
            src += f"/r/{t['subreddit']}"
        print(f"  {i:2}. [{src}] {t['title'][:90]}")

    # Step 3: Multi-LLM analysis
    print(f"\n>> STEP 3: Multi-LLM analysis (max {args.concurrent} concurrent)...")
    print("=" * 60)
    clients = LLMClients()

    if args.mock_llm:
        insights = _mock_analyze(topics)
    elif not any([clients.anthropic, clients.openai, clients.deepseek]):
        print("[ERROR] No LLM clients available. Set at least one API key.")
        print("        Or use --mock-llm to test with simulated LLM responses.")
        sys.exit(1)
    else:
        insights = await analyze_topics(clients, topics, max_concurrent=args.concurrent)

    # Step 4: Render report
    print(f"\n>> STEP 4: Generating HTML report...")
    path = render_report(insights, args.output)
    print(f"  -> Report saved to: {path}")

    # Summary
    agree_counts = {"high": 0, "partial": 0, "low": 0, "unknown": 0}
    for ins in insights:
        agree_counts[ins.agreement_level or "unknown"] += 1

    print(f"\n{'=' * 60}")
    print(f"[DONE] {len(insights)} topics analyzed")
    print(f"   HIGH agreement:    {agree_counts['high']}")
    print(f"   PARTIAL agreement: {agree_counts['partial']}")
    print(f"   LOW agreement:     {agree_counts['low']}")
    print(f"   UNKNOWN:           {agree_counts['unknown']}")
    print(f"\n   Open {path} in your browser to view the report.")


if __name__ == "__main__":
    asyncio.run(main())
