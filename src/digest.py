"""Compile new entries into a formatted Markdown + HTML digest."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


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

    # Group entries by category
    by_category: dict[str, list[dict]] = defaultdict(list)
    for entry in entries:
        by_category[entry["category"]].append(entry)

    # Category display order and labels
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
            # Group by source within category
            by_source: dict[str, list[dict]] = defaultdict(list)
            for item in items:
                by_source[item["source_name"]].append(item)
            sections.append({
                "label": label,
                "key": cat_key,
                "sources": dict(by_source),
                "count": len(items),
            })

    context = {
        "digest_id": digest_id,
        "date": date_str,
        "generated_at": now.isoformat(),
        "total_entries": len(entries),
        "sections": sections,
    }

    # --- Markdown ---
    md_lines = [
        f"# Agentic AI Digest — {date_str}",
        f"",
        f"> {len(entries)} new items across {len(sections)} categories",
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
                md_lines.append(f"- **[{title}]({url})**")
                if summary:
                    # Indent summary under the bullet
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
        # Fallback: wrap markdown in minimal HTML
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

    context = {
        "digest_id": digest_id,
        "date": now.strftime("%Y-%m-%d"),
        "generated_at": now.isoformat(),
        "total_entries": len(entries),
        "sections": sections,
    }

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
    template = env.get_template("digest_email.html")
    return template.render(**context)
