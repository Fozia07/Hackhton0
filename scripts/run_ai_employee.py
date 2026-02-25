#!/usr/bin/env python3
"""
AI Employee Runner - Production-Ready Automated Scheduler
Silver Tier Component

Automatically runs the AI Employee system every 5 minutes:
- Processes Inbox tasks
- Generates plans for complex tasks
- Routes through approval workflow
- Executes approved actions
- Maintains comprehensive logs

Usage:
    python3 run_ai_employee.py              # Run continuous (daemon mode)
    python3 run_ai_employee.py --once       # Run single cycle
    python3 run_ai_employee.py --dry-run    # Test without changes
    python3 run_ai_employee.py --verbose    # Debug output

Author: AI Employee System
Version: 1.0.0
"""

import os
import sys
import json
import time
import shutil
import signal
import logging
import hashlib
import argparse
import tempfile
import traceback
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import fcntl  # Unix file locking (will use alternative for Windows)

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.audit_logger import (
    get_audit_logger,
    ActionType,
    ApprovalStatus,
    ResultStatus
)

from utils.retry_handler import (
    get_retry_handler,
    RetryConfig,
    get_circuit_breaker,
    get_queue_manager,
    process_retry_queue
)

# Initialize audit logger
audit_logger = get_audit_logger()

# Initialize retry components
retry_handler = get_retry_handler(
    actor="ai_employee_runner",
    circuit_breaker="ai_employee_operations"
)
circuit_breaker = get_circuit_breaker("ai_employee_operations")
queue_manager = get_queue_manager()

# ==============================================================================
# CONFIGURATION
# ==============================================================================

class Config:
    """Central configuration for AI Employee Runner."""

    # Paths (relative to script location)
    BASE_DIR = Path(__file__).parent.parent
    VAULT_DIR = BASE_DIR / "AI_Employee_Vault"

    # Vault folders
    INBOX_DIR = VAULT_DIR / "Inbox"
    NEEDS_ACTION_DIR = VAULT_DIR / "Needs_Action"
    PLANS_DIR = VAULT_DIR / "Plans"
    PENDING_APPROVAL_DIR = VAULT_DIR / "Pending_Approval"
    APPROVED_DIR = VAULT_DIR / "Approved"
    REJECTED_DIR = VAULT_DIR / "Rejected"
    DONE_DIR = VAULT_DIR / "Done"
    LOGS_DIR = VAULT_DIR / "Logs"
    SCHEDULES_DIR = VAULT_DIR / "Schedules"

    # Lock file
    LOCK_FILE = BASE_DIR / ".ai_employee.lock"
    PID_FILE = BASE_DIR / ".ai_employee.pid"

    # Timing
    CYCLE_INTERVAL = 300  # 5 minutes in seconds
    MAX_CYCLE_DURATION = 240  # 4 minutes max per cycle
    RETRY_DELAY = 5  # seconds between retries
    MAX_RETRIES = 3

    # Limits
    MAX_TASKS_PER_CYCLE = 20
    MAX_LOG_SIZE_MB = 50
    MIN_DISK_SPACE_MB = 100

    # File handling
    ALLOWED_EXTENSIONS = {'.md', '.txt', '.json', '.yaml', '.yml'}
    IGNORED_FILES = {'.DS_Store', 'Thumbs.db', '.gitkeep', 'desktop.ini'}

    # Environment overrides
    @classmethod
    def load_from_env(cls):
        """Load configuration from environment variables."""
        if os.environ.get('AI_EMPLOYEE_VAULT'):
            cls.VAULT_DIR = Path(os.environ['AI_EMPLOYEE_VAULT'])
            cls._update_paths()

        if os.environ.get('AI_EMPLOYEE_CYCLE_INTERVAL'):
            cls.CYCLE_INTERVAL = int(os.environ['AI_EMPLOYEE_CYCLE_INTERVAL'])

        if os.environ.get('AI_EMPLOYEE_MAX_TASKS'):
            cls.MAX_TASKS_PER_CYCLE = int(os.environ['AI_EMPLOYEE_MAX_TASKS'])

    @classmethod
    def _update_paths(cls):
        """Update derived paths when VAULT_DIR changes."""
        cls.INBOX_DIR = cls.VAULT_DIR / "Inbox"
        cls.NEEDS_ACTION_DIR = cls.VAULT_DIR / "Needs_Action"
        cls.PLANS_DIR = cls.VAULT_DIR / "Plans"
        cls.PENDING_APPROVAL_DIR = cls.VAULT_DIR / "Pending_Approval"
        cls.APPROVED_DIR = cls.VAULT_DIR / "Approved"
        cls.REJECTED_DIR = cls.VAULT_DIR / "Rejected"
        cls.DONE_DIR = cls.VAULT_DIR / "Done"
        cls.LOGS_DIR = cls.VAULT_DIR / "Logs"
        cls.SCHEDULES_DIR = cls.VAULT_DIR / "Schedules"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

