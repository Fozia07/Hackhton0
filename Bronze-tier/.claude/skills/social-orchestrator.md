# Social Media Orchestrator Skill

## Skill: social-orchestrator

**Tier:** Gold
**Component:** Phase 2, Step 1
**Version:** 1.0.0
**Status:** Implemented

---

## Overview

Enterprise-grade Social Media Orchestrator that provides unified posting architecture for all social media platforms. Routes approved posts to platform-specific agents with full retry handling, circuit breaker protection, and watchdog integration.

---

## Supported Platforms

| Platform | File Prefix | Agent Script |
|----------|-------------|--------------|
| Facebook | `FACEBOOK_POST_*.md` | `scripts/facebook_poster.py` |
| Instagram | `INSTAGRAM_POST_*.md` | `scripts/instagram_poster.py` |
| Twitter/X | `TWITTER_POST_*.md` | `scripts/twitter_poster.py` |
| LinkedIn | `LINKEDIN_POST_*.md` | `scripts/linkedin_poster.py` |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                  SOCIAL MEDIA ORCHESTRATOR                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐                                                   │
│  │   Approved/  │  ← Posts awaiting processing                      │
│  │   Folder     │                                                   │
│  └──────┬───────┘                                                   │
│         │                                                            │
│         ▼                                                            │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              PLATFORM DETECTOR                                │   │
│  │  ┌─────────────────────────────────────────────────────────┐ │   │
│  │  │  Filename Prefix Detection                              │ │   │
│  │  │  FACEBOOK_POST_* → Facebook                             │ │   │
│  │  │  INSTAGRAM_POST_* → Instagram                           │ │   │
│  │  │  TWITTER_POST_* → Twitter                               │ │   │
│  │  │  LINKEDIN_POST_* → LinkedIn                             │ │   │
│  │  └─────────────────────────────────────────────────────────┘ │   │
│  │  ┌─────────────────────────────────────────────────────────┐ │   │
│  │  │  Content-Based Fallback Detection                       │ │   │
│  │  │  "platform: facebook" / "#facebook" in content          │ │   │
│  │  └─────────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────┘   │
│         │                                                            │
│         ▼                                                            │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              PLATFORM ROUTER                                  │   │
│  │                                                               │   │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐ │   │
│  │  │ Facebook  │  │ Instagram │  │ Twitter   │  │ LinkedIn  │ │   │
│  │  │  Agent    │  │   Agent   │  │  Agent    │  │   Agent   │ │   │
│  │  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘ │   │
│  │        │              │              │              │        │   │
│  │        └──────────────┴──────────────┴──────────────┘        │   │
│  │                           │                                   │   │
│  └───────────────────────────┼───────────────────────────────────┘   │
│                              │                                       │
│         ┌────────────────────┼────────────────────┐                 │
│         │                    │                    │                  │
│         ▼                    ▼                    ▼                  │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐           │
│  │   Success   │     │   Failure   │     │  Queued     │           │
│  │  → Done/    │     │  → Retry    │     │  → Retry_   │           │
│  │             │     │             │     │    Queue/   │           │
│  └─────────────┘     └─────────────┘     └─────────────┘           │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│                     INTEGRATION LAYER                                │
│                                                                      │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐        │
│  │  Audit    │  │  Retry    │  │  Circuit  │  │ Heartbeat │        │
│  │  Logger   │  │  Handler  │  │  Breaker  │  │  System   │        │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘        │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Flow Diagram

```
                          ┌─────────────────┐
                          │   START CYCLE   │
                          └────────┬────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │  Scan Approved/ for posts    │
                    │  matching *_POST_*.md        │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                        ┌──────────────────┐
                        │  Posts found?    │
                        └────────┬─────────┘
                                 │
                    ┌────────────┴────────────┐
                    │ NO                      │ YES
                    ▼                         ▼
           ┌────────────────┐    ┌────────────────────────┐
           │  Sleep 30s     │    │  For each post:        │
           │  Next cycle    │    │  1. Detect platform    │
           └────────────────┘    │  2. Check circuit      │
                                 │  3. Route to agent     │
                                 └───────────┬────────────┘
                                             │
                                             ▼
                                  ┌──────────────────┐
                                  │ Circuit Breaker  │
                                  │    Open?         │
                                  └────────┬─────────┘
                                           │
                              ┌────────────┴────────────┐
                              │ YES                     │ NO
                              ▼                         ▼
                    ┌─────────────────┐     ┌─────────────────┐
                    │  Queue post     │     │  Execute agent  │
                    │  for retry      │     │  subprocess     │
                    └─────────────────┘     └────────┬────────┘
                                                     │
                                                     ▼
                                          ┌──────────────────┐
                                          │    Success?      │
                                          └────────┬─────────┘
                                                   │
                                      ┌────────────┴────────────┐
                                      │ YES                     │ NO
                                      ▼                         ▼
                            ┌─────────────────┐     ┌─────────────────┐
                            │  Move to Done/  │     │  Retry?         │
                            │  Record success │     │  attempt < 3    │
                            └─────────────────┘     └────────┬────────┘
                                                             │
                                                ┌────────────┴────────────┐
                                                │ YES                     │ NO
                                                ▼                         ▼
                                      ┌─────────────────┐     ┌─────────────────┐
                                      │  Wait delay     │     │  Queue post     │
                                      │  Retry routing  │     │  Log failure    │
                                      └─────────────────┘     └─────────────────┘
```

