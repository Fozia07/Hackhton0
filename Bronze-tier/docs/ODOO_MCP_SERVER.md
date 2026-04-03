# Odoo Accounting MCP Server

## Overview

The Odoo Accounting MCP Server provides enterprise-grade accounting integration for the AI Employee System. It implements the Model Context Protocol (MCP) to expose Odoo ERP accounting capabilities as tools and resources.

## Features

- **Invoice Management**: Retrieve, filter, and track invoices
- **Payment Tracking**: Monitor inbound/outbound payments
- **Expense Management**: Track and categorize expenses
- **Financial Reporting**: Cash position, receivables, YTD performance
- **Weekly Audits**: Automated accounting audit generation
- **CEO Briefings**: Integrated with unified briefing system
- **Simulation Mode**: Test without live Odoo connection

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Claude Code / AI Agent                    │
└─────────────────────────────┬───────────────────────────────┘
                              │ MCP Protocol (stdio)
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Odoo MCP Server                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Tools     │  │  Resources  │  │  Accounting Service │  │
│  │  Handler    │  │   Handler   │  │                     │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         │                │                     │             │
│         └────────────────┼─────────────────────┘             │
│                          │                                   │
│  ┌───────────────────────┴───────────────────────────────┐  │
│  │              Odoo Connector                            │  │
│  │   (XML-RPC / Simulation Mode)                         │  │
│  └───────────────────────┬───────────────────────────────┘  │
└──────────────────────────┼──────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
    ┌──────────┐    ┌──────────┐    ┌──────────────────┐
    │ Odoo ERP │    │ Simulated│    │ AI Employee Vault│
    │ (Live)   │    │   Data   │    │  /Executive/     │
    └──────────┘    └──────────┘    └──────────────────┘
```

## Installation

The MCP server is included in the AI Employee System. No additional installation required.

### Configuration

```json
{
  "mcpServers": {
    "odoo-accounting": {
      "command": "python",
      "args": [
        "mcp_servers/odoo_accounting/server.py",
        "--mode", "stdio",
        "--simulate"
      ]
    }
  }
}
```

## Available Tools

### get_invoices
Retrieve invoices with optional filtering.

**Parameters:**
- `invoice_type`: `all`, `out_invoice` (sales), `in_invoice` (bills)
- `state`: `all`, `open`, `paid`, `partial`, `overdue`
- `limit`: Maximum number to return

**Example Response:**
```json
{
  "id": 1002,
  "number": "INV/2026/0002",
  "partner_name": "Digital Dynamics Inc",
  "date_invoice": "2026-02-23",
  "date_due": "2026-03-15",
  "amount_total": 8500.00,
  "amount_paid": 0.00,
  "state": "open"
}
```

### get_overdue_invoices
Get all overdue customer invoices with days overdue calculation.

**Returns:** List of overdue invoices with `days_overdue` field.

### get_payments
Retrieve payment records with filtering.

**Parameters:**
- `payment_type`: `all`, `inbound` (received), `outbound` (made)
- `date_from`: Start date (YYYY-MM-DD)
- `date_to`: End date (YYYY-MM-DD)

### get_expenses
Retrieve expense records.

**Parameters:**
- `state`: `all`, `pending`, `approved`, `rejected`
- `category`: Filter by expense category

### get_financial_summary
Get comprehensive financial summary.

**Returns:**
```json
{
  "company": "AI Employee Corp",
  "currency": "USD",
  "cash_position": {
    "cash": 45000.00,
    "bank": 128500.00,
    "total_liquid": 173500.00
  },
  "receivables": {
    "total_outstanding": 24700.00,
    "overdue_amount": 5200.00,
    "overdue_count": 1
  },
  "ytd_performance": {
    "revenue": 185000.00,
    "expenses": 72000.00,
    "net_income": 113000.00,
    "profit_margin": 61.1
  }
}
```

### generate_weekly_audit
Generate weekly accounting audit for CEO briefing.

**Parameters:**
- `save_to_vault`: Boolean (default: true) - Save to AI Employee Vault

**Outputs:**
- JSON report: `AI_Employee_Vault/Executive/accounting_audit_YYYYMMDD.json`
- Markdown summary: `AI_Employee_Vault/Executive/accounting_audit_YYYYMMDD.md`

### check_cash_flow
Analyze cash flow status and forecast.

**Parameters:**
- `days_ahead`: Number of days to forecast (default: 30)

## CLI Usage

### Test Mode
Verify all tools work correctly:
```bash
python3 mcp_servers/odoo_accounting/server.py --mode test --verbose
```

### Generate Audit
Create weekly accounting audit:
```bash
python3 mcp_servers/odoo_accounting/server.py --mode audit
```

### Run as MCP Server
Start in stdio mode for Claude Code integration:
```bash
python3 mcp_servers/odoo_accounting/server.py --mode stdio --simulate
```

### Live Odoo Connection
Connect to actual Odoo instance:
```bash
python3 mcp_servers/odoo_accounting/server.py \
  --mode stdio \
  --url http://your-odoo-server:8069 \
  --database your_database
```

## CEO Briefing Integration

The Odoo MCP Server integrates with the unified CEO Briefing system:

```bash
python3 scripts/weekly_ceo_briefing.py --verbose
```

This generates a comprehensive briefing combining:
- Financial health (from Odoo)
- Social media performance
- System operational health

## Simulation Mode

For development and testing, simulation mode provides realistic data:

- 5 sample invoices (paid, open, partial, overdue)
- 3 payment records
- 4 expense entries
- Company financial accounts

## Security Notes

- API keys are never logged
- Simulation mode uses no real credentials
- Live mode requires proper Odoo access rights

## File Structure

```
mcp_servers/
└── odoo_accounting/
    ├── __init__.py
    ├── server.py         # Main MCP server implementation
    └── config.json       # MCP configuration

.claude/skills/
└── odoo-accounting.md    # Claude Code skill definition

AI_Employee_Vault/Executive/
├── accounting_audit_YYYYMMDD.json
├── accounting_audit_YYYYMMDD.md
├── ceo_briefing_YYYYMMDD.json
└── ceo_briefing_YYYYMMDD.md
```

## Troubleshooting

### Server not responding
Check if running in correct mode:
```bash
python3 mcp_servers/odoo_accounting/server.py --mode test
```

### Connection failed (live mode)
Verify Odoo server is accessible:
```bash
curl http://your-odoo-server:8069/web/webclient/version_info
```

### Missing audit files
Ensure vault directories exist:
```bash
mkdir -p AI_Employee_Vault/Executive
```

---

*Part of AI Employee System - Gold Tier*
