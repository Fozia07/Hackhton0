# Social Media Orchestration System

## Gold Tier Phase 2 - Unified Posting Architecture

**Version:** 1.0.0
**Status:** Implemented
**Component:** Phase 2, Step 1

---

## Executive Summary

The Social Media Orchestration System provides a unified, enterprise-grade architecture for managing all social media posting operations. It acts as a central coordinator that:

- Detects approved posts from filename prefixes
- Routes posts to platform-specific agents
- Handles retries with exponential backoff
- Integrates with watchdog for continuous monitoring
- Maintains full audit trail of all operations

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Core Components](#core-components)
3. [Platform Detection](#platform-detection)
4. [Platform Routing](#platform-routing)
5. [Retry & Error Handling](#retry--error-handling)
6. [Watchdog Integration](#watchdog-integration)
7. [Audit Logging](#audit-logging)
8. [Configuration](#configuration)
9. [CLI Reference](#cli-reference)
10. [File Structure](#file-structure)
11. [Monitoring & Metrics](#monitoring--metrics)
12. [Troubleshooting](#troubleshooting)

---

## System Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     SOCIAL MEDIA ORCHESTRATION SYSTEM                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│    ┌─────────────────────────────────────────────────────────────────┐  │
│    │                         INPUT LAYER                              │  │
│    │                                                                  │  │
│    │  ┌─────────────────────────────────────────────────────────┐   │  │
│    │  │            AI_Employee_Vault/Approved/                   │   │  │
│    │  │                                                          │   │  │
│    │  │   FACEBOOK_POST_*.md  INSTAGRAM_POST_*.md               │   │  │
│    │  │   TWITTER_POST_*.md   LINKEDIN_POST_*.md                │   │  │
│    │  │                                                          │   │  │
│    │  └─────────────────────────────────────────────────────────┘   │  │
│    │                              │                                  │  │
│    └──────────────────────────────┼──────────────────────────────────┘  │
│                                   │                                      │
│                                   ▼                                      │
│    ┌─────────────────────────────────────────────────────────────────┐  │
│    │                      ORCHESTRATION LAYER                         │  │
│    │                                                                  │  │
│    │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │  │
│    │  │   Platform      │  │   Platform      │  │    Retry        │ │  │
│    │  │   Detector      │──▶   Router        │──▶    Handler      │ │  │
│    │  │                 │  │                 │  │                 │ │  │
│    │  └─────────────────┘  └─────────────────┘  └─────────────────┘ │  │
│    │                                                                  │  │
│    └──────────────────────────────────────────────────────────────────┘  │
│                                   │                                      │
│                                   ▼                                      │
│    ┌─────────────────────────────────────────────────────────────────┐  │
│    │                       AGENT LAYER                                │  │
│    │                                                                  │  │
│    │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐  │  │
│    │  │  Facebook  │ │ Instagram  │ │  Twitter   │ │  LinkedIn  │  │  │
│    │  │   Agent    │ │   Agent    │ │   Agent    │ │   Agent    │  │  │
│    │  │            │ │            │ │            │ │            │  │  │
│    │  │ facebook_  │ │ instagram_ │ │ twitter_   │ │ linkedin_  │  │  │
│    │  │ poster.py  │ │ poster.py  │ │ poster.py  │ │ poster.py  │  │  │
│    │  └────────────┘ └────────────┘ └────────────┘ └────────────┘  │  │
│    │                                                                  │  │
│    └──────────────────────────────────────────────────────────────────┘  │
│                                   │                                      │
│                                   ▼                                      │
│    ┌─────────────────────────────────────────────────────────────────┐  │
│    │                       OUTPUT LAYER                               │  │
│    │                                                                  │  │
│    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │  │
│    │  │    Done/    │  │ Retry_Queue/│  │      Audit Logs         │ │  │
│    │  │  (success)  │  │  (failed)   │  │                         │ │  │
│    │  └─────────────┘  └─────────────┘  └─────────────────────────┘ │  │
│    │                                                                  │  │
│    └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                       INTEGRATION LAYER                                  │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐│
│  │   Audit      │  │    Retry     │  │   Circuit    │  │  Heartbeat   ││
│  │   Logger     │  │   Handler    │  │   Breaker    │  │   System     ││
│  │              │  │              │  │              │  │              ││
│  │ Full audit   │  │ Exponential  │  │ Failure      │  │ Watchdog     ││
│  │ trail of all │  │ backoff with │  │ protection   │  │ integration  ││
│  │ operations   │  │ 3 retries    │  │ threshold    │  │ & monitoring ││
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘│
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
[Approved/] → [Detect Platform] → [Check Circuit] → [Route to Agent]
                                                           │
                                                           ▼
                                                    [Execute Agent]
                                                           │
                                    ┌──────────────────────┼──────────────────────┐
                                    │ SUCCESS              │ FAILURE              │
                                    ▼                      ▼                      ▼
                              [Move to Done/]        [Retry?]              [Queue Post]
                                                    ↓       ↓
                                               YES  ↓       ↓ NO
                                           [Wait Delay]  [Log Failure]
                                                ↓
                                           [Retry Agent]
```

---

## Core Components

### 1. SocialMediaOrchestrator

The main orchestrator class that coordinates all operations.

```python
class SocialMediaOrchestrator:
    """
    Main orchestrator for social media posting.

    Responsibilities:
    - Scan Approved/ folder for posts
    - Detect platform from filename
    - Route to appropriate agent
    - Handle retries and failures
    - Maintain audit trail
    - Integrate with watchdog
    """

    ACTOR = "social_media_orchestrator"

    def __init__(self, dry_run=False, simulate=False, verbose=False):
        # Initialize integrations
        self.audit_logger = get_audit_logger()
        self.retry_handler = get_retry_handler(actor=self.ACTOR)
        self.circuit_breaker = get_circuit_breaker("social_posting")
        self.heartbeat = HeartbeatWriter(self.ACTOR)
        self.router = PlatformRouter()

    def run_cycle(self) -> CycleResult:
        """Execute a single processing cycle."""
        ...

    def run_daemon(self):
        """Run continuously as a daemon."""
        ...
```

### 2. PlatformDetector

Detects the target platform from filename or content.

```python
class PlatformDetector:
    @staticmethod
    def detect(filename: str) -> Platform:
        """
        Detection priority:
        1. Filename prefix (FACEBOOK_POST_, etc.)
        2. Content-based fallback (platform: facebook)
        """
```

### 3. PlatformRouter

Routes posts to the appropriate platform agent.

```python
class PlatformRouter:
    def route(self, post: SocialPost, dry_run: bool = False) -> Tuple[bool, Optional[str]]:
        """
        Route post to platform agent.

        Returns:
            (success, error_message)
        """
```

### 4. SocialPost

Data structure representing a social media post.

```python
@dataclass
class SocialPost:
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
```

---

## Platform Detection

### Filename-Based Detection (Primary)

The orchestrator uses filename prefixes as the primary detection method:

| Prefix | Platform | Example |
|--------|----------|---------|
| `FACEBOOK_POST_` | Facebook | `FACEBOOK_POST_20260225_promo.md` |
| `INSTAGRAM_POST_` | Instagram | `INSTAGRAM_POST_new_product.md` |
| `TWITTER_POST_` | Twitter/X | `TWITTER_POST_announcement.md` |
| `LINKEDIN_POST_` | LinkedIn | `LINKEDIN_POST_article.md` |

### Content-Based Detection (Fallback)

If filename prefix is not recognized, content is scanned:

```markdown
---
platform: facebook
scheduled: 2026-02-25 10:00
---

Post content here...
```

Or hashtag-based:
```markdown
This is my post content #facebook
```

### Detection Code

```python
def detect(filename: str) -> Platform:
    filename_upper = filename.upper()

    for prefix, platform_name in PREFIXES.items():
        if filename_upper.startswith(prefix):
            return Platform(platform_name)

    return Platform.UNKNOWN

def detect_from_content(content: str) -> Platform:
    content_lower = content.lower()

    if "platform: facebook" in content_lower:
        return Platform.FACEBOOK
    elif "platform: instagram" in content_lower:
        return Platform.INSTAGRAM
    # ... etc
```

---

## Platform Routing

### Agent Scripts

Each platform has a dedicated posting agent:

| Platform | Script | Arguments |
|----------|--------|-----------|
| Facebook | `scripts/facebook_poster.py` | `--post-file <path>` |
| Instagram | `scripts/instagram_poster.py` | `--post-file <path>` |
| Twitter | `scripts/twitter_poster.py` | `--post-file <path>` |
| LinkedIn | `scripts/linkedin_poster.py` | `--post-file <path>` |

### Routing Process

```python
def route(self, post: SocialPost) -> Tuple[bool, Optional[str]]:
    # 1. Get agent path
    agent_path = Config.AGENTS.get(post.platform.value)

    # 2. Verify agent exists
    if not agent_path or not agent_path.exists():
        return False, f"Agent not available for {post.platform.value}"

    # 3. Execute agent as subprocess
    result = subprocess.run(
        [sys.executable, str(agent_path),
         "--post-file", str(post.filepath)],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(Config.BASE_DIR)
    )

    # 4. Check result
    if result.returncode == 0:
        return True, None
    else:
        return False, result.stderr or result.stdout
```

### Subprocess Management

- **Timeout:** 120 seconds max per agent execution
- **Capture:** stdout and stderr captured for logging
- **Working Directory:** Set to project base directory
- **Isolation:** Each agent runs in separate process

---

## Retry & Error Handling

### Retry Strategy

```
Attempt 1: Immediate execution
    ↓ (failure)
    Wait 30 seconds
    ↓
Attempt 2: Retry
    ↓ (failure)
    Wait 60 seconds
    ↓
Attempt 3: Final retry
    ↓ (failure)
    Queue for later
```

### Configuration

```python
class Config:
    MAX_RETRIES = 3
    RETRY_DELAYS = [30, 60, 300]  # seconds
```

### Circuit Breaker

Prevents cascade failures by stopping requests after repeated failures:

```
CLOSED → Normal operation
    ↓ (5 failures)
OPEN → All requests blocked
    ↓ (300 seconds)
HALF_OPEN → Test single request
    ↓ (success)
CLOSED
```

### Error Categories

| Category | Example | Response |
|----------|---------|----------|
| Agent Missing | Script not found | Log error, skip platform |
| Agent Timeout | Execution > 120s | Kill process, retry |
| Agent Error | Non-zero exit code | Retry with backoff |
| Network Error | API unavailable | Retry with backoff |
| Rate Limit | Too many requests | Queue with longer delay |
| Auth Error | Invalid credentials | Log critical, stop |

### Failure Queue

Failed posts are moved to the retry queue with metadata:

```
Retry_Queue/
└── social/
    ├── INSTAGRAM_POST_promo.md           # Original file
    └── INSTAGRAM_POST_promo.md.meta.json # Failure metadata
```

Metadata structure:
```json
{
  "original_file": "INSTAGRAM_POST_promo.md",
  "platform": "instagram",
  "attempts": 3,
  "last_error": "Agent timeout after 120 seconds",
  "queued_at": "2026-02-25T10:30:00"
}
```

---

## Watchdog Integration

### Heartbeat System

The orchestrator sends regular heartbeats to the watchdog:

```python
class SocialMediaOrchestrator:
    def __init__(self):
        self.heartbeat = HeartbeatWriter("social_media_orchestrator")

    def run_cycle(self):
        # Update heartbeat with current task
        self.heartbeat.update_task(f"cycle:{cycle_id}")

        # Process posts...

        # Update to idle
        self.heartbeat.update_task("idle")

    def run_daemon(self):
        self.heartbeat.start()  # Begin heartbeat thread

        try:
            while self.running:
                self.run_cycle()
                self.heartbeat.update_task("sleeping")
                time.sleep(Config.SCAN_INTERVAL)
        finally:
            self.heartbeat.stop()  # Clean shutdown
```

### Heartbeat Data

```json
{
  "agent": "social_media_orchestrator",
  "pid": 1234,
  "timestamp": "2026-02-25T10:00:00",
  "status": "running",
  "current_task": "cycle:20260225_100000",
  "cpu_percent": 15.2,
  "memory_percent": 8.5,
  "tasks_completed": 45,
  "errors_count": 2
}
```

### Monitored Metrics

| Metric | Threshold | Action |
|--------|-----------|--------|
| Last heartbeat | > 60s | Warning |
| Last heartbeat | > 120s | Alert + possible restart |
| CPU usage | > 85% | Throttle |
| Memory usage | > 80% | Throttle |
| Error rate | > 50% | Circuit breaker |

---

## Audit Logging

### Event Types

```python
class SocialActionType(Enum):
    SOCIAL_POST_DETECTED = "social_post_detected"
    SOCIAL_POST_ROUTED = "social_post_routed"
    SOCIAL_POST_STARTED = "social_post_started"
    SOCIAL_POST_SUCCESS = "social_post_success"
    SOCIAL_POST_FAILED = "social_post_failed"
    SOCIAL_POST_RETRIED = "social_post_retried"
    SOCIAL_POST_QUEUED = "social_post_queued"
    SOCIAL_CYCLE_STARTED = "social_cycle_started"
    SOCIAL_CYCLE_COMPLETED = "social_cycle_completed"
```

### Event Examples

**Post Detected:**
```json
{
  "timestamp": "2026-02-25T10:00:00",
  "action": "social_post_detected",
  "actor": "social_media_orchestrator",
  "target": "FACEBOOK_POST_20260225.md",
  "parameters": {
    "platform": "facebook",
    "post_id": "POST_20260225_100000_FACEBOOK_POST"
  }
}
```

**Post Success:**
```json
{
  "timestamp": "2026-02-25T10:00:15",
  "action": "social_post_success",
  "actor": "social_media_orchestrator",
  "target": "FACEBOOK_POST_20260225.md",
  "parameters": {
    "platform": "facebook",
    "attempts": 1,
    "duration_ms": 15000
  },
  "result": "success"
}
```

**Cycle Completed:**
```json
{
  "timestamp": "2026-02-25T10:01:00",
  "action": "social_cycle_completed",
  "actor": "social_media_orchestrator",
  "target": "20260225_100000",
  "parameters": {
    "posts_detected": 5,
    "posts_success": 4,
    "posts_failed": 1,
    "posts_queued": 1,
    "duration_seconds": 60,
    "by_platform": {
      "facebook": 2,
      "instagram": 1,
      "twitter": 1,
      "linkedin": 1
    }
  }
}
```

---

## Configuration

### Default Configuration

```python
class Config:
    # Paths
    BASE_DIR = Path(__file__).parent.parent
    VAULT_DIR = BASE_DIR / "AI_Employee_Vault"
    APPROVED_DIR = VAULT_DIR / "Approved"
    DONE_DIR = VAULT_DIR / "Done"
    RETRY_QUEUE_DIR = VAULT_DIR / "Retry_Queue" / "social"
    LOGS_DIR = VAULT_DIR / "Logs"

    # Platform agents
    AGENTS = {
        "facebook": BASE_DIR / "scripts" / "facebook_poster.py",
        "instagram": BASE_DIR / "scripts" / "instagram_poster.py",
        "twitter": BASE_DIR / "scripts" / "twitter_poster.py",
        "linkedin": BASE_DIR / "scripts" / "linkedin_poster.py",
    }

    # File prefixes
    PREFIXES = {
        "FACEBOOK_POST_": "facebook",
        "INSTAGRAM_POST_": "instagram",
        "TWITTER_POST_": "twitter",
        "LINKEDIN_POST_": "linkedin",
    }

    # Timing
    SCAN_INTERVAL = 30      # seconds between scans
    MAX_POSTS_PER_CYCLE = 10

    # Retry
    MAX_RETRIES = 3
    RETRY_DELAYS = [30, 60, 300]  # seconds
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SOCIAL_SCAN_INTERVAL` | 30 | Seconds between scans |
| `SOCIAL_MAX_RETRIES` | 3 | Max retry attempts |
| `SOCIAL_AGENT_TIMEOUT` | 120 | Agent execution timeout |

---

## CLI Reference

### Basic Commands

```bash
# Run as daemon (continuous)
python3 scripts/social_media_orchestrator.py

# Run single cycle
python3 scripts/social_media_orchestrator.py --once

# Dry run (no file changes)
python3 scripts/social_media_orchestrator.py --dry-run

# Simulate (no actual posting)
python3 scripts/social_media_orchestrator.py --simulate

# Verbose output
python3 scripts/social_media_orchestrator.py --verbose
```

### Combined Examples

```bash
# Test single cycle without changes
python3 scripts/social_media_orchestrator.py --once --dry-run --verbose

# Daemon with simulation
python3 scripts/social_media_orchestrator.py --simulate --verbose
```

### Output Example

```
============================================================
   Social Media Orchestrator
   Gold Tier Phase 2 - Unified Posting Architecture
============================================================
   Mode: Daemon (Continuous)
   Dry Run: False
   Simulate: False
   Verbose: True
============================================================

[2026-02-25 10:00:00] [INFO] Starting Social Media Orchestrator in daemon mode
[2026-02-25 10:00:00] [INFO] Scan interval: 30 seconds
[2026-02-25 10:00:00] [DEBUG] === Starting cycle 20260225_100000 ===
[2026-02-25 10:00:00] [INFO] Found 3 social media post(s)
[2026-02-25 10:00:01] [DEBUG] Processing: FACEBOOK_POST_promo.md -> facebook
[2026-02-25 10:00:05] [INFO] SUCCESS: FACEBOOK_POST_promo.md -> facebook
[2026-02-25 10:00:06] [DEBUG] Processing: INSTAGRAM_POST_new.md -> instagram
[2026-02-25 10:00:10] [INFO] SUCCESS: INSTAGRAM_POST_new.md -> instagram
[2026-02-25 10:00:11] [DEBUG] Processing: TWITTER_POST_update.md -> twitter
[2026-02-25 10:00:15] [INFO] SUCCESS: TWITTER_POST_update.md -> twitter
[2026-02-25 10:00:15] [INFO] Cycle complete: 3/3 success, 0 failed, 0 queued
```

---

## File Structure

```
Bronze-tier/
├── scripts/
│   ├── social_media_orchestrator.py   # Main orchestrator
│   ├── facebook_poster.py             # Facebook agent
│   ├── instagram_poster.py            # Instagram agent
│   ├── twitter_poster.py              # Twitter agent
│   └── linkedin_poster.py             # LinkedIn agent
│
├── utils/
│   ├── audit_logger.py                # Audit logging
│   ├── retry_handler.py               # Retry logic
│   └── heartbeat.py                   # Watchdog integration
│
├── AI_Employee_Vault/
│   ├── Approved/                      # Input folder
│   │   ├── FACEBOOK_POST_*.md
│   │   ├── INSTAGRAM_POST_*.md
│   │   ├── TWITTER_POST_*.md
│   │   └── LINKEDIN_POST_*.md
│   │
│   ├── Done/                          # Successfully posted
│   │   └── *.md
│   │
│   ├── Retry_Queue/
│   │   └── social/                    # Failed posts
│   │       ├── *.md
│   │       └── *.meta.json
│   │
│   └── Logs/
│       └── social_orchestrator.log
│
├── .claude/skills/
│   └── social-orchestrator.md         # Skill definition
│
└── docs/
    └── SOCIAL_ORCHESTRATION_SYSTEM.md # This documentation
```

---

## Monitoring & Metrics

### Health Dashboard

The orchestrator contributes to `AI_Employee_Vault/Watchdog/health.json`:

```json
{
  "agents": {
    "social_media_orchestrator": {
      "status": "healthy",
      "pid": 1234,
      "uptime": "2h 30m",
      "last_heartbeat": "5s ago",
      "current_task": "idle"
    }
  }
}
```

### Cycle Metrics

Each cycle produces metrics in the audit log:

| Metric | Description |
|--------|-------------|
| `posts_detected` | Total posts found |
| `posts_routed` | Posts sent to agents |
| `posts_success` | Successfully posted |
| `posts_failed` | Failed after retries |
| `posts_queued` | Moved to retry queue |
| `duration_seconds` | Cycle duration |
| `by_platform` | Breakdown by platform |

### Performance Targets

| Metric | Target |
|--------|--------|
| Cycle duration | < 60 seconds |
| Success rate | > 95% |
| Heartbeat interval | < 10 seconds |
| Memory usage | < 100 MB |
| CPU usage | < 5% (idle) |

---

## Troubleshooting

### Common Issues

**Agent Not Found**
```
ERROR: Agent not available for instagram
```
Solution: Create `scripts/instagram_poster.py` or verify path in Config.AGENTS

**Circuit Breaker Open**
```
WARN: Circuit breaker open - queuing post
```
Solution: Wait for automatic reset (300s) or investigate underlying failures

**Heartbeat Stale**
```
Watchdog detected stale heartbeat for social_media_orchestrator
```
Solution: Check if orchestrator is stuck; may need restart

**Permission Denied**
```
ERROR: Cannot move file to Done/
```
Solution: Check file permissions on Done/ directory

### Debug Mode

Run with verbose flag to see detailed output:

```bash
python3 scripts/social_media_orchestrator.py --verbose --once
```

### Log Files

Check these locations for detailed logs:

1. **Console Output:** Real-time logs
2. **Audit Log:** `AI_Employee_Vault/Logs/audit_log.json`
3. **Watchdog:** `AI_Employee_Vault/Watchdog/health.json`
4. **Incidents:** `AI_Employee_Vault/Watchdog/incidents.json`

### Manual Testing

```bash
# Create test post
echo "Test Facebook post content" > AI_Employee_Vault/Approved/FACEBOOK_POST_test.md

# Run single cycle with dry-run
python3 scripts/social_media_orchestrator.py --once --dry-run --verbose

# Check if post was detected
# Output should show: "Found 1 social media post(s)"
```

---

## Related Documentation

- [Watchdog System](./WATCHDOG_SYSTEM.md) - Process monitoring
- [Error Recovery](./ERROR_RECOVERY_SYSTEM.md) - Retry handling
- [Audit Logging](./AUDIT_LOGGING_SYSTEM.md) - Event tracking

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-02-25 | Initial implementation |

---

*Gold Tier - Social Media Orchestration System*
*Personal AI Employee Hackathon*
