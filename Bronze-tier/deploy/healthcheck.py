#!/usr/bin/env python3
"""
Platinum Tier - Health Check Script
AI Employee Hackathon

Used by Docker HEALTHCHECK to verify services are running.
Exit codes:
  0 = Healthy
  1 = Unhealthy
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta

# Configuration
VAULT_PATH = Path(os.environ.get("VAULT_PATH", "/data/AI_Employee_Vault"))
MAX_HEARTBEAT_AGE = timedelta(minutes=5)
REQUIRED_DIRS = ["Needs_Action", "Pending_Approval", "Approved", "Done", "In_Progress"]


def check_vault_exists() -> tuple[bool, str]:
    """Check if vault directory exists."""
    if not VAULT_PATH.exists():
        return False, f"Vault not found: {VAULT_PATH}"
    return True, "Vault exists"


def check_required_directories() -> tuple[bool, str]:
    """Check if required directories exist."""
    missing = []
    for dir_name in REQUIRED_DIRS:
        if not (VAULT_PATH / dir_name).exists():
            missing.append(dir_name)

    if missing:
        return False, f"Missing directories: {', '.join(missing)}"
    return True, "All directories present"


def check_git_repo() -> tuple[bool, str]:
    """Check if vault is a git repository."""
    git_dir = VAULT_PATH / ".git"
    if not git_dir.exists():
        return False, "Vault is not a git repository"
    return True, "Git repository OK"


def check_heartbeat() -> tuple[bool, str]:
    """Check if heartbeat is recent."""
    agent_id = os.environ.get("VAULT_AGENT_ID", "cloud")
    heartbeat_file = VAULT_PATH / "Signals" / f"heartbeat_{agent_id}.json"

    if not heartbeat_file.exists():
        return False, f"No heartbeat file: {heartbeat_file.name}"

    try:
        data = json.loads(heartbeat_file.read_text())
        timestamp_str = data.get("timestamp", "")

        # Parse ISO timestamp
        if timestamp_str:
            # Handle both formats
            timestamp_str = timestamp_str.replace("Z", "+00:00")
            timestamp = datetime.fromisoformat(timestamp_str)
            now = datetime.now(timestamp.tzinfo) if timestamp.tzinfo else datetime.now()

            age = now - timestamp
            if age > MAX_HEARTBEAT_AGE:
                return False, f"Heartbeat too old: {age}"

            return True, f"Heartbeat OK (age: {age.seconds}s)"

        return False, "Invalid heartbeat timestamp"

    except (json.JSONDecodeError, ValueError) as e:
        return False, f"Heartbeat parse error: {e}"


def check_sync_status() -> tuple[bool, str]:
    """Check sync status file."""
    sync_log = VAULT_PATH / "Logs" / "sync_status.json"

    if not sync_log.exists():
        # Not critical - may not have synced yet
        return True, "No sync status (OK for startup)"

    try:
        data = json.loads(sync_log.read_text())
        status = data.get("status", "unknown")

        if status in ["success", "no_changes"]:
            return True, f"Sync status: {status}"
        elif status == "conflict":
            return False, "Sync conflict detected"
        else:
            return True, f"Sync status: {status}"

    except (json.JSONDecodeError, ValueError) as e:
        return True, f"Sync status parse warning: {e}"


def check_processes() -> tuple[bool, str]:
    """Check if PID files exist and processes are running."""
    pid_files = [
        "/tmp/sync_vault.pid",
        "/tmp/cloud_agent.pid",
    ]

    running = []
    not_running = []

    for pid_file in pid_files:
        if os.path.exists(pid_file):
            try:
                with open(pid_file) as f:
                    pid = int(f.read().strip())

                # Check if process exists
                try:
                    os.kill(pid, 0)
                    running.append(os.path.basename(pid_file))
                except OSError:
                    not_running.append(os.path.basename(pid_file))

            except (ValueError, IOError):
                not_running.append(os.path.basename(pid_file))
        else:
            not_running.append(os.path.basename(pid_file))

    if not_running and running:
        return False, f"Some processes not running: {', '.join(not_running)}"
    elif not_running and not running:
        return False, "No processes running"

    return True, f"Processes running: {len(running)}"


def main():
    """Run all health checks."""
    checks = [
        ("Vault", check_vault_exists),
        ("Directories", check_required_directories),
        ("Git", check_git_repo),
        ("Heartbeat", check_heartbeat),
        ("Sync", check_sync_status),
        ("Processes", check_processes),
    ]

    all_healthy = True
    results = []

    for name, check_func in checks:
        try:
            healthy, message = check_func()
            status = "OK" if healthy else "FAIL"
            results.append(f"  [{status}] {name}: {message}")

            if not healthy:
                all_healthy = False

        except Exception as e:
            results.append(f"  [FAIL] {name}: Exception - {e}")
            all_healthy = False

    # Output results
    print("Health Check Results:")
    print("\n".join(results))

    if all_healthy:
        print("\nStatus: HEALTHY")
        sys.exit(0)
    else:
        print("\nStatus: UNHEALTHY")
        sys.exit(1)


if __name__ == "__main__":
    main()
