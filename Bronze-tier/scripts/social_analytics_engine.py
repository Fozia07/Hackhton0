#!/usr/bin/env python3
"""
Social Analytics & Intelligence Engine
=======================================

Gold Tier Autonomous Feedback & Analytics Engine

Completes the strategic loop: Plan → Execute → Measure → Learn → Adapt

This engine:
- Reads engagement metrics
- Evaluates performance across platforms
- Detects top-performing themes
- Identifies underperforming content
- Generates improvement recommendations
- Feeds strategic insights for next campaign
- Generates executive performance report

Usage:
    python3 scripts/social_analytics_engine.py
    python3 scripts/social_analytics_engine.py --verbose
    python3 scripts/social_analytics_engine.py --summary-only
    python3 scripts/social_analytics_engine.py --export-insights

Exit Codes:
    0 - Success
    1 - Missing metrics file
    2 - Analysis failure

Author: AI Employee System
Version: 1.0.0
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict
import statistics

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.audit_logger import get_audit_logger, ActionType, ResultStatus


# ==============================================================================
# EXIT CODES
# ==============================================================================

class ExitCode:
    SUCCESS = 0
    MISSING_METRICS = 1
    ANALYSIS_FAILURE = 2


# ==============================================================================
# CONFIGURATION
# ==============================================================================

class Config:
    BASE_DIR = Path(__file__).parent.parent
    VAULT_DIR = BASE_DIR / "AI_Employee_Vault"

    # Input paths
    METRICS_FILE = VAULT_DIR / "Analytics" / "social_metrics.json"

    # Output paths
    ANALYTICS_DIR = VAULT_DIR / "Analytics"
    EXECUTIVE_DIR = VAULT_DIR / "Executive"
    INSIGHTS_FILE = ANALYTICS_DIR / "strategy_insights.json"

    # Engagement score weights
    WEIGHT_LIKES = 1
    WEIGHT_COMMENTS = 2
    WEIGHT_SHARES = 3
    WEIGHT_CLICKS = 2

    # Thresholds
    TOP_PERFORMER_PERCENTILE = 75
    UNDERPERFORMER_PERCENTILE = 25
    ENGAGEMENT_DROP_ALERT_THRESHOLD = 0.20  # 20%

    # Actor
    ACTOR = "social_analytics_engine"


# ==============================================================================
# ENUMS
# ==============================================================================

class Platform(Enum):
    FACEBOOK = "facebook"
    LINKEDIN = "linkedin"
    TWITTER = "twitter"
    INSTAGRAM = "instagram"


class EngagementTrend(Enum):
    INCREASING = "increasing"
    STABLE = "stable"
    DECLINING = "declining"
    CRITICAL = "critical"


class PerformanceLevel(Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    AVERAGE = "average"
    BELOW_AVERAGE = "below_average"
    POOR = "poor"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class PostMetrics:
    """Metrics for a single post."""
    platform: str
    post_id: str
    date: str
    theme: str
    likes: int = 0
    comments: int = 0
    shares: int = 0
    clicks: int = 0
    impressions: int = 0
    reach: int = 0

    @property
    def engagement_score(self) -> float:
        """Calculate weighted engagement score."""
        return (
            (self.likes * Config.WEIGHT_LIKES) +
            (self.comments * Config.WEIGHT_COMMENTS) +
            (self.shares * Config.WEIGHT_SHARES) +
            (self.clicks * Config.WEIGHT_CLICKS)
        )

    @property
    def total_interactions(self) -> int:
        """Total raw interactions."""
        return self.likes + self.comments + self.shares + self.clicks

    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform": self.platform,
            "post_id": self.post_id,
            "date": self.date,
            "theme": self.theme,
            "likes": self.likes,
            "comments": self.comments,
            "shares": self.shares,
            "clicks": self.clicks,
            "engagement_score": self.engagement_score,
        }


@dataclass
class PlatformAnalysis:
    """Analysis results for a platform."""
    platform: str
    total_posts: int
    total_engagement: float
    avg_engagement: float
    avg_likes: float
    avg_comments: float
    avg_shares: float
    avg_clicks: float
    best_post: Optional[PostMetrics]
    worst_post: Optional[PostMetrics]
    performance_level: PerformanceLevel
    trend: EngagementTrend

    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform": self.platform,
            "total_posts": self.total_posts,
            "total_engagement": round(self.total_engagement, 2),
            "avg_engagement": round(self.avg_engagement, 2),
            "avg_likes": round(self.avg_likes, 2),
            "avg_comments": round(self.avg_comments, 2),
            "avg_shares": round(self.avg_shares, 2),
            "avg_clicks": round(self.avg_clicks, 2),
            "performance_level": self.performance_level.value,
            "trend": self.trend.value,
        }


@dataclass
class ThemeAnalysis:
    """Analysis results for a content theme."""
    theme: str
    total_posts: int
    total_engagement: float
    avg_engagement: float
    platforms_used: List[str]
    best_platform_for_theme: str
    performance_level: PerformanceLevel

    def to_dict(self) -> Dict[str, Any]:
        return {
            "theme": self.theme,
            "total_posts": self.total_posts,
            "total_engagement": round(self.total_engagement, 2),
            "avg_engagement": round(self.avg_engagement, 2),
            "platforms_used": self.platforms_used,
            "best_platform_for_theme": self.best_platform_for_theme,
            "performance_level": self.performance_level.value,
        }


@dataclass
class Recommendation:
    """Strategic recommendation."""
    category: str
    priority: str  # high, medium, low
    recommendation: str
    rationale: str
    expected_impact: str


@dataclass
class StrategyInsights:
    """Insights for campaign engine."""
    best_platform: str
    worst_platform: str
    best_theme: str
    worst_theme: str
    best_posting_times: Dict[str, str]
    engagement_trend: str
    recommendations: List[str]
    alerts: List[str]
    generated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PerformanceReport:
    """Complete performance report."""
    period_start: str
    period_end: str
    total_posts_analyzed: int
    total_engagement: float
    avg_engagement_per_post: float
    platform_analysis: List[PlatformAnalysis]
    theme_analysis: List[ThemeAnalysis]
    top_performers: List[PostMetrics]
    underperformers: List[PostMetrics]
    recommendations: List[Recommendation]
    alerts: List[str]
    overall_trend: EngagementTrend
    week_over_week_change: float


# ==============================================================================
# ANALYTICS ENGINE
# ==============================================================================

class SocialAnalyticsEngine:
    """Main analytics and intelligence engine."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.audit_logger = get_audit_logger()
        self.metrics: List[PostMetrics] = []
        self.platform_data: Dict[str, List[PostMetrics]] = defaultdict(list)
        self.theme_data: Dict[str, List[PostMetrics]] = defaultdict(list)

    def _log(self, message: str, level: str = "INFO"):
        """Print timestamped log message."""
        if self.verbose or level in ("ERROR", "WARN", "ALERT"):
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
    # DATA LOADING
    # ==========================================================================

    def load_metrics(self) -> bool:
        """Load metrics from JSON file."""
        self._log(f"Loading metrics from: {Config.METRICS_FILE}")

        if not Config.METRICS_FILE.exists():
            self._log("Metrics file not found!", "ERROR")
            return False

        try:
            with open(Config.METRICS_FILE, 'r') as f:
                data = json.load(f)

            posts = data.get("posts", [])

            if not posts:
                self._log("No posts found in metrics file", "WARN")
                return False

            for post_data in posts:
                metric = PostMetrics(
                    platform=post_data.get("platform", "unknown"),
                    post_id=post_data.get("post_id", ""),
                    date=post_data.get("date", ""),
                    theme=post_data.get("theme", "Unknown"),
                    likes=post_data.get("likes", 0),
                    comments=post_data.get("comments", 0),
                    shares=post_data.get("shares", 0),
                    clicks=post_data.get("clicks", 0),
                    impressions=post_data.get("impressions", 0),
                    reach=post_data.get("reach", 0),
                )
                self.metrics.append(metric)

                # Organize by platform
                self.platform_data[metric.platform].append(metric)

                # Organize by theme
                self.theme_data[metric.theme].append(metric)

            self._log(f"Loaded {len(self.metrics)} posts from metrics")
            return True

        except json.JSONDecodeError as e:
            self._log(f"Invalid JSON in metrics file: {e}", "ERROR")
            return False
        except Exception as e:
            self._log(f"Error loading metrics: {e}", "ERROR")
            return False

    # ==========================================================================
    # ENGAGEMENT CALCULATIONS
    # ==========================================================================

    def calculate_engagement_score(self, post: PostMetrics) -> float:
        """Calculate engagement score for a post."""
        return post.engagement_score

    def calculate_average_engagement(self, posts: List[PostMetrics]) -> float:
        """Calculate average engagement for a list of posts."""
        if not posts:
            return 0.0
        return sum(p.engagement_score for p in posts) / len(posts)

    def calculate_percentile(self, value: float, all_values: List[float]) -> float:
        """Calculate percentile rank of a value."""
        if not all_values:
            return 0.0
        below = sum(1 for v in all_values if v < value)
        return (below / len(all_values)) * 100

    # ==========================================================================
    # PLATFORM ANALYSIS
    # ==========================================================================

    def analyze_by_platform(self) -> List[PlatformAnalysis]:
        """Analyze performance by platform."""
        self._log("Analyzing performance by platform...")

        analyses = []
        all_avg_engagements = []

        # First pass: calculate averages
        for platform, posts in self.platform_data.items():
            if posts:
                avg = self.calculate_average_engagement(posts)
                all_avg_engagements.append(avg)

        # Second pass: create analysis
        for platform, posts in self.platform_data.items():
            if not posts:
                continue

            total_engagement = sum(p.engagement_score for p in posts)
            avg_engagement = total_engagement / len(posts)

            # Calculate averages for each metric
            avg_likes = sum(p.likes for p in posts) / len(posts)
            avg_comments = sum(p.comments for p in posts) / len(posts)
            avg_shares = sum(p.shares for p in posts) / len(posts)
            avg_clicks = sum(p.clicks for p in posts) / len(posts)

            # Find best and worst
            sorted_posts = sorted(posts, key=lambda p: p.engagement_score, reverse=True)
            best_post = sorted_posts[0] if sorted_posts else None
            worst_post = sorted_posts[-1] if sorted_posts else None

            # Determine performance level
            performance_level = self._determine_performance_level(
                avg_engagement, all_avg_engagements
            )

            # Determine trend
            trend = self._calculate_trend(posts)

            analysis = PlatformAnalysis(
                platform=platform,
                total_posts=len(posts),
                total_engagement=total_engagement,
                avg_engagement=avg_engagement,
                avg_likes=avg_likes,
                avg_comments=avg_comments,
                avg_shares=avg_shares,
                avg_clicks=avg_clicks,
                best_post=best_post,
                worst_post=worst_post,
                performance_level=performance_level,
                trend=trend,
            )

            analyses.append(analysis)
            self._log(f"  {platform}: avg={avg_engagement:.1f}, posts={len(posts)}, trend={trend.value}")

        return sorted(analyses, key=lambda a: a.avg_engagement, reverse=True)

    def _determine_performance_level(
        self,
        value: float,
        all_values: List[float]
    ) -> PerformanceLevel:
        """Determine performance level based on percentile."""
        if not all_values:
            return PerformanceLevel.AVERAGE

        percentile = self.calculate_percentile(value, all_values)

        if percentile >= 80:
            return PerformanceLevel.EXCELLENT
        elif percentile >= 60:
            return PerformanceLevel.GOOD
        elif percentile >= 40:
            return PerformanceLevel.AVERAGE
        elif percentile >= 20:
            return PerformanceLevel.BELOW_AVERAGE
        else:
            return PerformanceLevel.POOR

    def _calculate_trend(self, posts: List[PostMetrics]) -> EngagementTrend:
        """Calculate engagement trend from posts."""
        if len(posts) < 2:
            return EngagementTrend.STABLE

        # Sort by date
        try:
            sorted_posts = sorted(posts, key=lambda p: p.date)
        except Exception:
            return EngagementTrend.STABLE

        # Split into halves
        mid = len(sorted_posts) // 2
        first_half = sorted_posts[:mid]
        second_half = sorted_posts[mid:]

        if not first_half or not second_half:
            return EngagementTrend.STABLE

        first_avg = self.calculate_average_engagement(first_half)
        second_avg = self.calculate_average_engagement(second_half)

        if first_avg == 0:
            return EngagementTrend.STABLE

        change = (second_avg - first_avg) / first_avg

        if change > 0.1:
            return EngagementTrend.INCREASING
        elif change < -0.2:
            return EngagementTrend.CRITICAL
        elif change < -0.05:
            return EngagementTrend.DECLINING
        else:
            return EngagementTrend.STABLE

    # ==========================================================================
    # THEME ANALYSIS
    # ==========================================================================

    def analyze_by_theme(self) -> List[ThemeAnalysis]:
        """Analyze performance by content theme."""
        self._log("Analyzing performance by theme...")

        analyses = []
        all_avg_engagements = []

        # First pass
        for theme, posts in self.theme_data.items():
            if posts:
                avg = self.calculate_average_engagement(posts)
                all_avg_engagements.append(avg)

        # Second pass
        for theme, posts in self.theme_data.items():
            if not posts:
                continue

            total_engagement = sum(p.engagement_score for p in posts)
            avg_engagement = total_engagement / len(posts)

            # Get platforms used
            platforms_used = list(set(p.platform for p in posts))

            # Find best platform for this theme
            platform_scores = defaultdict(list)
            for p in posts:
                platform_scores[p.platform].append(p.engagement_score)

            best_platform = max(
                platform_scores.keys(),
                key=lambda pl: sum(platform_scores[pl]) / len(platform_scores[pl])
            ) if platform_scores else "unknown"

            performance_level = self._determine_performance_level(
                avg_engagement, all_avg_engagements
            )

            analysis = ThemeAnalysis(
                theme=theme,
                total_posts=len(posts),
                total_engagement=total_engagement,
                avg_engagement=avg_engagement,
                platforms_used=platforms_used,
                best_platform_for_theme=best_platform,
                performance_level=performance_level,
            )

            analyses.append(analysis)
            self._log(f"  {theme}: avg={avg_engagement:.1f}, best_platform={best_platform}")

        return sorted(analyses, key=lambda a: a.avg_engagement, reverse=True)

    # ==========================================================================
    # TOP/UNDER PERFORMERS
    # ==========================================================================

    def detect_top_performers(self, count: int = 3) -> List[PostMetrics]:
        """Detect top performing posts."""
        self._log("Detecting top performers...")

        sorted_posts = sorted(
            self.metrics,
            key=lambda p: p.engagement_score,
            reverse=True
        )

        top = sorted_posts[:count]

        for i, post in enumerate(top, 1):
            self._log(f"  #{i}: {post.post_id} ({post.platform}) - score={post.engagement_score:.1f}")

        return top

    def detect_underperformers(self, count: int = 3) -> List[PostMetrics]:
        """Detect underperforming posts."""
        self._log("Detecting underperformers...")

        sorted_posts = sorted(
            self.metrics,
            key=lambda p: p.engagement_score
        )

        bottom = sorted_posts[:count]

        for i, post in enumerate(bottom, 1):
            self._log(f"  #{i}: {post.post_id} ({post.platform}) - score={post.engagement_score:.1f}")

        return bottom

    # ==========================================================================
    # RECOMMENDATIONS
    # ==========================================================================

    def generate_recommendations(
        self,
        platform_analysis: List[PlatformAnalysis],
        theme_analysis: List[ThemeAnalysis],
        overall_trend: EngagementTrend
    ) -> List[Recommendation]:
        """Generate strategic recommendations."""
        self._log("Generating recommendations...")

        recommendations = []

        # Platform-based recommendations
        if platform_analysis:
            best_platform = platform_analysis[0]
            worst_platform = platform_analysis[-1] if len(platform_analysis) > 1 else None

            recommendations.append(Recommendation(
                category="Platform Strategy",
                priority="high",
                recommendation=f"Increase content volume on {best_platform.platform}",
                rationale=f"{best_platform.platform} has the highest average engagement ({best_platform.avg_engagement:.1f})",
                expected_impact="10-15% increase in overall engagement"
            ))

            if worst_platform and worst_platform.avg_engagement < best_platform.avg_engagement * 0.5:
                recommendations.append(Recommendation(
                    category="Platform Strategy",
                    priority="medium",
                    recommendation=f"Review and optimize {worst_platform.platform} content strategy",
                    rationale=f"{worst_platform.platform} engagement is significantly below average",
                    expected_impact="Potential 20% improvement on platform"
                ))

        # Theme-based recommendations
        if theme_analysis:
            best_theme = theme_analysis[0]
            worst_theme = theme_analysis[-1] if len(theme_analysis) > 1 else None

            recommendations.append(Recommendation(
                category="Content Strategy",
                priority="high",
                recommendation=f"Increase '{best_theme.theme}' themed content by 20%",
                rationale=f"'{best_theme.theme}' generates highest engagement ({best_theme.avg_engagement:.1f})",
                expected_impact="Expected 15% engagement boost"
            ))

            if worst_theme:
                recommendations.append(Recommendation(
                    category="Content Strategy",
                    priority="medium",
                    recommendation=f"Reduce or revamp '{worst_theme.theme}' content",
                    rationale=f"'{worst_theme.theme}' has lowest engagement ({worst_theme.avg_engagement:.1f})",
                    expected_impact="Resource reallocation to higher-performing content"
                ))

        # Trend-based recommendations
        if overall_trend == EngagementTrend.DECLINING:
            recommendations.append(Recommendation(
                category="Urgent Action",
                priority="high",
                recommendation="Audit recent content and adjust posting strategy",
                rationale="Overall engagement is declining",
                expected_impact="Stabilize engagement within 1-2 weeks"
            ))

        if overall_trend == EngagementTrend.CRITICAL:
            recommendations.append(Recommendation(
                category="Critical Alert",
                priority="high",
                recommendation="Immediate strategy review required - engagement dropped >20%",
                rationale="Critical engagement decline detected",
                expected_impact="Prevent further audience loss"
            ))

        # Engagement type recommendations
        if self.metrics:
            avg_shares = sum(p.shares for p in self.metrics) / len(self.metrics)
            avg_comments = sum(p.comments for p in self.metrics) / len(self.metrics)

            if avg_shares < avg_comments:
                recommendations.append(Recommendation(
                    category="Content Optimization",
                    priority="medium",
                    recommendation="Create more shareable content (infographics, quotes, statistics)",
                    rationale="Share rate is lower than comment rate",
                    expected_impact="Increase organic reach through shares"
                ))

            if avg_comments < 5:
                recommendations.append(Recommendation(
                    category="Engagement Tactics",
                    priority="medium",
                    recommendation="Add more questions and calls-to-action to drive comments",
                    rationale="Comment engagement is below optimal levels",
                    expected_impact="Boost algorithm visibility through increased comments"
                ))

        # Posting time recommendation
        recommendations.append(Recommendation(
            category="Timing Optimization",
            priority="low",
            recommendation="Test posting at different times based on platform analytics",
            rationale="Optimal posting times vary by audience and platform",
            expected_impact="5-10% engagement improvement"
        ))

        self._log(f"Generated {len(recommendations)} recommendations")
        return recommendations

    # ==========================================================================
    # ALERTS
    # ==========================================================================

    def check_for_alerts(
        self,
        platform_analysis: List[PlatformAnalysis],
        overall_trend: EngagementTrend,
        wow_change: float
    ) -> List[str]:
        """Check for critical alerts."""
        alerts = []

        # Week-over-week drop
        if wow_change < -Config.ENGAGEMENT_DROP_ALERT_THRESHOLD:
            alerts.append(
                f"ALERT: Engagement dropped {abs(wow_change)*100:.1f}% week-over-week. "
                f"Immediate review recommended."
            )

        # Critical trend
        if overall_trend == EngagementTrend.CRITICAL:
            alerts.append(
                "ALERT: Critical engagement decline detected. "
                "Campaign strategy adjustment required."
            )

        # Platform-specific alerts
        for analysis in platform_analysis:
            if analysis.trend == EngagementTrend.CRITICAL:
                alerts.append(
                    f"ALERT: {analysis.platform} engagement is critically low. "
                    f"Review platform-specific strategy."
                )

        # No engagement alert
        if self.metrics and all(p.engagement_score == 0 for p in self.metrics):
            alerts.append(
                "ALERT: Zero engagement detected across all posts. "
                "Verify tracking is working correctly."
            )

        return alerts

    # ==========================================================================
    # EXECUTIVE REPORT
    # ==========================================================================

    def generate_executive_report(
        self,
        platform_analysis: List[PlatformAnalysis],
        theme_analysis: List[ThemeAnalysis],
        top_performers: List[PostMetrics],
        underperformers: List[PostMetrics],
        recommendations: List[Recommendation],
        alerts: List[str],
        overall_trend: EngagementTrend,
        wow_change: float
    ) -> str:
        """Generate executive performance report."""
        self._log("Generating executive report...")

        Config.EXECUTIVE_DIR.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now().strftime("%Y%m%d")
        filename = f"weekly_performance_report_{date_str}.md"
        filepath = Config.EXECUTIVE_DIR / filename

        # Calculate totals
        total_engagement = sum(p.engagement_score for p in self.metrics)
        avg_engagement = total_engagement / len(self.metrics) if self.metrics else 0

        # Get date range
        dates = [p.date for p in self.metrics if p.date]
        period_start = min(dates) if dates else "N/A"
        period_end = max(dates) if dates else "N/A"

        lines = [
            "# Weekly Performance Report",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"**Analysis Period:** {period_start} to {period_end}",
            "",
        ]

        # Alerts section (if any)
        if alerts:
            lines.extend([
                "---",
                "",
                "## Alerts",
                "",
            ])
            for alert in alerts:
                lines.append(f"- {alert}")
            lines.append("")

        lines.extend([
            "---",
            "",
            "## Performance Summary",
            "",
            f"- **Total Posts Analyzed:** {len(self.metrics)}",
            f"- **Total Engagement Score:** {total_engagement:,.0f}",
            f"- **Average Engagement per Post:** {avg_engagement:.1f}",
            f"- **Overall Trend:** {overall_trend.value.upper()}",
            f"- **Week-over-Week Change:** {wow_change*100:+.1f}%",
            "",
            "---",
            "",
            "## Platform Comparison",
            "",
            "| Platform | Posts | Avg Engagement | Trend | Performance |",
            "|----------|-------|----------------|-------|-------------|",
        ])

        for pa in platform_analysis:
            lines.append(
                f"| {pa.platform.capitalize()} | {pa.total_posts} | "
                f"{pa.avg_engagement:.1f} | {pa.trend.value} | "
                f"{pa.performance_level.value.replace('_', ' ').title()} |"
            )

        lines.extend([
            "",
            "---",
            "",
            "## Theme Effectiveness",
            "",
            "| Theme | Posts | Avg Engagement | Best Platform | Performance |",
            "|-------|-------|----------------|---------------|-------------|",
        ])

        for ta in theme_analysis:
            lines.append(
                f"| {ta.theme} | {ta.total_posts} | {ta.avg_engagement:.1f} | "
                f"{ta.best_platform_for_theme} | {ta.performance_level.value.replace('_', ' ').title()} |"
            )

        lines.extend([
            "",
            "---",
            "",
            "## Top 3 Performing Posts",
            "",
        ])

        for i, post in enumerate(top_performers[:3], 1):
            lines.extend([
                f"### #{i}: {post.post_id}",
                f"- **Platform:** {post.platform}",
                f"- **Theme:** {post.theme}",
                f"- **Date:** {post.date}",
                f"- **Engagement Score:** {post.engagement_score:.0f}",
                f"- **Metrics:** {post.likes} likes, {post.comments} comments, "
                f"{post.shares} shares, {post.clicks} clicks",
                "",
            ])

        lines.extend([
            "---",
            "",
            "## Bottom 3 Performing Posts",
            "",
        ])

        for i, post in enumerate(underperformers[:3], 1):
            lines.extend([
                f"### #{i}: {post.post_id}",
                f"- **Platform:** {post.platform}",
                f"- **Theme:** {post.theme}",
                f"- **Date:** {post.date}",
                f"- **Engagement Score:** {post.engagement_score:.0f}",
                "",
            ])

        lines.extend([
            "---",
            "",
            "## Strategic Recommendations",
            "",
        ])

        # Group by priority
        high_priority = [r for r in recommendations if r.priority == "high"]
        medium_priority = [r for r in recommendations if r.priority == "medium"]
        low_priority = [r for r in recommendations if r.priority == "low"]

        if high_priority:
            lines.append("### High Priority")
            lines.append("")
            for r in high_priority:
                lines.extend([
                    f"**{r.category}:** {r.recommendation}",
                    f"- *Rationale:* {r.rationale}",
                    f"- *Expected Impact:* {r.expected_impact}",
                    "",
                ])

        if medium_priority:
            lines.append("### Medium Priority")
            lines.append("")
            for r in medium_priority:
                lines.extend([
                    f"**{r.category}:** {r.recommendation}",
                    f"- *Rationale:* {r.rationale}",
                    "",
                ])

        if low_priority:
            lines.append("### Low Priority")
            lines.append("")
            for r in low_priority:
                lines.append(f"- {r.recommendation}")
            lines.append("")

        lines.extend([
            "---",
            "",
            "## Risk Assessment",
            "",
        ])

        if overall_trend in (EngagementTrend.DECLINING, EngagementTrend.CRITICAL):
            lines.append("- **Engagement Risk:** HIGH - Declining trend requires immediate attention")
        elif overall_trend == EngagementTrend.STABLE:
            lines.append("- **Engagement Risk:** LOW - Stable performance")
        else:
            lines.append("- **Engagement Risk:** LOW - Positive growth trend")

        if wow_change < -0.1:
            lines.append(f"- **Volatility Risk:** MEDIUM - {abs(wow_change)*100:.0f}% week-over-week change")
        else:
            lines.append("- **Volatility Risk:** LOW - Consistent performance")

        lines.extend([
            "",
            "---",
            "",
            "## Next Steps",
            "",
            "1. Review high-priority recommendations",
            "2. Adjust campaign strategy based on insights",
            "3. Monitor performance metrics daily",
            "4. Schedule follow-up analysis in 7 days",
            "",
            "---",
            "",
            "*Generated by Social Analytics Engine - Gold Tier*",
        ])

        content = "\n".join(lines)

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            self._log(f"Executive report saved: {filename}")
            return str(filepath)
        except Exception as e:
            self._log(f"Error saving report: {e}", "ERROR")
            return ""

    # ==========================================================================
    # INSIGHTS EXPORT
    # ==========================================================================

    def export_insights_for_campaign_engine(
        self,
        platform_analysis: List[PlatformAnalysis],
        theme_analysis: List[ThemeAnalysis],
        recommendations: List[Recommendation],
        alerts: List[str],
        overall_trend: EngagementTrend
    ) -> bool:
        """Export insights for campaign engine consumption."""
        self._log("Exporting insights for campaign engine...")

        Config.ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)

        # Determine best/worst
        best_platform = platform_analysis[0].platform if platform_analysis else "unknown"
        worst_platform = platform_analysis[-1].platform if len(platform_analysis) > 1 else "unknown"
        best_theme = theme_analysis[0].theme if theme_analysis else "Unknown"
        worst_theme = theme_analysis[-1].theme if len(theme_analysis) > 1 else "Unknown"

        # Best posting times (simplified)
        best_times = {
            "facebook": "09:00",
            "linkedin": "08:00",
            "twitter": "12:00",
            "instagram": "19:00",
        }

        # Top recommendations as strings
        rec_strings = [r.recommendation for r in recommendations[:5]]

        insights = StrategyInsights(
            best_platform=best_platform,
            worst_platform=worst_platform,
            best_theme=best_theme,
            worst_theme=worst_theme,
            best_posting_times=best_times,
            engagement_trend=overall_trend.value,
            recommendations=rec_strings,
            alerts=alerts,
            generated_at=datetime.now().isoformat(),
        )

        try:
            with open(Config.INSIGHTS_FILE, 'w') as f:
                json.dump(insights.to_dict(), f, indent=2)
            self._log(f"Insights exported: {Config.INSIGHTS_FILE}")
            return True
        except Exception as e:
            self._log(f"Error exporting insights: {e}", "ERROR")
            return False

    # ==========================================================================
    # WEEK OVER WEEK CALCULATION
    # ==========================================================================

    def calculate_week_over_week_change(self) -> float:
        """Calculate week-over-week engagement change."""
        if len(self.metrics) < 2:
            return 0.0

        try:
            # Sort by date
            sorted_posts = sorted(self.metrics, key=lambda p: p.date)

            # Split into two halves (simulating weeks)
            mid = len(sorted_posts) // 2
            first_half = sorted_posts[:mid]
            second_half = sorted_posts[mid:]

            if not first_half or not second_half:
                return 0.0

            first_avg = self.calculate_average_engagement(first_half)
            second_avg = self.calculate_average_engagement(second_half)

            if first_avg == 0:
                return 0.0

            return (second_avg - first_avg) / first_avg

        except Exception:
            return 0.0

    # ==========================================================================
    # OVERALL TREND
    # ==========================================================================

    def calculate_overall_trend(self, wow_change: float) -> EngagementTrend:
        """Calculate overall engagement trend."""
        if wow_change > 0.1:
            return EngagementTrend.INCREASING
        elif wow_change < -0.2:
            return EngagementTrend.CRITICAL
        elif wow_change < -0.05:
            return EngagementTrend.DECLINING
        else:
            return EngagementTrend.STABLE

    # ==========================================================================
    # MAIN RUN
    # ==========================================================================

    def run(self, summary_only: bool = False, export_insights: bool = True) -> int:
        """Execute the analytics workflow."""
        self._log("=" * 60)
        self._log("Social Analytics Engine - Gold Tier")
        self._log("=" * 60)

        self._audit_log(
            action="analytics_started",
            target="social_metrics",
            result=ResultStatus.PENDING
        )

        # Load metrics
        if not self.load_metrics():
            self._audit_log(
                action="analytics_failed",
                target="social_metrics",
                result=ResultStatus.FAILURE,
                error="Missing metrics file"
            )
            return ExitCode.MISSING_METRICS

        try:
            # Analyze by platform
            platform_analysis = self.analyze_by_platform()

            # Analyze by theme
            theme_analysis = self.analyze_by_theme()

            # Calculate trends
            wow_change = self.calculate_week_over_week_change()
            overall_trend = self.calculate_overall_trend(wow_change)

            self._log(f"Overall trend: {overall_trend.value}")
            self._log(f"Week-over-week change: {wow_change*100:+.1f}%")

            # Detect performers
            top_performers = self.detect_top_performers()
            underperformers = self.detect_underperformers()

            # Generate recommendations
            recommendations = self.generate_recommendations(
                platform_analysis, theme_analysis, overall_trend
            )

            # Check for alerts
            alerts = self.check_for_alerts(platform_analysis, overall_trend, wow_change)

            if alerts:
                self._log("=" * 60, "ALERT")
                for alert in alerts:
                    self._log(alert, "ALERT")
                self._log("=" * 60, "ALERT")

            if not summary_only:
                # Generate executive report
                report_path = self.generate_executive_report(
                    platform_analysis,
                    theme_analysis,
                    top_performers,
                    underperformers,
                    recommendations,
                    alerts,
                    overall_trend,
                    wow_change
                )

            # Export insights
            if export_insights:
                self.export_insights_for_campaign_engine(
                    platform_analysis,
                    theme_analysis,
                    recommendations,
                    alerts,
                    overall_trend
                )

            # Success summary
            self._log("=" * 60)
            self._log("ANALYSIS COMPLETE")
            self._log("=" * 60)
            self._log(f"Posts analyzed: {len(self.metrics)}")
            self._log(f"Platforms: {len(platform_analysis)}")
            self._log(f"Themes: {len(theme_analysis)}")
            self._log(f"Recommendations: {len(recommendations)}")
            self._log(f"Alerts: {len(alerts)}")
            self._log(f"Overall trend: {overall_trend.value}")

            if not summary_only:
                self._log(f"Report: {report_path}")

            self._log("=" * 60)

            self._audit_log(
                action="analytics_completed",
                target="social_metrics",
                parameters={
                    "posts_analyzed": len(self.metrics),
                    "overall_trend": overall_trend.value,
                    "alerts_count": len(alerts),
                },
                result=ResultStatus.SUCCESS
            )

            return ExitCode.SUCCESS

        except Exception as e:
            self._log(f"Analysis failed: {e}", "ERROR")
            self._audit_log(
                action="analytics_failed",
                target="social_metrics",
                result=ResultStatus.FAILURE,
                error=str(e)
            )
            return ExitCode.ANALYSIS_FAILURE


# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Social Analytics Engine - Performance Analysis & Intelligence",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit Codes:
  0 - Success
  1 - Missing metrics file
  2 - Analysis failure

Examples:
  python3 scripts/social_analytics_engine.py
  python3 scripts/social_analytics_engine.py --verbose
  python3 scripts/social_analytics_engine.py --summary-only
  python3 scripts/social_analytics_engine.py --export-insights
        """
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )

    parser.add_argument(
        '--summary-only',
        action='store_true',
        help='Only show summary, skip report generation'
    )

    parser.add_argument(
        '--export-insights',
        action='store_true',
        default=True,
        help='Export insights for campaign engine (default: True)'
    )

    args = parser.parse_args()

    engine = SocialAnalyticsEngine(verbose=args.verbose)
    exit_code = engine.run(
        summary_only=args.summary_only,
        export_insights=args.export_insights
    )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
