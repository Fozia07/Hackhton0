"""
Approval Watcher - Human-in-the-Loop Workflow
Silver Tier Component

Monitors Pending_Approval folder and processes files
when they are moved to Approved or Rejected folders.

Based on: Skills/approval_workflow.md
"""

import os
import shutil
import time
import json
from datetime import datetime
from pathlib import Path

# Configuration
BASE_DIR = Path(__file__).parent.parent
VAULT_DIR = BASE_DIR / "AI_Employee_Vault"
PENDING_DIR = VAULT_DIR / "Pending_Approval"
APPROVED_DIR = VAULT_DIR / "Approved"
REJECTED_DIR = VAULT_DIR / "Rejected"
DONE_DIR = VAULT_DIR / "Done"
LOGS_DIR = VAULT_DIR / "Logs"
POLL_INTERVAL = 3  # seconds


def log(message, level="INFO"):
    """Print a timestamped log message."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")


def log_to_file(action_type, filename, status, details=""):
    """Log approval actions to daily log file."""
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = LOGS_DIR / f"{today}_approvals.json"

    entry = {
        "timestamp": datetime.now().isoformat(),
        "action_type": action_type,
        "filename": filename,
        "status": status,
        "details": details
    }

    # Load existing log or create new
    if log_file.exists():
        with open(log_file, "r") as f:
            try:
                log_data = json.load(f)
            except json.JSONDecodeError:
                log_data = {"date": today, "entries": []}
    else:
        log_data = {"date": today, "entries": []}

    log_data["entries"].append(entry)

    with open(log_file, "w") as f:
        json.dump(log_data, f, indent=2)


def parse_approval_request(filepath):
    """Parse an approval request markdown file."""
    with open(filepath, "r") as f:
        content = f.read()

    # Extract metadata from frontmatter
    metadata = {}
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            frontmatter = parts[1].strip()
            for line in frontmatter.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    metadata[key.strip()] = value.strip()

    return metadata, content


def process_approved(filename):
    """Process an approved request."""
    filepath = APPROVED_DIR / filename

    if not filepath.exists():
        return False

    log(f"Processing approved: {filename}")

    # Parse the approval request
    metadata, content = parse_approval_request(filepath)
    action_type = metadata.get("action", "unknown")

    # Log the approval
    log_to_file(action_type, filename, "approved", f"Action: {action_type}")

    # Update the file with approval timestamp
    approval_note = f"\n\n---\n\n## Approval Record\n\n"
    approval_note += f"**Approved At:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    approval_note += f"**Status:** APPROVED\n"
    approval_note += f"**Action Type:** {action_type}\n"

    with open(filepath, "a") as f:
        f.write(approval_note)

    # Move to Done
    dest = DONE_DIR / filename
    shutil.move(str(filepath), str(dest))
    log(f"Moved to Done: {filename}")

    # Trigger action based on type
    if action_type == "send_email":
        log(f"[ACTION] Email send approved - Ready for MCP execution", "ACTION")
    elif action_type == "post_linkedin":
        log(f"[ACTION] LinkedIn post approved - Ready for Playwright execution", "ACTION")
    elif action_type == "payment":
        log(f"[ACTION] Payment approved - Ready for execution", "ACTION")
    else:
        log(f"[ACTION] Generic action approved: {action_type}", "ACTION")

    return True


def process_rejected(filename):
    """Process a rejected request."""
    filepath = REJECTED_DIR / filename

    if not filepath.exists():
        return False

    log(f"Processing rejected: {filename}")

    # Parse the rejection
    metadata, content = parse_approval_request(filepath)
    action_type = metadata.get("action", "unknown")

    # Log the rejection
    log_to_file(action_type, filename, "rejected", f"Action: {action_type}")

    # Update the file with rejection timestamp
    rejection_note = f"\n\n---\n\n## Rejection Record\n\n"
    rejection_note += f"**Rejected At:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    rejection_note += f"**Status:** REJECTED\n"
    rejection_note += f"**Action Type:** {action_type}\n"

    with open(filepath, "a") as f:
        f.write(rejection_note)

    log(f"Rejection recorded: {filename}")

    return True


def get_files_in_folder(folder):
    """Get list of .md files in a folder."""
    if not folder.exists():
        return []
    return [f for f in os.listdir(folder) if f.endswith(".md")]


def create_sample_approval_request():
    """Create a sample approval request for testing."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sample_file = PENDING_DIR / f"APPROVAL_email_{timestamp}.md"

    content = f"""---
type: approval_request
request_id: APPROVAL_email_{timestamp}
action: send_email
to: client@example.com
subject: Test Email - Approval Required
created: {datetime.now().isoformat()}
status: pending
priority: medium
---

# Email Approval Request

## Summary
Request to send a test email to client.

## Action Details

- **To:** client@example.com
- **Subject:** Test Email - Approval Required
- **Body Preview:** This is a test email requiring approval...

## Instructions

**To Approve:** Move this file to `/Approved/` folder

**To Reject:** Move this file to `/Rejected/` folder

---
*Awaiting human decision*
*Generated by Approval Workflow Skill*
"""

    with open(sample_file, "w") as f:
        f.write(content)

    log(f"Created sample approval request: {sample_file.name}")
    return sample_file.name


def show_pending_summary():
    """Display summary of pending approvals."""
    pending = get_files_in_folder(PENDING_DIR)
    if pending:
        log(f"Pending approvals: {len(pending)}")
        for f in pending[:5]:  # Show first 5
            log(f"  - {f}")
        if len(pending) > 5:
            log(f"  ... and {len(pending) - 5} more")


def run_approval_watcher():
    """Main approval watcher loop."""
    print("=" * 60)
    print("Silver Tier - Approval Watcher")
    print("Human-in-the-Loop Workflow")
    print("=" * 60)
    print(f"Pending:  {PENDING_DIR}")
    print(f"Approved: {APPROVED_DIR}")
    print(f"Rejected: {REJECTED_DIR}")
    print(f"Done:     {DONE_DIR}")
    print("=" * 60)
    print("Watching for approval decisions... (Press Ctrl+C to stop)")
    print()

    # Track processed files to avoid reprocessing
    processed_approved = set()
    processed_rejected = set()

    # Initial summary
    show_pending_summary()

    while True:
        try:
            # Check for newly approved files
            approved_files = get_files_in_folder(APPROVED_DIR)
            for filename in approved_files:
                if filename not in processed_approved:
                    if process_approved(filename):
                        processed_approved.add(filename)
                    print()

            # Check for newly rejected files
            rejected_files = get_files_in_folder(REJECTED_DIR)
            for filename in rejected_files:
                if filename not in processed_rejected:
                    if process_rejected(filename):
                        processed_rejected.add(filename)
                    print()

            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print("\n")
            log("Approval watcher stopped.")
            break
        except Exception as e:
            log(f"Error: {e}", "ERROR")
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    # Ensure directories exist
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    APPROVED_DIR.mkdir(parents=True, exist_ok=True)
    REJECTED_DIR.mkdir(parents=True, exist_ok=True)
    DONE_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # Create sample approval request for testing
    create_sample_approval_request()

    # Run the watcher
    run_approval_watcher()
