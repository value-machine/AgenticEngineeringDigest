"""Web scrapers for sources without RSS feeds."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

import httpx
from bs4 import BeautifulSoup

from .base import Entry, Scraper

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
}


class HfPapersScraper(Scraper):
    """Scrape Hugging Face Daily Papers page."""

    async def scrape(self, source: dict[str, Any]) -> list[Entry]:
        url = "https://huggingface.co/papers"
        async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
            try:
                resp = await client.get(url, headers=HEADERS)
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                self.log_error(source["name"], exc)
                return []

        soup = BeautifulSoup(resp.text, "html.parser")
        entries: list[Entry] = []

        # HF papers page has article elements with paper links
        for article in soup.select("article")[:20]:
            link_el = article.select_one("a[href*='/papers/']")
            if not link_el:
                continue

            href = link_el.get("href", "")
            if not href.startswith("http"):
                href = f"https://huggingface.co{href}"

            title = link_el.get_text(strip=True) or "(untitled)"

            # Look for summary/description text
            summary_el = article.select_one("p")
            summary = summary_el.get_text(strip=True) if summary_el else ""
            if len(summary) > 500:
                summary = summary[:497] + "..."

            entry_id = hashlib.sha256(href.encode()).hexdigest()[:16]
            entries.append(Entry(
                id=entry_id,
                source_name=source["name"],
                category=source["category"],
                title=title,
                url=href,
                summary=summary,
                published=datetime.now(timezone.utc),
                scraped_at=datetime.now(timezone.utc),
            ))

        return entries


class GitHubTrendingScraper(Scraper):
    """Scrape GitHub trending repos, filtering for AI/ML-related ones."""

    AI_KEYWORDS = {
        "llm", "agent", "ai", "ml", "gpt", "transformer", "langchain",
        "rag", "embedding", "neural", "deep-learning", "machine-learning",
        "openai", "anthropic", "llama", "diffusion", "nlp", "mcp",
        "crewai", "autogen", "langgraph", "vector", "chatbot",
    }

    async def scrape(self, source: dict[str, Any]) -> list[Entry]:
        url = "https://github.com/trending?since=daily"
        async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
            try:
                resp = await client.get(url, headers=HEADERS)
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                self.log_error(source["name"], exc)
                return []

        soup = BeautifulSoup(resp.text, "html.parser")
        entries: list[Entry] = []

        for row in soup.select("article.Box-row"):
            h2 = row.select_one("h2 a")
            if not h2:
                continue

            repo_path = h2.get("href", "").strip("/")
            repo_url = f"https://github.com/{repo_path}"
            repo_name = repo_path.replace("/", " / ")

            desc_el = row.select_one("p")
            desc = desc_el.get_text(strip=True) if desc_el else ""

            # Filter: only include repos that look AI-related
            text_blob = f"{repo_path} {desc}".lower()
            if not any(kw in text_blob for kw in self.AI_KEYWORDS):
                continue

            # Stars today
            stars_el = row.select_one("span.d-inline-block.float-sm-right")
            stars_text = stars_el.get_text(strip=True) if stars_el else ""

            summary = desc
            if stars_text:
                summary = f"{desc} ({stars_text})" if desc else stars_text

            entry_id = hashlib.sha256(
                f"gh-trending:{repo_path}:{datetime.now(timezone.utc).date()}".encode()
            ).hexdigest()[:16]

            entries.append(Entry(
                id=entry_id,
                source_name=source["name"],
                category=source["category"],
                title=repo_name,
                url=repo_url,
                summary=summary,
                published=datetime.now(timezone.utc),
                scraped_at=datetime.now(timezone.utc),
            ))

        return entries
