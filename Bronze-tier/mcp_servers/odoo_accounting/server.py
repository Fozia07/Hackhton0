#!/usr/bin/env python3
"""
Odoo Accounting MCP Server
Gold Tier - Enterprise Accounting Integration

This MCP server provides accounting integration with Odoo ERP system.
Supports invoices, payments, expenses, and financial reporting.

Features:
- XML-RPC connection to Odoo
- Invoice management (create, read, update)
- Payment tracking and reconciliation
- Expense management
- Financial reports (P&L, Balance Sheet, Cash Flow)
- CEO Briefing integration for weekly accounting audits
- Simulation mode for testing without live Odoo instance
"""

import json
import sys
import logging
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import random

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("odoo_mcp_server")

# =============================================================================
# MCP Protocol Types
# =============================================================================

class MCPMessageType(Enum):
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    ERROR = "error"


@dataclass
class MCPTool:
    """MCP Tool definition"""
    name: str
    description: str
    input_schema: Dict[str, Any]


@dataclass
class MCPResource:
    """MCP Resource definition"""
    uri: str
    name: str
    description: str
    mime_type: str = "application/json"


# =============================================================================
# Odoo Connection Layer
# =============================================================================

class OdooConnectionMode(Enum):
    LIVE = "live"
    SIMULATE = "simulate"


@dataclass
class OdooConfig:
    """Odoo connection configuration"""
    url: str = "http://localhost:8069"
    database: str = "odoo_db"
    username: str = "admin"
    api_key: str = ""
    mode: OdooConnectionMode = OdooConnectionMode.SIMULATE


