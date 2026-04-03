#!/usr/bin/env python3
"""
Ralph Wiggum Loop - Autonomous Multi-Step Task Completion
Gold Tier - Enterprise Task Automation

"Me fail English? That's unpossible!" - Ralph Wiggum

This system embodies the persistent, never-give-up spirit of task completion.
It keeps working on tasks until they're done, handling failures gracefully,
and ensuring no task is left behind.

Features:
- Autonomous task queue processing
- Multi-step task execution with dependency resolution
- Intelligent failure recovery and retry logic
- Circuit breakers to prevent infinite loops
- Sub-task spawning for complex operations
- Comprehensive audit logging
- Integration with all AI Employee subsystems
"""

import json
import sys
import logging
import time
import hashlib
import subprocess
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, asdict, field
from enum import Enum
from collections import deque
import random

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ralph_wiggum")


# =============================================================================
# Task Types and States
# =============================================================================

class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4


class TaskType(Enum):
    # Social Media Tasks
    SOCIAL_POST = "social_post"
    SOCIAL_CAMPAIGN = "social_campaign"
    SOCIAL_ANALYTICS = "social_analytics"

    # Accounting Tasks
    ACCOUNTING_AUDIT = "accounting_audit"
    INVOICE_FOLLOWUP = "invoice_followup"
    EXPENSE_APPROVAL = "expense_approval"

    # System Tasks
    CEO_BRIEFING = "ceo_briefing"
    SYSTEM_HEALTH_CHECK = "system_health_check"
    ERROR_RECOVERY = "error_recovery"

    # Generic Tasks
    CUSTOM = "custom"
    MULTI_STEP = "multi_step"


@dataclass
class Task:
    """Represents a task in the queue"""
    id: str
    type: TaskType
    title: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    # Execution details
    steps: List[Dict[str, Any]] = field(default_factory=list)
    current_step: int = 0

    # Retry handling
    retry_count: int = 0
    max_retries: int = 3
    last_error: Optional[str] = None

    # Dependencies
    depends_on: List[str] = field(default_factory=list)
    blocks: List[str] = field(default_factory=list)

    # Results
    result: Optional[Dict[str, Any]] = None

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data["type"] = self.type.value
        data["status"] = self.status.value
        data["priority"] = self.priority.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """Create from dictionary"""
        data["type"] = TaskType(data["type"])
        data["status"] = TaskStatus(data["status"])
        data["priority"] = TaskPriority(data["priority"])
        return cls(**data)


@dataclass
class LoopState:
    """State of the Ralph Wiggum Loop"""
    is_running: bool = False
    started_at: Optional[str] = None
    iteration_count: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    last_activity: Optional[str] = None
    circuit_breaker_triggered: bool = False
    consecutive_failures: int = 0


# =============================================================================
# Task Executors
# =============================================================================

class TaskExecutor:
    """Base class for task executors"""

    def __init__(self, vault_path: Path):
        self.vault_path = vault_path

    def execute(self, task: Task) -> Dict[str, Any]:
        """Execute a task - override in subclasses"""
        raise NotImplementedError

    def validate(self, task: Task) -> bool:
        """Validate task can be executed"""
        return True


class SocialPostExecutor(TaskExecutor):
    """Executes social media posting tasks"""

    def execute(self, task: Task) -> Dict[str, Any]:
        logger.info(f"Executing social post task: {task.title}")

        platform = task.metadata.get("platform", "unknown")
        post_file = task.metadata.get("post_file")

        if not post_file:
            return {"success": False, "error": "No post file specified"}

        # Determine the poster script
        poster_map = {
            "facebook": "facebook_poster.py",
            "twitter": "twitter_poster.py",
            "instagram": "instagram_poster.py",
            "linkedin": "linkedin_poster.py"
        }

        poster = poster_map.get(platform.lower())
        if not poster:
            return {"success": False, "error": f"Unknown platform: {platform}"}

        scripts_dir = self.vault_path.parent / "scripts"
        poster_path = scripts_dir / poster

        try:
            result = subprocess.run(
                [sys.executable, str(poster_path), "--file", str(post_file), "--simulate"],
                capture_output=True,
                text=True,
                timeout=60
            )

            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Task execution timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}


