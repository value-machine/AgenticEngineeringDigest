"""Base scraper interface and shared data model."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

from rich.console import Console

console = Console(stderr=True, force_terminal=True)


@dataclass
class Entry:
    id: str
    source_name: str
    category: str
    title: str
    url: str
    summary: str
    published: datetime
    scraped_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["published"] = self.published.isoformat()
        d["scraped_at"] = self.scraped_at.isoformat()
        return d


class Scraper:
    """Base class — subclasses implement `scrape(source) -> list[Entry]`."""

    async def scrape(self, source: dict[str, Any]) -> list[Entry]:
        raise NotImplementedError

    @staticmethod
    def log_error(source_name: str, exc: Exception) -> None:
        console.print(f"  [red]X[/red] {source_name}: {exc}")
