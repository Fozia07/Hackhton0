#!/usr/bin/env python3
"""
System Watchdog Daemon
======================

Enterprise-grade standalone watchdog daemon for the AI Employee platform.

Provides continuous monitoring, auto-recovery, and system health management.

Usage:
    python3 scripts/system_watchdog.py              # Normal mode
    python3 scripts/system_watchdog.py --debug      # Debug mode (verbose)
    python3 scripts/system_watchdog.py --dry-run    # Dry run (no restarts)
    python3 scripts/system_watchdog.py --once       # Single scan
    python3 scripts/system_watchdog.py --status     # Show status and exit
    python3 scripts/system_watchdog.py --safe-mode  # Enter safe mode
    python3 scripts/system_watchdog.py --exit-safe  # Exit safe mode

Author: AI Employee System
Version: 1.0.0
"""

import os
import sys
import json
import time
import signal
import argparse
import threading
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("WARNING: psutil not installed. Some features will be limited.")
    print("Install with: pip install psutil")

from utils.watchdog import (
    WatchdogController, WatchdogConfig, WatchdogState,
    SafeModeConfig, SafeModeReason, get_watchdog
)
from utils.heartbeat import HeartbeatWriter, HeartbeatManager
from utils.process_monitor import ProcessMonitor
from utils.resource_guard import ResourceGuard, ResourceLevel
from utils.incident_logger import IncidentLogger, log_incident, IncidentType, IncidentResult
from utils.auto_restart import AutoRestartEngine, ProcessConfig


# ANSI colors for terminal output
class Colors:
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"

    @classmethod
    def disable(cls):
        """Disable colors for non-TTY output."""
        cls.RESET = ""
        cls.RED = ""
        cls.GREEN = ""
        cls.YELLOW = ""
        cls.BLUE = ""
        cls.MAGENTA = ""
        cls.CYAN = ""
        cls.WHITE = ""
        cls.BOLD = ""


# Check if stdout is a TTY
if not sys.stdout.isatty():
    Colors.disable()


# Default monitored processes
MONITORED_PROCESSES = [
    {
        "name": "run_ai_employee",
        "command": [sys.executable, "scripts/run_ai_employee.py"],
        "critical": True,
        "priority": 1
    },
    {
        "name": "agent_executor",
        "command": [sys.executable, "-m", "agent_executor"],
        "critical": True,
        "priority": 1
    },
    {
        "name": "filesystem_watcher",
        "command": [sys.executable, "-c", "from filesystem_watcher import main; main()"],
        "critical": True,
        "priority": 2
    },
    {
        "name": "plan_creator",
        "command": [sys.executable, "scripts/plan_creator.py"],
        "critical": False,
        "priority": 3
    },
    {
        "name": "linkedin_poster",
        "command": [sys.executable, "scripts/linkedin_poster.py"],
        "critical": False,
        "priority": 4
    },
    {
        "name": "ceo_briefing_generator",
        "command": [sys.executable, "scripts/ceo_briefing_generator.py"],
        "critical": False,
        "priority": 3
    },
    {
        "name": "email_server",
        "command": [sys.executable, "mcp_servers/email_server.py"],
        "critical": False,
        "priority": 4
    }
]


