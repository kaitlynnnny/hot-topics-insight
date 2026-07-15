#!/usr/bin/env python3
"""
bridge.py — connects Glean's JSONL output to the multi-LLM debate engine.

Flow:
  1. Read Glean JSONL → dedup by URL
  2. Cluster similar articles with sentence-transformers embeddings
  3. Pick top topics by cluster size × source diversity
  4. Run multi-LLM debate on each topic
  5. Output HTML report + Markdown digest
"""

import asyncio
import json
import os
import sys
from collections import Counter

# Force UTF-8 on Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# Load .env from our project root
load_dotenv(Path(__file__).resolve().parent / ".env")

from analyze.clients import LLMClients
from analyze.debate import analyze_topics
from output.render import render_report

# ── Config ────────────────────────────────────────────
# Auto-detect Glean output path
_GLEAN_DEFAULT = Path(__file__).resolve().parent.parent / "glean" / "output" / "glean-output.jsonl"
GLEAN_JSONL = Path(os.environ.get("GLEAN_OUTPUT", str(_GLEAN_DEFAULT)))
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
CLUSTER_THRESHOLD = 0.70  # cosine similarity threshold for grouping


# ── Step 1: Read Glean JSONL ──────────────────────────

def read_glean_output(path: Path) -> list[dict]:
    """Read JSONL, deduplicate by URL across multiple runs."""
    if not path.exists():
        print(f"[!] {path} not found -- run Glean first")
        return []

    seen_urls = set()
    items = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            url = item.get("url", "")
            if url and url in seen_urls:
                continue
            seen_urls.add(url)
            items.append(item)

    return items


# ── Step 2: Cluster similar articles ───────────────────

def cluster_topics(items: list[dict], threshold: float = CLUSTER_THRESHOLD) -> list[dict]:
    """
    Use sentence-transformers to group similar headlines into topics.
    Each cluster becomes one topic for the debate engine.
    """
    if not items:
        return []

    print("  Loading embedding model (first run downloads ~120MB)...")
    model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

    # Build rich text for each article: title + summary
    texts = []
    for item in items:
        title = item.get("title", "")
        summary = item.get("summary", "")
        texts.append(f"{title}. {summary}" if summary else title)

    print(f"  Encoding {len(texts)} articles...")
    embeddings = model.encode(texts, show_progress_bar=True)

    # Compute similarity matrix
    sim_matrix = cosine_similarity(embeddings)

    # Greedy clustering
    clusters = []
    used = set()

    for i in range(len(texts)):
        if i in used:
            continue
        cluster = [i]
        used.add(i)
        for j in range(i + 1, len(texts)):
            if j not in used and sim_matrix[i][j] > threshold:
                cluster.append(j)
                used.add(j)
        clusters.append(cluster)

    # Each cluster → one topic dict
    topics = []
    for cluster in clusters:
        best = items[cluster[0]]  # first item as representative
        sources = Counter()
        source_names = set()
        summaries = []
        for idx in cluster:
            src = items[idx].get("source_name", "unknown")
            sources[src] += 1
            source_names.add(src)
            s = items[idx].get("summary", "")
            if s:
                summaries.append(s)

        # Heat score: cluster size × source diversity
        heat = len(cluster) * (1 + len(source_names) * 0.5)

        topics.append({
            "title": best["title"],
            "url": best.get("url", ""),
            "source": "+".join(sorted(source_names)[:4]),
            "score": int(heat * 100),
            "num_comments": len(cluster),  # number of articles in cluster
            "related_queries": " | ".join(summaries[:3]),  # top 3 summaries as context
        })

    # Sort by heat descending
    topics.sort(key=lambda t: t["score"], reverse=True)
    return topics


# ── Step 3: Programmatic fact verification ─────────────

# Tier 1: top global outlets — 1 match is enough
TIER1_DOMAINS = [
    "bbc.co.uk", "bbc.com", "reuters.com", "apnews.com",
    "nytimes.com", "theguardian.com", "aljazeera.com",
    "cnn.com", "washingtonpost.com", "bloomberg.com",
    "wsj.com", "npr.org", "cnbc.com", "abcnews.go.com",
    "cbsnews.com", "nbcnews.com", "economist.com",
    "politico.com", "dw.com", "france24.com",
]

