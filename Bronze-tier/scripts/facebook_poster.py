#!/usr/bin/env python3
"""
Facebook Poster Agent
=====================

Gold Tier Phase 2 - Step 2
Production-grade Facebook posting agent with Playwright automation.

Integrates with social_media_orchestrator.py for unified posting.

Usage:
    python3 scripts/facebook_poster.py --file <path>
    python3 scripts/facebook_poster.py --file <path> --simulate
    python3 scripts/facebook_poster.py --file <path> --live --verbose
    python3 scripts/facebook_poster.py --file <path> --live --headless

Environment Variables (for --live mode):
    FACEBOOK_EMAIL    - Facebook login email
    FACEBOOK_PASSWORD - Facebook login password

Exit Codes:
    0 - Success
    1 - Validation error
    2 - Posting failure

Author: AI Employee System
Version: 2.0.0
"""

import os
import sys
import re
import json
import time
import random
import string
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables from .env file
from utils.env_loader import load_env
load_env()

# Configure logging for live automation
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("facebook_poster")

from utils.audit_logger import (
    get_audit_logger,
    ActionType,
    ResultStatus
)

from utils.heartbeat import HeartbeatWriter


# ==============================================================================
# CONSTANTS
# ==============================================================================

class ExitCode:
    """Exit codes for the agent."""
    SUCCESS = 0
    VALIDATION_ERROR = 1
    POSTING_FAILURE = 2


class FacebookActionType(Enum):
    """Custom action types for Facebook operations."""
    FACEBOOK_POST_STARTED = "facebook_post_started"
    FACEBOOK_POST_VALIDATED = "facebook_post_validated"
    FACEBOOK_POST_SUCCESS = "facebook_post_success"
    FACEBOOK_POST_FAILED = "facebook_post_failed"


# ==============================================================================
# CONFIGURATION
# ==============================================================================

class Config:
    """Facebook poster configuration."""

    # Validation
    MIN_CONTENT_LENGTH = 20
    MAX_CONTENT_LENGTH = 63206  # Facebook limit

    # Banned content markers
    BANNED_PATTERNS = [
        "[FORCE_FAIL]",
        "[PLACEHOLDER]",
        "[TODO]",
        "[INSERT",
        "{{",
        "}}",
    ]

    # Simulation settings
    MIN_LATENCY = 1.0  # seconds
    MAX_LATENCY = 2.0  # seconds

    # Agent identity
    ACTOR = "facebook_poster"
    PLATFORM = "facebook"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class ParsedPost:
    """Parsed Facebook post data."""
    filepath: Path
    title: Optional[str]
    body: str
    hashtags: List[str]
    media_references: List[str]
    metadata: Dict[str, Any]
    raw_content: str

    @property
    def full_content(self) -> str:
        """Get full post content for Facebook."""
        parts = []

        if self.title:
            parts.append(self.title)
            parts.append("")  # Empty line

        parts.append(self.body)

        if self.hashtags:
            parts.append("")
            parts.append(" ".join(self.hashtags))

        return "\n".join(parts)

    @property
    def content_length(self) -> int:
        """Get content length."""
        return len(self.full_content)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "filepath": str(self.filepath),
            "title": self.title,
            "body_preview": self.body[:200] if self.body else "",
            "hashtags": self.hashtags,
            "media_references": self.media_references,
            "content_length": self.content_length,
        }


@dataclass
class ValidationResult:
    """Result of post validation."""
    valid: bool
    errors: List[str]
    warnings: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PostResult:
    """Result of posting operation."""
    status: str  # "success" or "failed"
    platform: str
    post_id: Optional[str]
    timestamp: str
    error: Optional[str] = None
    simulated: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "platform": self.platform,
            "post_id": self.post_id,
            "timestamp": self.timestamp,
            "error": self.error,
            "simulated": self.simulated,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


# ==============================================================================
# POST LOADER
# ==============================================================================

