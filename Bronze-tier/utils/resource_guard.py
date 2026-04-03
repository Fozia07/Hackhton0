"""
Resource Guard - CPU/RAM Monitoring & Throttling
Gold Tier Component - Watchdog System

Monitors system resources and implements throttling to prevent overload:
- CPU usage monitoring
- RAM usage monitoring
- Disk usage monitoring
- Automatic throttling
- Emergency mode triggering

Features:
- Cross-platform (Windows + Linux + WSL)
- Non-blocking resource checks
- Configurable thresholds
- Trend analysis
"""

import os
import sys
import time
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("[WARNING] psutil not installed. Resource monitoring limited.")


# ==============================================================================
# ENUMERATIONS
# ==============================================================================

class ResourceLevel(Enum):
    """Resource usage level."""
    NORMAL = "normal"
    WARNING = "warning"
    THROTTLE = "throttle"
    EMERGENCY = "emergency"
    CRITICAL = "critical"


class ThrottleAction(Enum):
    """Throttling actions."""
    NONE = "none"
    SLOW_DOWN = "slow_down"
    PAUSE_NON_CRITICAL = "pause_non_critical"
    PAUSE_ALL = "pause_all"
    EMERGENCY_STOP = "emergency_stop"


# ==============================================================================
# CONFIGURATION
# ==============================================================================

class ResourceConfig:
    """Configuration for resource monitoring."""

    # CPU Thresholds (percentage)
    CPU_NORMAL = 70
    CPU_WARNING = 75
    CPU_THROTTLE = 85
    CPU_EMERGENCY = 95

    # RAM Thresholds (percentage)
    RAM_NORMAL = 65
    RAM_WARNING = 70
    RAM_THROTTLE = 80
    RAM_EMERGENCY = 90

    # Disk Thresholds (percentage)
    DISK_WARNING = 80
    DISK_THROTTLE = 90
    DISK_EMERGENCY = 95

    # Monitoring
    CHECK_INTERVAL = 5  # seconds
    HISTORY_SIZE = 60   # data points to keep
    TREND_WINDOW = 10   # data points for trend analysis

    # Throttling
    THROTTLE_DELAY_MULTIPLIER = 2.0  # Multiply delays by this
    THROTTLE_RECOVERY_TIME = 60      # Seconds before reducing throttle


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class ResourceSnapshot:
    """Snapshot of system resources."""
    timestamp: datetime
    cpu_percent: float
    cpu_count: int
    cpu_freq_mhz: float

    memory_total_gb: float
    memory_available_gb: float
    memory_used_gb: float
    memory_percent: float

    disk_total_gb: float
    disk_used_gb: float
    disk_free_gb: float
    disk_percent: float

    # Per-CPU usage (optional)
    cpu_per_core: List[float] = field(default_factory=list)


@dataclass
class ResourceStatus:
    """Current resource status with levels."""
    timestamp: datetime
    cpu_level: ResourceLevel
    ram_level: ResourceLevel
    disk_level: ResourceLevel
    overall_level: ResourceLevel
    throttle_action: ThrottleAction
    is_throttled: bool
    throttle_factor: float  # 1.0 = normal, 2.0 = 2x delays
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    # Raw percentage values for easy access
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_percent: float = 0.0

    @property
    def level(self) -> 'ResourceLevel':
        """Alias for overall_level."""
        return self.overall_level


@dataclass
class ResourceTrend:
    """Resource usage trend analysis."""
    resource: str
    current: float
    avg_5min: float
    avg_15min: float
    trend: str  # "rising", "falling", "stable"
    prediction_10min: float


# ==============================================================================
# RESOURCE GUARD
# ==============================================================================

