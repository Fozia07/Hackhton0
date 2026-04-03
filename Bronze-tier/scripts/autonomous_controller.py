#!/usr/bin/env python3
"""
Autonomous Controller
=====================

Final Gold Tier Step - Autonomous Trigger & Self-Improving Loop

This controller completes the full self-improving AI lifecycle:
1. Runs analytics engine
2. Reads strategy insights
3. Evaluates trigger conditions
4. Automatically triggers campaign engine if needed
5. Logs all decisions with full audit trail
6. Prevents infinite execution loops

Execution Flow:
    Analytics → Insights → Evaluate → Decision → Action → Report

Usage:
    python3 scripts/autonomous_controller.py
    python3 scripts/autonomous_controller.py --force
    python3 scripts/autonomous_controller.py --dry-run
    python3 scripts/autonomous_controller.py --verbose

Exit Codes:
    0 - Successful run
    1 - Analytics failure
    2 - Campaign trigger failure
    3 - Unexpected system error

Author: AI Employee System
Version: 1.0.0
"""

import os
import sys
import json
import subprocess
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.audit_logger import get_audit_logger, ActionType, ResultStatus


# ==============================================================================
# EXIT CODES
# ==============================================================================

class ExitCode:
    SUCCESS = 0
    ANALYTICS_FAILURE = 1
    CAMPAIGN_FAILURE = 2
    SYSTEM_ERROR = 3


# ==============================================================================
# CONFIGURATION
# ==============================================================================

class Config:
    BASE_DIR = Path(__file__).parent.parent
    VAULT_DIR = BASE_DIR / "AI_Employee_Vault"
    SCRIPTS_DIR = BASE_DIR / "scripts"

    # Input paths
    INSIGHTS_FILE = VAULT_DIR / "Analytics" / "strategy_insights.json"

    # Output paths
    SYSTEM_DIR = VAULT_DIR / "System"
    EXECUTIVE_DIR = VAULT_DIR / "Executive"
    STATE_FILE = SYSTEM_DIR / "autonomous_state.json"

    # Scripts
    ANALYTICS_SCRIPT = SCRIPTS_DIR / "social_analytics_engine.py"
    CAMPAIGN_SCRIPT = SCRIPTS_DIR / "social_campaign_engine.py"

    # Loop protection
    MIN_HOURS_BETWEEN_TRIGGERS = 24
    MAX_TRIGGERS_PER_WEEK = 3

    # Thresholds
    PLATFORM_RATIO_THRESHOLD = 0.50  # worst < 50% of best triggers action
    ENGAGEMENT_CRITICAL_THRESHOLD = 100  # absolute minimum engagement

    # Actor
    ACTOR = "autonomous_controller"


# ==============================================================================
# ENUMS
# ==============================================================================

class TriggerReason(Enum):
    DECLINING_TREND = "declining_engagement_trend"
    CRITICAL_TREND = "critical_engagement_trend"
    IMPROVEMENT_RECOMMENDED = "improvement_recommendations_detected"
    PLATFORM_IMBALANCE = "platform_performance_imbalance"
    LOW_ENGAGEMENT = "critically_low_engagement"
    FORCED = "manual_force_trigger"
    SCHEDULED = "scheduled_optimization"


class DecisionOutcome(Enum):
    TRIGGERED = "campaign_triggered"
    SKIPPED_COOLDOWN = "skipped_cooldown_active"
    SKIPPED_NO_TRIGGER = "skipped_no_trigger_conditions"
    SKIPPED_DRY_RUN = "skipped_dry_run_mode"
    FAILED = "trigger_failed"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class StrategyInsights:
    """Strategy insights from analytics engine."""
    best_platform: str = ""
    worst_platform: str = ""
    best_theme: str = ""
    worst_theme: str = ""
    best_posting_times: Dict[str, str] = field(default_factory=dict)
    engagement_trend: str = "stable"
    recommendations: List[str] = field(default_factory=list)
    alerts: List[str] = field(default_factory=list)
    generated_at: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StrategyInsights':
        return cls(
            best_platform=data.get("best_platform", ""),
            worst_platform=data.get("worst_platform", ""),
            best_theme=data.get("best_theme", ""),
            worst_theme=data.get("worst_theme", ""),
            best_posting_times=data.get("best_posting_times", {}),
            engagement_trend=data.get("engagement_trend", "stable"),
            recommendations=data.get("recommendations", []),
            alerts=data.get("alerts", []),
            generated_at=data.get("generated_at", ""),
        )


