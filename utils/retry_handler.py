#!/usr/bin/env python3
"""
Error Recovery & Retry System
Gold Tier Component

Production-grade failure recovery with:
- Exponential backoff retry mechanism
- Circuit breaker pattern
- Failure classification
- Task re-queueing
- Graceful degradation

Author: AI Employee System - Gold Tier
Version: 1.0.0
"""

import os
import sys
import json
import time
import random
import shutil
import threading
import traceback
from pathlib import Path
from datetime import datetime, timedelta
from typing import Callable, Any, Optional, Dict, List, Type, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from functools import wraps
from contextlib import contextmanager

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.audit_logger import (
    get_audit_logger,
    ActionType,
    ResultStatus
)

# Initialize audit logger
audit_logger = get_audit_logger()


# ==============================================================================
# ENUMERATIONS
# ==============================================================================

class FailureType(Enum):
    """Classification of failure types."""
    IO_ERROR = "io_error"                    # File system, disk errors
    NETWORK_ERROR = "network_error"          # Connection, timeout errors
    EXTERNAL_API = "external_api"            # Third-party API failures
    SYSTEM_ERROR = "system_error"            # Memory, resource errors
    VALIDATION_ERROR = "validation_error"    # Data validation failures
    PERMISSION_ERROR = "permission_error"    # Access denied
    TRANSIENT_ERROR = "transient_error"      # Temporary issues
    PERMANENT_ERROR = "permanent_error"      # Non-recoverable errors
    UNKNOWN_ERROR = "unknown_error"          # Unclassified errors


class RecoveryMode(Enum):
    """Recovery action modes."""
    IMMEDIATE_RETRY = "immediate_retry"      # Retry now
    DEFERRED_RETRY = "deferred_retry"        # Queue for later
    GRACEFUL_SKIP = "graceful_skip"          # Skip with logging
    SYSTEM_DEGRADATION = "system_degradation" # Enter degraded mode
    ABORT = "abort"                          # Stop processing


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing, reject requests
    HALF_OPEN = "half_open" # Testing recovery


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 5
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter_factor: float = 0.5
    retry_on: List[Type[Exception]] = field(default_factory=lambda: [
        IOError,
        OSError,
        ConnectionError,
        TimeoutError,
        PermissionError,
    ])
    no_retry_on: List[Type[Exception]] = field(default_factory=lambda: [
        KeyboardInterrupt,
        SystemExit,
        MemoryError,
    ])


@dataclass
class RetryState:
    """Current state of a retry operation."""
    attempt: int = 0
    max_attempts: int = 5
    last_error: Optional[str] = None
    last_error_type: Optional[str] = None
    failure_type: Optional[FailureType] = None
    started_at: Optional[str] = None
    last_attempt_at: Optional[str] = None
    next_retry_at: Optional[str] = None
    total_delay: float = 0.0
    successful: bool = False

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'attempt': self.attempt,
            'max_attempts': self.max_attempts,
            'last_error': self.last_error,
            'last_error_type': self.last_error_type,
            'failure_type': self.failure_type.value if self.failure_type else None,
            'started_at': self.started_at,
            'last_attempt_at': self.last_attempt_at,
            'next_retry_at': self.next_retry_at,
            'total_delay': self.total_delay,
            'successful': self.successful
        }


@dataclass
class TaskRetryMetadata:
    """Metadata for a task in the retry queue."""
    task_id: str
    original_path: str
    task_type: str
    attempt_count: int
    max_attempts: int
    last_error: str
    last_error_type: str
    failure_type: str
    created_at: str
    last_attempt_at: str
    next_retry_at: str
    actor: str
    parameters: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'TaskRetryMetadata':
        """Create from dictionary."""
        return cls(**data)


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5           # Failures before opening
    success_threshold: int = 3           # Successes to close
    timeout_seconds: float = 60.0        # Time before half-open
    half_open_max_calls: int = 3         # Max calls in half-open


