"""
Process Monitor - Process Health Detection
Gold Tier Component - Watchdog System

Monitors process states and detects anomalies:
- Crashed processes
- Hung/frozen processes
- Zombie processes
- Infinite loops
- Memory leaks

Features:
- Cross-platform (Windows + Linux + WSL)
- Non-intrusive monitoring
- PID tracking and validation
- Process state classification
"""

import os
import sys
import time
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("[WARNING] psutil not installed. Process monitoring limited.")


# ==============================================================================
# ENUMERATIONS
# ==============================================================================

class ProcessState(Enum):
    """Process state classification."""
    RUNNING = "running"
    SLEEPING = "sleeping"
    IDLE = "idle"
    STOPPED = "stopped"
    ZOMBIE = "zombie"
    DEAD = "dead"
    NOT_FOUND = "not_found"
    UNKNOWN = "unknown"


class ProcessHealth(Enum):
    """Process health assessment."""
    HEALTHY = "healthy"
    WARNING = "warning"
    HUNG = "hung"
    CRASHED = "crashed"
    ZOMBIE = "zombie"
    RUNAWAY = "runaway"  # Infinite loop / high CPU
    MEMORY_LEAK = "memory_leak"
    UNKNOWN = "unknown"


class ProcessPriority(Enum):
    """Process priority for restart ordering."""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


# ==============================================================================
# CONFIGURATION
# ==============================================================================

class ProcessMonitorConfig:
    """Configuration for process monitoring."""

    # Thresholds
    HUNG_CPU_THRESHOLD = 0.5        # CPU < 0.5% considered idle
    HUNG_TIME_THRESHOLD = 120       # Seconds before declaring hung
    RUNAWAY_CPU_THRESHOLD = 95      # CPU > 95% considered runaway
    RUNAWAY_TIME_THRESHOLD = 60     # Sustained for this many seconds
    MEMORY_LEAK_GROWTH = 50         # MB growth to flag leak
    MEMORY_LEAK_TIME = 300          # Over this many seconds

    # Monitored processes configuration
    MONITORED_PROCESSES = {
        "run_ai_employee": {
            "script": "scripts/run_ai_employee.py",
            "priority": ProcessPriority.CRITICAL,
            "restart_on_crash": True,
            "max_memory_mb": 512
        },
        "agent_executor": {
            "script": "agent_executor.py",
            "priority": ProcessPriority.CRITICAL,
            "restart_on_crash": True,
            "max_memory_mb": 256
        },
        "filesystem_watcher": {
            "script": "filesystem_watcher.py",
            "priority": ProcessPriority.HIGH,
            "restart_on_crash": True,
            "max_memory_mb": 128
        },
        "plan_creator": {
            "script": "scripts/plan_creator.py",
            "priority": ProcessPriority.MEDIUM,
            "restart_on_crash": True,
            "max_memory_mb": 256
        },
        "linkedin_poster": {
            "script": "scripts/linkedin_poster.py",
            "priority": ProcessPriority.MEDIUM,
            "restart_on_crash": True,
            "max_memory_mb": 512  # Browser automation needs more
        },
        "ceo_briefing_generator": {
            "script": "scripts/ceo_briefing_generator.py",
            "priority": ProcessPriority.LOW,
            "restart_on_crash": False,  # Not critical
            "max_memory_mb": 256
        },
        "email_server": {
            "script": "mcp_servers/email_server.py",
            "priority": ProcessPriority.MEDIUM,
            "restart_on_crash": True,
            "max_memory_mb": 128
        }
    }


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class ProcessInfo:
    """Information about a monitored process."""
    name: str
    pid: Optional[int] = None
    state: ProcessState = ProcessState.UNKNOWN
    health: ProcessHealth = ProcessHealth.UNKNOWN
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    memory_percent: float = 0.0
    threads: int = 0
    create_time: Optional[datetime] = None
    last_check: Optional[datetime] = None
    uptime_seconds: float = 0.0
    cmdline: str = ""
    is_responsive: bool = True

    # Tracking for anomaly detection
    cpu_history: List[float] = field(default_factory=list)
    memory_history: List[float] = field(default_factory=list)
    last_activity: Optional[datetime] = None


@dataclass
class ProcessCheckResult:
    """Result of a process health check."""
    name: str
    pid: Optional[int]
    health: ProcessHealth
    state: ProcessState
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    requires_action: bool = False
    action_type: Optional[str] = None  # "restart", "kill", "alert"


# ==============================================================================
# PROCESS MONITOR
# ==============================================================================

