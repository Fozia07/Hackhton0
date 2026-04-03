#!/usr/bin/env python3
"""
Social Media Orchestrator
=========================

Gold Tier Phase 2 - Unified Social Media Posting Architecture

Enterprise-grade orchestration layer for all social media posting agents.
Routes approved posts to the correct platform agent with full retry handling,
audit logging, and watchdog integration.

Supported Platforms:
- Facebook  (FACEBOOK_POST_*.md)
- Instagram (INSTAGRAM_POST_*.md)
- Twitter/X (TWITTER_POST_*.md)
- LinkedIn  (LINKEDIN_POST_*.md)

Usage:
    python3 scripts/social_media_orchestrator.py              # Daemon mode
    python3 scripts/social_media_orchestrator.py --once       # Single cycle
    python3 scripts/social_media_orchestrator.py --dry-run    # No file changes
    python3 scripts/social_media_orchestrator.py --simulate   # No actual posting
    python3 scripts/social_media_orchestrator.py --verbose    # Debug output

Author: AI Employee System
Version: 1.0.0
"""

import os
import sys
import json
import time
import shutil
import signal
import argparse
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

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
    RetryConfig,
    get_circuit_breaker,
    get_queue_manager
)

from utils.heartbeat import HeartbeatWriter


# ==============================================================================
# CONFIGURATION
# ==============================================================================

class Config:
    """Central configuration for Social Media Orchestrator."""

    # Paths
    BASE_DIR = Path(__file__).parent.parent
    VAULT_DIR = BASE_DIR / "AI_Employee_Vault"

    # Source/Destination folders
    APPROVED_DIR = VAULT_DIR / "Approved"
    DONE_DIR = VAULT_DIR / "Done"
    RETRY_QUEUE_DIR = VAULT_DIR / "Retry_Queue" / "social"
    LOGS_DIR = VAULT_DIR / "Logs"

    # Platform agent scripts
    AGENTS = {
        "facebook": BASE_DIR / "scripts" / "facebook_poster.py",
        "instagram": BASE_DIR / "scripts" / "instagram_poster.py",
        "twitter": BASE_DIR / "scripts" / "twitter_poster.py",
        "linkedin": BASE_DIR / "scripts" / "linkedin_poster.py",
    }

    # File prefixes for platform detection
    PREFIXES = {
        "FACEBOOK_POST_": "facebook",
        "INSTAGRAM_POST_": "instagram",
        "TWITTER_POST_": "twitter",
        "LINKEDIN_POST_": "linkedin",
    }

    # Timing
    SCAN_INTERVAL = 30  # seconds between scans
    MAX_POSTS_PER_CYCLE = 10

    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAYS = [30, 60, 300]  # seconds


# ==============================================================================
# ENUMERATIONS
# ==============================================================================

class Platform(Enum):
    """Supported social media platforms."""
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    TWITTER = "twitter"
    LINKEDIN = "linkedin"
    UNKNOWN = "unknown"


class PostStatus(Enum):
    """Post processing status."""
    PENDING = "pending"
    ROUTING = "routing"
    POSTING = "posting"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    QUEUED = "queued"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class SocialPost:
    """Represents a social media post to be processed."""
    id: str
    filename: str
    filepath: Path
    platform: Platform
    content: str
    metadata: Dict[str, Any]
    status: PostStatus = PostStatus.PENDING
    attempts: int = 0
    last_error: Optional[str] = None
    created_at: datetime = None
    processed_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "filename": self.filename,
            "filepath": str(self.filepath),
            "platform": self.platform.value,
            "content_preview": self.content[:200] if self.content else "",
            "status": self.status.value,
            "attempts": self.attempts,
            "last_error": self.last_error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
        }


@dataclass
class CycleResult:
    """Result of a processing cycle."""
    cycle_id: str
    started_at: datetime
    ended_at: datetime
    posts_detected: int
    posts_routed: int
    posts_success: int
    posts_failed: int
    posts_queued: int
    by_platform: Dict[str, int]
    errors: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat(),
            "duration_seconds": (self.ended_at - self.started_at).total_seconds(),
            "posts_detected": self.posts_detected,
            "posts_routed": self.posts_routed,
            "posts_success": self.posts_success,
            "posts_failed": self.posts_failed,
            "posts_queued": self.posts_queued,
            "by_platform": self.by_platform,
            "errors": self.errors,
        }