def load_post(filepath: Path, verbose: bool = False) -> ParsedPost:
    """
    Load and parse a post file.

    Args:
        filepath: Path to the markdown post file
        verbose: Enable verbose output

    Returns:
        ParsedPost object with parsed content

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file cannot be parsed
    """
    if verbose:
        print(f"[DEBUG] Loading post from: {filepath}")

    if not filepath.exists():
        raise FileNotFoundError(f"Post file not found: {filepath}")

    # Read raw content
    raw_content = filepath.read_text(encoding='utf-8')

    if not raw_content.strip():
        raise ValueError("Post file is empty")

    # Parse frontmatter and body
    metadata = {}
    body = raw_content
    title = None

    if raw_content.startswith('---'):
        parts = raw_content.split('---', 2)
        if len(parts) >= 3:
            # Parse YAML-like frontmatter
            for line in parts[1].strip().split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    metadata[key.strip().lower()] = value.strip()
            body = parts[2].strip()

    # Extract title (first # heading or metadata title)
    if 'title' in metadata:
        title = metadata['title']
    else:
        title_match = re.search(r'^#\s+(.+)$', body, re.MULTILINE)
        if title_match:
            title = title_match.group(1).strip()
            # Remove title from body
            body = re.sub(r'^#\s+.+\n?', '', body, count=1).strip()

    # Extract hashtags
    hashtags = re.findall(r'#\w+', body)

    # Remove hashtags from end of body if they're grouped together
    body_lines = body.split('\n')
    clean_body_lines = []
    hashtag_section_started = False

    for line in reversed(body_lines):
        stripped = line.strip()
        if stripped and all(word.startswith('#') for word in stripped.split()):
            hashtag_section_started = True
            continue
        if hashtag_section_started and not stripped:
            continue
        clean_body_lines.insert(0, line)
        hashtag_section_started = False

    body = '\n'.join(clean_body_lines).strip()

    # Extract media references
    media_references = []

    # Markdown images: ![alt](url)
    media_references.extend(re.findall(r'!\[.*?\]\((.+?)\)', raw_content))

    # Media metadata
    if 'image' in metadata:
        media_references.append(metadata['image'])
    if 'media' in metadata:
        media_references.append(metadata['media'])

    if verbose:
        print(f"[DEBUG] Title: {title}")
        print(f"[DEBUG] Body length: {len(body)} chars")
        print(f"[DEBUG] Hashtags: {hashtags}")
        print(f"[DEBUG] Media: {media_references}")

    return ParsedPost(
        filepath=filepath,
        title=title,
        body=body,
        hashtags=hashtags,
        media_references=media_references,
        metadata=metadata,
        raw_content=raw_content,
    )


# ==============================================================================
# POST VALIDATOR
# ==============================================================================

def validate_post(post: ParsedPost, verbose: bool = False) -> ValidationResult:
    """
    Validate a parsed post.

    Args:
        post: ParsedPost to validate
        verbose: Enable verbose output

    Returns:
        ValidationResult with validation status
    """
    errors = []
    warnings = []

    if verbose:
        print(f"[DEBUG] Validating post: {post.filepath.name}")

    # Check minimum length
    if post.content_length < Config.MIN_CONTENT_LENGTH:
        errors.append(
            f"Content too short: {post.content_length} chars "
            f"(minimum: {Config.MIN_CONTENT_LENGTH})"
        )

    # Check maximum length
    if post.content_length > Config.MAX_CONTENT_LENGTH:
        errors.append(
            f"Content too long: {post.content_length} chars "
            f"(maximum: {Config.MAX_CONTENT_LENGTH})"
        )

    # Check for banned patterns
    for pattern in Config.BANNED_PATTERNS:
        if pattern in post.raw_content:
            if pattern == "[FORCE_FAIL]":
                errors.append(f"Forced failure marker detected: {pattern}")
            else:
                errors.append(f"Banned content placeholder detected: {pattern}")

    # Check body exists
    if not post.body.strip():
        errors.append("Post body is empty")

    # Warnings
    if not post.hashtags:
        warnings.append("No hashtags found - consider adding for reach")

    if len(post.hashtags) > 30:
        warnings.append(f"Too many hashtags ({len(post.hashtags)}) - may reduce engagement")

    if post.title and len(post.title) > 100:
        warnings.append("Title is very long - consider shortening")

    valid = len(errors) == 0

    if verbose:
        print(f"[DEBUG] Validation result: {'PASSED' if valid else 'FAILED'}")
        for error in errors:
            print(f"[DEBUG]   Error: {error}")
        for warning in warnings:
            print(f"[DEBUG]   Warning: {warning}")

    return ValidationResult(
        valid=valid,
        errors=errors,
        warnings=warnings,
    )


# ==============================================================================
# SIMULATED POSTING
# ==============================================================================

def generate_post_id() -> str:
    """Generate a fake Facebook post ID."""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"FB_{timestamp}_{random_suffix}"


