"""
Google Trends hot topics fetcher — uses pytrends (no API key required).

Supports HTTP_PROXY / HTTPS_PROXY env vars for environments where
Google is blocked. Falls back to a mock dataset if the network is
unreachable so the LLM pipeline can still be tested.
"""

import os
from typing import Optional

from pytrends.request import TrendReq


def _get_proxy() -> Optional[str]:
    """Get proxy URL from environment for pytrends format."""
    proxy = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
    return proxy


def _mock_trends() -> list[dict]:
    """Return plausible mock trending topics for testing the LLM pipeline."""
    return [
        {"title": "COP35 Climate Summit", "related_queries": "carbon credits, climate finance, Paris Agreement", "source": "google_trends"},
        {"title": "Apple Vision Pro 2", "related_queries": "spatial computing, mixed reality, VR headset", "source": "google_trends"},
        {"title": "FIFA World Cup 2026", "related_queries": "qualifying matches, host cities, ticket sales", "source": "google_trends"},
        {"title": "NASA Artemis IV mission", "related_queries": "moon landing, lunar base, SpaceX Starship", "source": "google_trends"},
        {"title": "Quantum Computing breakthrough", "related_queries": "quantum supremacy, qubits, encryption", "source": "google_trends"},
        {"title": "BRICS currency proposal", "related_queries": "de-dollarization, gold standard, reserve currency", "source": "google_trends"},
        {"title": "WHO pandemic treaty negotiations", "related_queries": "global health, vaccine equity, biosecurity", "source": "google_trends"},
    ]


def fetch_trending() -> list[dict]:
    """
    Fetch daily and real-time trending searches from Google Trends.

    Returns a list of dicts: {title, related_queries, source}
    """
    topics = []

    proxy = _get_proxy()
    kwargs = {"hl": "en-US", "tz": 360, "timeout": 15}
    if proxy:
        kwargs["proxies"] = [proxy]

    try:
        pytrends = TrendReq(**kwargs)
    except Exception as e:
        print(f"  [!] Google Trends unreachable ({e}) -- using mock topics for testing")
        return _mock_trends()

    # Daily trending searches — try multiple regions
    regions = ["united_states", "united_kingdom", "japan", "south_korea"]
    for region in regions:
        try:
            daily = pytrends.trending_searches(pn=region)
            if daily is not None and not daily.empty:
                for _, row in daily.head(10).iterrows():
                    topics.append({
                        "title": str(row.iloc[0]),
                        "related_queries": "",
                        "source": "google_trends",
                    })
        except Exception:
            continue

    # Real-time trending
    try:
        realtime = pytrends.realtime_trending_searches(pn="US")
        if realtime is not None and not realtime.empty:
            for _, row in realtime.head(10).iterrows():
                title = str(row.get("title", row.iloc[0]))
                topics.append({
                    "title": title,
                    "related_queries": "",
                    "source": "google_trends",
                })
    except Exception:
        pass

    # Deduplicate
    seen = set()
    unique = []
    for t in topics:
        key = t["title"].lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(t)

    if not unique:
        print("  [!] Google Trends returned no data -- using mock topics for testing")
        return _mock_trends()

    return unique