# ==============================================================================
# CUSTOM ACTION TYPES
# ==============================================================================

class SocialActionType(Enum):
    """Custom action types for social media operations."""
    SOCIAL_POST_DETECTED = "social_post_detected"
    SOCIAL_POST_ROUTED = "social_post_routed"
    SOCIAL_POST_STARTED = "social_post_started"
    SOCIAL_POST_SUCCESS = "social_post_success"
    SOCIAL_POST_FAILED = "social_post_failed"
    SOCIAL_POST_RETRIED = "social_post_retried"
    SOCIAL_POST_QUEUED = "social_post_queued"
    SOCIAL_CYCLE_STARTED = "social_cycle_started"
    SOCIAL_CYCLE_COMPLETED = "social_cycle_completed"


# ==============================================================================
# PLATFORM DETECTOR
# ==============================================================================

class PlatformDetector:
    """Detects social media platform from filename."""

    @staticmethod
    def detect(filename: str) -> Platform:
        """
        Detect platform from filename prefix.

        Args:
            filename: Name of the post file

        Returns:
            Platform enum value
        """
        filename_upper = filename.upper()

        for prefix, platform_name in Config.PREFIXES.items():
            if filename_upper.startswith(prefix):
                return Platform(platform_name)

        # Try content-based detection as fallback
        return Platform.UNKNOWN

    @staticmethod
    def detect_from_content(content: str) -> Platform:
        """
        Fallback detection from post content.

        Args:
            content: Post content

        Returns:
            Platform enum value
        """
        content_lower = content.lower()

        if "platform: facebook" in content_lower or "#facebook" in content_lower:
            return Platform.FACEBOOK
        elif "platform: instagram" in content_lower or "#instagram" in content_lower:
            return Platform.INSTAGRAM
        elif "platform: twitter" in content_lower or "#twitter" in content_lower:
            return Platform.TWITTER
        elif "platform: linkedin" in content_lower or "#linkedin" in content_lower:
            return Platform.LINKEDIN

        return Platform.UNKNOWN


# ==============================================================================
# PLATFORM ROUTER
# ==============================================================================

