#!/usr/bin/env python3
"""
Platinum Tier - Claim Manager
Implements claim-by-move logic for multi-agent coordination.

The first agent to move a task from /Needs_Action to /In_Progress/<agent>/
owns that task. Other agents must skip it.
"""

import os
import shutil
import json
import fcntl
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, List, Dict
from enum import Enum

# Add parent directory for imports
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class AgentType(Enum):
    """Agent types for claim ownership."""
    CLOUD = "cloud"
    LOCAL = "local"


class ClaimStatus(Enum):
    """Status of a claim operation."""
    SUCCESS = "success"
    ALREADY_CLAIMED = "already_claimed"
    FILE_NOT_FOUND = "file_not_found"
    CLAIM_FAILED = "claim_failed"
    RELEASED = "released"


class ClaimManager:
    """
    Manages task claiming between Cloud and Local agents.

    Implements the claim-by-move rule:
    - First agent to move file to /In_Progress/<agent>/ owns it
    - Other agents must check and skip claimed tasks
    - Provides atomic claim operations using file locking
    """

    def __init__(self, vault_path: str, agent_type: AgentType):
        """
        Initialize ClaimManager.

        Args:
            vault_path: Path to AI_Employee_Vault
            agent_type: Type of agent (CLOUD or LOCAL)
        """
        self.vault_path = Path(vault_path)
        self.agent_type = agent_type
        self.agent_id = agent_type.value

        # Define paths
        self.needs_action_path = self.vault_path / "Needs_Action"
        self.in_progress_path = self.vault_path / "In_Progress"
        self.my_workspace = self.in_progress_path / self.agent_id
        self.other_workspace = self.in_progress_path / (
            "local" if self.agent_id == "cloud" else "cloud"
        )
        self.done_path = self.vault_path / "Done"
        self.pending_approval_path = self.vault_path / "Pending_Approval"
        self.approved_path = self.vault_path / "Approved"

        # Lock file for atomic operations
        self.lock_file = self.in_progress_path / ".claim_lock"

        # Ensure directories exist
        self._ensure_directories()

    def _ensure_directories(self):
        """Ensure all required directories exist."""
        for path in [self.my_workspace, self.other_workspace,
                     self.needs_action_path, self.done_path,
                     self.pending_approval_path, self.approved_path]:
            path.mkdir(parents=True, exist_ok=True)

    def _acquire_lock(self, timeout: float = 5.0) -> Optional[int]:
        """
        Acquire exclusive lock for atomic operations.

        Args:
            timeout: Maximum time to wait for lock

        Returns:
            File descriptor if lock acquired, None otherwise
        """
        start_time = time.time()

        # Create lock file if it doesn't exist
        self.lock_file.touch(exist_ok=True)

        fd = os.open(str(self.lock_file), os.O_RDWR)

        while time.time() - start_time < timeout:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return fd
            except (IOError, OSError):
                time.sleep(0.1)

        os.close(fd)
        return None

    def _release_lock(self, fd: int):
        """Release the lock."""
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
        except:
            pass

    def claim_task(self, task_filename: str,
                   source_folder: str = None) -> Tuple[ClaimStatus, str]:
        """
        Attempt to claim a task by moving it to agent's workspace.

        Args:
            task_filename: Name of the task file
            source_folder: Subfolder in Needs_Action (e.g., 'email', 'general')

        Returns:
            Tuple of (ClaimStatus, message)
        """
        # Build source path
        if source_folder:
            source_path = self.needs_action_path / source_folder / task_filename
        else:
            source_path = self.needs_action_path / task_filename

        # Check if file exists
        if not source_path.exists():
            # Check if already claimed by another agent
            other_claimed = self.other_workspace / task_filename
            my_claimed = self.my_workspace / task_filename

            if other_claimed.exists():
                return ClaimStatus.ALREADY_CLAIMED, f"Task claimed by other agent"
            elif my_claimed.exists():
                return ClaimStatus.ALREADY_CLAIMED, f"Task already claimed by this agent"
            else:
                return ClaimStatus.FILE_NOT_FOUND, f"Task file not found: {task_filename}"

        # Acquire lock for atomic operation
        fd = self._acquire_lock()
        if fd is None:
            return ClaimStatus.CLAIM_FAILED, "Could not acquire lock"

        try:
            # Double-check file still exists (another agent might have claimed it)
            if not source_path.exists():
                return ClaimStatus.ALREADY_CLAIMED, "Task was claimed by another agent"

            # Move to my workspace
            dest_path = self.my_workspace / task_filename
            shutil.move(str(source_path), str(dest_path))

            # Create claim metadata
            self._write_claim_metadata(dest_path, source_folder)

            return ClaimStatus.SUCCESS, f"Task claimed: {task_filename}"

        except Exception as e:
            return ClaimStatus.CLAIM_FAILED, f"Claim failed: {str(e)}"

        finally:
            self._release_lock(fd)

    def _write_claim_metadata(self, task_path: Path, source_folder: str = None):
        """Write metadata about the claim."""
        meta_path = task_path.with_suffix(task_path.suffix + ".claim.json")
        metadata = {
            "claimed_by": self.agent_id,
            "claimed_at": datetime.now().isoformat(),
            "source_folder": source_folder,
            "original_path": str(task_path.name)
        }
        meta_path.write_text(json.dumps(metadata, indent=2))

    def release_task(self, task_filename: str,
                     destination: str = "done") -> Tuple[ClaimStatus, str]:
        """
        Release a claimed task by moving it to destination.

        Args:
            task_filename: Name of the task file
            destination: Where to move ('done', 'pending_approval', 'approved', 'needs_action')

        Returns:
            Tuple of (ClaimStatus, message)
        """
        source_path = self.my_workspace / task_filename

        if not source_path.exists():
            return ClaimStatus.FILE_NOT_FOUND, f"Task not in workspace: {task_filename}"

        # Determine destination path
        dest_map = {
            "done": self.done_path,
            "pending_approval": self.pending_approval_path,
            "approved": self.approved_path,
            "needs_action": self.needs_action_path
        }

        dest_folder = dest_map.get(destination, self.done_path)
        dest_path = dest_folder / task_filename

        try:
            shutil.move(str(source_path), str(dest_path))

            # Remove claim metadata
            meta_path = source_path.with_suffix(source_path.suffix + ".claim.json")
            if meta_path.exists():
                meta_path.unlink()

            return ClaimStatus.RELEASED, f"Task released to {destination}: {task_filename}"

        except Exception as e:
            return ClaimStatus.CLAIM_FAILED, f"Release failed: {str(e)}"

    def get_my_claimed_tasks(self) -> List[Dict]:
        """
        Get list of tasks claimed by this agent.

        Returns:
            List of task info dictionaries
        """
        tasks = []
        for task_file in self.my_workspace.glob("*.md"):
            if task_file.name.startswith("."):
                continue

            meta_path = task_file.with_suffix(task_file.suffix + ".claim.json")
            metadata = {}
            if meta_path.exists():
                try:
                    metadata = json.loads(meta_path.read_text())
                except:
                    pass

            tasks.append({
                "filename": task_file.name,
                "path": str(task_file),
                "claimed_at": metadata.get("claimed_at"),
                "source_folder": metadata.get("source_folder")
            })

        return tasks

    def get_other_claimed_tasks(self) -> List[str]:
        """
        Get list of tasks claimed by the other agent.

        Returns:
            List of task filenames
        """
        tasks = []
        for task_file in self.other_workspace.glob("*.md"):
            if not task_file.name.startswith("."):
                tasks.append(task_file.name)
        return tasks

    def get_available_tasks(self, source_folder: str = None) -> List[Dict]:
        """
        Get list of unclaimed tasks in Needs_Action.

        Args:
            source_folder: Optional subfolder to check

        Returns:
            List of task info dictionaries
        """
        if source_folder:
            search_path = self.needs_action_path / source_folder
        else:
            search_path = self.needs_action_path

        if not search_path.exists():
            return []

        tasks = []
        for task_file in search_path.glob("*.md"):
            if task_file.name.startswith("."):
                continue

            # Check if claimed by either agent
            if not self._is_claimed(task_file.name):
                tasks.append({
                    "filename": task_file.name,
                    "path": str(task_file),
                    "folder": source_folder
                })

        return tasks

    def _is_claimed(self, task_filename: str) -> bool:
        """Check if a task is already claimed by any agent."""
        return (
            (self.my_workspace / task_filename).exists() or
            (self.other_workspace / task_filename).exists()
        )

    def is_task_mine(self, task_filename: str) -> bool:
        """Check if a task is claimed by this agent."""
        return (self.my_workspace / task_filename).exists()

    def get_claim_status(self) -> Dict:
        """
        Get overall claim status for monitoring.

        Returns:
            Dictionary with claim statistics
        """
        my_tasks = self.get_my_claimed_tasks()
        other_tasks = self.get_other_claimed_tasks()
        available = self.get_available_tasks()

        return {
            "agent_id": self.agent_id,
            "my_claimed_count": len(my_tasks),
            "other_claimed_count": len(other_tasks),
            "available_count": len(available),
            "my_tasks": [t["filename"] for t in my_tasks],
            "other_tasks": other_tasks,
            "timestamp": datetime.now().isoformat()
        }


