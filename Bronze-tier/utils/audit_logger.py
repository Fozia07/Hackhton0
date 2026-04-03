#!/usr/bin/env python3
"""
Enterprise Audit Logging System
Gold Tier Component

Centralized, thread-safe audit logging for the AI Employee system.
Records all system actions in structured JSON format with automatic
log rotation and retention management.

Features:
- Thread-safe logging with file locking
- Atomic writes to prevent corruption
- Auto-cleanup of logs older than 90 days
- High-performance buffered writes
- Graceful failure handling
- Standard JSON format for all entries

Usage:
    from utils.audit_logger import AuditLogger, ActionType

    logger = AuditLogger()
    logger.log(
        action_type=ActionType.TASK_CREATED,
        actor="filesystem_watcher",
        target="/Inbox/task.txt",
        parameters={"size": 1024},
        result="success"
    )

Author: AI Employee System - Gold Tier
Version: 1.0.0
"""

import os
import sys
import json
import fcntl
import threading
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass, asdict
from contextlib import contextmanager
import traceback


# ==============================================================================
# ACTION TYPES ENUMERATION
# ==============================================================================

class ActionType(Enum):
    """Standardized action types for audit logging."""

    # File System Actions
    INBOX_DETECTED = "inbox_detected"
    TASK_CREATED = "task_created"
    TASK_MOVED = "task_moved"
    TASK_DELETED = "task_deleted"
    FILE_PROCESSED = "file_processed"

    # Task Lifecycle
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_SKIPPED = "task_skipped"

    # Planning
    PLAN_GENERATED = "plan_generated"
    PLAN_EXECUTED = "plan_executed"
    PLAN_FAILED = "plan_failed"

    # Approval Workflow
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_REJECTED = "approval_rejected"
    APPROVAL_EXPIRED = "approval_expired"

    # External Actions
    EMAIL_SENT = "email_sent"
    EMAIL_DRAFT_CREATED = "email_draft_created"
    EMAIL_FAILED = "email_failed"

    # Social Media
    LINKEDIN_POST_CREATED = "linkedin_post_created"
    LINKEDIN_POST_PUBLISHED = "linkedin_post_published"
    LINKEDIN_POST_FAILED = "linkedin_post_failed"
    FACEBOOK_POST = "facebook_post"
    TWITTER_POST = "twitter_post"

    # Business Intelligence
    CEO_BRIEFING_STARTED = "ceo_briefing_started"
    CEO_BRIEFING_GENERATED = "ceo_briefing_generated"
    CEO_BRIEFING_FAILED = "ceo_briefing_failed"
    FINANCIAL_ANALYSIS = "financial_analysis"

    # System Events
    SYSTEM_STARTED = "system_started"
    SYSTEM_STOPPED = "system_stopped"
    CYCLE_STARTED = "cycle_started"
    CYCLE_COMPLETED = "cycle_completed"
    HEALTH_CHECK = "health_check"

    # Errors & Recovery
    ERROR_OCCURRED = "error_occurred"
    RETRY_ATTEMPTED = "retry_attempted"
    RECOVERY_ATTEMPTED = "recovery_attempted"
    RECOVERY_SUCCESS = "recovery_success"
    RECOVERY_FAILED = "recovery_failed"
    CIRCUIT_BREAKER_OPENED = "circuit_breaker_opened"
    CIRCUIT_BREAKER_CLOSED = "circuit_breaker_closed"
    TASK_QUEUED = "task_queued"

    # MCP Actions
    MCP_REQUEST = "mcp_request"
    MCP_RESPONSE = "mcp_response"
    MCP_ERROR = "mcp_error"


class ApprovalStatus(Enum):
    """Approval status values."""
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_APPROVED = "auto_approved"
    EXPIRED = "expired"


class ResultStatus(Enum):
    """Result status values."""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    SKIPPED = "skipped"
    PENDING = "pending"


# ==============================================================================
# LOG ENTRY DATA CLASS
# ==============================================================================

@dataclass
class AuditLogEntry:
    """Structured audit log entry."""
    timestamp: str
    action_type: str
    actor: str
    target: str
    parameters: Dict[str, Any]
    approval_status: str
    result: str
    error: Optional[str] = None
    duration_ms: Optional[float] = None
    correlation_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        data = {
            'timestamp': self.timestamp,
            'action_type': self.action_type,
            'actor': self.actor,
            'target': self.target,
            'parameters': self.parameters,
            'approval_status': self.approval_status,
            'result': self.result,
        }

        # Include optional fields only if set
        if self.error is not None:
            data['error'] = self.error
        if self.duration_ms is not None:
            data['duration_ms'] = self.duration_ms
        if self.correlation_id is not None:
            data['correlation_id'] = self.correlation_id
        if self.metadata is not None:
            data['metadata'] = self.metadata

        return data


