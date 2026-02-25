#!/usr/bin/env python3
"""
Bronze Tier Agent Executor
Enhanced with Gold Tier Audit Logging & Error Recovery

Processes tasks from Needs_Action folder, updates metadata,
and moves completed tasks to Done folder with comprehensive audit logging
and retry handling for resilient operation.
"""

import os
import sys
import shutil
import re
from datetime import datetime

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.audit_logger import (
    get_audit_logger,
    ActionType,
    ApprovalStatus,
    ResultStatus
)

from utils.retry_handler import (
    get_retry_handler,
    RetryConfig,
    get_circuit_breaker,
    get_queue_manager
)

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VAULT_DIR = os.path.join(BASE_DIR, "AI_Employee_Vault")
NEEDS_ACTION_DIR = os.path.join(VAULT_DIR, "Needs_Action")
DONE_DIR = os.path.join(VAULT_DIR, "Done")

# Actor name for audit logging
ACTOR = "agent_executor"

# Initialize audit logger
audit_logger = get_audit_logger()

# Initialize retry handler with circuit breaker
retry_config = RetryConfig(
    max_retries=3,
    base_delay=0.5,
    max_delay=15.0
)
retry_handler = get_retry_handler(
    actor=ACTOR,
    circuit_breaker="task_processing"
)
circuit_breaker = get_circuit_breaker("task_processing")
queue_manager = get_queue_manager()


