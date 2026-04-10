"""SQLite storage for entry deduplication and digest history."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from src.scrapers.base import Entry

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "digest.db"


class Storage:
    def __init__(self, db_path: Path = DEFAULT_DB) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS entries (
                id          TEXT PRIMARY KEY,
                source_name TEXT NOT NULL,
                category    TEXT NOT NULL,
                title       TEXT NOT NULL,
                url         TEXT NOT NULL,
                summary     TEXT,
                published   TEXT NOT NULL,
                scraped_at  TEXT NOT NULL,
                digest_id   TEXT
            );

            CREATE TABLE IF NOT EXISTS digests (
                id          TEXT PRIMARY KEY,
                created_at  TEXT NOT NULL,
                entry_count INTEGER NOT NULL,
                file_path   TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_entries_scraped
                ON entries (scraped_at);
            CREATE INDEX IF NOT EXISTS idx_entries_digest
                ON entries (digest_id);
        """)
        self.conn.commit()

    def insert_entries(self, entries: list[Entry]) -> list[Entry]:
        """Insert entries, returning only the NEW ones (not already in DB)."""
        new: list[Entry] = []
        for entry in entries:
            try:
                self.conn.execute(
                    """INSERT INTO entries
                       (id, source_name, category, title, url, summary, published, scraped_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        entry.id,
                        entry.source_name,
                        entry.category,
                        entry.title,
                        entry.url,
                        entry.summary,
                        entry.published.isoformat(),
                        entry.scraped_at.isoformat(),
                    ),
                )
                new.append(entry)
            except sqlite3.IntegrityError:
                pass  # already seen
        self.conn.commit()
        return new

    def get_undigested_entries(self, max_age_days: int | None = None) -> list[dict]:
        """Return entries not yet included in a digest, optionally filtered by age."""
        if max_age_days is not None:
            cutoff = datetime.now(timezone.utc) - __import__("datetime").timedelta(days=max_age_days)
            rows = self.conn.execute(
                "SELECT * FROM entries WHERE digest_id IS NULL AND published >= ? ORDER BY published DESC",
                (cutoff.isoformat(),),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM entries WHERE digest_id IS NULL ORDER BY published DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def mark_digested(self, entry_ids: list[str], digest_id: str) -> None:
        if not entry_ids:
            return
        placeholders = ",".join("?" * len(entry_ids))
        self.conn.execute(
            f"UPDATE entries SET digest_id = ? WHERE id IN ({placeholders})",
            [digest_id, *entry_ids],
        )
        self.conn.commit()

    def record_digest(self, digest_id: str, entry_count: int, file_path: str) -> None:
        self.conn.execute(
            "INSERT INTO digests (id, created_at, entry_count, file_path) VALUES (?, ?, ?, ?)",
            (digest_id, datetime.now(timezone.utc).isoformat(), entry_count, file_path),
        )
        self.conn.commit()

    def digest_sent_today(self) -> bool:
        """Return True if a digest was already recorded today (UTC)."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        count = self.conn.execute(
            "SELECT COUNT(*) FROM digests WHERE created_at >= ?",
            (f"{today}T00:00:00+00:00",),
        ).fetchone()[0]
        return count > 0

    def stats(self) -> dict:
        total = self.conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        undigested = self.conn.execute(
            "SELECT COUNT(*) FROM entries WHERE digest_id IS NULL"
        ).fetchone()[0]
        digests = self.conn.execute("SELECT COUNT(*) FROM digests").fetchone()[0]
        return {"total_entries": total, "undigested": undigested, "digests_created": digests}

    def close(self) -> None:
        self.conn.close()