class SocialCampaignExecutor(TaskExecutor):
    """Executes social media campaign generation"""

    def execute(self, task: Task) -> Dict[str, Any]:
        logger.info(f"Executing campaign task: {task.title}")

        scripts_dir = self.vault_path.parent / "scripts"
        campaign_script = scripts_dir / "social_campaign_engine.py"

        try:
            result = subprocess.run(
                [sys.executable, str(campaign_script), "--generate", "--auto-approve"],
                capture_output=True,
                text=True,
                timeout=120
            )

            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


class AccountingAuditExecutor(TaskExecutor):
    """Executes accounting audit tasks"""

    def execute(self, task: Task) -> Dict[str, Any]:
        logger.info(f"Executing accounting audit: {task.title}")

        mcp_dir = self.vault_path.parent / "mcp_servers" / "odoo_accounting"
        server_script = mcp_dir / "server.py"

        try:
            result = subprocess.run(
                [sys.executable, str(server_script), "--mode", "audit"],
                capture_output=True,
                text=True,
                timeout=60
            )

            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


class CEOBriefingExecutor(TaskExecutor):
    """Executes CEO briefing generation"""

    def execute(self, task: Task) -> Dict[str, Any]:
        logger.info(f"Executing CEO briefing: {task.title}")

        scripts_dir = self.vault_path.parent / "scripts"
        briefing_script = scripts_dir / "weekly_ceo_briefing.py"

        try:
            result = subprocess.run(
                [sys.executable, str(briefing_script), "--output", "file"],
                capture_output=True,
                text=True,
                timeout=90
            )

            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


class SystemHealthExecutor(TaskExecutor):
    """Executes system health checks"""

    def execute(self, task: Task) -> Dict[str, Any]:
        logger.info(f"Executing system health check: {task.title}")

        health_results = {
            "timestamp": datetime.now().isoformat(),
            "checks": []
        }

        # Check vault directories
        required_dirs = ["Approved", "Done", "Drafts", "Executive", "Logs", "System"]
        for dir_name in required_dirs:
            dir_path = self.vault_path / dir_name
            health_results["checks"].append({
                "name": f"Directory: {dir_name}",
                "status": "ok" if dir_path.exists() else "missing",
                "path": str(dir_path)
            })

        # Check critical scripts
        scripts_dir = self.vault_path.parent / "scripts"
        critical_scripts = [
            "social_media_orchestrator.py",
            "social_campaign_engine.py",
            "weekly_ceo_briefing.py"
        ]

        for script in critical_scripts:
            script_path = scripts_dir / script
            health_results["checks"].append({
                "name": f"Script: {script}",
                "status": "ok" if script_path.exists() else "missing"
            })

        # Overall status
        all_ok = all(c["status"] == "ok" for c in health_results["checks"])
        health_results["overall_status"] = "healthy" if all_ok else "degraded"

        return {
            "success": True,
            "health_report": health_results
        }


class MultiStepExecutor(TaskExecutor):
    """Executes multi-step tasks"""

    def execute(self, task: Task) -> Dict[str, Any]:
        logger.info(f"Executing multi-step task: {task.title}")

        steps = task.steps
        results = []

        for i, step in enumerate(steps[task.current_step:], start=task.current_step):
            logger.info(f"  Step {i+1}/{len(steps)}: {step.get('name', 'unnamed')}")

            step_type = step.get("type", "command")

            if step_type == "command":
                cmd = step.get("command")
                if cmd:
                    try:
                        result = subprocess.run(
                            cmd,
                            shell=True,
                            capture_output=True,
                            text=True,
                            timeout=step.get("timeout", 60)
                        )
                        step_result = {
                            "step": i,
                            "name": step.get("name"),
                            "success": result.returncode == 0,
                            "output": result.stdout
                        }
                    except Exception as e:
                        step_result = {
                            "step": i,
                            "success": False,
                            "error": str(e)
                        }
                else:
                    step_result = {"step": i, "success": False, "error": "No command specified"}

            elif step_type == "delay":
                time.sleep(step.get("seconds", 1))
                step_result = {"step": i, "success": True, "action": "delayed"}

            else:
                step_result = {"step": i, "success": True, "action": "skipped"}

            results.append(step_result)
            task.current_step = i + 1

            # Stop on failure unless continue_on_error is set
            if not step_result.get("success") and not step.get("continue_on_error"):
                return {
                    "success": False,
                    "completed_steps": i + 1,
                    "total_steps": len(steps),
                    "step_results": results,
                    "error": step_result.get("error", "Step failed")
                }

        return {
            "success": True,
            "completed_steps": len(steps),
            "total_steps": len(steps),
            "step_results": results
        }


