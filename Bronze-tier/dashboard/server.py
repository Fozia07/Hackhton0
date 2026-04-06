#!/usr/bin/env python3
"""
AI Employee Dashboard - Web Server
Compatible with Python 3.6+

Usage:
    python3 server.py                    # Run on default port 8080
    python3 server.py --port 3000        # Run on custom port
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

# Paths
DASHBOARD_DIR = Path(__file__).parent.resolve()
BASE_DIR = DASHBOARD_DIR.parent
VAULT_DIR = Path(os.environ.get("VAULT_PATH", str(BASE_DIR / "AI_Employee_Vault")))

# Create all required directories
def create_directories():
    """Create all required directories."""
    dirs = [
        VAULT_DIR,
        VAULT_DIR / "Needs_Action",
        VAULT_DIR / "Needs_Action" / "email",
        VAULT_DIR / "Needs_Action" / "general",
        VAULT_DIR / "Needs_Action" / "social",
        VAULT_DIR / "Pending_Approval",
        VAULT_DIR / "Done",
        VAULT_DIR / "Logs",
        VAULT_DIR / "Signals",
    ]
    for d in dirs:
        try:
            d.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"Warning: Could not create {d}: {e}")

# Create directories on import
create_directories()

# Directory shortcuts
NEEDS_ACTION = VAULT_DIR / "Needs_Action"
PENDING_APPROVAL = VAULT_DIR / "Pending_Approval"
DONE = VAULT_DIR / "Done"
LOGS_DIR = VAULT_DIR / "Logs"


class DashboardHandler(SimpleHTTPRequestHandler):
    """HTTP Request Handler for Dashboard API and static files."""

    def translate_path(self, path):
        """Translate URL path to filesystem path - serve from dashboard dir."""
        # Remove query string and fragment
        path = path.split('?', 1)[0]
        path = path.split('#', 1)[0]

        # Normalize path
        if path == '/':
            path = '/index.html'

        # Build full path from dashboard directory
        return str(DASHBOARD_DIR / path.lstrip('/'))

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

    def handle_get_tasks(self):
        """Get all tasks from vault folders."""
        tasks = []

        def read_folder_tasks(folder, status):
            if not folder.exists():
                return []
            result = []
            try:
                for f in folder.glob("*.md"):
                    task = parse_task_file(f, status)
                    if task:
                        result.append(task)
            except Exception:
                pass
            return result

        tasks.extend(read_folder_tasks(NEEDS_ACTION, 'pending'))
        tasks.extend(read_folder_tasks(PENDING_APPROVAL, 'processing'))
        tasks.extend(read_folder_tasks(DONE, 'done'))

        for subfolder in ['email', 'general', 'social']:
            tasks.extend(read_folder_tasks(NEEDS_ACTION / subfolder, 'pending'))

        tasks.sort(key=lambda x: x.get('createdAt', ''), reverse=True)
        self.send_json({'tasks': tasks[:50]})

    def handle_create_task(self):
        """Create a new task file."""
        try:
            data = self.read_json_body()
            title = data.get('title', 'Untitled Task')
            task_type = data.get('type', 'GENERAL')
            priority = data.get('priority', 'normal')

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_title = ''.join(c if c.isalnum() or c in '-_' else '_' for c in title[:30])
            filename = f"{task_type}_{safe_title}_{timestamp}.md"

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

            if task_type == 'EMAIL':
                folder = NEEDS_ACTION / 'email'
            elif task_type in ['FACEBOOK', 'LINKEDIN', 'TWITTER', 'INSTAGRAM']:
                folder = NEEDS_ACTION / 'social'
            else:
                folder = NEEDS_ACTION / 'general'

            folder.mkdir(parents=True, exist_ok=True)
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
        logs = [
            {'time': datetime.now().strftime('%H:%M:%S'), 'level': 'info', 'message': 'Dashboard server running'},
            {'time': datetime.now().strftime('%H:%M:%S'), 'level': 'success', 'message': 'System operational'},
            {'time': datetime.now().strftime('%H:%M:%S'), 'level': 'info', 'message': 'Cloud agent ready'},
        ]

        sync_log = LOGS_DIR / f"sync_{datetime.now().strftime('%Y%m%d')}.log"
        if sync_log.exists():
            try:
                lines = sync_log.read_text().strip().split('\n')[-20:]
                for line in reversed(lines):
                    if line.strip():
                        logs.append({'time': '', 'level': 'info', 'message': line[:100]})
            except Exception:
                pass

        self.send_json({'logs': logs})

    def handle_get_status(self):
        """Get system status."""
        status = {
            'status': 'running',
            'agentId': 'cloud',
            'syncInterval': 60,
            'agentInterval': 30,
            'lastHeartbeat': datetime.now().isoformat(),
            'isHealthy': True
        }
        self.send_json(status)

    def handle_get_metrics(self):
        """Get task metrics."""
        def count_files(folder, pattern="*.md"):
            if not folder.exists():
                return 0
            return len(list(folder.glob(pattern)))

        pending = count_files(NEEDS_ACTION) + count_files(NEEDS_ACTION / "email") + count_files(NEEDS_ACTION / "general")
        processing = count_files(PENDING_APPROVAL)
        done = count_files(DONE)

        metrics = {
            'tasksProcessed': done,
            'emailsDrafted': count_files(DONE, "*EMAIL*.md"),
            'socialPosts': count_files(DONE, "*FACEBOOK*.md") + count_files(DONE, "*LINKEDIN*.md"),
            'pending': pending,
            'processing': processing
        }

        self.send_json(metrics)

    def log_message(self, format, *args):
        """Custom logging."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] {args[0]}")


def parse_task_file(filepath, status):
    """Parse a task file and extract metadata."""
    try:
        content = filepath.read_text()
        name = filepath.name

        task_type = 'GENERAL'
        for t in ['EMAIL', 'FACEBOOK', 'LINKEDIN', 'TWITTER', 'INSTAGRAM']:
            if t in name.upper():
                task_type = t
                break

        title = name.replace('.md', '').replace('_', ' ')
        for line in content.split('\n'):
            if line.startswith('# '):
                title = line[2:].strip()
                break

        priority = 'normal'
        content_lower = content.lower()
        if 'priority: high' in content_lower:
            priority = 'high'
        elif 'priority: urgent' in content_lower:
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


def main():
    parser = argparse.ArgumentParser(description='AI Employee Dashboard Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8080, help='Port to listen on')
    args = parser.parse_args()

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║           AI Employee Dashboard Server                        ║
╠══════════════════════════════════════════════════════════════╣
║  Server running at:  http://{args.host}:{args.port}                       ║
║  Dashboard:          http://localhost:{args.port}                       ║
║  Vault path:         {str(VAULT_DIR)[:40]:<40} ║
╚══════════════════════════════════════════════════════════════╝

Press Ctrl+C to stop the server.
    """)

    try:
        server = HTTPServer((args.host, args.port), DashboardHandler)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