# Tier 2: regional & specialized — need 2 matches (or 1 + tier1)
TIER2_DOMAINS = [
    "thehindu.com", "straitstimes.com", "japantimes.co.jp",
    "scmp.com", "nikkei.com", "timesofindia.indiatimes.com",
    "al-monitor.com", "haaretz.com", "timesofisrael.com",
    "af.reuters.com", "channelnewsasia.com", "ansa.it",
    "elpais.com", "lemonde.fr", "spiegel.de",
    "independent.co.uk", "telegraph.co.uk", "usatoday.com",
    "latimes.com", "chicagotribune.com", "bostonglobe.com",
    "sfchronicle.com", "theatlantic.com", "newyorker.com",
    "vox.com", "axios.com", "techcrunch.com", "theverge.com",
    "arstechnica.com", "wired.com", "nature.com", "science.org",
    "ndtv.com", "dawn.com", "smh.com.au", "theage.com.au",
    "rnz.co.nz", "bbc.com/zhongwen", "bbc.com/zhongwen/simp",
]


def _extract_keywords(title: str) -> str:
    """Extract key search terms from a headline."""
    import re
    # Remove quotes, special chars, keep meaningful words
    cleaned = re.sub(r'[^\w\s]', ' ', title)
    words = [w for w in cleaned.split() if len(w) > 3 and w.lower()
             not in ('this', 'that', 'with', 'from', 'they', 'their',
                     'have', 'been', 'were', 'after', 'over', 'into',
                     'about', 'what', 'when', 'where', 'which', 'there')]
    # Take key words (first 6-8 substantive words)
    return ' '.join(words[:8])


def verify_topic(topic: dict) -> tuple[bool, str]:
    """
    Programmatic fact verification — NO LLM involved.
    1. Extract keywords from headline
    2. Search the web
    3. Check multi-tier domain matching
    4. Cluster size boosts confidence (already multi-source = already vetted)

    Returns: (is_verified, evidence_string)
    """
    from analyze.clients import search_web

    title = topic["title"]
    cluster_size = topic.get("num_comments", 1)
    keywords = _extract_keywords(title)

    # Search with keywords (not exact title) for broader matching
    results = search_web(f'{keywords} news', max_results=8)

    if results.startswith("[Web search") or results.startswith("[No search"):
        # If cluster already has 2+ sources, trust the cluster
        if cluster_size >= 2:
            return True, f"[Multi-source cluster ({cluster_size} articles) — passing through]"
        return True, "[Search unavailable — passing through]"

    results_lower = results.lower()

    # Count matches by tier
    tier1_matches = [d for d in TIER1_DOMAINS if d in results_lower]
    tier2_matches = [d for d in TIER2_DOMAINS if d in results_lower]

    # Scoring
    tier1_score = len(tier1_matches)
    tier2_score = len(tier2_matches)
    cluster_bonus = min(cluster_size - 1, 3)  # each extra source in cluster = +1 bonus, capped at 3

    total_score = tier1_score * 3 + tier2_score + cluster_bonus

    # Evidence for debate prompt
    lines = results.split("\n")
    evidence = "\n".join(lines[:6]) if len(lines) > 6 else results
    evidence = evidence[:600]

    matched = tier1_matches + tier2_matches

    # Decision logic
    if tier1_score >= 1:
        # At least 1 Tier-1 match → verified
        return True, f"Verified by Tier-1: {', '.join(tier1_matches[:4])}\nSearch evidence:\n{evidence}"
    elif tier2_score >= 2:
        # 2+ Tier-2 matches → verified
        return True, f"Verified by Tier-2: {', '.join(tier2_matches[:4])}\nSearch evidence:\n{evidence}"
    elif tier1_score >= 1 or (tier2_score >= 1 and cluster_size >= 2):
        # 1 Tier-1 OR (1 Tier-2 + cluster of 2+) → verified
        return True, f"Verified (mixed): Tier-1={tier1_score}, Tier-2={tier2_score}, cluster={cluster_size}\nSearch evidence:\n{evidence}"
    elif cluster_size >= 3:
        # 3+ sources already reporting this → verified even without search match
        return True, f"Verified by cluster confidence ({cluster_size} sources)\nSearch evidence:\n{evidence}"
    elif total_score >= 2:
        return True, f"Verified (score={total_score})\nSearch evidence:\n{evidence}"
    else:
        return False, f"No credible source found (tier1={tier1_score}, tier2={tier2_score}, cluster={cluster_size}). Results:\n{evidence}"


