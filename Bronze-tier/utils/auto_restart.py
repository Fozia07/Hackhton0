"""
Auto Restart Engine
===================

Enterprise-grade auto-restart manager with backoff strategy and circuit breaker protection.

Features:
- Graceful shutdown with timeout
- Forced kill fallback
- Exponential backoff with jitter
- Circuit breaker protection
- Restart verification
- Cross-platform support (Windows + Linux + WSL)

Author: AI Employee System
Version: 1.0.0
"""

import os
import sys
import time
import signal
import subprocess
import threading
import random
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, List, Callable, Any, Tuple
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from utils.incident_logger import (
    IncidentLogger, IncidentType, IncidentSeverity, IncidentResult,
    log_incident
)


class RestartResult(Enum):
    """Result of a restart attempt."""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    CIRCUIT_OPEN = "circuit_open"
    COOLDOWN = "cooldown"
    PROCESS_NOT_FOUND = "process_not_found"
    SHUTDOWN_FAILED = "shutdown_failed"
    VERIFICATION_FAILED = "verification_failed"


class ShutdownMethod(Enum):
    """Method used to stop a process."""
    GRACEFUL = "graceful"
    TERMINATE = "terminate"
    KILL = "kill"
    NONE = "none"


@dataclass
class RestartAttempt:
    """Record of a restart attempt."""
    process_name: str
    pid: Optional[int]
    timestamp: datetime
    attempt_number: int
    shutdown_method: ShutdownMethod
    restart_result: RestartResult
    new_pid: Optional[int] = None
    duration_ms: float = 0.0
    error: Optional[str] = None
    backoff_seconds: float = 0.0


@dataclass
class CircuitState:
    """Circuit breaker state for a process."""
    process_name: str
    is_open: bool = False
    failure_count: int = 0
    last_failure: Optional[datetime] = None
    last_success: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    half_open: bool = False

    # Configuration
    failure_threshold: int = 5
    reset_timeout_seconds: int = 300  # 5 minutes
    half_open_success_threshold: int = 2
    half_open_success_count: int = 0


@dataclass
class ProcessConfig:
    """Configuration for a managed process."""
    name: str
    command: List[str]
    working_dir: Optional[str] = None
    env: Optional[Dict[str, str]] = None
    graceful_timeout: float = 10.0
    terminate_timeout: float = 5.0
    startup_timeout: float = 30.0
    priority: int = 1  # 1=highest, 10=lowest
    critical: bool = False  # If true, triggers safe mode on repeated failures
    max_restarts: int = 5
    restart_window_seconds: int = 600  # 10 minutes
    health_check: Optional[Callable[[], bool]] = None


class BackoffStrategy:
    """Exponential backoff with jitter."""

    # Backoff delays in seconds
    BASE_DELAYS = [5, 15, 30, 60, 120, 300]
    MAX_DELAY = 600  # 10 minutes max
    JITTER_FACTOR = 0.25  # +/- 25% jitter

    @classmethod
    def get_delay(cls, attempt: int) -> float:
        """Get delay for given attempt number (1-indexed)."""
        if attempt <= 0:
            return 0

        idx = min(attempt - 1, len(cls.BASE_DELAYS) - 1)
        base_delay = cls.BASE_DELAYS[idx]

        # Add jitter
        jitter = base_delay * cls.JITTER_FACTOR
        delay = base_delay + random.uniform(-jitter, jitter)

        return min(max(0, delay), cls.MAX_DELAY)

    @classmethod
    def reset_delay(cls) -> float:
        """Get initial delay after reset."""
        return cls.BASE_DELAYS[0]


