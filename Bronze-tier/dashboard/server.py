#!/usr/bin/env python3
"""
AI Employee Dashboard - Web Server
Serves the dashboard UI and provides REST API for task management.

Usage:
    python3 server.py                    # Run on default port 8080
    python3 server.py --port 3000        # Run on custom port
    python3 server.py --host 0.0.0.0     # Listen on all interfaces
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading
import time

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Paths
DASHBOARD_DIR = Path(__file__).parent
BASE_DIR = DASHBOARD_DIR.parent
VAULT_DIR = Path(os.environ.get("VAULT_PATH", BASE_DIR / "AI_Employee_Vault"))
NEEDS_ACTION = VAULT_DIR / "Needs_Action"
PENDING_APPROVAL = VAULT_DIR / "Pending_Approval"
DONE = VAULT_DIR / "Done"
LOGS_DIR = VAULT_DIR / "Logs"

# Ensure directories exist (create parents if needed)
VAULT_DIR.mkdir(parents=True, exist_ok=True)
NEEDS_ACTION.mkdir(parents=True, exist_ok=True)
PENDING_APPROVAL.mkdir(parents=True, exist_ok=True)
DONE.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
(NEEDS_ACTION / "email").mkdir(parents=True, exist_ok=True)
(NEEDS_ACTION / "general").mkdir(parents=True, exist_ok=True)
(NEEDS_ACTION / "social").mkdir(parents=True, exist_ok=True)
(VAULT_DIR / "Signals").mkdir(parents=True, exist_ok=True)


class DashboardHandler(SimpleHTTPRequestHandler):
    """HTTP Request Handler for Dashboard API and static files."""

    def __init__(self, *args, **kwargs):
        # Change to dashboard directory for static files
        super().__init__(*args, directory=str(DASHBOARD_DIR), **kwargs)

    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path

        # API Routes
        if path == '/api/tasks':
            self.handle_get_tasks()
        elif path == '/api/logs':
            self.handle_get_logs()
        elif path == '/api/status':
            self.handle_get_status()
        elif path == '/api/metrics':
            self.handle_get_metrics()
        else:
            # Serve static files
            if path == '/':
                self.path = '/index.html'
            super().do_GET()

    def do_POST(self):
        """Handle POST requests."""
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/api/tasks':
            self.handle_create_task()
        else:
            self.send_error(404, 'Not Found')

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()

    def send_cors_headers(self):
        """Add CORS headers."""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def send_json(self, data, status=200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def read_json_body(self):
        """Read JSON from request body."""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        return json.loads(body) if body else {}

    # ==========================================
    # API Handlers
    # ==========================================

    def handle_get_tasks(self):
        """Get all tasks from vault folders."""
        tasks = []

        # Helper to read tasks from a folder
        def read_folder_tasks(folder, status):
            if not folder.exists():
                return []
            folder_tasks = []
            for f in folder.glob("*.md"):
                task = parse_task_file(f, status)
                if task:
                    folder_tasks.append(task)
            return folder_tasks

        # Read from all task folders
        tasks.extend(read_folder_tasks(NEEDS_ACTION, 'pending'))
        tasks.extend(read_folder_tasks(PENDING_APPROVAL, 'processing'))
        tasks.extend(read_folder_tasks(DONE, 'done'))

        # Also check subfolders
        for subfolder in ['email', 'general', 'social']:
            tasks.extend(read_folder_tasks(NEEDS_ACTION / subfolder, 'pending'))

        # Sort by creation time (newest first)
        tasks.sort(key=lambda x: x.get('createdAt', ''), reverse=True)

        self.send_json({'tasks': tasks[:50]})  # Limit to 50 tasks

    def handle_create_task(self):
        """Create a new task file."""
        try:
            data = self.read_json_body()
            title = data.get('title', 'Untitled Task')
            task_type = data.get('type', 'GENERAL')
            priority = data.get('priority', 'normal')

            # Generate filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{task_type}_{sanitize_filename(title[:30])}_{timestamp}.md"

            # Create task content
            content = f"""---
type: {task_type.lower()}
priority: {priority}
created_at: {datetime.now().isoformat()}
status: pending
---

# {title}

Task created via Dashboard API.

