#!/usr/bin/env python3
"""
Weekly CEO Briefing Generator
Gold Tier - Unified Business Intelligence with Email Delivery

Combines data from:
- Odoo Accounting (financial health, invoices, cash flow)
- Social Media Analytics (engagement, performance, campaigns)
- System Health (uptime, errors, processing stats)

Generates comprehensive weekly briefing for executive review.
Supports SMTP email delivery to CEO.

Usage:
    python3 scripts/weekly_ceo_briefing.py --verbose
    python3 scripts/weekly_ceo_briefing.py --send-email
    python3 scripts/weekly_ceo_briefing.py --output file --send-email

Environment Variables (for --send-email):
    SMTP_SERVER   - SMTP server hostname
    SMTP_PORT     - SMTP port (default: 587)
    SMTP_EMAIL    - Sender email address
    SMTP_PASSWORD - Sender email password
    CEO_EMAIL     - Recipient CEO email address
"""

import os
import json
import sys
import logging
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables from .env file
from utils.env_loader import load_env
load_env()

from mcp_servers.odoo_accounting.server import OdooMCPServer, OdooConfig, OdooConnectionMode

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ceo_briefing")


class CEOBriefingGenerator:
    """
    Generates comprehensive weekly CEO briefings.
    Integrates accounting, social media, and system health data.
    """

    def __init__(self, vault_path: Optional[Path] = None):
        self.vault_path = vault_path or Path(__file__).parent.parent / "AI_Employee_Vault"
        self.executive_path = self.vault_path / "Executive"
        self.analytics_path = self.vault_path / "Analytics"
        self.logs_path = self.vault_path / "Logs"

        # Ensure directories exist
        self.executive_path.mkdir(parents=True, exist_ok=True)

        # Initialize Odoo connector
        config = OdooConfig(mode=OdooConnectionMode.SIMULATE)
        self.odoo_server = OdooMCPServer(config)
        self.odoo_server.connector.connect()

    def gather_accounting_data(self) -> Dict[str, Any]:
        """Gather accounting data from Odoo"""
        logger.info("Gathering accounting data...")

        try:
            summary_result = self.odoo_server.call_tool("get_financial_summary", {})
            overdue_result = self.odoo_server.call_tool("get_overdue_invoices", {})
            cash_flow_result = self.odoo_server.call_tool("check_cash_flow", {"days_ahead": 30})

            return {
                "financial_summary": summary_result.get("result", {}),
                "overdue_invoices": overdue_result.get("result", []),
                "cash_flow_forecast": cash_flow_result.get("result", {}),
                "status": "success"
            }
        except Exception as e:
            logger.error(f"Error gathering accounting data: {e}")
            return {"status": "error", "error": str(e)}

    def gather_social_media_data(self) -> Dict[str, Any]:
        """Gather social media analytics data"""
        logger.info("Gathering social media data...")

        try:
            # Load strategy insights if available
            insights_file = self.analytics_path / "strategy_insights.json"
            if insights_file.exists():
                with open(insights_file, 'r') as f:
                    insights = json.load(f)
            else:
                insights = {}

            # Load social metrics
            metrics_file = self.analytics_path / "social_metrics.json"
            if metrics_file.exists():
                with open(metrics_file, 'r') as f:
                    metrics = json.load(f)
            else:
                metrics = {"posts": []}

            # Calculate summary stats
            posts = metrics.get("posts", [])
            total_posts = len(posts)
            total_engagement = sum(
                p.get("likes", 0) + p.get("comments", 0) + p.get("shares", 0)
                for p in posts
            )

            # Platform breakdown
            platform_stats = {}
            for p in posts:
                platform = p.get("platform", "unknown")
                if platform not in platform_stats:
                    platform_stats[platform] = {"posts": 0, "engagement": 0}
                platform_stats[platform]["posts"] += 1
                platform_stats[platform]["engagement"] += (
                    p.get("likes", 0) + p.get("comments", 0) + p.get("shares", 0)
                )

            return {
                "total_posts": total_posts,
                "total_engagement": total_engagement,
                "avg_engagement": total_engagement / total_posts if total_posts > 0 else 0,
                "platform_breakdown": platform_stats,
                "insights": insights,
                "status": "success"
            }
        except Exception as e:
            logger.error(f"Error gathering social media data: {e}")
            return {"status": "error", "error": str(e)}

    def gather_system_health_data(self) -> Dict[str, Any]:
        """Gather system health and operational data"""
        logger.info("Gathering system health data...")

        try:
            # Check runner log for recent activity
            runner_log = self.logs_path / "runner.log"
            recent_runs = 0
            errors = 0

            if runner_log.exists():
                with open(runner_log, 'r') as f:
                    lines = f.readlines()[-100:]  # Last 100 lines

                for line in lines:
                    if "Processing" in line or "SUCCESS" in line:
                        recent_runs += 1
                    if "ERROR" in line or "FAILED" in line:
                        errors += 1

            # Check watchdog status
            watchdog_status = self.vault_path / "Watchdog" / "system_status.json"
            if watchdog_status.exists():
                with open(watchdog_status, 'r') as f:
                    watchdog = json.load(f)
            else:
                watchdog = {"status": "unknown"}

            # Check autonomous state
            auto_state = self.vault_path / "System" / "autonomous_state.json"
            if auto_state.exists():
                with open(auto_state, 'r') as f:
                    autonomous = json.load(f)
            else:
                autonomous = {}

            return {
                "recent_runs": recent_runs,
                "errors_detected": errors,
                "error_rate": errors / recent_runs if recent_runs > 0 else 0,
                "watchdog_status": watchdog.get("status", "unknown"),
                "autonomous_triggers": autonomous.get("trigger_count_this_week", 0),
                "last_autonomous_decision": autonomous.get("last_decision", "none"),
                "status": "success"
            }
        except Exception as e:
            logger.error(f"Error gathering system health data: {e}")
            return {"status": "error", "error": str(e)}

    def generate_briefing(self) -> Dict[str, Any]:
        """Generate comprehensive CEO briefing"""
        logger.info("Generating CEO briefing...")

        # Gather all data
        accounting = self.gather_accounting_data()
        social = self.gather_social_media_data()
        system = self.gather_system_health_data()

        # Calculate overall health score (0-100)
        health_score = self._calculate_health_score(accounting, social, system)

        # Generate risk alerts
        risks = self._identify_risks(accounting, social, system)

        # Generate recommendations
        recommendations = self._generate_recommendations(accounting, social, system)

        briefing = {
            "report_type": "Weekly CEO Briefing",
            "generated_at": datetime.now().isoformat(),
            "period": {
                "start": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
                "end": datetime.now().strftime("%Y-%m-%d")
            },
            "overall_health_score": health_score,
            "executive_summary": self._generate_executive_summary(accounting, social, system, health_score),
            "financial_overview": accounting,
            "social_media_overview": social,
            "system_health": system,
            "risk_alerts": risks,
            "recommendations": recommendations
        }

        return briefing

    def _calculate_health_score(
        self,
        accounting: Dict[str, Any],
        social: Dict[str, Any],
        system: Dict[str, Any]
    ) -> int:
        """Calculate overall business health score (0-100)"""

        score = 100

        # Financial factors (-30 max)
        if accounting.get("status") == "success":
            fin = accounting.get("financial_summary", {})
            overdue = len(accounting.get("overdue_invoices", []))

            # Deduct for low cash
            if fin.get("cash_position", {}).get("total_liquid", 0) < 50000:
                score -= 15

            # Deduct for overdue invoices
            score -= min(overdue * 5, 15)

        # Social media factors (-20 max)
        if social.get("status") == "success":
            if social.get("avg_engagement", 0) < 10:
                score -= 10
            if social.get("total_posts", 0) < 5:
                score -= 10

        # System health factors (-20 max)
        if system.get("status") == "success":
            error_rate = system.get("error_rate", 0)
            if error_rate > 0.1:
                score -= 10
            if error_rate > 0.3:
                score -= 10

        return max(0, min(100, score))

    def _identify_risks(
        self,
        accounting: Dict[str, Any],
        social: Dict[str, Any],
        system: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Identify key risks requiring attention"""

        risks = []

        # Accounting risks
        if accounting.get("status") == "success":
            overdue = accounting.get("overdue_invoices", [])
            if overdue:
                total_overdue = sum(
                    inv["amount_total"] - inv["amount_paid"]
                    for inv in overdue
                )
                risks.append({
                    "category": "Financial",
                    "severity": "HIGH" if total_overdue > 10000 else "MEDIUM",
                    "title": "Overdue Receivables",
                    "description": f"${total_overdue:,.2f} overdue from {len(overdue)} invoices",
                    "action": "Initiate collection process"
                })

            fin = accounting.get("financial_summary", {})
            cash = fin.get("cash_position", {}).get("total_liquid", 0)
            if cash < 50000:
                risks.append({
                    "category": "Financial",
                    "severity": "HIGH",
                    "title": "Low Cash Reserves",
                    "description": f"Cash position at ${cash:,.2f}",
                    "action": "Review upcoming obligations and accelerate collections"
                })

        # System risks
        if system.get("status") == "success":
            if system.get("error_rate", 0) > 0.2:
                risks.append({
                    "category": "Operations",
                    "severity": "MEDIUM",
                    "title": "Elevated Error Rate",
                    "description": f"{system['error_rate']*100:.1f}% error rate in recent operations",
                    "action": "Review error logs and address root causes"
                })

        return risks

    def _generate_recommendations(
        self,
        accounting: Dict[str, Any],
        social: Dict[str, Any],
        system: Dict[str, Any]
    ) -> List[str]:
        """Generate actionable recommendations"""

        recommendations = []

        # Financial recommendations
        if accounting.get("status") == "success":
            fin = accounting.get("financial_summary", {})
            margin = fin.get("ytd_performance", {}).get("profit_margin", 0)

            if margin > 60:
                recommendations.append(
                    "Strong profit margin - consider reinvesting in growth initiatives"
                )
            elif margin < 40:
                recommendations.append(
                    "Review expense categories to improve profit margins"
                )

            cash = fin.get("cash_position", {}).get("total_liquid", 0)
            if cash > 200000:
                recommendations.append(
                    "Excess cash reserves - evaluate short-term investment options"
                )

        # Social media recommendations
        if social.get("status") == "success":
            insights = social.get("insights", {})
            if insights.get("improvement_recommendations"):
                for rec in insights["improvement_recommendations"][:2]:
                    recommendations.append(f"Social: {rec.get('recommendation', '')}")

            if social.get("total_posts", 0) < 10:
                recommendations.append(
                    "Increase social media posting frequency to improve visibility"
                )

        # System recommendations
        if system.get("status") == "success":
            if system.get("autonomous_triggers", 0) == 0:
                recommendations.append(
                    "Review autonomous controller settings to enable self-optimization"
                )

        if not recommendations:
            recommendations.append("All systems operating normally - maintain current practices")

        return recommendations

    def _generate_executive_summary(
        self,
        accounting: Dict[str, Any],
        social: Dict[str, Any],
        system: Dict[str, Any],
        health_score: int
    ) -> str:
        """Generate executive summary paragraph"""

        # Health status
        if health_score >= 80:
            health_status = "excellent"
        elif health_score >= 60:
            health_status = "good"
        elif health_score >= 40:
            health_status = "needs attention"
        else:
            health_status = "critical"

        # Financial highlight
        fin = accounting.get("financial_summary", {})
        cash = fin.get("cash_position", {}).get("total_liquid", 0)
        margin = fin.get("ytd_performance", {}).get("profit_margin", 0)

        # Social highlight
        engagement = social.get("total_engagement", 0)
        posts = social.get("total_posts", 0)

        summary = (
            f"Overall business health is {health_status} (score: {health_score}/100). "
            f"Financial position shows ${cash:,.0f} in liquid assets with {margin:.1f}% YTD profit margin. "
            f"Social media presence generated {engagement:,} total engagements across {posts} posts. "
            f"System operations are {'stable' if system.get('error_rate', 0) < 0.1 else 'experiencing some issues'}."
        )

        return summary

    def save_briefing(self, briefing: Dict[str, Any]) -> str:
        """Save briefing to vault"""

        date_str = datetime.now().strftime("%Y%m%d")

        # Save JSON
        json_path = self.executive_path / f"ceo_briefing_{date_str}.json"
        with open(json_path, 'w') as f:
            json.dump(briefing, f, indent=2)

        # Save Markdown
        md_path = self.executive_path / f"ceo_briefing_{date_str}.md"
        md_content = self._format_briefing_markdown(briefing)
        with open(md_path, 'w') as f:
            f.write(md_content)

        logger.info(f"CEO Briefing saved to {md_path}")
        return str(md_path)

    def _format_briefing_markdown(self, briefing: Dict[str, Any]) -> str:
        """Format briefing as markdown"""

        md = f"""# Weekly CEO Briefing

**Generated:** {briefing['generated_at']}
**Period:** {briefing['period']['start']} to {briefing['period']['end']}

---

## Overall Health Score: {briefing['overall_health_score']}/100

{self._health_score_indicator(briefing['overall_health_score'])}

---

## Executive Summary

{briefing['executive_summary']}

---

## Financial Overview

"""
        fin = briefing.get("financial_overview", {}).get("financial_summary", {})
        if fin:
            cash = fin.get("cash_position", {})
            ytd = fin.get("ytd_performance", {})

            md += f"""### Cash Position
| Account | Amount |
|---------|--------|
| Cash | ${cash.get('cash', 0):,.2f} |
| Bank | ${cash.get('bank', 0):,.2f} |
| **Total Liquid** | **${cash.get('total_liquid', 0):,.2f}** |

### Year-to-Date Performance
| Metric | Value |
|--------|-------|
| Revenue | ${ytd.get('revenue', 0):,.2f} |
| Expenses | ${ytd.get('expenses', 0):,.2f} |
| Net Income | ${ytd.get('net_income', 0):,.2f} |
| Profit Margin | {ytd.get('profit_margin', 0):.1f}% |

"""

        md += "---\n\n## Social Media Overview\n\n"
        social = briefing.get("social_media_overview", {})
        if social.get("status") == "success":
            md += f"""| Metric | Value |
|--------|-------|
| Total Posts | {social.get('total_posts', 0)} |
| Total Engagement | {social.get('total_engagement', 0):,} |
| Avg Engagement/Post | {social.get('avg_engagement', 0):.1f} |

"""
            if social.get("platform_breakdown"):
                md += "### Platform Breakdown\n\n"
                md += "| Platform | Posts | Engagement |\n"
                md += "|----------|-------|------------|\n"
                for platform, stats in social["platform_breakdown"].items():
                    md += f"| {platform.title()} | {stats['posts']} | {stats['engagement']:,} |\n"
                md += "\n"

        md += "---\n\n## System Health\n\n"
        system = briefing.get("system_health", {})
        if system.get("status") == "success":
            md += f"""| Metric | Value |
|--------|-------|
| Recent Operations | {system.get('recent_runs', 0)} |
| Errors Detected | {system.get('errors_detected', 0)} |
| Error Rate | {system.get('error_rate', 0)*100:.1f}% |
| Autonomous Triggers | {system.get('autonomous_triggers', 0)} |

"""

        md += "---\n\n## Risk Alerts\n\n"
        risks = briefing.get("risk_alerts", [])
        if risks:
            for risk in risks:
                severity_icon = "🔴" if risk["severity"] == "HIGH" else "🟡" if risk["severity"] == "MEDIUM" else "🟢"
                md += f"### {severity_icon} [{risk['severity']}] {risk['title']}\n"
                md += f"**Category:** {risk['category']}\n\n"
                md += f"{risk['description']}\n\n"
                md += f"**Recommended Action:** {risk['action']}\n\n"
        else:
            md += "No significant risks identified.\n\n"

        md += "---\n\n## Recommendations\n\n"
        for i, rec in enumerate(briefing.get("recommendations", []), 1):
            md += f"{i}. {rec}\n"

        md += "\n---\n\n*Generated by AI Employee System - Gold Tier CEO Briefing*\n"

        return md

    def _health_score_indicator(self, score: int) -> str:
        """Generate visual health score indicator"""
        if score >= 80:
            return "🟢 **EXCELLENT** - Business is performing optimally"
        elif score >= 60:
            return "🟡 **GOOD** - Minor issues to address"
        elif score >= 40:
            return "🟠 **ATTENTION NEEDED** - Several areas require focus"
        else:
            return "🔴 **CRITICAL** - Immediate action required"

    def send_email(
        self,
        briefing: Dict[str, Any],
        briefing_path: str
    ) -> Tuple[bool, str]:
        """
        Send CEO briefing via SMTP email.

        Args:
            briefing: The briefing data dictionary
            briefing_path: Path to the markdown briefing file

        Returns:
            Tuple of (success, message)

        Environment Variables Required:
            SMTP_SERVER   - SMTP server hostname
            SMTP_PORT     - SMTP port (default: 587)
            SMTP_EMAIL    - Sender email address
            SMTP_PASSWORD - Sender email password
            CEO_EMAIL     - Recipient CEO email address
        """
        logger.info("Preparing to send CEO briefing via email...")

        # Get environment variables
        smtp_server = os.environ.get('SMTP_SERVER')
        smtp_port = int(os.environ.get('SMTP_PORT', 587))
        smtp_email = os.environ.get('SMTP_EMAIL')
        smtp_password = os.environ.get('SMTP_PASSWORD')
        ceo_email = os.environ.get('CEO_EMAIL')

        # Validate credentials
        missing = []
        if not smtp_server:
            missing.append('SMTP_SERVER')
        if not smtp_email:
            missing.append('SMTP_EMAIL')
        if not smtp_password:
            missing.append('SMTP_PASSWORD')
        if not ceo_email:
            missing.append('CEO_EMAIL')

        if missing:
            error_msg = f"Missing environment variables: {', '.join(missing)}"
            logger.error(error_msg)
            self._log_email_event("credentials_missing", {"missing": missing})
            return False, error_msg

        try:
            # Create email message
            msg = MIMEMultipart('mixed')
            msg['Subject'] = f"Weekly AI Employee CEO Briefing - {datetime.now().strftime('%Y-%m-%d')}"
            msg['From'] = smtp_email
            msg['To'] = ceo_email

            # Create HTML body
            health_score = briefing.get('overall_health_score', 0)
            health_status = self._get_health_status_text(health_score)
            executive_summary = briefing.get('executive_summary', 'No summary available.')

            html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .header {{ background-color: #1a365d; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; }}
        .health-score {{ font-size: 48px; font-weight: bold; text-align: center; margin: 20px 0; }}
        .health-excellent {{ color: #22c55e; }}
        .health-good {{ color: #eab308; }}
        .health-attention {{ color: #f97316; }}
        .health-critical {{ color: #ef4444; }}
        .summary {{ background-color: #f3f4f6; padding: 15px; border-radius: 8px; margin: 20px 0; }}
        .risks {{ margin: 20px 0; }}
        .risk-high {{ border-left: 4px solid #ef4444; padding-left: 10px; margin: 10px 0; }}
        .risk-medium {{ border-left: 4px solid #eab308; padding-left: 10px; margin: 10px 0; }}
        .footer {{ background-color: #f3f4f6; padding: 15px; text-align: center; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Weekly CEO Briefing</h1>
        <p>{briefing['period']['start']} to {briefing['period']['end']}</p>
    </div>

    <div class="content">
        <div class="health-score {self._get_health_css_class(health_score)}">
            {health_score}/100
        </div>
        <p style="text-align: center; font-size: 18px;">{health_status}</p>

        <div class="summary">
            <h2>Executive Summary</h2>
            <p>{executive_summary}</p>
        </div>

        <div class="risks">
            <h2>Risk Alerts</h2>
"""
            risks = briefing.get('risk_alerts', [])
            if risks:
                for risk in risks:
                    risk_class = 'risk-high' if risk['severity'] == 'HIGH' else 'risk-medium'
                    html_body += f"""
            <div class="{risk_class}">
                <strong>[{risk['severity']}] {risk['title']}</strong><br>
                {risk['description']}<br>
                <em>Action: {risk['action']}</em>
            </div>
"""
            else:
                html_body += "<p>No significant risks identified.</p>"

            html_body += """
        </div>

        <h2>Recommendations</h2>
        <ol>
"""
            for rec in briefing.get('recommendations', []):
                html_body += f"            <li>{rec}</li>\n"

            html_body += """
        </ol>

        <p><strong>Full report attached as markdown file.</strong></p>
    </div>

    <div class="footer">
        <p>Generated by AI Employee System - Gold Tier</p>
        <p>This is an automated briefing. Please review the attached full report for details.</p>
    </div>
</body>
</html>
"""

            # Attach HTML body
            html_part = MIMEText(html_body, 'html')
            msg.attach(html_part)

            # Attach the markdown file
            if briefing_path and Path(briefing_path).exists():
                with open(briefing_path, 'rb') as f:
                    attachment = MIMEApplication(f.read(), _subtype='md')
                    attachment.add_header(
                        'Content-Disposition',
                        'attachment',
                        filename=Path(briefing_path).name
                    )
                    msg.attach(attachment)

            # Send email
            logger.info(f"Connecting to SMTP server: {smtp_server}:{smtp_port}")

            context = ssl.create_default_context()

            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls(context=context)
                server.login(smtp_email, smtp_password)
                server.send_message(msg)

            logger.info(f"Email sent successfully to {ceo_email}")
            self._log_email_event("email_sent", {
                "recipient": ceo_email,
                "health_score": health_score,
                "attachment": briefing_path
            })

            return True, f"Email sent successfully to {ceo_email}"

        except smtplib.SMTPAuthenticationError as e:
            error_msg = f"SMTP authentication failed: {str(e)}"
            logger.error(error_msg)
            self._log_email_event("auth_failed", {"error": str(e)})
            return False, error_msg

        except smtplib.SMTPException as e:
            error_msg = f"SMTP error: {str(e)}"
            logger.error(error_msg)
            self._log_email_event("smtp_error", {"error": str(e)})
            return False, error_msg

        except Exception as e:
            error_msg = f"Email sending failed: {str(e)}"
            logger.error(error_msg)
            self._log_email_event("email_error", {"error": str(e)})
            return False, error_msg

    def _get_health_status_text(self, score: int) -> str:
        """Get health status text without emoji"""
        if score >= 80:
            return "EXCELLENT - Business is performing optimally"
        elif score >= 60:
            return "GOOD - Minor issues to address"
        elif score >= 40:
            return "ATTENTION NEEDED - Several areas require focus"
        else:
            return "CRITICAL - Immediate action required"

    def _get_health_css_class(self, score: int) -> str:
        """Get CSS class for health score"""
        if score >= 80:
            return "health-excellent"
        elif score >= 60:
            return "health-good"
        elif score >= 40:
            return "health-attention"
        else:
            return "health-critical"

    def _log_email_event(self, event_type: str, details: Dict[str, Any]):
        """Log email event to file"""
        log_path = self.logs_path
        log_path.mkdir(parents=True, exist_ok=True)
        log_file = log_path / "ceo_briefing_email.log"

        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event_type,
            "details": details
        }

        with open(log_file, 'a') as f:
            f.write(json.dumps(entry) + "\n")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Weekly CEO Briefing Generator - Gold Tier",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables (for --send-email):
    SMTP_SERVER   - SMTP server hostname (e.g., smtp.gmail.com)
    SMTP_PORT     - SMTP port (default: 587)
    SMTP_EMAIL    - Sender email address
    SMTP_PASSWORD - Sender email password or app password
    CEO_EMAIL     - Recipient CEO email address

