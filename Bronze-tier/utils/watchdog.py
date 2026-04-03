"""
Watchdog Controller
===================

Enterprise-grade main watchdog orchestrator that coordinates all monitoring
and recovery components for the AI Employee platform.

Features:
- Coordinates heartbeat, process monitor, resource guard, incident logger
- Safe mode state machine with automatic activation/recovery
- Continuous monitoring event loop
- Recovery action execution
- Health status aggregation
- Cross-platform support (Windows + Linux + WSL)

Author: AI Employee System
Version: 1.0.0
"""

import os
import sys
import json
import time
import signal
import threading
import atexit
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Dict, List, Callable, Any, Set
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from utils.heartbeat import (
    HeartbeatManager, HeartbeatWriter, Heartbeat,
    AgentHealth, HealthLevel
)
from utils.process_monitor import (
    ProcessMonitor, ProcessState, ProcessHealth, ProcessCheckResult
)
from utils.resource_guard import (
    ResourceGuard, ResourceStatus, ResourceLevel, ThrottleAction
)
from utils.incident_logger import (
    IncidentLogger, IncidentType, IncidentSeverity, IncidentResult,
    log_incident
)
from utils.auto_restart import (
    AutoRestartEngine, RestartResult, ProcessConfig, BackoffStrategy
)


class WatchdogState(Enum):
    """Watchdog operational state."""
    STARTING = "starting"
    RUNNING = "running"
    SAFE_MODE = "safe_mode"
    RECOVERY = "recovery"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class SafeModeReason(Enum):
    """Reasons for entering safe mode."""
    CRASH_THRESHOLD = "crash_threshold"
    RESTART_THRESHOLD = "restart_threshold"
    MEMORY_CRITICAL = "memory_critical"
    CPU_CRITICAL = "cpu_critical"
    MANUAL = "manual"
    CIRCUIT_BREAKER = "circuit_breaker"


@dataclass
class SafeModeConfig:
    """Safe mode configuration."""
    crash_threshold: int = 3
    crash_window_seconds: int = 600  # 10 minutes
    restart_threshold: int = 5
    restart_window_seconds: int = 1800  # 30 minutes
    memory_threshold: float = 90.0
    cpu_threshold: float = 95.0
    recovery_timeout_seconds: int = 900  # 15 minutes
    auto_recover: bool = True


@dataclass
class WatchdogConfig:
    """Watchdog configuration."""
    scan_interval: float = 10.0
    heartbeat_timeout: float = 60.0
    hung_threshold: float = 120.0
    process_check_interval: float = 30.0
    resource_check_interval: float = 15.0
    health_output_interval: float = 60.0
    safe_mode: SafeModeConfig = field(default_factory=SafeModeConfig)
    monitored_processes: List[str] = field(default_factory=lambda: [
        "run_ai_employee",
        "agent_executor",
        "filesystem_watcher",
        "plan_creator",
        "linkedin_poster",
        "ceo_briefing_generator",
        "email_server"
    ])


@dataclass
class SystemHealth:
    """Aggregated system health status."""
    timestamp: str
    state: str
    uptime_seconds: float
    processes_healthy: int
    processes_warning: int
    processes_critical: int
    processes_total: int
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    resource_level: str
    throttle_factor: float
    safe_mode_active: bool
    safe_mode_reason: Optional[str]
    open_circuits: List[str]
    recent_incidents: int
    last_scan: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProcessHealthStatus:
    """Health status for a single process."""
    name: str
    pid: Optional[int]
    state: str
    health: str
    last_heartbeat: Optional[str]
    heartbeat_age_seconds: Optional[float]
    cpu_percent: float
    memory_percent: float
    restart_count: int
    last_restart: Optional[str]
    circuit_open: bool