@dataclass
class AutonomousState:
    """Persistent state for loop protection."""
    last_trigger_timestamp: Optional[str] = None
    trigger_count_this_week: int = 0
    week_start: Optional[str] = None
    last_decision: Optional[str] = None
    last_reason: Optional[str] = None
    history: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AutonomousState':
        return cls(
            last_trigger_timestamp=data.get("last_trigger_timestamp"),
            trigger_count_this_week=data.get("trigger_count_this_week", 0),
            week_start=data.get("week_start"),
            last_decision=data.get("last_decision"),
            last_reason=data.get("last_reason"),
            history=data.get("history", []),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TriggerCondition:
    """Represents a trigger condition evaluation."""
    name: str
    triggered: bool
    reason: TriggerReason
    details: str
    severity: str  # low, medium, high, critical


@dataclass
class AutonomyDecision:
    """Complete autonomy decision record."""
    timestamp: str
    analytics_success: bool
    insights_loaded: bool
    conditions_evaluated: List[TriggerCondition]
    triggered_conditions: List[str]
    decision: DecisionOutcome
    reasoning: str
    campaign_triggered: bool
    campaign_success: Optional[bool]
    cooldown_active: bool
    safety_checks_passed: bool
    execution_time_ms: float


# ==============================================================================
# AUTONOMOUS CONTROLLER
# ==============================================================================

class AutonomousController:
    """
    Main autonomous controller for self-improving AI lifecycle.

    Orchestrates the complete feedback loop:
    Analytics → Insights → Evaluate → Decision → Action → Report
    """

    def __init__(self, verbose: bool = False, dry_run: bool = False, force: bool = False):
        self.verbose = verbose
        self.dry_run = dry_run
        self.force = force
        self.audit_logger = get_audit_logger()
        self.state: Optional[AutonomousState] = None
        self.insights: Optional[StrategyInsights] = None
        self.start_time = datetime.now()

    def _log(self, message: str, level: str = "INFO"):
        """Print timestamped log message."""
        if self.verbose or level in ("ERROR", "WARN", "ALERT", "DECISION"):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] [{level}] {message}")

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
            action_type=ActionType.TASK_STARTED,
            actor=Config.ACTOR,
            target=target,
            parameters={"action": action, **(parameters or {})},
            result=result,
            error=error
        )

    # ==========================================================================
    # STATE MANAGEMENT
    # ==========================================================================

    def load_state(self) -> AutonomousState:
        """Load autonomous state from file."""
        self._log("Loading autonomous state...")

        Config.SYSTEM_DIR.mkdir(parents=True, exist_ok=True)

        if Config.STATE_FILE.exists():
            try:
                with open(Config.STATE_FILE, 'r') as f:
                    data = json.load(f)
                self.state = AutonomousState.from_dict(data)
                self._log(f"State loaded: last trigger={self.state.last_trigger_timestamp}")
            except Exception as e:
                self._log(f"Error loading state: {e}", "WARN")
                self.state = AutonomousState()
        else:
            self._log("No existing state - initializing fresh")
            self.state = AutonomousState()

        # Reset weekly counter if new week
        self._check_weekly_reset()

        return self.state

    def save_state(self):
        """Save autonomous state to file."""
        if self.dry_run:
            self._log("[DRY-RUN] Would save state")
            return

        try:
            Config.SYSTEM_DIR.mkdir(parents=True, exist_ok=True)
            with open(Config.STATE_FILE, 'w') as f:
                json.dump(self.state.to_dict(), f, indent=2)
            self._log("State saved")
        except Exception as e:
            self._log(f"Error saving state: {e}", "ERROR")

    def _check_weekly_reset(self):
        """Reset weekly counter if it's a new week."""
        now = datetime.now()
        current_week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")

        if self.state.week_start != current_week_start:
            self._log("New week detected - resetting trigger counter")
            self.state.week_start = current_week_start
            self.state.trigger_count_this_week = 0

    def update_state(self, decision: DecisionOutcome, reason: str, triggered: bool):
        """Update state after decision."""
        now = datetime.now()

        self.state.last_decision = decision.value
        self.state.last_reason = reason

        if triggered:
            self.state.last_trigger_timestamp = now.isoformat()
            self.state.trigger_count_this_week += 1

        # Add to history (keep last 10)
        self.state.history.append({
            "timestamp": now.isoformat(),
            "decision": decision.value,
            "reason": reason,
            "triggered": triggered,
        })
        self.state.history = self.state.history[-10:]

        self.save_state()

    # ==========================================================================
    # ANALYTICS EXECUTION
    # ==========================================================================

    def run_analytics(self) -> bool:
        """Run social analytics engine via subprocess."""
        self._log("Running analytics engine...")

        if not Config.ANALYTICS_SCRIPT.exists():
            self._log(f"Analytics script not found: {Config.ANALYTICS_SCRIPT}", "ERROR")
            return False

        try:
            cmd = [sys.executable, str(Config.ANALYTICS_SCRIPT)]
            if self.verbose:
                cmd.append("--verbose")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(Config.BASE_DIR)
            )

            if result.returncode == 0:
                self._log("Analytics completed successfully")
                return True
            elif result.returncode == 1:
                self._log("Analytics skipped - no metrics file", "WARN")
                return False
            else:
                self._log(f"Analytics failed with code {result.returncode}", "ERROR")
                if self.verbose and result.stderr:
                    self._log(f"Error: {result.stderr[:500]}", "ERROR")
                return False

        except subprocess.TimeoutExpired:
            self._log("Analytics timed out after 300 seconds", "ERROR")
            return False
        except Exception as e:
            self._log(f"Analytics execution error: {e}", "ERROR")
            return False

    # ==========================================================================
    # INSIGHTS LOADING
    # ==========================================================================

    def load_insights(self) -> bool:
        """Load strategy insights from JSON file."""
        self._log("Loading strategy insights...")

        if not Config.INSIGHTS_FILE.exists():
            self._log("Insights file not found", "WARN")
            return False

        try:
            with open(Config.INSIGHTS_FILE, 'r') as f:
                data = json.load(f)

            self.insights = StrategyInsights.from_dict(data)
            self._log(f"Insights loaded: trend={self.insights.engagement_trend}, "
                     f"best={self.insights.best_platform}")
            return True

        except json.JSONDecodeError as e:
            self._log(f"Invalid JSON in insights file: {e}", "ERROR")
            return False
        except Exception as e:
            self._log(f"Error loading insights: {e}", "ERROR")
            return False

    # ==========================================================================
    # TRIGGER CONDITION EVALUATION
    # ==========================================================================

    def evaluate_trigger_conditions(self) -> List[TriggerCondition]:
        """Evaluate all trigger conditions."""
        self._log("Evaluating trigger conditions...")

        conditions = []

        if not self.insights:
            return conditions

        # Condition 1: Declining engagement trend
        if self.insights.engagement_trend == "declining":
            conditions.append(TriggerCondition(
                name="Declining Engagement Trend",
                triggered=True,
                reason=TriggerReason.DECLINING_TREND,
                details=f"Engagement trend is '{self.insights.engagement_trend}'",
                severity="high"
            ))
        elif self.insights.engagement_trend == "critical":
            conditions.append(TriggerCondition(
                name="Critical Engagement Trend",
                triggered=True,
                reason=TriggerReason.CRITICAL_TREND,
                details="Engagement has dropped critically",
                severity="critical"
            ))
        else:
            conditions.append(TriggerCondition(
                name="Engagement Trend Check",
                triggered=False,
                reason=TriggerReason.DECLINING_TREND,
                details=f"Engagement trend is '{self.insights.engagement_trend}' (acceptable)",
                severity="low"
            ))

        # Condition 2: Improvement recommendations
        improvement_keywords = ["increase", "improve", "boost", "optimize", "enhance"]
        improvement_recs = [
            r for r in self.insights.recommendations
            if any(kw in r.lower() for kw in improvement_keywords)
        ]

        if improvement_recs:
            conditions.append(TriggerCondition(
                name="Improvement Recommendations",
                triggered=True,
                reason=TriggerReason.IMPROVEMENT_RECOMMENDED,
                details=f"Found {len(improvement_recs)} improvement recommendations",
                severity="medium"
            ))
        else:
            conditions.append(TriggerCondition(
                name="Improvement Recommendations",
                triggered=False,
                reason=TriggerReason.IMPROVEMENT_RECOMMENDED,
                details="No improvement recommendations found",
                severity="low"
            ))

        # Condition 3: Platform imbalance
        # This would need actual engagement data - using alerts as proxy
        platform_alerts = [
            a for a in self.insights.alerts
            if "platform" in a.lower() or self.insights.worst_platform in a.lower()
        ]

        if platform_alerts:
            conditions.append(TriggerCondition(
                name="Platform Performance Imbalance",
                triggered=True,
                reason=TriggerReason.PLATFORM_IMBALANCE,
                details=f"Platform alerts detected for {self.insights.worst_platform}",
                severity="medium"
            ))
        elif self.insights.worst_platform and self.insights.best_platform:
            # Check if worst platform is significantly underperforming
            conditions.append(TriggerCondition(
                name="Platform Performance Imbalance",
                triggered=False,
                reason=TriggerReason.PLATFORM_IMBALANCE,
                details=f"Best: {self.insights.best_platform}, Worst: {self.insights.worst_platform}",
                severity="low"
            ))

        # Condition 4: Critical alerts
        if self.insights.alerts:
            conditions.append(TriggerCondition(
                name="Critical Alerts",
                triggered=True,
                reason=TriggerReason.LOW_ENGAGEMENT,
                details=f"{len(self.insights.alerts)} critical alert(s) detected",
                severity="high"
            ))
        else:
            conditions.append(TriggerCondition(
                name="Critical Alerts",
                triggered=False,
                reason=TriggerReason.LOW_ENGAGEMENT,
                details="No critical alerts",
                severity="low"
            ))

        # Condition 5: Force trigger
        if self.force:
            conditions.append(TriggerCondition(
                name="Manual Force Trigger",
                triggered=True,
                reason=TriggerReason.FORCED,
                details="User requested forced trigger via --force flag",
                severity="high"
            ))

        # Log conditions
        for cond in conditions:
            status = "TRIGGERED" if cond.triggered else "OK"
            self._log(f"  [{status}] {cond.name}: {cond.details}")

        return conditions

    def check_cooldown(self) -> Tuple[bool, str]:
        """Check if cooldown period is active."""
        if self.force:
            return False, "Cooldown bypassed via --force flag"

        if not self.state.last_trigger_timestamp:
            return False, "No previous trigger recorded"

        try:
            last_trigger = datetime.fromisoformat(self.state.last_trigger_timestamp)
            hours_since = (datetime.now() - last_trigger).total_seconds() / 3600

            if hours_since < Config.MIN_HOURS_BETWEEN_TRIGGERS:
                remaining = Config.MIN_HOURS_BETWEEN_TRIGGERS - hours_since
                return True, f"Cooldown active: {remaining:.1f} hours remaining"

        except Exception:
            pass

        # Check weekly limit
        if self.state.trigger_count_this_week >= Config.MAX_TRIGGERS_PER_WEEK:
            return True, f"Weekly limit reached: {self.state.trigger_count_this_week}/{Config.MAX_TRIGGERS_PER_WEEK}"

        return False, "Cooldown not active"

    def should_trigger(self, conditions: List[TriggerCondition]) -> Tuple[bool, str]:
        """Determine if campaign should be triggered based on conditions."""
        triggered_conditions = [c for c in conditions if c.triggered]

        if not triggered_conditions:
            return False, "No trigger conditions met"

        # Check for critical conditions
        critical = [c for c in triggered_conditions if c.severity == "critical"]
        if critical:
            return True, f"Critical condition: {critical[0].name}"

        # Check for high severity conditions
        high = [c for c in triggered_conditions if c.severity == "high"]
        if high:
            return True, f"High priority: {high[0].name}"

        # Check for multiple medium conditions
        medium = [c for c in triggered_conditions if c.severity == "medium"]
        if len(medium) >= 2:
            return True, f"Multiple improvement opportunities ({len(medium)} conditions)"

        # Single medium condition - trigger if force or declining
        if medium:
            if self.force:
                return True, f"Forced: {medium[0].name}"
            for c in medium:
                if c.reason == TriggerReason.IMPROVEMENT_RECOMMENDED:
                    return True, f"Optimization opportunity: {c.name}"

        return False, "Conditions not severe enough to trigger"

    # ==========================================================================
    # CAMPAIGN TRIGGERING
    # ==========================================================================

    def trigger_campaign_if_needed(
        self,
        conditions: List[TriggerCondition]
    ) -> Tuple[bool, DecisionOutcome, str]:
        """Trigger campaign engine if conditions warrant."""

        # Check cooldown first
        cooldown_active, cooldown_reason = self.check_cooldown()
        if cooldown_active:
            self._log(f"Cooldown: {cooldown_reason}", "DECISION")
            return False, DecisionOutcome.SKIPPED_COOLDOWN, cooldown_reason

        # Evaluate trigger decision
        should_trigger, trigger_reason = self.should_trigger(conditions)

        if not should_trigger:
            self._log(f"Decision: No trigger - {trigger_reason}", "DECISION")
            return False, DecisionOutcome.SKIPPED_NO_TRIGGER, trigger_reason

        # Dry run check
        if self.dry_run:
            self._log(f"[DRY-RUN] Would trigger campaign: {trigger_reason}", "DECISION")
            return False, DecisionOutcome.SKIPPED_DRY_RUN, f"Dry run - {trigger_reason}"

        # Execute trigger
        self._log(f"TRIGGERING CAMPAIGN: {trigger_reason}", "DECISION")
        self._log("=" * 50, "DECISION")

        success = self._execute_campaign_trigger()

        if success:
            self._log("Campaign triggered successfully", "DECISION")
            return True, DecisionOutcome.TRIGGERED, trigger_reason
        else:
            self._log("Campaign trigger FAILED", "ERROR")
            return False, DecisionOutcome.FAILED, f"Execution failed - {trigger_reason}"

    def _execute_campaign_trigger(self) -> bool:
        """Execute the campaign engine subprocess."""
        self._log("Executing campaign engine...")

        if not Config.CAMPAIGN_SCRIPT.exists():
            self._log(f"Campaign script not found: {Config.CAMPAIGN_SCRIPT}", "ERROR")
            return False

        try:
            cmd = [sys.executable, str(Config.CAMPAIGN_SCRIPT)]
            if self.verbose:
                cmd.append("--verbose")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
                cwd=str(Config.BASE_DIR)
            )

            if result.returncode == 0:
                self._log("Campaign engine completed successfully")
                return True
            else:
                self._log(f"Campaign engine failed with code {result.returncode}", "ERROR")
                if result.stderr:
                    self._log(f"Error: {result.stderr[:500]}", "ERROR")
                return False

        except subprocess.TimeoutExpired:
            self._log("Campaign engine timed out after 600 seconds", "ERROR")
            return False
        except Exception as e:
            self._log(f"Campaign execution error: {e}", "ERROR")
            return False

    # ==========================================================================
    # REPORTING
    # ==========================================================================

    def save_autonomy_report(
        self,
        decision: AutonomyDecision,
        conditions: List[TriggerCondition]
    ) -> str:
        """Generate and save autonomy decision report."""
        self._log("Generating autonomy report...")

        if self.dry_run:
            self._log("[DRY-RUN] Would save autonomy report")
            return ""

        Config.EXECUTIVE_DIR.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"autonomy_decision_{date_str}.md"
        filepath = Config.EXECUTIVE_DIR / filename

        lines = [
            "# Autonomy Decision Report",
            "",
            f"**Generated:** {decision.timestamp}",
            f"**Execution Time:** {decision.execution_time_ms:.0f}ms",
            "",
            "---",
            "",
            "## Summary",
            "",
            f"- **Decision:** {decision.decision.value.replace('_', ' ').title()}",
            f"- **Campaign Triggered:** {'Yes' if decision.campaign_triggered else 'No'}",
            f"- **Reasoning:** {decision.reasoning}",
            "",
            "---",
            "",
            "## Analytics Summary",
            "",
            f"- **Analytics Execution:** {'Success' if decision.analytics_success else 'Failed'}",
            f"- **Insights Loaded:** {'Yes' if decision.insights_loaded else 'No'}",
            "",
        ]

        if self.insights:
            lines.extend([
                f"- **Engagement Trend:** {self.insights.engagement_trend}",
                f"- **Best Platform:** {self.insights.best_platform}",
                f"- **Worst Platform:** {self.insights.worst_platform}",
                f"- **Best Theme:** {self.insights.best_theme}",
                f"- **Alerts:** {len(self.insights.alerts)}",
                f"- **Recommendations:** {len(self.insights.recommendations)}",
                "",
            ])

        lines.extend([
            "---",
            "",
            "## Trigger Conditions Evaluated",
            "",
            "| Condition | Status | Severity | Details |",
            "|-----------|--------|----------|---------|",
        ])

        for cond in conditions:
            status = "TRIGGERED" if cond.triggered else "OK"
            lines.append(f"| {cond.name} | {status} | {cond.severity} | {cond.details[:50]} |")

        lines.extend([
            "",
            "---",
            "",
            "## Triggered Conditions",
            "",
        ])

        if decision.triggered_conditions:
            for tc in decision.triggered_conditions:
                lines.append(f"- {tc}")
        else:
            lines.append("- None")

        lines.extend([
            "",
            "---",
            "",
            "## Safety Checks",
            "",
            f"- **Cooldown Status:** {'Active' if decision.cooldown_active else 'Inactive'}",
            f"- **Safety Checks Passed:** {'Yes' if decision.safety_checks_passed else 'No'}",
            f"- **Triggers This Week:** {self.state.trigger_count_this_week}/{Config.MAX_TRIGGERS_PER_WEEK}",
            "",
        ])

        if self.state.last_trigger_timestamp:
            lines.append(f"- **Last Trigger:** {self.state.last_trigger_timestamp}")

        lines.extend([
            "",
            "---",
            "",
            "## Decision Reasoning",
            "",
            decision.reasoning,
            "",
        ])

        if decision.campaign_triggered:
            lines.extend([
                "---",
                "",
                "## Campaign Execution",
                "",
                f"- **Triggered:** Yes",
                f"- **Success:** {'Yes' if decision.campaign_success else 'No'}",
                "",
            ])

        lines.extend([
            "---",
            "",
            "## Next Actions",
            "",
        ])

        if decision.campaign_triggered and decision.campaign_success:
            lines.extend([
                "1. Review generated campaign drafts in `AI_Employee_Vault/Drafts/`",
                "2. Approve posts via approval workflow",
                "3. Monitor orchestrator for posting execution",
                "4. Schedule next analytics review in 24-48 hours",
            ])
        elif decision.decision == DecisionOutcome.SKIPPED_COOLDOWN:
            lines.extend([
                "1. Wait for cooldown period to expire",
                "2. Re-run autonomous controller after cooldown",
                "3. Review current campaign performance manually",
            ])
        else:
            lines.extend([
                "1. Continue monitoring current campaign performance",
                "2. Review analytics dashboard for trends",
                "3. Schedule next autonomous run in 24 hours",
            ])

        lines.extend([
            "",
            "---",
            "",
            "*Generated by Autonomous Controller - Gold Tier*",
        ])

        content = "\n".join(lines)

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            self._log(f"Autonomy report saved: {filename}")
            return str(filepath)
        except Exception as e:
            self._log(f"Error saving report: {e}", "ERROR")
            return ""

    # ==========================================================================
    # MAIN EXECUTION
    # ==========================================================================

    def run(self) -> int:
        """Execute the autonomous control workflow."""
        self._log("=" * 60)
        self._log("AUTONOMOUS CONTROLLER - Gold Tier")
        self._log("Self-Improving AI Lifecycle Engine")
        self._log("=" * 60)

        if self.dry_run:
            self._log("[DRY-RUN MODE] No changes will be made")
        if self.force:
            self._log("[FORCE MODE] Cooldown bypassed")

        self._audit_log(
            action="autonomous_cycle_started",
            target="ai_lifecycle",
            parameters={
                "dry_run": self.dry_run,
                "force": self.force,
            },
            result=ResultStatus.PENDING
        )

        # Initialize tracking
        analytics_success = False
        insights_loaded = False
        conditions: List[TriggerCondition] = []
        campaign_triggered = False
        campaign_success = None
        decision_outcome = DecisionOutcome.SKIPPED_NO_TRIGGER
        decision_reason = "Initialization"

        try:
            # Step 1: Load state
            self.load_state()

            # Check cooldown early
            cooldown_active, cooldown_reason = self.check_cooldown()

            # Step 2: Run analytics
            analytics_success = self.run_analytics()

            if not analytics_success:
                self._log("Analytics failed - cannot proceed", "ERROR")
                decision_outcome = DecisionOutcome.FAILED
                decision_reason = "Analytics execution failed"

                # Still generate report
                decision = AutonomyDecision(
                    timestamp=datetime.now().isoformat(),
                    analytics_success=False,
                    insights_loaded=False,
                    conditions_evaluated=[],
                    triggered_conditions=[],
                    decision=decision_outcome,
                    reasoning=decision_reason,
                    campaign_triggered=False,
                    campaign_success=None,
                    cooldown_active=cooldown_active,
                    safety_checks_passed=False,
                    execution_time_ms=(datetime.now() - self.start_time).total_seconds() * 1000,
                )

                self.save_autonomy_report(decision, [])
                self.update_state(decision_outcome, decision_reason, False)

                self._audit_log(
                    action="autonomous_cycle_failed",
                    target="ai_lifecycle",
                    result=ResultStatus.FAILURE,
                    error="Analytics failed"
                )

                return ExitCode.ANALYTICS_FAILURE

            # Step 3: Load insights
            insights_loaded = self.load_insights()

            if not insights_loaded:
                self._log("Could not load insights - using limited evaluation", "WARN")

            # Step 4: Evaluate conditions
            conditions = self.evaluate_trigger_conditions()

            # Step 5: Make decision and potentially trigger
            campaign_triggered, decision_outcome, decision_reason = \
                self.trigger_campaign_if_needed(conditions)

            if campaign_triggered:
                campaign_success = True  # If we got here, it succeeded

            # Step 6: Update state
            self.update_state(decision_outcome, decision_reason, campaign_triggered)

            # Step 7: Generate report
            triggered_conditions = [c.name for c in conditions if c.triggered]

            decision = AutonomyDecision(
                timestamp=datetime.now().isoformat(),
                analytics_success=analytics_success,
                insights_loaded=insights_loaded,
                conditions_evaluated=conditions,
                triggered_conditions=triggered_conditions,
                decision=decision_outcome,
                reasoning=decision_reason,
                campaign_triggered=campaign_triggered,
                campaign_success=campaign_success,
                cooldown_active=cooldown_active,
                safety_checks_passed=not cooldown_active or self.force,
                execution_time_ms=(datetime.now() - self.start_time).total_seconds() * 1000,
            )

            report_path = self.save_autonomy_report(decision, conditions)

            # Final summary
            self._log("=" * 60)
            self._log("AUTONOMOUS CYCLE COMPLETE")
            self._log("=" * 60)
            self._log(f"Decision: {decision_outcome.value}")
            self._log(f"Reason: {decision_reason}")
            self._log(f"Campaign Triggered: {campaign_triggered}")
            self._log(f"Conditions Evaluated: {len(conditions)}")
            self._log(f"Conditions Triggered: {len(triggered_conditions)}")

            if report_path:
                self._log(f"Report: {report_path}")

            self._log("=" * 60)

            self._audit_log(
                action="autonomous_cycle_completed",
                target="ai_lifecycle",
                parameters={
                    "decision": decision_outcome.value,
                    "campaign_triggered": campaign_triggered,
                    "conditions_triggered": len(triggered_conditions),
                },
                result=ResultStatus.SUCCESS
            )

            # Determine exit code
            if decision_outcome == DecisionOutcome.FAILED:
                return ExitCode.CAMPAIGN_FAILURE

            return ExitCode.SUCCESS

        except Exception as e:
            self._log(f"Unexpected error: {e}", "ERROR")

            self._audit_log(
                action="autonomous_cycle_failed",
                target="ai_lifecycle",
                result=ResultStatus.FAILURE,
                error=str(e)
            )

            return ExitCode.SYSTEM_ERROR


# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Autonomous Controller - Self-Improving AI Lifecycle",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit Codes:
  0 - Successful run
  1 - Analytics failure
  2 - Campaign trigger failure
  3 - Unexpected system error

Examples:
  python3 scripts/autonomous_controller.py
  python3 scripts/autonomous_controller.py --verbose
  python3 scripts/autonomous_controller.py --dry-run
  python3 scripts/autonomous_controller.py --force
        """
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simulate execution without making changes'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='Force trigger, bypassing cooldown'
    )

    args = parser.parse_args()

    controller = AutonomousController(
        verbose=args.verbose,
        dry_run=args.dry_run,
        force=args.force
    )

    exit_code = controller.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
