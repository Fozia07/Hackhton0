"""
Gmail Watcher - Email Monitoring
Silver Tier Component

Monitors Gmail inbox for new emails using Gmail API.
Creates task files in the vault for processing.

Based on: Skills/gmail_watcher.md

Setup Required:
1. Create Google Cloud Project
2. Enable Gmail API
3. Create OAuth 2.0 credentials
4. Download credentials.json to secure location
5. Set GMAIL_CREDENTIALS_PATH environment variable
"""

import os
import sys
import time
import json
import base64
from datetime import datetime
from pathlib import Path
from email.utils import parsedate_to_datetime

# Configuration
BASE_DIR = Path(__file__).parent.parent
VAULT_DIR = BASE_DIR / "AI_Employee_Vault"
INBOX_EMAIL_DIR = VAULT_DIR / "Inbox" / "email"
NEEDS_ACTION_EMAIL_DIR = VAULT_DIR / "Needs_Action" / "email"
LOGS_DIR = VAULT_DIR / "Logs"
CREDENTIALS_PATH = os.environ.get("GMAIL_CREDENTIALS_PATH", "")
TOKEN_PATH = BASE_DIR / "secrets" / "gmail_token.json"
POLL_INTERVAL = 120  # seconds (2 minutes)

# Priority keywords
CRITICAL_KEYWORDS = ["urgent", "asap", "emergency", "critical", "immediately"]
HIGH_KEYWORDS = ["important", "priority", "deadline", "invoice", "payment"]
BUSINESS_KEYWORDS = ["proposal", "contract", "meeting", "client", "project"]

# Track processed emails
PROCESSED_FILE = LOGS_DIR / "processed_emails.json"


def log(message, level="INFO"):
    """Print a timestamped log message."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")


def load_processed_emails():
    """Load list of already processed email IDs."""
    if PROCESSED_FILE.exists():
        with open(PROCESSED_FILE, "r") as f:
            try:
                return set(json.load(f))
            except json.JSONDecodeError:
                return set()
    return set()


def save_processed_emails(processed_ids):
    """Save list of processed email IDs."""
    with open(PROCESSED_FILE, "w") as f:
        json.dump(list(processed_ids), f)


def determine_priority(subject, snippet):
    """Determine email priority based on keywords."""
    text = (subject + " " + snippet).lower()

    for keyword in CRITICAL_KEYWORDS:
        if keyword in text:
            return "critical"

    for keyword in HIGH_KEYWORDS:
        if keyword in text:
            return "high"

    for keyword in BUSINESS_KEYWORDS:
        if keyword in text:
            return "medium"

    return "low"


def create_email_task(email_data):
    """Create a task file for an email."""
    email_id = email_data["id"]
    sender = email_data.get("from", "Unknown")
    subject = email_data.get("subject", "No Subject")
    snippet = email_data.get("snippet", "")
    received = email_data.get("date", datetime.now().isoformat())
    labels = email_data.get("labels", [])

    priority = determine_priority(subject, snippet)

    # Create filename
    safe_subject = "".join(c for c in subject[:30] if c.isalnum() or c in " -_").strip()
    filename = f"EMAIL_{email_id[:8]}_{safe_subject}.md"
    filepath = NEEDS_ACTION_EMAIL_DIR / filename

    content = f"""---
type: email
email_id: {email_id}
from: {sender}
subject: {subject}
received: {received}
priority: {priority}
status: pending
labels: {labels}
---

# Email: {subject}

## From
{sender}

## Received
{received}

## Preview
{snippet}

## Priority
**{priority.upper()}**

## Suggested Actions
- [ ] Reply to sender
- [ ] Forward to relevant party
- [ ] Create follow-up task
- [ ] Archive after processing