class WatchdogController:
    """
    Main watchdog orchestrator.

    Coordinates all monitoring components and handles recovery actions.
    """

    _instance = None
    _lock = threading.Lock()

    # Default paths
    VAULT_DIR = Path(__file__).parent.parent / "AI_Employee_Vault" / "Watchdog"
    HEALTH_FILE = VAULT_DIR / "health.json"
    SAFE_MODE_FLAG = VAULT_DIR / "SAFE_MODE_ACTIVE"

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
        self._config = WatchdogConfig()

        # Initialize components
        self._heartbeat_manager = HeartbeatManager()
        self._process_monitor = ProcessMonitor()
        self._resource_guard = ResourceGuard()
        self._incident_logger = IncidentLogger()
        self._restart_engine = AutoRestartEngine()

        # State
        self._state = WatchdogState.STOPPED
        self._safe_mode_active = False
        self._safe_mode_reason: Optional[SafeModeReason] = None
        self._safe_mode_entered_at: Optional[datetime] = None
        self._start_time: Optional[datetime] = None
        self._last_scan: Optional[datetime] = None
        self._shutdown_requested = False

        # Monitoring thread
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Process PIDs (tracked externally or discovered)
        self._known_pids: Dict[str, int] = {}

        # Callbacks
        self._on_safe_mode_callbacks: List[Callable[[bool, Optional[str]], None]] = []
        self._on_recovery_callbacks: List[Callable[[str, bool], None]] = []

        # Counters for safe mode detection
        self._crash_times: List[datetime] = []
        self._restart_times: List[datetime] = []

        # Debug/dry-run modes
        self._debug = False
        self._dry_run = False

        # Ensure vault directory exists
        self.VAULT_DIR.mkdir(parents=True, exist_ok=True)

        # Check for existing safe mode flag
        if self.SAFE_MODE_FLAG.exists():
            self._safe_mode_active = True
            self._safe_mode_reason = SafeModeReason.MANUAL
            self._state = WatchdogState.SAFE_MODE

        # Register shutdown handler
        atexit.register(self._cleanup)

        self._initialized = True

    def configure(self, config: WatchdogConfig) -> None:
        """Update watchdog configuration."""
        with self._lock:
            self._config = config

    def set_debug(self, enabled: bool) -> None:
        """Enable debug mode."""
        self._debug = enabled

    def set_dry_run(self, enabled: bool) -> None:
        """Enable dry-run mode (no actual restarts)."""
        self._dry_run = enabled
        self._restart_engine.set_dry_run(enabled)

    def register_process(self, name: str, pid: int, config: Optional[ProcessConfig] = None) -> None:
        """Register a process for monitoring."""
        with self._lock:
            self._known_pids[name] = pid
            self._process_monitor.track_process(name, pid)

            if config:
                self._restart_engine.configure_process(config)

    def unregister_process(self, name: str) -> None:
        """Unregister a process from monitoring."""
        with self._lock:
            self._known_pids.pop(name, None)

    def add_safe_mode_callback(self, callback: Callable[[bool, Optional[str]], None]) -> None:
        """Add callback for safe mode state changes."""
        self._on_safe_mode_callbacks.append(callback)

    def add_recovery_callback(self, callback: Callable[[str, bool], None]) -> None:
        """Add callback for recovery events."""
        self._on_recovery_callbacks.append(callback)

    def start(self) -> None:
        """Start the watchdog monitoring loop."""
        with self._lock:
            if self._state in (WatchdogState.RUNNING, WatchdogState.SAFE_MODE):
                return

            self._state = WatchdogState.STARTING
            self._start_time = datetime.now()
            self._stop_event.clear()
            self._shutdown_requested = False

            # Setup signal handlers
            self._setup_signal_handlers()

            # Register resource guard callback
            self._resource_guard.add_throttle_callback(self._on_resource_throttle)

            # Register restart callback
            self._restart_engine.add_circuit_open_callback(self._on_circuit_open)

            # Start monitoring thread
            self._monitor_thread = threading.Thread(
                target=self._monitoring_loop,
                name="WatchdogMonitor",
                daemon=True
            )
            self._monitor_thread.start()

            # Log startup
            log_incident(
                event=IncidentType.WATCHDOG_START,
                process_name="watchdog",
                reason="startup",
                action="start",
                result=IncidentResult.SUCCESS
            )

            if self._safe_mode_active:
                self._state = WatchdogState.SAFE_MODE
            else:
                self._state = WatchdogState.RUNNING

    def stop(self) -> None:
        """Stop the watchdog monitoring loop."""
        with self._lock:
            if self._state == WatchdogState.STOPPED:
                return

            self._state = WatchdogState.STOPPING
            self._shutdown_requested = True
            self._stop_event.set()

        # Wait for thread to finish
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=10.0)

        # Log shutdown
        log_incident(
            event=IncidentType.WATCHDOG_STOP,
            process_name="watchdog",
            reason="shutdown",
            action="stop",
            result=IncidentResult.SUCCESS
        )

        self._state = WatchdogState.STOPPED

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            self._log_debug(f"Received signal {signum}, shutting down...")
            self._shutdown_requested = True
            self._stop_event.set()

        if sys.platform != 'win32':
            signal.signal(signal.SIGTERM, signal_handler)
            signal.signal(signal.SIGINT, signal_handler)
        else:
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGBREAK, signal_handler)

    def _cleanup(self) -> None:
        """Cleanup on shutdown."""
        self._restart_engine.cleanup()

    def _log_debug(self, message: str) -> None:
        """Log debug message if debug mode enabled."""
        if self._debug:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] [DEBUG] {message}")

    def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        last_process_check = datetime.min
        last_resource_check = datetime.min
        last_health_output = datetime.min

        while not self._stop_event.is_set():
            try:
                now = datetime.now()
                self._last_scan = now

                # Always check heartbeats
                self._check_heartbeats()

                # Periodic process check
                if (now - last_process_check).total_seconds() >= self._config.process_check_interval:
                    self._check_processes()
                    last_process_check = now

                # Periodic resource check
                if (now - last_resource_check).total_seconds() >= self._config.resource_check_interval:
                    self._check_resources()
                    last_resource_check = now

                # Periodic health output
                if (now - last_health_output).total_seconds() >= self._config.health_output_interval:
                    self._output_health_status()
                    last_health_output = now

                # Check safe mode recovery
                if self._safe_mode_active:
                    self._check_safe_mode_recovery()

            except Exception as e:
                self._log_debug(f"Error in monitoring loop: {e}")
                log_incident(
                    event=IncidentType.WATCHDOG_ERROR,
                    process_name="watchdog",
                    reason=str(e),
                    action="monitoring",
                    result=IncidentResult.FAILED,
                    severity=IncidentSeverity.HIGH
                )

            # Sleep until next scan
            self._stop_event.wait(self._config.scan_interval)

    def _check_heartbeats(self) -> None:
        """Check all agent heartbeats."""
        for process_name in self._config.monitored_processes:
            try:
                health = self._heartbeat_manager.get_agent_health(process_name)

                if health is None:
                    continue  # No heartbeat registered for this process

                # Check for stale/dead heartbeat
                if health.level == HealthLevel.DEAD:
                    self._log_debug(f"Process {process_name} heartbeat DEAD (age: {health.age_seconds:.1f}s)")
                    self._handle_dead_process(process_name, health, "heartbeat_dead")

                elif health.level == HealthLevel.HUNG:
                    self._log_debug(f"Process {process_name} heartbeat HUNG (age: {health.age_seconds:.1f}s)")
                    self._handle_hung_process(process_name, health)

                elif health.level == HealthLevel.STALE:
                    self._log_debug(f"Process {process_name} heartbeat STALE (age: {health.age_seconds:.1f}s)")
                    log_incident(
                        event=IncidentType.HEARTBEAT_STALE,
                        process_name=process_name,
                        reason=f"heartbeat_age_{health.age_seconds:.1f}s",
                        action="warning",
                        result=IncidentResult.PENDING,
                        severity=IncidentSeverity.MEDIUM
                    )

            except Exception as e:
                self._log_debug(f"Error checking heartbeat for {process_name}: {e}")

    def _check_processes(self) -> None:
        """Check all monitored processes."""
        for process_name in self._config.monitored_processes:
            try:
                pid = self._known_pids.get(process_name)
                if not pid:
                    continue

                result = self._process_monitor.check_process(pid, process_name)

                if result.health == ProcessHealth.CRASHED:
                    self._handle_crashed_process(process_name, pid, result)

                elif result.health == ProcessHealth.ZOMBIE:
                    self._handle_zombie_process(process_name, pid, result)

                elif result.health == ProcessHealth.HUNG:
                    self._handle_hung_process_by_check(process_name, pid, result)

                elif result.health == ProcessHealth.RUNAWAY:
                    self._handle_runaway_process(process_name, pid, result)

            except Exception as e:
                self._log_debug(f"Error checking process {process_name}: {e}")

    def _check_resources(self) -> None:
        """Check system resources."""
        try:
            status = self._resource_guard.check_resources()

            # Check for emergency conditions
            if status.level == ResourceLevel.EMERGENCY:
                self._handle_resource_emergency(status)

            elif status.level == ResourceLevel.CRITICAL:
                self._handle_resource_critical(status)

            elif status.level == ResourceLevel.THROTTLE:
                self._log_debug(f"Resources throttled: CPU={status.cpu_percent:.1f}%, RAM={status.memory_percent:.1f}%")

        except Exception as e:
            self._log_debug(f"Error checking resources: {e}")

    def _handle_dead_process(self, process_name: str, health: AgentHealth, reason: str) -> None:
        """Handle a dead process (no heartbeat)."""
        pid = self._known_pids.get(process_name)

        # Record crash
        self._crash_times.append(datetime.now())
        self._crash_times = [t for t in self._crash_times
                            if (datetime.now() - t).total_seconds() < self._config.safe_mode.crash_window_seconds]

        # Check safe mode threshold
        if len(self._crash_times) >= self._config.safe_mode.crash_threshold:
            self.enter_safe_mode(SafeModeReason.CRASH_THRESHOLD)
            return

        # Log and attempt restart
        log_incident(
            event=IncidentType.PROCESS_CRASH,
            process_name=process_name,
            reason=reason,
            action="restart_pending",
            result=IncidentResult.PENDING,
            severity=IncidentSeverity.HIGH
        )

        if not self._safe_mode_active or self._is_critical_process(process_name):
            self._attempt_restart(process_name, pid, reason)

    def _handle_hung_process(self, process_name: str, health: AgentHealth) -> None:
        """Handle a hung process (stale heartbeat but process running)."""
        pid = self._known_pids.get(process_name)

        log_incident(
            event=IncidentType.PROCESS_HUNG,
            process_name=process_name,
            reason=f"heartbeat_hung_{health.age_seconds:.1f}s",
            action="kill_restart",
            result=IncidentResult.PENDING,
            severity=IncidentSeverity.HIGH
        )

        if not self._safe_mode_active or self._is_critical_process(process_name):
            # Kill and restart
            if pid:
                self._restart_engine.kill_process(pid)
            self._attempt_restart(process_name, pid, "hung_process")

    def _handle_crashed_process(self, process_name: str, pid: int, result: ProcessCheckResult) -> None:
        """Handle a crashed process."""
        self._crash_times.append(datetime.now())
        self._crash_times = [t for t in self._crash_times
                            if (datetime.now() - t).total_seconds() < self._config.safe_mode.crash_window_seconds]

        if len(self._crash_times) >= self._config.safe_mode.crash_threshold:
            self.enter_safe_mode(SafeModeReason.CRASH_THRESHOLD)
            return

        log_incident(
            event=IncidentType.PROCESS_CRASH,
            process_name=process_name,
            reason="process_not_found",
            action="restart_pending",
            result=IncidentResult.PENDING,
            severity=IncidentSeverity.HIGH
        )

        if not self._safe_mode_active or self._is_critical_process(process_name):
            self._attempt_restart(process_name, pid, "crashed")

    def _handle_zombie_process(self, process_name: str, pid: int, result: ProcessCheckResult) -> None:
        """Handle a zombie process."""
        log_incident(
            event=IncidentType.PROCESS_ZOMBIE,
            process_name=process_name,
            reason="zombie_state",
            action="kill_restart",
            result=IncidentResult.PENDING,
            severity=IncidentSeverity.HIGH
        )

        if not self._safe_mode_active or self._is_critical_process(process_name):
            self._restart_engine.kill_process(pid)
            self._attempt_restart(process_name, pid, "zombie")

    def _handle_hung_process_by_check(self, process_name: str, pid: int, result: ProcessCheckResult) -> None:
        """Handle a hung process detected by process check."""
        log_incident(
            event=IncidentType.PROCESS_HUNG,
            process_name=process_name,
            reason="low_cpu_activity",
            action="kill_restart",
            result=IncidentResult.PENDING,
            severity=IncidentSeverity.MEDIUM
        )

        if not self._safe_mode_active or self._is_critical_process(process_name):
            self._restart_engine.kill_process(pid)
            self._attempt_restart(process_name, pid, "hung_low_cpu")

    def _handle_runaway_process(self, process_name: str, pid: int, result: ProcessCheckResult) -> None:
        """Handle a runaway process (excessive CPU)."""
        log_incident(
            event=IncidentType.RESOURCE_WARNING,
            process_name=process_name,
            reason=f"runaway_cpu_{result.cpu_percent:.1f}%",
            action="kill_restart",
            result=IncidentResult.PENDING,
            severity=IncidentSeverity.HIGH
        )

        # Kill runaway process
        self._restart_engine.kill_process(pid)
        self._attempt_restart(process_name, pid, "runaway_cpu")

    def _handle_resource_emergency(self, status: ResourceStatus) -> None:
        """Handle resource emergency."""
        reason = None
        if status.memory_percent >= self._config.safe_mode.memory_threshold:
            reason = SafeModeReason.MEMORY_CRITICAL
        elif status.cpu_percent >= self._config.safe_mode.cpu_threshold:
            reason = SafeModeReason.CPU_CRITICAL

        if reason:
            self.enter_safe_mode(reason)

        log_incident(
            event=IncidentType.RESOURCE_EMERGENCY,
            process_name="system",
            reason=f"cpu={status.cpu_percent:.1f}% mem={status.memory_percent:.1f}%",
            action="emergency_mode",
            result=IncidentResult.SUCCESS,
            severity=IncidentSeverity.CRITICAL
        )

    def _handle_resource_critical(self, status: ResourceStatus) -> None:
        """Handle critical resource usage."""
        log_incident(
            event=IncidentType.RESOURCE_CRITICAL,
            process_name="system",
            reason=f"cpu={status.cpu_percent:.1f}% mem={status.memory_percent:.1f}%",
            action="throttle",
            result=IncidentResult.SUCCESS,
            severity=IncidentSeverity.HIGH
        )

    def _on_resource_throttle(self, action: ThrottleAction, factor: float) -> None:
        """Callback when resource throttling changes."""
        self._log_debug(f"Throttle action: {action.value}, factor: {factor}")

        if action == ThrottleAction.EMERGENCY_STOP:
            self.enter_safe_mode(SafeModeReason.MEMORY_CRITICAL)

    def _on_circuit_open(self, process_name: str) -> None:
        """Callback when circuit breaker opens."""
        self._log_debug(f"Circuit breaker opened for {process_name}")

        # Check if too many circuits are open
        open_circuits = [
            name for name in self._config.monitored_processes
            if self._restart_engine.is_circuit_open(name)
        ]

        if len(open_circuits) >= 3:
            self.enter_safe_mode(SafeModeReason.CIRCUIT_BREAKER)

    def _attempt_restart(self, process_name: str, pid: Optional[int], reason: str) -> None:
        """Attempt to restart a process."""
        if self._dry_run:
            self._log_debug(f"[DRY-RUN] Would restart {process_name} (reason: {reason})")
            return

        # Record restart time
        self._restart_times.append(datetime.now())
        self._restart_times = [t for t in self._restart_times
                              if (datetime.now() - t).total_seconds() < self._config.safe_mode.restart_window_seconds]

        # Check restart threshold
        if len(self._restart_times) >= self._config.safe_mode.restart_threshold:
            self.enter_safe_mode(SafeModeReason.RESTART_THRESHOLD)
            return

        # Attempt restart
        attempt = self._restart_engine.restart_process(process_name, pid, reason)

        success = attempt.restart_result == RestartResult.SUCCESS

        # Update known PID
        if success and attempt.new_pid:
            with self._lock:
                self._known_pids[process_name] = attempt.new_pid
                self._process_monitor.track_process(process_name, attempt.new_pid)

        # Notify callbacks
        for callback in self._on_recovery_callbacks:
            try:
                callback(process_name, success)
            except Exception:
                pass

    def _is_critical_process(self, process_name: str) -> bool:
        """Check if a process is critical (should run even in safe mode)."""
        critical_processes = {"watchdog", "run_ai_employee", "filesystem_watcher"}
        return process_name in critical_processes

    def enter_safe_mode(self, reason: SafeModeReason) -> None:
        """Enter safe mode."""
        with self._lock:
            if self._safe_mode_active:
                return

            self._safe_mode_active = True
            self._safe_mode_reason = reason
            self._safe_mode_entered_at = datetime.now()
            self._state = WatchdogState.SAFE_MODE

            # Create flag file
            self.SAFE_MODE_FLAG.write_text(json.dumps({
                "entered_at": self._safe_mode_entered_at.isoformat(),
                "reason": reason.value
            }))

            # Update restart engine
            self._restart_engine.set_safe_mode(True)

        log_incident(
            event=IncidentType.SAFE_MODE_ENTER,
            process_name="watchdog",
            reason=reason.value,
            action="enter_safe_mode",
            result=IncidentResult.SUCCESS,
            severity=IncidentSeverity.CRITICAL
        )

        self._log_debug(f"SAFE MODE ENTERED: {reason.value}")

        # Notify callbacks
        for callback in self._on_safe_mode_callbacks:
            try:
                callback(True, reason.value)
            except Exception:
                pass

    def exit_safe_mode(self, manual: bool = False) -> None:
        """Exit safe mode."""
        with self._lock:
            if not self._safe_mode_active:
                return

            self._safe_mode_active = False
            self._safe_mode_reason = None
            self._safe_mode_entered_at = None
            self._state = WatchdogState.RUNNING

            # Remove flag file
            if self.SAFE_MODE_FLAG.exists():
                self.SAFE_MODE_FLAG.unlink()

            # Update restart engine
            self._restart_engine.set_safe_mode(False)

            # Clear counters
            self._crash_times.clear()
            self._restart_times.clear()

        log_incident(
            event=IncidentType.SAFE_MODE_EXIT,
            process_name="watchdog",
            reason="manual" if manual else "auto_recovery",
            action="exit_safe_mode",
            result=IncidentResult.SUCCESS,
            severity=IncidentSeverity.INFO
        )

        self._log_debug("SAFE MODE EXITED")

        # Notify callbacks
        for callback in self._on_safe_mode_callbacks:
            try:
                callback(False, None)
            except Exception:
                pass

    def _check_safe_mode_recovery(self) -> None:
        """Check if safe mode should be exited."""
        if not self._config.safe_mode.auto_recover:
            return

        if not self._safe_mode_entered_at:
            return

        elapsed = (datetime.now() - self._safe_mode_entered_at).total_seconds()

        if elapsed < self._config.safe_mode.recovery_timeout_seconds:
            return

        # Check if conditions have improved
        status = self._resource_guard.get_status()

        if status.cpu_percent < self._config.safe_mode.cpu_threshold - 10:
            if status.memory_percent < self._config.safe_mode.memory_threshold - 10:
                self._log_debug("Resources normalized, attempting safe mode exit...")
                self.exit_safe_mode()

    def _output_health_status(self) -> None:
        """Output system health to file."""
        try:
            health = self.get_system_health()
            self.HEALTH_FILE.write_text(json.dumps(health.to_dict(), indent=2))
        except Exception as e:
            self._log_debug(f"Error writing health status: {e}")

    def get_system_health(self) -> SystemHealth:
        """Get aggregated system health status."""
        resource_status = self._resource_guard.get_status()

        # Count process health states
        healthy = 0
        warning = 0
        critical = 0
        total = 0

        for process_name in self._config.monitored_processes:
            total += 1
            health = self._heartbeat_manager.get_agent_health(process_name)

            if health is None:
                continue

            if health.level in (HealthLevel.HEALTHY,):
                healthy += 1
            elif health.level in (HealthLevel.WARNING, HealthLevel.STALE):
                warning += 1
            else:
                critical += 1

        # Get open circuits
        open_circuits = [
            name for name in self._config.monitored_processes
            if self._restart_engine.is_circuit_open(name)
        ]

        # Get recent incidents
        recent_incidents = len(self._incident_logger.get_incidents(
            since=datetime.now() - timedelta(hours=1)
        ))

        return SystemHealth(
            timestamp=datetime.now().isoformat(),
            state=self._state.value,
            uptime_seconds=(datetime.now() - self._start_time).total_seconds() if self._start_time else 0,
            processes_healthy=healthy,
            processes_warning=warning,
            processes_critical=critical,
            processes_total=total,
            cpu_percent=resource_status.cpu_percent,
            memory_percent=resource_status.memory_percent,
            disk_percent=resource_status.disk_percent,
            resource_level=resource_status.level.value,
            throttle_factor=resource_status.throttle_factor,
            safe_mode_active=self._safe_mode_active,
            safe_mode_reason=self._safe_mode_reason.value if self._safe_mode_reason else None,
            open_circuits=open_circuits,
            recent_incidents=recent_incidents,
            last_scan=self._last_scan.isoformat() if self._last_scan else ""
        )

    def get_process_health(self, process_name: str) -> Optional[ProcessHealthStatus]:
        """Get health status for a specific process."""
        pid = self._known_pids.get(process_name)
        health = self._heartbeat_manager.get_agent_health(process_name)
        heartbeat = self._heartbeat_manager.get_heartbeat(process_name)

        restart_history = self._restart_engine.get_restart_history(process_name, limit=10)
        restart_count = len(restart_history)
        last_restart = restart_history[0].timestamp.isoformat() if restart_history else None

        circuit_open = self._restart_engine.is_circuit_open(process_name)

        return ProcessHealthStatus(
            name=process_name,
            pid=pid,
            state=heartbeat.status if heartbeat else "unknown",
            health=health.level.value if health else "unknown",
            last_heartbeat=heartbeat.timestamp if heartbeat else None,
            heartbeat_age_seconds=health.age_seconds if health else None,
            cpu_percent=heartbeat.cpu if heartbeat else 0.0,
            memory_percent=heartbeat.memory if heartbeat else 0.0,
            restart_count=restart_count,
            last_restart=last_restart,
            circuit_open=circuit_open
        )

    def get_state(self) -> WatchdogState:
        """Get current watchdog state."""
        return self._state

    def is_safe_mode(self) -> bool:
        """Check if safe mode is active."""
        return self._safe_mode_active

    def scan_once(self) -> SystemHealth:
        """Perform a single scan and return health status."""
        self._check_heartbeats()
        self._check_processes()
        self._check_resources()
        self._output_health_status()
        return self.get_system_health()


# Singleton accessor
def get_watchdog() -> WatchdogController:
    """Get the singleton WatchdogController instance."""
    return WatchdogController()


# Test / Demo
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Watchdog Controller Demo")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")
    parser.add_argument("--once", action="store_true", help="Single scan only")
    args = parser.parse_args()

    watchdog = get_watchdog()
    watchdog.set_debug(args.debug)
    watchdog.set_dry_run(args.dry_run)

    print("\n=== Watchdog Controller Demo ===\n")

    if args.once:
        health = watchdog.scan_once()
        print(f"State: {health.state}")
        print(f"CPU: {health.cpu_percent:.1f}%")
        print(f"Memory: {health.memory_percent:.1f}%")
        print(f"Resource Level: {health.resource_level}")
        print(f"Safe Mode: {health.safe_mode_active}")
    else:
        print("Starting watchdog... (Ctrl+C to stop)")
        watchdog.start()

        try:
            while watchdog.get_state() != WatchdogState.STOPPED:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping watchdog...")
            watchdog.stop()

    print("\n=== Demo Complete ===")
