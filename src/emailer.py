"""Send digest emails via the Resend API."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
from rich.console import Console

console = Console(force_terminal=True)

SETTINGS_PATH = Path(__file__).resolve().parent.parent / "config" / "settings.json"
RESEND_URL = "https://api.resend.com/emails"


def load_email_settings() -> dict:
    with open(SETTINGS_PATH, encoding="utf-8") as f:
        return json.load(f)["email"]


def send_digest_email(
    html_content: str,
    subject: str,
    *,
    recipients: list[str] | None = None,
    api_key: str | None = None,
    from_addr: str | None = None,
) -> bool:
    """Send an HTML digest email via Resend. Returns True on success."""
    settings = load_email_settings()

    api_key = api_key or settings.get("resend_api_key", "")
    recipients = recipients or settings.get("recipients", [])
    from_addr = from_addr or settings.get("from", "onboarding@resend.dev")

    if not api_key:
        console.print("[red]No Resend API key found.[/red] Set it in config/settings.json")
        return False
    if not recipients:
        console.print("[red]No recipients configured.[/red] Set them in config/settings.json")
        return False

    payload = {
        "from": from_addr,
        "to": recipients,
        "subject": subject,
        "html": html_content,
    }

    try:
        resp = httpx.post(
            RESEND_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        console.print(f"  [green]Email sent[/green] to {', '.join(recipients)} (id: {data.get('id', '?')})")
        return True
    except httpx.HTTPStatusError as exc:
        body = exc.response.text
        console.print(f"  [red]Email failed[/red] ({exc.response.status_code}): {body}")
        return False
    except httpx.HTTPError as exc:
        console.print(f"  [red]Email failed[/red]: {exc}")
        return False