---
*Detected by Gmail Watcher*
*Created: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
"""

    with open(filepath, "w") as f:
        f.write(content)

    log(f"Created task: {filename} (Priority: {priority})")
    return filepath


def get_gmail_service():
    """Initialize Gmail API service."""
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

        creds = None

        # Load existing token
        if TOKEN_PATH.exists():
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

        # Refresh or get new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not CREDENTIALS_PATH or not Path(CREDENTIALS_PATH).exists():
                    log("Gmail credentials not found. Set GMAIL_CREDENTIALS_PATH", "ERROR")
                    return None
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
                creds = flow.run_local_server(port=0)

            # Save token
            TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(TOKEN_PATH, "w") as token:
                token.write(creds.to_json())

        return build("gmail", "v1", credentials=creds)

    except ImportError:
        log("Gmail API libraries not installed. Run: pip install google-auth-oauthlib google-api-python-client", "ERROR")
        return None
    except Exception as e:
        log(f"Gmail API error: {e}", "ERROR")
        return None


def fetch_emails(service, max_results=10):
    """Fetch unread emails from Gmail."""
    try:
        # Query for unread important emails
        results = service.users().messages().list(
            userId="me",
            q="is:unread",
            maxResults=max_results
        ).execute()

        messages = results.get("messages", [])
        emails = []

        for msg in messages:
            # Get full message
            message = service.users().messages().get(
                userId="me",
                id=msg["id"],
                format="full"
            ).execute()

            # Extract headers
            headers = {}
            for header in message["payload"]["headers"]:
                headers[header["name"].lower()] = header["value"]

            email_data = {
                "id": msg["id"],
                "from": headers.get("from", "Unknown"),
                "subject": headers.get("subject", "No Subject"),
                "date": headers.get("date", ""),
                "snippet": message.get("snippet", ""),
                "labels": message.get("labelIds", [])
            }
            emails.append(email_data)

        return emails

    except Exception as e:
        log(f"Error fetching emails: {e}", "ERROR")
        return []


def simulate_emails():
    """Generate simulated emails for testing without API."""
    import random

    sample_emails = [
        {
            "id": f"sim_{datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(1000,9999)}",
            "from": "client@example.com",
            "subject": "URGENT: Invoice Payment Required",
            "date": datetime.now().isoformat(),
            "snippet": "Please process the attached invoice as soon as possible. Payment is due by end of week.",
            "labels": ["INBOX", "IMPORTANT"]
        },
        {
            "id": f"sim_{datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(1000,9999)}",
            "from": "partner@business.com",
            "subject": "Meeting Request: Project Discussion",
            "date": datetime.now().isoformat(),
            "snippet": "Would like to schedule a meeting to discuss the upcoming project milestones.",
            "labels": ["INBOX"]
        },
        {
            "id": f"sim_{datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(1000,9999)}",
            "from": "newsletter@updates.com",
            "subject": "Weekly Newsletter",
            "date": datetime.now().isoformat(),
            "snippet": "Here's your weekly roundup of industry news and updates.",
            "labels": ["INBOX"]
        }
    ]

    # Return 1-2 random emails
    return random.sample(sample_emails, random.randint(1, 2))


def run_gmail_watcher(simulation_mode=False):
    """Main Gmail watcher loop."""
    print("=" * 60)
    print("Silver Tier - Gmail Watcher")
    print("Email Monitoring System")
    print("=" * 60)

    if simulation_mode:
        print("MODE: Simulation (no real API calls)")
    else:
        print("MODE: Live Gmail API")

    print(f"Output: {NEEDS_ACTION_EMAIL_DIR}")
    print(f"Poll Interval: {POLL_INTERVAL} seconds")
    print("=" * 60)
    print("Watching for emails... (Press Ctrl+C to stop)")
    print()

    # Ensure directories exist
    NEEDS_ACTION_EMAIL_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # Load processed emails
    processed_ids = load_processed_emails()

    # Initialize Gmail service if not simulation
    service = None
    if not simulation_mode:
        service = get_gmail_service()
        if not service:
            log("Falling back to simulation mode", "WARN")
            simulation_mode = True

    while True:
        try:
            # Fetch emails
            if simulation_mode:
                emails = simulate_emails()
                log(f"Simulated {len(emails)} email(s)")
            else:
                emails = fetch_emails(service)
                log(f"Fetched {len(emails)} unread email(s)")

            # Process new emails
            new_count = 0
            for email in emails:
                if email["id"] not in processed_ids:
                    create_email_task(email)
                    processed_ids.add(email["id"])
                    new_count += 1

            if new_count > 0:
                log(f"Created {new_count} new task(s)")
                save_processed_emails(processed_ids)

            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print("\n")
            log("Gmail watcher stopped.")
            save_processed_emails(processed_ids)
            break
        except Exception as e:
            log(f"Error: {e}", "ERROR")
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    # Check for simulation flag
    simulation_mode = "--simulate" in sys.argv or "-s" in sys.argv

    if not simulation_mode and not CREDENTIALS_PATH:
        log("No Gmail credentials found.", "WARN")
        log("Running in simulation mode. Use --simulate flag explicitly.", "WARN")
        log("To use real Gmail API:", "INFO")
        log("  1. Set GMAIL_CREDENTIALS_PATH environment variable", "INFO")
        log("  2. Install: pip install google-auth-oauthlib google-api-python-client", "INFO")
        simulation_mode = True

    run_gmail_watcher(simulation_mode=simulation_mode)