class ProcessMonitor:
    """
    Monitors process health and detects anomalies.

    Thread-safe implementation for continuous monitoring.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize process monitor."""
        if self._initialized:
            return

        self._initialized = True
        self._processes: Dict[str, ProcessInfo] = {}
        self._pid_map: Dict[str, int] = {}  # name -> pid mapping
        self._check_lock = threading.Lock()

        # History for trend analysis
        self._history_size = 30  # Keep 30 data points

    def register_process(self, name: str, pid: int):
        """
        Register a process to monitor.

        Args:
            name: Process name/identifier
            pid: Process ID
        """
        with self._check_lock:
            self._pid_map[name] = pid
            self._processes[name] = ProcessInfo(
                name=name,
                pid=pid,
                last_check=datetime.now()
            )

    def track_process(self, name: str, pid: int):
        """
        Track a process for monitoring.

        Alias for register_process.

        Args:
            name: Process name/identifier
            pid: Process ID
        """
        self.register_process(name, pid)

    def unregister_process(self, name: str):
        """Remove a process from monitoring."""
        with self._check_lock:
            if name in self._pid_map:
                del self._pid_map[name]
            if name in self._processes:
                del self._processes[name]

    def get_process_state(self, pid: int) -> ProcessState:
        """
        Get the state of a process by PID.

        Args:
            pid: Process ID

        Returns:
            ProcessState enum value
        """
        if not PSUTIL_AVAILABLE:
            return ProcessState.UNKNOWN

        try:
            process = psutil.Process(pid)
            status = process.status()

            status_map = {
                psutil.STATUS_RUNNING: ProcessState.RUNNING,
                psutil.STATUS_SLEEPING: ProcessState.SLEEPING,
                psutil.STATUS_IDLE: ProcessState.IDLE,
                psutil.STATUS_STOPPED: ProcessState.STOPPED,
                psutil.STATUS_ZOMBIE: ProcessState.ZOMBIE,
                psutil.STATUS_DEAD: ProcessState.DEAD,
            }

            return status_map.get(status, ProcessState.UNKNOWN)

        except psutil.NoSuchProcess:
            return ProcessState.NOT_FOUND
        except psutil.AccessDenied:
            return ProcessState.UNKNOWN
        except Exception:
            return ProcessState.UNKNOWN

    def get_process_info(self, name: str) -> Optional[ProcessInfo]:
        """
        Get detailed information about a monitored process.

        Args:
            name: Process name

        Returns:
            ProcessInfo or None if not found
        """
        if not PSUTIL_AVAILABLE:
            return None

        pid = self._pid_map.get(name)
        if pid is None:
            return None

        try:
            process = psutil.Process(pid)

            # Get basic info
            cpu_percent = process.cpu_percent(interval=0.1)
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)
            memory_percent = process.memory_percent()

            # Get state
            state = self.get_process_state(pid)

            # Build process info
            info = ProcessInfo(
                name=name,
                pid=pid,
                state=state,
                cpu_percent=round(cpu_percent, 2),
                memory_mb=round(memory_mb, 2),
                memory_percent=round(memory_percent, 2),
                threads=process.num_threads(),
                create_time=datetime.fromtimestamp(process.create_time()),
                last_check=datetime.now(),
                cmdline=" ".join(process.cmdline()[:3]),  # First 3 parts
                is_responsive=True
            )

            # Calculate uptime
            info.uptime_seconds = (datetime.now() - info.create_time).total_seconds()

            # Update history
            with self._check_lock:
                if name in self._processes:
                    old_info = self._processes[name]
                    info.cpu_history = old_info.cpu_history[-self._history_size:] + [cpu_percent]
                    info.memory_history = old_info.memory_history[-self._history_size:] + [memory_mb]
                else:
                    info.cpu_history = [cpu_percent]
                    info.memory_history = [memory_mb]

                self._processes[name] = info

            return info

        except psutil.NoSuchProcess:
            info = ProcessInfo(
                name=name,
                pid=pid,
                state=ProcessState.NOT_FOUND,
                health=ProcessHealth.CRASHED,
                last_check=datetime.now()
            )
            with self._check_lock:
                self._processes[name] = info
            return info

        except Exception as e:
            return None

    def check_process_health(self, name: str) -> ProcessCheckResult:
        """
        Perform comprehensive health check on a process.

        Args:
            name: Process name

        Returns:
            ProcessCheckResult with health assessment
        """
        info = self.get_process_info(name)
        issues = []
        recommendations = []
        health = ProcessHealth.HEALTHY
        requires_action = False
        action_type = None

        if info is None:
            return ProcessCheckResult(
                name=name,
                pid=None,
                health=ProcessHealth.UNKNOWN,
                state=ProcessState.UNKNOWN,
                issues=["Unable to get process information"],
                requires_action=False
            )

        # Check if process exists
        if info.state == ProcessState.NOT_FOUND:
            return ProcessCheckResult(
                name=name,
                pid=info.pid,
                health=ProcessHealth.CRASHED,
                state=ProcessState.NOT_FOUND,
                issues=["Process not found - likely crashed"],
                recommendations=["Restart process"],
                requires_action=True,
                action_type="restart"
            )

        # Check for zombie
        if info.state == ProcessState.ZOMBIE:
            return ProcessCheckResult(
                name=name,
                pid=info.pid,
                health=ProcessHealth.ZOMBIE,
                state=ProcessState.ZOMBIE,
                issues=["Process is zombie - defunct but not reaped"],
                recommendations=["Kill zombie process and restart"],
                requires_action=True,
                action_type="kill"
            )

        # Check for hung process (low CPU for extended period)
        if len(info.cpu_history) >= 10:
            avg_cpu = sum(info.cpu_history[-10:]) / 10
            if avg_cpu < ProcessMonitorConfig.HUNG_CPU_THRESHOLD:
                issues.append(f"Process appears hung (avg CPU: {avg_cpu:.2f}%)")
                health = ProcessHealth.HUNG
                requires_action = True
                action_type = "restart"

        # Check for runaway process (very high CPU)
        if len(info.cpu_history) >= 5:
            recent_cpu = info.cpu_history[-5:]
            if all(c > ProcessMonitorConfig.RUNAWAY_CPU_THRESHOLD for c in recent_cpu):
                issues.append(f"Process runaway - sustained high CPU ({info.cpu_percent}%)")
                health = ProcessHealth.RUNAWAY
                requires_action = True
                action_type = "restart"

        # Check for memory leak
        if len(info.memory_history) >= 10:
            memory_growth = info.memory_history[-1] - info.memory_history[0]
            if memory_growth > ProcessMonitorConfig.MEMORY_LEAK_GROWTH:
                issues.append(f"Possible memory leak - grew {memory_growth:.1f}MB")
                if health == ProcessHealth.HEALTHY:
                    health = ProcessHealth.MEMORY_LEAK
                recommendations.append("Monitor memory usage closely")

        # Check against max memory
        config = ProcessMonitorConfig.MONITORED_PROCESSES.get(name, {})
        max_memory = config.get("max_memory_mb", 512)
        if info.memory_mb > max_memory:
            issues.append(f"Memory exceeds limit ({info.memory_mb:.1f}MB > {max_memory}MB)")
            if health == ProcessHealth.HEALTHY:
                health = ProcessHealth.WARNING

        # Set health based on issues
        if not issues:
            health = ProcessHealth.HEALTHY
        elif health == ProcessHealth.HEALTHY and issues:
            health = ProcessHealth.WARNING

        # Update stored info
        info.health = health
        with self._check_lock:
            self._processes[name] = info

        return ProcessCheckResult(
            name=name,
            pid=info.pid,
            health=health,
            state=info.state,
            issues=issues,
            recommendations=recommendations,
            requires_action=requires_action,
            action_type=action_type
        )

    def check_process(self, pid: int, name: str) -> ProcessCheckResult:
        """
        Check health of a specific process by PID and name.

        Updates internal PID mapping and performs health check.

        Args:
            pid: Process ID
            name: Process name/identifier

        Returns:
            ProcessCheckResult with health assessment
        """
        # Ensure process is registered with current PID
        with self._check_lock:
            if name not in self._pid_map or self._pid_map[name] != pid:
                self._pid_map[name] = pid
                if name not in self._processes:
                    self._processes[name] = ProcessInfo(
                        name=name,
                        pid=pid,
                        last_check=datetime.now()
                    )
                else:
                    self._processes[name].pid = pid

        return self.check_process_health(name)

    def check_all_processes(self) -> Dict[str, ProcessCheckResult]:
        """
        Check health of all registered processes.

        Returns:
            Dict of process name to check result
        """
        results = {}
        for name in list(self._pid_map.keys()):
            results[name] = self.check_process_health(name)
        return results

    def find_process_by_script(self, script_name: str) -> Optional[int]:
        """
        Find a process PID by its script name.

        Args:
            script_name: Name of the script (e.g., "run_ai_employee.py")

        Returns:
            PID if found, None otherwise
        """
        if not PSUTIL_AVAILABLE:
            return None

        try:
            for proc in psutil.process_iter(['pid', 'cmdline']):
                try:
                    cmdline = proc.info.get('cmdline', [])
                    if cmdline:
                        cmd_str = " ".join(cmdline)
                        if script_name in cmd_str:
                            return proc.info['pid']
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass

        return None

    def discover_processes(self) -> Dict[str, int]:
        """
        Discover and register all monitored processes.

        Returns:
            Dict of process name to PID
        """
        discovered = {}

        for name, config in ProcessMonitorConfig.MONITORED_PROCESSES.items():
            script = config["script"]
            pid = self.find_process_by_script(script)

            if pid:
                self.register_process(name, pid)
                discovered[name] = pid

        return discovered

    def get_unhealthy_processes(self) -> List[ProcessCheckResult]:
        """Get list of processes that are not healthy."""
        results = self.check_all_processes()
        return [
            result for result in results.values()
            if result.health not in [ProcessHealth.HEALTHY, ProcessHealth.WARNING]
        ]

    def get_processes_requiring_action(self) -> List[ProcessCheckResult]:
        """Get list of processes that require action."""
        results = self.check_all_processes()
        return [
            result for result in results.values()
            if result.requires_action
        ]

    def is_process_alive(self, name: str) -> bool:
        """Check if a process is alive."""
        pid = self._pid_map.get(name)
        if pid is None:
            return False

        if not PSUTIL_AVAILABLE:
            # Fallback: try to send signal 0
            try:
                os.kill(pid, 0)
                return True
            except OSError:
                return False

        try:
            process = psutil.Process(pid)
            return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
        except psutil.NoSuchProcess:
            return False
        except Exception:
            return False

    def get_system_process_count(self) -> int:
        """Get total number of processes on system."""
        if not PSUTIL_AVAILABLE:
            return 0
        return len(psutil.pids())

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all monitored processes."""
        results = self.check_all_processes()

        healthy = sum(1 for r in results.values() if r.health == ProcessHealth.HEALTHY)
        warning = sum(1 for r in results.values() if r.health == ProcessHealth.WARNING)
        unhealthy = sum(1 for r in results.values() if r.health not in [ProcessHealth.HEALTHY, ProcessHealth.WARNING])

        return {
            "timestamp": datetime.now().isoformat(),
            "total_monitored": len(results),
            "healthy": healthy,
            "warning": warning,
            "unhealthy": unhealthy,
            "processes": {
                name: {
                    "pid": r.pid,
                    "health": r.health.value,
                    "state": r.state.value,
                    "issues": r.issues,
                    "requires_action": r.requires_action
                }
                for name, r in results.items()
            }
        }


# ==============================================================================
# SINGLETON ACCESSOR
# ==============================================================================

_process_monitor: Optional[ProcessMonitor] = None


def get_process_monitor() -> ProcessMonitor:
    """Get the singleton process monitor."""
    global _process_monitor
    if _process_monitor is None:
        _process_monitor = ProcessMonitor()
    return _process_monitor


# ==============================================================================
# TEST / DEMO
# ==============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Process Monitor - Test")
    print("=" * 60)

    if not PSUTIL_AVAILABLE:
        print("\n[ERROR] psutil not installed. Run: pip install psutil")
        sys.exit(1)

    monitor = get_process_monitor()

    # Register current process for testing
    print("\n1. Registering current process...")
    monitor.register_process("test_process", os.getpid())

    # Get process info
    print("\n2. Getting process info...")
    info = monitor.get_process_info("test_process")
    if info:
        print(f"   PID: {info.pid}")
        print(f"   State: {info.state.value}")
        print(f"   CPU: {info.cpu_percent}%")
        print(f"   Memory: {info.memory_mb:.1f}MB")
        print(f"   Threads: {info.threads}")

    # Check health
    print("\n3. Checking process health...")
    result = monitor.check_process_health("test_process")
    print(f"   Health: {result.health.value}")
    print(f"   Issues: {result.issues or 'None'}")
    print(f"   Requires action: {result.requires_action}")

    # Discover processes
    print("\n4. Discovering AI Employee processes...")
    discovered = monitor.discover_processes()
    if discovered:
        for name, pid in discovered.items():
            print(f"   Found: {name} (PID {pid})")
    else:
        print("   No AI Employee processes currently running")

    # Summary
    print("\n5. Process summary:")
    summary = monitor.get_summary()
    print(f"   Total monitored: {summary['total_monitored']}")
    print(f"   Healthy: {summary['healthy']}")
    print(f"   Warning: {summary['warning']}")
    print(f"   Unhealthy: {summary['unhealthy']}")

    print("\n" + "=" * 60)
    print("Process Monitor tests completed!")
    print("=" * 60)
