"""
Heartbeat System - Agent Health Monitoring
Gold Tier Component - Watchdog System

Provides heartbeat tracking for all AI Employee agents.
Each agent writes heartbeat data every 10 seconds, and the
watchdog monitors for stale heartbeats to detect hung processes.

Features:
- Thread-safe heartbeat writing
- Cross-platform compatibility (Windows + Linux + WSL)
- Automatic stale heartbeat detection
- Integration with audit logging
- Minimal CPU overhead
"""

import os
import sys
import json
import time
import threading
import platform
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


# ==============================================================================
# CONFIGURATION
# ==============================================================================

class HeartbeatConfig:
    """Configuration for heartbeat system."""

    # Paths
    BASE_DIR = Path(__file__).parent.parent
    VAULT_DIR = BASE_DIR / "AI_Employee_Vault"
    WATCHDOG_DIR = VAULT_DIR / "Watchdog"
    HEARTBEAT_FILE = WATCHDOG_DIR / "heartbeats.json"

    # Timing (in seconds)
    HEARTBEAT_INTERVAL = 10      # Write heartbeat every 10s
    STALE_THRESHOLD = 60         # Consider stale after 60s
    HUNG_THRESHOLD = 120         # Consider hung after 120s
    DEAD_THRESHOLD = 300         # Consider dead after 5 min

    # Limits
    MAX_HEARTBEAT_HISTORY = 100  # Max heartbeats to keep per agent


# ==============================================================================
# ENUMERATIONS
# ==============================================================================

class AgentStatus(Enum):
    """Agent health status."""
    STARTING = "starting"
    RUNNING = "running"
    IDLE = "idle"
    BUSY = "busy"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    HUNG = "hung"
    DEAD = "dead"


class HeartbeatHealth(Enum):
    """Heartbeat health assessment."""
    HEALTHY = "healthy"
    WARNING = "warning"
    STALE = "stale"
    HUNG = "hung"
    DEAD = "dead"
    UNKNOWN = "unknown"


# Alias for backward compatibility
HealthLevel = HeartbeatHealth


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class Heartbeat:
    """Individual heartbeat data."""
    agent: str
    pid: int
    timestamp: str
    status: str
    current_task: Optional[str] = None
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_mb: float = 0.0
    uptime_seconds: float = 0.0
    tasks_completed: int = 0
    errors_count: int = 0
    last_error: Optional[str] = None
    hostname: str = field(default_factory=lambda: platform.node())
    platform: str = field(default_factory=lambda: platform.system())
    python_version: str = field(default_factory=lambda: platform.python_version())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Heartbeat':
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class AgentHealth:
    """Aggregated agent health information."""
    agent: str
    health: HeartbeatHealth
    last_heartbeat: Optional[datetime] = None
    seconds_since_heartbeat: float = 0.0
    pid: Optional[int] = None
    status: str = "unknown"
    current_task: Optional[str] = None
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    uptime_seconds: float = 0.0
    restart_count: int = 0
    error_count: int = 0

    @property
    def level(self) -> HeartbeatHealth:
        """Alias for health attribute (backward compatibility)."""
        return self.health

    @property
    def age_seconds(self) -> float:
        """Alias for seconds_since_heartbeat (backward compatibility)."""
        return self.seconds_since_heartbeat


# ==============================================================================
# HEARTBEAT MANAGER
# ==============================================================================

