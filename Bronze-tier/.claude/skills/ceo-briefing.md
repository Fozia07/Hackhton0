# CEO Briefing Generator Skill

## Overview

Enterprise-grade automated system that generates comprehensive "Monday Morning CEO Briefing" reports. Analyzes business performance, financial health, productivity metrics, and system reliability to provide actionable executive insights.

## Skill Metadata

```yaml
name: ceo-briefing
version: 1.0.0
tier: Gold
category: business-intelligence
trigger: scheduled (Sunday 23:00) | manual
execution_time: ~30 seconds
output: CEO_Briefings/CEO_Briefing_YYYY-MM-DD.md
```

## Purpose

Transform raw business data into executive-ready intelligence:
- Aggregate financial transactions and calculate KPIs
- Measure productivity and identify bottlenecks
- Score business health and system reliability
- Generate actionable recommendations
- Predict trends and identify opportunities

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    CEO BRIEFING GENERATION PIPELINE                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                      DATA COLLECTION LAYER                        │   │
│  ├──────────────────────────────────────────────────────────────────┤   │
│  │                                                                    │   │
│  │  Business_Goals.md    Bank_Transactions.md    /Done/    /Logs/   │   │
│  │        │                      │                 │          │      │   │
│  │        ▼                      ▼                 ▼          ▼      │   │
│  │  ┌──────────┐          ┌──────────┐      ┌──────────┐ ┌────────┐ │   │
│  │  │  Goals   │          │ Finance  │      │  Tasks   │ │ System │ │   │
│  │  │  Parser  │          │  Parser  │      │  Parser  │ │ Parser │ │   │
│  │  └────┬─────┘          └────┬─────┘      └────┬─────┘ └───┬────┘ │   │
│  └───────┼─────────────────────┼────────────────┼────────────┼──────┘   │
│          │                     │                │            │          │
│          ▼                     ▼                ▼            ▼          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                      ANALYSIS ENGINE                              │   │
│  ├──────────────────────────────────────────────────────────────────┤   │
│  │                                                                    │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────┐ │   │
│  │  │  Financial  │  │Productivity │  │    Risk     │  │  Trend   │ │   │
│  │  │  Analyzer   │  │  Analyzer   │  │  Analyzer   │  │ Analyzer │ │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └────┬─────┘ │   │
│  │         │                │                │              │        │   │
│  │         └────────────────┴────────────────┴──────────────┘        │   │
│  │                                │                                   │   │
│  └────────────────────────────────┼───────────────────────────────────┘   │
│                                   ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    INTELLIGENCE LAYER                             │   │
│  ├──────────────────────────────────────────────────────────────────┤   │
│  │                                                                    │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐   │   │
│  │  │  Health Score   │  │ Recommendations │  │   Predictions   │   │   │
│  │  │   Calculator    │  │     Engine      │  │     Engine      │   │   │
│  │  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘   │   │
│  │           │                    │                    │            │   │
│  └───────────┴────────────────────┴────────────────────┴────────────┘   │
│                                   │                                       │
│                                   ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    REPORT GENERATOR                               │   │
│  ├──────────────────────────────────────────────────────────────────┤   │
│  │                                                                    │   │
│  │              CEO_Briefings/CEO_Briefing_YYYY-MM-DD.md            │   │
│  │                                                                    │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Input Sources

| Source | Path | Purpose |
|--------|------|---------|
| Business Goals | `AI_Employee_Vault/Business_Goals.md` | Targets, KPIs, objectives |
| Bank Transactions | `AI_Employee_Vault/Bank_Transactions.md` | Financial records |
| Completed Tasks | `AI_Employee_Vault/Done/` | Productivity tracking |
| System Logs | `AI_Employee_Vault/Logs/` | Reliability metrics |

## Output Contract

### File Location
```
AI_Employee_Vault/CEO_Briefings/CEO_Briefing_YYYY-MM-DD.md
```

### Report Structure

```markdown
# Monday Morning CEO Briefing
## Week of YYYY-MM-DD

### 1. Executive Summary
- One-paragraph business health overview
- Key wins and concerns
- Critical action items

### 2. Business Health Score: XX/100
- Score breakdown by category
- Trend indicator (↑↓→)
- Comparison to previous week

### 3. Financial Analysis
- Revenue summary
- Expense breakdown
- Cashflow status
- Budget variance

### 4. Productivity Metrics
- Tasks completed
- Average completion time
- Efficiency score
- Team performance

### 5. Bottlenecks & Risks
- Delayed tasks
- Resource constraints
- External risks
- Mitigation strategies

### 6. AI Recommendations
- Priority actions
- Optimization opportunities
- Cost-saving suggestions
- Growth strategies

### 7. Next Week Strategy
- Focus areas
- Key deliverables
- Resource allocation
- Success criteria

### 8. System Reliability
- Uptime percentage
- Error rate
- Processing efficiency
- Health indicators
```

## Invocation

### Manual Execution
```bash
# Generate briefing for current week
python3 scripts/ceo_briefing_generator.py

# Dry run (preview without saving)
python3 scripts/ceo_briefing_generator.py --dry-run

# Generate with verbose output
python3 scripts/ceo_briefing_generator.py --verbose

# Generate for specific date
python3 scripts/ceo_briefing_generator.py --date 2026-02-24

# Simulation mode (use sample data)
python3 scripts/ceo_briefing_generator.py --simulate
```

### Scheduled Execution (Cron)
```bash
# Run every Sunday at 11:00 PM
0 23 * * 0 cd /path/to/Bronze-tier && python3 scripts/ceo_briefing_generator.py >> AI_Employee_Vault/Logs/ceo_briefing.log 2>&1
```

## Scoring Algorithms

### Business Health Score (0-100)

| Component | Weight | Factors |
|-----------|--------|---------|
| Financial Health | 35% | Revenue vs target, expense ratio, cashflow |
| Productivity | 25% | Task completion rate, efficiency |
| Goal Progress | 20% | KPI achievement, milestone completion |
| System Reliability | 10% | Uptime, error rate |
| Risk Posture | 10% | Risk count, severity, mitigation |

### Risk Severity Scoring

| Level | Score | Criteria |
|-------|-------|----------|
| Critical | 5 | Business-threatening, immediate action |
| High | 4 | Significant impact, urgent attention |
| Medium | 3 | Moderate impact, planned response |
| Low | 2 | Minor impact, monitor |
| Info | 1 | Awareness only |

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Missing Business_Goals.md | Generate with defaults, flag warning |
| Missing Bank_Transactions.md | Use simulation data, note in report |
| Empty Done folder | Report zero productivity, alert |
| Corrupted log files | Skip, log error, continue |
| Write permission denied | Fail gracefully, output to stdout |

## Dependencies

- Python 3.10+
- No external packages (standard library only)
- Read access to vault folders
- Write access to CEO_Briefings folder

## Security Considerations

- No sensitive data in logs
- Financial figures aggregated (no raw transactions)
- Report marked as confidential
- Access control via filesystem permissions

---

*CEO Briefing Generator Skill - Gold Tier*
*Enterprise-Grade Business Intelligence*