# =============================================================================
# Ralph Wiggum Loop Controller
# =============================================================================

class RalphWiggumLoop:
    """
    The Ralph Wiggum Loop - Autonomous Task Completion Engine

    "I'm learnding!" - Ralph Wiggum

    This controller manages the autonomous execution of tasks,
    ensuring they complete successfully or fail gracefully.
    """

    # Circuit breaker settings
    MAX_CONSECUTIVE_FAILURES = 5
    MAX_ITERATIONS_PER_RUN = 100
    COOLDOWN_AFTER_CIRCUIT_BREAK = 300  # 5 minutes

    def __init__(self, vault_path: Optional[Path] = None):
        self.vault_path = vault_path or Path(__file__).parent.parent / "AI_Employee_Vault"
        self.queue_path = self.vault_path / "System" / "task_queue.json"
        self.state_path = self.vault_path / "System" / "ralph_state.json"
        self.log_path = self.vault_path / "Logs" / "ralph_wiggum.log"

        # Ensure directories exist
        self.queue_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize state
        self.state = self._load_state()
        self.task_queue: List[Task] = self._load_queue()

        # Initialize executors
        self.executors: Dict[TaskType, TaskExecutor] = {
            TaskType.SOCIAL_POST: SocialPostExecutor(self.vault_path),
            TaskType.SOCIAL_CAMPAIGN: SocialCampaignExecutor(self.vault_path),
            TaskType.ACCOUNTING_AUDIT: AccountingAuditExecutor(self.vault_path),
            TaskType.CEO_BRIEFING: CEOBriefingExecutor(self.vault_path),
            TaskType.SYSTEM_HEALTH_CHECK: SystemHealthExecutor(self.vault_path),
            TaskType.MULTI_STEP: MultiStepExecutor(self.vault_path),
        }

    def _load_state(self) -> LoopState:
        """Load loop state from file"""
        if self.state_path.exists():
            try:
                with open(self.state_path, 'r') as f:
                    data = json.load(f)
                return LoopState(**data)
            except Exception as e:
                logger.warning(f"Failed to load state: {e}")
        return LoopState()

    def _save_state(self):
        """Save loop state to file"""
        with open(self.state_path, 'w') as f:
            json.dump(asdict(self.state), f, indent=2)

    def _load_queue(self) -> List[Task]:
        """Load task queue from file"""
        if self.queue_path.exists():
            try:
                with open(self.queue_path, 'r') as f:
                    data = json.load(f)
                return [Task.from_dict(t) for t in data.get("tasks", [])]
            except Exception as e:
                logger.warning(f"Failed to load queue: {e}")
        return []

    def _save_queue(self):
        """Save task queue to file"""
        with open(self.queue_path, 'w') as f:
            json.dump({
                "tasks": [t.to_dict() for t in self.task_queue],
                "updated_at": datetime.now().isoformat()
            }, f, indent=2)

    def _log_event(self, event_type: str, task: Optional[Task], details: Dict[str, Any]):
        """Log an event to the Ralph Wiggum log"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event_type,
            "task_id": task.id if task else None,
            "task_title": task.title if task else None,
            "details": details
        }

        with open(self.log_path, 'a') as f:
            f.write(json.dumps(log_entry) + "\n")

    def add_task(self, task: Task) -> str:
        """Add a task to the queue"""
        # Generate ID if not set
        if not task.id:
            task.id = hashlib.md5(
                f"{task.title}{datetime.now().isoformat()}".encode()
            ).hexdigest()[:12]

        self.task_queue.append(task)
        self._save_queue()
        self._log_event("task_added", task, {"priority": task.priority.value})

        logger.info(f"Task added: {task.id} - {task.title}")
        return task.id

    def get_next_task(self) -> Optional[Task]:
        """Get the next task to execute based on priority and dependencies"""

        # Filter pending tasks
        pending = [t for t in self.task_queue if t.status == TaskStatus.PENDING]

        if not pending:
            return None

        # Check dependencies
        eligible = []
        completed_ids = {t.id for t in self.task_queue if t.status == TaskStatus.COMPLETED}

        for task in pending:
            if all(dep_id in completed_ids for dep_id in task.depends_on):
                eligible.append(task)

        if not eligible:
            return None

        # Sort by priority
        eligible.sort(key=lambda t: t.priority.value)

        return eligible[0]

    def execute_task(self, task: Task) -> bool:
        """Execute a single task"""

        logger.info(f"Executing task: {task.id} - {task.title}")

        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.now().isoformat()
        task.updated_at = datetime.now().isoformat()
        self._save_queue()

        self._log_event("task_started", task, {})

        try:
            # Get executor
            executor = self.executors.get(task.type)

            if not executor:
                # Use generic command executor for custom tasks
                if task.type == TaskType.CUSTOM:
                    result = self._execute_custom_task(task)
                else:
                    raise ValueError(f"No executor for task type: {task.type}")
            else:
                result = executor.execute(task)

            # Process result
            if result.get("success"):
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.now().isoformat()
                task.result = result
                self.state.tasks_completed += 1
                self.state.consecutive_failures = 0

                self._log_event("task_completed", task, {"result": result})
                logger.info(f"Task completed: {task.id}")

                return True
            else:
                raise Exception(result.get("error", "Task execution failed"))

        except Exception as e:
            error_msg = str(e)
            task.last_error = error_msg
            task.retry_count += 1

            if task.retry_count < task.max_retries:
                task.status = TaskStatus.RETRYING
                logger.warning(f"Task failed, will retry ({task.retry_count}/{task.max_retries}): {error_msg}")
                self._log_event("task_retry", task, {"error": error_msg, "attempt": task.retry_count})
            else:
                task.status = TaskStatus.FAILED
                self.state.tasks_failed += 1
                self.state.consecutive_failures += 1
                logger.error(f"Task failed permanently: {error_msg}")
                self._log_event("task_failed", task, {"error": error_msg})

            task.updated_at = datetime.now().isoformat()
            self._save_queue()

            return False

    def _execute_custom_task(self, task: Task) -> Dict[str, Any]:
        """Execute a custom task"""

        command = task.metadata.get("command")
        if not command:
            return {"success": False, "error": "No command specified for custom task"}

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=task.metadata.get("timeout", 120)
            )

            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def check_circuit_breaker(self) -> bool:
        """Check if circuit breaker should trigger"""

        if self.state.consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
            logger.error(f"Circuit breaker triggered: {self.state.consecutive_failures} consecutive failures")
            self.state.circuit_breaker_triggered = True
            self._save_state()
            self._log_event("circuit_breaker", None, {
                "consecutive_failures": self.state.consecutive_failures
            })
            return True

        return False

    def reset_circuit_breaker(self):
        """Reset the circuit breaker"""
        self.state.circuit_breaker_triggered = False
        self.state.consecutive_failures = 0
        self._save_state()
        logger.info("Circuit breaker reset")

    def run_once(self) -> Dict[str, Any]:
        """Run one iteration of the loop"""

        self.state.iteration_count += 1
        self.state.last_activity = datetime.now().isoformat()

        # Check circuit breaker
        if self.state.circuit_breaker_triggered:
            return {
                "status": "circuit_breaker_active",
                "message": "Circuit breaker is active. Reset manually to continue."
            }

        # Get next task
        task = self.get_next_task()

        if not task:
            # Check for retrying tasks
            retrying = [t for t in self.task_queue if t.status == TaskStatus.RETRYING]
            if retrying:
                task = retrying[0]
                task.status = TaskStatus.PENDING  # Reset for retry
            else:
                return {
                    "status": "queue_empty",
                    "message": "No tasks to process"
                }

        # Execute task
        success = self.execute_task(task)

        # Check circuit breaker after execution
        if self.check_circuit_breaker():
            return {
                "status": "circuit_breaker_triggered",
                "task_id": task.id,
                "message": "Too many consecutive failures"
            }

        self._save_state()

        return {
            "status": "completed" if success else "failed",
            "task_id": task.id,
            "task_title": task.title,
            "success": success
        }

    def run_loop(self, max_iterations: Optional[int] = None) -> Dict[str, Any]:
        """
        Run the Ralph Wiggum Loop until all tasks complete or circuit breaker triggers

        "Me fail English? That's unpossible!"
        """

        max_iter = max_iterations or self.MAX_ITERATIONS_PER_RUN

        logger.info("="*60)
        logger.info("  RALPH WIGGUM LOOP STARTING")
        logger.info("  'I'm learnding!'")
        logger.info("="*60)

        self.state.is_running = True
        self.state.started_at = datetime.now().isoformat()
        self._save_state()

        self._log_event("loop_started", None, {"max_iterations": max_iter})

        results = {
            "iterations": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "task_results": []
        }

        try:
            for i in range(max_iter):
                result = self.run_once()
                results["iterations"] += 1
                results["task_results"].append(result)

                if result["status"] == "completed":
                    results["tasks_completed"] += 1
                elif result["status"] == "failed":
                    results["tasks_failed"] += 1
                elif result["status"] == "queue_empty":
                    logger.info("All tasks completed!")
                    break
                elif result["status"] in ["circuit_breaker_active", "circuit_breaker_triggered"]:
                    logger.error("Circuit breaker stopped the loop")
                    break

                # Small delay between tasks
                time.sleep(0.5)

        finally:
            self.state.is_running = False
            self._save_state()

        self._log_event("loop_completed", None, results)

        logger.info("="*60)
        logger.info("  RALPH WIGGUM LOOP COMPLETE")
        logger.info(f"  Iterations: {results['iterations']}")
        logger.info(f"  Completed: {results['tasks_completed']}")
        logger.info(f"  Failed: {results['tasks_failed']}")
        logger.info("="*60)

        return results

    def get_status(self) -> Dict[str, Any]:
        """Get current loop status"""

        pending = len([t for t in self.task_queue if t.status == TaskStatus.PENDING])
        in_progress = len([t for t in self.task_queue if t.status == TaskStatus.IN_PROGRESS])
        completed = len([t for t in self.task_queue if t.status == TaskStatus.COMPLETED])
        failed = len([t for t in self.task_queue if t.status == TaskStatus.FAILED])
        retrying = len([t for t in self.task_queue if t.status == TaskStatus.RETRYING])

        return {
            "loop_state": asdict(self.state),
            "queue_status": {
                "total": len(self.task_queue),
                "pending": pending,
                "in_progress": in_progress,
                "completed": completed,
                "failed": failed,
                "retrying": retrying
            },
            "circuit_breaker": {
                "triggered": self.state.circuit_breaker_triggered,
                "consecutive_failures": self.state.consecutive_failures,
                "threshold": self.MAX_CONSECUTIVE_FAILURES
            }
        }

    def clear_completed(self):
        """Remove completed tasks from queue"""
        before = len(self.task_queue)
        self.task_queue = [t for t in self.task_queue if t.status != TaskStatus.COMPLETED]
        after = len(self.task_queue)
        self._save_queue()
        logger.info(f"Cleared {before - after} completed tasks")

    def clear_all(self):
        """Clear all tasks from queue"""
        self.task_queue = []
        self._save_queue()
        logger.info("Task queue cleared")


# =============================================================================
# Demo and Testing
# =============================================================================

def create_demo_tasks(loop: RalphWiggumLoop):
    """Create demo tasks for testing"""

    # Task 1: System health check
    task1 = Task(
        id="demo_health_001",
        type=TaskType.SYSTEM_HEALTH_CHECK,
        title="System Health Check",
        description="Verify all system components are operational",
        priority=TaskPriority.HIGH
    )

    # Task 2: Accounting audit (depends on health check)
    task2 = Task(
        id="demo_audit_001",
        type=TaskType.ACCOUNTING_AUDIT,
        title="Weekly Accounting Audit",
        description="Generate accounting audit report",
        priority=TaskPriority.NORMAL,
        depends_on=["demo_health_001"]
    )

    # Task 3: CEO Briefing (depends on audit)
    task3 = Task(
        id="demo_ceo_001",
        type=TaskType.CEO_BRIEFING,
        title="CEO Weekly Briefing",
        description="Generate comprehensive CEO briefing",
        priority=TaskPriority.NORMAL,
        depends_on=["demo_audit_001"]
    )

    # Task 4: Multi-step task
    task4 = Task(
        id="demo_multi_001",
        type=TaskType.MULTI_STEP,
        title="Multi-step Demo",
        description="Demonstrate multi-step task execution",
        priority=TaskPriority.LOW,
        steps=[
            {"name": "Step 1", "type": "delay", "seconds": 1},
            {"name": "Step 2", "type": "command", "command": "echo 'Step 2 complete'"},
            {"name": "Step 3", "type": "delay", "seconds": 1}
        ]
    )

    # Add tasks
    for task in [task1, task2, task3, task4]:
        loop.add_task(task)

    print(f"Added {4} demo tasks to queue")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Ralph Wiggum Loop - Autonomous Task Completion"
    )
    parser.add_argument(
        "--mode",
        choices=["run", "status", "demo", "clear", "reset"],
        default="status",
        help="Operation mode"
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=50,
        help="Maximum iterations for run mode"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    loop = RalphWiggumLoop()

    print("\n" + "="*60)
    print("    RALPH WIGGUM LOOP")
    print("    'Me fail English? That's unpossible!'")
    print("="*60 + "\n")

    if args.mode == "status":
        status = loop.get_status()
        print("Loop State:")
        print(f"  Running: {status['loop_state']['is_running']}")
        print(f"  Iterations: {status['loop_state']['iteration_count']}")
        print(f"  Completed: {status['loop_state']['tasks_completed']}")
        print(f"  Failed: {status['loop_state']['tasks_failed']}")

        print("\nQueue Status:")
        qs = status['queue_status']
        print(f"  Total: {qs['total']}")
        print(f"  Pending: {qs['pending']}")
        print(f"  In Progress: {qs['in_progress']}")
        print(f"  Completed: {qs['completed']}")
        print(f"  Failed: {qs['failed']}")
        print(f"  Retrying: {qs['retrying']}")

        print("\nCircuit Breaker:")
        cb = status['circuit_breaker']
        print(f"  Triggered: {cb['triggered']}")
        print(f"  Consecutive Failures: {cb['consecutive_failures']}/{cb['threshold']}")

    elif args.mode == "demo":
        print("Creating demo tasks...")
        create_demo_tasks(loop)

        print("\nRunning loop...")
        results = loop.run_loop(max_iterations=args.max_iterations)

        print(f"\nResults:")
        print(f"  Iterations: {results['iterations']}")
        print(f"  Completed: {results['tasks_completed']}")
        print(f"  Failed: {results['tasks_failed']}")

    elif args.mode == "run":
        print("Running Ralph Wiggum Loop...")
        results = loop.run_loop(max_iterations=args.max_iterations)

        print(f"\nResults:")
        print(f"  Iterations: {results['iterations']}")
        print(f"  Completed: {results['tasks_completed']}")
        print(f"  Failed: {results['tasks_failed']}")

    elif args.mode == "clear":
        print("Clearing completed tasks...")
        loop.clear_completed()

    elif args.mode == "reset":
        print("Resetting circuit breaker...")
        loop.reset_circuit_breaker()
        print("Clearing all tasks...")
        loop.clear_all()

    print("\n" + "="*60)


if __name__ == "__main__":
    main()
