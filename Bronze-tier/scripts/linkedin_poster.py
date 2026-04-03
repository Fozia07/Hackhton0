#!/usr/bin/env python3
"""
LinkedIn Poster Agent
=====================

Gold Tier Phase 2 - Step 2
Production-grade LinkedIn posting agent with Playwright automation.

Integrates with social_media_orchestrator.py for unified posting.

Usage:
    python3 scripts/linkedin_poster.py --file <path>
    python3 scripts/linkedin_poster.py --file <path> --simulate
    python3 scripts/linkedin_poster.py --file <path> --live --verbose
    python3 scripts/linkedin_poster.py --file <path> --live --headless

Environment Variables (for --live mode):
    LINKEDIN_EMAIL    - LinkedIn login email
    LINKEDIN_PASSWORD - LinkedIn login password

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

sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables from .env file
from utils.env_loader import load_env
load_env()

# Configure logging for live automation
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("linkedin_poster")

from utils.audit_logger import get_audit_logger, ActionType, ResultStatus
from utils.heartbeat import HeartbeatWriter


class ExitCode:
    SUCCESS = 0
    VALIDATION_ERROR = 1
    POSTING_FAILURE = 2


class LinkedInActionType(Enum):
    LINKEDIN_POST_STARTED = "linkedin_post_started"
    LINKEDIN_POST_VALIDATED = "linkedin_post_validated"
    LINKEDIN_POST_SUCCESS = "linkedin_post_success"
    LINKEDIN_POST_FAILED = "linkedin_post_failed"


class Config:
    MIN_CONTENT_LENGTH = 20
    MAX_CONTENT_LENGTH = 3000
    MAX_ARTICLE_LENGTH = 125000
    BANNED_PATTERNS = ["[FORCE_FAIL]", "[PLACEHOLDER]", "[TODO]", "[INSERT", "{{", "}}"]
    MIN_LATENCY = 1.0
    MAX_LATENCY = 2.0
    ACTOR = "linkedin_poster"
    PLATFORM = "linkedin"


@dataclass
class ParsedPost:
    filepath: Path
    title: Optional[str]
    body: str
    hashtags: List[str]
    mentions: List[str]
    media_references: List[str]
    metadata: Dict[str, Any]
    raw_content: str
    is_article: bool = False

    @property
    def full_content(self) -> str:
        parts = []
        if self.title and not self.is_article:
            parts.append(self.title)
            parts.append("")
        parts.append(self.body)
        if self.hashtags:
            parts.append("")
            parts.append(" ".join(self.hashtags))
        return "\n".join(parts)

    @property
    def content_length(self) -> int:
        return len(self.full_content)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filepath": str(self.filepath),
            "title": self.title,
            "body_preview": self.body[:200] if self.body else "",
            "hashtags": self.hashtags,
            "mentions": self.mentions,
            "media_references": self.media_references,
            "content_length": self.content_length,
            "is_article": self.is_article,
        }


@dataclass
class ValidationResult:
    valid: bool
    errors: List[str]
    warnings: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PostResult:
    status: str
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


def load_post(filepath: Path, verbose: bool = False) -> ParsedPost:
    if verbose:
        print(f"[DEBUG] Loading post from: {filepath}")

    if not filepath.exists():
        raise FileNotFoundError(f"Post file not found: {filepath}")

    raw_content = filepath.read_text(encoding='utf-8')

    if not raw_content.strip():
        raise ValueError("Post file is empty")

    metadata = {}
    body = raw_content
    title = None

    if raw_content.startswith('---'):
        parts = raw_content.split('---', 2)
        if len(parts) >= 3:
            for line in parts[1].strip().split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    metadata[key.strip().lower()] = value.strip()
            body = parts[2].strip()

    # Extract title
    if 'title' in metadata:
        title = metadata['title']
    else:
        title_match = re.search(r'^#\s+(.+)$', body, re.MULTILINE)
        if title_match:
            title = title_match.group(1).strip()
            body = re.sub(r'^#\s+.+\n?', '', body, count=1).strip()

    # Check if article
    is_article = metadata.get('type', '').lower() == 'article' or len(body) > Config.MAX_CONTENT_LENGTH

    hashtags = re.findall(r'#\w+', body)
    mentions = re.findall(r'@\w+', body)

    # Clean hashtags from end
    lines = body.split('\n')
    clean_lines = []
    for line in reversed(lines):
        stripped = line.strip()
        if stripped and all(word.startswith('#') for word in stripped.split()):
            continue
        clean_lines.insert(0, line)
    body = '\n'.join(clean_lines).strip()

    media_references = re.findall(r'!\[.*?\]\((.+?)\)', raw_content)
    if 'image' in metadata:
        media_references.append(metadata['image'])
    if 'media' in metadata:
        media_references.append(metadata['media'])

    if verbose:
        print(f"[DEBUG] Title: {title}")
        print(f"[DEBUG] Body length: {len(body)} chars")
        print(f"[DEBUG] Is article: {is_article}")
        print(f"[DEBUG] Hashtags: {len(hashtags)}")

    return ParsedPost(
        filepath=filepath,
        title=title,
        body=body,
        hashtags=hashtags,
        mentions=mentions,
        media_references=media_references,
        metadata=metadata,
        raw_content=raw_content,
        is_article=is_article,
    )


def validate_post(post: ParsedPost, verbose: bool = False) -> ValidationResult:
    errors = []
    warnings = []

    if verbose:
        print(f"[DEBUG] Validating post: {post.filepath.name}")

    max_length = Config.MAX_ARTICLE_LENGTH if post.is_article else Config.MAX_CONTENT_LENGTH

    if post.content_length < Config.MIN_CONTENT_LENGTH:
        errors.append(f"Content too short: {post.content_length} chars (min: {Config.MIN_CONTENT_LENGTH})")

    if post.content_length > max_length:
        errors.append(f"Content too long: {post.content_length} chars (max: {max_length})")

    for pattern in Config.BANNED_PATTERNS:
        if pattern in post.raw_content:
            errors.append(f"Banned content detected: {pattern}")

    if not post.body.strip():
        errors.append("Post body is empty")

    if post.is_article and not post.title:
        warnings.append("Article without title may have less engagement")

    if not post.hashtags:
        warnings.append("No hashtags - consider adding 3-5 for reach")

    if len(post.hashtags) > 10:
        warnings.append("Too many hashtags may appear unprofessional")

    valid = len(errors) == 0

    if verbose:
        print(f"[DEBUG] Validation: {'PASSED' if valid else 'FAILED'}")

    return ValidationResult(valid=valid, errors=errors, warnings=warnings)


def generate_post_id() -> str:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_suffix = ''.join(random.choices(string.digits, k=10))
    return f"LI_{timestamp}_{random_suffix}"


def simulate_post(post: ParsedPost, verbose: bool = False) -> PostResult:
    if verbose:
        print(f"[DEBUG] Simulating LinkedIn post...")

    if "[FORCE_FAIL]" in post.raw_content:
        raise Exception("Simulated failure: [FORCE_FAIL] marker detected")

    latency = random.uniform(Config.MIN_LATENCY, Config.MAX_LATENCY)
    if verbose:
        print(f"[DEBUG] Simulating latency: {latency:.2f}s")
    time.sleep(latency)

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


def live_post(post: ParsedPost, verbose: bool = False, headless: bool = False) -> PostResult:
    """
    Live LinkedIn posting using Playwright browser automation.

    Automates the browser to:
    1. Login to LinkedIn
    2. Create a new post
    3. Publish the content

    Args:
        post: ParsedPost to publish
        verbose: Enable verbose output
        headless: Run browser in headless mode

    Returns:
        PostResult with posting status

    Environment Variables Required:
        LINKEDIN_EMAIL - LinkedIn login email
        LINKEDIN_PASSWORD - LinkedIn login password
    """
    if verbose:
        print(f"[DEBUG] Live posting with Playwright...")
        print(f"[DEBUG] Headless mode: {headless}")

    # Check for credentials
    email = os.environ.get('LINKEDIN_EMAIL')
    password = os.environ.get('LINKEDIN_PASSWORD')

    if not email or not password:
        error_msg = "Missing credentials. Set LINKEDIN_EMAIL and LINKEDIN_PASSWORD environment variables."
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
        from utils.playwright_automation import run_linkedin_automation

        if verbose:
            print(f"[DEBUG] Starting Playwright automation...")
            print(f"[DEBUG] Content length: {post.content_length} chars")

        # Get full post content
        content = post.full_content

        # Run automation
        result = run_linkedin_automation(
            content=content,
            email=email,
            password=password,
            headless=headless
        )

        if result.success:
            post_id = generate_post_id()
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
    log_file = log_path / "linkedin_live_automation.log"

    entry = {
        "timestamp": datetime.now().isoformat(),
        "event": event_type,
        "platform": "linkedin",
        "details": details
    }

    with open(log_file, 'a') as f:
        f.write(json.dumps(entry) + "\n")


class LinkedInPoster:
    """
    LinkedIn posting agent with Playwright automation support.
    """

    def __init__(self, verbose: bool = False, headless: bool = False):
        self.verbose = verbose
        self.headless = headless
        self.audit_logger = get_audit_logger()
        self.heartbeat = HeartbeatWriter(Config.ACTOR)

    def _log(self, message: str, level: str = "INFO"):
        if self.verbose or level in ("ERROR", "WARN"):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] [{level}] {message}")

    def _audit_log(self, action: LinkedInActionType, target: str,
                   parameters: Dict[str, Any] = None,
                   result: ResultStatus = ResultStatus.SUCCESS, error: str = None):
        self.audit_logger.log(
            action_type=ActionType.TASK_STARTED,
            actor=Config.ACTOR,
            target=target,
            parameters={"custom_action": action.value, "platform": Config.PLATFORM, **(parameters or {})},
            result=result,
            error=error
        )

    def post(self, filepath: Path, simulate: bool = True) -> Tuple[PostResult, int]:
        filename = filepath.name
        self.heartbeat.start()
        self.heartbeat.update_task("linkedin_posting")

        try:
            self._log(f"Starting LinkedIn post: {filename}")
            self._audit_log(LinkedInActionType.LINKEDIN_POST_STARTED, filename,
                          {"simulate": simulate}, ResultStatus.PENDING)

            try:
                post = load_post(filepath, verbose=self.verbose)
            except (FileNotFoundError, ValueError) as e:
                self._log(f"Load error: {e}", "ERROR")
                self._audit_log(LinkedInActionType.LINKEDIN_POST_FAILED, filename,
                              {"stage": "load"}, ResultStatus.FAILURE, str(e))
                return PostResult("failed", Config.PLATFORM, None,
                                datetime.now().isoformat(), str(e), simulate), ExitCode.VALIDATION_ERROR

            validation = validate_post(post, verbose=self.verbose)

            if not validation.valid:
                error_msg = "; ".join(validation.errors)
                self._log(f"Validation failed: {error_msg}", "ERROR")
                self._audit_log(LinkedInActionType.LINKEDIN_POST_FAILED, filename,
                              {"stage": "validation", "errors": validation.errors},
                              ResultStatus.FAILURE, error_msg)
                return PostResult("failed", Config.PLATFORM, None,
                                datetime.now().isoformat(), error_msg, simulate), ExitCode.VALIDATION_ERROR

            self._log("Post validated successfully")
            self._audit_log(LinkedInActionType.LINKEDIN_POST_VALIDATED, filename,
                          {"content_length": post.content_length, "is_article": post.is_article},
                          ResultStatus.SUCCESS)

            try:
                result = simulate_post(post, self.verbose) if simulate else live_post(post, self.verbose, self.headless)

                if result.status == "success":
                    self._log(f"Post successful: {result.post_id}")
                    self._audit_log(LinkedInActionType.LINKEDIN_POST_SUCCESS, filename,
                                  {"post_id": result.post_id}, ResultStatus.SUCCESS)
                    self.heartbeat.task_completed()
                    return result, ExitCode.SUCCESS
                else:
                    self._log(f"Post failed: {result.error}", "ERROR")
                    self._audit_log(LinkedInActionType.LINKEDIN_POST_FAILED, filename,
                                  {"stage": "posting"}, ResultStatus.FAILURE, result.error)
                    self.heartbeat.record_error(result.error)
                    return result, ExitCode.POSTING_FAILURE

            except Exception as e:
                self._log(f"Exception: {e}", "ERROR")
                self._audit_log(LinkedInActionType.LINKEDIN_POST_FAILED, filename,
                              {"stage": "posting"}, ResultStatus.FAILURE, str(e))
                self.heartbeat.record_error(str(e))
                return PostResult("failed", Config.PLATFORM, None,
                                datetime.now().isoformat(), str(e), simulate), ExitCode.POSTING_FAILURE
        finally:
            self.heartbeat.stop()
            self.audit_logger.flush()


def main():
    parser = argparse.ArgumentParser(
        description="LinkedIn Poster Agent - Post content to LinkedIn",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables (for --live mode):
    LINKEDIN_EMAIL    - LinkedIn login email
    LINKEDIN_PASSWORD - LinkedIn login password

Examples:
    python3 scripts/linkedin_poster.py --file post.md
    python3 scripts/linkedin_poster.py --file post.md --simulate
    python3 scripts/linkedin_poster.py --file post.md --live --verbose
    python3 scripts/linkedin_poster.py --file post.md --live --headless
        """
    )
    parser.add_argument('--file', '-f', type=str, required=True, help='Path to post file')
    parser.add_argument('--post-file', type=str, help='Alias for --file')
    parser.add_argument('--simulate', action='store_true', default=True, help='Simulated mode (default)')
    parser.add_argument('--live', action='store_true', help='Live posting with Playwright automation')
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode (for --live)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')

    args = parser.parse_args()
    file_path = args.post_file or args.file
    filepath = Path(file_path).resolve()
    simulate = not args.live

    if args.verbose:
        print("=" * 60)
        print("   LinkedIn Poster Agent")
        print("   Gold Tier - Playwright Automation")
        print("=" * 60)
        print(f"   File: {filepath}")
        print(f"   Mode: {'Simulated' if simulate else 'LIVE'}")
        if not simulate:
            print(f"   Headless: {args.headless}")
        print("=" * 60)

    poster = LinkedInPoster(verbose=args.verbose, headless=args.headless)
    result, exit_code = poster.post(filepath, simulate=simulate)
    print(result.to_json())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
