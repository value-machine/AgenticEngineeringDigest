"""Compile new entries into a formatted Markdown + HTML digest."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def _format_published(raw: str) -> str:
    """Parse an ISO date string and return a short display date like 'Apr 7'."""
    try:
        dt = datetime.fromisoformat(raw)
        return dt.strftime("%b %-d")
    except Exception:
        try:
            # Windows strftime doesn't support %-d
            dt = datetime.fromisoformat(raw)
            return dt.strftime("%b %d").replace(" 0", " ")
        except Exception:
            return ""


def _compute_date_range(entries: list[dict]) -> tuple[str, str]:
    """Return (oldest_date, newest_date) as display strings from entry published fields."""
    dates = []
    for e in entries:
        try:
            dt = datetime.fromisoformat(e["published"])
            # Normalize to UTC-aware for consistent comparison
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            dates.append(dt)
        except Exception:
            pass
    if not dates:
        now = datetime.now(timezone.utc)
        return now.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d")
    oldest = min(dates)
    newest = max(dates)
    return oldest.strftime("%b %d, %Y").replace(" 0", " "), newest.strftime("%b %d, %Y").replace(" 0", " ")


def _prepare_sections(entries: list[dict]) -> list[dict]:
    """Group entries by category and source, adding formatted dates."""
    # Add display date to each entry
    for entry in entries:
        entry["display_date"] = _format_published(entry.get("published", ""))

    by_category: dict[str, list[dict]] = defaultdict(list)
    for entry in entries:
        by_category[entry["category"]].append(entry)

    category_labels = {
        "newsletter": "Newsletters",
        "podcast": "Podcasts",
        "community": "Community (Reddit)",
        "paper_tracking": "Papers",
        "github_tracking": "GitHub Trending",
        "youtube": "YouTube",
        "twitter": "X / Twitter",
    }

    sections: list[dict] = []
    for cat_key, label in category_labels.items():
        items = by_category.get(cat_key, [])
        if items:
            by_source: dict[str, list[dict]] = defaultdict(list)
            for item in items:
                by_source[item["source_name"]].append(item)
            sections.append({
                "label": label,
                "key": cat_key,
                "sources": dict(by_source),
                "count": len(items),
            })

    return sections


def generate_digest(
    entries: list[dict],
    output_dir: Path = OUTPUT_DIR,
) -> tuple[str, Path, Path] | None:
    """Generate Markdown and HTML digest files. Returns (digest_id, md_path, html_path) or None."""
    if not entries:
        return None

    output_dir.mkdir(parents=True, exist_ok=True)

    digest_id = uuid.uuid4().hex[:8]
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H%M")

    sections = _prepare_sections(entries)
    oldest, newest = _compute_date_range(entries)

    context = {
        "digest_id": digest_id,
        "date": date_str,
        "generated_at": now.isoformat(),
        "total_entries": len(entries),
        "date_range_from": oldest,
        "date_range_to": newest,
        "sections": sections,
    }

    # --- Markdown ---
    md_lines = [
        f"# Agentic AI Digest -- {date_str}",
        f"",
        f"> {len(entries)} items from **{oldest}** to **{newest}**",
        f"> Generated: {now.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
    ]

    for section in sections:
        md_lines.append(f"## {section['label']} ({section['count']})")
        md_lines.append("")
        for source_name, items in section["sources"].items():
            md_lines.append(f"### {source_name}")
            md_lines.append("")
            for item in items:
                title = item["title"]
                url = item["url"]
                summary = item.get("summary", "")
                pub_date = item.get("display_date", "")
                date_prefix = f"[{pub_date}] " if pub_date else ""
                md_lines.append(f"- {date_prefix}**[{title}]({url})**")
                if summary:
                    md_lines.append(f"  {summary}")
                md_lines.append("")
        md_lines.append("---")
        md_lines.append("")

    md_content = "\n".join(md_lines)
    md_path = output_dir / f"digest-{date_str}-{time_str}.md"
    md_path.write_text(md_content, encoding="utf-8")

    # --- HTML ---
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
    try:
        template = env.get_template("digest.html")
        html_content = template.render(**context)
    except Exception:
        html_content = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Digest {date_str}</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 780px; margin: 2rem auto; padding: 0 1rem; line-height: 1.6; color: #1a1a1a; }}
a {{ color: #2563eb; }} h1 {{ border-bottom: 2px solid #e5e7eb; padding-bottom: .5rem; }}
h2 {{ color: #4b5563; margin-top: 2rem; }} h3 {{ color: #6b7280; }}
blockquote {{ border-left: 3px solid #d1d5db; margin: 0; padding-left: 1rem; color: #6b7280; }}
li {{ margin-bottom: .5rem; }}
</style></head><body>
<pre style="white-space:pre-wrap">{md_content}</pre>
</body></html>"""

    html_path = output_dir / f"digest-{date_str}-{time_str}.html"
    html_path.write_text(html_content, encoding="utf-8")

    return digest_id, md_path, html_path


def render_email_html(entries: list[dict]) -> str:
    """Render entries as email-optimized HTML (inline styles, no CSS variables)."""
    now = datetime.now(timezone.utc)
    digest_id = uuid.uuid4().hex[:8]

    sections = _prepare_sections(entries)
    oldest, newest = _compute_date_range(entries)

    context = {
        "digest_id": digest_id,
        "date": now.strftime("%Y-%m-%d"),
        "generated_at": now.isoformat(),
        "total_entries": len(entries),
        "date_range_from": oldest,
        "date_range_to": newest,
        "sections": sections,
    }

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
    template = env.get_template("digest_email.html")
    return template.render(**context)