# ==============================================================================
# FAILURE CLASSIFIER
# ==============================================================================

class FailureClassifier:
    """Classifies exceptions into failure types."""

    # Exception to failure type mapping
    EXCEPTION_MAP = {
        # IO Errors
        IOError: FailureType.IO_ERROR,
        FileNotFoundError: FailureType.IO_ERROR,
        FileExistsError: FailureType.IO_ERROR,
        IsADirectoryError: FailureType.IO_ERROR,
        NotADirectoryError: FailureType.IO_ERROR,

        # Network Errors
        ConnectionError: FailureType.NETWORK_ERROR,
        ConnectionRefusedError: FailureType.NETWORK_ERROR,
        ConnectionResetError: FailureType.NETWORK_ERROR,
        TimeoutError: FailureType.NETWORK_ERROR,
        BrokenPipeError: FailureType.NETWORK_ERROR,

        # Permission Errors
        PermissionError: FailureType.PERMISSION_ERROR,

        # System Errors
        MemoryError: FailureType.SYSTEM_ERROR,
        OSError: FailureType.SYSTEM_ERROR,
        SystemError: FailureType.SYSTEM_ERROR,

        # Validation Errors
        ValueError: FailureType.VALIDATION_ERROR,
        TypeError: FailureType.VALIDATION_ERROR,
        KeyError: FailureType.VALIDATION_ERROR,
        AttributeError: FailureType.VALIDATION_ERROR,
    }

    # Recoverable failure types
    RECOVERABLE_TYPES = {
        FailureType.IO_ERROR,
        FailureType.NETWORK_ERROR,
        FailureType.EXTERNAL_API,
        FailureType.TRANSIENT_ERROR,
        FailureType.PERMISSION_ERROR,  # May be transient
    }

    # Error message patterns for classification
    MESSAGE_PATTERNS = {
        'timeout': FailureType.NETWORK_ERROR,
        'connection': FailureType.NETWORK_ERROR,
        'refused': FailureType.NETWORK_ERROR,
        'api': FailureType.EXTERNAL_API,
        'rate limit': FailureType.EXTERNAL_API,
        'quota': FailureType.EXTERNAL_API,
        'permission': FailureType.PERMISSION_ERROR,
        'access denied': FailureType.PERMISSION_ERROR,
        'disk full': FailureType.IO_ERROR,
        'no space': FailureType.IO_ERROR,
        'memory': FailureType.SYSTEM_ERROR,
    }

    @classmethod
    def classify(cls, exception: Exception) -> FailureType:
        """Classify an exception into a failure type."""
        # Direct type match
        exc_type = type(exception)
        if exc_type in cls.EXCEPTION_MAP:
            return cls.EXCEPTION_MAP[exc_type]

        # Check inheritance
        for known_type, failure_type in cls.EXCEPTION_MAP.items():
            if isinstance(exception, known_type):
                return failure_type

        # Check error message patterns
        error_msg = str(exception).lower()
        for pattern, failure_type in cls.MESSAGE_PATTERNS.items():
            if pattern in error_msg:
                return failure_type

        return FailureType.UNKNOWN_ERROR

    @classmethod
    def is_recoverable(cls, failure_type: FailureType) -> bool:
        """Check if a failure type is recoverable."""
        return failure_type in cls.RECOVERABLE_TYPES

    @classmethod
    def get_recovery_mode(cls, failure_type: FailureType, attempt: int, max_attempts: int) -> RecoveryMode:
        """Determine the recovery mode based on failure type and attempt count."""
        if failure_type == FailureType.PERMANENT_ERROR:
            return RecoveryMode.ABORT

        if failure_type == FailureType.VALIDATION_ERROR:
            return RecoveryMode.GRACEFUL_SKIP

        if not cls.is_recoverable(failure_type):
            if attempt >= max_attempts:
                return RecoveryMode.GRACEFUL_SKIP
            return RecoveryMode.DEFERRED_RETRY

        if attempt < max_attempts:
            return RecoveryMode.IMMEDIATE_RETRY

        return RecoveryMode.DEFERRED_RETRY


