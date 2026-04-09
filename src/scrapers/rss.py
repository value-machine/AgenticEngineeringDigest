"""RSS/Atom feed scraper — handles newsletters, podcasts, Reddit, and YouTube feeds."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
import httpx

from .base import Entry, Scraper


class RssScraper(Scraper):
    """Fetch and parse any RSS/Atom feed."""

    async def scrape(self, source: dict[str, Any]) -> list[Entry]:
        feed_url = source.get("feed_url")
        if not feed_url:
            return []

        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; Feedfetcher-Google; +https://github.com/value-machine/AgenticEngineeringDigest)",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
        }
        # Reddit requires a descriptive UA
        if "reddit.com" in feed_url:
            headers["User-Agent"] = "AgenticDigest:0.1 (by /u/agentic-digest-bot)"
        # Substack blocks non-browser UAs from cloud runners — use a browser-like UA
        elif "substack.com" in feed_url or "api.substack.com" in feed_url:
            headers["User-Agent"] = (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )

        async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
            try:
                resp = await client.get(feed_url, headers=headers)
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                self.log_error(source["name"], exc)
                return []

        feed = feedparser.parse(resp.text)
        entries: list[Entry] = []

        for item in feed.entries[:25]:  # cap per source
            published = self._parse_date(item)
            entry = Entry(
                id=self._make_id(feed_url, item),
                source_name=source["name"],
                category=source["category"],
                title=item.get("title", "(untitled)"),
                url=item.get("link", ""),
                summary=self._clean_summary(item),
                published=published,
                scraped_at=datetime.now(timezone.utc),
            )
            entries.append(entry)

        return entries

    @staticmethod
    def _make_id(feed_url: str, item: Any) -> str:
        raw = item.get("id") or item.get("link") or item.get("title", "")
        return hashlib.sha256(f"{feed_url}:{raw}".encode()).hexdigest()[:16]

    @staticmethod
    def _parse_date(item: Any) -> datetime:
        for field in ("published", "updated"):
            raw = item.get(field)
            if raw:
                try:
                    return parsedate_to_datetime(raw)
                except Exception:
                    pass
            parsed = item.get(f"{field}_parsed")
            if parsed:
                try:
                    from time import mktime
                    return datetime.fromtimestamp(mktime(parsed), tz=timezone.utc)
                except Exception:
                    pass
        return datetime.now(timezone.utc)

    @staticmethod
    def _clean_summary(item: Any) -> str:
        raw = item.get("summary") or item.get("description") or ""
        # Strip HTML tags for a plain-text summary
        from bs4 import BeautifulSoup
        text = BeautifulSoup(raw, "html.parser").get_text(separator=" ", strip=True)
        # Truncate to ~500 chars
        if len(text) > 500:
            text = text[:497] + "..."
        return text