def simulate_post(post: ParsedPost, verbose: bool = False) -> PostResult:
    """
    Simulate posting to Facebook.

    Args:
        post: ParsedPost to publish
        verbose: Enable verbose output

    Returns:
        PostResult with simulated result

    Raises:
        Exception: If [FORCE_FAIL] is in content (simulated failure)
    """
    if verbose:
        print(f"[DEBUG] Simulating Facebook post...")

    # Check for forced failure
    if "[FORCE_FAIL]" in post.raw_content:
        raise Exception("Simulated failure: [FORCE_FAIL] marker detected")

    # Simulate network latency
    latency = random.uniform(Config.MIN_LATENCY, Config.MAX_LATENCY)
    if verbose:
        print(f"[DEBUG] Simulating network latency: {latency:.2f}s")
    time.sleep(latency)

    # Generate fake post ID
    post_id = generate_post_id()

    if verbose:
        print(f"[DEBUG] Generated post ID: {post_id}")

    return PostResult(
        status="success",
        platform=Config.PLATFORM,
        post_id=post_id,
        timestamp=datetime.now().isoformat(),
        simulated=True,
    )


# ==============================================================================
# LIVE POSTING WITH PLAYWRIGHT
# ==============================================================================

def live_post(post: ParsedPost, verbose: bool = False, headless: bool = False) -> PostResult:
    """
    Live Facebook posting using Playwright browser automation.

    Automates the browser to:
    1. Login to Facebook
    2. Create a new post
    3. Publish the content

    Args:
        post: ParsedPost to publish
        verbose: Enable verbose output
        headless: Run browser in headless mode

    Returns:
        PostResult with posting status

    Environment Variables Required:
        FACEBOOK_EMAIL - Facebook login email
        FACEBOOK_PASSWORD - Facebook login password
    """
    if verbose:
        print(f"[DEBUG] Live posting with Playwright...")
        print(f"[DEBUG] Headless mode: {headless}")

    # Check for credentials
    email = os.environ.get('FACEBOOK_EMAIL')
    password = os.environ.get('FACEBOOK_PASSWORD')

    if not email or not password:
        error_msg = "Missing credentials. Set FACEBOOK_EMAIL and FACEBOOK_PASSWORD environment variables."
        logger.error(error_msg)
        _log_live_event("credentials_missing", {"error": error_msg})
        return PostResult(
            status="failed",
            platform=Config.PLATFORM,
            post_id=None,
            timestamp=datetime.now().isoformat(),
            error=error_msg,
            simulated=False,
        )

    try:
        # Import and run Playwright automation
        from utils.playwright_automation import run_facebook_automation

        if verbose:
            print(f"[DEBUG] Starting Playwright automation...")
            print(f"[DEBUG] Content length: {post.content_length} chars")

        # Get full post content
        content = post.full_content

        # Run automation
        result = run_facebook_automation(
            content=content,
            email=email,
            password=password,
            headless=headless
        )

        if result.success:
            post_id = generate_post_id()  # Use generated ID since we can't easily get real one
            _log_live_event("post_published", {
                "post_id": post_id,
                "content_length": len(content),
                "screenshot": result.screenshot_path
            })

            if verbose:
                print(f"[DEBUG] Post published successfully")
                if result.screenshot_path:
                    print(f"[DEBUG] Screenshot: {result.screenshot_path}")

            return PostResult(
                status="success",
                platform=Config.PLATFORM,
                post_id=post_id,
                timestamp=datetime.now().isoformat(),
                simulated=False,
            )
        else:
            _log_live_event("post_failed", {
                "error": result.error,
                "screenshot": result.screenshot_path
            })

            if verbose:
                print(f"[DEBUG] Post failed: {result.error}")

            return PostResult(
                status="failed",
                platform=Config.PLATFORM,
                post_id=None,
                timestamp=datetime.now().isoformat(),
                error=result.error or result.message,
                simulated=False,
            )

    except ImportError as e:
        error_msg = f"Playwright not installed. Run: pip install playwright && playwright install chromium"
        logger.error(error_msg)
        _log_live_event("import_error", {"error": str(e)})
        return PostResult(
            status="failed",
            platform=Config.PLATFORM,
            post_id=None,
            timestamp=datetime.now().isoformat(),
            error=error_msg,
            simulated=False,
        )
    except Exception as e:
        error_msg = f"Live posting error: {str(e)}"
        logger.error(error_msg)
        _log_live_event("automation_error", {"error": str(e)})
        return PostResult(
            status="failed",
            platform=Config.PLATFORM,
            post_id=None,
            timestamp=datetime.now().isoformat(),
            error=error_msg,
            simulated=False,
        )