class AutoRestartEngine:
    """
    Enterprise-grade auto-restart manager.

    Features:
    - Graceful shutdown with timeout
    - Forced kill fallback
    - Exponential backoff with jitter
    - Circuit breaker protection
    - Restart verification
    - Cross-platform support
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._lock = threading.RLock()
        self._incident_logger = IncidentLogger()

        # Process configurations
        self._process_configs: Dict[str, ProcessConfig] = {}

        # Circuit breaker states
        self._circuit_states: Dict[str, CircuitState] = {}

        # Restart history
        self._restart_history: Dict[str, List[RestartAttempt]] = {}

        # Running processes (managed by this engine)
        self._managed_processes: Dict[str, subprocess.Popen] = {}

        # Callbacks
        self._on_restart_callbacks: List[Callable[[str, RestartResult], None]] = []
        self._on_circuit_open_callbacks: List[Callable[[str], None]] = []

        # State
        self._dry_run = False
        self._safe_mode = False

        self._initialized = True

    def configure_process(self, config: ProcessConfig) -> None:
        """Register a process configuration."""
        with self._lock:
            self._process_configs[config.name] = config

            if config.name not in self._circuit_states:
                self._circuit_states[config.name] = CircuitState(
                    process_name=config.name,
                    failure_threshold=config.max_restarts,
                    reset_timeout_seconds=config.restart_window_seconds
                )

            if config.name not in self._restart_history:
                self._restart_history[config.name] = []

    def set_dry_run(self, enabled: bool) -> None:
        """Enable/disable dry run mode (no actual restarts)."""
        self._dry_run = enabled

    def set_safe_mode(self, enabled: bool) -> None:
        """Enable/disable safe mode."""
        self._safe_mode = enabled

    def add_restart_callback(self, callback: Callable[[str, RestartResult], None]) -> None:
        """Add callback for restart events."""
        self._on_restart_callbacks.append(callback)

    def add_circuit_open_callback(self, callback: Callable[[str], None]) -> None:
        """Add callback for circuit breaker open events."""
        self._on_circuit_open_callbacks.append(callback)

    def get_circuit_state(self, process_name: str) -> Optional[CircuitState]:
        """Get circuit breaker state for a process."""
        return self._circuit_states.get(process_name)

    def is_circuit_open(self, process_name: str) -> bool:
        """Check if circuit breaker is open for process."""
        state = self._circuit_states.get(process_name)
        if not state:
            return False

        # Check if should reset (timeout elapsed)
        if state.is_open and state.opened_at:
            elapsed = (datetime.now() - state.opened_at).total_seconds()
            if elapsed >= state.reset_timeout_seconds:
                state.half_open = True
                return False

        return state.is_open

    def reset_circuit(self, process_name: str) -> None:
        """Manually reset circuit breaker for process."""
        with self._lock:
            if process_name in self._circuit_states:
                state = self._circuit_states[process_name]
                state.is_open = False
                state.half_open = False
                state.failure_count = 0
                state.half_open_success_count = 0

                log_incident(
                    event=IncidentType.CIRCUIT_BREAKER_CLOSE,
                    process_name=process_name,
                    reason="manual_reset",
                    action="reset",
                    result=IncidentResult.SUCCESS
                )

    def _record_failure(self, process_name: str) -> None:
        """Record a failure and potentially open circuit."""
        with self._lock:
            if process_name not in self._circuit_states:
                self._circuit_states[process_name] = CircuitState(process_name=process_name)

            state = self._circuit_states[process_name]
            state.failure_count += 1
            state.last_failure = datetime.now()

            # Reset half-open state on failure
            if state.half_open:
                state.half_open = False
                state.half_open_success_count = 0

            # Check if should open circuit
            if state.failure_count >= state.failure_threshold:
                state.is_open = True
                state.opened_at = datetime.now()

                log_incident(
                    event=IncidentType.CIRCUIT_BREAKER_OPEN,
                    process_name=process_name,
                    reason=f"failure_threshold_reached ({state.failure_count}/{state.failure_threshold})",
                    action="open_circuit",
                    result=IncidentResult.SUCCESS,
                    severity=IncidentSeverity.HIGH
                )

                # Notify callbacks
                for callback in self._on_circuit_open_callbacks:
                    try:
                        callback(process_name)
                    except Exception:
                        pass

    def _record_success(self, process_name: str) -> None:
        """Record a success and potentially close circuit."""
        with self._lock:
            if process_name not in self._circuit_states:
                return

            state = self._circuit_states[process_name]
            state.last_success = datetime.now()

            if state.half_open:
                state.half_open_success_count += 1

                if state.half_open_success_count >= state.half_open_success_threshold:
                    # Close circuit
                    state.is_open = False
                    state.half_open = False
                    state.failure_count = 0
                    state.half_open_success_count = 0

                    log_incident(
                        event=IncidentType.CIRCUIT_BREAKER_CLOSE,
                        process_name=process_name,
                        reason="recovery_verified",
                        action="close_circuit",
                        result=IncidentResult.SUCCESS
                    )

    def _get_restart_count_in_window(self, process_name: str, window_seconds: int) -> int:
        """Get number of restarts in time window."""
        cutoff = datetime.now() - timedelta(seconds=window_seconds)
        history = self._restart_history.get(process_name, [])
        return sum(1 for r in history if r.timestamp > cutoff)

    def stop_process(
        self,
        pid: int,
        graceful_timeout: float = 10.0,
        terminate_timeout: float = 5.0
    ) -> Tuple[ShutdownMethod, bool]:
        """
        Stop a process gracefully with fallback to force kill.

        Returns: (method_used, success)
        """
        if not PSUTIL_AVAILABLE:
            return self._stop_process_basic(pid, graceful_timeout)

        try:
            process = psutil.Process(pid)
        except psutil.NoSuchProcess:
            return (ShutdownMethod.NONE, True)  # Already stopped
        except Exception:
            return (ShutdownMethod.NONE, False)

        # Try graceful shutdown (SIGTERM on Unix, terminate() on Windows)
        try:
            process.terminate()
            try:
                process.wait(timeout=graceful_timeout)
                return (ShutdownMethod.GRACEFUL, True)
            except psutil.TimeoutExpired:
                pass
        except Exception:
            pass

        # Try SIGTERM explicitly on Unix
        if hasattr(signal, 'SIGTERM') and sys.platform != 'win32':
            try:
                os.kill(pid, signal.SIGTERM)
                time.sleep(terminate_timeout)

                if not process.is_running():
                    return (ShutdownMethod.TERMINATE, True)
            except Exception:
                pass

        # Force kill
        try:
            process.kill()
            process.wait(timeout=5.0)
            return (ShutdownMethod.KILL, True)
        except Exception as e:
            return (ShutdownMethod.KILL, False)

    def _stop_process_basic(
        self,
        pid: int,
        timeout: float = 10.0
    ) -> Tuple[ShutdownMethod, bool]:
        """Basic process stop without psutil."""
        try:
            if sys.platform == 'win32':
                subprocess.run(
                    ['taskkill', '/PID', str(pid), '/F'],
                    capture_output=True,
                    timeout=timeout
                )
            else:
                os.kill(pid, signal.SIGTERM)
                time.sleep(min(timeout, 5.0))

                # Check if still running
                try:
                    os.kill(pid, 0)
                    # Still running, force kill
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass  # Process is gone

            return (ShutdownMethod.KILL, True)
        except Exception:
            return (ShutdownMethod.NONE, False)

    def start_process(self, config: ProcessConfig) -> Tuple[Optional[subprocess.Popen], Optional[int]]:
        """
        Start a process with the given configuration.

        Returns: (Popen object, PID) or (None, None) on failure
        """
        if self._dry_run:
            return (None, 99999)  # Fake PID for dry run

        try:
            env = os.environ.copy()
            if config.env:
                env.update(config.env)

            # Build startup info for Windows
            startup_info = None
            creation_flags = 0

            if sys.platform == 'win32':
                startup_info = subprocess.STARTUPINFO()
                startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

            process = subprocess.Popen(
                config.command,
                cwd=config.working_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=startup_info,
                creationflags=creation_flags if sys.platform == 'win32' else 0
            )

            # Brief wait to ensure process started
            time.sleep(0.5)

            if process.poll() is not None:
                # Process already exited
                return (None, None)

            return (process, process.pid)

        except Exception as e:
            return (None, None)

    def verify_process_running(
        self,
        pid: int,
        timeout: float = 10.0,
        health_check: Optional[Callable[[], bool]] = None
    ) -> bool:
        """Verify a process is running and healthy."""
        if self._dry_run:
            return True

        start = time.time()

        while time.time() - start < timeout:
            # Check if process exists
            if PSUTIL_AVAILABLE:
                try:
                    process = psutil.Process(pid)
                    if not process.is_running():
                        return False
                except psutil.NoSuchProcess:
                    return False
            else:
                try:
                    os.kill(pid, 0)
                except OSError:
                    return False

            # Run custom health check if provided
            if health_check:
                try:
                    if health_check():
                        return True
                except Exception:
                    pass
            else:
                # No health check, just verify process exists
                return True

            time.sleep(1.0)

        return False

    def restart_process(
        self,
        process_name: str,
        current_pid: Optional[int] = None,
        reason: str = "unknown",
        force: bool = False
    ) -> RestartAttempt:
        """
        Restart a process with full recovery logic.

        Args:
            process_name: Name of the process to restart
            current_pid: Current PID if known
            reason: Reason for restart
            force: Force restart even if circuit is open

        Returns: RestartAttempt with result
        """
        start_time = time.time()

        # Get configuration
        config = self._process_configs.get(process_name)
        if not config:
            # Create default config for unknown process
            config = ProcessConfig(
                name=process_name,
                command=[sys.executable, f"scripts/{process_name}.py"]
            )

        # Get attempt number
        restart_count = self._get_restart_count_in_window(
            process_name,
            config.restart_window_seconds
        )
        attempt_number = restart_count + 1

        # Calculate backoff
        backoff_seconds = BackoffStrategy.get_delay(attempt_number)

        # Check circuit breaker
        if not force and self.is_circuit_open(process_name):
            attempt = RestartAttempt(
                process_name=process_name,
                pid=current_pid,
                timestamp=datetime.now(),
                attempt_number=attempt_number,
                shutdown_method=ShutdownMethod.NONE,
                restart_result=RestartResult.CIRCUIT_OPEN,
                backoff_seconds=backoff_seconds,
                error="Circuit breaker is open"
            )
            self._record_attempt(attempt)
            return attempt

        # Check safe mode
        if self._safe_mode and not config.critical:
            attempt = RestartAttempt(
                process_name=process_name,
                pid=current_pid,
                timestamp=datetime.now(),
                attempt_number=attempt_number,
                shutdown_method=ShutdownMethod.NONE,
                restart_result=RestartResult.SKIPPED,
                backoff_seconds=0,
                error="Safe mode active, skipping non-critical process"
            )
            self._record_attempt(attempt)
            return attempt

        # Apply backoff delay
        if backoff_seconds > 0 and attempt_number > 1:
            log_incident(
                event=IncidentType.PROCESS_RESTART,
                process_name=process_name,
                reason=f"backoff_wait_{backoff_seconds:.1f}s",
                action="waiting",
                result=IncidentResult.PENDING
            )

            if not self._dry_run:
                time.sleep(backoff_seconds)

        # Stop current process if running
        shutdown_method = ShutdownMethod.NONE
        if current_pid:
            shutdown_method, stopped = self.stop_process(
                current_pid,
                config.graceful_timeout,
                config.terminate_timeout
            )

            if not stopped:
                attempt = RestartAttempt(
                    process_name=process_name,
                    pid=current_pid,
                    timestamp=datetime.now(),
                    attempt_number=attempt_number,
                    shutdown_method=shutdown_method,
                    restart_result=RestartResult.SHUTDOWN_FAILED,
                    backoff_seconds=backoff_seconds,
                    error="Failed to stop existing process",
                    duration_ms=(time.time() - start_time) * 1000
                )
                self._record_attempt(attempt)
                self._record_failure(process_name)
                return attempt

        # Start new process
        process, new_pid = self.start_process(config)

        if not new_pid:
            attempt = RestartAttempt(
                process_name=process_name,
                pid=current_pid,
                timestamp=datetime.now(),
                attempt_number=attempt_number,
                shutdown_method=shutdown_method,
                restart_result=RestartResult.FAILED,
                backoff_seconds=backoff_seconds,
                error="Failed to start process",
                duration_ms=(time.time() - start_time) * 1000
            )
            self._record_attempt(attempt)
            self._record_failure(process_name)

            log_incident(
                event=IncidentType.RECOVERY_FAILED,
                process_name=process_name,
                reason=reason,
                action="restart",
                result=IncidentResult.FAILED,
                severity=IncidentSeverity.HIGH
            )

            return attempt

        # Verify process is running
        if not self.verify_process_running(
            new_pid,
            config.startup_timeout,
            config.health_check
        ):
            attempt = RestartAttempt(
                process_name=process_name,
                pid=current_pid,
                timestamp=datetime.now(),
                attempt_number=attempt_number,
                shutdown_method=shutdown_method,
                restart_result=RestartResult.VERIFICATION_FAILED,
                new_pid=new_pid,
                backoff_seconds=backoff_seconds,
                error="Process verification failed",
                duration_ms=(time.time() - start_time) * 1000
            )
            self._record_attempt(attempt)
            self._record_failure(process_name)

            log_incident(
                event=IncidentType.RECOVERY_FAILED,
                process_name=process_name,
                reason="verification_failed",
                action="restart",
                result=IncidentResult.FAILED,
                severity=IncidentSeverity.HIGH
            )

            return attempt

        # Success
        duration_ms = (time.time() - start_time) * 1000

        attempt = RestartAttempt(
            process_name=process_name,
            pid=current_pid,
            timestamp=datetime.now(),
            attempt_number=attempt_number,
            shutdown_method=shutdown_method,
            restart_result=RestartResult.SUCCESS,
            new_pid=new_pid,
            backoff_seconds=backoff_seconds,
            duration_ms=duration_ms
        )

        self._record_attempt(attempt)
        self._record_success(process_name)

        # Store managed process
        if process:
            with self._lock:
                self._managed_processes[process_name] = process

        log_incident(
            event=IncidentType.RECOVERY_SUCCESS,
            process_name=process_name,
            reason=reason,
            action="restart",
            result=IncidentResult.SUCCESS,
            details={
                "old_pid": current_pid,
                "new_pid": new_pid,
                "attempt": attempt_number,
                "duration_ms": duration_ms,
                "shutdown_method": shutdown_method.value
            }
        )

        # Notify callbacks
        for callback in self._on_restart_callbacks:
            try:
                callback(process_name, RestartResult.SUCCESS)
            except Exception:
                pass

        return attempt

    def _record_attempt(self, attempt: RestartAttempt) -> None:
        """Record a restart attempt in history."""
        with self._lock:
            if attempt.process_name not in self._restart_history:
                self._restart_history[attempt.process_name] = []

            history = self._restart_history[attempt.process_name]
            history.append(attempt)

            # Keep last 100 attempts
            if len(history) > 100:
                self._restart_history[attempt.process_name] = history[-100:]

    def kill_process(self, pid: int) -> bool:
        """Force kill a process immediately."""
        if self._dry_run:
            return True

        if PSUTIL_AVAILABLE:
            try:
                process = psutil.Process(pid)
                process.kill()
                process.wait(timeout=5.0)
                return True
            except Exception:
                pass

        # Fallback
        try:
            if sys.platform == 'win32':
                subprocess.run(
                    ['taskkill', '/PID', str(pid), '/F'],
                    capture_output=True,
                    timeout=5.0
                )
            else:
                os.kill(pid, signal.SIGKILL)
            return True
        except Exception:
            return False

    def get_restart_history(
        self,
        process_name: Optional[str] = None,
        limit: int = 50
    ) -> List[RestartAttempt]:
        """Get restart history."""
        with self._lock:
            if process_name:
                history = self._restart_history.get(process_name, [])
            else:
                # Combine all histories
                history = []
                for h in self._restart_history.values():
                    history.extend(h)
                history.sort(key=lambda x: x.timestamp, reverse=True)

            return history[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """Get restart statistics."""
        with self._lock:
            total_restarts = sum(len(h) for h in self._restart_history.values())
            successful = sum(
                sum(1 for a in h if a.restart_result == RestartResult.SUCCESS)
                for h in self._restart_history.values()
            )
            failed = total_restarts - successful

            open_circuits = [
                name for name, state in self._circuit_states.items()
                if state.is_open
            ]

            return {
                "total_restarts": total_restarts,
                "successful": successful,
                "failed": failed,
                "success_rate": (successful / total_restarts * 100) if total_restarts > 0 else 100.0,
                "open_circuits": open_circuits,
                "managed_processes": list(self._managed_processes.keys()),
                "safe_mode": self._safe_mode,
                "dry_run": self._dry_run
            }

    def cleanup(self) -> None:
        """Cleanup managed processes."""
        with self._lock:
            for name, process in list(self._managed_processes.items()):
                try:
                    if process.poll() is None:
                        process.terminate()
                        process.wait(timeout=5.0)
                except Exception:
                    pass

            self._managed_processes.clear()


# Singleton accessor
def get_restart_engine() -> AutoRestartEngine:
    """Get the singleton AutoRestartEngine instance."""
    return AutoRestartEngine()


# Convenience functions
def restart_process(
    process_name: str,
    current_pid: Optional[int] = None,
    reason: str = "unknown"
) -> RestartAttempt:
    """Restart a process."""
    return get_restart_engine().restart_process(process_name, current_pid, reason)


def stop_process(pid: int) -> Tuple[ShutdownMethod, bool]:
    """Stop a process gracefully."""
    return get_restart_engine().stop_process(pid)


def kill_process(pid: int) -> bool:
    """Force kill a process."""
    return get_restart_engine().kill_process(pid)


def is_circuit_open(process_name: str) -> bool:
    """Check if circuit breaker is open."""
    return get_restart_engine().is_circuit_open(process_name)


def reset_circuit(process_name: str) -> None:
    """Reset circuit breaker."""
    get_restart_engine().reset_circuit(process_name)


# Test / Demo
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Auto Restart Engine Demo")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")
    args = parser.parse_args()

    engine = get_restart_engine()

    if args.dry_run:
        engine.set_dry_run(True)
        print("Running in dry-run mode")

    # Configure test process
    test_config = ProcessConfig(
        name="test_process",
        command=[sys.executable, "-c", "import time; time.sleep(3600)"],
        graceful_timeout=5.0,
        critical=False
    )
    engine.configure_process(test_config)

    print("\n=== Auto Restart Engine Demo ===\n")

    # Simulate restart attempts
    for i in range(3):
        print(f"\nAttempt {i + 1}:")
        attempt = engine.restart_process("test_process", reason="demo_test")
        print(f"  Result: {attempt.restart_result.value}")
        print(f"  New PID: {attempt.new_pid}")
        print(f"  Duration: {attempt.duration_ms:.1f}ms")
        print(f"  Backoff: {attempt.backoff_seconds:.1f}s")

        if attempt.new_pid and not args.dry_run:
            # Kill for next iteration
            engine.kill_process(attempt.new_pid)
            time.sleep(1)

    # Show stats
    print("\n=== Statistics ===")
    stats = engine.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # Cleanup
    engine.cleanup()
    print("\n=== Demo Complete ===")
