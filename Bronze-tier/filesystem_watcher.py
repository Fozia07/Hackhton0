#!/usr/bin/env python3
"""
Bronze Tier Filesystem Watcher
Enhanced with Gold Tier Audit Logging & Error Recovery

Monitors the Inbox folder for new files and moves them to Needs_Action
with metadata generation, comprehensive audit logging, and retry handling.
"""

import os
import sys
import shutil
import time
from datetime import datetime
from pathlib import Path

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
    FailureClassifier,
    get_circuit_breaker
)

from utils.heartbeat import HeartbeatWriter

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VAULT_DIR = os.path.join(BASE_DIR, "AI_Employee_Vault")
INBOX_DIR = os.path.join(VAULT_DIR, "Inbox")
NEEDS_ACTION_DIR = os.path.join(VAULT_DIR, "Needs_Action")
POLL_INTERVAL = 2  # seconds

# Actor name for audit logging
ACTOR = "filesystem_watcher"

# Initialize audit logger
audit_logger = get_audit_logger()

# Initialize heartbeat for watchdog monitoring
heartbeat_writer = HeartbeatWriter(ACTOR)

# Initialize retry handler with circuit breaker
retry_config = RetryConfig(
    max_retries=3,
    base_delay=1.0,
    max_delay=30.0
)
retry_handler = get_retry_handler(
    actor=ACTOR,
    circuit_breaker="filesystem_operations"
)
circuit_breaker = get_circuit_breaker("filesystem_operations")


def get_metadata_content(filename, detected_time):
    """Generate markdown metadata content for a file."""
    return f"""# Task Metadata

---

**Original Filename:** {filename}

**Date Detected:** {detected_time.strftime("%Y-%m-%d")}

**Time Detected:** {detected_time.strftime("%H:%M:%S")}

**Status:** pending

**Source:** inbox

---
"""


def _do_process_file(filename, source_path, dest_path, metadata_path, detected_time, start_time, file_size):
    """Internal file processing logic (called by retry handler)."""
    # Log inbox detection
    audit_logger.log(
        action_type=ActionType.INBOX_DETECTED,
        actor=ACTOR,
        target=source_path,
        parameters={
            'filename': filename,
            'size_bytes': file_size
        },
        result=ResultStatus.SUCCESS
    )

    # Move the file
    shutil.move(source_path, dest_path)
    print(f"[{detected_time.strftime('%Y-%m-%d %H:%M:%S')}] Moved: {filename} -> Needs_Action/")

    # Log file movement
    audit_logger.log(
        action_type=ActionType.TASK_MOVED,
        actor=ACTOR,
        target=filename,
        parameters={
            'source': INBOX_DIR,
            'destination': NEEDS_ACTION_DIR,
            'size_bytes': file_size
        },
        result=ResultStatus.SUCCESS
    )

    # Create metadata file
    metadata_content = get_metadata_content(filename, detected_time)
    with open(metadata_path, "w") as f:
        f.write(metadata_content)
    print(f"[{detected_time.strftime('%Y-%m-%d %H:%M:%S')}] Created: {filename}.md")

    # Log task creation
    audit_logger.log_with_duration(
        action_type=ActionType.TASK_CREATED,
        actor=ACTOR,
        target=metadata_path,
        start_time=start_time,
        parameters={
            'original_file': filename,
            'metadata_file': filename + '.md',
            'size_bytes': file_size
        },
        result=ResultStatus.SUCCESS
    )

    return True


def process_file(filename):
    """Move file from Inbox to Needs_Action and create metadata (with retry)."""
    source_path = os.path.join(INBOX_DIR, filename)
    dest_path = os.path.join(NEEDS_ACTION_DIR, filename)
    metadata_path = os.path.join(NEEDS_ACTION_DIR, filename + ".md")

    detected_time = datetime.now()
    start_time = datetime.now()
    file_size = os.path.getsize(source_path) if os.path.exists(source_path) else 0

    # Check circuit breaker
    if not circuit_breaker.can_execute():
        print(f"[{detected_time.strftime('%Y-%m-%d %H:%M:%S')}] CIRCUIT OPEN: Skipping {filename}")
        audit_logger.log(
            action_type=ActionType.WARNING_RAISED,
            actor=ACTOR,
            target=filename,
            parameters={'reason': 'circuit_breaker_open'},
            result=ResultStatus.FAILURE
        )
        return False

    try:
        # Execute with retry handling
        result = retry_handler.execute(
            _do_process_file,
            filename,
            source_path,
            dest_path,
            metadata_path,
            detected_time,
            start_time,
            file_size,
            task_id=f"process_{filename}",
            task_type="file_processing"
        )
        circuit_breaker.record_success()
        return result

    except Exception as e:
        # Log error after all retries exhausted
        circuit_breaker.record_failure(e)
        audit_logger.log_error(
            actor=ACTOR,
            target=source_path,
            error_message=str(e),
            error_type=type(e).__name__,
            parameters={'filename': filename, 'retries_exhausted': True}
        )
        raise


def watch_inbox():
    """Continuously monitor the Inbox folder for new files."""
    print("=" * 50)
    print("Bronze Tier Filesystem Watcher")
    print("With Gold Tier Audit Logging & Error Recovery")
    print("=" * 50)
    print(f"Monitoring: {INBOX_DIR}")
    print(f"Destination: {NEEDS_ACTION_DIR}")
    print(f"Poll interval: {POLL_INTERVAL} seconds")
    print("=" * 50)
    print("Waiting for files... (Press Ctrl+C to stop)")
    print()

    # Start heartbeat for watchdog monitoring
    heartbeat_writer.start()
    heartbeat_writer.update_task("initializing")

    # Log system start
    audit_logger.log(
        action_type=ActionType.SYSTEM_STARTED,
        actor=ACTOR,
        target="inbox_monitor",
        parameters={
            'inbox_dir': INBOX_DIR,
            'destination_dir': NEEDS_ACTION_DIR,
            'poll_interval': POLL_INTERVAL
        },
        result=ResultStatus.SUCCESS
    )

    files_processed = 0
    files_failed = 0

    while True:
        try:
            # Update heartbeat - monitoring
            heartbeat_writer.update_task("monitoring")

            # Get list of files in Inbox (ignore directories)
            files = [f for f in os.listdir(INBOX_DIR)
                     if os.path.isfile(os.path.join(INBOX_DIR, f))]

            # Process each file
            for filename in files:
                try:
                    # Update heartbeat with current file
                    heartbeat_writer.update_task(f"processing:{filename}")

                    if process_file(filename):
                        files_processed += 1
                    else:
                        files_failed += 1
                except Exception as e:
                    print(f"Error processing {filename}: {e}")
                    files_failed += 1

            # Wait before next check
            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print("\nWatcher stopped.")
            print(f"Files processed: {files_processed}, Failed: {files_failed}")
            cb_state = circuit_breaker.get_state()
            print(f"Circuit breaker state: {cb_state['state']}")

            # Log system stop
            audit_logger.log(
                action_type=ActionType.SYSTEM_STOPPED,
                actor=ACTOR,
                target="inbox_monitor",
                parameters={
                    'files_processed': files_processed,
                    'reason': 'user_interrupt'
                },
                result=ResultStatus.SUCCESS
            )
            audit_logger.flush()

            # Stop heartbeat
            heartbeat_writer.update_task("stopped")
            heartbeat_writer.stop()
            break

        except Exception as e:
            # Log error
            audit_logger.log_error(
                actor=ACTOR,
                target="inbox_monitor",
                error_message=str(e),
                error_type=type(e).__name__
            )
            print(f"Error: {e}")
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    watch_inbox()
