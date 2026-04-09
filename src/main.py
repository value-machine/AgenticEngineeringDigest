"""CLI entry point for the agentic-engineers-digest pipeline."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from src.scrapers import SCRAPERS
from src.scrapers.base import Entry
from src.storage import Storage
from src.digest import generate_digest, render_email_html
from src.emailer import send_digest_email

console = Console(force_terminal=True)
CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "sources.json"


def load_sources(path: Path = CONFIG_PATH) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [s for s in data["sources"] if s.get("enabled", False)]


async def scrape_all(sources: list[dict]) -> list[Entry]:
    """Run all scrapers concurrently and collect entries."""
    all_entries: list[Entry] = []

    async def _scrape_one(source: dict) -> list[Entry]:
        method = source.get("scrape_method", "rss")
        scraper_cls = SCRAPERS.get(method)
        if not scraper_cls:
            console.print(f"  [yellow]?[/yellow] {source['name']}: unknown method \"{method}\"")
            return []
        scraper = scraper_cls()
        entries = await scraper.scrape(source)
        status = f"[green]+{len(entries)}[/green]" if entries else "[dim]0[/dim]"
        console.print(f"  {status}  {source['name']}")
        return entries

    tasks = [_scrape_one(s) for s in sources]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            console.print(f"  [red]X[/red] {sources[i]['name']}: {result}")
        else:
            all_entries.extend(result)

    return all_entries


@click.group()
def cli() -> None:
    """Agentic Engineers Digest — scrape, deduplicate, and compile AI news."""
    pass


@cli.command()
@click.option("--no-digest", is_flag=True, help="Scrape only, don't generate a digest.")
@click.option("--no-scrape", is_flag=True, help="Skip scraping, generate digest from accumulated entries.")
@click.option("--email", "send_email", is_flag=True, help="Email the digest after generating.")
def run(no_digest: bool, no_scrape: bool, send_email: bool) -> None:
    """Scrape sources, generate a digest, and optionally email it."""
    if no_digest and no_scrape:
        console.print("[red]Cannot use --no-digest and --no-scrape together.[/red]")
        return

    console.print("\n[bold]Agentic Engineers Digest[/bold]\n")
    store = Storage()

    # --- Scrape phase ---
    if not no_scrape:
        sources = load_sources()
        console.print(f"Scraping [cyan]{len(sources)}[/cyan] enabled sources...\n")

        entries = asyncio.run(scrape_all(sources))
        console.print(f"\nFetched [cyan]{len(entries)}[/cyan] total entries.")

        new_entries = store.insert_entries(entries)
        console.print(f"New entries: [green]{len(new_entries)}[/green]  (duplicates skipped: {len(entries) - len(new_entries)})")

        if no_digest:
            store.close()
            return

    # --- Digest phase ---
    undigested = store.get_undigested_entries()
    if not undigested:
        console.print("\n[dim]No new entries to compile. Digest skipped.[/dim]")
        store.close()
        return

    console.print(f"\nCompiling digest from [cyan]{len(undigested)}[/cyan] entries...")
    result = generate_digest(undigested)

    if result:
        digest_id, md_path, html_path = result
        entry_ids = [e["id"] for e in undigested]
        store.mark_digested(entry_ids, digest_id)
        store.record_digest(digest_id, len(undigested), str(md_path))
        console.print(f"\n[bold green]Digest ready![/bold green]")
        console.print(f"  Markdown: {md_path}")
        console.print(f"  HTML:     {html_path}")

        # --- Email phase ---
        if send_email:
            console.print("\nSending email digest...")
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            email_html = render_email_html(undigested)
            send_digest_email(
                email_html,
                subject=f"Agentic AI Weekly Digest -- {date_str}",
            )

    store.close()


@cli.command("send-digest")
@click.option("--html", "html_path", type=click.Path(exists=True), help="Path to an existing HTML digest file.")
def send_digest(html_path: str | None) -> None:
    """Send (or re-send) a digest email from an existing file or latest undigested entries."""
    if html_path:
        html_content = Path(html_path).read_text(encoding="utf-8")
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    else:
        store = Storage()
        undigested = store.get_undigested_entries()
        store.close()
        if not undigested:
            console.print("[dim]No undigested entries. Nothing to send.[/dim]")
            return
        html_content = render_email_html(undigested)
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    console.print("Sending digest email...")
    send_digest_email(
        html_content,
        subject=f"Agentic AI Weekly Digest -- {date_str}",
    )


@cli.command()
def stats() -> None:
    """Show database statistics."""
    store = Storage()
    s = store.stats()
    table = Table(title="Digest Database Stats")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green", justify="right")
    table.add_row("Total entries", str(s["total_entries"]))
    table.add_row("Undigested", str(s["undigested"]))
    table.add_row("Digests created", str(s["digests_created"]))
    console.print(table)
    store.close()


@cli.command()
def sources() -> None:
    """List all configured sources and their status."""
    with open(CONFIG_PATH, encoding="utf-8") as f:
        data = json.load(f)

    table = Table(title="Configured Sources")
    table.add_column("Source", style="bold")
    table.add_column("Category", style="cyan")
    table.add_column("Method", style="dim")
    table.add_column("Enabled", justify="center")

    for s in data["sources"]:
        enabled = "[green]yes[/green]" if s.get("enabled") else "[red]no[/red]"
        table.add_row(s["name"], s["category"], s.get("scrape_method", "---"), enabled)

    console.print(table)


@cli.command()
def settings() -> None:
    """Show current digest settings."""
    settings_path = Path(__file__).resolve().parent.parent / "config" / "settings.json"
    with open(settings_path, encoding="utf-8") as f:
        data = json.load(f)

    email = data.get("email", {})
    sched = data.get("schedule", {})

    table = Table(title="Digest Settings")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Email enabled", str(email.get("enabled", False)))
    table.add_row("Recipients", ", ".join(email.get("recipients", [])))
    table.add_row("From address", email.get("from", "—"))
    table.add_row("API key", email.get("resend_api_key", "")[:8] + "..." if email.get("resend_api_key") else "not set")
    table.add_row("Scrape frequency", sched.get("scrape_frequency", "—"))
    table.add_row("Digest frequency", sched.get("digest_frequency", "—"))
    table.add_row("Digest day", sched.get("digest_day", "—"))
    table.add_row("Digest time (UTC)", sched.get("digest_time_utc", "—"))

    console.print(table)


if __name__ == "__main__":
    cli()
