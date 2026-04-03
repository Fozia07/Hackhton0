#!/usr/bin/env python3
"""
Platinum Tier - Vault Sync Automation
Syncs AI_Employee_Vault between Cloud and Local agents via Git.

Features:
- Pull-before-push conflict safety
- Automatic commit with timestamps
- Continuous sync loop (configurable interval)
- Claim-by-move compatible (respects file moves as atomic operations)
- Logs sync status to Updates/

Usage:
    python3 sync_vault.py                    # Run continuous (60s interval)
    python3 sync_vault.py --once             # Single sync cycle
    python3 sync_vault.py --interval 30      # Custom interval (seconds)
    python3 sync_vault.py --dry-run          # Test mode (no actual git ops)
    python3 sync_vault.py --init             # Initialize vault as git repo

Environment:
    Set VAULT_GIT_REMOTE to override default remote URL
    Set VAULT_SYNC_BRANCH to override default branch (main)
"""

import os
import sys
import time
import json
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from enum import Enum
from typing import Optional, Tuple, List

# Paths (support Docker environment)
SCRIPT_DIR = Path(__file__).parent
BASE_DIR = SCRIPT_DIR.parent
VAULT_DIR = Path(os.environ.get("VAULT_PATH", BASE_DIR / "AI_Employee_Vault"))
LOGS_DIR = VAULT_DIR / "Logs"
UPDATES_DIR = VAULT_DIR / "Updates"

# Ensure directories exist
LOGS_DIR.mkdir(exist_ok=True)
UPDATES_DIR.mkdir(exist_ok=True)


class SyncStatus(Enum):
    """Sync operation status."""
    SUCCESS = "success"
    NO_CHANGES = "no_changes"
    CONFLICT = "conflict"
    ERROR = "error"
    PULL_FAILED = "pull_failed"
    PUSH_FAILED = "push_failed"
    NOT_INITIALIZED = "not_initialized"


class VaultSyncLogger:
    """Logger for vault sync operations."""

    def __init__(self, agent_id: str = "sync"):
        self.agent_id = agent_id
        self.log_file = LOGS_DIR / f"sync_{datetime.now().strftime('%Y%m%d')}.log"
        self.sync_log = LOGS_DIR / "sync_status.json"

    def log(self, level: str, message: str):
        """Log a message with timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] [{level.upper()}] [{self.agent_id}] {message}"
        print(log_line)

        # Append to daily log file
        try:
            with open(self.log_file, "a") as f:
                f.write(log_line + "\n")
        except Exception:
            pass  # Don't fail on log write errors

    def info(self, message: str):
        self.log("INFO", message)

    def warn(self, message: str):
        self.log("WARN", message)

    def error(self, message: str):
        self.log("ERROR", message)

    def debug(self, message: str):
        self.log("DEBUG", message)

    def write_sync_status(self, status: SyncStatus, details: dict = None):
        """Write sync status to JSON file for other agents to read."""
        status_data = {
            "last_sync": datetime.now().isoformat(),
            "status": status.value,
            "agent_id": self.agent_id,
            "details": details or {}
        }

        try:
            self.sync_log.write_text(json.dumps(status_data, indent=2))
        except Exception as e:
            self.error(f"Failed to write sync status: {e}")


class VaultSync:
    """Git-based vault synchronization."""

    def __init__(self,
                 agent_id: str = None,
                 dry_run: bool = False,
                 remote: str = None,
                 branch: str = None):
        """
        Initialize vault sync.

        Args:
            agent_id: Identifier for this sync agent (cloud/local/sync)
            dry_run: If True, don't execute actual git commands
            remote: Git remote URL (overrides env var)
            branch: Git branch name (overrides env var)
        """
        self.agent_id = agent_id or os.environ.get("VAULT_AGENT_ID", "sync")
        self.dry_run = dry_run
        self.remote = remote or os.environ.get("VAULT_GIT_REMOTE", "origin")
        self.branch = branch or os.environ.get("VAULT_SYNC_BRANCH", "main")
        self.logger = VaultSyncLogger(self.agent_id)
        self.vault_path = VAULT_DIR

    def _run_git(self, args: List[str], check: bool = True) -> Tuple[bool, str, str]:
        """
        Run a git command in the vault directory.

        Returns:
            Tuple of (success, stdout, stderr)
        """
        cmd = ["git"] + args
        cmd_str = " ".join(cmd)

        if self.dry_run:
            self.logger.debug(f"[DRY-RUN] Would run: {cmd_str}")
            return True, "", ""

        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.vault_path),
                capture_output=True,
                text=True,
                timeout=60
            )

            success = result.returncode == 0

            if not success and check:
                self.logger.debug(f"Git command failed: {cmd_str}")
                self.logger.debug(f"stderr: {result.stderr[:200]}")

            return success, result.stdout, result.stderr

        except subprocess.TimeoutExpired:
            self.logger.error(f"Git command timed out: {cmd_str}")
            return False, "", "Command timed out"
        except Exception as e:
            self.logger.error(f"Git command error: {e}")
            return False, "", str(e)

    def is_initialized(self) -> bool:
        """Check if vault is a git repository."""
        git_dir = self.vault_path / ".git"
        return git_dir.exists()

    def init_repo(self, remote_url: str = None) -> bool:
        """Initialize vault as git repository."""
        self.logger.info("Initializing vault as git repository...")

        # Check if already initialized
        if self.is_initialized():
            self.logger.info("Vault is already a git repository")
            return True

        # Init
        success, _, _ = self._run_git(["init"])
        if not success:
            self.logger.error("Failed to initialize git repository")
            return False

        # Create .gitignore
        self._create_gitignore()

        # Add remote if provided
        if remote_url:
            success, _, _ = self._run_git(["remote", "add", "origin", remote_url])
            if not success:
                self.logger.warn("Failed to add remote (may already exist)")

        # Initial commit
        self._run_git(["add", "-A"])
        self._run_git(["commit", "-m", "Initial vault setup"])

        self.logger.info("Vault initialized successfully")
        return True

    def _create_gitignore(self):
        """Create .gitignore for vault-specific exclusions."""
        gitignore_path = self.vault_path / ".gitignore"

        gitignore_content = """# Vault .gitignore - Platinum Tier Sync