class PlatformRouter:
    """Routes posts to appropriate platform agents."""

    def __init__(self, simulate: bool = False, verbose: bool = False):
        self.simulate = simulate
        self.verbose = verbose
        self._agent_status: Dict[str, bool] = {}

    def _log(self, message: str):
        """Log message if verbose mode enabled."""
        if self.verbose:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] [ROUTER] {message}")

    def _build_agent_command(
        self,
        agent_path: Path,
        post_filepath: Path,
        simulate: bool = False,
        verbose: bool = False
    ) -> List[str]:
        """
        Build clean command list for agent subprocess.

        FIX: Avoid adding empty strings to argument list.
        Only append flags when they are actually enabled.

        Args:
            agent_path: Path to the agent script
            post_filepath: Path to the post file
            simulate: Whether to run in simulate mode
            verbose: Whether to enable verbose output

        Returns:
            List of command arguments for subprocess
        """
        # Start with required arguments
        cmd = [
            sys.executable,
            str(agent_path),
            "--file", str(post_filepath),  # Required: pass post file path
        ]

        # Only append optional flags if enabled (avoid empty strings!)
        if simulate:
            cmd.append("--simulate")

        if verbose:
            cmd.append("--verbose")

        return cmd

    def check_agent_available(self, platform: Platform) -> bool:
        """Check if platform agent script exists."""
        if platform == Platform.UNKNOWN:
            return False

        agent_path = Config.AGENTS.get(platform.value)
        if agent_path and agent_path.exists():
            return True

        self._log(f"Agent not found for {platform.value}: {agent_path}")
        return False

    def route(
        self,
        post: SocialPost,
        dry_run: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """
        Route a post to its platform agent.

        Args:
            post: The social post to route
            dry_run: If True, don't execute agent

        Returns:
            Tuple of (success, error_message)
        """
        if post.platform == Platform.UNKNOWN:
            return False, "Unknown platform - cannot route"

        agent_path = Config.AGENTS.get(post.platform.value)

        if not agent_path or not agent_path.exists():
            return False, f"Agent not available for {post.platform.value}"

        self._log(f"Routing to {post.platform.value}: {post.filename}")

        if self.simulate:
            self._log(f"[SIMULATE] Would invoke: {agent_path}")
            time.sleep(0.5)  # Simulate processing time
            return True, None

        if dry_run:
            self._log(f"[DRY-RUN] Would invoke: {agent_path}")
            return True, None

        # Execute agent using clean command builder
        try:
            # FIX: Use command builder to avoid empty string arguments
            cmd = self._build_agent_command(
                agent_path=agent_path,
                post_filepath=post.filepath,
                simulate=False,  # Not simulate mode - actually post
                verbose=self.verbose
            )

            self._log(f"Executing: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(Config.BASE_DIR)
            )

            if result.returncode == 0:
                self._log(f"Agent success for {post.filename}")
                return True, None
            else:
                error = result.stderr or result.stdout or "Unknown error"
                self._log(f"Agent failed: {error[:200]}")
                return False, error[:500]

        except subprocess.TimeoutExpired:
            return False, "Agent timeout after 120 seconds"
        except Exception as e:
            return False, str(e)


# ==============================================================================
# SOCIAL MEDIA ORCHESTRATOR
# ==============================================================================

class SocialMediaOrchestrator:
    """
    Main orchestrator for social media posting.

    Coordinates detection, routing, retry handling, and logging
    for all social media posts.
    """

    ACTOR = "social_media_orchestrator"

    def __init__(
        self,
        dry_run: bool = False,
        simulate: bool = False,
        verbose: bool = False
    ):
        self.dry_run = dry_run
        self.simulate = simulate
        self.verbose = verbose
        self.running = True

        # Initialize components
        self.audit_logger = get_audit_logger()
        self.retry_handler = get_retry_handler(
            actor=self.ACTOR,
            circuit_breaker="social_posting"
        )
        self.circuit_breaker = get_circuit_breaker("social_posting")
        self.queue_manager = get_queue_manager()
        self.router = PlatformRouter(simulate=simulate, verbose=verbose)
        self.heartbeat = HeartbeatWriter(self.ACTOR)

        # Ensure directories exist
        Config.APPROVED_DIR.mkdir(parents=True, exist_ok=True)
        Config.DONE_DIR.mkdir(parents=True, exist_ok=True)
        Config.RETRY_QUEUE_DIR.mkdir(parents=True, exist_ok=True)
        Config.LOGS_DIR.mkdir(parents=True, exist_ok=True)

        # Statistics
        self._total_processed = 0
        self._total_success = 0
        self._total_failed = 0

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self._log("Shutdown signal received...")
        self.running = False

    def _log(self, message: str, level: str = "INFO"):
        """Print timestamped log message."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")

    def _debug(self, message: str):
        """Print debug message if verbose."""
        if self.verbose:
            self._log(message, "DEBUG")

    def _audit_log(
        self,
        action: str,
        target: str,
        parameters: Dict[str, Any] = None,
        result: ResultStatus = ResultStatus.SUCCESS,
        error: str = None
    ):
        """Log action to audit system."""
        self.audit_logger.log(
            action_type=ActionType.TASK_STARTED,  # Using existing type
            actor=self.ACTOR,
            target=target,
            parameters={
                "custom_action": action,
                **(parameters or {})
            },
            result=result,
            error=error
        )

    def _generate_post_id(self, filepath: Path) -> str:
        """Generate unique post ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"POST_{timestamp}_{filepath.stem[:20]}"

    def scan_approved_posts(self) -> List[SocialPost]:
        """
        Scan Approved folder for social media posts.

        Returns:
            List of SocialPost objects
        """
        posts = []

        if not Config.APPROVED_DIR.exists():
            return posts

        for filepath in Config.APPROVED_DIR.glob("*.md"):
            # Skip non-social posts
            platform = PlatformDetector.detect(filepath.name)

            if platform == Platform.UNKNOWN:
                # Try content-based detection
                try:
                    content = filepath.read_text(encoding='utf-8')
                    platform = PlatformDetector.detect_from_content(content)
                except Exception:
                    continue

            if platform == Platform.UNKNOWN:
                continue  # Not a social media post

            # Parse post content
            try:
                content = filepath.read_text(encoding='utf-8')
                metadata = self._parse_frontmatter(content)
            except Exception as e:
                self._debug(f"Error reading {filepath.name}: {e}")
                continue

            post = SocialPost(
                id=self._generate_post_id(filepath),
                filename=filepath.name,
                filepath=filepath,
                platform=platform,
                content=content,
                metadata=metadata
            )

            posts.append(post)

            # Limit posts per cycle
            if len(posts) >= Config.MAX_POSTS_PER_CYCLE:
                break

        return posts

    def _parse_frontmatter(self, content: str) -> Dict[str, Any]:
        """Parse YAML frontmatter from content."""
        metadata = {}

        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                try:
                    for line in parts[1].strip().split('\n'):
                        if ':' in line:
                            key, value = line.split(':', 1)
                            metadata[key.strip()] = value.strip()
                except Exception:
                    pass

        return metadata

    def process_post(self, post: SocialPost) -> bool:
        """
        Process a single social media post.

        Args:
            post: The post to process

        Returns:
            True if successful, False otherwise
        """
        start_time = datetime.now()
        post.status = PostStatus.ROUTING

        self._debug(f"Processing: {post.filename} -> {post.platform.value}")

        # Log detection
        self._audit_log(
            action=SocialActionType.SOCIAL_POST_DETECTED.value,
            target=post.filename,
            parameters={
                "platform": post.platform.value,
                "post_id": post.id
            }
        )

        # Check circuit breaker
        if not self.circuit_breaker.can_execute():
            self._log(f"Circuit breaker open - queuing {post.filename}", "WARN")
            self._queue_post(post, "circuit_breaker_open")
            return False

        # Log routing
        self._audit_log(
            action=SocialActionType.SOCIAL_POST_ROUTED.value,
            target=post.filename,
            parameters={
                "platform": post.platform.value,
                "agent": str(Config.AGENTS.get(post.platform.value, "none"))
            }
        )

        # Attempt posting with retry
        post.status = PostStatus.POSTING
        success = False
        last_error = None

        for attempt in range(1, Config.MAX_RETRIES + 1):
            post.attempts = attempt

            # Log attempt
            self._audit_log(
                action=SocialActionType.SOCIAL_POST_STARTED.value,
                target=post.filename,
                parameters={
                    "platform": post.platform.value,
                    "attempt": attempt,
                    "max_attempts": Config.MAX_RETRIES
                },
                result=ResultStatus.PENDING
            )

            # Route to platform agent
            success, error = self.router.route(post, dry_run=self.dry_run)

            if success:
                post.status = PostStatus.SUCCESS
                post.processed_at = datetime.now()

                # Log success
                self._audit_log(
                    action=SocialActionType.SOCIAL_POST_SUCCESS.value,
                    target=post.filename,
                    parameters={
                        "platform": post.platform.value,
                        "attempts": attempt,
                        "duration_ms": (datetime.now() - start_time).total_seconds() * 1000
                    }
                )

                # Move to Done
                self._move_to_done(post)
                self.circuit_breaker.record_success()

                self._log(f"SUCCESS: {post.filename} -> {post.platform.value}")
                return True

            else:
                last_error = error
                post.last_error = error

                # Log retry
                if attempt < Config.MAX_RETRIES:
                    self._audit_log(
                        action=SocialActionType.SOCIAL_POST_RETRIED.value,
                        target=post.filename,
                        parameters={
                            "platform": post.platform.value,
                            "attempt": attempt,
                            "error": error[:200] if error else "Unknown"
                        },
                        result=ResultStatus.PENDING
                    )

                    delay = Config.RETRY_DELAYS[min(attempt - 1, len(Config.RETRY_DELAYS) - 1)]
                    self._log(f"Retry {attempt}/{Config.MAX_RETRIES} in {delay}s: {post.filename}", "WARN")

                    if not self.simulate:
                        time.sleep(delay)

        # All retries exhausted
        post.status = PostStatus.FAILED
        self.circuit_breaker.record_failure(Exception(last_error or "Unknown error"))

        # Log failure
        self._audit_log(
            action=SocialActionType.SOCIAL_POST_FAILED.value,
            target=post.filename,
            parameters={
                "platform": post.platform.value,
                "attempts": post.attempts,
                "error": last_error[:200] if last_error else "Unknown"
            },
            result=ResultStatus.FAILURE,
            error=last_error
        )

        # Queue for later retry
        self._queue_post(post, last_error)

        self._log(f"FAILED: {post.filename} after {post.attempts} attempts", "ERROR")
        return False

    def _move_to_done(self, post: SocialPost):
        """Move successfully posted file to Done folder."""
        if self.dry_run:
            self._debug(f"[DRY-RUN] Would move {post.filename} to Done/")
            return

        try:
            dest = Config.DONE_DIR / post.filename
            counter = 1
            while dest.exists():
                dest = Config.DONE_DIR / f"{post.filepath.stem}_{counter}{post.filepath.suffix}"
                counter += 1

            shutil.move(str(post.filepath), str(dest))
            self._debug(f"Moved to Done: {dest.name}")
        except Exception as e:
            self._log(f"Error moving to Done: {e}", "ERROR")

    def _queue_post(self, post: SocialPost, reason: str):
        """Queue failed post for later retry."""
        if self.dry_run:
            self._debug(f"[DRY-RUN] Would queue {post.filename}")
            return

        try:
            # Create queue entry
            queue_entry = {
                "original_file": post.filename,
                "platform": post.platform.value,
                "attempts": post.attempts,
                "last_error": reason,
                "queued_at": datetime.now().isoformat(),
                "content_preview": post.content[:500] if post.content else ""
            }

            # Move file to retry queue
            dest = Config.RETRY_QUEUE_DIR / post.filename
            shutil.move(str(post.filepath), str(dest))

            # Write metadata
            meta_file = Config.RETRY_QUEUE_DIR / f"{post.filename}.meta.json"
            with open(meta_file, 'w') as f:
                json.dump(queue_entry, f, indent=2)

            # Log queuing
            self._audit_log(
                action=SocialActionType.SOCIAL_POST_QUEUED.value,
                target=post.filename,
                parameters={
                    "platform": post.platform.value,
                    "reason": reason[:200] if reason else "Unknown"
                }
            )

            self._debug(f"Queued for retry: {post.filename}")

        except Exception as e:
            self._log(f"Error queuing post: {e}", "ERROR")

    def run_cycle(self) -> CycleResult:
        """
        Execute a single processing cycle.

        Returns:
            CycleResult with cycle statistics
        """
        cycle_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        started_at = datetime.now()
        errors = []
        by_platform = {p.value: 0 for p in Platform if p != Platform.UNKNOWN}

        posts_detected = 0
        posts_routed = 0
        posts_success = 0
        posts_failed = 0
        posts_queued = 0

        # Update heartbeat
        self.heartbeat.update_task(f"cycle:{cycle_id}")

        self._debug(f"=== Starting cycle {cycle_id} ===")

        # Log cycle start
        self._audit_log(
            action=SocialActionType.SOCIAL_CYCLE_STARTED.value,
            target=cycle_id,
            parameters={
                "dry_run": self.dry_run,
                "simulate": self.simulate
            },
            result=ResultStatus.PENDING
        )

        try:
            # Scan for posts
            posts = self.scan_approved_posts()
            posts_detected = len(posts)

            if posts:
                self._log(f"Found {posts_detected} social media post(s)")

                # Group by platform
                for post in posts:
                    by_platform[post.platform.value] = by_platform.get(post.platform.value, 0) + 1

                # Process each post
                for post in posts:
                    posts_routed += 1

                    try:
                        if self.process_post(post):
                            posts_success += 1
                            self._total_success += 1
                        else:
                            posts_failed += 1
                            posts_queued += 1
                            self._total_failed += 1

                        self._total_processed += 1

                    except Exception as e:
                        posts_failed += 1
                        errors.append(f"{post.filename}: {str(e)}")
                        self._log(f"Error processing {post.filename}: {e}", "ERROR")

            else:
                self._debug("No social media posts found in Approved/")

        except Exception as e:
            errors.append(str(e))
            self._log(f"Cycle error: {e}", "ERROR")

        ended_at = datetime.now()

        result = CycleResult(
            cycle_id=cycle_id,
            started_at=started_at,
            ended_at=ended_at,
            posts_detected=posts_detected,
            posts_routed=posts_routed,
            posts_success=posts_success,
            posts_failed=posts_failed,
            posts_queued=posts_queued,
            by_platform=by_platform,
            errors=errors
        )

        # Log cycle completion
        self._audit_log(
            action=SocialActionType.SOCIAL_CYCLE_COMPLETED.value,
            target=cycle_id,
            parameters=result.to_dict(),
            result=ResultStatus.SUCCESS if not errors else ResultStatus.PARTIAL
        )

        # Update heartbeat
        self.heartbeat.update_task("idle")

        if posts_detected > 0:
            self._log(
                f"Cycle complete: {posts_success}/{posts_detected} success, "
                f"{posts_failed} failed, {posts_queued} queued"
            )

        return result

    def run_once(self):
        """Run a single cycle and exit."""
        self._log("Running single cycle")
        self.heartbeat.start()

        if self.simulate:
            self._log("SIMULATION MODE - No actual posting")
        if self.dry_run:
            self._log("DRY-RUN MODE - No file changes")

        try:
            result = self.run_cycle()

            print("\n" + "=" * 50)
            print("CYCLE RESULT")
            print("=" * 50)
            print(f"Posts detected: {result.posts_detected}")
            print(f"Posts success:  {result.posts_success}")
            print(f"Posts failed:   {result.posts_failed}")
            print(f"Posts queued:   {result.posts_queued}")
            print(f"Duration:       {(result.ended_at - result.started_at).total_seconds():.2f}s")
            print("=" * 50)

        finally:
            self.heartbeat.stop()
            self.audit_logger.flush()

    def run_daemon(self):
        """Run continuously as a daemon."""
        self._log("Starting Social Media Orchestrator in daemon mode")
        self._log(f"Scan interval: {Config.SCAN_INTERVAL} seconds")

        if self.simulate:
            self._log("SIMULATION MODE - No actual posting")
        if self.dry_run:
            self._log("DRY-RUN MODE - No file changes")

        self.heartbeat.start()
        total_cycles = 0

        try:
            while self.running:
                result = self.run_cycle()
                total_cycles += 1

                if self.running:
                    self.heartbeat.update_task("sleeping")

                    # Sleep in increments for graceful shutdown
                    sleep_remaining = Config.SCAN_INTERVAL
                    while sleep_remaining > 0 and self.running:
                        time.sleep(min(5, sleep_remaining))
                        sleep_remaining -= 5

        except KeyboardInterrupt:
            self._log("Interrupted by user")
        finally:
            self.heartbeat.stop()
            self.audit_logger.flush()

            print("\n" + "=" * 50)
            print("FINAL SUMMARY")
            print("=" * 50)
            print(f"Total cycles:    {total_cycles}")
            print(f"Total processed: {self._total_processed}")
            print(f"Total success:   {self._total_success}")
            print(f"Total failed:    {self._total_failed}")
            print("=" * 50)

        self._log("Social Media Orchestrator stopped")


# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Social Media Orchestrator - Unified posting system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/social_media_orchestrator.py              # Daemon mode
  python3 scripts/social_media_orchestrator.py --once       # Single cycle
  python3 scripts/social_media_orchestrator.py --dry-run    # Test without changes
  python3 scripts/social_media_orchestrator.py --simulate   # No actual posting
  python3 scripts/social_media_orchestrator.py --verbose    # Debug output
        """
    )

    parser.add_argument(
        '--once',
        action='store_true',
        help='Run a single cycle and exit'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simulate actions without file changes'
    )

    parser.add_argument(
        '--simulate',
        action='store_true',
        help='Simulation mode - no actual posting to platforms'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose (debug) output'
    )

    parser.add_argument(
        '--daemon',
        action='store_true',
        help='Run continuously (default if --once not specified)'
    )

    args = parser.parse_args()

    # Banner
    print("=" * 60)
    print("   Social Media Orchestrator")
    print("   Gold Tier Phase 2 - Unified Posting Architecture")
    print("=" * 60)
    print(f"   Mode: {'Single Cycle' if args.once else 'Daemon (Continuous)'}")
    print(f"   Dry Run: {args.dry_run}")
    print(f"   Simulate: {args.simulate}")
    print(f"   Verbose: {args.verbose}")
    print("=" * 60)
    print()

    # Create orchestrator
    orchestrator = SocialMediaOrchestrator(
        dry_run=args.dry_run,
        simulate=args.simulate,
        verbose=args.verbose
    )

    # Run
    if args.once:
        orchestrator.run_once()
    else:
        orchestrator.run_daemon()


if __name__ == "__main__":
    main()
