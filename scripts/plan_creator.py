"""
Plan Creator - Claude Reasoning Loop
Silver Tier Component
Enhanced with Gold Tier Audit Logging & Error Recovery

Analyzes tasks in Needs_Action and creates detailed Plan.md files
with step-by-step execution strategies.

Based on: Skills/plan_creator.md

This script can be:
1. Run standalone to process all pending tasks
2. Integrated with Claude Code for AI-enhanced planning
3. Used as a template generator for manual planning
"""

import os
import sys
import re
from datetime import datetime
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.audit_logger import (
    get_audit_logger,
    ActionType,
    ApprovalStatus,
    ResultStatus
)

from utils.retry_handler import (
    get_retry_handler,
    get_circuit_breaker,
    get_queue_manager
)

# Configuration
BASE_DIR = Path(__file__).parent.parent
VAULT_DIR = BASE_DIR / "AI_Employee_Vault"
NEEDS_ACTION_DIR = VAULT_DIR / "Needs_Action"
PLANS_DIR = VAULT_DIR / "Plans"
HANDBOOK_PATH = VAULT_DIR / "Company_Handbook.md"
GOALS_PATH = VAULT_DIR / "Business_Goals.md"
LOGS_DIR = VAULT_DIR / "Logs"

# Actor name for audit logging
ACTOR = "plan_creator"

# Initialize audit logger
audit_logger = get_audit_logger()

# Initialize retry handler
retry_handler = get_retry_handler(
    actor=ACTOR,
    circuit_breaker="plan_creation"
)
circuit_breaker = get_circuit_breaker("plan_creation")
queue_manager = get_queue_manager()