class TaskStatus(Enum):
    """Task status enumeration."""
    NEW = "new"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskPriority(Enum):
    """Task priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class Task:
    """Represents a task in the system."""
    id: str
    filename: str
    filepath: Path
    task_type: str
    status: TaskStatus
    priority: TaskPriority
    created_at: datetime
    content: str
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict:
        """Convert task to dictionary."""
        return {
            'id': self.id,
            'filename': self.filename,
            'filepath': str(self.filepath),
            'task_type': self.task_type,
            'status': self.status.value,
            'priority': self.priority.value,
            'created_at': self.created_at.isoformat(),
            'content_preview': self.content[:200] if self.content else '',
            'metadata': self.metadata
        }


@dataclass
class CycleResult:
    """Result of a single execution cycle."""
    cycle_id: str
    started_at: datetime
    ended_at: datetime
    tasks_processed: int
    tasks_completed: int
    tasks_failed: int
    errors: List[str]

    def to_dict(self) -> Dict:
        """Convert result to dictionary."""
        return {
            'cycle_id': self.cycle_id,
            'started_at': self.started_at.isoformat(),
            'ended_at': self.ended_at.isoformat(),
            'duration_seconds': (self.ended_at - self.started_at).total_seconds(),
            'tasks_processed': self.tasks_processed,
            'tasks_completed': self.tasks_completed,
            'tasks_failed': self.tasks_failed,
            'success_rate': (self.tasks_completed / self.tasks_processed * 100) if self.tasks_processed > 0 else 100,
            'errors': self.errors
        }


# ==============================================================================
# LOGGING SETUP
# ==============================================================================

class StructuredLogger:
    """JSON-structured logging with file rotation."""

    def __init__(self, log_dir: Path, name: str = "ai_employee"):
        self.log_dir = log_dir
        self.name = name
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Setup Python logging
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_format)
        self.logger.addHandler(console_handler)

        # File handler (human-readable)
        log_file = self.log_dir / "runner.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(console_format)
        self.logger.addHandler(file_handler)

    def _get_json_log_file(self) -> Path:
        """Get today's JSON log file path."""
        return self.log_dir / f"{datetime.now().strftime('%Y-%m-%d')}_runner.json"

    def _write_json_log(self, entry: Dict):
        """Write entry to JSON log file."""
        log_file = self._get_json_log_file()

        logs = []
        if log_file.exists():
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    logs = json.load(f)
            except (json.JSONDecodeError, IOError):
                logs = []

        logs.append(entry)

        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(logs, f, indent=2, default=str)

    def log(self, level: str, message: str, **kwargs):
        """Log message with structured data."""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'message': message,
            **kwargs
        }

        # Python logging
        log_func = getattr(self.logger, level.lower(), self.logger.info)
        log_func(message)

        # JSON logging
        self._write_json_log(entry)

    def info(self, message: str, **kwargs):
        self.log('INFO', message, **kwargs)

    def debug(self, message: str, **kwargs):
        self.log('DEBUG', message, **kwargs)

    def warning(self, message: str, **kwargs):
        self.log('WARNING', message, **kwargs)

    def error(self, message: str, **kwargs):
        self.log('ERROR', message, **kwargs)

    def critical(self, message: str, **kwargs):
        self.log('CRITICAL', message, **kwargs)


# ==============================================================================
# FILE LOCKING (Cross-platform)
# ==============================================================================