class SystemWatchdogDaemon:
    """
    Standalone watchdog daemon.

    Provides continuous monitoring with terminal-friendly output.
    """

    # Vault directory
    VAULT_DIR = Path(__file__).parent.parent / "AI_Employee_Vault" / "Watchdog"
    PID_FILE = VAULT_DIR / "watchdog.pid"

    def __init__(self, args):
        self.args = args
        self.watchdog = get_watchdog()
        self.heartbeat_writer: HeartbeatWriter = None
        self._running = False
        self._scan_count = 0
        self._start_time = datetime.now()

        # Ensure vault directory exists
        self.VAULT_DIR.mkdir(parents=True, exist_ok=True)

        # Configure watchdog
        self._configure()

    def _configure(self):
        """Configure watchdog based on arguments."""
        config = WatchdogConfig(
            scan_interval=self.args.interval,
            heartbeat_timeout=60.0,
            hung_threshold=120.0,
            process_check_interval=30.0,
            resource_check_interval=15.0,
            health_output_interval=60.0,
            safe_mode=SafeModeConfig(
                crash_threshold=3,
                crash_window_seconds=600,
                restart_threshold=5,
                restart_window_seconds=1800,
                memory_threshold=90.0,
                cpu_threshold=95.0,
                recovery_timeout_seconds=900,
                auto_recover=True
            ),
            monitored_processes=[p["name"] for p in MONITORED_PROCESSES]
        )

        self.watchdog.configure(config)
        self.watchdog.set_debug(self.args.debug)
        self.watchdog.set_dry_run(self.args.dry_run)

        # Register process configurations
        restart_engine = AutoRestartEngine()
        for proc in MONITORED_PROCESSES:
            restart_engine.configure_process(ProcessConfig(
                name=proc["name"],
                command=proc["command"],
                working_dir=str(Path(__file__).parent.parent),
                critical=proc.get("critical", False),
                priority=proc.get("priority", 5)
            ))

        # Register callbacks
        self.watchdog.add_safe_mode_callback(self._on_safe_mode_change)
        self.watchdog.add_recovery_callback(self._on_recovery)

    def _on_safe_mode_change(self, active: bool, reason: str):
        """Callback when safe mode changes."""
        if active:
            self._print_alert(f"SAFE MODE ACTIVATED: {reason}")
        else:
            self._print_info("Safe mode deactivated")

    def _on_recovery(self, process_name: str, success: bool):
        """Callback when recovery is attempted."""
        if success:
            self._print_success(f"Successfully recovered: {process_name}")
        else:
            self._print_error(f"Failed to recover: {process_name}")

    def _print(self, message: str, color: str = Colors.RESET):
        """Print with timestamp and optional color."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"{Colors.CYAN}[{timestamp}]{Colors.RESET} {color}{message}{Colors.RESET}")

    def _print_info(self, message: str):
        self._print(f"INFO: {message}", Colors.BLUE)

    def _print_success(self, message: str):
        self._print(f"OK: {message}", Colors.GREEN)

    def _print_warning(self, message: str):
        self._print(f"WARN: {message}", Colors.YELLOW)

    def _print_error(self, message: str):
        self._print(f"ERROR: {message}", Colors.RED)

    def _print_alert(self, message: str):
        self._print(f"ALERT: {message}", Colors.RED + Colors.BOLD)

    def _print_header(self, message: str):
        print(f"\n{Colors.BOLD}{Colors.MAGENTA}{'='*60}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.MAGENTA}  {message}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.MAGENTA}{'='*60}{Colors.RESET}\n")

    def _write_pid_file(self):
        """Write PID file for daemon detection."""
        self.PID_FILE.write_text(str(os.getpid()))

    def _remove_pid_file(self):
        """Remove PID file."""
        if self.PID_FILE.exists():
            self.PID_FILE.unlink()

    def _check_existing_daemon(self) -> bool:
        """Check if another daemon is already running."""
        if not self.PID_FILE.exists():
            return False

        try:
            pid = int(self.PID_FILE.read_text().strip())

            if PSUTIL_AVAILABLE:
                if psutil.pid_exists(pid):
                    proc = psutil.Process(pid)
                    if "watchdog" in proc.name().lower() or "python" in proc.name().lower():
                        return True
            else:
                # Basic check
                try:
                    os.kill(pid, 0)
                    return True
                except OSError:
                    pass

            # Stale PID file
            self._remove_pid_file()
            return False

        except Exception:
            self._remove_pid_file()
            return False

    def show_status(self):
        """Show current system status and exit."""
        self._print_header("AI EMPLOYEE WATCHDOG STATUS")

        # Check if daemon is running
        if self._check_existing_daemon():
            self._print_success("Watchdog daemon is RUNNING")
            pid = int(self.PID_FILE.read_text().strip())
            print(f"  PID: {pid}")
        else:
            self._print_warning("Watchdog daemon is NOT RUNNING")

        # Get system health
        health = self.watchdog.get_system_health()

        print(f"\n{Colors.BOLD}System Health:{Colors.RESET}")
        print(f"  State: {self._colorize_state(health.state)}")
        print(f"  Uptime: {self._format_uptime(health.uptime_seconds)}")

        print(f"\n{Colors.BOLD}Resources:{Colors.RESET}")
        print(f"  CPU: {self._colorize_percent(health.cpu_percent)}%")
        print(f"  Memory: {self._colorize_percent(health.memory_percent)}%")
        print(f"  Disk: {self._colorize_percent(health.disk_percent)}%")
        print(f"  Level: {self._colorize_level(health.resource_level)}")
        print(f"  Throttle: {health.throttle_factor:.2f}x")

        print(f"\n{Colors.BOLD}Processes:{Colors.RESET}")
        print(f"  Healthy: {Colors.GREEN}{health.processes_healthy}{Colors.RESET}")
        print(f"  Warning: {Colors.YELLOW}{health.processes_warning}{Colors.RESET}")
        print(f"  Critical: {Colors.RED}{health.processes_critical}{Colors.RESET}")
        print(f"  Total: {health.processes_total}")

        print(f"\n{Colors.BOLD}Safe Mode:{Colors.RESET}")
        if health.safe_mode_active:
            print(f"  Status: {Colors.RED}ACTIVE{Colors.RESET}")
            print(f"  Reason: {health.safe_mode_reason}")
        else:
            print(f"  Status: {Colors.GREEN}INACTIVE{Colors.RESET}")

        if health.open_circuits:
            print(f"\n{Colors.BOLD}Open Circuit Breakers:{Colors.RESET}")
            for circuit in health.open_circuits:
                print(f"  - {Colors.RED}{circuit}{Colors.RESET}")

        print(f"\n{Colors.BOLD}Incidents (last hour):{Colors.RESET} {health.recent_incidents}")

        print()

    def _colorize_state(self, state: str) -> str:
        """Colorize state string."""
        colors = {
            "running": Colors.GREEN,
            "safe_mode": Colors.RED,
            "starting": Colors.YELLOW,
            "stopping": Colors.YELLOW,
            "stopped": Colors.RED,
            "error": Colors.RED
        }
        color = colors.get(state.lower(), Colors.RESET)
        return f"{color}{state.upper()}{Colors.RESET}"

    def _colorize_percent(self, value: float) -> str:
        """Colorize percentage value."""
        if value >= 90:
            return f"{Colors.RED}{value:.1f}{Colors.RESET}"
        elif value >= 75:
            return f"{Colors.YELLOW}{value:.1f}{Colors.RESET}"
        else:
            return f"{Colors.GREEN}{value:.1f}{Colors.RESET}"

    def _colorize_level(self, level: str) -> str:
        """Colorize resource level."""
        colors = {
            "normal": Colors.GREEN,
            "warning": Colors.YELLOW,
            "throttle": Colors.YELLOW,
            "emergency": Colors.RED,
            "critical": Colors.RED
        }
        color = colors.get(level.lower(), Colors.RESET)
        return f"{color}{level.upper()}{Colors.RESET}"

    def _format_uptime(self, seconds: float) -> str:
        """Format uptime in human-readable form."""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds // 60)}m {int(seconds % 60)}s"
        elif seconds < 86400:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
        else:
            days = int(seconds // 86400)
            hours = int((seconds % 86400) // 3600)
            return f"{days}d {hours}h"

    def enter_safe_mode(self):
        """Enter safe mode and exit."""
        self._print_header("ENTERING SAFE MODE")
        self.watchdog.enter_safe_mode(SafeModeReason.MANUAL)
        self._print_success("Safe mode activated")

    def exit_safe_mode(self):
        """Exit safe mode and exit."""
        self._print_header("EXITING SAFE MODE")
        self.watchdog.exit_safe_mode(manual=True)
        self._print_success("Safe mode deactivated")

    def run_once(self):
        """Perform a single scan and exit."""
        self._print_header("SINGLE SCAN MODE")

        self._print_info("Performing system scan...")
        health = self.watchdog.scan_once()

        print(f"\n{Colors.BOLD}Scan Results:{Colors.RESET}")
        print(f"  State: {self._colorize_state(health.state)}")
        print(f"  CPU: {self._colorize_percent(health.cpu_percent)}%")
        print(f"  Memory: {self._colorize_percent(health.memory_percent)}%")
        print(f"  Processes: {health.processes_healthy}/{health.processes_total} healthy")
        print(f"  Resource Level: {self._colorize_level(health.resource_level)}")

        if health.safe_mode_active:
            self._print_warning(f"Safe mode active: {health.safe_mode_reason}")

        self._print_success("Scan complete")

    def run(self):
        """Run the watchdog daemon."""
        # Check for existing daemon
        if self._check_existing_daemon():
            self._print_error("Another watchdog daemon is already running!")
            pid = int(self.PID_FILE.read_text().strip())
            print(f"Existing daemon PID: {pid}")
            print("Use --status to check status or kill the existing process first.")
            return 1

        self._print_header("AI EMPLOYEE WATCHDOG DAEMON")

        if self.args.dry_run:
            self._print_warning("Running in DRY-RUN mode (no restarts will be performed)")

        if self.args.debug:
            self._print_info("Debug mode enabled")

        # Write PID file
        self._write_pid_file()
        self._print_info(f"Watchdog daemon started (PID: {os.getpid()})")

        # Start heartbeat for watchdog itself
        self.heartbeat_writer = HeartbeatWriter("watchdog")
        self.heartbeat_writer.start()

        # Start watchdog
        self.watchdog.start()
        self._running = True

        self._print_success("Monitoring started")
        print(f"  Scan interval: {self.args.interval}s")
        print(f"  Monitored processes: {len(MONITORED_PROCESSES)}")
        print()

        # Setup signal handlers
        def signal_handler(signum, frame):
            self._print_info(f"Received signal {signum}, shutting down...")
            self._running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        if hasattr(signal, 'SIGBREAK'):
            signal.signal(signal.SIGBREAK, signal_handler)

        # Main loop
        try:
            while self._running and self.watchdog.get_state() != WatchdogState.STOPPED:
                self._scan_count += 1

                # Update heartbeat
                self.heartbeat_writer.update_task(f"scan_{self._scan_count}")

                # Periodic status output
                if self.args.debug or self._scan_count % 6 == 0:  # Every minute with default interval
                    health = self.watchdog.get_system_health()
                    self._print_status_line(health)

                time.sleep(self.args.interval)

        except Exception as e:
            self._print_error(f"Watchdog error: {e}")
            log_incident(
                event=IncidentType.WATCHDOG_ERROR,
                process_name="watchdog",
                reason=str(e),
                action="daemon_crash",
                result=IncidentResult.FAILED
            )
            return 1

        finally:
            # Cleanup
            self._print_info("Shutting down...")

            if self.heartbeat_writer:
                self.heartbeat_writer.stop()

            self.watchdog.stop()
            self._remove_pid_file()

            self._print_success("Watchdog daemon stopped")

        return 0

    def _print_status_line(self, health):
        """Print compact status line."""
        safe = f"{Colors.RED}[SAFE]{Colors.RESET}" if health.safe_mode_active else ""
        throttle = f"{Colors.YELLOW}[THROTTLE {health.throttle_factor:.1f}x]{Colors.RESET}" if health.throttle_factor > 1.0 else ""

        status = (
            f"CPU: {self._colorize_percent(health.cpu_percent)}% | "
            f"MEM: {self._colorize_percent(health.memory_percent)}% | "
            f"Procs: {health.processes_healthy}/{health.processes_total} | "
            f"Scans: {self._scan_count} "
            f"{safe}{throttle}"
        )

        self._print(status)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="AI Employee System Watchdog Daemon",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/system_watchdog.py              # Start daemon
  python3 scripts/system_watchdog.py --debug      # Start with debug output
  python3 scripts/system_watchdog.py --dry-run    # Test mode (no restarts)
  python3 scripts/system_watchdog.py --once       # Single scan
  python3 scripts/system_watchdog.py --status     # Show status
  python3 scripts/system_watchdog.py --safe-mode  # Enter safe mode
  python3 scripts/system_watchdog.py --exit-safe  # Exit safe mode
        """
    )

    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="Enable debug mode (verbose output)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode (no actual restarts)"
    )

    parser.add_argument(
        "--once", "-1",
        action="store_true",
        help="Perform single scan and exit"
    )

    parser.add_argument(
        "--status", "-s",
        action="store_true",
        help="Show status and exit"
    )

    parser.add_argument(
        "--safe-mode",
        action="store_true",
        help="Enter safe mode"
    )

    parser.add_argument(
        "--exit-safe",
        action="store_true",
        help="Exit safe mode"
    )

    parser.add_argument(
        "--interval", "-i",
        type=float,
        default=10.0,
        help="Scan interval in seconds (default: 10)"
    )

    args = parser.parse_args()

    # Create daemon instance
    daemon = SystemWatchdogDaemon(args)

    # Handle commands
    if args.status:
        daemon.show_status()
        return 0

    if args.safe_mode:
        daemon.enter_safe_mode()
        return 0

    if args.exit_safe:
        daemon.exit_safe_mode()
        return 0

    if args.once:
        daemon.run_once()
        return 0

    # Run daemon
    return daemon.run()


if __name__ == "__main__":
    sys.exit(main())