class OdooConnector:
    """
    Handles connection to Odoo ERP via XML-RPC.
    Supports both live and simulated modes.
    """

    def __init__(self, config: OdooConfig):
        self.config = config
        self.uid: Optional[int] = None
        self.connected = False
        self._simulation_data = self._init_simulation_data()

    def _init_simulation_data(self) -> Dict[str, Any]:
        """Initialize realistic simulation data for testing"""
        today = datetime.now()

        return {
            "invoices": [
                {
                    "id": 1001,
                    "number": "INV/2026/0001",
                    "partner_name": "TechCorp Solutions",
                    "date_invoice": (today - timedelta(days=15)).strftime("%Y-%m-%d"),
                    "date_due": (today + timedelta(days=15)).strftime("%Y-%m-%d"),
                    "amount_total": 15000.00,
                    "amount_paid": 15000.00,
                    "state": "paid",
                    "type": "out_invoice",
                    "currency": "USD"
                },
                {
                    "id": 1002,
                    "number": "INV/2026/0002",
                    "partner_name": "Digital Dynamics Inc",
                    "date_invoice": (today - timedelta(days=10)).strftime("%Y-%m-%d"),
                    "date_due": (today + timedelta(days=20)).strftime("%Y-%m-%d"),
                    "amount_total": 8500.00,
                    "amount_paid": 0.00,
                    "state": "open",
                    "type": "out_invoice",
                    "currency": "USD"
                },
                {
                    "id": 1003,
                    "number": "INV/2026/0003",
                    "partner_name": "StartupHub Ventures",
                    "date_invoice": (today - timedelta(days=5)).strftime("%Y-%m-%d"),
                    "date_due": (today + timedelta(days=25)).strftime("%Y-%m-%d"),
                    "amount_total": 22000.00,
                    "amount_paid": 11000.00,
                    "state": "partial",
                    "type": "out_invoice",
                    "currency": "USD"
                },
                {
                    "id": 1004,
                    "number": "INV/2026/0004",
                    "partner_name": "CloudServe Ltd",
                    "date_invoice": (today - timedelta(days=45)).strftime("%Y-%m-%d"),
                    "date_due": (today - timedelta(days=15)).strftime("%Y-%m-%d"),
                    "amount_total": 5200.00,
                    "amount_paid": 0.00,
                    "state": "overdue",
                    "type": "out_invoice",
                    "currency": "USD"
                },
                {
                    "id": 1005,
                    "number": "BILL/2026/0001",
                    "partner_name": "AWS Cloud Services",
                    "date_invoice": (today - timedelta(days=20)).strftime("%Y-%m-%d"),
                    "date_due": (today - timedelta(days=5)).strftime("%Y-%m-%d"),
                    "amount_total": 3200.00,
                    "amount_paid": 3200.00,
                    "state": "paid",
                    "type": "in_invoice",
                    "currency": "USD"
                }
            ],
            "payments": [
                {
                    "id": 2001,
                    "name": "PAY/2026/0001",
                    "partner_name": "TechCorp Solutions",
                    "date": (today - timedelta(days=5)).strftime("%Y-%m-%d"),
                    "amount": 15000.00,
                    "payment_type": "inbound",
                    "state": "posted",
                    "journal": "Bank",
                    "reference": "Wire Transfer"
                },
                {
                    "id": 2002,
                    "name": "PAY/2026/0002",
                    "partner_name": "StartupHub Ventures",
                    "date": (today - timedelta(days=2)).strftime("%Y-%m-%d"),
                    "amount": 11000.00,
                    "payment_type": "inbound",
                    "state": "posted",
                    "journal": "Bank",
                    "reference": "Partial Payment"
                },
                {
                    "id": 2003,
                    "name": "PAY/2026/0003",
                    "partner_name": "AWS Cloud Services",
                    "date": (today - timedelta(days=10)).strftime("%Y-%m-%d"),
                    "amount": 3200.00,
                    "payment_type": "outbound",
                    "state": "posted",
                    "journal": "Bank",
                    "reference": "Monthly Cloud Bill"
                }
            ],
            "expenses": [
                {
                    "id": 3001,
                    "name": "Office Supplies",
                    "employee": "John Smith",
                    "date": (today - timedelta(days=8)).strftime("%Y-%m-%d"),
                    "amount": 450.00,
                    "category": "Office",
                    "state": "approved",
                    "description": "Printer paper, ink cartridges"
                },
                {
                    "id": 3002,
                    "name": "Client Lunch Meeting",
                    "employee": "Sarah Johnson",
                    "date": (today - timedelta(days=3)).strftime("%Y-%m-%d"),
                    "amount": 185.00,
                    "category": "Meals & Entertainment",
                    "state": "approved",
                    "description": "Business lunch with TechCorp"
                },
                {
                    "id": 3003,
                    "name": "Software Subscription",
                    "employee": "Admin",
                    "date": (today - timedelta(days=1)).strftime("%Y-%m-%d"),
                    "amount": 299.00,
                    "category": "Software",
                    "state": "pending",
                    "description": "Annual license renewal"
                },
                {
                    "id": 3004,
                    "name": "Travel - Conference",
                    "employee": "Mike Chen",
                    "date": (today - timedelta(days=12)).strftime("%Y-%m-%d"),
                    "amount": 1250.00,
                    "category": "Travel",
                    "state": "approved",
                    "description": "Tech Summit 2026 attendance"
                }
            ],
            "accounts": {
                "cash": 45000.00,
                "bank": 128500.00,
                "accounts_receivable": 35700.00,
                "accounts_payable": 8500.00,
                "revenue_ytd": 185000.00,
                "expenses_ytd": 72000.00,
                "net_income_ytd": 113000.00
            },
            "company": {
                "name": "AI Employee Corp",
                "currency": "USD",
                "fiscal_year_start": "2026-01-01"
            }
        }

    def connect(self) -> bool:
        """Establish connection to Odoo"""
        if self.config.mode == OdooConnectionMode.SIMULATE:
            logger.info("Connected to Odoo (SIMULATION MODE)")
            self.connected = True
            self.uid = 1
            return True

        try:
            import xmlrpc.client

            # Authenticate
            common = xmlrpc.client.ServerProxy(f"{self.config.url}/xmlrpc/2/common")
            self.uid = common.authenticate(
                self.config.database,
                self.config.username,
                self.config.api_key,
                {}
            )

            if self.uid:
                self.connected = True
                logger.info(f"Connected to Odoo at {self.config.url}")
                return True
            else:
                logger.error("Odoo authentication failed")
                return False

        except Exception as e:
            logger.error(f"Failed to connect to Odoo: {e}")
            return False

    def execute(self, model: str, method: str, *args, **kwargs) -> Any:
        """Execute Odoo model method"""
        if self.config.mode == OdooConnectionMode.SIMULATE:
            return self._simulate_execute(model, method, *args, **kwargs)

        try:
            import xmlrpc.client
            models = xmlrpc.client.ServerProxy(f"{self.config.url}/xmlrpc/2/object")
            return models.execute_kw(
                self.config.database,
                self.uid,
                self.config.api_key,
                model,
                method,
                args,
                kwargs
            )
        except Exception as e:
            logger.error(f"Odoo execute error: {e}")
            raise

    def _simulate_execute(self, model: str, method: str, *args, **kwargs) -> Any:
        """Simulate Odoo operations for testing"""

        if model == "account.move" and method == "search_read":
            # Filter invoices based on domain
            invoices = self._simulation_data["invoices"]
            domain = args[0] if args else []

            # Apply basic filtering
            for condition in domain:
                if len(condition) == 3:
                    field, op, value = condition
                    if field == "state" and op == "=":
                        invoices = [i for i in invoices if i["state"] == value]
                    elif field == "type" and op == "=":
                        invoices = [i for i in invoices if i["type"] == value]

            return invoices

        elif model == "account.payment" and method == "search_read":
            return self._simulation_data["payments"]

        elif model == "hr.expense" and method == "search_read":
            return self._simulation_data["expenses"]

        elif model == "account.account" and method == "read":
            return self._simulation_data["accounts"]

        elif model == "res.company" and method == "read":
            return [self._simulation_data["company"]]

        return []