def get_claim_manager(agent_type: str = None) -> ClaimManager:
    """
    Factory function to get ClaimManager instance.

    Args:
        agent_type: 'cloud' or 'local'. If None, reads from config.

    Returns:
        ClaimManager instance
    """
    base_dir = Path(__file__).parent.parent
    # Support Docker environment variable
    vault_path = Path(os.environ.get("VAULT_PATH", base_dir / "AI_Employee_Vault"))

    # Determine agent type
    if agent_type is None:
        config_path = base_dir / "config" / "agent_config.json"
        if config_path.exists():
            config = json.loads(config_path.read_text())
            agent_type = config.get("agent_type", "local")
        else:
            agent_type = "local"

    agent_enum = AgentType.CLOUD if agent_type == "cloud" else AgentType.LOCAL
    return ClaimManager(str(vault_path), agent_enum)


# CLI interface for testing
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Claim Manager CLI")
    parser.add_argument("--agent", choices=["cloud", "local"], default="local",
                        help="Agent type")
    parser.add_argument("--action", choices=["status", "claim", "release", "list"],
                        default="status", help="Action to perform")
    parser.add_argument("--task", help="Task filename for claim/release")
    parser.add_argument("--folder", help="Source folder in Needs_Action")
    parser.add_argument("--dest", default="done",
                        choices=["done", "pending_approval", "approved", "needs_action"],
                        help="Destination for release")

    args = parser.parse_args()

    manager = get_claim_manager(args.agent)

    if args.action == "status":
        status = manager.get_claim_status()
        print(json.dumps(status, indent=2))

    elif args.action == "claim":
        if not args.task:
            print("Error: --task required for claim action")
            sys.exit(1)
        result, msg = manager.claim_task(args.task, args.folder)
        print(f"{result.value}: {msg}")

    elif args.action == "release":
        if not args.task:
            print("Error: --task required for release action")
            sys.exit(1)
        result, msg = manager.release_task(args.task, args.dest)
        print(f"{result.value}: {msg}")

    elif args.action == "list":
        print("=== My Claimed Tasks ===")
        for task in manager.get_my_claimed_tasks():
            print(f"  - {task['filename']}")

        print("\n=== Other Agent's Tasks ===")
        for task in manager.get_other_claimed_tasks():
            print(f"  - {task}")

        print("\n=== Available Tasks ===")
        for task in manager.get_available_tasks():
            print(f"  - {task['filename']}")