def log(message):
    """Print a timestamped log message."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


def get_metadata_files():
    """Get all .md metadata files in Needs_Action folder."""
    files = []
    for filename in os.listdir(NEEDS_ACTION_DIR):
        if filename.endswith(".md"):
            files.append(filename)
    return files


def read_metadata(metadata_path):
    """Read metadata file content."""
    with open(metadata_path, "r") as f:
        return f.read()


def update_metadata_content(content):
    """Update metadata: change status to completed, add completion timestamp."""
    completion_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Update status from pending to completed
    updated = re.sub(
        r"\*\*Status:\*\*\s*pending",
        "**Status:** completed",
        content
    )

    # Also handle lowercase status field
    updated = re.sub(
        r"Status:\s*pending",
        "Status: completed",
        updated
    )

    # Add completion timestamp after Status line
    if "**Completion Time:**" not in updated:
        updated = re.sub(
            r"(\*\*Status:\*\*\s*completed)",
            f"\\1\n\n**Completion Time:** {completion_time}",
            updated
        )

    # Add processing note
    if "## Processing Log" not in updated:
        updated += f"\n\n## Processing Log\n\n"
        updated += f"| Timestamp | Action |\n"
        updated += f"|-----------|--------|\n"
        updated += f"| {completion_time} | Task processed by agent_executor |\n"
        updated += f"| {completion_time} | Status changed: pending → completed |\n"
        updated += f"| {completion_time} | Moved to Done folder |\n"

    return updated


def write_metadata(metadata_path, content):
    """Write updated content to metadata file."""
    with open(metadata_path, "w") as f:
        f.write(content)


def move_to_done(filename):
    """Move file from Needs_Action to Done."""
    source = os.path.join(NEEDS_ACTION_DIR, filename)
    destination = os.path.join(DONE_DIR, filename)
    shutil.move(source, destination)
    return destination


def _execute_task_processing(metadata_filename, task_filename, metadata_path, start_time):
    """Internal task processing logic (called by retry handler)."""
    # Step 1: Read metadata
    log(f"  Reading metadata...")
    content = read_metadata(metadata_path)
    log(f"  Metadata read successfully")

    # Step 2: Update metadata
    log(f"  Updating status: pending → completed")
    updated_content = update_metadata_content(content)
    write_metadata(metadata_path, updated_content)
    log(f"  Metadata updated")

    # Step 3: Move metadata file to Done
    log(f"  Moving metadata to Done/")
    move_to_done(metadata_filename)

    # Log metadata movement
    audit_logger.log(
        action_type=ActionType.TASK_MOVED,
        actor=ACTOR,
        target=metadata_filename,
        parameters={
            'source': NEEDS_ACTION_DIR,
            'destination': DONE_DIR,
            'file_type': 'metadata'
        },
        result=ResultStatus.SUCCESS
    )

    # Step 4: Move task file to Done (if exists)
    if task_filename:
        task_path = os.path.join(NEEDS_ACTION_DIR, task_filename)
        if os.path.exists(task_path):
            log(f"  Moving task file to Done/")
            move_to_done(task_filename)

            # Log task file movement
            audit_logger.log(
                action_type=ActionType.TASK_MOVED,
                actor=ACTOR,
                target=task_filename,
                parameters={
                    'source': NEEDS_ACTION_DIR,
                    'destination': DONE_DIR,
                    'file_type': 'task'
                },
                result=ResultStatus.SUCCESS
            )
        else:
            log(f"  No task file found (metadata only)")

    log(f"  Task completed successfully")

    # Log task completed
    audit_logger.log_with_duration(
        action_type=ActionType.TASK_COMPLETED,
        actor=ACTOR,
        target=metadata_filename,
        start_time=start_time,
        parameters={
            'metadata_file': metadata_filename,
            'task_file': task_filename,
            'destination': DONE_DIR
        },
        result=ResultStatus.SUCCESS
    )

    return True


def process_task(metadata_filename):
    """Process a single task: read, update, move (with retry handling)."""
    start_time = datetime.now()
    log(f"Processing: {metadata_filename}")

    # Check circuit breaker
    if not circuit_breaker.can_execute():
        log(f"  CIRCUIT OPEN: Skipping task processing")
        audit_logger.log(
            action_type=ActionType.WARNING_RAISED,
            actor=ACTOR,
            target=metadata_filename,
            parameters={'reason': 'circuit_breaker_open'},
            result=ResultStatus.FAILURE
        )
        return False

    # Log task started
    audit_logger.log(
        action_type=ActionType.TASK_STARTED,
        actor=ACTOR,
        target=metadata_filename,
        parameters={'source_folder': 'Needs_Action'},
        result=ResultStatus.PENDING
    )

    # Determine task file name (remove .md extension if double extension)
    # e.g., "task.txt.md" -> "task.txt"
    if metadata_filename.endswith(".md"):
        task_filename = metadata_filename[:-3]  # Remove .md
    else:
        task_filename = None

    metadata_path = os.path.join(NEEDS_ACTION_DIR, metadata_filename)

    try:
        # Execute with retry handling
        result = retry_handler.execute(
            _execute_task_processing,
            metadata_filename,
            task_filename,
            metadata_path,
            start_time,
            task_id=f"task_{metadata_filename}",
            task_type="task_processing"
        )
        circuit_breaker.record_success()
        return result

    except Exception as e:
        # Log task failed after all retries
        circuit_breaker.record_failure(e)
        audit_logger.log_with_duration(
            action_type=ActionType.TASK_FAILED,
            actor=ACTOR,
            target=metadata_filename,
            start_time=start_time,
            parameters={
                'metadata_file': metadata_filename,
                'retries_exhausted': True
            },
            result=ResultStatus.FAILURE,
            error=str(e)
        )
        raise


def run_agent():
    """Main agent loop - process all tasks in Needs_Action."""
    print("=" * 60)
    print("Bronze Tier Agent Executor")
    print("With Gold Tier Audit Logging & Error Recovery")
    print("=" * 60)
    print(f"Source:      {NEEDS_ACTION_DIR}")
    print(f"Destination: {DONE_DIR}")
    print("=" * 60)
    print()

    # Log system start
    audit_logger.log(
        action_type=ActionType.SYSTEM_STARTED,
        actor=ACTOR,
        target="task_processor",
        parameters={
            'source_dir': NEEDS_ACTION_DIR,
            'destination_dir': DONE_DIR
        },
        result=ResultStatus.SUCCESS
    )

    # Get all metadata files
    metadata_files = get_metadata_files()

    if not metadata_files:
        log("No tasks found in Needs_Action/")
        print("\nAgent finished - nothing to process.")

        # Log no tasks
        audit_logger.log(
            action_type=ActionType.SYSTEM_STOPPED,
            actor=ACTOR,
            target="task_processor",
            parameters={'reason': 'no_tasks_found'},
            result=ResultStatus.SUCCESS
        )
        audit_logger.flush()
        return

    log(f"Found {len(metadata_files)} task(s) to process")
    print()

    # Process each task
    processed = 0
    failed = 0

    for metadata_file in metadata_files:
        try:
            process_task(metadata_file)
            processed += 1
            print()
        except Exception as e:
            log(f"  ERROR: {e}")

            # Log error
            audit_logger.log_error(
                actor=ACTOR,
                target=metadata_file,
                error_message=str(e),
                error_type=type(e).__name__
            )
            failed += 1
            print()

    # Summary
    print("=" * 60)
    print("EXECUTION SUMMARY")
    print("=" * 60)
    print(f"Tasks processed: {processed}")
    print(f"Tasks failed:    {failed}")
    print(f"Total:           {len(metadata_files)}")

    # Circuit breaker status
    cb_state = circuit_breaker.get_state()
    print(f"Circuit State:   {cb_state['state']}")

    # Retry queue status
    queue_stats = queue_manager.get_queue_stats()
    if queue_stats['total_tasks'] > 0:
        print(f"Retry Queue:     {queue_stats['total_tasks']} tasks pending")

    print("=" * 60)

    # Log system stop
    audit_logger.log(
        action_type=ActionType.SYSTEM_STOPPED,
        actor=ACTOR,
        target="task_processor",
        parameters={
            'tasks_processed': processed,
            'tasks_failed': failed,
            'total_tasks': len(metadata_files)
        },
        result=ResultStatus.SUCCESS if failed == 0 else ResultStatus.PARTIAL
    )
    audit_logger.flush()


if __name__ == "__main__":
    run_agent()