# ==============================================================================
# CIRCUIT BREAKER
# ==============================================================================

class CircuitBreaker:
    """
    Circuit breaker pattern implementation.

    Prevents cascading failures by stopping calls to a failing service.
    """

    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.half_open_calls = 0
        self._lock = threading.Lock()

    def can_execute(self) -> bool:
        """Check if execution is allowed."""
        with self._lock:
            if self.state == CircuitState.CLOSED:
                return True

            if self.state == CircuitState.OPEN:
                # Check if timeout has passed
                if self.last_failure_time:
                    elapsed = (datetime.now() - self.last_failure_time).total_seconds()
                    if elapsed >= self.config.timeout_seconds:
                        self._transition_to_half_open()
                        return True
                return False

            if self.state == CircuitState.HALF_OPEN:
                if self.half_open_calls < self.config.half_open_max_calls:
                    self.half_open_calls += 1
                    return True
                return False

            return False

    def record_success(self):
        """Record a successful execution."""
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    self._transition_to_closed()
            elif self.state == CircuitState.CLOSED:
                # Reset failure count on success
                self.failure_count = 0

    def record_failure(self, exception: Exception = None):
        """Record a failed execution."""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = datetime.now()

            if self.state == CircuitState.HALF_OPEN:
                self._transition_to_open()
            elif self.state == CircuitState.CLOSED:
                if self.failure_count >= self.config.failure_threshold:
                    self._transition_to_open()

    def _transition_to_open(self):
        """Transition to open state."""
        self.state = CircuitState.OPEN
        self.success_count = 0
        self.half_open_calls = 0

        # Log circuit opened
        audit_logger.log(
            action_type=ActionType.WARNING_RAISED,
            actor="circuit_breaker",
            target=self.name,
            parameters={
                'state': 'open',
                'failure_count': self.failure_count,
                'event': 'circuit_opened'
            },
            result=ResultStatus.FAILURE
        )

    def _transition_to_half_open(self):
        """Transition to half-open state."""
        self.state = CircuitState.HALF_OPEN
        self.half_open_calls = 0
        self.success_count = 0

        # Log circuit half-open
        audit_logger.log(
            action_type=ActionType.RECOVERY_ATTEMPTED,
            actor="circuit_breaker",
            target=self.name,
            parameters={
                'state': 'half_open',
                'event': 'circuit_testing'
            },
            result=ResultStatus.PENDING
        )

    def _transition_to_closed(self):
        """Transition to closed state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0

        # Log circuit closed
        audit_logger.log(
            action_type=ActionType.RECOVERY_SUCCESS,
            actor="circuit_breaker",
            target=self.name,
            parameters={
                'state': 'closed',
                'event': 'circuit_recovered'
            },
            result=ResultStatus.SUCCESS
        )

    def get_state(self) -> Dict:
        """Get current circuit breaker state."""
        return {
            'name': self.name,
            'state': self.state.value,
            'failure_count': self.failure_count,
            'success_count': self.success_count,
            'last_failure': self.last_failure_time.isoformat() if self.last_failure_time else None
        }

    def reset(self):
        """Reset the circuit breaker."""
        with self._lock:
            self._transition_to_closed()


# ==============================================================================
# RETRY QUEUE MANAGER
# ==============================================================================

class RetryQueueManager:
    """Manages the retry queue for failed tasks."""

    def __init__(self, queue_dir: Path = None):
        base_dir = Path(__file__).parent.parent
        self.queue_dir = queue_dir or base_dir / "AI_Employee_Vault" / "Retry_Queue"
        self.queue_dir.mkdir(parents=True, exist_ok=True)

    def enqueue(self, metadata: TaskRetryMetadata) -> Path:
        """Add a task to the retry queue."""
        filename = f"RETRY_{metadata.task_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.queue_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(metadata.to_dict(), f, indent=2)

        # Log task queued
        audit_logger.log(
            action_type=ActionType.TASK_MOVED,
            actor="retry_queue_manager",
            target=metadata.task_id,
            parameters={
                'queue_file': filename,
                'attempt': metadata.attempt_count,
                'next_retry': metadata.next_retry_at,
                'destination': 'Retry_Queue'
            },
            result=ResultStatus.SUCCESS
        )

        return filepath

    def dequeue(self, task_id: str) -> Optional[TaskRetryMetadata]:
        """Remove and return a task from the retry queue."""
        for filepath in self.queue_dir.glob(f"RETRY_{task_id}_*.json"):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                metadata = TaskRetryMetadata.from_dict(data)
                filepath.unlink()
                return metadata
            except Exception:
                continue
        return None

    def get_ready_tasks(self) -> List[TaskRetryMetadata]:
        """Get all tasks ready for retry."""
        ready_tasks = []
        now = datetime.now()

        for filepath in self.queue_dir.glob("RETRY_*.json"):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                metadata = TaskRetryMetadata.from_dict(data)

                # Check if ready for retry
                next_retry = datetime.fromisoformat(metadata.next_retry_at)
                if next_retry <= now:
                    ready_tasks.append(metadata)
            except Exception:
                continue

        return ready_tasks

    def get_all_tasks(self) -> List[TaskRetryMetadata]:
        """Get all tasks in the queue."""
        tasks = []
        for filepath in self.queue_dir.glob("RETRY_*.json"):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                tasks.append(TaskRetryMetadata.from_dict(data))
            except Exception:
                continue
        return tasks

    def remove_task(self, task_id: str) -> bool:
        """Remove a task from the queue."""
        for filepath in self.queue_dir.glob(f"RETRY_{task_id}_*.json"):
            try:
                filepath.unlink()
                return True
            except Exception:
                continue
        return False

    def clear_expired(self, max_age_hours: int = 72) -> int:
        """Clear tasks that have exceeded maximum retry age."""
        cleared = 0
        cutoff = datetime.now() - timedelta(hours=max_age_hours)

        for filepath in self.queue_dir.glob("RETRY_*.json"):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                created = datetime.fromisoformat(data['created_at'])
                if created < cutoff:
                    filepath.unlink()
                    cleared += 1
            except Exception:
                continue

        return cleared

    def get_queue_stats(self) -> Dict:
        """Get queue statistics."""
        tasks = self.get_all_tasks()
        ready = self.get_ready_tasks()

        stats = {
            'total_tasks': len(tasks),
            'ready_for_retry': len(ready),
            'by_failure_type': {},
            'by_actor': {},
            'oldest_task': None,
            'newest_task': None
        }

        for task in tasks:
            # Count by failure type
            ft = task.failure_type
            stats['by_failure_type'][ft] = stats['by_failure_type'].get(ft, 0) + 1

            # Count by actor
            stats['by_actor'][task.actor] = stats['by_actor'].get(task.actor, 0) + 1

        if tasks:
            sorted_tasks = sorted(tasks, key=lambda t: t.created_at)
            stats['oldest_task'] = sorted_tasks[0].created_at
            stats['newest_task'] = sorted_tasks[-1].created_at

        return stats


# ==============================================================================
# RETRY HANDLER
# ==============================================================================

class RetryHandler:
    """
    Main retry handler with exponential backoff.

    Usage:
        handler = RetryHandler(actor="my_script")

        @handler.with_retry
        def my_function():
            # May fail
            pass

        # Or manually:
        result = handler.execute(my_function, arg1, arg2)
    """

    # Global circuit breakers by name
    _circuit_breakers: Dict[str, CircuitBreaker] = {}
    _lock = threading.Lock()

    def __init__(
        self,
        actor: str,
        config: RetryConfig = None,
        circuit_breaker_name: str = None
    ):
        self.actor = actor
        self.config = config or RetryConfig()
        self.queue_manager = RetryQueueManager()

        # Get or create circuit breaker
        if circuit_breaker_name:
            self.circuit_breaker = self._get_circuit_breaker(circuit_breaker_name)
        else:
            self.circuit_breaker = None

    @classmethod
    def _get_circuit_breaker(cls, name: str) -> CircuitBreaker:
        """Get or create a circuit breaker by name."""
        with cls._lock:
            if name not in cls._circuit_breakers:
                cls._circuit_breakers[name] = CircuitBreaker(name)
            return cls._circuit_breakers[name]

    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay with exponential backoff and jitter.

        delay = min(base * (exponential_base ^ attempt), max_delay)
        delay = delay * (1 + random(-jitter, +jitter))
        """
        # Exponential backoff
        delay = self.config.base_delay * (self.config.exponential_base ** attempt)

        # Cap at max delay
        delay = min(delay, self.config.max_delay)

        # Add jitter
        jitter_range = delay * self.config.jitter_factor
        jitter = random.uniform(-jitter_range, jitter_range)
        delay = max(0.1, delay + jitter)  # Minimum 100ms

        return delay

    def should_retry(self, exception: Exception, attempt: int) -> bool:
        """Determine if we should retry based on exception and attempt count."""
        # Check if max retries exceeded
        if attempt >= self.config.max_retries:
            return False

        # Check explicit no-retry exceptions
        for exc_type in self.config.no_retry_on:
            if isinstance(exception, exc_type):
                return False

        # Check explicit retry exceptions
        for exc_type in self.config.retry_on:
            if isinstance(exception, exc_type):
                return True

        # Check if failure type is recoverable
        failure_type = FailureClassifier.classify(exception)
        return FailureClassifier.is_recoverable(failure_type)

    def execute(
        self,
        func: Callable,
        *args,
        task_id: str = None,
        task_type: str = "general",
        **kwargs
    ) -> Any:
        """
        Execute a function with retry handling.

        Args:
            func: Function to execute
            *args: Positional arguments
            task_id: Optional task identifier
            task_type: Type of task
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            Exception: If all retries exhausted
        """
        task_id = task_id or f"task_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        state = RetryState(
            max_attempts=self.config.max_retries,
            started_at=datetime.now().isoformat()
        )

        # Check circuit breaker
        if self.circuit_breaker and not self.circuit_breaker.can_execute():
            # Log circuit open
            audit_logger.log(
                action_type=ActionType.WARNING_RAISED,
                actor=self.actor,
                target=task_id,
                parameters={
                    'reason': 'circuit_breaker_open',
                    'circuit': self.circuit_breaker.name
                },
                result=ResultStatus.FAILURE
            )
            raise RuntimeError(f"Circuit breaker '{self.circuit_breaker.name}' is open")

        last_exception = None

        while state.attempt < state.max_attempts:
            state.attempt += 1
            state.last_attempt_at = datetime.now().isoformat()

            try:
                # Log retry attempt
                if state.attempt > 1:
                    audit_logger.log(
                        action_type=ActionType.RECOVERY_ATTEMPTED,
                        actor=self.actor,
                        target=task_id,
                        parameters={
                            'attempt': state.attempt,
                            'max_attempts': state.max_attempts,
                            'last_error': state.last_error
                        },
                        result=ResultStatus.PENDING
                    )

                # Execute function
                result = func(*args, **kwargs)

                # Success!
                state.successful = True
                if self.circuit_breaker:
                    self.circuit_breaker.record_success()

                # Log success after retry
                if state.attempt > 1:
                    audit_logger.log(
                        action_type=ActionType.RECOVERY_SUCCESS,
                        actor=self.actor,
                        target=task_id,
                        parameters={
                            'attempt': state.attempt,
                            'total_delay': state.total_delay
                        },
                        result=ResultStatus.SUCCESS
                    )

                return result

            except Exception as e:
                last_exception = e
                state.last_error = str(e)
                state.last_error_type = type(e).__name__
                state.failure_type = FailureClassifier.classify(e)

                # Record failure
                if self.circuit_breaker:
                    self.circuit_breaker.record_failure(e)

                # Log failure
                audit_logger.log(
                    action_type=ActionType.ERROR_OCCURRED,
                    actor=self.actor,
                    target=task_id,
                    parameters={
                        'attempt': state.attempt,
                        'error_type': state.last_error_type,
                        'failure_type': state.failure_type.value
                    },
                    result=ResultStatus.FAILURE,
                    error=state.last_error
                )

                # Check if we should retry
                if not self.should_retry(e, state.attempt):
                    break

                # Check if more attempts available
                if state.attempt >= state.max_attempts:
                    break

                # Calculate delay
                delay = self.calculate_delay(state.attempt)
                state.total_delay += delay
                state.next_retry_at = (
                    datetime.now() + timedelta(seconds=delay)
                ).isoformat()

                # Wait before retry
                time.sleep(delay)

        # All retries exhausted
        recovery_mode = FailureClassifier.get_recovery_mode(
            state.failure_type,
            state.attempt,
            state.max_attempts
        )

        # Handle based on recovery mode
        if recovery_mode == RecoveryMode.DEFERRED_RETRY:
            # Queue for later retry
            next_retry = datetime.now() + timedelta(minutes=15)
            metadata = TaskRetryMetadata(
                task_id=task_id,
                original_path=str(kwargs.get('filepath', '')),
                task_type=task_type,
                attempt_count=state.attempt,
                max_attempts=state.max_attempts + 3,  # Extended retries
                last_error=state.last_error,
                last_error_type=state.last_error_type,
                failure_type=state.failure_type.value,
                created_at=state.started_at,
                last_attempt_at=state.last_attempt_at,
                next_retry_at=next_retry.isoformat(),
                actor=self.actor,
                parameters=dict(kwargs)
            )
            self.queue_manager.enqueue(metadata)

        # Raise the last exception
        raise last_exception

    def with_retry(
        self,
        func: Callable = None,
        *,
        task_type: str = "general"
    ) -> Callable:
        """
        Decorator for adding retry handling to a function.

        Usage:
            @handler.with_retry
            def my_function():
                pass

            @handler.with_retry(task_type="email")
            def send_email():
                pass
        """
        def decorator(fn: Callable) -> Callable:
            @wraps(fn)
            def wrapper(*args, **kwargs):
                task_id = kwargs.pop('_task_id', None) or f"{fn.__name__}_{datetime.now().strftime('%H%M%S')}"
                return self.execute(fn, *args, task_id=task_id, task_type=task_type, **kwargs)
            return wrapper

        if func is not None:
            return decorator(func)
        return decorator

    @contextmanager
    def retry_context(self, task_id: str, task_type: str = "general"):
        """
        Context manager for retry handling.

        Usage:
            with handler.retry_context("task_123", "email") as ctx:
                # Do work
                ctx.mark_success()
        """
        state = RetryState(
            max_attempts=self.config.max_retries,
            started_at=datetime.now().isoformat()
        )

        class RetryContext:
            def __init__(ctx_self):
                ctx_self.state = state
                ctx_self.success = False

            def mark_success(ctx_self):
                ctx_self.success = True
                state.successful = True

            def get_attempt(ctx_self) -> int:
                return state.attempt

        ctx = RetryContext()

        try:
            state.attempt = 1
            state.last_attempt_at = datetime.now().isoformat()
            yield ctx

            if not ctx.success:
                raise RuntimeError("Context completed without marking success")

        except Exception as e:
            state.last_error = str(e)
            state.last_error_type = type(e).__name__
            state.failure_type = FailureClassifier.classify(e)

            audit_logger.log_error(
                actor=self.actor,
                target=task_id,
                error_message=str(e),
                error_type=type(e).__name__
            )
            raise