def _log_live_event(event_type: str, details: Dict[str, Any]):
    """Log live posting event to file."""
    log_path = Path(__file__).parent.parent / "AI_Employee_Vault" / "Logs"
    log_path.mkdir(parents=True, exist_ok=True)
    log_file = log_path / "facebook_live_automation.log"

    entry = {
        "timestamp": datetime.now().isoformat(),
        "event": event_type,
        "platform": "facebook",
        "details": details
    }

    with open(log_file, 'a') as f:
        f.write(json.dumps(entry) + "\n")


# ==============================================================================
# FACEBOOK POSTER AGENT
# ==============================================================================

class FacebookPoster:
    """
    Facebook posting agent.

    Handles the full posting workflow with audit logging
    and watchdog integration.

    Supports:
    - Simulated mode for testing
    - Live mode with Playwright browser automation
    """

    def __init__(self, verbose: bool = False, headless: bool = False):
        self.verbose = verbose
        self.headless = headless
        self.audit_logger = get_audit_logger()
        self.heartbeat = HeartbeatWriter(Config.ACTOR)

    def _log(self, message: str, level: str = "INFO"):
        """Print timestamped log message."""
        if self.verbose or level in ("ERROR", "WARN"):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] [{level}] {message}")

    def _audit_log(
        self,
        action: FacebookActionType,
        target: str,
        parameters: Dict[str, Any] = None,
        result: ResultStatus = ResultStatus.SUCCESS,
        error: str = None
    ):
        """Log action to audit system."""
        self.audit_logger.log(
            action_type=ActionType.TASK_STARTED,
            actor=Config.ACTOR,
            target=target,
            parameters={
                "custom_action": action.value,
                "platform": Config.PLATFORM,
                **(parameters or {})
            },
            result=result,
            error=error
        )

    def post(
        self,
        filepath: Path,
        simulate: bool = True
    ) -> Tuple[PostResult, int]:
        """
        Execute the full posting workflow.

        Args:
            filepath: Path to post file
            simulate: Use simulated mode (default True)

        Returns:
            Tuple of (PostResult, exit_code)
        """
        filename = filepath.name

        # Start heartbeat
        self.heartbeat.start()
        self.heartbeat.update_task("facebook_posting")

        try:
            # Log start
            self._log(f"Starting Facebook post: {filename}")
            self._audit_log(
                action=FacebookActionType.FACEBOOK_POST_STARTED,
                target=filename,
                parameters={"simulate": simulate},
                result=ResultStatus.PENDING
            )

            # Load post
            try:
                post = load_post(filepath, verbose=self.verbose)
            except FileNotFoundError as e:
                self._log(f"File not found: {e}", "ERROR")
                self._audit_log(
                    action=FacebookActionType.FACEBOOK_POST_FAILED,
                    target=filename,
                    parameters={"stage": "load"},
                    result=ResultStatus.FAILURE,
                    error=str(e)
                )
                return PostResult(
                    status="failed",
                    platform=Config.PLATFORM,
                    post_id=None,
                    timestamp=datetime.now().isoformat(),
                    error=str(e),
                    simulated=simulate,
                ), ExitCode.VALIDATION_ERROR
            except ValueError as e:
                self._log(f"Parse error: {e}", "ERROR")
                self._audit_log(
                    action=FacebookActionType.FACEBOOK_POST_FAILED,
                    target=filename,
                    parameters={"stage": "parse"},
                    result=ResultStatus.FAILURE,
                    error=str(e)
                )
                return PostResult(
                    status="failed",
                    platform=Config.PLATFORM,
                    post_id=None,
                    timestamp=datetime.now().isoformat(),
                    error=str(e),
                    simulated=simulate,
                ), ExitCode.VALIDATION_ERROR

            # Validate post
            validation = validate_post(post, verbose=self.verbose)

            if not validation.valid:
                error_msg = "; ".join(validation.errors)
                self._log(f"Validation failed: {error_msg}", "ERROR")
                self._audit_log(
                    action=FacebookActionType.FACEBOOK_POST_FAILED,
                    target=filename,
                    parameters={
                        "stage": "validation",
                        "errors": validation.errors,
                    },
                    result=ResultStatus.FAILURE,
                    error=error_msg
                )
                return PostResult(
                    status="failed",
                    platform=Config.PLATFORM,
                    post_id=None,
                    timestamp=datetime.now().isoformat(),
                    error=error_msg,
                    simulated=simulate,
                ), ExitCode.VALIDATION_ERROR

            # Log validation success
            self._log("Post validated successfully")
            self._audit_log(
                action=FacebookActionType.FACEBOOK_POST_VALIDATED,
                target=filename,
                parameters={
                    "content_length": post.content_length,
                    "hashtag_count": len(post.hashtags),
                    "has_media": len(post.media_references) > 0,
                    "warnings": validation.warnings,
                },
                result=ResultStatus.SUCCESS
            )

            # Post (simulated or live)
            try:
                if simulate:
                    result = simulate_post(post, verbose=self.verbose)
                else:
                    result = live_post(post, verbose=self.verbose, headless=self.headless)

                if result.status == "success":
                    self._log(f"Post successful: {result.post_id}")
                    self._audit_log(
                        action=FacebookActionType.FACEBOOK_POST_SUCCESS,
                        target=filename,
                        parameters={
                            "post_id": result.post_id,
                            "simulated": result.simulated,
                        },
                        result=ResultStatus.SUCCESS
                    )

                    # Update heartbeat
                    self.heartbeat.task_completed()

                    return result, ExitCode.SUCCESS
                else:
                    self._log(f"Post failed: {result.error}", "ERROR")
                    self._audit_log(
                        action=FacebookActionType.FACEBOOK_POST_FAILED,
                        target=filename,
                        parameters={"stage": "posting"},
                        result=ResultStatus.FAILURE,
                        error=result.error
                    )

                    # Update heartbeat
                    self.heartbeat.record_error(result.error)

                    return result, ExitCode.POSTING_FAILURE

            except Exception as e:
                error_msg = str(e)
                self._log(f"Posting exception: {error_msg}", "ERROR")
                self._audit_log(
                    action=FacebookActionType.FACEBOOK_POST_FAILED,
                    target=filename,
                    parameters={"stage": "posting", "exception": type(e).__name__},
                    result=ResultStatus.FAILURE,
                    error=error_msg
                )

                # Update heartbeat
                self.heartbeat.record_error(error_msg)

                return PostResult(
                    status="failed",
                    platform=Config.PLATFORM,
                    post_id=None,
                    timestamp=datetime.now().isoformat(),
                    error=error_msg,
                    simulated=simulate,
                ), ExitCode.POSTING_FAILURE

        finally:
            # Stop heartbeat
            self.heartbeat.stop()
            self.audit_logger.flush()


# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Facebook Poster Agent - Post content to Facebook",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit Codes:
  0 - Success
  1 - Validation error
  2 - Posting failure

Examples:
  python3 scripts/facebook_poster.py --file post.md
  python3 scripts/facebook_poster.py --file post.md --simulate
  python3 scripts/facebook_poster.py --file post.md --live --verbose
        """
    )

    parser.add_argument(
        '--file', '-f',
        type=str,
        required=True,
        help='Path to the post file (markdown)'
    )

    parser.add_argument(
        '--post-file',
        type=str,
        help='Alias for --file (compatibility with orchestrator)'
    )

    parser.add_argument(
        '--simulate',
        action='store_true',
        default=True,
        help='Use simulated mode (default)'
    )

    parser.add_argument(
        '--live',
        action='store_true',
        help='Use live posting mode with Playwright automation'
    )

    parser.add_argument(
        '--headless',
        action='store_true',
        help='Run browser in headless mode (for --live)'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )

    args = parser.parse_args()

    # Resolve file path
    file_path = args.post_file or args.file
    filepath = Path(file_path).resolve()

    # Determine mode
    simulate = not args.live

    # Print header if verbose
    if args.verbose:
        print("=" * 60)
        print("   Facebook Poster Agent")
        print("   Gold Tier Phase 2 - Step 2")
        print("=" * 60)
        print(f"   File: {filepath}")
        print(f"   Mode: {'Simulated' if simulate else 'LIVE'}")
        print("=" * 60)
        print()

    # Execute posting
    poster = FacebookPoster(verbose=args.verbose, headless=args.headless)
    result, exit_code = poster.post(filepath, simulate=simulate)

    # Output result as JSON
    print(result.to_json())

    # Exit with appropriate code
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