def log(message, level="INFO"):
    """Print a timestamped log message."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")


def parse_task_file(filepath):
    """Parse a task markdown file and extract metadata."""
    with open(filepath, "r") as f:
        content = f.read()

    metadata = {}
    body = content

    # Extract frontmatter
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            frontmatter = parts[1].strip()
            body = parts[2].strip()
            for line in frontmatter.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    metadata[key.strip()] = value.strip()

    return metadata, body


def get_task_type(metadata, body):
    """Determine the type of task."""
    task_type = metadata.get("type", "general")

    # Check for specific patterns
    if "email" in task_type.lower() or "email_id" in metadata:
        return "email"
    if "linkedin" in task_type.lower():
        return "linkedin"
    if "payment" in body.lower() or "invoice" in body.lower():
        return "financial"
    if "meeting" in body.lower() or "schedule" in body.lower():
        return "scheduling"

    return task_type


def determine_complexity(metadata, body):
    """Determine task complexity."""
    # Count indicators
    complexity_score = 0

    # Check priority
    priority = metadata.get("priority", "medium").lower()
    if priority == "critical":
        complexity_score += 3
    elif priority == "high":
        complexity_score += 2
    elif priority == "medium":
        complexity_score += 1

    # Check content length
    if len(body) > 500:
        complexity_score += 2
    elif len(body) > 200:
        complexity_score += 1

    # Check for multiple action items
    if body.count("[ ]") > 3:
        complexity_score += 2

    if complexity_score >= 5:
        return "high"
    elif complexity_score >= 3:
        return "medium"
    return "low"


def generate_steps_for_email(metadata, body):
    """Generate execution steps for email tasks."""
    steps = []

    steps.append({
        "phase": "Analysis",
        "actions": [
            {"step": "1.1", "action": "Read full email content", "owner": "AI"},
            {"step": "1.2", "action": "Identify sender and context", "owner": "AI"},
            {"step": "1.3", "action": "Determine required response type", "owner": "AI"}
        ]
    })

    steps.append({
        "phase": "Response Preparation",
        "actions": [
            {"step": "2.1", "action": "Draft response based on context", "owner": "AI"},
            {"step": "2.2", "action": "Review draft for tone and accuracy", "owner": "Human"},
            {"step": "2.3", "action": "Create approval request", "owner": "AI"}
        ]
    })

    steps.append({
        "phase": "Execution",
        "actions": [
            {"step": "3.1", "action": "Await human approval", "owner": "Human"},
            {"step": "3.2", "action": "Send email via MCP", "owner": "AI"},
            {"step": "3.3", "action": "Log completion", "owner": "AI"}
        ]
    })

    return steps


def generate_steps_for_linkedin(metadata, body):
    """Generate execution steps for LinkedIn tasks."""
    steps = []

    steps.append({
        "phase": "Content Creation",
        "actions": [
            {"step": "1.1", "action": "Define post objective", "owner": "AI"},
            {"step": "1.2", "action": "Draft post content", "owner": "AI"},
            {"step": "1.3", "action": "Select appropriate hashtags", "owner": "AI"}
        ]
    })

    steps.append({
        "phase": "Review & Approval",
        "actions": [
            {"step": "2.1", "action": "Review content for brand alignment", "owner": "Human"},
            {"step": "2.2", "action": "Check for compliance issues", "owner": "Human"},
            {"step": "2.3", "action": "Approve or request changes", "owner": "Human"}
        ]
    })

    steps.append({
        "phase": "Publishing",
        "actions": [
            {"step": "3.1", "action": "Execute LinkedIn automation", "owner": "AI"},
            {"step": "3.2", "action": "Verify post is live", "owner": "AI"},
            {"step": "3.3", "action": "Log and archive", "owner": "AI"}
        ]
    })

    return steps


def generate_steps_for_general(metadata, body):
    """Generate execution steps for general tasks."""
    steps = []

    steps.append({
        "phase": "Understanding",
        "actions": [
            {"step": "1.1", "action": "Analyze task requirements", "owner": "AI"},
            {"step": "1.2", "action": "Identify dependencies", "owner": "AI"},
            {"step": "1.3", "action": "Gather necessary resources", "owner": "AI"}
        ]
    })

    steps.append({
        "phase": "Execution",
        "actions": [
            {"step": "2.1", "action": "Execute primary task actions", "owner": "AI/Human"},
            {"step": "2.2", "action": "Validate results", "owner": "AI"},
            {"step": "2.3", "action": "Handle any exceptions", "owner": "Human"}
        ]
    })

    steps.append({
        "phase": "Completion",
        "actions": [
            {"step": "3.1", "action": "Document outcomes", "owner": "AI"},
            {"step": "3.2", "action": "Update relevant files", "owner": "AI"},
            {"step": "3.3", "action": "Move to Done", "owner": "AI"}
        ]
    })

    return steps


def generate_steps(task_type, metadata, body):
    """Generate appropriate steps based on task type."""
    if task_type == "email":
        return generate_steps_for_email(metadata, body)
    elif task_type == "linkedin":
        return generate_steps_for_linkedin(metadata, body)
    else:
        return generate_steps_for_general(metadata, body)


def format_steps_markdown(steps):
    """Format steps as markdown."""
    output = ""

    for phase_data in steps:
        phase = phase_data["phase"]
        actions = phase_data["actions"]

        output += f"\n### Phase: {phase}\n\n"
        output += "| Step | Action | Owner | Status |\n"
        output += "|------|--------|-------|--------|\n"

        for action in actions:
            output += f"| {action['step']} | {action['action']} | {action['owner']} | Pending |\n"

    return output


def identify_risks(task_type, metadata, body):
    """Identify potential risks for the task."""
    risks = []

    # Common risks
    risks.append({
        "risk": "Task requirements unclear",
        "likelihood": "Medium",
        "mitigation": "Request clarification before proceeding"
    })

    # Type-specific risks
    if task_type == "email":
        risks.append({
            "risk": "Response tone inappropriate",
            "likelihood": "Low",
            "mitigation": "Human review before sending"
        })
        risks.append({
            "risk": "Wrong recipient",
            "likelihood": "Low",
            "mitigation": "Verify email address in approval"
        })

    elif task_type == "linkedin":
        risks.append({
            "risk": "Content violates platform guidelines",
            "likelihood": "Low",
            "mitigation": "Human review of all posts"
        })

    elif task_type == "financial":
        risks.append({
            "risk": "Incorrect payment amount",
            "likelihood": "Medium",
            "mitigation": "Double verification required"
        })

    # Priority-based risks
    if metadata.get("priority") == "critical":
        risks.append({
            "risk": "Time constraint pressure",
            "likelihood": "High",
            "mitigation": "Prioritize and allocate resources immediately"
        })

    return risks


def format_risks_markdown(risks):
    """Format risks as markdown table."""
    output = "\n| Risk | Likelihood | Mitigation |\n"
    output += "|------|------------|------------|\n"

    for risk in risks:
        output += f"| {risk['risk']} | {risk['likelihood']} | {risk['mitigation']} |\n"

    return output


def _do_create_plan(task_filepath, start_time):
    """Internal plan creation logic (called by retry handler)."""
    # Parse task
    metadata, body = parse_task_file(task_filepath)
    task_type = get_task_type(metadata, body)
    complexity = determine_complexity(metadata, body)
    requires_approval = task_type in ["email", "linkedin", "financial"]

    # Generate plan components
    steps = generate_steps(task_type, metadata, body)
    risks = identify_risks(task_type, metadata, body)

    # Create plan filename
    task_name = task_filepath.stem
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    plan_filename = f"PLAN_{task_name}_{timestamp}.md"
    plan_filepath = PLANS_DIR / plan_filename

    # Get task title
    task_title = metadata.get("subject", metadata.get("title", task_name))

    # Generate plan content
    plan_content = f"""---