class ResourceGuard:
    """
    Monitors system resources and implements throttling.

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
        """Initialize resource guard."""
        if self._initialized:
            return

        self._initialized = True
        self._history: List[ResourceSnapshot] = []
        self._check_lock = threading.Lock()
        self._throttle_factor = 1.0
        self._throttle_start: Optional[datetime] = None
        self._last_check: Optional[datetime] = None
        self._last_throttle_action: ThrottleAction = ThrottleAction.NONE

        # Callbacks for throttle events (callback receives: action, throttle_factor)
        self._throttle_callbacks: List[Callable[[ThrottleAction, float], None]] = []

    def get_snapshot(self) -> ResourceSnapshot:
        """
        Get current resource snapshot.

        Returns:
            ResourceSnapshot with current usage data
        """
        now = datetime.now()

        if not PSUTIL_AVAILABLE:
            return ResourceSnapshot(
                timestamp=now,
                cpu_percent=0.0,
                cpu_count=1,
                cpu_freq_mhz=0.0,
                memory_total_gb=0.0,
                memory_available_gb=0.0,
                memory_used_gb=0.0,
                memory_percent=0.0,
                disk_total_gb=0.0,
                disk_used_gb=0.0,
                disk_free_gb=0.0,
                disk_percent=0.0
            )

        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            cpu_freq_mhz = cpu_freq.current if cpu_freq else 0.0
            cpu_per_core = psutil.cpu_percent(interval=0.1, percpu=True)

            # Memory
            memory = psutil.virtual_memory()
            memory_total_gb = memory.total / (1024 ** 3)
            memory_available_gb = memory.available / (1024 ** 3)
            memory_used_gb = memory.used / (1024 ** 3)
            memory_percent = memory.percent

            # Disk (root partition)
            try:
                disk = psutil.disk_usage('/')
            except Exception:
                # Windows fallback
                disk = psutil.disk_usage('C:\\')

            disk_total_gb = disk.total / (1024 ** 3)
            disk_used_gb = disk.used / (1024 ** 3)
            disk_free_gb = disk.free / (1024 ** 3)
            disk_percent = disk.percent

            snapshot = ResourceSnapshot(
                timestamp=now,
                cpu_percent=round(cpu_percent, 2),
                cpu_count=cpu_count,
                cpu_freq_mhz=round(cpu_freq_mhz, 2),
                memory_total_gb=round(memory_total_gb, 2),
                memory_available_gb=round(memory_available_gb, 2),
                memory_used_gb=round(memory_used_gb, 2),
                memory_percent=round(memory_percent, 2),
                disk_total_gb=round(disk_total_gb, 2),
                disk_used_gb=round(disk_used_gb, 2),
                disk_free_gb=round(disk_free_gb, 2),
                disk_percent=round(disk_percent, 2),
                cpu_per_core=cpu_per_core
            )

            # Store in history
            with self._check_lock:
                self._history.append(snapshot)
                # Trim history
                if len(self._history) > ResourceConfig.HISTORY_SIZE:
                    self._history = self._history[-ResourceConfig.HISTORY_SIZE:]
                self._last_check = now

            return snapshot

        except Exception as e:
            return ResourceSnapshot(
                timestamp=now,
                cpu_percent=0.0,
                cpu_count=1,
                cpu_freq_mhz=0.0,
                memory_total_gb=0.0,
                memory_available_gb=0.0,
                memory_used_gb=0.0,
                memory_percent=0.0,
                disk_total_gb=0.0,
                disk_used_gb=0.0,
                disk_free_gb=0.0,
                disk_percent=0.0
            )

    def _get_level(self, value: float, normal: float, warning: float,
                   throttle: float, emergency: float) -> ResourceLevel:
        """Determine resource level based on thresholds."""
        if value >= emergency:
            return ResourceLevel.CRITICAL
        elif value >= throttle:
            return ResourceLevel.THROTTLE
        elif value >= warning:
            return ResourceLevel.WARNING
        elif value >= normal:
            return ResourceLevel.NORMAL
        else:
            return ResourceLevel.NORMAL

    def get_status(self) -> ResourceStatus:
        """
        Get current resource status with throttle recommendations.

        Returns:
            ResourceStatus with levels and actions
        """
        snapshot = self.get_snapshot()
        issues = []
        recommendations = []

        # Determine levels
        cpu_level = self._get_level(
            snapshot.cpu_percent,
            ResourceConfig.CPU_NORMAL,
            ResourceConfig.CPU_WARNING,
            ResourceConfig.CPU_THROTTLE,
            ResourceConfig.CPU_EMERGENCY
        )

        ram_level = self._get_level(
            snapshot.memory_percent,
            ResourceConfig.RAM_NORMAL,
            ResourceConfig.RAM_WARNING,
            ResourceConfig.RAM_THROTTLE,
            ResourceConfig.RAM_EMERGENCY
        )

        disk_level = self._get_level(
            snapshot.disk_percent,
            80, 85, 90, 95  # Disk thresholds
        )

        # Overall level is the worst of all
        levels = [cpu_level, ram_level, disk_level]
        level_priority = {
            ResourceLevel.CRITICAL: 5,
            ResourceLevel.EMERGENCY: 4,
            ResourceLevel.THROTTLE: 3,
            ResourceLevel.WARNING: 2,
            ResourceLevel.NORMAL: 1
        }
        overall_level = max(levels, key=lambda l: level_priority.get(l, 0))

        # Determine throttle action
        throttle_action = ThrottleAction.NONE
        is_throttled = False
        throttle_factor = 1.0

        if overall_level == ResourceLevel.CRITICAL:
            throttle_action = ThrottleAction.EMERGENCY_STOP
            is_throttled = True
            throttle_factor = 10.0
            issues.append("CRITICAL: System resources critically low")
            recommendations.append("Enter safe mode immediately")

        elif overall_level == ResourceLevel.THROTTLE:
            throttle_action = ThrottleAction.PAUSE_NON_CRITICAL
            is_throttled = True
            throttle_factor = 3.0
            issues.append("Resources elevated - throttling active")
            recommendations.append("Pause non-critical operations")

        elif overall_level == ResourceLevel.WARNING:
            throttle_action = ThrottleAction.SLOW_DOWN
            is_throttled = True
            throttle_factor = 1.5
            issues.append("Resource usage elevated")
            recommendations.append("Monitor closely")

        # Add specific issues
        if cpu_level in [ResourceLevel.THROTTLE, ResourceLevel.CRITICAL]:
            issues.append(f"CPU: {snapshot.cpu_percent}%")

        if ram_level in [ResourceLevel.THROTTLE, ResourceLevel.CRITICAL]:
            issues.append(f"RAM: {snapshot.memory_percent}%")

        if disk_level in [ResourceLevel.THROTTLE, ResourceLevel.CRITICAL]:
            issues.append(f"Disk: {snapshot.disk_percent}%")

        # Update throttle state and notify callbacks
        with self._check_lock:
            prev_action = self._last_throttle_action
            if is_throttled:
                self._throttle_factor = throttle_factor
                if self._throttle_start is None:
                    self._throttle_start = datetime.now()
            else:
                self._throttle_factor = 1.0
                self._throttle_start = None

            # Invoke callbacks if throttle action changed
            if throttle_action != prev_action:
                self._last_throttle_action = throttle_action
                for callback in self._throttle_callbacks:
                    try:
                        callback(throttle_action, throttle_factor)
                    except Exception:
                        pass  # Don't let callback errors break monitoring

        return ResourceStatus(
            timestamp=snapshot.timestamp,
            cpu_level=cpu_level,
            ram_level=ram_level,
            disk_level=disk_level,
            overall_level=overall_level,
            throttle_action=throttle_action,
            is_throttled=is_throttled,
            throttle_factor=throttle_factor,
            issues=issues,
            recommendations=recommendations,
            cpu_percent=snapshot.cpu_percent,
            memory_percent=snapshot.memory_percent,
            disk_percent=snapshot.disk_percent
        )

    def get_trend(self, resource: str = "cpu") -> ResourceTrend:
        """
        Get trend analysis for a resource.

        Args:
            resource: "cpu", "ram", or "disk"

        Returns:
            ResourceTrend with analysis
        """
        with self._check_lock:
            history = list(self._history)

        if not history:
            return ResourceTrend(
                resource=resource,
                current=0.0,
                avg_5min=0.0,
                avg_15min=0.0,
                trend="unknown",
                prediction_10min=0.0
            )

        # Get values based on resource type
        if resource == "cpu":
            values = [s.cpu_percent for s in history]
        elif resource == "ram":
            values = [s.memory_percent for s in history]
        elif resource == "disk":
            values = [s.disk_percent for s in history]
        else:
            values = [0.0]

        current = values[-1] if values else 0.0

        # Calculate averages
        # Assuming 5-second intervals
        samples_5min = 60  # 5 minutes / 5 seconds
        samples_15min = 180

        avg_5min = sum(values[-samples_5min:]) / len(values[-samples_5min:]) if values else 0.0
        avg_15min = sum(values[-samples_15min:]) / len(values[-samples_15min:]) if values else 0.0

        # Determine trend
        if len(values) >= 10:
            recent = sum(values[-5:]) / 5
            older = sum(values[-10:-5]) / 5
            diff = recent - older

            if diff > 5:
                trend = "rising"
            elif diff < -5:
                trend = "falling"
            else:
                trend = "stable"
        else:
            trend = "unknown"

        # Simple linear prediction
        if len(values) >= 10 and trend != "unknown":
            slope = (values[-1] - values[-10]) / 10
            prediction = current + (slope * 120)  # 10 min = 120 samples at 5s
            prediction = max(0, min(100, prediction))
        else:
            prediction = current

        return ResourceTrend(
            resource=resource,
            current=round(current, 2),
            avg_5min=round(avg_5min, 2),
            avg_15min=round(avg_15min, 2),
            trend=trend,
            prediction_10min=round(prediction, 2)
        )

    def should_throttle(self) -> bool:
        """Check if operations should be throttled."""
        status = self.get_status()
        return status.is_throttled

    def get_throttle_factor(self) -> float:
        """Get current throttle factor (1.0 = normal, >1.0 = throttled)."""
        with self._check_lock:
            return self._throttle_factor

    def get_throttled_delay(self, base_delay: float) -> float:
        """
        Get delay adjusted for current throttle level.

        Args:
            base_delay: Normal delay in seconds

        Returns:
            Adjusted delay
        """
        return base_delay * self.get_throttle_factor()

    def is_safe_to_start_task(self) -> Tuple[bool, str]:
        """
        Check if it's safe to start a new task.

        Returns:
            Tuple of (is_safe, reason)
        """
        status = self.get_status()

        if status.overall_level == ResourceLevel.CRITICAL:
            return False, "System resources critical"

        if status.overall_level == ResourceLevel.THROTTLE:
            return False, "System throttled - wait for resources"

        if status.memory_percent > 85:
            return False, f"Memory too high ({status.memory_percent}%)"

        return True, "OK"

    def register_throttle_callback(self, callback: Callable[[ThrottleAction, float], None]):
        """Register a callback for throttle events."""
        self._throttle_callbacks.append(callback)

    def add_throttle_callback(self, callback: Callable[[ThrottleAction, float], None]):
        """
        Add a callback for throttle events.

        Alias for register_throttle_callback.

        Args:
            callback: Function called with (ThrottleAction, throttle_factor)
        """
        self.register_throttle_callback(callback)

    def check_resources(self) -> ResourceStatus:
        """
        Check current resource status.

        Alias for get_status.

        Returns:
            ResourceStatus with levels and actions
        """
        return self.get_status()

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of resource status."""
        status = self.get_status()
        cpu_trend = self.get_trend("cpu")
        ram_trend = self.get_trend("ram")

        snapshot = self._history[-1] if self._history else None

        return {
            "timestamp": datetime.now().isoformat(),
            "overall_level": status.overall_level.value,
            "is_throttled": status.is_throttled,
            "throttle_factor": status.throttle_factor,
            "cpu": {
                "percent": snapshot.cpu_percent if snapshot else 0,
                "level": status.cpu_level.value,
                "trend": cpu_trend.trend,
                "cores": snapshot.cpu_count if snapshot else 0
            },
            "ram": {
                "percent": snapshot.memory_percent if snapshot else 0,
                "used_gb": snapshot.memory_used_gb if snapshot else 0,
                "total_gb": snapshot.memory_total_gb if snapshot else 0,
                "level": status.ram_level.value,
                "trend": ram_trend.trend
            },
            "disk": {
                "percent": snapshot.disk_percent if snapshot else 0,
                "free_gb": snapshot.disk_free_gb if snapshot else 0,
                "level": status.disk_level.value
            },
            "issues": status.issues,
            "recommendations": status.recommendations
        }