# ==============================================================================
# CONVENIENCE FUNCTIONS
# ==============================================================================

def get_retry_handler(actor: str, circuit_breaker: str = None) -> RetryHandler:
    """Get a retry handler instance."""
    return RetryHandler(actor=actor, circuit_breaker_name=circuit_breaker)


def retry_operation(
    func: Callable,
    actor: str,
    task_id: str = None,
    max_retries: int = 5,
    **kwargs
) -> Any:
    """
    Convenience function to retry an operation.

    Args:
        func: Function to execute
        actor: Actor name for logging
        task_id: Optional task identifier
        max_retries: Maximum retry attempts
        **kwargs: Passed to function

    Returns:
        Function result
    """
    config = RetryConfig(max_retries=max_retries)
    handler = RetryHandler(actor=actor, config=config)
    return handler.execute(func, task_id=task_id, **kwargs)


def get_queue_manager() -> RetryQueueManager:
    """Get the retry queue manager."""
    return RetryQueueManager()


def get_circuit_breaker(name: str) -> CircuitBreaker:
    """Get or create a circuit breaker."""
    return RetryHandler._get_circuit_breaker(name)


def process_retry_queue(actor: str) -> Dict:
    """
    Process all ready tasks in the retry queue.

    Returns:
        Summary of processing results
    """
    manager = RetryQueueManager()
    ready_tasks = manager.get_ready_tasks()

    results = {
        'processed': 0,
        'succeeded': 0,
        'failed': 0,
        'requeued': 0
    }

    for task in ready_tasks:
        results['processed'] += 1

        # Log processing attempt
        audit_logger.log(
            action_type=ActionType.TASK_STARTED,
            actor=actor,
            target=task.task_id,
            parameters={
                'from': 'retry_queue',
                'attempt': task.attempt_count + 1
            },
            result=ResultStatus.PENDING
        )

        # Here you would dispatch to the appropriate handler
        # This is a placeholder - actual implementation depends on task type
        # For now, just remove from queue after max attempts
        if task.attempt_count >= task.max_attempts:
            manager.remove_task(task.task_id)
            results['failed'] += 1

            audit_logger.log(
                action_type=ActionType.TASK_FAILED,
                actor=actor,
                target=task.task_id,
                parameters={
                    'reason': 'max_retries_exceeded',
                    'total_attempts': task.attempt_count
                },
                result=ResultStatus.FAILURE
            )
        else:
            results['requeued'] += 1

    return results