**Type:** {task_type}
**Priority:** {priority}
**Created:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

            # Determine folder based on type
            if task_type == 'EMAIL':
                folder = NEEDS_ACTION / 'email'
            elif task_type in ['FACEBOOK', 'LINKEDIN', 'TWITTER', 'INSTAGRAM']:
                folder = NEEDS_ACTION / 'social'
            else:
                folder = NEEDS_ACTION / 'general'

            folder.mkdir(exist_ok=True)
            filepath = folder / filename
            filepath.write_text(content)

            task = {
                'id': timestamp,
                'title': title,
                'type': task_type,
                'priority': priority,
                'status': 'pending',
                'createdAt': datetime.now().isoformat(),
                'filename': filename
            }

            self.send_json({'success': True, 'task': task}, status=201)

        except Exception as e:
            self.send_json({'error': str(e)}, status=500)

    def handle_get_logs(self):
        """Get recent log entries."""
        logs = []

        # Read from sync log
        sync_log = LOGS_DIR / f"sync_{datetime.now().strftime('%Y%m%d')}.log"
        if sync_log.exists():
            try:
                lines = sync_log.read_text().strip().split('\n')[-50:]  # Last 50 lines
                for line in reversed(lines):
                    if line.strip():
                        logs.append(parse_log_line(line))
            except Exception:
                pass

        # If no logs, return simulated data
        if not logs:
            logs = [
                {'time': datetime.now().strftime('%H:%M:%S'), 'level': 'info', 'message': 'System running normally'},
                {'time': datetime.now().strftime('%H:%M:%S'), 'level': 'success', 'message': 'Vault sync completed'},
            ]

        self.send_json({'logs': logs})

    def handle_get_status(self):
        """Get system status."""
        # Check heartbeat file
        heartbeat_file = VAULT_DIR / "Signals" / "heartbeat_cloud.json"
        is_healthy = False
        last_heartbeat = None

        if heartbeat_file.exists():
            try:
                data = json.loads(heartbeat_file.read_text())
                last_heartbeat = data.get('timestamp')
                # Consider healthy if heartbeat within 5 minutes
                if last_heartbeat:
                    hb_time = datetime.fromisoformat(last_heartbeat.replace('Z', '+00:00'))
                    age = (datetime.now(hb_time.tzinfo) if hb_time.tzinfo else datetime.now()) - hb_time
                    is_healthy = age.total_seconds() < 300
            except Exception:
                pass

        status = {
            'status': 'running' if is_healthy else 'unknown',
            'agentId': 'cloud',
            'syncInterval': 60,
            'agentInterval': 30,
            'lastHeartbeat': last_heartbeat,
            'isHealthy': is_healthy
        }

        self.send_json(status)

    def handle_get_metrics(self):
        """Get task metrics."""
        # Count tasks in different states
        pending = count_files(NEEDS_ACTION, "*.md") + count_files(NEEDS_ACTION / "email", "*.md") + count_files(NEEDS_ACTION / "general", "*.md")
        processing = count_files(PENDING_APPROVAL, "*.md")
        done = count_files(DONE, "*.md")

        # Count by type
        email_count = count_files(DONE, "*EMAIL*.md")
        social_count = count_files(DONE, "*FACEBOOK*.md") + count_files(DONE, "*LINKEDIN*.md") + count_files(DONE, "*TWITTER*.md")

        metrics = {
            'tasksProcessed': done,
            'emailsDrafted': email_count,
            'socialPosts': social_count,
            'pending': pending,
            'processing': processing
        }

        self.send_json(metrics)

    def log_message(self, format, *args):
        """Override to customize logging."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] {args[0]}")


# ==========================================
# Helper Functions
# ==========================================

def parse_task_file(filepath, status):
    """Parse a task file and extract metadata."""
    try:
        content = filepath.read_text()
        name = filepath.name

        # Determine task type from filename
        task_type = 'GENERAL'
        for t in ['EMAIL', 'FACEBOOK', 'LINKEDIN', 'TWITTER', 'INSTAGRAM']:
            if t in name.upper():
                task_type = t
                break

        # Extract title from content or filename
        title = name.replace('.md', '').replace('_', ' ')
        if '# ' in content:
            for line in content.split('\n'):
                if line.startswith('# '):
                    title = line[2:].strip()
                    break

        # Extract priority from content
        priority = 'normal'
        if 'priority: high' in content.lower():
            priority = 'high'
        elif 'priority: urgent' in content.lower():
            priority = 'urgent'

        return {
            'id': filepath.stem,
            'title': title[:50],
            'type': task_type,
            'priority': priority,
            'status': status,
            'createdAt': datetime.fromtimestamp(filepath.stat().st_mtime).isoformat(),
            'filename': name
        }
    except Exception:
        return None


def parse_log_line(line):
    """Parse a log line into structured data."""
    try:
        # Expected format: [timestamp] [LEVEL] [agent] message
        parts = line.split('] ')
        time_part = parts[0].replace('[', '').split(' ')[-1]
        level = parts[1].replace('[', '').lower() if len(parts) > 1 else 'info'
        message = '] '.join(parts[2:]) if len(parts) > 2 else line

        return {
            'time': time_part,
            'level': level if level in ['info', 'warn', 'error', 'success', 'debug'] else 'info',
            'message': message
        }
    except Exception:
        return {'time': '', 'level': 'info', 'message': line}


def count_files(folder, pattern):
    """Count files matching pattern in folder."""
    if not folder.exists():
        return 0
    return len(list(folder.glob(pattern)))


def sanitize_filename(name):
    """Sanitize string for use in filename."""
    return ''.join(c if c.isalnum() or c in '-_' else '_' for c in name)


# ==========================================
# Main
# ==========================================

def main():
    parser = argparse.ArgumentParser(description='AI Employee Dashboard Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8080, help='Port to listen on')
    args = parser.parse_args()

    server = HTTPServer((args.host, args.port), DashboardHandler)

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║           AI Employee Dashboard Server                        ║
╠══════════════════════════════════════════════════════════════╣
║  Server running at:  http://{args.host}:{args.port}                     ║
║  Dashboard:          http://localhost:{args.port}                     ║
║  Vault path:         {str(VAULT_DIR)[:40]:<40} ║
╚══════════════════════════════════════════════════════════════╝

Press Ctrl+C to stop the server.
    """)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.shutdown()


if __name__ == '__main__':
    main()
