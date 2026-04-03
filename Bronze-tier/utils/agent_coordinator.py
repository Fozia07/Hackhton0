#!/usr/bin/env python3
"""
Platinum Tier - Agent Coordinator
Manages coordination between Cloud and Local agents.

Handles:
- Work-zone ownership and permissions
- Signal passing between agents
- Dashboard update delegation
- Agent status monitoring
"""

import os
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any
from enum import Enum
from dataclasses import dataclass, asdict

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class WorkZone(Enum):
    """Work zones that can be owned by agents."""
    EMAIL_TRIAGE = "email_triage"
    EMAIL_SEND = "email_send"
    SOCIAL_DRAFT = "social_draft"
    SOCIAL_POST = "social_post"
    APPROVALS = "approvals"
    WHATSAPP = "whatsapp"
    PAYMENTS = "payments"
    ODOO_READ = "odoo_read"
    ODOO_WRITE = "odoo_write"
    ACCOUNTING = "accounting"
    CEO_BRIEFING = "ceo_briefing"


class Permission(Enum):
    """Permissions for agent actions."""
    DRAFT_ONLY = "draft_only"
    FULL_ACCESS = "full_access"
    READ_ONLY = "read_only"
    NO_ACCESS = "no_access"


@dataclass
class AgentConfig:
    """Configuration for an agent."""
    agent_id: str
    agent_type: str  # 'cloud' or 'local'
    is_active: bool
    owned_zones: List[str]
    draft_only_zones: List[str]
    read_only_zones: List[str]
    last_heartbeat: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'AgentConfig':
        """Create from dict, only using fields defined in dataclass."""
        valid_fields = {'agent_id', 'agent_type', 'is_active', 'owned_zones',
                        'draft_only_zones', 'read_only_zones', 'last_heartbeat'}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}

        # Set defaults for missing fields
        filtered_data.setdefault('is_active', True)
        filtered_data.setdefault('draft_only_zones', [])
        filtered_data.setdefault('read_only_zones', [])
        filtered_data.setdefault('last_heartbeat', '')

        return cls(**filtered_data)


@dataclass
class Signal:
    """Signal passed between agents."""
    signal_id: str
    signal_type: str
    from_agent: str
    to_agent: str
    payload: Dict
    created_at: str
    expires_at: str
    acknowledged: bool = False

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'Signal':
        return cls(**data)