class FileLock:
    """Cross-platform file locking to prevent concurrent runs."""

    def __init__(self, lock_file: Path):
        self.lock_file = lock_file
        self.lock_fd = None
        self._is_windows = sys.platform == 'win32'

    def acquire(self) -> bool:
        """Acquire the lock. Returns True if successful."""
        try:
            self.lock_fd = open(self.lock_file, 'w')

            if self._is_windows:
                # Windows locking
                import msvcrt
                msvcrt.locking(self.lock_fd.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                # Unix locking
                fcntl.flock(self.lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

            # Write PID to lock file
            self.lock_fd.write(str(os.getpid()))
            self.lock_fd.flush()
            return True

        except (IOError, OSError, ImportError):
            if self.lock_fd:
                self.lock_fd.close()
                self.lock_fd = None
            return False

    def release(self):
        """Release the lock."""
        if self.lock_fd:
            try:
                if self._is_windows:
                    import msvcrt
                    msvcrt.locking(self.lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(self.lock_fd.fileno(), fcntl.LOCK_UN)
            except (IOError, OSError, ImportError):
                pass
            finally:
                self.lock_fd.close()
                self.lock_fd = None

                # Remove lock file
                try:
                    self.lock_file.unlink()
                except OSError:
                    pass

    def __enter__(self):
        if not self.acquire():
            raise RuntimeError("Could not acquire lock - another instance may be running")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False


# ==============================================================================
# HEALTH CHECKS
# ==============================================================================

class HealthChecker:
    """System health verification."""

    def __init__(self, config: Config, logger: StructuredLogger):
        self.config = config
        self.logger = logger

    def check_all(self) -> tuple[bool, List[str]]:
        """Run all health checks. Returns (healthy, issues)."""
        issues = []

        # Check folders exist
        folders = [
            self.config.VAULT_DIR,
            self.config.INBOX_DIR,
            self.config.NEEDS_ACTION_DIR,
            self.config.DONE_DIR,
            self.config.LOGS_DIR
        ]

        for folder in folders:
            if not folder.exists():
                try:
                    folder.mkdir(parents=True, exist_ok=True)
                    self.logger.info(f"Created missing folder: {folder}")
                except OSError as e:
                    issues.append(f"Cannot create folder {folder}: {e}")

        # Check disk space
        try:
            stat = shutil.disk_usage(self.config.VAULT_DIR)
            free_mb = stat.free / (1024 * 1024)
            if free_mb < self.config.MIN_DISK_SPACE_MB:
                issues.append(f"Low disk space: {free_mb:.1f}MB free (minimum: {self.config.MIN_DISK_SPACE_MB}MB)")
        except OSError as e:
            issues.append(f"Cannot check disk space: {e}")

        # Check write permission
        try:
            test_file = self.config.LOGS_DIR / ".health_check"
            test_file.write_text("health check")
            test_file.unlink()
        except OSError as e:
            issues.append(f"Cannot write to logs directory: {e}")

        healthy = len(issues) == 0
        return healthy, issues


# ==============================================================================
# TASK PROCESSOR
# ==============================================================================

class TaskProcessor:
    """Main task processing logic."""

    def __init__(self, config: Config, logger: StructuredLogger, dry_run: bool = False):
        self.config = config
        self.logger = logger
        self.dry_run = dry_run

    def generate_task_id(self, filepath: Path) -> str:
        """Generate unique task ID from filepath."""
        content = f"{filepath}{datetime.now().isoformat()}"
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def parse_frontmatter(self, content: str) -> tuple[Dict, str]:
        """Parse YAML frontmatter from markdown content."""
        metadata = {}
        body = content

        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                try:
                    # Simple YAML parsing (key: value)
                    for line in parts[1].strip().split('\n'):
                        if ':' in line:
                            key, value = line.split(':', 1)
                            metadata[key.strip()] = value.strip()
                    body = parts[2].strip()
                except Exception:
                    pass

        return metadata, body

    def detect_task_type(self, filename: str, content: str) -> str:
        """Detect task type from filename and content."""
        filename_lower = filename.lower()
        content_lower = content.lower()

        if 'email' in filename_lower or 'email' in content_lower:
            return 'email'
        elif 'linkedin' in filename_lower or 'linkedin' in content_lower:
            return 'linkedin'
        elif 'approval' in filename_lower:
            return 'approval'
        elif 'plan' in filename_lower:
            return 'plan'
        else:
            return 'general'

    def detect_priority(self, content: str, metadata: Dict) -> TaskPriority:
        """Detect task priority from content and metadata."""
        # Check metadata first
        if 'priority' in metadata:
            priority_str = metadata['priority'].lower()
            if priority_str == 'urgent':
                return TaskPriority.URGENT
            elif priority_str == 'high':
                return TaskPriority.HIGH
            elif priority_str == 'low':
                return TaskPriority.LOW

        # Check content for urgency keywords
        content_lower = content.lower()
        if any(word in content_lower for word in ['urgent', 'asap', 'immediately', 'critical']):
            return TaskPriority.URGENT
        elif any(word in content_lower for word in ['important', 'priority', 'soon']):
            return TaskPriority.HIGH

        return TaskPriority.MEDIUM

    def should_skip_file(self, filepath: Path) -> bool:
        """Check if file should be skipped."""
        # Skip ignored files
        if filepath.name in self.config.IGNORED_FILES:
            return True

        # Skip hidden files
        if filepath.name.startswith('.'):
            return True

        # Skip non-allowed extensions
        if filepath.suffix.lower() not in self.config.ALLOWED_EXTENSIONS:
            return True

        return False

    def scan_inbox(self) -> List[Path]:
        """Scan inbox for new files."""
        files = []

        # Scan main inbox
        if self.config.INBOX_DIR.exists():
            for item in self.config.INBOX_DIR.rglob('*'):
                if item.is_file() and not self.should_skip_file(item):
                    files.append(item)

        return sorted(files, key=lambda f: f.stat().st_mtime)[:self.config.MAX_TASKS_PER_CYCLE]

    def scan_needs_action(self) -> List[Path]:
        """Scan Needs_Action for pending tasks."""
        files = []

        if self.config.NEEDS_ACTION_DIR.exists():
            for item in self.config.NEEDS_ACTION_DIR.rglob('*.md'):
                if item.is_file() and not self.should_skip_file(item):
                    files.append(item)

        return sorted(files, key=lambda f: f.stat().st_mtime)[:self.config.MAX_TASKS_PER_CYCLE]

    def scan_approved(self) -> List[Path]:
        """Scan Approved folder for tasks ready to execute."""
        files = []

        if self.config.APPROVED_DIR.exists():
            for item in self.config.APPROVED_DIR.rglob('*.md'):
                if item.is_file() and not self.should_skip_file(item):
                    files.append(item)

        return sorted(files, key=lambda f: f.stat().st_mtime)[:self.config.MAX_TASKS_PER_CYCLE]

    def create_task_from_file(self, filepath: Path) -> Task:
        """Create Task object from file."""
        content = filepath.read_text(encoding='utf-8')
        metadata, body = self.parse_frontmatter(content)

        return Task(
            id=self.generate_task_id(filepath),
            filename=filepath.name,
            filepath=filepath,
            task_type=self.detect_task_type(filepath.name, content),
            status=TaskStatus.NEW,
            priority=self.detect_priority(content, metadata),
            created_at=datetime.fromtimestamp(filepath.stat().st_mtime),
            content=content,
            metadata=metadata
        )

    def move_file(self, source: Path, dest_dir: Path, add_timestamp: bool = False) -> Path:
        """Move file to destination directory."""
        dest_dir.mkdir(parents=True, exist_ok=True)

        if add_timestamp:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            new_name = f"{source.stem}_{timestamp}{source.suffix}"
        else:
            new_name = source.name

        dest_path = dest_dir / new_name

        # Handle name collision
        counter = 1
        while dest_path.exists():
            new_name = f"{source.stem}_{counter}{source.suffix}"
            dest_path = dest_dir / new_name
            counter += 1

        if not self.dry_run:
            shutil.move(str(source), str(dest_path))

        return dest_path

    def create_metadata_file(self, task: Task, dest_dir: Path) -> Path:
        """Create metadata markdown file for a task."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        meta_filename = f"TASK_{task.task_type.upper()}_{timestamp}.md"
        meta_path = dest_dir / meta_filename

        content = f"""---
task_id: {task.id}
original_file: {task.filename}
task_type: {task.task_type}
priority: {task.priority.value}
status: pending
created: {datetime.now().isoformat()}
processed_by: ai_employee_runner
---

# Task: {task.filename}

## Original Content

{task.content}

## Processing Info

- **Detected Type:** {task.task_type}
- **Priority:** {task.priority.value}
- **Received:** {task.created_at.isoformat()}
- **Processed:** {datetime.now().isoformat()}

## Next Steps

- [ ] Review task details
- [ ] Execute required actions
- [ ] Mark as complete

---
*Auto-generated by AI Employee Runner*
"""

        if not self.dry_run:
            meta_path.write_text(content, encoding='utf-8')

        return meta_path

    def process_inbox_item(self, filepath: Path) -> bool:
        """Process a single inbox item."""
        start_time = datetime.now()
        try:
            task = self.create_task_from_file(filepath)
            self.logger.info(f"Processing inbox item: {task.filename}", task_id=task.id)

            # Audit log: inbox detection
            audit_logger.log(
                action_type=ActionType.INBOX_DETECTED,
                actor="ai_employee_runner",
                target=str(filepath),
                parameters={'task_id': task.id, 'task_type': task.task_type},
                result=ResultStatus.SUCCESS
            )

            # Determine destination based on task type
            if task.task_type == 'email':
                dest_dir = self.config.NEEDS_ACTION_DIR / 'email'
            elif task.task_type == 'linkedin':
                dest_dir = self.config.NEEDS_ACTION_DIR / 'linkedin'
            else:
                dest_dir = self.config.NEEDS_ACTION_DIR / 'general'

            # Move original file
            new_path = self.move_file(filepath, dest_dir)
            self.logger.debug(f"Moved to: {new_path}")

            # Audit log: task moved
            audit_logger.log(
                action_type=ActionType.TASK_MOVED,
                actor="ai_employee_runner",
                target=task.filename,
                parameters={'source': str(filepath.parent), 'destination': str(dest_dir)},
                result=ResultStatus.SUCCESS
            )

            # Create metadata file
            if filepath.suffix not in ['.md']:
                meta_path = self.create_metadata_file(task, dest_dir)
                self.logger.debug(f"Created metadata: {meta_path}")

                # Audit log: task created
                audit_logger.log_with_duration(
                    action_type=ActionType.TASK_CREATED,
                    actor="ai_employee_runner",
                    target=str(meta_path),
                    start_time=start_time,
                    parameters={'task_id': task.id, 'task_type': task.task_type},
                    result=ResultStatus.SUCCESS
                )

            return True

        except Exception as e:
            self.logger.error(f"Failed to process inbox item: {filepath}", error=str(e))
            audit_logger.log_error(
                actor="ai_employee_runner",
                target=str(filepath),
                error_message=str(e),
                error_type=type(e).__name__
            )
            return False

    def process_needs_action_item(self, filepath: Path) -> bool:
        """Process a task in Needs_Action folder."""
        start_time = datetime.now()
        try:
            task = self.create_task_from_file(filepath)
            self.logger.info(f"Processing task: {task.filename}", task_id=task.id)

            # Audit log: task started
            audit_logger.log(
                action_type=ActionType.TASK_STARTED,
                actor="ai_employee_runner",
                target=task.filename,
                parameters={'task_id': task.id, 'task_type': task.task_type},
                result=ResultStatus.PENDING
            )

            # Check if task requires approval based on type
            requires_approval = task.task_type in ['email', 'linkedin']

            if requires_approval:
                # Move to Pending_Approval
                new_path = self.move_file(filepath, self.config.PENDING_APPROVAL_DIR)
                self.logger.info(f"Task requires approval, moved to: {new_path}")

                # Audit log: approval requested
                audit_logger.log_with_duration(
                    action_type=ActionType.APPROVAL_REQUESTED,
                    actor="ai_employee_runner",
                    target=task.filename,
                    start_time=start_time,
                    parameters={'task_type': task.task_type, 'destination': 'Pending_Approval'},
                    approval_status=ApprovalStatus.PENDING,
                    result=ResultStatus.SUCCESS
                )
            else:
                # Simple tasks go directly to Done
                new_path = self.move_file(filepath, self.config.DONE_DIR, add_timestamp=True)
                self.logger.info(f"Task completed, moved to: {new_path}")

                # Audit log: task completed
                audit_logger.log_with_duration(
                    action_type=ActionType.TASK_COMPLETED,
                    actor="ai_employee_runner",
                    target=task.filename,
                    start_time=start_time,
                    parameters={'task_type': task.task_type, 'destination': 'Done'},
                    approval_status=ApprovalStatus.NOT_REQUIRED,
                    result=ResultStatus.SUCCESS
                )

            return True

        except Exception as e:
            self.logger.error(f"Failed to process task: {filepath}", error=str(e))
            audit_logger.log_error(
                actor="ai_employee_runner",
                target=str(filepath),
                error_message=str(e),
                error_type=type(e).__name__
            )
            return False

    def process_approved_item(self, filepath: Path) -> bool:
        """Process an approved task."""
        start_time = datetime.now()
        try:
            task = self.create_task_from_file(filepath)
            self.logger.info(f"Executing approved task: {task.filename}", task_id=task.id)

            # Audit log: approval granted (task moved to Approved means it was approved)
            audit_logger.log(
                action_type=ActionType.APPROVAL_GRANTED,
                actor="ai_employee_runner",
                target=task.filename,
                parameters={'task_id': task.id, 'task_type': task.task_type},
                approval_status=ApprovalStatus.APPROVED,
                result=ResultStatus.SUCCESS
            )

            # Add execution record to file
            if not self.dry_run:
                content = filepath.read_text(encoding='utf-8')
                execution_record = f"""

---

## Execution Record

**Executed At:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Executed By:** AI Employee Runner
**Status:** Completed
**Dry Run:** {self.dry_run}

---
*Task execution completed*
"""
                filepath.write_text(content + execution_record, encoding='utf-8')

            # Move to Done
            new_path = self.move_file(filepath, self.config.DONE_DIR, add_timestamp=True)
            self.logger.info(f"Task executed and moved to Done: {new_path}")

            # Audit log: task completed
            audit_logger.log_with_duration(
                action_type=ActionType.TASK_COMPLETED,
                actor="ai_employee_runner",
                target=task.filename,
                start_time=start_time,
                parameters={
                    'task_id': task.id,
                    'task_type': task.task_type,
                    'destination': 'Done'
                },
                approval_status=ApprovalStatus.APPROVED,
                result=ResultStatus.SUCCESS
            )

            return True

        except Exception as e:
            self.logger.error(f"Failed to execute approved task: {filepath}", error=str(e))
            audit_logger.log_error(
                actor="ai_employee_runner",
                target=str(filepath),
                error_message=str(e),
                error_type=type(e).__name__
            )
            return False


# ==============================================================================
# DASHBOARD UPDATER
# ==============================================================================

class DashboardUpdater:
    """Updates the Dashboard.md with current status."""

    def __init__(self, config: Config, logger: StructuredLogger, dry_run: bool = False):
        self.config = config
        self.logger = logger
        self.dry_run = dry_run

    def count_files(self, directory: Path) -> int:
        """Count files in directory recursively."""
        if not directory.exists():
            return 0
        return sum(1 for _ in directory.rglob('*.md'))

    def update(self, cycle_result: CycleResult):
        """Update Dashboard.md with current status."""
        dashboard_path = self.config.VAULT_DIR / "Dashboard.md"

        # Count tasks in each folder
        counts = {
            'inbox': self.count_files(self.config.INBOX_DIR),
            'needs_action': self.count_files(self.config.NEEDS_ACTION_DIR),
            'pending_approval': self.count_files(self.config.PENDING_APPROVAL_DIR),
            'approved': self.count_files(self.config.APPROVED_DIR),
            'done': self.count_files(self.config.DONE_DIR)
        }

        content = f"""---
last_updated: {datetime.now().isoformat()}
auto_generated: true
---

# AI Employee Dashboard

## System Status

| Metric | Value |
|--------|-------|
| **Last Run** | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |
| **Status** | Active |
| **Mode** | {'Dry Run' if self.dry_run else 'Production'} |

## Task Queue

| Folder | Count |
|--------|-------|
| Inbox | {counts['inbox']} |
| Needs Action | {counts['needs_action']} |
| Pending Approval | {counts['pending_approval']} |
| Approved | {counts['approved']} |
| Done (Today) | {counts['done']} |

## Last Cycle Summary

| Metric | Value |
|--------|-------|
| **Cycle ID** | {cycle_result.cycle_id} |
| **Duration** | {(cycle_result.ended_at - cycle_result.started_at).total_seconds():.1f}s |
| **Tasks Processed** | {cycle_result.tasks_processed} |
| **Tasks Completed** | {cycle_result.tasks_completed} |
| **Tasks Failed** | {cycle_result.tasks_failed} |

## Recent Activity

*Updated automatically every 5 minutes*

---

## Quick Actions

- **Check Inbox:** Review `/Inbox/` for new items
- **Approve Tasks:** Review `/Pending_Approval/` for pending decisions
- **View Logs:** Check `/Logs/` for execution history

---

*Auto-generated by AI Employee Runner*
*Next run in approximately 5 minutes*
"""

        if not self.dry_run:
            dashboard_path.write_text(content, encoding='utf-8')
            self.logger.debug("Dashboard updated")


# ==============================================================================
# MAIN RUNNER
# ==============================================================================

class AIEmployeeRunner:
    """Main AI Employee Runner orchestrator."""

    def __init__(self, dry_run: bool = False, verbose: bool = False):
        self.dry_run = dry_run
        self.verbose = verbose
        self.running = True

        # Load configuration
        Config.load_from_env()
        self.config = Config

        # Initialize components
        self.logger = StructuredLogger(self.config.LOGS_DIR)
        self.health_checker = HealthChecker(self.config, self.logger)
        self.processor = TaskProcessor(self.config, self.logger, dry_run)
        self.dashboard = DashboardUpdater(self.config, self.logger, dry_run)

        # Set log level
        if verbose:
            self.logger.logger.setLevel(logging.DEBUG)
            for handler in self.logger.logger.handlers:
                handler.setLevel(logging.DEBUG)

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

    def run_cycle(self) -> CycleResult:
        """Execute a single processing cycle."""
        cycle_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        started_at = datetime.now()
        errors = []
        tasks_processed = 0
        tasks_completed = 0
        tasks_failed = 0

        self.logger.info(f"=== Starting cycle {cycle_id} ===", cycle_id=cycle_id)

        # Audit log: cycle started
        audit_logger.log(
            action_type=ActionType.CYCLE_STARTED,
            actor="ai_employee_runner",
            target=cycle_id,
            parameters={'dry_run': self.dry_run},
            result=ResultStatus.PENDING
        )

        try:
            # 1. Health check
            healthy, issues = self.health_checker.check_all()
            if not healthy:
                for issue in issues:
                    self.logger.warning(f"Health issue: {issue}")
                    errors.append(issue)

            # 2. Process Inbox
            inbox_files = self.processor.scan_inbox()
            self.logger.info(f"Found {len(inbox_files)} items in Inbox")

            for filepath in inbox_files:
                tasks_processed += 1
                if self.processor.process_inbox_item(filepath):
                    tasks_completed += 1
                else:
                    tasks_failed += 1

            # 3. Process Needs_Action
            action_files = self.processor.scan_needs_action()
            self.logger.info(f"Found {len(action_files)} items in Needs_Action")

            for filepath in action_files:
                tasks_processed += 1
                if self.processor.process_needs_action_item(filepath):
                    tasks_completed += 1
                else:
                    tasks_failed += 1

            # 4. Process Approved items
            approved_files = self.processor.scan_approved()
            self.logger.info(f"Found {len(approved_files)} items in Approved")

            for filepath in approved_files:
                tasks_processed += 1
                if self.processor.process_approved_item(filepath):
                    tasks_completed += 1
                else:
                    tasks_failed += 1

            # 5. Process Retry Queue
            retry_queue_stats = queue_manager.get_queue_stats()
            if retry_queue_stats['ready_for_retry'] > 0:
                self.logger.info(f"Processing {retry_queue_stats['ready_for_retry']} items from Retry Queue")
                retry_results = process_retry_queue("ai_employee_runner")
                tasks_processed += retry_results['processed']
                tasks_completed += retry_results['succeeded']
                tasks_failed += retry_results['failed']

        except Exception as e:
            self.logger.error(f"Cycle error: {e}", error=str(e), traceback=traceback.format_exc())
            errors.append(str(e))
            circuit_breaker.record_failure(e)

        ended_at = datetime.now()

        result = CycleResult(
            cycle_id=cycle_id,
            started_at=started_at,
            ended_at=ended_at,
            tasks_processed=tasks_processed,
            tasks_completed=tasks_completed,
            tasks_failed=tasks_failed,
            errors=errors
        )

        # Update dashboard
        self.dashboard.update(result)

        # Log summary
        self.logger.info(
            f"=== Cycle {cycle_id} complete ===",
            **result.to_dict()
        )

        # Audit log: cycle completed
        audit_logger.log_with_duration(
            action_type=ActionType.CYCLE_COMPLETED,
            actor="ai_employee_runner",
            target=cycle_id,
            start_time=started_at,
            parameters={
                'tasks_processed': tasks_processed,
                'tasks_completed': tasks_completed,
                'tasks_failed': tasks_failed,
                'error_count': len(errors)
            },
            result=ResultStatus.SUCCESS if tasks_failed == 0 else ResultStatus.PARTIAL
        )
        audit_logger.flush()

        return result

    def run_once(self):
        """Run a single cycle."""
        self.logger.info("Running single cycle")

        # Audit log: system started
        audit_logger.log(
            action_type=ActionType.SYSTEM_STARTED,
            actor="ai_employee_runner",
            target="single_cycle",
            parameters={'mode': 'once', 'dry_run': self.dry_run},
            result=ResultStatus.SUCCESS
        )

        if self.dry_run:
            self.logger.info("DRY RUN MODE - No changes will be made")

        result = self.run_cycle()

        # Audit log: system stopped
        audit_logger.log(
            action_type=ActionType.SYSTEM_STOPPED,
            actor="ai_employee_runner",
            target="single_cycle",
            parameters={
                'mode': 'once',
                'tasks_processed': result.tasks_processed,
                'tasks_completed': result.tasks_completed
            },
            result=ResultStatus.SUCCESS
        )
        audit_logger.flush()

        return result

    def run_daemon(self):
        """Run continuously as a daemon."""
        self.logger.info("Starting AI Employee Runner in daemon mode")
        self.logger.info(f"Cycle interval: {self.config.CYCLE_INTERVAL} seconds")

        # Audit log: system started
        audit_logger.log(
            action_type=ActionType.SYSTEM_STARTED,
            actor="ai_employee_runner",
            target="daemon",
            parameters={
                'mode': 'daemon',
                'dry_run': self.dry_run,
                'cycle_interval': self.config.CYCLE_INTERVAL
            },
            result=ResultStatus.SUCCESS
        )

        if self.dry_run:
            self.logger.info("DRY RUN MODE - No changes will be made")

        total_cycles = 0
        total_tasks = 0

        while self.running:
            try:
                result = self.run_cycle()
                total_cycles += 1
                total_tasks += result.tasks_processed

                if self.running:
                    self.logger.info(f"Sleeping for {self.config.CYCLE_INTERVAL} seconds...")

                    # Sleep in small increments to allow graceful shutdown
                    sleep_remaining = self.config.CYCLE_INTERVAL
                    while sleep_remaining > 0 and self.running:
                        time.sleep(min(5, sleep_remaining))
                        sleep_remaining -= 5

            except Exception as e:
                self.logger.error(f"Daemon error: {e}", traceback=traceback.format_exc())
                audit_logger.log_error(
                    actor="ai_employee_runner",
                    target="daemon",
                    error_message=str(e),
                    error_type=type(e).__name__
                )
                time.sleep(30)  # Wait before retry

        # Audit log: system stopped
        audit_logger.log(
            action_type=ActionType.SYSTEM_STOPPED,
            actor="ai_employee_runner",
            target="daemon",
            parameters={
                'mode': 'daemon',
                'total_cycles': total_cycles,
                'total_tasks': total_tasks,
                'reason': 'shutdown_requested'
            },
            result=ResultStatus.SUCCESS
        )
        audit_logger.flush()

        self.logger.info("AI Employee Runner stopped")


# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='AI Employee Runner - Automated Task Processor',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 run_ai_employee.py              # Run as daemon (continuous)
  python3 run_ai_employee.py --once       # Run single cycle
  python3 run_ai_employee.py --dry-run    # Test without changes
  python3 run_ai_employee.py --verbose    # Debug output
        """
    )

    parser.add_argument(
        '--once',
        action='store_true',
        help='Run a single cycle and exit'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simulate actions without making changes'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose (debug) output'
    )

    parser.add_argument(
        '--version',
        action='version',
        version='AI Employee Runner v1.0.0'
    )

    args = parser.parse_args()

    # Banner
    print("=" * 60)
    print("   AI Employee Runner - Silver Tier")
    print("   Production-Ready Automated Scheduler")
    print("=" * 60)
    print(f"   Mode: {'Single Cycle' if args.once else 'Daemon (Continuous)'}")
    print(f"   Dry Run: {args.dry_run}")
    print(f"   Verbose: {args.verbose}")
    print("=" * 60)
    print()

    # Acquire lock to prevent concurrent runs
    lock = FileLock(Config.LOCK_FILE)

    try:
        if not lock.acquire():
            print("ERROR: Another instance is already running.")
            print(f"       Lock file: {Config.LOCK_FILE}")
            sys.exit(1)

        runner = AIEmployeeRunner(dry_run=args.dry_run, verbose=args.verbose)

        if args.once:
            result = runner.run_once()
            print()
            print("Cycle Result:")
            print(json.dumps(result.to_dict(), indent=2))
        else:
            runner.run_daemon()

    except KeyboardInterrupt:
        print("\nShutdown requested...")
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        traceback.print_exc()
        sys.exit(1)
    finally:
        lock.release()
        print("AI Employee Runner stopped.")


if __name__ == "__main__":
    main()
