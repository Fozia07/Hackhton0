"""
Email MCP Server - Model Context Protocol Server for Email
Silver Tier Component
Enhanced with Gold Tier Audit Logging & Error Recovery

A custom MCP server that enables Claude Code to send emails.
Based on: Skills/email_sender.md

This server implements the MCP protocol for email operations:
- send_email: Send an email via Gmail API
- draft_email: Create a draft email
- list_emails: List recent emails

Usage:
1. Configure in Claude Code settings
2. Set GMAIL_CREDENTIALS_PATH environment variable
3. Server will handle email operations from Claude

MCP Server runs as a subprocess that communicates via stdin/stdout JSON-RPC.
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)

# Configuration
BASE_DIR = Path(__file__).parent.parent
VAULT_DIR = BASE_DIR / "AI_Employee_Vault"
LOGS_DIR = VAULT_DIR / "Logs"
SIMULATION_MODE = os.environ.get("MCP_SIMULATION", "true").lower() == "true"

# Add parent directory for imports
sys.path.insert(0, str(BASE_DIR))

from utils.audit_logger import (
    get_audit_logger,
    ActionType,
    ApprovalStatus,
    ResultStatus
)

from utils.retry_handler import (
    get_retry_handler,
    get_circuit_breaker,
    get_queue_manager
)

# Actor name for audit logging
ACTOR = "email_mcp_server"

# Initialize audit logger
audit_logger = get_audit_logger()

# Initialize retry handler
retry_handler = get_retry_handler(
    actor=ACTOR,
    circuit_breaker="email_operations"
)
circuit_breaker = get_circuit_breaker("email_operations")
queue_manager = get_queue_manager()


class EmailMCPServer:
    """MCP Server for Email operations."""

    def __init__(self):
        self.name = "email-mcp"
        self.version = "1.0.0"
        self.gmail_service = None

        if not SIMULATION_MODE:
            self._init_gmail_service()

    def _init_gmail_service(self):
        """Initialize Gmail API service."""
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            credentials_path = os.environ.get("GMAIL_CREDENTIALS_PATH")
            token_path = BASE_DIR / "secrets" / "gmail_token.json"

            if token_path.exists():
                creds = Credentials.from_authorized_user_file(str(token_path))
                self.gmail_service = build("gmail", "v1", credentials=creds)
                logger.info("Gmail service initialized")
            else:
                logger.warning("Gmail token not found, running in simulation mode")

        except ImportError:
            logger.warning("Gmail libraries not installed, running in simulation mode")
        except Exception as e:
            logger.error(f"Failed to initialize Gmail: {e}")

    def get_capabilities(self):
        """Return server capabilities."""
        return {
            "name": self.name,
            "version": self.version,
            "tools": [
                {
                    "name": "send_email",
                    "description": "Send an email to a recipient",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "to": {"type": "string", "description": "Recipient email address"},
                            "subject": {"type": "string", "description": "Email subject"},
                            "body": {"type": "string", "description": "Email body content"},
                            "cc": {"type": "array", "items": {"type": "string"}, "description": "CC recipients"},
                        },
                        "required": ["to", "subject", "body"]
                    }
                },
                {
                    "name": "draft_email",
                    "description": "Create a draft email",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "to": {"type": "string", "description": "Recipient email address"},
                            "subject": {"type": "string", "description": "Email subject"},
                            "body": {"type": "string", "description": "Email body content"},
                        },
                        "required": ["to", "subject", "body"]
                    }
                },
                {
                    "name": "list_emails",
                    "description": "List recent emails from inbox",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "max_results": {"type": "integer", "description": "Maximum emails to return", "default": 10},
                            "query": {"type": "string", "description": "Search query", "default": "is:unread"}
                        }
                    }
                }
            ]
        }

    def send_email(self, to, subject, body, cc=None):
        """Send an email."""
        start_time = datetime.now()
        logger.info(f"Sending email to: {to}")

        if SIMULATION_MODE or not self.gmail_service:
            # Simulation mode
            result = {
                "success": True,
                "message_id": f"sim_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "to": to,
                "subject": subject,
                "sent_at": datetime.now().isoformat(),
                "simulation": True
            }
            self._log_action("send_email", result)

            # Audit log: email sent (simulated)
            audit_logger.log_with_duration(
                action_type=ActionType.EMAIL_SENT,
                actor=ACTOR,
                target=to,
                start_time=start_time,
                parameters={
                    'message_id': result['message_id'],
                    'subject': subject,
                    'simulation': True
                },
                result=ResultStatus.SUCCESS
            )
            return result

        # Check circuit breaker
        if not circuit_breaker.can_execute():
            logger.warning("CIRCUIT OPEN: Skipping email send")
            audit_logger.log(
                action_type=ActionType.WARNING_RAISED,
                actor=ACTOR,
                target=to,
                parameters={'reason': 'circuit_breaker_open', 'action': 'send_email'},
                result=ResultStatus.FAILURE
            )
            return {"success": False, "error": "Circuit breaker open - too many failures"}

        # Real Gmail API with retry handling
        def _do_send_email():
            import base64
            from email.mime.text import MIMEText

            message = MIMEText(body)
            message["to"] = to
            message["subject"] = subject
            if cc:
                message["cc"] = ", ".join(cc)

            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

            sent = self.gmail_service.users().messages().send(
                userId="me",
                body={"raw": raw}
            ).execute()
            return sent

        try:
            sent = retry_handler.execute(
                _do_send_email,
                task_id=f"send_email_{to}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                task_type="email_send"
            )
            circuit_breaker.record_success()

            result = {
                "success": True,
                "message_id": sent["id"],
                "to": to,
                "subject": subject,
                "sent_at": datetime.now().isoformat()
            }
            self._log_action("send_email", result)

            # Audit log: email sent (live)
            audit_logger.log_with_duration(
                action_type=ActionType.EMAIL_SENT,
                actor=ACTOR,
                target=to,
                start_time=start_time,
                parameters={
                    'message_id': sent['id'],
                    'subject': subject,
                    'simulation': False
                },
                result=ResultStatus.SUCCESS
            )
            return result

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            circuit_breaker.record_failure(e)

            # Audit log: error
            audit_logger.log_error(
                actor=ACTOR,
                target=to,
                error_message=str(e),
                error_type=type(e).__name__,
                parameters={'subject': subject, 'retries_exhausted': True}
            )
            return {"success": False, "error": str(e)}

    def draft_email(self, to, subject, body):
        """Create a draft email."""
        start_time = datetime.now()
        logger.info(f"Creating draft for: {to}")

        if SIMULATION_MODE or not self.gmail_service:
            result = {
                "success": True,
                "draft_id": f"draft_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "to": to,
                "subject": subject,
                "created_at": datetime.now().isoformat(),
                "simulation": True
            }
            self._log_action("draft_email", result)

            # Audit log: email drafted (simulated)
            audit_logger.log_with_duration(
                action_type=ActionType.EMAIL_DRAFTED,
                actor=ACTOR,
                target=to,
                start_time=start_time,
                parameters={
                    'draft_id': result['draft_id'],
                    'subject': subject,
                    'simulation': True
                },
                result=ResultStatus.SUCCESS
            )
            return result

        # Check circuit breaker
        if not circuit_breaker.can_execute():
            logger.warning("CIRCUIT OPEN: Skipping draft creation")
            audit_logger.log(
                action_type=ActionType.WARNING_RAISED,
                actor=ACTOR,
                target=to,
                parameters={'reason': 'circuit_breaker_open', 'action': 'draft_email'},
                result=ResultStatus.FAILURE
            )
            return {"success": False, "error": "Circuit breaker open - too many failures"}

        # Real Gmail API with retry handling
        def _do_draft_email():
            import base64
            from email.mime.text import MIMEText

            message = MIMEText(body)
            message["to"] = to
            message["subject"] = subject

            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

            draft = self.gmail_service.users().drafts().create(
                userId="me",
                body={"message": {"raw": raw}}
            ).execute()
            return draft

        try:
            draft = retry_handler.execute(
                _do_draft_email,
                task_id=f"draft_email_{to}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                task_type="email_draft"
            )
            circuit_breaker.record_success()

            result = {
                "success": True,
                "draft_id": draft["id"],
                "to": to,
                "subject": subject,
                "created_at": datetime.now().isoformat()
            }
            self._log_action("draft_email", result)

            # Audit log: email drafted (live)
            audit_logger.log_with_duration(
                action_type=ActionType.EMAIL_DRAFTED,
                actor=ACTOR,
                target=to,
                start_time=start_time,
                parameters={
                    'draft_id': draft['id'],
                    'subject': subject,
                    'simulation': False
                },
                result=ResultStatus.SUCCESS
            )
            return result

        except Exception as e:
            logger.error(f"Failed to create draft: {e}")
            circuit_breaker.record_failure(e)

            # Audit log: error
            audit_logger.log_error(
                actor=ACTOR,
                target=to,
                error_message=str(e),
                error_type=type(e).__name__,
                parameters={'subject': subject, 'action': 'draft_email', 'retries_exhausted': True}
            )
            return {"success": False, "error": str(e)}

    def list_emails(self, max_results=10, query="is:unread"):
        """List recent emails."""
        logger.info(f"Listing emails: {query}")

        if SIMULATION_MODE or not self.gmail_service:
            # Return simulated emails
            result = {
                "success": True,
                "emails": [
                    {
                        "id": "sim_001",
                        "from": "client@example.com",
                        "subject": "Project Update",
                        "snippet": "Here's the latest update...",
                        "date": datetime.now().isoformat()
                    },
                    {
                        "id": "sim_002",
                        "from": "partner@business.com",
                        "subject": "Meeting Request",
                        "snippet": "Can we schedule a call...",
                        "date": datetime.now().isoformat()
                    }
                ],
                "total": 2,
                "simulation": True
            }
            return result

        # Check circuit breaker
        if not circuit_breaker.can_execute():
            logger.warning("CIRCUIT OPEN: Skipping email listing")
            return {"success": False, "error": "Circuit breaker open - too many failures"}

        # Real Gmail API with retry handling
        def _do_list_emails():
            results = self.gmail_service.users().messages().list(
                userId="me",
                q=query,
                maxResults=max_results
            ).execute()

            messages = results.get("messages", [])
            emails = []

            for msg in messages[:max_results]:
                message = self.gmail_service.users().messages().get(
                    userId="me",
                    id=msg["id"],
                    format="metadata",
                    metadataHeaders=["From", "Subject", "Date"]
                ).execute()

                headers = {h["name"]: h["value"] for h in message["payload"]["headers"]}
                emails.append({
                    "id": msg["id"],
                    "from": headers.get("From", ""),
                    "subject": headers.get("Subject", ""),
                    "snippet": message.get("snippet", ""),
                    "date": headers.get("Date", "")
                })

            return emails

        try:
            emails = retry_handler.execute(
                _do_list_emails,
                task_id=f"list_emails_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                task_type="email_list"
            )
            circuit_breaker.record_success()
            return {"success": True, "emails": emails, "total": len(emails)}

        except Exception as e:
            logger.error(f"Failed to list emails: {e}")
            circuit_breaker.record_failure(e)
            return {"success": False, "error": str(e)}

    def _log_action(self, action, result):
        """Log MCP action to file."""
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        log_file = LOGS_DIR / f"{datetime.now().strftime('%Y-%m-%d')}_mcp_actions.json"

        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "result": result
        }

        # Append to log
        logs = []
        if log_file.exists():
            try:
                with open(log_file, "r") as f:
                    logs = json.load(f)
            except:
                logs = []

        logs.append(entry)

        with open(log_file, "w") as f:
            json.dump(logs, f, indent=2)

    def handle_request(self, request):
        """Handle an MCP request."""
        method = request.get("method", "")
        params = request.get("params", {})
        request_id = request.get("id")

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": self.get_capabilities()
                }
            }

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"tools": self.get_capabilities()["tools"]}
            }

        elif method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})

            if tool_name == "send_email":
                result = self.send_email(**arguments)
            elif tool_name == "draft_email":
                result = self.draft_email(**arguments)
            elif tool_name == "list_emails":
                result = self.list_emails(**arguments)
            else:
                result = {"error": f"Unknown tool: {tool_name}"}

            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result)}]}
            }

        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"}
            }


def run_server():
    """Run the MCP server."""
    server = EmailMCPServer()
    logger.info("Email MCP Server started")
    logger.info(f"Simulation mode: {SIMULATION_MODE}")

    # Audit log: system started
    audit_logger.log(
        action_type=ActionType.SYSTEM_STARTED,
        actor=ACTOR,
        target="email_mcp_server",
        parameters={'simulation_mode': SIMULATION_MODE},
        result=ResultStatus.SUCCESS
    )

    request_count = 0

    # Read requests from stdin, write responses to stdout
    for line in sys.stdin:
        try:
            request = json.loads(line.strip())
            response = server.handle_request(request)
            print(json.dumps(response), flush=True)
            request_count += 1
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON: {line}")
            audit_logger.log_error(
                actor=ACTOR,
                target="request_parser",
                error_message="Invalid JSON received",
                error_type="JSONDecodeError"
            )
        except Exception as e:
            logger.error(f"Error handling request: {e}")
            audit_logger.log_error(
                actor=ACTOR,
                target="request_handler",
                error_message=str(e),
                error_type=type(e).__name__
            )

    # Audit log: system stopped
    audit_logger.log(
        action_type=ActionType.SYSTEM_STOPPED,
        actor=ACTOR,
        target="email_mcp_server",
        parameters={'requests_processed': request_count},
        result=ResultStatus.SUCCESS
    )
    audit_logger.flush()


def test_server():
    """Test the server functionality."""
    server = EmailMCPServer()

    print("=" * 60)
    print("Email MCP Server - Test Mode")
    print("=" * 60)
    print(f"Simulation Mode: {SIMULATION_MODE}")
    print()

    # Test capabilities
    caps = server.get_capabilities()
    print(f"Server: {caps['name']} v{caps['version']}")
    print(f"Tools: {[t['name'] for t in caps['tools']]}")
    print()

    # Test send_email
    print("Testing send_email...")
    result = server.send_email(
        to="test@example.com",
        subject="Test Email",
        body="This is a test email from MCP server."
    )
    print(f"Result: {json.dumps(result, indent=2)}")
    print()

    # Test draft_email
    print("Testing draft_email...")
    result = server.draft_email(
        to="client@example.com",
        subject="Draft: Project Proposal",
        body="Please review the attached proposal..."
    )
    print(f"Result: {json.dumps(result, indent=2)}")
    print()

    # Test list_emails
    print("Testing list_emails...")
    result = server.list_emails(max_results=5)
    print(f"Result: {json.dumps(result, indent=2)}")
    print()

    # Circuit breaker status
    cb_state = circuit_breaker.get_state()
    print(f"Circuit State: {cb_state['state']}")

    # Retry queue status
    queue_stats = queue_manager.get_queue_stats()
    if queue_stats['total_tasks'] > 0:
        print(f"Retry Queue: {queue_stats['total_tasks']} tasks pending")

    print("=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    if "--test" in sys.argv:
        test_server()
    else:
        run_server()