class AgentCoordinator:
    """
    Coordinates activities between Cloud and Local agents.

    Responsibilities:
    - Load and validate agent configuration
    - Check work-zone permissions
    - Send and receive signals
    - Write updates for Dashboard (Cloud -> Local)
    - Monitor agent status
    """

    def __init__(self, vault_path: str, agent_type: str = "local"):
        """
        Initialize AgentCoordinator.

        Args:
            vault_path: Path to AI_Employee_Vault
            agent_type: 'cloud' or 'local'
        """
        self.vault_path = Path(vault_path)
        self.agent_type = agent_type
        self.base_dir = self.vault_path.parent

        # Paths
        self.config_path = self.base_dir / "config"
        self.updates_path = self.vault_path / "Updates"
        self.signals_path = self.vault_path / "Signals"

        # Ensure directories exist
        self._ensure_directories()

        # Load configurations
        self.agent_config = self._load_agent_config()
        self.work_zones = self._load_work_zones()

    def _ensure_directories(self):
        """Ensure required directories exist."""
        for path in [self.config_path, self.updates_path, self.signals_path]:
            path.mkdir(parents=True, exist_ok=True)

    def _load_agent_config(self) -> AgentConfig:
        """Load agent configuration."""
        config_file = self.config_path / "agent_config.json"

        if config_file.exists():
            data = json.loads(config_file.read_text())
            return AgentConfig.from_dict(data)

        # Default configuration
        if self.agent_type == "cloud":
            return AgentConfig(
                agent_id="cloud",
                agent_type="cloud",
                is_active=True,
                owned_zones=["email_triage", "social_draft"],
                draft_only_zones=["email_send", "social_post"],
                read_only_zones=["odoo_read", "accounting"]
            )
        else:
            return AgentConfig(
                agent_id="local",
                agent_type="local",
                is_active=True,
                owned_zones=["email_send", "social_post", "approvals",
                             "whatsapp", "payments", "odoo_write", "accounting",
                             "ceo_briefing"],
                draft_only_zones=[],
                read_only_zones=["email_triage", "social_draft"]
            )

    def _load_work_zones(self) -> Dict:
        """Load work zone definitions."""
        zones_file = self.config_path / "work_zones.json"

        if zones_file.exists():
            return json.loads(zones_file.read_text())

        # Default work zones
        return {
            "zones": {
                "email_triage": {
                    "description": "Email reading and draft replies",
                    "cloud_permission": "full_access",
                    "local_permission": "read_only"
                },
                "email_send": {
                    "description": "Actually sending emails",
                    "cloud_permission": "draft_only",
                    "local_permission": "full_access"
                },
                "social_draft": {
                    "description": "Creating social media post drafts",
                    "cloud_permission": "full_access",
                    "local_permission": "read_only"
                },
                "social_post": {
                    "description": "Publishing to social media",
                    "cloud_permission": "no_access",
                    "local_permission": "full_access"
                },
                "approvals": {
                    "description": "Approving or rejecting tasks",
                    "cloud_permission": "no_access",
                    "local_permission": "full_access"
                },
                "whatsapp": {
                    "description": "WhatsApp messaging",
                    "cloud_permission": "no_access",
                    "local_permission": "full_access"
                },
                "payments": {
                    "description": "Payment processing",
                    "cloud_permission": "no_access",
                    "local_permission": "full_access"
                },
                "odoo_read": {
                    "description": "Reading from Odoo",
                    "cloud_permission": "full_access",
                    "local_permission": "full_access"
                },
                "odoo_write": {
                    "description": "Writing to Odoo",
                    "cloud_permission": "no_access",
                    "local_permission": "full_access"
                }
            }
        }

    def can_access_zone(self, zone: str) -> Permission:
        """
        Check if this agent can access a work zone.

        Args:
            zone: Work zone name

        Returns:
            Permission level for the zone
        """
        if zone in self.agent_config.owned_zones:
            return Permission.FULL_ACCESS
        elif zone in self.agent_config.draft_only_zones:
            return Permission.DRAFT_ONLY
        elif zone in self.agent_config.read_only_zones:
            return Permission.READ_ONLY
        else:
            return Permission.NO_ACCESS

    def is_zone_owner(self, zone: str) -> bool:
        """Check if this agent owns a zone."""
        return zone in self.agent_config.owned_zones

    def get_my_zones(self) -> List[str]:
        """Get list of zones owned by this agent."""
        return self.agent_config.owned_zones

    # ==================== SIGNALS ====================

    def send_signal(self, signal_type: str, to_agent: str,
                    payload: Dict, ttl_seconds: int = 3600) -> Signal:
        """
        Send a signal to another agent.

        Args:
            signal_type: Type of signal (e.g., 'task_ready', 'approval_needed')
            to_agent: Target agent ('cloud' or 'local')
            payload: Signal data
            ttl_seconds: Time-to-live in seconds

        Returns:
            Created Signal object
        """
        now = datetime.now()
        signal_id = f"{signal_type}_{now.strftime('%Y%m%d_%H%M%S_%f')}"

        signal = Signal(
            signal_id=signal_id,
            signal_type=signal_type,
            from_agent=self.agent_type,
            to_agent=to_agent,
            payload=payload,
            created_at=now.isoformat(),
            expires_at=(datetime.fromtimestamp(
                now.timestamp() + ttl_seconds
            )).isoformat(),
            acknowledged=False
        )

        # Write signal file
        signal_file = self.signals_path / f"{signal_id}.json"
        signal_file.write_text(json.dumps(signal.to_dict(), indent=2))

        return signal

    def get_pending_signals(self) -> List[Signal]:
        """
        Get signals intended for this agent.

        Returns:
            List of pending signals
        """
        signals = []
        now = datetime.now()

        for signal_file in self.signals_path.glob("*.json"):
            try:
                data = json.loads(signal_file.read_text())
                signal = Signal.from_dict(data)

                # Check if signal is for this agent and not expired
                if signal.to_agent == self.agent_type and not signal.acknowledged:
                    expires = datetime.fromisoformat(signal.expires_at)
                    if now < expires:
                        signals.append(signal)
            except Exception:
                continue

        return signals

    def acknowledge_signal(self, signal_id: str) -> bool:
        """
        Acknowledge a signal (mark as processed).

        Args:
            signal_id: Signal ID to acknowledge

        Returns:
            True if acknowledged successfully
        """
        signal_file = self.signals_path / f"{signal_id}.json"

        if not signal_file.exists():
            return False

        try:
            data = json.loads(signal_file.read_text())
            data["acknowledged"] = True
            data["acknowledged_at"] = datetime.now().isoformat()
            signal_file.write_text(json.dumps(data, indent=2))
            return True
        except Exception:
            return False

    def cleanup_expired_signals(self):
        """Remove expired signals."""
        now = datetime.now()

        for signal_file in self.signals_path.glob("*.json"):
            try:
                data = json.loads(signal_file.read_text())
                expires = datetime.fromisoformat(data.get("expires_at", ""))
                if now > expires:
                    signal_file.unlink()
            except Exception:
                continue

    # ==================== UPDATES ====================

    def write_update(self, update_type: str, data: Dict):
        """
        Write an update for the other agent (Cloud -> Local primarily).

        Args:
            update_type: Type of update ('dashboard', 'task_complete', etc.)
            data: Update data
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        update_file = self.updates_path / f"{update_type}_{timestamp}.json"

        update = {
            "type": update_type,
            "from_agent": self.agent_type,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }

        update_file.write_text(json.dumps(update, indent=2))

    def get_pending_updates(self) -> List[Dict]:
        """
        Get updates from other agent.

        Returns:
            List of update dictionaries
        """
        updates = []

        for update_file in sorted(self.updates_path.glob("*.json")):
            try:
                data = json.loads(update_file.read_text())
                if data.get("from_agent") != self.agent_type:
                    data["_file"] = str(update_file)
                    updates.append(data)
            except Exception:
                continue

        return updates

    def mark_update_processed(self, update_file: str):
        """
        Mark an update as processed by moving to processed folder.

        Args:
            update_file: Path to update file
        """
        file_path = Path(update_file)
        if file_path.exists():
            processed_dir = self.updates_path / "processed"
            processed_dir.mkdir(exist_ok=True)
            file_path.rename(processed_dir / file_path.name)

    def write_dashboard_update(self, metrics: Dict):
        """
        Write dashboard update (used by Cloud agent).

        Local agent will merge this into Dashboard.md.

        Args:
            metrics: Dashboard metrics to update
        """
        self.write_update("dashboard", {
            "metrics": metrics,
            "source": self.agent_type
        })

    # ==================== HEARTBEAT ====================

    def update_heartbeat(self):
        """Update agent heartbeat for health monitoring."""
        heartbeat_file = self.signals_path / f"heartbeat_{self.agent_type}.json"

        heartbeat = {
            "agent_type": self.agent_type,
            "agent_id": self.agent_config.agent_id,
            "timestamp": datetime.now().isoformat(),
            "status": "active"
        }

        heartbeat_file.write_text(json.dumps(heartbeat, indent=2))

    def get_other_agent_status(self) -> Optional[Dict]:
        """
        Check status of the other agent.

        Returns:
            Heartbeat data if available, None otherwise
        """
        other = "cloud" if self.agent_type == "local" else "local"
        heartbeat_file = self.signals_path / f"heartbeat_{other}.json"

        if not heartbeat_file.exists():
            return None

        try:
            data = json.loads(heartbeat_file.read_text())
            # Check if heartbeat is recent (within 5 minutes)
            timestamp = datetime.fromisoformat(data.get("timestamp", ""))
            age_seconds = (datetime.now() - timestamp).total_seconds()
            data["age_seconds"] = age_seconds
            data["is_recent"] = age_seconds < 300
            return data
        except Exception:
            return None

    def get_coordination_status(self) -> Dict:
        """
        Get overall coordination status.

        Returns:
            Status dictionary
        """
        other_status = self.get_other_agent_status()
        pending_signals = self.get_pending_signals()
        pending_updates = self.get_pending_updates()

        return {
            "agent_type": self.agent_type,
            "agent_id": self.agent_config.agent_id,
            "is_active": self.agent_config.is_active,
            "owned_zones": self.agent_config.owned_zones,
            "other_agent": other_status,
            "pending_signals": len(pending_signals),
            "pending_updates": len(pending_updates),
            "timestamp": datetime.now().isoformat()
        }


def get_coordinator(agent_type: str = None) -> AgentCoordinator:
    """
    Factory function to get AgentCoordinator instance.

    Args:
        agent_type: 'cloud' or 'local'. If None, reads from config.

    Returns:
        AgentCoordinator instance
    """
    base_dir = Path(__file__).parent.parent
    # Support Docker environment variable
    vault_path = Path(os.environ.get("VAULT_PATH", base_dir / "AI_Employee_Vault"))

    if agent_type is None:
        config_path = base_dir / "config" / "agent_config.json"
        if config_path.exists():
            config = json.loads(config_path.read_text())
            agent_type = config.get("agent_type", "local")
        else:
            agent_type = "local"

    return AgentCoordinator(str(vault_path), agent_type)


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Agent Coordinator CLI")
    parser.add_argument("--agent", choices=["cloud", "local"], default="local")
    parser.add_argument("--action", choices=["status", "signal", "updates", "heartbeat"],
                        default="status")
    parser.add_argument("--signal-type", help="Type of signal to send")
    parser.add_argument("--to", choices=["cloud", "local"], help="Target agent")
    parser.add_argument("--payload", help="JSON payload for signal")

    args = parser.parse_args()

    coordinator = get_coordinator(args.agent)

    if args.action == "status":
        status = coordinator.get_coordination_status()
        print(json.dumps(status, indent=2))

    elif args.action == "signal":
        if args.signal_type and args.to:
            payload = json.loads(args.payload) if args.payload else {}
            signal = coordinator.send_signal(args.signal_type, args.to, payload)
            print(f"Signal sent: {signal.signal_id}")
        else:
            # List pending signals
            signals = coordinator.get_pending_signals()
            print(f"Pending signals: {len(signals)}")
            for s in signals:
                print(f"  - {s.signal_type} from {s.from_agent}")

    elif args.action == "updates":
        updates = coordinator.get_pending_updates()
        print(f"Pending updates: {len(updates)}")
        for u in updates:
            print(f"  - {u.get('type')} from {u.get('from_agent')}")

    elif args.action == "heartbeat":
        coordinator.update_heartbeat()
        print("Heartbeat updated")