# ==============================================================================
# SINGLETON ACCESSOR
# ==============================================================================

_resource_guard: Optional[ResourceGuard] = None


def get_resource_guard() -> ResourceGuard:
    """Get the singleton resource guard."""
    global _resource_guard
    if _resource_guard is None:
        _resource_guard = ResourceGuard()
    return _resource_guard


# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def check_resources() -> Dict[str, Any]:
    """Quick check of system resources."""
    return get_resource_guard().get_summary()


def is_system_healthy() -> bool:
    """Check if system resources are healthy."""
    status = get_resource_guard().get_status()
    return status.overall_level in [ResourceLevel.NORMAL, ResourceLevel.WARNING]


def get_throttle_delay(base_delay: float) -> float:
    """Get throttled delay for operations."""
    return get_resource_guard().get_throttled_delay(base_delay)


# ==============================================================================
# TEST / DEMO
# ==============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Resource Guard - Test")
    print("=" * 60)

    if not PSUTIL_AVAILABLE:
        print("\n[ERROR] psutil not installed. Run: pip install psutil")
        sys.exit(1)

    guard = get_resource_guard()

    # Get snapshot
    print("\n1. Resource Snapshot:")
    snapshot = guard.get_snapshot()
    print(f"   CPU: {snapshot.cpu_percent}% ({snapshot.cpu_count} cores)")
    print(f"   RAM: {snapshot.memory_percent}% ({snapshot.memory_used_gb:.1f}/{snapshot.memory_total_gb:.1f} GB)")
    print(f"   Disk: {snapshot.disk_percent}% ({snapshot.disk_free_gb:.1f} GB free)")

    # Get status
    print("\n2. Resource Status:")
    status = guard.get_status()
    print(f"   Overall Level: {status.overall_level.value}")
    print(f"   CPU Level: {status.cpu_level.value}")
    print(f"   RAM Level: {status.ram_level.value}")
    print(f"   Disk Level: {status.disk_level.value}")
    print(f"   Throttled: {status.is_throttled}")
    print(f"   Throttle Factor: {status.throttle_factor}x")

    # Get trends (need some history first)
    print("\n3. Building history for trend analysis...")
    for i in range(5):
        guard.get_snapshot()
        time.sleep(0.5)

    cpu_trend = guard.get_trend("cpu")
    print(f"   CPU Trend: {cpu_trend.trend}")
    print(f"   CPU Current: {cpu_trend.current}%")
    print(f"   CPU Prediction (10min): {cpu_trend.prediction_10min}%")

    # Check safety
    print("\n4. Task Safety Check:")
    is_safe, reason = guard.is_safe_to_start_task()
    print(f"   Safe to start task: {is_safe}")
    print(f"   Reason: {reason}")

    # Summary
    print("\n5. Resource Summary:")
    summary = guard.get_summary()
    print(f"   Overall: {summary['overall_level']}")
    print(f"   Issues: {summary['issues'] or 'None'}")

    print("\n" + "=" * 60)
    print("Resource Guard tests completed!")
    print("=" * 60)
