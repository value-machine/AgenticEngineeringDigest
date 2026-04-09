# Agentic Engineers Digest

Manage the agentic AI news digest pipeline. Run this command to scrape sources, generate digests, send emails, or adjust settings.

## What to do

Based on the user's input "$ARGUMENTS", determine and execute the appropriate action:

### If the user wants to **send a digest now** (e.g., "send", "email", "now", or no arguments):
1. Run: `python -m src.main run --email` from the project directory `C:/Users/Lenovo/Documents/AppDev/agentic-engineers-digest`
2. This scrapes all sources, generates a digest, and emails it to the configured recipients.

### If the user wants to **scrape only** (e.g., "scrape", "fetch"):
1. Run: `python -m src.main run --no-digest`

### If the user wants to **generate without emailing** (e.g., "generate", "build", "compile"):
1. Run: `python -m src.main run --no-scrape`
2. Tell them where the output files are (in the `output/` directory).

### If the user wants to **re-send an existing digest** (e.g., "resend", "re-send"):
1. Find the latest HTML file in `output/` directory.
2. Run: `python -m src.main send-digest --html <path>`

### If the user wants to **check status** (e.g., "status", "stats"):
1. Run: `python -m src.main stats`
2. Run: `python -m src.main settings`

### If the user wants to **change settings** (e.g., "settings", "configure", "change"):
Settings are in `config/settings.json`. Here's what they can adjust:

- **Recipients**: `email.recipients` -- array of email addresses, e.g., `["tom@tmi.one", "alice@example.com"]`
- **Digest frequency**: `schedule.digest_frequency` -- `"weekly"` or `"daily"`
- **Digest day**: `schedule.digest_day` -- `"Monday"`, `"Wednesday"`, etc. (only matters for weekly)
- **Digest time**: `schedule.digest_time_utc` -- e.g., `"07:15"` (also update the cron in `.github/workflows/digest.yml`)
- **From address**: `email.from` -- requires a verified domain on resend.com for custom addresses
- **API key**: `email.resend_api_key` -- from your Resend dashboard

Read the current `config/settings.json`, apply the requested change, and write it back.

If they also want to change the **GitHub Actions schedule**, update the cron expressions in `.github/workflows/digest.yml`:
- Daily scrape cron: `"0 7 * * *"` (first entry)
- Weekly digest cron: `"15 7 * * 1"` (second entry, where `1` = Monday, `0` = Sunday, etc.)

### If the user wants to **list sources** (e.g., "sources", "list"):
1. Run: `python -m src.main sources`

### If the user asks **how it works**:
Explain: Daily scraping captures ephemeral content (Reddit top posts, GitHub trending). All entries are stored in a SQLite database with deduplication. Once per week, all undigested entries are compiled into a Markdown + HTML digest and emailed via Resend. The pipeline can run locally via CLI or automatically via GitHub Actions.
