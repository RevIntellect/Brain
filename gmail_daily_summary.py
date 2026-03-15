#!/usr/bin/env python3
"""
Gmail Daily Summary Generator

Connects to one or more Gmail accounts via the Gmail API, fetches today's
important emails, categorizes them, and outputs a JSON file that the
gmail-summary.html dashboard can display.

Setup:
  1. Enable the Gmail API at https://console.cloud.google.com/apis
  2. Create OAuth 2.0 credentials (Desktop app) and download as credentials.json
  3. pip install -r requirements.txt
  4. python gmail_daily_summary.py

On first run, a browser window will open for OAuth consent per account.
Tokens are cached in tokens/ so subsequent runs are non-interactive.
"""

import argparse
import base64
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from email.utils import parseaddr
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
SCRIPT_DIR = Path(__file__).parent.resolve()
TOKEN_DIR = SCRIPT_DIR / "tokens"
OUTPUT_FILE = SCRIPT_DIR / "gmail_summary.json"
CREDENTIALS_FILE = SCRIPT_DIR / "credentials.json"

# Category keywords (lowercase)
MEETING_KEYWORDS = [
    "invite", "calendar", "meeting", "zoom", "teams", "webex",
    "google meet", "agenda", "rsvp", "scheduled", "join us",
]
NEWSLETTER_KEYWORDS = [
    "unsubscribe", "newsletter", "digest", "weekly update",
    "daily brief", "subscription", "mailing list",
]


def authenticate(account_name: str) -> Credentials:
    """Authenticate a Gmail account and return credentials."""
    TOKEN_DIR.mkdir(exist_ok=True)
    token_path = TOKEN_DIR / f"{account_name}.json"
    creds = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                print(f"Error: {CREDENTIALS_FILE} not found.")
                print("Download OAuth credentials from Google Cloud Console.")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            print(f"\n--- Authenticating account: {account_name} ---")
            creds = flow.run_local_server(port=0)

        token_path.write_text(creds.to_json())

    return creds


def get_todays_messages(service, hours_back: int = 24, max_results: int = 100):
    """Fetch messages from the last N hours."""
    after = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    query = f"after:{after.strftime('%Y/%m/%d')}"

    results = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )
    return results.get("messages", [])


def get_message_detail(service, msg_id: str) -> dict:
    """Fetch full message metadata and snippet."""
    msg = (
        service.users()
        .messages()
        .get(userId="me", id=msg_id, format="metadata",
             metadataHeaders=["From", "To", "Subject", "Date"])
        .execute()
    )
    return msg


def parse_message(msg: dict, account_name: str) -> dict:
    """Parse a Gmail message into a structured dict."""
    headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
    snippet = msg.get("snippet", "")
    labels = msg.get("labelIds", [])

    from_raw = headers.get("from", "")
    from_name, from_email = parseaddr(from_raw)
    from_display = from_name if from_name else from_email

    # Parse date
    date_str = headers.get("date", "")
    time_display = ""
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(date_str)
        time_display = dt.strftime("%-I:%M %p")
    except Exception:
        time_display = date_str[:16] if date_str else ""

    # Determine category
    category = categorize(headers, snippet, labels)

    # Determine if unread
    unread = "UNREAD" in labels

    # Clean label names
    clean_labels = []
    for l in labels:
        if l.startswith("CATEGORY_"):
            clean_labels.append(l.replace("CATEGORY_", "").title())
        elif l not in ("UNREAD", "INBOX", "IMPORTANT", "SENT", "DRAFT", "SPAM", "TRASH", "STARRED"):
            clean_labels.append(l.replace("Label_", "").replace("_", " "))

    return {
        "id": msg["id"],
        "account": account_name,
        "from": from_display,
        "from_email": from_email,
        "to": headers.get("to", ""),
        "subject": headers.get("subject", "(no subject)"),
        "snippet": snippet,
        "time": time_display,
        "date": date_str,
        "category": category,
        "unread": unread,
        "labels": clean_labels,
        "is_important": "IMPORTANT" in labels,
        "is_starred": "STARRED" in labels,
    }


def categorize(headers: dict, snippet: str, labels: list) -> str:
    """Categorize an email based on content signals."""
    subject = headers.get("subject", "").lower()
    combined = f"{subject} {snippet}".lower()

    # Important / starred
    if "IMPORTANT" in labels or "STARRED" in labels:
        return "important"

    # Meetings / calendar
    if any(kw in combined for kw in MEETING_KEYWORDS):
        return "meeting"

    # Action required signals
    action_signals = [
        "action required", "please review", "need your", "can you",
        "could you", "urgent", "asap", "deadline", "by eod", "by end of day",
        "follow up", "response needed", "awaiting your", "time sensitive",
    ]
    if any(sig in combined for sig in action_signals):
        return "action"

    # Newsletters
    if any(kw in combined for kw in NEWSLETTER_KEYWORDS):
        return "newsletter"

    # Updates (notifications, automated)
    if "CATEGORY_UPDATES" in labels or "CATEGORY_SOCIAL" in labels:
        return "update"
    update_signals = ["notification", "alert", "automated", "noreply", "no-reply"]
    from_addr = headers.get("from", "").lower()
    if any(sig in from_addr for sig in update_signals):
        return "update"

    return "other"


def run(accounts: list[str], hours_back: int = 24, max_results: int = 100):
    """Main execution: fetch and summarize emails from all accounts."""
    all_emails = []

    for account_name in accounts:
        print(f"Fetching emails for: {account_name}")
        creds = authenticate(account_name)
        service = build("gmail", "v1", credentials=creds)

        messages = get_todays_messages(service, hours_back, max_results)
        print(f"  Found {len(messages)} messages in last {hours_back}h")

        for msg_stub in messages:
            try:
                msg = get_message_detail(service, msg_stub["id"])
                parsed = parse_message(msg, account_name)
                all_emails.append(parsed)
            except Exception as e:
                print(f"  Warning: Failed to parse message {msg_stub['id']}: {e}")

    # Sort: important first, then by time (newest first)
    priority_order = {"important": 0, "action": 1, "meeting": 2, "update": 3, "newsletter": 4, "other": 5}
    all_emails.sort(key=lambda e: (priority_order.get(e["category"], 9), not e["unread"]))

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "accounts": accounts,
        "total": len(all_emails),
        "important_count": sum(1 for e in all_emails if e["category"] == "important"),
        "action_count": sum(1 for e in all_emails if e["category"] == "action"),
        "emails": all_emails,
    }

    OUTPUT_FILE.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\nSummary written to {OUTPUT_FILE}")
    print(f"  Total: {summary['total']} emails")
    print(f"  Important: {summary['important_count']}")
    print(f"  Needs Reply: {summary['action_count']}")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Gmail Daily Summary Generator")
    parser.add_argument(
        "accounts", nargs="*", default=["primary"],
        help="Account names (used for token storage). Default: primary"
    )
    parser.add_argument(
        "--hours", type=int, default=24,
        help="Look back N hours (default: 24)"
    )
    parser.add_argument(
        "--max", type=int, default=100,
        help="Max messages per account (default: 100)"
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Output JSON file path (default: gmail_summary.json)"
    )
    args = parser.parse_args()

    if args.output:
        global OUTPUT_FILE
        OUTPUT_FILE = Path(args.output)

    run(args.accounts, args.hours, args.max)


if __name__ == "__main__":
    main()
