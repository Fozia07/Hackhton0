#!/usr/bin/env python3
"""
Platinum Tier - Cloud Agent
Runs 24/7 on cloud VM, creates drafts only.

Responsibilities:
- Claim email/social tasks from Needs_Action
- Create draft replies (NEVER send)
- Create social post drafts (NEVER post)
- Write updates for Local agent

Usage:
    python3 cloud_agent.py           # Run continuous
    python3 cloud_agent.py --once    # Single cycle
    python3 cloud_agent.py --dry-run # Test mode
"""

import os
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.claim_manager import get_claim_manager, ClaimStatus
from utils.agent_coordinator import get_coordinator

# Paths (support Docker environment)
BASE_DIR = Path(__file__).parent.parent
VAULT_DIR = Path(os.environ.get("VAULT_PATH", BASE_DIR / "AI_Employee_Vault"))
NEEDS_ACTION = VAULT_DIR / "Needs_Action"
PENDING_APPROVAL = VAULT_DIR / "Pending_Approval"
DRAFTS = VAULT_DIR / "Drafts"

# Ensure folders exist
PENDING_APPROVAL.mkdir(exist_ok=True)
DRAFTS.mkdir(exist_ok=True)


def log(msg):
    """Simple logging."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [CLOUD] {msg}")


class CloudAgent:
    """Cloud Agent - Draft creation only."""

    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.claim_manager = get_claim_manager("cloud")
        self.coordinator = get_coordinator("cloud")
        self.running = False

    def get_tasks(self):
        """Get claimable email/social tasks."""
        tasks = []

        # Check root Needs_Action
        for f in NEEDS_ACTION.glob("*.md"):
            if self._is_my_task(f.name):
                tasks.append({"filename": f.name, "path": f, "folder": None})

        # Check subfolders
        for subfolder in ["email", "general"]:
            folder_path = NEEDS_ACTION / subfolder
            if folder_path.exists():
                for f in folder_path.glob("*.md"):
                    if self._is_my_task(f.name):
                        tasks.append({"filename": f.name, "path": f, "folder": subfolder})

        return tasks

    def _is_my_task(self, filename):
        """Check if this is an email or social task (Cloud's domain)."""
        name = filename.upper()
        return any(x in name for x in ["EMAIL", "FACEBOOK", "TWITTER", "LINKEDIN", "INSTAGRAM", "SOCIAL"])

    def process_task(self, task):
        """Process a single task - create draft."""
        filename = task["filename"]
        filepath = task["path"]
        folder = task["folder"]

        log(f"Processing: {filename}")

        # Claim task
        status, msg = self.claim_manager.claim_task(filename, folder)
        if status != ClaimStatus.SUCCESS:
            log(f"  Skip: {msg}")
            return False

        log(f"  Claimed successfully")

        try:
            # Read content
            content = filepath.read_text() if filepath.exists() else ""

            # Detect task type
            name_upper = filename.upper()
            if "EMAIL" in name_upper:
                draft = self._create_email_draft(filename, content)
            else:
                draft = self._create_social_draft(filename, content)

            # Save draft to Pending_Approval
            if not self.dry_run:
                draft_filename = f"DRAFT_{filename}"
                draft_path = PENDING_APPROVAL / draft_filename
                draft_path.write_text(draft)
                log(f"  Draft saved: {draft_filename}")

                # Send signal to Local
                self.coordinator.send_signal(
                    "approval_needed", "local",
                    {"task": filename, "draft": draft_filename}
                )

            # Release task
            self.claim_manager.release_task(filename, "pending_approval")
            log(f"  Released to Pending_Approval")

            # Write update
            self.coordinator.write_update("task_drafted", {
                "task": filename,
                "type": "email" if "EMAIL" in name_upper else "social"
            })

            return True

        except Exception as e:
            log(f"  Error: {e}")
            self.claim_manager.release_task(filename, "needs_action")
            return False

    def _create_email_draft(self, filename, content):
        """Create email draft reply."""
        now = datetime.now().isoformat()

        return f"""---
type: email_draft
original_task: {filename}
created_by: cloud_agent
created_at: {now}
status: pending_approval
action_required: send_email
---

# Email Draft - Awaiting Approval

**Original Task:** {filename}
**Created By:** Cloud Agent
**Created At:** {now}

## Draft Reply

Dear [Recipient],

Thank you for your message. I am reviewing your request and will respond shortly.

Best regards,
AI Employee

---

## Original Content

{content}

---

## Instructions

- Move to `/Approved/` to send this email
- Move to `/Rejected/` to discard
- Edit content above before approving if needed
"""

    def _create_social_draft(self, filename, content):
        """Create social media post draft."""
        now = datetime.now().isoformat()

        # Detect platform
        name_upper = filename.upper()
        if "FACEBOOK" in name_upper:
            platform = "Facebook"
        elif "TWITTER" in name_upper:
            platform = "Twitter"
        elif "LINKEDIN" in name_upper:
            platform = "LinkedIn"
        elif "INSTAGRAM" in name_upper:
            platform = "Instagram"
        else:
            platform = "Social Media"

        return f"""---
type: social_draft
platform: {platform.lower()}
original_task: {filename}
created_by: cloud_agent
created_at: {now}
status: pending_approval
action_required: post_to_{platform.lower()}
---

# {platform} Post Draft - Awaiting Approval

**Platform:** {platform}
**Created By:** Cloud Agent
**Created At:** {now}

## Draft Post

{content if content.strip() else "[Cloud Agent would generate content here based on business goals]"}

---

## Instructions

- Move to `/Approved/` to publish this post
- Move to `/Rejected/` to discard
- Edit content above before approving if needed
"""

    def run_cycle(self):
        """Run one processing cycle."""
        log("=== Starting cycle ===")

        # Update heartbeat
        self.coordinator.update_heartbeat()

        # Get tasks
        tasks = self.get_tasks()
        log(f"Found {len(tasks)} tasks")

        processed = 0
        for task in tasks[:5]:  # Limit per cycle
            if self.process_task(task):
                processed += 1

        log(f"Cycle complete: {processed} tasks processed")
        return processed

    def run(self, interval=60):
        """Run continuous loop."""
        self.running = True
        log("Starting Cloud Agent (Ctrl+C to stop)")

        try:
            while self.running:
                self.run_cycle()
                log(f"Sleeping {interval}s...")
                time.sleep(interval)
        except KeyboardInterrupt:
            log("Shutting down...")
        finally:
            self.running = False


def main():
    parser = argparse.ArgumentParser(description="Cloud Agent")
    parser.add_argument("--once", action="store_true", help="Single cycle")
    parser.add_argument("--dry-run", action="store_true", help="Test mode")
    parser.add_argument("--interval", type=int, default=60, help="Cycle interval")
    args = parser.parse_args()

    agent = CloudAgent(dry_run=args.dry_run)

    if args.once:
        agent.run_cycle()
    else:
        agent.run(interval=args.interval)


if __name__ == "__main__":
    main()
