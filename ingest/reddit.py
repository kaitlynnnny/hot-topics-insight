"""
Reddit hot topics fetcher — uses the public .json API (no auth required).

Supports HTTP_PROXY / HTTPS_PROXY env vars for environments where
Reddit is blocked. Falls back to a mock dataset if the network is
unreachable so the LLM pipeline can still be tested.
"""

import aiohttp
import asyncio
import os
from typing import Optional

REDDIT_SUBREDDITS = ["all", "worldnews", "news", "technology", "science"]
REDDIT_BASE = "https://www.reddit.com"
OLD_REDDIT = "https://old.reddit.com"
LIMIT_PER_SUB = 15

# Browser-like User-Agent to reduce bot blocking
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
    "hot-topics-insight/0.1 (research; contact@example.com)",
]


def _get_headers() -> dict:
    import random
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
    }


def _get_proxy() -> Optional[str]:
    """Get proxy URL from environment."""
    return os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY") or os.getenv("https_proxy") or os.getenv("http_proxy")


async def _fetch_subreddit(
    session: aiohttp.ClientSession, subreddit: str, base_url: str
) -> list[dict]:
    """Fetch hot posts from a single subreddit."""
    url = f"{base_url}/r/{subreddit}/hot.json?limit={LIMIT_PER_SUB}&raw_json=1"
    try:
        async with session.get(url, headers=_get_headers(), timeout=15) as resp:
            if resp.status != 200:
                return []
            data = await resp.json(content_type=None)  # accept any content-type
    except Exception:
        return []

    posts = []
    for child in data.get("data", {}).get("children", []):
        post = child.get("data", {})
        title = post.get("title", "")
        if not title or post.get("stickied"):
            continue
        posts.append(
            {
                "title": title,
                "url": f"https://reddit.com{post.get('permalink', '')}",
                "score": post.get("score", 0),
                "num_comments": post.get("num_comments", 0),
                "subreddit": post.get("subreddit", subreddit),
                "source": "reddit",
            }
        )
    return posts


def _mock_posts() -> list[dict]:
    """Return plausible mock topics for testing the LLM pipeline offline."""
    return [
        {"title": "EU passes landmark AI regulation requiring transparency from large language models", "url": "", "score": 28500, "num_comments": 3400, "subreddit": "worldnews", "source": "reddit"},
        {"title": "Scientists achieve net-positive fusion energy for the first time in sustained reaction", "url": "", "score": 41200, "num_comments": 5200, "subreddit": "science", "source": "reddit"},
        {"title": "Global semiconductor supply chain reshapes as new fabs open outside Taiwan", "url": "", "score": 18300, "num_comments": 2100, "subreddit": "technology", "source": "reddit"},
        {"title": "Argentina inflation drops below 30% for first time in 5 years under new economic policy", "url": "", "score": 15600, "num_comments": 1800, "subreddit": "worldnews", "source": "reddit"},
        {"title": "Breakthrough CRISPR 3.0 enables precise gene repair with 99% accuracy in human trials", "url": "", "score": 32000, "num_comments": 2800, "subreddit": "science", "source": "reddit"},
        {"title": "Central banks in BRICS nations accelerate gold purchases, shifting reserve composition", "url": "", "score": 12100, "num_comments": 1500, "subreddit": "news", "source": "reddit"},
        {"title": "Major ransomware attack hits US healthcare systems, affecting 50+ hospitals", "url": "", "score": 24500, "num_comments": 4100, "subreddit": "news", "source": "reddit"},
    ]


async def fetch_hot_posts(subreddits: Optional[list[str]] = None) -> list[dict]:
    """
    Fetch hot posts from Reddit. Tries multiple endpoints, falls back to mock data.

    Returns a list of dicts: {title, url, score, num_comments, subreddit, source}
    """
    if subreddits is None:
        subreddits = REDDIT_SUBREDDITS

    proxy = _get_proxy()
    connector = None
    kwargs = {}
    if proxy:
        kwargs["proxy"] = proxy

    all_posts = []

    # Try www.reddit.com first, then old.reddit.com
    for base in (REDDIT_BASE, OLD_REDDIT):
        if all_posts:
            break
        try:
            async with aiohttp.ClientSession(connector=connector, **kwargs) as session:
                tasks = [_fetch_subreddit(session, sub, base) for sub in subreddits]
                results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, list):
                    all_posts.extend(result)
        except Exception:
            continue

    # If we got real data, dedup and return
    if all_posts:
        all_posts.sort(key=lambda p: p["score"], reverse=True)
        seen_titles = set()
        unique = []
        for p in all_posts:
            key = p["title"].lower()[:60].strip()
            if key not in seen_titles:
                seen_titles.add(key)
                unique.append(p)
        return unique

    # Fallback: use mock data so the LLM pipeline can still run
    print("  [!] Reddit unreachable (geo-blocked or no network) -- using mock topics for testing")
    return _mock_posts()