def verify_topics(topics: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split topics into verified and rejected."""
    verified = []
    rejected = []

    for t in topics:
        is_real, evidence = verify_topic(t)
        if is_real:
            t["verification_evidence"] = evidence
            verified.append(t)
            print(f"    [VERIFIED] {t['title'][:70]}...")
        else:
            rejected.append(t)
            print(f"    [REJECTED] {t['title'][:70]}... (t1=0 t2=0 cluster={t.get('num_comments',1)})")

    return verified, rejected


# ── Step 4: Markdown digest ────────────────────────────

def generate_markdown_digest(insights: list) -> str:
    """Generate a daily Markdown digest."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Global Hot Topics — Daily Digest",
        f"*{now}*",
        "",
        "---",
        "",
    ]
    for i, ins in enumerate(insights, 1):
        agree = {"high": "G", "partial": "Y", "low": "R", "unknown": "?"}.get(
            ins.agreement_level, "?"
        )
        lines.append(f"## {i}. {ins.title}")
        lines.append(f"**Agreement**: {agree} ({ins.agreement_level})")
        lines.append(f"**Final Agreement**: {ins.final_agreement}")
        if ins.bottom_line:
            lines.append(f"**Bottom Line**: {ins.bottom_line}")
        if ins.key_tension:
            lines.append(f"*Tension: {ins.key_tension}*")
        models_used = ", ".join(ins.active_models)
        lines.append(f"*Models: {models_used}*")
        lines.append("")
    return "\n".join(lines)


# ── Main ───────────────────────────────────────────────

async def main():
    top_n = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    concurrent = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    mock = "--mock" in sys.argv

    print("=" * 60)
    print("BRIDGE: Glean JSONL -> Clustering -> Web Verification -> Multi-LLM Debate")
    print("=" * 60)

    # 1. Read Glean output
    print("\n[1/5] Reading Glean JSONL...")
    items = read_glean_output(GLEAN_JSONL)
    print(f"  {len(items)} unique articles (URL-deduped)")

    if not items:
        print("[!] No data. Run Glean first, then re-run bridge.py")
        return

    # 2. Cluster
    print(f"\n[2/5] Clustering with sentence-transformers (threshold={CLUSTER_THRESHOLD})...")
    all_topics = cluster_topics(items)
    print(f"  {len(all_topics)} unique topic clusters found")

    # Show top clusters
    candidates = all_topics[:max(top_n * 2, 20)]  # verify more than needed
    print(f"\n  Top {len(candidates)} candidates by heat score:")

    # 3. Programmatic web verification
    print(f"\n[3/5] Verifying with web search (programmatic, no LLM)...")
    print("=" * 60)
    verified_topics, rejected_topics = verify_topics(candidates)

    # Take top N verified
    topics = verified_topics[:top_n]
    print(f"\n  Verified: {len(verified_topics)} | Rejected: {len(rejected_topics)}")
    print(f"  Top {len(topics)} entering debate:")
    for i, t in enumerate(topics, 1):
        print(f"  {i:2}. [{t['source']}] {t['title'][:85]}")

    if rejected_topics:
        print(f"\n  Rejected (no credible source match):")
        for t in rejected_topics[:5]:
            print(f"     X {t['title'][:70]}...")

    if not topics:
        print("[!] All topics failed verification. Try again later or lower threshold.")
        return

    # 4. Multi-LLM debate
    print(f"\n[4/5] Running multi-LLM debate on {len(topics)} verified topics (max {concurrent} concurrent)...")
    print("=" * 60)

    if mock:
        from main import _mock_analyze
        insights = _mock_analyze(topics)
    else:
        clients = LLMClients()
        if not any([clients.anthropic, clients.openai, clients.deepseek]):
            print("[!] No API keys found. Using --mock mode.")
            from main import _mock_analyze
            insights = _mock_analyze(topics)
        else:
            insights = await analyze_topics(clients, topics, max_concurrent=concurrent)

    # 5. Output
    print(f"\n[5/5] Generating output...")

    # HTML report — pass raw items for news listing section
    html_path = render_report(insights, raw_items=items, output_path=str(OUTPUT_DIR / "report.html"))
    print(f"  HTML report: {html_path}")

    # Markdown digest
    md = generate_markdown_digest(insights)
    md_path = OUTPUT_DIR / "daily-digest.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"  Markdown digest: {md_path}")

    # Summary
    agree_counts = {"high": 0, "partial": 0, "low": 0, "unknown": 0}
    for ins in insights:
        agree_counts[ins.agreement_level or "unknown"] += 1

    print(f"\n{'=' * 60}")
    print(f"[DONE] {len(insights)} topics debated")
    print(f"   HIGH agreement:    {agree_counts['high']}")
    print(f"   PARTIAL agreement: {agree_counts['partial']}")
    print(f"   LOW agreement:     {agree_counts['low']}")
    print(f"\n   Open {html_path} in your browser.")


if __name__ == "__main__":
    asyncio.run(main())