---

## Error Handling

### Retry Logic

| Attempt | Delay | Action |
|---------|-------|--------|
| 1st | Immediate | Execute agent |
| 2nd | 30 seconds | Retry after delay |
| 3rd | 60 seconds | Final retry |
| Failed | - | Queue for later |

### Error Categories

| Error Type | Detection | Response |
|------------|-----------|----------|
| Agent not found | Script missing | Skip platform, log error |
| Agent timeout | > 120 seconds | Kill process, retry |
| Agent failure | Non-zero exit | Retry with backoff |
| Circuit open | Too many failures | Queue all posts |
| File error | IO exception | Log and continue |

### Circuit Breaker Integration

```python
# Circuit breaker states
CLOSED      # Normal operation
HALF_OPEN   # Testing recovery
OPEN        # Blocking all requests

# Thresholds
failure_threshold = 5    # Failures to open circuit
reset_timeout = 300      # Seconds before half-open
```

---

## Watchdog Integration

The orchestrator fully integrates with the Watchdog system:

```python
from utils.heartbeat import HeartbeatWriter

class SocialMediaOrchestrator:
    def __init__(self):
        self.heartbeat = HeartbeatWriter("social_media_orchestrator")

    def run_cycle(self):
        self.heartbeat.update_task(f"cycle:{cycle_id}")
        # ... process posts ...
        self.heartbeat.update_task("idle")

    def run_daemon(self):
        self.heartbeat.start()
        try:
            while self.running:
                self.run_cycle()
                self.heartbeat.update_task("sleeping")
                time.sleep(30)
        finally:
            self.heartbeat.stop()
```

### Heartbeat Data

```json
{
  "agent": "social_media_orchestrator",
  "status": "running",
  "current_task": "cycle:20260225_100000",
  "tasks_completed": 45,
  "errors_count": 2
}
```

---

## Platform Routing Logic

### Detection Priority

1. **Filename Prefix** (Primary)
   - `FACEBOOK_POST_` → Facebook
   - `INSTAGRAM_POST_` → Instagram
   - `TWITTER_POST_` → Twitter
   - `LINKEDIN_POST_` → LinkedIn

2. **Content Detection** (Fallback)
   - `platform: facebook` in frontmatter
   - `#facebook` hashtag in content

### Routing Process

```python
class PlatformRouter:
    def route(self, post: SocialPost) -> Tuple[bool, Optional[str]]:
        # 1. Check agent exists
        agent_path = Config.AGENTS.get(post.platform.value)
        if not agent_path or not agent_path.exists():
            return False, "Agent not available"

        # 2. Execute agent subprocess
        result = subprocess.run(
            [sys.executable, str(agent_path),
             "--post-file", str(post.filepath)],
            timeout=120
        )

        # 3. Return result
        return result.returncode == 0, error_message
```

---

## CLI Usage

```bash
# Daemon mode (continuous)
python3 scripts/social_media_orchestrator.py

# Single cycle
python3 scripts/social_media_orchestrator.py --once

# Dry run (no file changes)
python3 scripts/social_media_orchestrator.py --dry-run

# Simulation (no actual posting)
python3 scripts/social_media_orchestrator.py --simulate

# Verbose output
python3 scripts/social_media_orchestrator.py --verbose

# Combined
python3 scripts/social_media_orchestrator.py --once --dry-run --verbose
```

---

## File Structure

```
scripts/
└── social_media_orchestrator.py    # Main orchestrator

AI_Employee_Vault/
├── Approved/                        # Input: posts to process
│   ├── FACEBOOK_POST_20260225.md
│   ├── INSTAGRAM_POST_promo.md
│   └── LINKEDIN_POST_article.md
├── Done/                            # Output: successful posts
│   └── FACEBOOK_POST_20260225.md
├── Retry_Queue/                     # Failed posts
│   └── social/
│       ├── INSTAGRAM_POST_promo.md
│       └── INSTAGRAM_POST_promo.md.meta.json
└── Logs/
    └── social_orchestrator.log
```

---

## Audit Logging Events

| Event | Description |
|-------|-------------|
| `social_post_detected` | Post found in Approved/ |
| `social_post_routed` | Platform identified, routing to agent |
| `social_post_started` | Agent execution started |
| `social_post_success` | Post published successfully |
| `social_post_failed` | Post failed after all retries |
| `social_post_retried` | Retry attempt initiated |
| `social_post_queued` | Post moved to retry queue |
| `social_cycle_started` | Processing cycle began |
| `social_cycle_completed` | Processing cycle finished |

---

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `SCAN_INTERVAL` | 30s | Time between scans |
| `MAX_POSTS_PER_CYCLE` | 10 | Max posts per cycle |
| `MAX_RETRIES` | 3 | Retry attempts |
| `RETRY_DELAYS` | [30, 60, 300] | Seconds between retries |
| `AGENT_TIMEOUT` | 120s | Agent execution timeout |

---

## Related Skills

- `watchdog-system.md` - Heartbeat/monitoring integration
- `error-recovery.md` - Retry handler integration
- `audit-logging.md` - Full audit trail

---

## Documentation

- `docs/SOCIAL_ORCHESTRATION_SYSTEM.md` - Full technical documentation

---

*Gold Tier - Social Media Orchestrator*
*Personal AI Employee Hackathon*