class HeartbeatManager:
    """
    Manages heartbeat data for all agents.

    Thread-safe implementation for reading and writing heartbeat data.
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
        """Initialize heartbeat manager."""
        if self._initialized:
            return

        self._initialized = True
        self._file_lock = threading.Lock()
        self._heartbeats: Dict[str, Heartbeat] = {}
        self._history: Dict[str, list] = {}

        # Ensure directory exists
        HeartbeatConfig.WATCHDOG_DIR.mkdir(parents=True, exist_ok=True)

        # Load existing heartbeats
        self._load_heartbeats()

    def _load_heartbeats(self):
        """Load heartbeats from file."""
        try:
            if HeartbeatConfig.HEARTBEAT_FILE.exists():
                with open(HeartbeatConfig.HEARTBEAT_FILE, 'r') as f:
                    data = json.load(f)
                    for agent, hb_data in data.get('current', {}).items():
                        self._heartbeats[agent] = Heartbeat.from_dict(hb_data)
        except Exception:
            pass  # Start fresh if file is corrupted

    def _save_heartbeats(self):
        """Save heartbeats to file."""
        try:
            data = {
                'updated': datetime.now().isoformat(),
                'current': {
                    agent: hb.to_dict()
                    for agent, hb in self._heartbeats.items()
                }
            }

            # Atomic write
            temp_file = HeartbeatConfig.HEARTBEAT_FILE.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2)
            temp_file.replace(HeartbeatConfig.HEARTBEAT_FILE)

        except Exception as e:
            # Log but don't crash
            pass

    def write_heartbeat(
        self,
        agent: str,
        status: AgentStatus = AgentStatus.RUNNING,
        current_task: Optional[str] = None,
        tasks_completed: int = 0,
        errors_count: int = 0,
        last_error: Optional[str] = None
    ) -> Heartbeat:
        """
        Write a heartbeat for an agent.

        Args:
            agent: Agent name/identifier
            status: Current agent status
            current_task: Task being processed (if any)
            tasks_completed: Number of tasks completed
            errors_count: Number of errors encountered
            last_error: Last error message (if any)

        Returns:
            The heartbeat that was written
        """
        pid = os.getpid()

        # Get resource usage
        cpu_percent = 0.0
        memory_percent = 0.0
        memory_mb = 0.0

        if PSUTIL_AVAILABLE:
            try:
                process = psutil.Process(pid)
                cpu_percent = process.cpu_percent(interval=0.1)
                memory_info = process.memory_info()
                memory_mb = memory_info.rss / (1024 * 1024)
                memory_percent = process.memory_percent()
            except Exception:
                pass

        # Calculate uptime
        uptime = 0.0
        if agent in self._heartbeats:
            try:
                first_hb = datetime.fromisoformat(
                    self._history.get(agent, [{}])[0].get('timestamp', datetime.now().isoformat())
                )
                uptime = (datetime.now() - first_hb).total_seconds()
            except Exception:
                pass

        heartbeat = Heartbeat(
            agent=agent,
            pid=pid,
            timestamp=datetime.now().isoformat(),
            status=status.value if isinstance(status, AgentStatus) else status,
            current_task=current_task,
            cpu_percent=round(cpu_percent, 2),
            memory_percent=round(memory_percent, 2),
            memory_mb=round(memory_mb, 2),
            uptime_seconds=round(uptime, 2),
            tasks_completed=tasks_completed,
            errors_count=errors_count,
            last_error=last_error
        )

        with self._file_lock:
            self._heartbeats[agent] = heartbeat

            # Maintain history
            if agent not in self._history:
                self._history[agent] = []
            self._history[agent].append(heartbeat.to_dict())

            # Trim history
            if len(self._history[agent]) > HeartbeatConfig.MAX_HEARTBEAT_HISTORY:
                self._history[agent] = self._history[agent][-HeartbeatConfig.MAX_HEARTBEAT_HISTORY:]

            self._save_heartbeats()

        return heartbeat

    def get_heartbeat(self, agent: str) -> Optional[Heartbeat]:
        """Get the latest heartbeat for an agent."""
        with self._file_lock:
            return self._heartbeats.get(agent)

    def get_all_heartbeats(self) -> Dict[str, Heartbeat]:
        """Get all current heartbeats."""
        with self._file_lock:
            return dict(self._heartbeats)

    def get_agent_health(self, agent: str) -> AgentHealth:
        """
        Assess the health of an agent based on heartbeat data.

        Args:
            agent: Agent name

        Returns:
            AgentHealth assessment
        """
        heartbeat = self.get_heartbeat(agent)

        if heartbeat is None:
            return AgentHealth(
                agent=agent,
                health=HeartbeatHealth.UNKNOWN
            )

        # Calculate time since last heartbeat
        try:
            last_hb_time = datetime.fromisoformat(heartbeat.timestamp)
            seconds_since = (datetime.now() - last_hb_time).total_seconds()
        except Exception:
            seconds_since = float('inf')

        # Determine health status
        if seconds_since > HeartbeatConfig.DEAD_THRESHOLD:
            health = HeartbeatHealth.DEAD
        elif seconds_since > HeartbeatConfig.HUNG_THRESHOLD:
            health = HeartbeatHealth.HUNG
        elif seconds_since > HeartbeatConfig.STALE_THRESHOLD:
            health = HeartbeatHealth.STALE
        elif seconds_since > HeartbeatConfig.HEARTBEAT_INTERVAL * 3:
            health = HeartbeatHealth.WARNING
        else:
            health = HeartbeatHealth.HEALTHY

        return AgentHealth(
            agent=agent,
            health=health,
            last_heartbeat=last_hb_time if seconds_since != float('inf') else None,
            seconds_since_heartbeat=round(seconds_since, 2),
            pid=heartbeat.pid,
            status=heartbeat.status,
            current_task=heartbeat.current_task,
            cpu_percent=heartbeat.cpu_percent,
            memory_percent=heartbeat.memory_percent,
            uptime_seconds=heartbeat.uptime_seconds,
            error_count=heartbeat.errors_count
        )

    def get_all_health(self) -> Dict[str, AgentHealth]:
        """Get health status for all known agents."""
        return {
            agent: self.get_agent_health(agent)
            for agent in self._heartbeats.keys()
        }

    def remove_heartbeat(self, agent: str):
        """Remove heartbeat for an agent (when it shuts down)."""
        with self._file_lock:
            if agent in self._heartbeats:
                del self._heartbeats[agent]
            self._save_heartbeats()

    def clear_stale_heartbeats(self, max_age_seconds: float = 3600):
        """Remove heartbeats older than max_age_seconds."""
        now = datetime.now()
        stale_agents = []

        with self._file_lock:
            for agent, heartbeat in self._heartbeats.items():
                try:
                    hb_time = datetime.fromisoformat(heartbeat.timestamp)
                    if (now - hb_time).total_seconds() > max_age_seconds:
                        stale_agents.append(agent)
                except Exception:
                    stale_agents.append(agent)

            for agent in stale_agents:
                del self._heartbeats[agent]

            if stale_agents:
                self._save_heartbeats()

        return stale_agents


# ==============================================================================
# HEARTBEAT WRITER (For Agents)
# ==============================================================================

class HeartbeatWriter:
    """
    Automatic heartbeat writer for agents.

    Runs in a background thread to periodically write heartbeats.
    """

    def __init__(
        self,
        agent: str,
        interval: float = HeartbeatConfig.HEARTBEAT_INTERVAL,
        auto_start: bool = True
    ):
        """
        Initialize heartbeat writer.

        Args:
            agent: Agent name/identifier
            interval: Heartbeat interval in seconds
            auto_start: Start writing immediately
        """
        self.agent = agent
        self.interval = interval
        self.manager = HeartbeatManager()

        self._status = AgentStatus.STARTING
        self._current_task: Optional[str] = None
        self._tasks_completed = 0
        self._errors_count = 0
        self._last_error: Optional[str] = None

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

        if auto_start:
            self.start()

    def start(self):
        """Start the heartbeat writer thread."""
        if self._running:
            return

        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=True,
            name=f"heartbeat-{self.agent}"
        )
        self._thread.start()

    def stop(self):
        """Stop the heartbeat writer."""
        self._running = False
        self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        # Write final heartbeat
        self._status = AgentStatus.STOPPED
        self._write_heartbeat()

    def _heartbeat_loop(self):
        """Background heartbeat loop."""
        while self._running and not self._stop_event.is_set():
            try:
                self._write_heartbeat()
            except Exception:
                pass  # Don't crash on heartbeat failure

            # Wait for interval or stop signal
            self._stop_event.wait(timeout=self.interval)

    def _write_heartbeat(self):
        """Write current heartbeat."""
        with self._lock:
            self.manager.write_heartbeat(
                agent=self.agent,
                status=self._status,
                current_task=self._current_task,
                tasks_completed=self._tasks_completed,
                errors_count=self._errors_count,
                last_error=self._last_error
            )

    def set_status(self, status: AgentStatus):
        """Update agent status."""
        with self._lock:
            self._status = status

    def set_task(self, task: Optional[str]):
        """Update current task."""
        with self._lock:
            self._current_task = task

    def update_task(self, task: Optional[str]):
        """
        Update current task and set status to RUNNING/BUSY.

        This is a convenience method that:
        - Updates the current task description
        - Sets status to BUSY if task is provided, IDLE if None
        - Triggers an immediate heartbeat write

        Args:
            task: Current task description (e.g., "processing:file.md")
        """
        with self._lock:
            self._current_task = task
            if task:
                self._status = AgentStatus.BUSY if "processing" in str(task).lower() else AgentStatus.RUNNING
            else:
                self._status = AgentStatus.IDLE

        # Write immediate heartbeat to reflect the change
        self._write_heartbeat()

    def task_completed(self):
        """Increment completed task counter."""
        with self._lock:
            self._tasks_completed += 1
            self._current_task = None

    def record_error(self, error: str):
        """Record an error."""
        with self._lock:
            self._errors_count += 1
            self._last_error = error[:200]  # Truncate

    def beat(self):
        """Write an immediate heartbeat (manual trigger)."""
        self._write_heartbeat()


# ==============================================================================
# CONTEXT MANAGER
# ==============================================================================

class HeartbeatContext:
    """
    Context manager for automatic heartbeat handling.

    Usage:
        with HeartbeatContext("agent_executor") as hb:
            hb.set_task("processing emails")
            # do work
            hb.task_completed()
    """

    def __init__(self, agent: str, auto_start: bool = True):
        self.agent = agent
        self.auto_start = auto_start
        self.writer: Optional[HeartbeatWriter] = None

    def __enter__(self) -> HeartbeatWriter:
        self.writer = HeartbeatWriter(
            agent=self.agent,
            auto_start=self.auto_start
        )
        self.writer.set_status(AgentStatus.RUNNING)
        return self.writer

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.writer:
            if exc_type is not None:
                self.writer.record_error(str(exc_val))
                self.writer.set_status(AgentStatus.ERROR)
            self.writer.stop()
        return False  # Don't suppress exceptions


# ==============================================================================
# SINGLETON ACCESSORS
# ==============================================================================

_heartbeat_manager: Optional[HeartbeatManager] = None
_heartbeat_writers: Dict[str, HeartbeatWriter] = {}


def get_heartbeat_manager() -> HeartbeatManager:
    """Get the singleton heartbeat manager."""
    global _heartbeat_manager
    if _heartbeat_manager is None:
        _heartbeat_manager = HeartbeatManager()
    return _heartbeat_manager


def get_heartbeat_writer(agent: str, auto_start: bool = True) -> HeartbeatWriter:
    """Get or create a heartbeat writer for an agent."""
    global _heartbeat_writers
    if agent not in _heartbeat_writers:
        _heartbeat_writers[agent] = HeartbeatWriter(agent, auto_start=auto_start)
    return _heartbeat_writers[agent]


def stop_heartbeat_writer(agent: str):
    """Stop and remove a heartbeat writer."""
    global _heartbeat_writers
    if agent in _heartbeat_writers:
        _heartbeat_writers[agent].stop()
        del _heartbeat_writers[agent]


# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def check_all_agents_health() -> Dict[str, AgentHealth]:
    """Check health of all registered agents."""
    return get_heartbeat_manager().get_all_health()


def get_unhealthy_agents() -> Dict[str, AgentHealth]:
    """Get agents that are not healthy."""
    all_health = check_all_agents_health()
    return {
        agent: health
        for agent, health in all_health.items()
        if health.health not in [HeartbeatHealth.HEALTHY, HeartbeatHealth.WARNING]
    }


def is_agent_alive(agent: str, max_stale_seconds: float = None) -> bool:
    """Check if an agent is alive based on heartbeat."""
    if max_stale_seconds is None:
        max_stale_seconds = HeartbeatConfig.STALE_THRESHOLD

    manager = get_heartbeat_manager()
    heartbeat = manager.get_heartbeat(agent)

    if heartbeat is None:
        return False

    try:
        hb_time = datetime.fromisoformat(heartbeat.timestamp)
        seconds_since = (datetime.now() - hb_time).total_seconds()
        return seconds_since <= max_stale_seconds
    except Exception:
        return False


# ==============================================================================
# TEST / DEMO
# ==============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Heartbeat System - Test")
    print("=" * 60)

    # Test heartbeat writer
    print("\n1. Testing HeartbeatWriter...")
    writer = HeartbeatWriter("test_agent", interval=2)
    writer.set_status(AgentStatus.RUNNING)
    writer.set_task("test_task_1")

    time.sleep(3)
    writer.task_completed()
    writer.set_task("test_task_2")

    time.sleep(2)
    writer.stop()
    print("   HeartbeatWriter test complete")

    # Test heartbeat manager
    print("\n2. Testing HeartbeatManager...")
    manager = get_heartbeat_manager()

    # Check health
    health = manager.get_agent_health("test_agent")
    print(f"   Agent: {health.agent}")
    print(f"   Health: {health.health.value}")
    print(f"   Last heartbeat: {health.seconds_since_heartbeat:.1f}s ago")
    print(f"   PID: {health.pid}")

    # Test context manager
    print("\n3. Testing HeartbeatContext...")
    with HeartbeatContext("context_test_agent") as hb:
        hb.set_task("context_task")
        time.sleep(2)
        hb.task_completed()
    print("   HeartbeatContext test complete")

    # Show all heartbeats
    print("\n4. All heartbeats:")
    all_hb = manager.get_all_heartbeats()
    for agent, hb in all_hb.items():
        print(f"   - {agent}: {hb.status} (PID {hb.pid})")

    print("\n" + "=" * 60)
    print("Heartbeat System tests completed!")
    print("=" * 60)