Examples:
    python3 scripts/weekly_ceo_briefing.py --verbose
    python3 scripts/weekly_ceo_briefing.py --send-email
    python3 scripts/weekly_ceo_briefing.py --output file --send-email
        """
    )
    parser.add_argument(
        "--output",
        choices=["console", "file", "both"],
        default="both",
        help="Output destination (default: both)"
    )
    parser.add_argument(
        "--send-email",
        action="store_true",
        help="Send briefing via email to CEO"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    print("\n" + "="*60)
    print("      WEEKLY CEO BRIEFING GENERATOR")
    print("      Gold Tier - AI Employee System")
    print("="*60 + "\n")

    generator = CEOBriefingGenerator()
    briefing = generator.generate_briefing()

    briefing_path = None
    if args.output in ["file", "both"] or args.send_email:
        briefing_path = generator.save_briefing(briefing)
        print(f"Briefing saved to: {briefing_path}")

    if args.output in ["console", "both"]:
        print("\n" + "-"*60)
        print("EXECUTIVE SUMMARY")
        print("-"*60)
        print(f"\nHealth Score: {briefing['overall_health_score']}/100")
        print(f"\n{briefing['executive_summary']}")

        print("\n" + "-"*60)
        print("RISK ALERTS")
        print("-"*60)
        for risk in briefing.get("risk_alerts", []):
            print(f"\n[{risk['severity']}] {risk['title']}")
            print(f"  {risk['description']}")

        print("\n" + "-"*60)
        print("RECOMMENDATIONS")
        print("-"*60)
        for i, rec in enumerate(briefing.get("recommendations", []), 1):
            print(f"  {i}. {rec}")

    # Send email if requested
    if args.send_email:
        print("\n" + "-"*60)
        print("SENDING EMAIL")
        print("-"*60)

        success, message = generator.send_email(briefing, briefing_path)

        if success:
            print(f"\n[SUCCESS] {message}")
        else:
            print(f"\n[FAILED] {message}")

    print("\n" + "="*60)
    print("      Briefing Generation Complete")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
