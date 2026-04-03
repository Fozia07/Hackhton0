"""
Incident Logger - Structured Incident Tracking
Gold Tier Component - Watchdog System

Tracks and logs all watchdog incidents:
- Process crashes
- Process restarts
- Resource alerts
- Safe mode events
- Recovery actions

Features:
- Structured JSON logging
- Integration with audit_logger
- Incident history management
- Statistics and reporting
"""

import os
import sys
import json
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import uuid

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.audit_logger import get_audit_logger, ActionType, ResultStatus


# ==============================================================================
# CONFIGURATION
# ==============================================================================

class IncidentConfig:
    """Configuration for incident logging."""

    BASE_DIR = Path(__file__).parent.parent
    VAULT_DIR = BASE_DIR / "AI_Employee_Vault"
    WATCHDOG_DIR = VAULT_DIR / "Watchdog"

    INCIDENTS_FILE = WATCHDOG_DIR / "incidents.json"
    RESTARTS_FILE = WATCHDOG_DIR / "restarts.json"
    METRICS_FILE = WATCHDOG_DIR / "metrics.json"

    MAX_INCIDENTS = 1000  # Max incidents to keep
    MAX_RESTARTS = 500    # Max restart records to keep


# ==============================================================================
# ENUMERATIONS
# ==============================================================================

class IncidentType(Enum):
    """Types of incidents."""
    PROCESS_CRASH = "process_crash"
    PROCESS_HUNG = "process_hung"
    PROCESS_ZOMBIE = "process_zombie"
    PROCESS_RESTART = "process_restart"
    PROCESS_KILL = "process_kill"
    HEARTBEAT_STALE = "heartbeat_stale"
    HEARTBEAT_RECOVERED = "heartbeat_recovered"
    RESOURCE_WARNING = "resource_warning"
    RESOURCE_THROTTLE = "resource_throttle"
    RESOURCE_CRITICAL = "resource_critical"
    RESOURCE_EMERGENCY = "resource_emergency"
    SAFE_MODE_ENTER = "safe_mode_enter"
    SAFE_MODE_EXIT = "safe_mode_exit"
    WATCHDOG_START = "watchdog_start"
    WATCHDOG_STOP = "watchdog_stop"
    WATCHDOG_ERROR = "watchdog_error"
    RECOVERY_SUCCESS = "recovery_success"
    RECOVERY_FAILED = "recovery_failed"
    CIRCUIT_BREAKER_OPEN = "circuit_breaker_open"
    CIRCUIT_BREAKER_CLOSE = "circuit_breaker_close"