# ==============================================================================
# FILE LOCK CONTEXT MANAGER
# ==============================================================================

@contextmanager
def file_lock(filepath: Path, mode: str = 'r+'):
    """
    Cross-platform file locking context manager.
    Uses fcntl on Unix, fallback for Windows.
    """
    fd = None
    try:
        # Ensure parent directory exists
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # Create file if doesn't exist
        if not filepath.exists():
            filepath.write_text('[]')

        fd = open(filepath, mode)

        # Try to acquire lock
        if sys.platform != 'win32':
            fcntl.flock(fd.fileno(), fcntl.LOCK_EX)

        yield fd

    finally:
        if fd:
            if sys.platform != 'win32':
                fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
            fd.close()


# ==============================================================================
# MAIN AUDIT LOGGER CLASS
# ==============================================================================

class AuditLogger:
    """
    Enterprise-grade audit logging system.

    Features:
    - Thread-safe logging with file locking
    - Atomic writes using temp file + rename
    - Automatic log rotation by date
    - Retention management (90 days default)
    - High-performance with buffered writes
    - Graceful failure handling
    """

    # Default configuration
    DEFAULT_LOG_DIR = Path(__file__).parent.parent / "AI_Employee_Vault" / "Logs"
    DEFAULT_RETENTION_DAYS = 90
    LOG_FILE_FORMAT = "{date}.json"

    # Singleton instance
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """Singleton pattern for global logger instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(
        self,
        log_dir: Optional[Path] = None,
        retention_days: int = DEFAULT_RETENTION_DAYS,
        buffer_size: int = 10,
        auto_flush: bool = True
    ):
        """
        Initialize the audit logger.

        Args:
            log_dir: Directory for log files
            retention_days: Days to retain logs (default 90)
            buffer_size: Number of entries to buffer before flush
            auto_flush: Auto-flush after each write
        """
        if self._initialized:
            return

        self.log_dir = log_dir or self.DEFAULT_LOG_DIR
        self.retention_days = retention_days
        self.buffer_size = buffer_size
        self.auto_flush = auto_flush

        self._buffer: List[AuditLogEntry] = []
        self._buffer_lock = threading.Lock()
        self._write_lock = threading.Lock()

        # Ensure log directory exists
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Run initial cleanup
        self._cleanup_old_logs()

        self._initialized = True

    def _get_log_file_path(self, date: Optional[datetime] = None) -> Path:
        """Get the log file path for a specific date."""
        if date is None:
            date = datetime.now()
        filename = self.LOG_FILE_FORMAT.format(date=date.strftime('%Y-%m-%d'))
        return self.log_dir / filename

    def _cleanup_old_logs(self):
        """Remove log files older than retention period."""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.retention_days)

            for log_file in self.log_dir.glob("*.json"):
                # Skip non-date formatted files
                try:
                    # Extract date from filename (YYYY-MM-DD.json)
                    date_str = log_file.stem
                    file_date = datetime.strptime(date_str, '%Y-%m-%d')

                    if file_date < cutoff_date:
                        log_file.unlink()
                except (ValueError, OSError):
                    continue

        except Exception:
            # Silently ignore cleanup errors
            pass

    def _read_log_file(self, filepath: Path) -> List[Dict]:
        """Read existing log entries from file."""
        try:
            if filepath.exists():
                content = filepath.read_text(encoding='utf-8')
                if content.strip():
                    return json.loads(content)
        except (json.JSONDecodeError, IOError):
            pass
        return []

    def _write_log_file_atomic(self, filepath: Path, entries: List[Dict]):
        """
        Write log entries atomically using temp file + rename.
        This ensures the log file is never corrupted.
        """
        # Create temp file in same directory for atomic rename
        temp_fd, temp_path = tempfile.mkstemp(
            suffix='.tmp',
            prefix='audit_',
            dir=filepath.parent
        )

        try:
            # Write to temp file
            with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                json.dump(entries, f, indent=2, default=str)

            # Atomic rename (works on same filesystem)
            shutil.move(temp_path, filepath)

        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

    def log(
        self,
        action_type: ActionType,
        actor: str,
        target: str,
        parameters: Optional[Dict[str, Any]] = None,
        approval_status: ApprovalStatus = ApprovalStatus.NOT_REQUIRED,
        result: ResultStatus = ResultStatus.SUCCESS,
        error: Optional[str] = None,
        duration_ms: Optional[float] = None,
        correlation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AuditLogEntry:
        """
        Log an audit entry.

        Args:
            action_type: Type of action being logged
            actor: Who/what performed the action
            target: What was acted upon
            parameters: Action parameters
            approval_status: Approval state
            result: Outcome of the action
            error: Error message if failed
            duration_ms: Action duration in milliseconds
            correlation_id: ID to correlate related actions
            metadata: Additional metadata

        Returns:
            The created log entry
        """
        entry = AuditLogEntry(
            timestamp=datetime.now().isoformat(),
            action_type=action_type.value if isinstance(action_type, ActionType) else str(action_type),
            actor=actor,
            target=target,
            parameters=parameters or {},
            approval_status=approval_status.value if isinstance(approval_status, ApprovalStatus) else str(approval_status),
            result=result.value if isinstance(result, ResultStatus) else str(result),
            error=error,
            duration_ms=duration_ms,
            correlation_id=correlation_id,
            metadata=metadata
        )

        with self._buffer_lock:
            self._buffer.append(entry)

            if self.auto_flush or len(self._buffer) >= self.buffer_size:
                self._flush_buffer()

        return entry

    def _flush_buffer(self):
        """Flush buffered entries to disk."""
        if not self._buffer:
            return

        entries_to_write = self._buffer.copy()
        self._buffer.clear()

        with self._write_lock:
            try:
                filepath = self._get_log_file_path()

                # Read existing entries
                existing = self._read_log_file(filepath)

                # Append new entries
                for entry in entries_to_write:
                    existing.append(entry.to_dict())

                # Write atomically
                self._write_log_file_atomic(filepath, existing)

            except Exception as e:
                # On failure, put entries back in buffer
                self._buffer = entries_to_write + self._buffer
                # Log to stderr as fallback
                print(f"[AUDIT_LOGGER_ERROR] Failed to write logs: {e}", file=sys.stderr)

    def flush(self):
        """Manually flush any buffered entries."""
        with self._buffer_lock:
            self._flush_buffer()

    def log_error(
        self,
        actor: str,
        target: str,
        error_message: str,
        error_type: Optional[str] = None,
        stack_trace: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None
    ) -> AuditLogEntry:
        """
        Convenience method for logging errors.
        """
        params = parameters or {}
        if error_type:
            params['error_type'] = error_type
        if stack_trace:
            params['stack_trace'] = stack_trace[:1000]  # Limit size

        return self.log(
            action_type=ActionType.ERROR_OCCURRED,
            actor=actor,
            target=target,
            parameters=params,
            result=ResultStatus.FAILURE,
            error=error_message
        )

    def log_with_duration(
        self,
        action_type: ActionType,
        actor: str,
        target: str,
        start_time: datetime,
        **kwargs
    ) -> AuditLogEntry:
        """
        Log an action with automatic duration calculation.
        """
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        return self.log(
            action_type=action_type,
            actor=actor,
            target=target,
            duration_ms=round(duration_ms, 2),
            **kwargs
        )

    @contextmanager
    def timed_action(
        self,
        action_type: ActionType,
        actor: str,
        target: str,
        parameters: Optional[Dict[str, Any]] = None
    ):
        """
        Context manager for timing and logging actions.

        Usage:
            with logger.timed_action(ActionType.TASK_STARTED, "worker", "task1") as ctx:
                # do work
                ctx['result'] = ResultStatus.SUCCESS
        """
        start_time = datetime.now()
        context = {
            'result': ResultStatus.SUCCESS,
            'error': None,
            'metadata': {}
        }

        try:
            yield context
        except Exception as e:
            context['result'] = ResultStatus.FAILURE
            context['error'] = str(e)
            raise
        finally:
            self.log_with_duration(
                action_type=action_type,
                actor=actor,
                target=target,
                start_time=start_time,
                parameters=parameters,
                result=context['result'],
                error=context['error'],
                metadata=context.get('metadata')
            )

    def get_logs(
        self,
        date: Optional[datetime] = None,
        action_type: Optional[ActionType] = None,
        actor: Optional[str] = None,
        result: Optional[ResultStatus] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Retrieve log entries with optional filtering.

        Args:
            date: Date to retrieve logs for (default today)
            action_type: Filter by action type
            actor: Filter by actor
            result: Filter by result status
            limit: Maximum entries to return

        Returns:
            List of matching log entries
        """
        filepath = self._get_log_file_path(date)
        entries = self._read_log_file(filepath)

        # Apply filters
        if action_type:
            action_value = action_type.value if isinstance(action_type, ActionType) else str(action_type)
            entries = [e for e in entries if e.get('action_type') == action_value]

        if actor:
            entries = [e for e in entries if e.get('actor') == actor]

        if result:
            result_value = result.value if isinstance(result, ResultStatus) else str(result)
            entries = [e for e in entries if e.get('result') == result_value]

        # Return limited entries (most recent first)
        return entries[-limit:][::-1] if entries else []

    def get_statistics(self, date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Get statistics for a day's logs.
        """
        entries = self.get_logs(date, limit=10000)

        stats = {
            'total_entries': len(entries),
            'by_action_type': {},
            'by_result': {},
            'by_actor': {},
            'error_count': 0,
            'avg_duration_ms': 0
        }

        durations = []

        for entry in entries:
            # Count by action type
            action = entry.get('action_type', 'unknown')
            stats['by_action_type'][action] = stats['by_action_type'].get(action, 0) + 1

            # Count by result
            result = entry.get('result', 'unknown')
            stats['by_result'][result] = stats['by_result'].get(result, 0) + 1

            # Count by actor
            actor = entry.get('actor', 'unknown')
            stats['by_actor'][actor] = stats['by_actor'].get(actor, 0) + 1

            # Count errors
            if entry.get('error'):
                stats['error_count'] += 1

            # Collect durations
            if entry.get('duration_ms'):
                durations.append(entry['duration_ms'])

        if durations:
            stats['avg_duration_ms'] = round(sum(durations) / len(durations), 2)

        return stats


# ==============================================================================
# GLOBAL LOGGER INSTANCE
# ==============================================================================

# Create global singleton instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger(log_dir: Optional[Path] = None) -> AuditLogger:
    """
    Get the global audit logger instance.

    Args:
        log_dir: Optional custom log directory

    Returns:
        AuditLogger singleton instance
    """
    global _audit_logger

    if _audit_logger is None:
        _audit_logger = AuditLogger(log_dir=log_dir)

    return _audit_logger


def audit_log(
    action_type: ActionType,
    actor: str,
    target: str,
    **kwargs
) -> AuditLogEntry:
    """
    Convenience function for quick logging.

    Usage:
        from utils.audit_logger import audit_log, ActionType

        audit_log(ActionType.TASK_CREATED, "watcher", "/Inbox/task.txt")
    """
    return get_audit_logger().log(
        action_type=action_type,
        actor=actor,
        target=target,
        **kwargs
    )


# ==============================================================================
# DECORATOR FOR AUTOMATIC LOGGING
# ==============================================================================

def audited(action_type: ActionType, actor: str):
    """
    Decorator to automatically log function execution.

    Usage:
        @audited(ActionType.TASK_STARTED, "processor")
        def process_task(task_path):
            # function body
            return result
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            target = str(args[0]) if args else "unknown"
            logger = get_audit_logger()

            start_time = datetime.now()
            result_status = ResultStatus.SUCCESS
            error_msg = None

            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                result_status = ResultStatus.FAILURE
                error_msg = str(e)
                raise
            finally:
                logger.log_with_duration(
                    action_type=action_type,
                    actor=actor,
                    target=target,
                    start_time=start_time,
                    result=result_status,
                    error=error_msg,
                    parameters={'function': func.__name__}
                )

        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    return decorator


# ==============================================================================
# CLI FOR TESTING
# ==============================================================================

def main():
    """CLI for testing the audit logger."""
    import argparse

    parser = argparse.ArgumentParser(description='Audit Logger CLI')
    parser.add_argument('--test', action='store_true', help='Run test logging')
    parser.add_argument('--stats', action='store_true', help='Show today\'s statistics')
    parser.add_argument('--list', type=int, default=0, help='List N recent entries')
    parser.add_argument('--cleanup', action='store_true', help='Run log cleanup')

    args = parser.parse_args()

    logger = get_audit_logger()

    if args.test:
        print("Running audit logger tests...")

        # Test various log types
        logger.log(
            action_type=ActionType.SYSTEM_STARTED,
            actor="audit_logger_cli",
            target="system",
            parameters={'version': '1.0.0'},
            result=ResultStatus.SUCCESS
        )

        logger.log(
            action_type=ActionType.TASK_CREATED,
            actor="test",
            target="/Inbox/test_task.txt",
            parameters={'size': 1024, 'type': 'text'},
            result=ResultStatus.SUCCESS
        )

        logger.log_error(
            actor="test",
            target="/Inbox/error_task.txt",
            error_message="Test error for demonstration",
            error_type="TestError"
        )

        logger.flush()
        print("Test entries written successfully!")
        print(f"Log file: {logger._get_log_file_path()}")

    if args.stats:
        stats = logger.get_statistics()
        print("\n=== Today's Audit Log Statistics ===")
        print(f"Total Entries: {stats['total_entries']}")
        print(f"Error Count: {stats['error_count']}")
        print(f"Avg Duration: {stats['avg_duration_ms']}ms")
        print("\nBy Action Type:")
        for action, count in stats['by_action_type'].items():
            print(f"  {action}: {count}")
        print("\nBy Result:")
        for result, count in stats['by_result'].items():
            print(f"  {result}: {count}")

    if args.list > 0:
        entries = logger.get_logs(limit=args.list)
        print(f"\n=== Last {args.list} Log Entries ===")
        for entry in entries:
            print(json.dumps(entry, indent=2))

    if args.cleanup:
        print("Running log cleanup...")
        logger._cleanup_old_logs()
        print("Cleanup complete!")


if __name__ == "__main__":
    main()
