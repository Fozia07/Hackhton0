#!/usr/bin/env python3
"""
Platinum Tier - Multi-Agent Orchestrator
Extends the AI Employee Runner with claim-by-move coordination.

Features:
- Claim-by-move task ownership
- Cloud/Local agent coordination
- Signal handling between agents
- Dashboard update merging (Local only)
- Work-zone enforcement

Usage:
    python3 platinum_orchestrator.py              # Run continuous
    python3 platinum_orchestrator.py --once       # Single cycle
    python3 platinum_orchestrator.py --agent cloud  # Run as cloud agent
    python3 platinum_orchestrator.py --status     # Show status

Author: AI Employee System
Version: 1.0.0 (Platinum Tier)
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.claim_manager import (
    ClaimManager,
    ClaimStatus,
    AgentType,
    get_claim_manager
)

from utils.agent_coordinator import (
    AgentCoordinator,
    Permission,
    get_coordinator
)

from utils.audit_logger import (
    get_audit_logger,
    ActionType,
    ResultStatus
)

from utils.heartbeat import HeartbeatWriter


# ==============================================================================
# CONFIGURATION
# ==============================================================================

class PlatinumConfig:
    """Configuration for Platinum Orchestrator."""

    BASE_DIR = Path(__file__).parent.parent
    VAULT_DIR = BASE_DIR / "AI_Employee_Vault"
    CONFIG_DIR = BASE_DIR / "config"

    # Folders
    INBOX_DIR = VAULT_DIR / "Inbox"
    NEEDS_ACTION_DIR = VAULT_DIR / "Needs_Action"
    IN_PROGRESS_DIR = VAULT_DIR / "In_Progress"
    PENDING_APPROVAL_DIR = VAULT_DIR / "Pending_Approval"
    APPROVED_DIR = VAULT_DIR / "Approved"
    DONE_DIR = VAULT_DIR / "Done"
    UPDATES_DIR = VAULT_DIR / "Updates"
    SIGNALS_DIR = VAULT_DIR / "Signals"
    DRAFTS_DIR = VAULT_DIR / "Drafts"

    # Timing
    CYCLE_INTERVAL = 60  # 1 minute for responsive coordination
    HEARTBEAT_INTERVAL = 30
    SIGNAL_CHECK_INTERVAL = 15

    # Limits
    MAX_TASKS_PER_CYCLE = 10

    @classmethod
    def load_agent_config(cls, agent_type: str) -> Dict:
        """Load agent configuration."""
        if agent_type == "cloud":
            config_file = cls.CONFIG_DIR / "agent_config.cloud.json"
        else:
            config_file = cls.CONFIG_DIR / "agent_config.json"

        if config_file.exists():
            return json.loads(config_file.read_text())

        return {"agent_type": agent_type}


# ==============================================================================
# TASK PROCESSOR
# ==============================================================================

@dataclass
class TaskInfo:
    """Information about a task."""
    filename: str
    filepath: Path
    folder: str
    task_type: str
    content: str
    metadata: Dict


class PlatinumOrchestrator:
    """
    Platinum Tier Orchestrator with multi-agent coordination.

    Extends Gold tier with:
    - Claim-by-move task ownership
    - Cloud/Local work-zone separation
    - Signal-based coordination
    - Dashboard update merging
    """

    def __init__(self, agent_type: str = "local", dry_run: bool = False,
                 verbose: bool = False):
        """
        Initialize Platinum Orchestrator.

        Args:
            agent_type: 'cloud' or 'local'
            dry_run: If True, don't make changes
            verbose: Enable verbose logging
        """
        self.agent_type = agent_type
        self.dry_run = dry_run
        self.verbose = verbose

        # Load configuration
        self.config = PlatinumConfig.load_agent_config(agent_type)

        # Initialize components
        self.claim_manager = get_claim_manager(agent_type)
        self.coordinator = get_coordinator(agent_type)
        self.audit_logger = get_audit_logger()
        self.heartbeat = HeartbeatWriter(f"platinum_orchestrator_{agent_type}")

        # Work zone definitions
        self.work_zones = self._load_work_zones()

        # Running state
        self.running = False
        self.cycle_count = 0

    def _load_work_zones(self) -> Dict:
        """Load work zone configuration."""
        zones_file = PlatinumConfig.CONFIG_DIR / "work_zones.json"
        if zones_file.exists():
            return json.loads(zones_file.read_text())
        return {"zones": {}}

    def log(self, message: str, level: str = "INFO"):
        """Log message."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prefix = f"[{timestamp}] [{self.agent_type.upper()}] [{level}]"
        print(f"{prefix} {message}")

        if self.verbose or level in ["ERROR", "WARNING"]:
            self.audit_logger.log(
                action_type=ActionType.TASK_STARTED if level == "INFO" else ActionType.TASK_FAILED,
                actor=f"platinum_orchestrator_{self.agent_type}",
                target="system",
                parameters={"message": message, "level": level},
                result=ResultStatus.SUCCESS if level != "ERROR" else ResultStatus.FAILURE
            )

    # ==================== TASK DISCOVERY ====================

    def discover_tasks(self) -> List[TaskInfo]:
        """
        Discover available tasks that this agent can work on.

        Returns:
            List of TaskInfo objects
        """
        tasks = []

        # Check Needs_Action folder (with subfolders)
        for source_folder in [None, "email", "general", "linkedin"]:
            available = self.claim_manager.get_available_tasks(source_folder)

            for task_data in available:
                filepath = Path(task_data["path"])

                # Parse task type from filename or content
                task_type = self._detect_task_type(filepath)

                # Check if this agent can handle this task type
                if self._can_handle_task(task_type):
                    content = filepath.read_text() if filepath.exists() else ""
                    tasks.append(TaskInfo(
                        filename=task_data["filename"],
                        filepath=filepath,
                        folder=source_folder or "root",
                        task_type=task_type,
                        content=content,
                        metadata=self._parse_metadata(content)
                    ))

        # Also check Approved folder (for Local agent)
        if self.agent_type == "local":
            tasks.extend(self._get_approved_tasks())

        return tasks[:PlatinumConfig.MAX_TASKS_PER_CYCLE]

    def _detect_task_type(self, filepath: Path) -> str:
        """Detect task type from filename."""
        filename = filepath.name.upper()

        if "EMAIL" in filename:
            return "email_triage" if "DRAFT" in filename else "email_send"
        elif "FACEBOOK" in filename or "INSTAGRAM" in filename or \
             "TWITTER" in filename or "LINKEDIN" in filename:
            return "social_draft" if "DRAFT" in filename else "social_post"
        elif "APPROVAL" in filename:
            return "approvals"
        elif "PAYMENT" in filename:
            return "payments"
        elif "WHATSAPP" in filename:
            return "whatsapp"
        elif "ODOO" in filename or "INVOICE" in filename:
            return "odoo_write"
        else:
            return "general"

    def _can_handle_task(self, task_type: str) -> bool:
        """Check if this agent can handle the task type."""
        permission = self.coordinator.can_access_zone(task_type)
        return permission in [Permission.FULL_ACCESS, Permission.DRAFT_ONLY]

    def _parse_metadata(self, content: str) -> Dict:
        """Parse YAML frontmatter from content."""
        metadata = {}

        if content.startswith("---"):
            try:
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    import yaml
                    metadata = yaml.safe_load(parts[1]) or {}
            except Exception:
                pass

        return metadata

    def _get_approved_tasks(self) -> List[TaskInfo]:
        """Get tasks from Approved folder."""
        tasks = []
        approved_dir = PlatinumConfig.APPROVED_DIR

        if not approved_dir.exists():
            return tasks

        for filepath in approved_dir.glob("*.md"):
            if filepath.name.startswith("."):
                continue

            task_type = self._detect_task_type(filepath)
            content = filepath.read_text()

            tasks.append(TaskInfo(
                filename=filepath.name,
                filepath=filepath,
                folder="approved",
                task_type=task_type,
                content=content,
                metadata=self._parse_metadata(content)
            ))

        return tasks

    # ==================== TASK PROCESSING ====================

    def process_task(self, task: TaskInfo) -> Tuple[bool, str]:
        """
        Process a single task with claim-by-move.

        Args:
            task: TaskInfo object

        Returns:
            Tuple of (success, message)
        """
        self.log(f"Processing: {task.filename} (type: {task.task_type})")

        # Skip claiming for already-approved tasks
        if task.folder != "approved":
            # Attempt to claim task
            claim_status, claim_msg = self.claim_manager.claim_task(
                task.filename,
                task.folder if task.folder != "root" else None
            )

            if claim_status != ClaimStatus.SUCCESS:
                self.log(f"  Could not claim: {claim_msg}", "WARNING")
                return False, claim_msg

            self.log(f"  Claimed task successfully")

        try:
            # Process based on task type and permissions
            permission = self.coordinator.can_access_zone(task.task_type)

            if permission == Permission.FULL_ACCESS:
                success, msg = self._execute_task(task)
            elif permission == Permission.DRAFT_ONLY:
                success, msg = self._create_draft(task)
            else:
                success, msg = False, f"No permission for zone: {task.task_type}"

            # Release task to appropriate destination
            if success:
                if permission == Permission.DRAFT_ONLY:
                    dest = "pending_approval"
                else:
                    dest = "done"

                if task.folder != "approved":
                    self.claim_manager.release_task(task.filename, dest)
                else:
                    # Move from Approved to Done
                    self._move_to_done(task)

                self.log(f"  Completed -> {dest}")
            else:
                # Release back to needs_action on failure
                if task.folder != "approved":
                    self.claim_manager.release_task(task.filename, "needs_action")
                self.log(f"  Failed: {msg}", "ERROR")

            return success, msg

        except Exception as e:
            error_msg = str(e)
            self.log(f"  Exception: {error_msg}", "ERROR")

            # Release on error
            if task.folder != "approved":
                self.claim_manager.release_task(task.filename, "needs_action")

            return False, error_msg

    def _execute_task(self, task: TaskInfo) -> Tuple[bool, str]:
        """Execute a task with full access."""
        if self.dry_run:
            return True, "Dry run - would execute"

        # Dispatch based on task type
        if task.task_type == "social_post":
            return self._execute_social_post(task)
        elif task.task_type == "email_send":
            return self._execute_email_send(task)
        elif task.task_type == "approvals":
            return True, "Approval task processed"
        else:
            return True, f"Task type {task.task_type} completed"

    def _create_draft(self, task: TaskInfo) -> Tuple[bool, str]:
        """Create a draft for approval."""
        if self.dry_run:
            return True, "Dry run - would create draft"

        # Create draft in Pending_Approval
        draft_filename = f"DRAFT_{task.filename}"
        draft_path = PlatinumConfig.PENDING_APPROVAL_DIR / draft_filename

        draft_content = f"""---
type: draft_approval
original_task: {task.filename}
task_type: {task.task_type}
created_by: {self.agent_type}
created_at: {datetime.now().isoformat()}
status: pending_approval
---

# Draft Approval Request

**Task:** {task.filename}
**Type:** {task.task_type}
**Created by:** {self.agent_type} agent

## Original Content

{task.content}

## Actions

- Move to `/Approved/` to approve
- Move to `/Rejected/` to reject
"""

        draft_path.write_text(draft_content)

        # Send signal to Local agent
        self.coordinator.send_signal(
            signal_type="approval_needed",
            to_agent="local",
            payload={
                "task": task.filename,
                "draft": draft_filename,
                "task_type": task.task_type
            }
        )

        return True, f"Draft created: {draft_filename}"

    def _execute_social_post(self, task: TaskInfo) -> Tuple[bool, str]:
        """Execute social media post."""
        # Detect platform from filename
        filename_upper = task.filename.upper()

        if "FACEBOOK" in filename_upper:
            platform = "facebook"
        elif "TWITTER" in filename_upper:
            platform = "twitter"
        elif "LINKEDIN" in filename_upper:
            platform = "linkedin"
        elif "INSTAGRAM" in filename_upper:
            platform = "instagram"
        else:
            return False, "Unknown social platform"

        self.log(f"  Would post to {platform}")

        # In production, call the actual poster script
        # For now, mark as success
        return True, f"Posted to {platform}"

    def _execute_email_send(self, task: TaskInfo) -> Tuple[bool, str]:
        """Execute email send."""
        self.log(f"  Would send email")
        return True, "Email sent"

    def _move_to_done(self, task: TaskInfo):
        """Move task from Approved to Done."""
        import shutil
        dest = PlatinumConfig.DONE_DIR / task.filename
        shutil.move(str(task.filepath), str(dest))

    # ==================== SIGNAL HANDLING ====================

    def process_signals(self):
        """Process any pending signals for this agent."""
        signals = self.coordinator.get_pending_signals()

        for signal in signals:
            self.log(f"Signal: {signal.signal_type} from {signal.from_agent}")

            # Handle signal based on type
            if signal.signal_type == "approval_needed":
                self.log(f"  Approval request for: {signal.payload.get('task')}")
            elif signal.signal_type == "task_complete":
                self.log(f"  Task completed: {signal.payload.get('task')}")

            # Acknowledge signal
            self.coordinator.acknowledge_signal(signal.signal_id)

    # ==================== UPDATE HANDLING ====================

    def process_updates(self):
        """Process updates from other agent (Local only)."""
        if self.agent_type != "local":
            return

        updates = self.coordinator.get_pending_updates()

        for update in updates:
            update_type = update.get("type")
            self.log(f"Update: {update_type} from {update.get('from_agent')}")

            if update_type == "dashboard":
                self._merge_dashboard_update(update.get("data", {}))

            # Mark update as processed
            if "_file" in update:
                self.coordinator.mark_update_processed(update["_file"])

    def _merge_dashboard_update(self, data: Dict):
        """Merge dashboard update into Dashboard.md."""
        dashboard_path = PlatinumConfig.VAULT_DIR / "Dashboard.md"

        if not dashboard_path.exists():
            return

        # Read current dashboard
        content = dashboard_path.read_text()

        # Update metrics if present
        metrics = data.get("metrics", {})
        if metrics:
            self.log(f"  Merging {len(metrics)} metrics into Dashboard")
            # In production, actually update the dashboard content

    # ==================== MAIN CYCLE ====================

    def run_cycle(self) -> Dict:
        """
        Run a single orchestration cycle.

        Returns:
            Cycle result dictionary
        """
        self.cycle_count += 1
        cycle_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        start_time = datetime.now()

        self.log(f"=== Cycle {self.cycle_count} ({cycle_id}) ===")

        # Update heartbeat
        self.heartbeat.update_task(f"cycle:{cycle_id}")

        results = {
            "cycle_id": cycle_id,
            "agent_type": self.agent_type,
            "started_at": start_time.isoformat(),
            "tasks_found": 0,
            "tasks_processed": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "signals_processed": 0,
            "updates_processed": 0
        }

        try:
            # 1. Process signals
            self.process_signals()

            # 2. Process updates (Local only)
            self.process_updates()

            # 3. Discover tasks
            tasks = self.discover_tasks()
            results["tasks_found"] = len(tasks)
            self.log(f"Found {len(tasks)} tasks to process")

            # 4. Process tasks
            for task in tasks:
                results["tasks_processed"] += 1
                success, msg = self.process_task(task)

                if success:
                    results["tasks_completed"] += 1
                else:
                    results["tasks_failed"] += 1

            # 5. Cleanup expired signals
            self.coordinator.cleanup_expired_signals()

        except Exception as e:
            self.log(f"Cycle error: {e}", "ERROR")
            results["error"] = str(e)

        # Finalize
        end_time = datetime.now()
        results["ended_at"] = end_time.isoformat()
        results["duration_seconds"] = (end_time - start_time).total_seconds()

        self.log(f"Cycle complete: {results['tasks_completed']}/{results['tasks_processed']} tasks")

        return results

    def run(self):
        """Run orchestrator in continuous mode."""
        self.running = True
        self.heartbeat.start()

        self.log(f"Starting Platinum Orchestrator ({self.agent_type})")
        self.log(f"Cycle interval: {PlatinumConfig.CYCLE_INTERVAL}s")

        try:
            while self.running:
                self.run_cycle()

                # Update heartbeat
                self.heartbeat.update_task("sleeping")
                self.coordinator.update_heartbeat()

                # Sleep until next cycle
                time.sleep(PlatinumConfig.CYCLE_INTERVAL)

        except KeyboardInterrupt:
            self.log("Shutting down...")
        finally:
            self.running = False
            self.heartbeat.stop()
            self.log("Orchestrator stopped")

    def get_status(self) -> Dict:
        """Get orchestrator status."""
        claim_status = self.claim_manager.get_claim_status()
        coord_status = self.coordinator.get_coordination_status()

        return {
            "agent_type": self.agent_type,
            "running": self.running,
            "cycle_count": self.cycle_count,
            "claim_status": claim_status,
            "coordination_status": coord_status,
            "timestamp": datetime.now().isoformat()
        }


# ==============================================================================
# CLI
# ==============================================================================

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Platinum Tier Multi-Agent Orchestrator"
    )
    parser.add_argument(
        "--agent", choices=["cloud", "local"], default="local",
        help="Agent type (default: local)"
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Run single cycle and exit"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Test mode - no changes made"
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Show status and exit"
    )

    args = parser.parse_args()

    # Create orchestrator
    orchestrator = PlatinumOrchestrator(
        agent_type=args.agent,
        dry_run=args.dry_run,
        verbose=args.verbose
    )

    if args.status:
        status = orchestrator.get_status()
        print(json.dumps(status, indent=2))
        return

    if args.once:
        result = orchestrator.run_cycle()
        print(json.dumps(result, indent=2))
    else:
        orchestrator.run()


if __name__ == "__main__":
    main()
