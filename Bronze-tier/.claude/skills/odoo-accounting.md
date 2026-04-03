# Odoo Accounting Integration

## Description
Enterprise-grade accounting integration with Odoo ERP system. Provides financial reporting, invoice management, payment tracking, expense management, and automated CEO briefings.

## When to Use
- When user asks about financial status, invoices, or payments
- When generating weekly accounting audits
- When checking cash flow or receivables
- When preparing CEO briefings with financial data
- When tracking expenses or pending approvals

## MCP Server
This skill uses the `odoo-accounting` MCP server located at `mcp_servers/odoo_accounting/server.py`

## Available Tools

### get_invoices
Retrieve invoices with optional filtering
- `invoice_type`: all, out_invoice (sales), in_invoice (bills)
- `state`: all, open, paid, partial, overdue
- `limit`: Maximum number to return

### get_overdue_invoices
Get all overdue customer invoices with days overdue calculation.
Critical for collections follow-up.

### get_payments
Retrieve payment records with filtering
- `payment_type`: all, inbound (received), outbound (made)
- `date_from`, `date_to`: Date range filter

### get_expenses
Retrieve expense records
- `state`: all, pending, approved, rejected
- `category`: Filter by expense category

### get_financial_summary
Comprehensive financial summary including:
- Cash position (cash, bank, total liquid)
- Receivables (outstanding, overdue)
- Payables
- YTD performance (revenue, expenses, net income, margin)

### generate_weekly_audit
Generate weekly accounting audit for CEO briefing
- Automatically saves to `AI_Employee_Vault/Executive/`
- Includes risks and recommendations

### check_cash_flow
Analyze cash flow status and forecast
- `days_ahead`: Number of days to forecast (default 30)

## CLI Usage

```bash
# Test mode - verify all tools work
python mcp_servers/odoo_accounting/server.py --mode test --verbose

# Generate weekly audit
python mcp_servers/odoo_accounting/server.py --mode audit

# Run as MCP server (stdio)
python mcp_servers/odoo_accounting/server.py --mode stdio --simulate
```

## Integration with CEO Briefing

The weekly audit automatically generates:
1. JSON report: `AI_Employee_Vault/Executive/accounting_audit_YYYYMMDD.json`
2. Markdown summary: `AI_Employee_Vault/Executive/accounting_audit_YYYYMMDD.md`

## Simulation Mode
By default, the server runs in simulation mode with realistic test data.
For live Odoo connection, configure:
- `--url`: Odoo server URL
- `--database`: Database name
- Remove `--simulate` flag

## Example Workflow

1. Check financial health:
   - Call `get_financial_summary` tool

2. Follow up on collections:
   - Call `get_overdue_invoices` tool

3. Weekly CEO briefing:
   - Call `generate_weekly_audit` tool with `save_to_vault: true`