class IncidentSeverity(Enum):
    """Incident severity levels."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentResult(Enum):
    """Incident action result."""
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"
    SKIPPED = "skipped"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class Incident:
    """Individual incident record."""
    id: str
    timestamp: str
    type: str
    severity: str
    process: Optional[str] = None
    pid: Optional[int] = None
    reason: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    action: Optional[str] = None
    result: str = "pending"
    new_pid: Optional[int] = None
    duration_ms: Optional[float] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Incident':
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class RestartRecord:
    """Record of a process restart."""
    id: str
    timestamp: str
    process: str
    old_pid: Optional[int]
    new_pid: Optional[int]
    reason: str
    success: bool
    attempt: int
    duration_ms: float
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class IncidentMetrics:
    """Aggregated incident metrics."""
    total_incidents: int = 0
    incidents_24h: int = 0
    incidents_1h: int = 0
    restarts_24h: int = 0
    restarts_1h: int = 0
    crashes_24h: int = 0
    safe_mode_count: int = 0
    last_incident: Optional[str] = None
    by_type: Dict[str, int] = field(default_factory=dict)
    by_severity: Dict[str, int] = field(default_factory=dict)
    by_process: Dict[str, int] = field(default_factory=dict)


# ==============================================================================
# INCIDENT LOGGER
# ==============================================================================

class IncidentLogger:
    """
    Logs and tracks watchdog incidents.

    Thread-safe implementation with file persistence.
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
        """Initialize incident logger."""
        if self._initialized:
            return

        self._initialized = True
        self._file_lock = threading.Lock()
        self._incidents: List[Incident] = []
        self._restarts: List[RestartRecord] = []
        self._audit_logger = get_audit_logger()

        # Ensure directory exists
        IncidentConfig.WATCHDOG_DIR.mkdir(parents=True, exist_ok=True)

        # Load existing data
        self._load_data()

    def _load_data(self):
        """Load existing incidents and restarts."""
        try:
            if IncidentConfig.INCIDENTS_FILE.exists():
                with open(IncidentConfig.INCIDENTS_FILE, 'r') as f:
                    data = json.load(f)
                    self._incidents = [
                        Incident.from_dict(inc) for inc in data.get('incidents', [])
                    ]
        except Exception:
            self._incidents = []

        try:
            if IncidentConfig.RESTARTS_FILE.exists():
                with open(IncidentConfig.RESTARTS_FILE, 'r') as f:
                    data = json.load(f)
                    self._restarts = [
                        RestartRecord(**r) for r in data.get('restarts', [])
                    ]
        except Exception:
            self._restarts = []

    def _save_incidents(self):
        """Save incidents to file."""
        try:
            data = {
                'updated': datetime.now().isoformat(),
                'count': len(self._incidents),
                'incidents': [inc.to_dict() for inc in self._incidents]
            }

            temp_file = IncidentConfig.INCIDENTS_FILE.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2)
            temp_file.replace(IncidentConfig.INCIDENTS_FILE)

        except Exception:
            pass

    def _save_restarts(self):
        """Save restart records to file."""
        try:
            data = {
                'updated': datetime.now().isoformat(),
                'count': len(self._restarts),
                'restarts': [r.to_dict() for r in self._restarts]
            }

            temp_file = IncidentConfig.RESTARTS_FILE.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2)
            temp_file.replace(IncidentConfig.RESTARTS_FILE)

        except Exception:
            pass

    def _generate_id(self) -> str:
        """Generate unique incident ID."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique = uuid.uuid4().hex[:6].upper()
        return f"INC_{timestamp}_{unique}"

    def log_incident(
        self,
        incident_type: IncidentType,
        severity: IncidentSeverity,
        process: Optional[str] = None,
        pid: Optional[int] = None,
        reason: str = "",
        details: Optional[Dict[str, Any]] = None,
        action: Optional[str] = None,
        result: IncidentResult = IncidentResult.PENDING,
        new_pid: Optional[int] = None,
        duration_ms: Optional[float] = None,
        error: Optional[str] = None
    ) -> Incident:
        """
        Log a new incident.

        Args:
            incident_type: Type of incident
            severity: Severity level
            process: Process name (if applicable)
            pid: Process ID (if applicable)
            reason: Reason for the incident
            details: Additional details
            action: Action taken
            result: Result of action
            new_pid: New PID after restart
            duration_ms: Duration of action
            error: Error message (if any)

        Returns:
            The created Incident
        """
        incident = Incident(
            id=self._generate_id(),
            timestamp=datetime.now().isoformat(),
            type=incident_type.value,
            severity=severity.value,
            process=process,
            pid=pid,
            reason=reason,
            details=details or {},
            action=action,
            result=result.value,
            new_pid=new_pid,
            duration_ms=duration_ms,
            error=error
        )

        with self._file_lock:
            self._incidents.append(incident)

            # Trim if needed
            if len(self._incidents) > IncidentConfig.MAX_INCIDENTS:
                self._incidents = self._incidents[-IncidentConfig.MAX_INCIDENTS:]

            self._save_incidents()

        # Also log to audit logger
        self._log_to_audit(incident)

        return incident

    def _log_to_audit(self, incident: Incident):
        """Log incident to audit system."""
        try:
            # Map incident type to action type
            action_map = {
                IncidentType.PROCESS_CRASH.value: ActionType.ERROR_OCCURRED,
                IncidentType.PROCESS_RESTART.value: ActionType.RECOVERY_ATTEMPTED,
                IncidentType.SAFE_MODE_ENTER.value: ActionType.WARNING_RAISED,
                IncidentType.RESOURCE_CRITICAL.value: ActionType.WARNING_RAISED,
            }

            action_type = action_map.get(incident.type, ActionType.WARNING_RAISED)

            # Map result
            result_map = {
                'success': ResultStatus.SUCCESS,
                'failed': ResultStatus.FAILURE,
                'pending': ResultStatus.PENDING,
                'skipped': ResultStatus.SKIPPED
            }
            result_status = result_map.get(incident.result, ResultStatus.PENDING)

            self._audit_logger.log(
                action_type=action_type,
                actor="watchdog",
                target=incident.process or "system",
                parameters={
                    'incident_id': incident.id,
                    'incident_type': incident.type,
                    'severity': incident.severity,
                    'reason': incident.reason,
                    'pid': incident.pid,
                    **incident.details
                },
                result=result_status,
                error=incident.error
            )

        except Exception:
            pass  # Don't fail if audit logging fails

    def log_restart(
        self,
        process: str,
        old_pid: Optional[int],
        new_pid: Optional[int],
        reason: str,
        success: bool,
        attempt: int,
        duration_ms: float,
        error: Optional[str] = None
    ) -> RestartRecord:
        """
        Log a process restart.

        Args:
            process: Process name
            old_pid: Previous PID
            new_pid: New PID
            reason: Reason for restart
            success: Whether restart succeeded
            attempt: Attempt number
            duration_ms: Time taken
            error: Error message if failed

        Returns:
            RestartRecord
        """
        record = RestartRecord(
            id=self._generate_id().replace('INC_', 'RST_'),
            timestamp=datetime.now().isoformat(),
            process=process,
            old_pid=old_pid,
            new_pid=new_pid,
            reason=reason,
            success=success,
            attempt=attempt,
            duration_ms=duration_ms,
            error=error
        )

        with self._file_lock:
            self._restarts.append(record)

            # Trim if needed
            if len(self._restarts) > IncidentConfig.MAX_RESTARTS:
                self._restarts = self._restarts[-IncidentConfig.MAX_RESTARTS:]

            self._save_restarts()

        # Log incident as well
        self.log_incident(
            incident_type=IncidentType.PROCESS_RESTART,
            severity=IncidentSeverity.HIGH if not success else IncidentSeverity.MEDIUM,
            process=process,
            pid=old_pid,
            reason=reason,
            details={'attempt': attempt},
            action='restart',
            result=IncidentResult.SUCCESS if success else IncidentResult.FAILED,
            new_pid=new_pid,
            duration_ms=duration_ms,
            error=error
        )

        return record

    def get_incidents(
        self,
        hours: Optional[int] = None,
        since: Optional[datetime] = None,
        incident_type: Optional[IncidentType] = None,
        severity: Optional[IncidentSeverity] = None,
        process: Optional[str] = None,
        limit: int = 100
    ) -> List[Incident]:
        """
        Get incidents with optional filtering.

        Args:
            hours: Only incidents within last N hours
            since: Only incidents since this datetime
            incident_type: Filter by type
            severity: Filter by severity
            process: Filter by process
            limit: Maximum incidents to return

        Returns:
            List of matching incidents
        """
        with self._file_lock:
            incidents = list(self._incidents)

        # Filter by time (since takes precedence over hours)
        if since:
            incidents = [
                inc for inc in incidents
                if datetime.fromisoformat(inc.timestamp) >= since
            ]
        elif hours:
            cutoff = datetime.now() - timedelta(hours=hours)
            incidents = [
                inc for inc in incidents
                if datetime.fromisoformat(inc.timestamp) >= cutoff
            ]

        # Filter by type
        if incident_type:
            incidents = [
                inc for inc in incidents
                if inc.type == incident_type.value
            ]

        # Filter by severity
        if severity:
            incidents = [
                inc for inc in incidents
                if inc.severity == severity.value
            ]

        # Filter by process
        if process:
            incidents = [
                inc for inc in incidents
                if inc.process == process
            ]

        # Sort by timestamp descending and limit
        incidents.sort(key=lambda x: x.timestamp, reverse=True)
        return incidents[:limit]

    def get_restarts(
        self,
        hours: Optional[int] = None,
        process: Optional[str] = None,
        limit: int = 100
    ) -> List[RestartRecord]:
        """Get restart records with optional filtering."""
        with self._file_lock:
            restarts = list(self._restarts)

        if hours:
            cutoff = datetime.now() - timedelta(hours=hours)
            restarts = [
                r for r in restarts
                if datetime.fromisoformat(r.timestamp) >= cutoff
            ]

        if process:
            restarts = [r for r in restarts if r.process == process]

        restarts.sort(key=lambda x: x.timestamp, reverse=True)
        return restarts[:limit]

    def get_metrics(self) -> IncidentMetrics:
        """Get aggregated incident metrics."""
        now = datetime.now()
        cutoff_24h = now - timedelta(hours=24)
        cutoff_1h = now - timedelta(hours=1)

        with self._file_lock:
            incidents = list(self._incidents)
            restarts = list(self._restarts)

        metrics = IncidentMetrics(
            total_incidents=len(incidents)
        )

        # Count by time periods
        for inc in incidents:
            try:
                ts = datetime.fromisoformat(inc.timestamp)

                if ts >= cutoff_24h:
                    metrics.incidents_24h += 1

                    if inc.type == IncidentType.PROCESS_CRASH.value:
                        metrics.crashes_24h += 1

                    if inc.type == IncidentType.SAFE_MODE_ENTER.value:
                        metrics.safe_mode_count += 1

                if ts >= cutoff_1h:
                    metrics.incidents_1h += 1

                # Count by type
                metrics.by_type[inc.type] = metrics.by_type.get(inc.type, 0) + 1

                # Count by severity
                metrics.by_severity[inc.severity] = metrics.by_severity.get(inc.severity, 0) + 1

                # Count by process
                if inc.process:
                    metrics.by_process[inc.process] = metrics.by_process.get(inc.process, 0) + 1

            except Exception:
                continue

        # Count restarts
        for r in restarts:
            try:
                ts = datetime.fromisoformat(r.timestamp)
                if ts >= cutoff_24h:
                    metrics.restarts_24h += 1
                if ts >= cutoff_1h:
                    metrics.restarts_1h += 1
            except Exception:
                continue

        # Last incident
        if incidents:
            metrics.last_incident = incidents[-1].timestamp

        return metrics

    def should_enter_safe_mode(self) -> Tuple[bool, str]:
        """
        Check if safe mode should be triggered based on incidents.

        Returns:
            Tuple of (should_enter, reason)
        """
        now = datetime.now()
        cutoff_10min = now - timedelta(minutes=10)
        cutoff_30min = now - timedelta(minutes=30)

        with self._file_lock:
            incidents = list(self._incidents)
            restarts = list(self._restarts)

        # Count crashes in last 10 minutes
        crashes_10min = sum(
            1 for inc in incidents
            if inc.type == IncidentType.PROCESS_CRASH.value
            and datetime.fromisoformat(inc.timestamp) >= cutoff_10min
        )

        if crashes_10min >= 3:
            return True, f"Too many crashes ({crashes_10min} in 10 minutes)"

        # Count restarts in last 30 minutes
        restarts_30min = sum(
            1 for r in restarts
            if datetime.fromisoformat(r.timestamp) >= cutoff_30min
        )

        if restarts_30min >= 5:
            return True, f"Too many restarts ({restarts_30min} in 30 minutes)"

        return False, ""

    def save_metrics(self):
        """Save current metrics to file."""
        try:
            metrics = self.get_metrics()
            data = {
                'updated': datetime.now().isoformat(),
                'metrics': asdict(metrics)
            }

            with open(IncidentConfig.METRICS_FILE, 'w') as f:
                json.dump(data, f, indent=2)

        except Exception:
            pass


# ==============================================================================
# SINGLETON ACCESSOR
# ==============================================================================

_incident_logger: Optional[IncidentLogger] = None


def get_incident_logger() -> IncidentLogger:
    """Get the singleton incident logger."""
    global _incident_logger
    if _incident_logger is None:
        _incident_logger = IncidentLogger()
    return _incident_logger


# ==============================================================================
# CONVENIENCE FUNCTIONS
# ==============================================================================

def log_crash(process: str, pid: int, reason: str, error: Optional[str] = None):
    """Log a process crash."""
    return get_incident_logger().log_incident(
        incident_type=IncidentType.PROCESS_CRASH,
        severity=IncidentSeverity.HIGH,
        process=process,
        pid=pid,
        reason=reason,
        error=error
    )


def log_restart(process: str, old_pid: int, new_pid: int, reason: str,
                success: bool, attempt: int, duration_ms: float):
    """Log a process restart."""
    return get_incident_logger().log_restart(
        process=process,
        old_pid=old_pid,
        new_pid=new_pid,
        reason=reason,
        success=success,
        attempt=attempt,
        duration_ms=duration_ms
    )


def log_safe_mode_enter(reason: str):
    """Log safe mode entry."""
    return get_incident_logger().log_incident(
        incident_type=IncidentType.SAFE_MODE_ENTER,
        severity=IncidentSeverity.CRITICAL,
        reason=reason,
        action="enter_safe_mode",
        result=IncidentResult.SUCCESS
    )


def log_safe_mode_exit(reason: str):
    """Log safe mode exit."""
    return get_incident_logger().log_incident(
        incident_type=IncidentType.SAFE_MODE_EXIT,
        severity=IncidentSeverity.INFO,
        reason=reason,
        action="exit_safe_mode",
        result=IncidentResult.SUCCESS
    )


def log_incident(
    event: IncidentType,
    process_name: Optional[str] = None,
    reason: str = "",
    action: Optional[str] = None,
    result: IncidentResult = IncidentResult.PENDING,
    severity: IncidentSeverity = IncidentSeverity.MEDIUM,
    details: Optional[Dict[str, Any]] = None,
    pid: Optional[int] = None,
    new_pid: Optional[int] = None,
    duration_ms: Optional[float] = None,
    error: Optional[str] = None
):
    """
    Convenience function to log an incident.

    Args:
        event: Type of incident (IncidentType)
        process_name: Name of the process involved
        reason: Reason for the incident
        action: Action taken
        result: Result of action
        severity: Severity level (default: MEDIUM)
        details: Additional details dict
        pid: Process ID
        new_pid: New PID after restart
        duration_ms: Duration of action in ms
        error: Error message

    Returns:
        The created Incident
    """
    return get_incident_logger().log_incident(
        incident_type=event,
        severity=severity,
        process=process_name,
        pid=pid,
        reason=reason,
        details=details,
        action=action,
        result=result,
        new_pid=new_pid,
        duration_ms=duration_ms,
        error=error
    )


# ==============================================================================
# TEST / DEMO
# ==============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Incident Logger - Test")
    print("=" * 60)

    logger = get_incident_logger()

    # Log some test incidents
    print("\n1. Logging test incidents...")

    inc1 = logger.log_incident(
        incident_type=IncidentType.PROCESS_CRASH,
        severity=IncidentSeverity.HIGH,
        process="test_agent",
        pid=1234,
        reason="Simulated crash for testing",
        action="restart",
        result=IncidentResult.PENDING
    )
    print(f"   Logged: {inc1.id}")

    inc2 = logger.log_incident(
        incident_type=IncidentType.RESOURCE_WARNING,
        severity=IncidentSeverity.MEDIUM,
        reason="CPU usage elevated",
        details={'cpu_percent': 85.5},
        action="throttle",
        result=IncidentResult.SUCCESS
    )
    print(f"   Logged: {inc2.id}")

    # Log a restart
    print("\n2. Logging restart...")
    restart = logger.log_restart(
        process="test_agent",
        old_pid=1234,
        new_pid=5678,
        reason="crash recovery",
        success=True,
        attempt=1,
        duration_ms=1500.5
    )
    print(f"   Logged: {restart.id}")

    # Get metrics
    print("\n3. Getting metrics...")
    metrics = logger.get_metrics()
    print(f"   Total incidents: {metrics.total_incidents}")
    print(f"   Incidents (24h): {metrics.incidents_24h}")
    print(f"   Restarts (24h): {metrics.restarts_24h}")
    print(f"   By type: {metrics.by_type}")

    # Check safe mode trigger
    print("\n4. Safe mode check...")
    should_enter, reason = logger.should_enter_safe_mode()
    print(f"   Should enter safe mode: {should_enter}")
    if reason:
        print(f"   Reason: {reason}")

    # Save metrics
    print("\n5. Saving metrics...")
    logger.save_metrics()
    print("   Saved to metrics.json")

    print("\n" + "=" * 60)
    print("Incident Logger tests completed!")
    print("=" * 60)