type: plan
plan_id: PLAN_{task_name}_{timestamp}
related_task: {task_filepath}
task_type: {task_type}
created: {datetime.now().isoformat()}
status: draft
complexity: {complexity}
requires_approval: {requires_approval}
---

# Plan: {task_title}

## Objective

Process and complete the task: **{task_title}**

Task Type: **{task_type.upper()}**
Complexity: **{complexity.upper()}**
Priority: **{metadata.get('priority', 'medium').upper()}**

## Related Task

- **Task File:** `{task_filepath.name}`
- **Location:** `{task_filepath.parent}`
- **Status:** {metadata.get('status', 'pending')}

## Context

This plan was auto-generated based on task analysis.
Task type "{task_type}" requires {"human approval before execution" if requires_approval else "standard processing"}.

## Execution Steps
{format_steps_markdown(steps)}

## Risks & Mitigation
{format_risks_markdown(risks)}

## Resources Required

- AI Agent for automated steps
- Human reviewer for approval steps
- MCP servers for external actions (if applicable)

## Validation Checklist

- [ ] All steps are clear and actionable
- [ ] Dependencies identified
- [ ] Risks assessed
- [ ] Aligned with business goals

## Approval Section

{"**This plan requires human approval before execution.**" if requires_approval else "This plan can proceed with standard workflow."}

- [ ] Plan reviewed
- [ ] Approved for execution