# ==============================================================================
# CLI INTERFACE
# ==============================================================================

def main():
    """CLI for testing retry handler."""
    print("=" * 60)
    print("Error Recovery & Retry System - Gold Tier")
    print("=" * 60)

    # Test retry with simulated failures
    handler = RetryHandler(actor="test_runner", circuit_breaker_name="test_circuit")

    failure_count = [0]

    def flaky_function():
        """Function that fails a few times then succeeds."""
        failure_count[0] += 1
        if failure_count[0] < 3:
            raise ConnectionError(f"Simulated failure #{failure_count[0]}")
        return "Success!"

    print("\nTest 1: Retry with eventual success")
    print("-" * 40)
    try:
        result = handler.execute(flaky_function, task_id="test_task_1")
        print(f"Result: {result}")
        print(f"Attempts: {failure_count[0]}")
    except Exception as e:
        print(f"Failed: {e}")

    # Test queue manager
    print("\nTest 2: Queue Manager")
    print("-" * 40)
    manager = RetryQueueManager()
    stats = manager.get_queue_stats()
    print(f"Queue stats: {json.dumps(stats, indent=2)}")

    # Test circuit breaker
    print("\nTest 3: Circuit Breaker")
    print("-" * 40)
    cb = get_circuit_breaker("test_circuit")
    print(f"Circuit state: {cb.get_state()}")

    print("\n" + "=" * 60)
    print("Tests completed!")
    print("=" * 60)

    # Flush audit logs
    audit_logger.flush()


if __name__ == "__main__":
    main()
