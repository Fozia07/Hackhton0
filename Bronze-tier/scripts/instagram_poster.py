#!/usr/bin/env python3
"""
Instagram Poster Agent
======================

Gold Tier Phase 2 - Step 2
Production-grade Instagram posting agent.

Integrates with social_media_orchestrator.py for unified posting.

Usage:
    python3 scripts/instagram_poster.py --file <path>
    python3 scripts/instagram_poster.py --file <path> --simulate
    python3 scripts/instagram_poster.py --file <path> --live --verbose

Exit Codes:
    0 - Success
    1 - Validation error
    2 - Posting failure

Author: AI Employee System
Version: 1.0.0
"""

import os
import sys
import re
import json
import time
import random
import string
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.audit_logger import get_audit_logger, ActionType, ResultStatus
from utils.heartbeat import HeartbeatWriter


class ExitCode:
    SUCCESS = 0
    VALIDATION_ERROR = 1
    POSTING_FAILURE = 2


class InstagramActionType(Enum):
    INSTAGRAM_POST_STARTED = "instagram_post_started"
    INSTAGRAM_POST_VALIDATED = "instagram_post_validated"
    INSTAGRAM_POST_SUCCESS = "instagram_post_success"
    INSTAGRAM_POST_FAILED = "instagram_post_failed"


class Config:
    MIN_CONTENT_LENGTH = 1
    MAX_CONTENT_LENGTH = 2200
    MAX_HASHTAGS = 30
    BANNED_PATTERNS = ["[FORCE_FAIL]", "[PLACEHOLDER]", "[TODO]", "[INSERT", "{{", "}}"]
    MIN_LATENCY = 1.0
    MAX_LATENCY = 2.0
    ACTOR = "instagram_poster"
    PLATFORM = "instagram"


@dataclass
class ParsedPost:
    filepath: Path
    caption: str
    hashtags: List[str]
    media_references: List[str]
    metadata: Dict[str, Any]
    raw_content: str

    @property
    def full_content(self) -> str:
        parts = [self.caption]
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
            "caption_preview": self.caption[:200] if self.caption else "",
            "hashtags": self.hashtags,
            "media_references": self.media_references,
            "content_length": self.content_length,
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
    caption = raw_content

    if raw_content.startswith('---'):
        parts = raw_content.split('---', 2)
        if len(parts) >= 3:
            for line in parts[1].strip().split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    metadata[key.strip().lower()] = value.strip()
            caption = parts[2].strip()

    # Remove title if present
    caption = re.sub(r'^#\s+.+\n?', '', caption, count=1).strip()

    hashtags = re.findall(r'#\w+', caption)

    # Clean hashtags from end
    lines = caption.split('\n')
    clean_lines = []
    for line in reversed(lines):
        stripped = line.strip()
        if stripped and all(word.startswith('#') for word in stripped.split()):
            continue
        clean_lines.insert(0, line)
    caption = '\n'.join(clean_lines).strip()

    media_references = re.findall(r'!\[.*?\]\((.+?)\)', raw_content)
    if 'image' in metadata:
        media_references.append(metadata['image'])
    if 'media' in metadata:
        media_references.append(metadata['media'])

    if verbose:
        print(f"[DEBUG] Caption length: {len(caption)} chars")
        print(f"[DEBUG] Hashtags: {len(hashtags)}")
        print(f"[DEBUG] Media: {media_references}")

    return ParsedPost(
        filepath=filepath,
        caption=caption,
        hashtags=hashtags,
        media_references=media_references,
        metadata=metadata,
        raw_content=raw_content,
    )


def validate_post(post: ParsedPost, verbose: bool = False) -> ValidationResult:
    errors = []
    warnings = []

    if verbose:
        print(f"[DEBUG] Validating post: {post.filepath.name}")

    if post.content_length < Config.MIN_CONTENT_LENGTH:
        errors.append(f"Content too short: {post.content_length} chars")

    if post.content_length > Config.MAX_CONTENT_LENGTH:
        errors.append(f"Content too long: {post.content_length} chars (max: {Config.MAX_CONTENT_LENGTH})")

    for pattern in Config.BANNED_PATTERNS:
        if pattern in post.raw_content:
            errors.append(f"Banned content detected: {pattern}")

    if len(post.hashtags) > Config.MAX_HASHTAGS:
        errors.append(f"Too many hashtags: {len(post.hashtags)} (max: {Config.MAX_HASHTAGS})")

    if not post.media_references:
        warnings.append("No media references - Instagram posts typically require images")

    if not post.hashtags:
        warnings.append("No hashtags found - consider adding for reach")

    valid = len(errors) == 0

    if verbose:
        print(f"[DEBUG] Validation: {'PASSED' if valid else 'FAILED'}")

    return ValidationResult(valid=valid, errors=errors, warnings=warnings)


def generate_post_id() -> str:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"IG_{timestamp}_{random_suffix}"