# Generated by sync_vault.py

# Security - NEVER sync these
.env
.env.*
*.pem
*.key
credentials.json
token.json
tokens/
secrets/
session/
*.secret

# Logs - Keep structure, exclude content
Logs/*.log
Logs/*.json
!Logs/.gitkeep

# Temporary files
*.tmp
*.temp
*.swp
*.swo
*~
.DS_Store
Thumbs.db

# Lock files (claim-by-move system)
*.lock
.locks/

# Screenshots and large media
Logs/screenshots/
*.png
*.jpg
*.jpeg
!Business/**/*.png
!Business/**/*.jpg

# Obsidian (optional - sync if needed for multi-device)
# .obsidian/

# Python cache
__pycache__/
*.pyc
*.pyo

# IDE
.vscode/
.idea/

# Sync status (local only)
.sync_status
"""

        if not self.dry_run:
            gitignore_path.write_text(gitignore_content)
            self.logger.info("Created .gitignore for vault")
        else:
            self.logger.debug("[DRY-RUN] Would create .gitignore")

    def get_status(self) -> dict:
        """Get current git status."""
        status = {
            "initialized": self.is_initialized(),
            "changes": [],
            "untracked": [],
            "staged": [],
            "conflicts": []
        }

        if not status["initialized"]:
            return status

        # Get status
        success, stdout, _ = self._run_git(["status", "--porcelain"])
        if success and stdout:
            for line in stdout.strip().split("\n"):
                if not line:
                    continue
                code = line[:2]
                filepath = line[3:]

                if code == "??":
                    status["untracked"].append(filepath)
                elif code == "UU":
                    status["conflicts"].append(filepath)
                elif code[0] in "MADRC":
                    status["staged"].append(filepath)
                elif code[1] in "MADRC":
                    status["changes"].append(filepath)

        return status

    def pull(self) -> Tuple[SyncStatus, str]:
        """
        Pull latest changes from remote.

        Uses rebase to maintain linear history and avoid merge commits.
        """
        self.logger.info("Pulling latest changes...")

        if not self.is_initialized():
            return SyncStatus.NOT_INITIALIZED, "Vault not initialized"

        # Stash any local changes first
        status = self.get_status()
        has_changes = status["changes"] or status["untracked"] or status["staged"]

        if has_changes:
            self.logger.debug("Stashing local changes before pull...")
            self._run_git(["stash", "push", "-m", "auto-stash-before-pull"])

        # Pull with rebase
        success, stdout, stderr = self._run_git(
            ["pull", "--rebase", self.remote, self.branch],
            check=False
        )

        # Restore stashed changes
        if has_changes:
            self.logger.debug("Restoring stashed changes...")
            stash_success, _, stash_err = self._run_git(["stash", "pop"], check=False)
            if not stash_success and "No stash" not in stash_err:
                self.logger.warn(f"Stash pop warning: {stash_err[:100]}")

        if not success:
            # Check for conflicts
            if "CONFLICT" in stderr or "conflict" in stderr.lower():
                self.logger.error("Pull resulted in conflicts!")
                return SyncStatus.CONFLICT, stderr[:200]

            # Check if it's just "already up to date"
            if "Already up to date" in stdout or "Already up-to-date" in stdout:
                return SyncStatus.NO_CHANGES, "Already up to date"

            return SyncStatus.PULL_FAILED, stderr[:200]

        self.logger.info("Pull completed successfully")
        return SyncStatus.SUCCESS, stdout[:200] if stdout else "Pull complete"

    def commit_changes(self, message: str = None) -> Tuple[SyncStatus, str]:
        """
        Stage and commit all changes.

        Commit message includes timestamp and agent ID for traceability.
        """
        if not self.is_initialized():
            return SyncStatus.NOT_INITIALIZED, "Vault not initialized"

        # Check for changes
        status = self.get_status()
        if not (status["changes"] or status["untracked"] or status["staged"]):
            return SyncStatus.NO_CHANGES, "No changes to commit"

        # Stage all changes
        self._run_git(["add", "-A"])

        # Create commit message
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if message:
            commit_msg = f"[{self.agent_id}] {message} ({timestamp})"
        else:
            # Auto-generate message based on changes
            change_count = len(status["changes"]) + len(status["untracked"]) + len(status["staged"])
            commit_msg = f"[{self.agent_id}] Auto-sync: {change_count} file(s) ({timestamp})"

        # Commit
        success, stdout, stderr = self._run_git(["commit", "-m", commit_msg])

        if not success:
            if "nothing to commit" in stderr or "nothing to commit" in stdout:
                return SyncStatus.NO_CHANGES, "Nothing to commit"
            return SyncStatus.ERROR, stderr[:200]

        self.logger.info(f"Committed: {commit_msg}")
        return SyncStatus.SUCCESS, commit_msg

    def push(self) -> Tuple[SyncStatus, str]:
        """Push commits to remote."""
        self.logger.info("Pushing changes to remote...")

        if not self.is_initialized():
            return SyncStatus.NOT_INITIALIZED, "Vault not initialized"

        # Check if we have commits to push
        success, stdout, _ = self._run_git(
            ["log", f"{self.remote}/{self.branch}..HEAD", "--oneline"],
            check=False
        )

        if success and not stdout.strip():
            return SyncStatus.NO_CHANGES, "No commits to push"

        # Push
        success, stdout, stderr = self._run_git(
            ["push", self.remote, self.branch],
            check=False
        )

        if not success:
            # Check if we need to pull first
            if "rejected" in stderr.lower() or "non-fast-forward" in stderr.lower():
                self.logger.warn("Push rejected - need to pull first")
                return SyncStatus.CONFLICT, "Push rejected - remote has new changes"

            return SyncStatus.PUSH_FAILED, stderr[:200]

        self.logger.info("Push completed successfully")
        return SyncStatus.SUCCESS, "Push complete"

    def sync_cycle(self) -> SyncStatus:
        """
        Run a complete sync cycle: pull -> commit -> push.

        Implements conflict safety by always pulling before pushing.
        """
        self.logger.info("=== Starting sync cycle ===")

        if not self.is_initialized():
            self.logger.error("Vault not initialized as git repo")
            self.logger.write_sync_status(SyncStatus.NOT_INITIALIZED)
            return SyncStatus.NOT_INITIALIZED

        # Step 1: Pull latest (conflict safety)
        pull_status, pull_msg = self.pull()

        if pull_status == SyncStatus.CONFLICT:
            self.logger.error(f"Sync aborted due to conflict: {pull_msg}")
            self.logger.write_sync_status(SyncStatus.CONFLICT, {"step": "pull", "message": pull_msg})
            return SyncStatus.CONFLICT

        if pull_status == SyncStatus.PULL_FAILED:
            self.logger.warn(f"Pull failed (may be offline): {pull_msg}")
            # Continue with local commit anyway

        # Step 2: Commit local changes
        commit_status, commit_msg = self.commit_changes()

        if commit_status == SyncStatus.ERROR:
            self.logger.error(f"Commit failed: {commit_msg}")
            self.logger.write_sync_status(SyncStatus.ERROR, {"step": "commit", "message": commit_msg})
            return SyncStatus.ERROR

        # Step 3: Push if we have commits
        if commit_status == SyncStatus.SUCCESS:
            push_status, push_msg = self.push()

            if push_status == SyncStatus.CONFLICT:
                # Retry: pull and push again
                self.logger.info("Retrying sync after conflict...")
                pull_status, _ = self.pull()
                if pull_status == SyncStatus.SUCCESS:
                    push_status, push_msg = self.push()

            if push_status == SyncStatus.PUSH_FAILED:
                self.logger.warn(f"Push failed (may be offline): {push_msg}")
                self.logger.write_sync_status(SyncStatus.PUSH_FAILED, {"message": push_msg})
                return SyncStatus.PUSH_FAILED

            if push_status == SyncStatus.SUCCESS:
                self.logger.info("Sync cycle completed: changes pushed")
                self.logger.write_sync_status(SyncStatus.SUCCESS, {"committed": True, "pushed": True})
                return SyncStatus.SUCCESS

        # No changes case
        self.logger.info("Sync cycle completed: no local changes")
        self.logger.write_sync_status(SyncStatus.NO_CHANGES)
        return SyncStatus.NO_CHANGES

    def write_sync_update(self, status: SyncStatus, details: dict = None):
        """Write sync update to Updates/ folder for other agents."""
        update_file = UPDATES_DIR / f"sync_{self.agent_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        update_data = {
            "type": "vault_sync",
            "agent_id": self.agent_id,
            "timestamp": datetime.now().isoformat(),
            "status": status.value,
            "details": details or {}
        }

        try:
            update_file.write_text(json.dumps(update_data, indent=2))
            self.logger.debug(f"Wrote sync update: {update_file.name}")
        except Exception as e:
            self.logger.warn(f"Failed to write sync update: {e}")

    def run_continuous(self, interval: int = 60):
        """
        Run continuous sync loop.

        Args:
            interval: Seconds between sync cycles (30-300)
        """
        interval = max(30, min(300, interval))  # Clamp to reasonable range

        self.logger.info(f"Starting continuous sync (interval: {interval}s)")
        self.logger.info("Press Ctrl+C to stop")

        cycle_count = 0
        error_count = 0
        max_errors = 5  # Stop after consecutive errors

        try:
            while True:
                cycle_count += 1
                self.logger.info(f"--- Cycle {cycle_count} ---")

                try:
                    status = self.sync_cycle()

                    if status in [SyncStatus.SUCCESS, SyncStatus.NO_CHANGES]:
                        error_count = 0  # Reset on success
                    else:
                        error_count += 1

                    # Write periodic update
                    if cycle_count % 10 == 0:
                        self.write_sync_update(status, {
                            "cycle": cycle_count,
                            "consecutive_errors": error_count
                        })

                    # Check error threshold
                    if error_count >= max_errors:
                        self.logger.error(f"Too many consecutive errors ({error_count}). Stopping.")
                        break

                except Exception as e:
                    self.logger.error(f"Cycle error: {e}")
                    error_count += 1

                self.logger.info(f"Sleeping {interval}s...")
                time.sleep(interval)

        except KeyboardInterrupt:
            self.logger.info("Sync stopped by user")

        self.logger.info(f"Sync ended after {cycle_count} cycles")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Vault Git Sync - Platinum Tier",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 sync_vault.py                    # Continuous sync (60s)
  python3 sync_vault.py --once             # Single cycle
  python3 sync_vault.py --interval 30      # 30s interval
  python3 sync_vault.py --init             # Initialize vault repo
  python3 sync_vault.py --init --remote git@github.com:user/vault.git

Environment Variables:
  VAULT_GIT_REMOTE   - Git remote name or URL (default: origin)
  VAULT_SYNC_BRANCH  - Branch to sync (default: main)
  VAULT_AGENT_ID     - Agent identifier (default: sync)
        """
    )

    parser.add_argument("--once", action="store_true",
                        help="Run single sync cycle")
    parser.add_argument("--interval", type=int, default=60,
                        help="Sync interval in seconds (default: 60)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Test mode - don't execute git commands")
    parser.add_argument("--init", action="store_true",
                        help="Initialize vault as git repository")
    parser.add_argument("--remote", type=str,
                        help="Git remote URL (for --init)")
    parser.add_argument("--branch", type=str, default="main",
                        help="Git branch name (default: main)")
    parser.add_argument("--agent-id", type=str, default="sync",
                        help="Agent identifier for commits")
    parser.add_argument("--status", action="store_true",
                        help="Show sync status and exit")

    args = parser.parse_args()

    # Create sync instance
    sync = VaultSync(
        agent_id=args.agent_id,
        dry_run=args.dry_run,
        branch=args.branch
    )

    # Status check
    if args.status:
        status = sync.get_status()
        print(json.dumps(status, indent=2))
        return

    # Initialize if requested
    if args.init:
        success = sync.init_repo(args.remote)
        if not success:
            sys.exit(1)
        if args.once or args.dry_run:
            return  # Just init, don't sync (or dry-run complete)

    # Check if initialized (skip in dry-run mode)
    if not args.dry_run and not sync.is_initialized():
        print("ERROR: Vault is not a git repository.")
        print("Run with --init to initialize, or manually:")
        print(f"  cd {VAULT_DIR}")
        print("  git init")
        print("  git remote add origin <your-repo-url>")
        sys.exit(1)

    # Run sync
    if args.once:
        status = sync.sync_cycle()
        sys.exit(0 if status in [SyncStatus.SUCCESS, SyncStatus.NO_CHANGES] else 1)
    else:
        sync.run_continuous(interval=args.interval)


if __name__ == "__main__":
    main()