---
*Generated by Plan Creator*
*{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
"""

    # Write plan file
    with open(plan_filepath, "w") as f:
        f.write(plan_content)

    log(f"Plan created: {plan_filename}")
    log(f"  Type: {task_type}, Complexity: {complexity}")

    # Audit log: plan creation completed
    audit_logger.log_with_duration(
        action_type=ActionType.PLAN_CREATED,
        actor=ACTOR,
        target=str(plan_filepath),
        start_time=start_time,
        parameters={
            'source_task': task_filepath.name,
            'task_type': task_type,
            'complexity': complexity,
            'requires_approval': requires_approval,
            'steps_count': sum(len(phase['actions']) for phase in steps),
            'risks_count': len(risks)
        },
        approval_status=ApprovalStatus.PENDING if requires_approval else ApprovalStatus.NOT_REQUIRED,
        result=ResultStatus.SUCCESS
    )

    return plan_filepath


def create_plan(task_filepath):
    """Create a plan for a task file (with retry handling)."""
    start_time = datetime.now()
    task_filepath = Path(task_filepath)

    log(f"Creating plan for: {task_filepath.name}")

    # Check circuit breaker
    if not circuit_breaker.can_execute():
        log(f"  CIRCUIT OPEN: Skipping plan creation", "WARNING")
        audit_logger.log(
            action_type=ActionType.WARNING_RAISED,
            actor=ACTOR,
            target=str(task_filepath),
            parameters={'reason': 'circuit_breaker_open'},
            result=ResultStatus.FAILURE
        )
        return None

    # Log plan creation started
    audit_logger.log(
        action_type=ActionType.TASK_STARTED,
        actor=ACTOR,
        target=str(task_filepath),
        parameters={'task_file': task_filepath.name},
        result=ResultStatus.PENDING
    )

    try:
        # Execute with retry handling
        result = retry_handler.execute(
            _do_create_plan,
            task_filepath,
            start_time,
            task_id=f"plan_{task_filepath.stem}",
            task_type="plan_creation"
        )
        circuit_breaker.record_success()
        return result

    except Exception as e:
        # Log failure after all retries exhausted
        circuit_breaker.record_failure(e)
        audit_logger.log_with_duration(
            action_type=ActionType.TASK_FAILED,
            actor=ACTOR,
            target=str(task_filepath),
            start_time=start_time,
            parameters={
                'task_file': task_filepath.name,
                'retries_exhausted': True
            },
            result=ResultStatus.FAILURE,
            error=str(e)
        )
        raise


def get_pending_tasks():
    """Get all pending tasks from Needs_Action."""
    tasks = []

    # Check all subdirectories
    for subdir in ["", "email", "linkedin", "general"]:
        search_dir = NEEDS_ACTION_DIR / subdir if subdir else NEEDS_ACTION_DIR
        if search_dir.exists():
            for f in search_dir.glob("*.md"):
                tasks.append(f)

    return tasks


def run_plan_creator():
    """Main plan creator loop."""
    print("=" * 60)
    print("Silver Tier - Plan Creator")
    print("With Gold Tier Audit Logging")
    print("=" * 60)
    print(f"Tasks Source: {NEEDS_ACTION_DIR}")
    print(f"Plans Output: {PLANS_DIR}")
    print("=" * 60)
    print()

    # Audit log: system started
    audit_logger.log(
        action_type=ActionType.SYSTEM_STARTED,
        actor=ACTOR,
        target="plan_creator",
        parameters={
            'tasks_dir': str(NEEDS_ACTION_DIR),
            'plans_dir': str(PLANS_DIR)
        },
        result=ResultStatus.SUCCESS
    )

    # Ensure directories exist
    PLANS_DIR.mkdir(parents=True, exist_ok=True)

    # Get pending tasks
    tasks = get_pending_tasks()
    log(f"Found {len(tasks)} task(s) to process")

    if not tasks:
        log("No tasks found in Needs_Action")
        # Audit log: no tasks
        audit_logger.log(
            action_type=ActionType.SYSTEM_STOPPED,
            actor=ACTOR,
            target="plan_creator",
            parameters={'reason': 'no_tasks_found'},
            result=ResultStatus.SUCCESS
        )
        audit_logger.flush()
        return

    # Process each task
    plans_created = 0
    plans_failed = 0
    for task_path in tasks:
        try:
            create_plan(task_path)
            plans_created += 1
            print()
        except Exception as e:
            log(f"Error processing {task_path.name}: {e}", "ERROR")
            # Audit log: error
            audit_logger.log_error(
                actor=ACTOR,
                target=str(task_path),
                error_message=str(e),
                error_type=type(e).__name__
            )
            plans_failed += 1
            print()

    # Summary
    print("=" * 60)
    print("PLAN CREATION SUMMARY")
    print("=" * 60)
    print(f"Tasks processed: {len(tasks)}")
    print(f"Plans created:   {plans_created}")
    print(f"Plans failed:    {plans_failed}")
    print(f"Plans location:  {PLANS_DIR}")

    # Circuit breaker status
    cb_state = circuit_breaker.get_state()
    print(f"Circuit State:   {cb_state['state']}")

    # Retry queue status
    queue_stats = queue_manager.get_queue_stats()
    if queue_stats['total_tasks'] > 0:
        print(f"Retry Queue:     {queue_stats['total_tasks']} tasks pending")

    print("=" * 60)

    # Audit log: system stopped
    audit_logger.log(
        action_type=ActionType.SYSTEM_STOPPED,
        actor=ACTOR,
        target="plan_creator",
        parameters={
            'tasks_processed': len(tasks),
            'plans_created': plans_created,
            'plans_failed': plans_failed
        },
        result=ResultStatus.SUCCESS if plans_failed == 0 else ResultStatus.PARTIAL
    )
    audit_logger.flush()


if __name__ == "__main__":
    run_plan_creator()