def simulate_post(post: ParsedPost, verbose: bool = False) -> PostResult:
    if verbose:
        print(f"[DEBUG] Simulating Instagram post...")

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


def live_post_stub(post: ParsedPost, verbose: bool = False) -> PostResult:
    if verbose:
        print(f"[DEBUG] Live posting not configured")

    return PostResult(
        status="failed",
        platform=Config.PLATFORM,
        post_id=None,
        timestamp=datetime.now().isoformat(),
        error="Live posting not configured. Set INSTAGRAM_ACCESS_TOKEN environment variable.",
        simulated=False,
    )


class InstagramPoster:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.audit_logger = get_audit_logger()
        self.heartbeat = HeartbeatWriter(Config.ACTOR)

    def _log(self, message: str, level: str = "INFO"):
        if self.verbose or level in ("ERROR", "WARN"):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] [{level}] {message}")

    def _audit_log(self, action: InstagramActionType, target: str,
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
        self.heartbeat.update_task("instagram_posting")

        try:
            self._log(f"Starting Instagram post: {filename}")
            self._audit_log(InstagramActionType.INSTAGRAM_POST_STARTED, filename,
                          {"simulate": simulate}, ResultStatus.PENDING)

            try:
                post = load_post(filepath, verbose=self.verbose)
            except (FileNotFoundError, ValueError) as e:
                self._log(f"Load error: {e}", "ERROR")
                self._audit_log(InstagramActionType.INSTAGRAM_POST_FAILED, filename,
                              {"stage": "load"}, ResultStatus.FAILURE, str(e))
                return PostResult("failed", Config.PLATFORM, None,
                                datetime.now().isoformat(), str(e), simulate), ExitCode.VALIDATION_ERROR

            validation = validate_post(post, verbose=self.verbose)

            if not validation.valid:
                error_msg = "; ".join(validation.errors)
                self._log(f"Validation failed: {error_msg}", "ERROR")
                self._audit_log(InstagramActionType.INSTAGRAM_POST_FAILED, filename,
                              {"stage": "validation", "errors": validation.errors},
                              ResultStatus.FAILURE, error_msg)
                return PostResult("failed", Config.PLATFORM, None,
                                datetime.now().isoformat(), error_msg, simulate), ExitCode.VALIDATION_ERROR

            self._log("Post validated successfully")
            self._audit_log(InstagramActionType.INSTAGRAM_POST_VALIDATED, filename,
                          {"content_length": post.content_length, "hashtag_count": len(post.hashtags)},
                          ResultStatus.SUCCESS)

            try:
                result = simulate_post(post, self.verbose) if simulate else live_post_stub(post, self.verbose)

                if result.status == "success":
                    self._log(f"Post successful: {result.post_id}")
                    self._audit_log(InstagramActionType.INSTAGRAM_POST_SUCCESS, filename,
                                  {"post_id": result.post_id}, ResultStatus.SUCCESS)
                    self.heartbeat.task_completed()
                    return result, ExitCode.SUCCESS
                else:
                    self._log(f"Post failed: {result.error}", "ERROR")
                    self._audit_log(InstagramActionType.INSTAGRAM_POST_FAILED, filename,
                                  {"stage": "posting"}, ResultStatus.FAILURE, result.error)
                    self.heartbeat.record_error(result.error)
                    return result, ExitCode.POSTING_FAILURE

            except Exception as e:
                self._log(f"Exception: {e}", "ERROR")
                self._audit_log(InstagramActionType.INSTAGRAM_POST_FAILED, filename,
                              {"stage": "posting"}, ResultStatus.FAILURE, str(e))
                self.heartbeat.record_error(str(e))
                return PostResult("failed", Config.PLATFORM, None,
                                datetime.now().isoformat(), str(e), simulate), ExitCode.POSTING_FAILURE
        finally:
            self.heartbeat.stop()
            self.audit_logger.flush()


def main():
    parser = argparse.ArgumentParser(description="Instagram Poster Agent")
    parser.add_argument('--file', '-f', type=str, required=True, help='Path to post file')
    parser.add_argument('--post-file', type=str, help='Alias for --file')
    parser.add_argument('--simulate', action='store_true', default=True, help='Simulated mode')
    parser.add_argument('--live', action='store_true', help='Live posting mode')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')

    args = parser.parse_args()
    file_path = args.post_file or args.file
    filepath = Path(file_path).resolve()
    simulate = not args.live

    if args.verbose:
        print("=" * 60)
        print("   Instagram Poster Agent")
        print("=" * 60)
        print(f"   File: {filepath}")
        print(f"   Mode: {'Simulated' if simulate else 'LIVE'}")
        print("=" * 60)

    poster = InstagramPoster(verbose=args.verbose)
    result, exit_code = poster.post(filepath, simulate=simulate)
    print(result.to_json())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