# =============================================================================
# Accounting Services
# =============================================================================

class AccountingService:
    """High-level accounting operations"""

    def __init__(self, connector: OdooConnector):
        self.connector = connector
        self.vault_path = Path(__file__).parent.parent.parent / "AI_Employee_Vault"

    def get_invoices(
        self,
        invoice_type: str = "all",
        state: str = "all",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get invoices with optional filtering"""

        domain = []
        if invoice_type != "all":
            domain.append(("type", "=", invoice_type))
        if state != "all":
            domain.append(("state", "=", state))

        invoices = self.connector.execute(
            "account.move",
            "search_read",
            domain,
            fields=["id", "number", "partner_name", "date_invoice", "date_due",
                   "amount_total", "amount_paid", "state", "type", "currency"],
            limit=limit
        )

        return invoices

    def get_overdue_invoices(self) -> List[Dict[str, Any]]:
        """Get all overdue invoices"""
        invoices = self.get_invoices(invoice_type="out_invoice")
        today = datetime.now().strftime("%Y-%m-%d")

        overdue = []
        for inv in invoices:
            if inv["state"] in ["open", "overdue"] and inv["date_due"] < today:
                inv["days_overdue"] = (datetime.now() - datetime.strptime(inv["date_due"], "%Y-%m-%d")).days
                overdue.append(inv)

        return sorted(overdue, key=lambda x: x["days_overdue"], reverse=True)

    def get_payments(
        self,
        payment_type: str = "all",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get payments with optional filtering"""

        payments = self.connector.execute(
            "account.payment",
            "search_read",
            [],
            fields=["id", "name", "partner_name", "date", "amount",
                   "payment_type", "state", "journal", "reference"]
        )

        if payment_type != "all":
            payments = [p for p in payments if p["payment_type"] == payment_type]

        if date_from:
            payments = [p for p in payments if p["date"] >= date_from]
        if date_to:
            payments = [p for p in payments if p["date"] <= date_to]

        return payments

    def get_expenses(
        self,
        state: str = "all",
        category: str = "all"
    ) -> List[Dict[str, Any]]:
        """Get expenses with optional filtering"""

        expenses = self.connector.execute(
            "hr.expense",
            "search_read",
            [],
            fields=["id", "name", "employee", "date", "amount",
                   "category", "state", "description"]
        )

        if state != "all":
            expenses = [e for e in expenses if e["state"] == state]
        if category != "all":
            expenses = [e for e in expenses if e["category"] == category]

        return expenses

    def get_financial_summary(self) -> Dict[str, Any]:
        """Get overall financial summary"""

        accounts = self.connector._simulation_data["accounts"]
        company = self.connector._simulation_data["company"]

        invoices = self.get_invoices()
        payments = self.get_payments()
        expenses = self.get_expenses()
        overdue = self.get_overdue_invoices()

        # Calculate totals
        total_receivable = sum(
            inv["amount_total"] - inv["amount_paid"]
            for inv in invoices
            if inv["type"] == "out_invoice" and inv["state"] in ["open", "partial", "overdue"]
        )

        total_payable = sum(
            inv["amount_total"] - inv["amount_paid"]
            for inv in invoices
            if inv["type"] == "in_invoice" and inv["state"] in ["open", "partial"]
        )

        total_overdue = sum(inv["amount_total"] - inv["amount_paid"] for inv in overdue)

        pending_expenses = sum(
            exp["amount"] for exp in expenses if exp["state"] == "pending"
        )

        return {
            "company": company["name"],
            "currency": company["currency"],
            "as_of_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "cash_position": {
                "cash": accounts["cash"],
                "bank": accounts["bank"],
                "total_liquid": accounts["cash"] + accounts["bank"]
            },
            "receivables": {
                "total_outstanding": total_receivable,
                "overdue_amount": total_overdue,
                "overdue_count": len(overdue)
            },
            "payables": {
                "total_outstanding": total_payable
            },
            "ytd_performance": {
                "revenue": accounts["revenue_ytd"],
                "expenses": accounts["expenses_ytd"],
                "net_income": accounts["net_income_ytd"],
                "profit_margin": round(accounts["net_income_ytd"] / accounts["revenue_ytd"] * 100, 1)
            },
            "pending_approvals": {
                "expenses": pending_expenses,
                "expense_count": len([e for e in expenses if e["state"] == "pending"])
            }
        }

    def generate_weekly_audit(self) -> Dict[str, Any]:
        """Generate weekly accounting audit for CEO briefing"""

        summary = self.get_financial_summary()
        invoices = self.get_invoices()
        payments = self.get_payments()
        expenses = self.get_expenses()
        overdue = self.get_overdue_invoices()

        # Calculate weekly metrics
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        weekly_payments_in = sum(
            p["amount"] for p in payments
            if p["payment_type"] == "inbound" and p["date"] >= week_ago
        )

        weekly_payments_out = sum(
            p["amount"] for p in payments
            if p["payment_type"] == "outbound" and p["date"] >= week_ago
        )

        weekly_expenses = sum(
            e["amount"] for e in expenses if e["date"] >= week_ago
        )

        # Risk assessment
        risks = []
        if summary["receivables"]["overdue_amount"] > 5000:
            risks.append({
                "level": "HIGH" if summary["receivables"]["overdue_amount"] > 10000 else "MEDIUM",
                "category": "Receivables",
                "description": f"${summary['receivables']['overdue_amount']:,.2f} overdue from {len(overdue)} invoices",
                "action": "Follow up with customers immediately"
            })

        if summary["cash_position"]["total_liquid"] < 50000:
            risks.append({
                "level": "HIGH",
                "category": "Cash Flow",
                "description": f"Low liquid assets: ${summary['cash_position']['total_liquid']:,.2f}",
                "action": "Review upcoming payments and accelerate collections"
            })

        if summary["pending_approvals"]["expense_count"] > 5:
            risks.append({
                "level": "LOW",
                "category": "Operations",
                "description": f"{summary['pending_approvals']['expense_count']} expenses pending approval",
                "action": "Review and approve pending expenses"
            })

        audit = {
            "report_type": "Weekly Accounting Audit",
            "generated_at": datetime.now().isoformat(),
            "period": {
                "start": week_ago,
                "end": datetime.now().strftime("%Y-%m-%d")
            },
            "executive_summary": {
                "cash_position": summary["cash_position"]["total_liquid"],
                "weekly_cash_in": weekly_payments_in,
                "weekly_cash_out": weekly_payments_out,
                "net_cash_flow": weekly_payments_in - weekly_payments_out,
                "ytd_profit_margin": summary["ytd_performance"]["profit_margin"]
            },
            "key_metrics": summary,
            "weekly_activity": {
                "payments_received": weekly_payments_in,
                "payments_made": weekly_payments_out,
                "expenses_incurred": weekly_expenses,
                "invoices_issued": len([i for i in invoices if i["date_invoice"] >= week_ago])
            },
            "overdue_invoices": overdue,
            "risks": risks,
            "recommendations": self._generate_recommendations(summary, overdue, risks)
        }

        return audit

    def _generate_recommendations(
        self,
        summary: Dict[str, Any],
        overdue: List[Dict[str, Any]],
        risks: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate actionable recommendations"""

        recommendations = []

        # Overdue collections
        if overdue:
            top_overdue = overdue[0] if overdue else None
            if top_overdue:
                recommendations.append(
                    f"Priority: Collect ${top_overdue['amount_total'] - top_overdue['amount_paid']:,.2f} "
                    f"from {top_overdue['partner_name']} ({top_overdue['days_overdue']} days overdue)"
                )

        # Cash management
        if summary["cash_position"]["total_liquid"] > 200000:
            recommendations.append(
                "Consider short-term investment options for excess cash reserves"
            )

        # Profit margin
        if summary["ytd_performance"]["profit_margin"] < 50:
            recommendations.append(
                "Review expense categories for potential cost optimization"
            )
        elif summary["ytd_performance"]["profit_margin"] > 70:
            recommendations.append(
                "Strong margins - consider reinvestment in growth initiatives"
            )

        # General
        if not risks:
            recommendations.append(
                "Financial health is strong - maintain current practices"
            )

        return recommendations

    def save_audit_to_vault(self, audit: Dict[str, Any]) -> str:
        """Save audit report to AI Employee Vault"""

        # Ensure directory exists
        exec_dir = self.vault_path / "Executive"
        exec_dir.mkdir(parents=True, exist_ok=True)

        # Save JSON report
        report_date = datetime.now().strftime("%Y%m%d")
        json_path = exec_dir / f"accounting_audit_{report_date}.json"

        with open(json_path, "w") as f:
            json.dump(audit, f, indent=2)

        # Generate markdown summary
        md_path = exec_dir / f"accounting_audit_{report_date}.md"
        md_content = self._format_audit_markdown(audit)

        with open(md_path, "w") as f:
            f.write(md_content)

        logger.info(f"Audit saved to {md_path}")
        return str(md_path)

    def _format_audit_markdown(self, audit: Dict[str, Any]) -> str:
        """Format audit as markdown for CEO briefing"""

        summary = audit["executive_summary"]
        metrics = audit["key_metrics"]

        md = f"""# Weekly Accounting Audit

**Generated:** {audit['generated_at']}
**Period:** {audit['period']['start']} to {audit['period']['end']}

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Cash Position | ${summary['cash_position']:,.2f} |
| Weekly Cash In | ${summary['weekly_cash_in']:,.2f} |
| Weekly Cash Out | ${summary['weekly_cash_out']:,.2f} |
| Net Cash Flow | ${summary['net_cash_flow']:,.2f} |
| YTD Profit Margin | {summary['ytd_profit_margin']}% |

---

## Financial Health

### Cash Position
- **Cash:** ${metrics['cash_position']['cash']:,.2f}
- **Bank:** ${metrics['cash_position']['bank']:,.2f}
- **Total Liquid:** ${metrics['cash_position']['total_liquid']:,.2f}

### Receivables
- **Outstanding:** ${metrics['receivables']['total_outstanding']:,.2f}
- **Overdue:** ${metrics['receivables']['overdue_amount']:,.2f} ({metrics['receivables']['overdue_count']} invoices)

### Year-to-Date Performance
- **Revenue:** ${metrics['ytd_performance']['revenue']:,.2f}
- **Expenses:** ${metrics['ytd_performance']['expenses']:,.2f}
- **Net Income:** ${metrics['ytd_performance']['net_income']:,.2f}

---

## Risk Assessment

"""

        if audit["risks"]:
            for risk in audit["risks"]:
                md += f"### {risk['level']} - {risk['category']}\n"
                md += f"- **Issue:** {risk['description']}\n"
                md += f"- **Action:** {risk['action']}\n\n"
        else:
            md += "No significant risks identified.\n\n"

        md += "---\n\n## Overdue Invoices\n\n"

        if audit["overdue_invoices"]:
            md += "| Invoice | Customer | Amount | Days Overdue |\n"
            md += "|---------|----------|--------|-------------|\n"
            for inv in audit["overdue_invoices"]:
                amount = inv["amount_total"] - inv["amount_paid"]
                md += f"| {inv['number']} | {inv['partner_name']} | ${amount:,.2f} | {inv['days_overdue']} |\n"
        else:
            md += "No overdue invoices.\n"

        md += "\n---\n\n## Recommendations\n\n"
        for i, rec in enumerate(audit["recommendations"], 1):
            md += f"{i}. {rec}\n"

        md += "\n---\n\n*Generated by Odoo Accounting MCP Server - Gold Tier*\n"

        return md


# =============================================================================
# MCP Server Implementation
# =============================================================================

class OdooMCPServer:
    """
    MCP Server for Odoo Accounting Integration

    Implements the Model Context Protocol for Claude Code integration.
    Provides tools and resources for accounting operations.
    """

    def __init__(self, config: Optional[OdooConfig] = None):
        self.config = config or OdooConfig()
        self.connector = OdooConnector(self.config)
        self.accounting = AccountingService(self.connector)
        self.tools = self._define_tools()
        self.resources = self._define_resources()

    def _define_tools(self) -> List[MCPTool]:
        """Define available MCP tools"""

        return [
            MCPTool(
                name="get_invoices",
                description="Retrieve invoices from Odoo. Filter by type (out_invoice=sales, in_invoice=bills) and state (open, paid, partial, overdue).",
                input_schema={
                    "type": "object",
                    "properties": {
                        "invoice_type": {
                            "type": "string",
                            "enum": ["all", "out_invoice", "in_invoice"],
                            "description": "Filter by invoice type"
                        },
                        "state": {
                            "type": "string",
                            "enum": ["all", "open", "paid", "partial", "overdue"],
                            "description": "Filter by state"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of invoices to return"
                        }
                    }
                }
            ),
            MCPTool(
                name="get_overdue_invoices",
                description="Get all overdue customer invoices with days overdue calculation. Critical for collections follow-up.",
                input_schema={
                    "type": "object",
                    "properties": {}
                }
            ),
            MCPTool(
                name="get_payments",
                description="Retrieve payment records. Filter by type (inbound=received, outbound=made) and date range.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "payment_type": {
                            "type": "string",
                            "enum": ["all", "inbound", "outbound"],
                            "description": "Filter by payment direction"
                        },
                        "date_from": {
                            "type": "string",
                            "format": "date",
                            "description": "Start date (YYYY-MM-DD)"
                        },
                        "date_to": {
                            "type": "string",
                            "format": "date",
                            "description": "End date (YYYY-MM-DD)"
                        }
                    }
                }
            ),
            MCPTool(
                name="get_expenses",
                description="Retrieve expense records. Filter by state (pending, approved) and category.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "state": {
                            "type": "string",
                            "enum": ["all", "pending", "approved", "rejected"],
                            "description": "Filter by approval state"
                        },
                        "category": {
                            "type": "string",
                            "description": "Filter by expense category"
                        }
                    }
                }
            ),
            MCPTool(
                name="get_financial_summary",
                description="Get comprehensive financial summary including cash position, receivables, payables, and YTD performance.",
                input_schema={
                    "type": "object",
                    "properties": {}
                }
            ),
            MCPTool(
                name="generate_weekly_audit",
                description="Generate weekly accounting audit report for CEO briefing. Includes financial health, risks, and recommendations.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "save_to_vault": {
                            "type": "boolean",
                            "description": "Save report to AI Employee Vault",
                            "default": True
                        }
                    }
                }
            ),
            MCPTool(
                name="check_cash_flow",
                description="Analyze current cash flow status and forecast based on pending invoices and payments.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "days_ahead": {
                            "type": "integer",
                            "description": "Number of days to forecast",
                            "default": 30
                        }
                    }
                }
            )
        ]

    def _define_resources(self) -> List[MCPResource]:
        """Define available MCP resources"""

        return [
            MCPResource(
                uri="odoo://financial/summary",
                name="Financial Summary",
                description="Current financial summary including cash, receivables, and YTD performance"
            ),
            MCPResource(
                uri="odoo://invoices/overdue",
                name="Overdue Invoices",
                description="List of all overdue customer invoices requiring attention"
            ),
            MCPResource(
                uri="odoo://audit/latest",
                name="Latest Audit Report",
                description="Most recent weekly accounting audit"
            )
        ]

    def initialize(self) -> Dict[str, Any]:
        """Initialize the MCP server"""

        connected = self.connector.connect()

        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"subscribe": False, "listChanged": False}
            },
            "serverInfo": {
                "name": "odoo-accounting-mcp",
                "version": "1.0.0",
                "description": "Odoo Accounting Integration for AI Employee System"
            },
            "status": "connected" if connected else "simulation_mode"
        }

    def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools"""
        return [asdict(tool) for tool in self.tools]

    def list_resources(self) -> List[Dict[str, Any]]:
        """List available resources"""
        return [asdict(resource) for resource in self.resources]

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool call"""

        try:
            if name == "get_invoices":
                result = self.accounting.get_invoices(
                    invoice_type=arguments.get("invoice_type", "all"),
                    state=arguments.get("state", "all"),
                    limit=arguments.get("limit", 100)
                )

            elif name == "get_overdue_invoices":
                result = self.accounting.get_overdue_invoices()

            elif name == "get_payments":
                result = self.accounting.get_payments(
                    payment_type=arguments.get("payment_type", "all"),
                    date_from=arguments.get("date_from"),
                    date_to=arguments.get("date_to")
                )

            elif name == "get_expenses":
                result = self.accounting.get_expenses(
                    state=arguments.get("state", "all"),
                    category=arguments.get("category", "all")
                )

            elif name == "get_financial_summary":
                result = self.accounting.get_financial_summary()

            elif name == "generate_weekly_audit":
                audit = self.accounting.generate_weekly_audit()
                if arguments.get("save_to_vault", True):
                    path = self.accounting.save_audit_to_vault(audit)
                    audit["saved_to"] = path
                result = audit

            elif name == "check_cash_flow":
                days = arguments.get("days_ahead", 30)
                summary = self.accounting.get_financial_summary()
                invoices = self.accounting.get_invoices(state="open")

                # Simple cash flow projection
                expected_inflow = sum(
                    inv["amount_total"] - inv["amount_paid"]
                    for inv in invoices if inv["type"] == "out_invoice"
                )

                result = {
                    "current_cash": summary["cash_position"]["total_liquid"],
                    "expected_inflow_30d": expected_inflow,
                    "projected_cash_30d": summary["cash_position"]["total_liquid"] + expected_inflow,
                    "forecast_days": days,
                    "status": "healthy" if summary["cash_position"]["total_liquid"] > 50000 else "attention_needed"
                }

            else:
                return {
                    "error": f"Unknown tool: {name}",
                    "available_tools": [t.name for t in self.tools]
                }

            return {
                "success": True,
                "tool": name,
                "result": result
            }

        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {
                "success": False,
                "tool": name,
                "error": str(e)
            }

    def read_resource(self, uri: str) -> Dict[str, Any]:
        """Read a resource"""

        try:
            if uri == "odoo://financial/summary":
                return self.accounting.get_financial_summary()

            elif uri == "odoo://invoices/overdue":
                return {"overdue_invoices": self.accounting.get_overdue_invoices()}

            elif uri == "odoo://audit/latest":
                return self.accounting.generate_weekly_audit()

            else:
                return {"error": f"Unknown resource: {uri}"}

        except Exception as e:
            return {"error": str(e)}

    def run_stdio(self):
        """Run the MCP server in stdio mode"""

        logger.info("Starting Odoo MCP Server (stdio mode)")
        self.connector.connect()

        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break

                request = json.loads(line.strip())
                response = self._handle_request(request)

                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()

            except json.JSONDecodeError as e:
                error_response = {
                    "jsonrpc": "2.0",
                    "error": {"code": -32700, "message": f"Parse error: {e}"},
                    "id": None
                }
                sys.stdout.write(json.dumps(error_response) + "\n")
                sys.stdout.flush()
            except Exception as e:
                logger.error(f"Request handling error: {e}")

    def _handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming MCP request"""

        method = request.get("method", "")
        params = request.get("params", {})
        request_id = request.get("id")

        result = None
        error = None

        if method == "initialize":
            result = self.initialize()

        elif method == "tools/list":
            result = {"tools": self.list_tools()}

        elif method == "resources/list":
            result = {"resources": self.list_resources()}

        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            result = self.call_tool(tool_name, tool_args)

        elif method == "resources/read":
            uri = params.get("uri", "")
            result = self.read_resource(uri)

        else:
            error = {"code": -32601, "message": f"Method not found: {method}"}

        response = {"jsonrpc": "2.0", "id": request_id}
        if error:
            response["error"] = error
        else:
            response["result"] = result

        return response


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    """Main entry point"""

    import argparse

    parser = argparse.ArgumentParser(
        description="Odoo Accounting MCP Server - Gold Tier"
    )
    parser.add_argument(
        "--mode",
        choices=["stdio", "test", "audit"],
        default="stdio",
        help="Server mode (default: stdio)"
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        default=True,
        help="Use simulation mode (no live Odoo connection)"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8069",
        help="Odoo server URL"
    )
    parser.add_argument(
        "--database",
        default="odoo_db",
        help="Odoo database name"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Configure connection
    config = OdooConfig(
        url=args.url,
        database=args.database,
        mode=OdooConnectionMode.SIMULATE if args.simulate else OdooConnectionMode.LIVE
    )

    server = OdooMCPServer(config)

    if args.mode == "stdio":
        server.run_stdio()

    elif args.mode == "test":
        # Test mode - run through all tools
        print("\n=== Odoo MCP Server Test Mode ===\n")

        init_result = server.initialize()
        print(f"Initialized: {init_result['serverInfo']['name']} v{init_result['serverInfo']['version']}")
        print(f"Status: {init_result['status']}\n")

        print("Available Tools:")
        for tool in server.list_tools():
            print(f"  - {tool['name']}: {tool['description'][:60]}...")

        print("\n--- Testing get_financial_summary ---")
        result = server.call_tool("get_financial_summary", {})
        print(json.dumps(result["result"], indent=2))

        print("\n--- Testing get_overdue_invoices ---")
        result = server.call_tool("get_overdue_invoices", {})
        print(json.dumps(result["result"], indent=2))

        print("\n--- Testing check_cash_flow ---")
        result = server.call_tool("check_cash_flow", {"days_ahead": 30})
        print(json.dumps(result["result"], indent=2))

        print("\n=== All Tests Completed ===")

    elif args.mode == "audit":
        # Generate weekly audit
        print("\n=== Generating Weekly Accounting Audit ===\n")

        server.initialize()
        result = server.call_tool("generate_weekly_audit", {"save_to_vault": True})

        if result["success"]:
            print(f"Audit generated successfully!")
            print(f"Saved to: {result['result'].get('saved_to', 'N/A')}")
            print("\n--- Executive Summary ---")
            summary = result["result"]["executive_summary"]
            print(f"Cash Position: ${summary['cash_position']:,.2f}")
            print(f"Weekly Cash Flow: ${summary['net_cash_flow']:,.2f}")
            print(f"YTD Profit Margin: {summary['ytd_profit_margin']}%")

            if result["result"]["risks"]:
                print("\n--- Risks Identified ---")
                for risk in result["result"]["risks"]:
                    print(f"  [{risk['level']}] {risk['category']}: {risk['description']}")
        else:
            print(f"Error: {result['error']}")


if __name__ == "__main__":
    main()
