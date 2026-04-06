/**
 * AI Employee Dashboard - Application Logic
 * Handles task management, logs, and real-time updates
 */

// ============================================
// Configuration
// ============================================
const CONFIG = {
    API_URL: window.location.origin + '/api',
    REFRESH_INTERVAL: 5000,  // 5 seconds
    LOG_LIMIT: 100,
    SIMULATED_MODE: true     // Set to false when backend API is available
};

// ============================================
// State Management
// ============================================
const state = {
    tasks: [],
    logs: [],
    metrics: {
        tasksProcessed: 0,
        emailsDrafted: 0,
        socialPosts: 0
    },
    currentFilter: 'all',
    isConnected: true
};

// ============================================
// Initialization
// ============================================
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

function initializeApp() {
    // Load initial data
    loadTasks();
    loadLogs();
    updateMetrics();

    // Set up event listeners
    setupFilterButtons();
    setupKeyboardShortcuts();

    // Start refresh timer
    setInterval(refreshAll, CONFIG.REFRESH_INTERVAL);

    // Add initial log
    addLog('info', 'Dashboard initialized successfully');
    addLog('info', 'Cloud agent connection established');
    addLog('success', 'System is running in healthy state');

    // Update last update time
    updateLastUpdateTime();

    // Simulate some initial tasks if in simulated mode
    if (CONFIG.SIMULATED_MODE) {
        simulateInitialData();
    }
}

// ============================================
// Task Management
// ============================================
function loadTasks() {
    if (CONFIG.SIMULATED_MODE) {
        // Use simulated data
        updateTaskList();
        return;
    }

    // Real API call
    fetch(`${CONFIG.API_URL}/tasks`)
        .then(res => res.json())
        .then(data => {
            state.tasks = data.tasks || [];
            updateTaskList();
        })
        .catch(err => {
            console.error('Failed to load tasks:', err);
            addLog('error', 'Failed to load tasks from server');
        });
}

function addTask() {
    const input = document.getElementById('taskInput');
    const typeSelect = document.getElementById('taskType');
    const prioritySelect = document.getElementById('taskPriority');

    const title = input.value.trim();
    if (!title) {
        showToast('Please enter a task description', 'error');
        input.focus();
        return;
    }

    const task = {
        id: Date.now(),
        title: title,
        type: typeSelect.value,
        priority: prioritySelect.value,
        status: 'pending',
        createdAt: new Date().toISOString()
    };

    if (CONFIG.SIMULATED_MODE) {
        // Add to local state
        state.tasks.unshift(task);
        updateTaskList();
        updateMetrics();

        // Simulate processing
        simulateTaskProcessing(task);

        showToast(`Task "${title}" added successfully`, 'success');
        addLog('info', `New task created: ${title}`);
    } else {
        // Real API call
        fetch(`${CONFIG.API_URL}/tasks`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(task)
        })
        .then(res => res.json())
        .then(data => {
            state.tasks.unshift(data.task || task);
            updateTaskList();
            showToast(`Task "${title}" added successfully`, 'success');
            addLog('info', `New task created: ${title}`);
        })
        .catch(err => {
            console.error('Failed to add task:', err);
            showToast('Failed to add task', 'error');
        });
    }

    // Clear input
    input.value = '';
    input.focus();
}

function simulateTaskProcessing(task) {
    // Simulate task going to processing after 2-5 seconds
    const processDelay = 2000 + Math.random() * 3000;

    setTimeout(() => {
        const taskIndex = state.tasks.findIndex(t => t.id === task.id);
        if (taskIndex !== -1) {
            state.tasks[taskIndex].status = 'processing';
            updateTaskList();
            addLog('info', `Processing task: ${task.title}`);

            // Simulate completion after 3-8 seconds
            const completeDelay = 3000 + Math.random() * 5000;
            setTimeout(() => {
                const idx = state.tasks.findIndex(t => t.id === task.id);
                if (idx !== -1) {
                    state.tasks[idx].status = 'done';
                    updateTaskList();
                    updateTaskMetrics(task.type);
                    addLog('success', `Task completed: ${task.title}`);
                }
            }, completeDelay);
        }
    }, processDelay);
}

function updateTaskList() {
    const container = document.getElementById('taskList');
    const countBadge = document.getElementById('taskCount');

    // Filter tasks
    let filteredTasks = state.tasks;
    if (state.currentFilter !== 'all') {
        filteredTasks = state.tasks.filter(t => t.status === state.currentFilter);
    }

    // Update count
    countBadge.textContent = filteredTasks.length;

    // Render tasks
    if (filteredTasks.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M9 11l3 3L22 4M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/>
                </svg>
                <p>No tasks found</p>
            </div>
        `;
        return;
    }

    container.innerHTML = filteredTasks.map(task => createTaskHTML(task)).join('');
}

function createTaskHTML(task) {
    const iconType = getTaskIconType(task.type);
    const iconSVG = getTaskIcon(task.type);

    return `
        <div class="task-item" data-id="${task.id}">
            <div class="task-icon ${iconType}">
                ${iconSVG}
            </div>
            <div class="task-content">
                <div class="task-title">${escapeHtml(task.title)}</div>
                <div class="task-meta">
                    <span class="task-status ${task.status}">
                        ${getStatusIcon(task.status)}
                        ${capitalizeFirst(task.status)}
                    </span>
                    <span class="task-priority ${task.priority}">${capitalizeFirst(task.priority)}</span>
                    <span>${task.type}</span>
                </div>
            </div>
        </div>
    `;
}

function getTaskIconType(type) {
    if (type === 'EMAIL') return 'email';
    if (['FACEBOOK', 'LINKEDIN', 'TWITTER', 'INSTAGRAM'].includes(type)) return 'social';
    return 'general';
}

function getTaskIcon(type) {
    const icons = {
        EMAIL: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>',
        FACEBOOK: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg>',
        LINKEDIN: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>',
        TWITTER: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M23.953 4.57a10 10 0 01-2.825.775 4.958 4.958 0 002.163-2.723c-.951.555-2.005.959-3.127 1.184a4.92 4.92 0 00-8.384 4.482C7.69 8.095 4.067 6.13 1.64 3.162a4.822 4.822 0 00-.666 2.475c0 1.71.87 3.213 2.188 4.096a4.904 4.904 0 01-2.228-.616v.06a4.923 4.923 0 003.946 4.827 4.996 4.996 0 01-2.212.085 4.936 4.936 0 004.604 3.417 9.867 9.867 0 01-6.102 2.105c-.39 0-.779-.023-1.17-.067a13.995 13.995 0 007.557 2.209c9.053 0 13.998-7.496 13.998-13.985 0-.21 0-.42-.015-.63A9.935 9.935 0 0024 4.59z"/></svg>',
        INSTAGRAM: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C8.74 0 8.333.015 7.053.072 5.775.132 4.905.333 4.14.63c-.789.306-1.459.717-2.126 1.384S.935 3.35.63 4.14C.333 4.905.131 5.775.072 7.053.012 8.333 0 8.74 0 12s.015 3.667.072 4.947c.06 1.277.261 2.148.558 2.913.306.788.717 1.459 1.384 2.126.667.666 1.336 1.079 2.126 1.384.766.296 1.636.499 2.913.558C8.333 23.988 8.74 24 12 24s3.667-.015 4.947-.072c1.277-.06 2.148-.262 2.913-.558.788-.306 1.459-.718 2.126-1.384.666-.667 1.079-1.335 1.384-2.126.296-.765.499-1.636.558-2.913.06-1.28.072-1.687.072-4.947s-.015-3.667-.072-4.947c-.06-1.277-.262-2.149-.558-2.913-.306-.789-.718-1.459-1.384-2.126C21.319 1.347 20.651.935 19.86.63c-.765-.297-1.636-.499-2.913-.558C15.667.012 15.26 0 12 0zm0 2.16c3.203 0 3.585.016 4.85.071 1.17.055 1.805.249 2.227.415.562.217.96.477 1.382.896.419.42.679.819.896 1.381.164.422.36 1.057.413 2.227.057 1.266.07 1.646.07 4.85s-.015 3.585-.074 4.85c-.061 1.17-.256 1.805-.421 2.227-.224.562-.479.96-.899 1.382-.419.419-.824.679-1.38.896-.42.164-1.065.36-2.235.413-1.274.057-1.649.07-4.859.07-3.211 0-3.586-.015-4.859-.074-1.171-.061-1.816-.256-2.236-.421-.569-.224-.96-.479-1.379-.899-.421-.419-.69-.824-.9-1.38-.165-.42-.359-1.065-.42-2.235-.045-1.26-.061-1.649-.061-4.844 0-3.196.016-3.586.061-4.861.061-1.17.255-1.814.42-2.234.21-.57.479-.96.9-1.381.419-.419.81-.689 1.379-.898.42-.166 1.051-.361 2.221-.421 1.275-.045 1.65-.06 4.859-.06l.045.03zm0 3.678c-3.405 0-6.162 2.76-6.162 6.162 0 3.405 2.76 6.162 6.162 6.162 3.405 0 6.162-2.76 6.162-6.162 0-3.405-2.76-6.162-6.162-6.162zM12 16c-2.21 0-4-1.79-4-4s1.79-4 4-4 4 1.79 4 4-1.79 4-4 4zm7.846-10.405c0 .795-.646 1.44-1.44 1.44-.795 0-1.44-.646-1.44-1.44 0-.794.646-1.439 1.44-1.439.793-.001 1.44.645 1.44 1.439z"/></svg>',
        GENERAL: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>'
    };
    return icons[type] || icons.GENERAL;
}

function getStatusIcon(status) {
    const icons = {
        pending: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
        processing: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 4v6h-6M1 20v-6h6M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/></svg>',
        done: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>'
    };
    return icons[status] || '';
}

// ============================================
// Filter Management
// ============================================
function setupFilterButtons() {
    const buttons = document.querySelectorAll('.filter-btn');
    buttons.forEach(btn => {
        btn.addEventListener('click', () => {
            buttons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.currentFilter = btn.dataset.filter;
            updateTaskList();
        });
    });
}

// ============================================
// Logs Management
// ============================================
function loadLogs() {
    if (CONFIG.SIMULATED_MODE) {
        return;
    }

    fetch(`${CONFIG.API_URL}/logs`)
        .then(res => res.json())
        .then(data => {
            state.logs = data.logs || [];
            renderLogs();
        })
        .catch(err => {
            console.error('Failed to load logs:', err);
        });
}

function addLog(level, message) {
    const log = {
        time: new Date().toLocaleTimeString(),
        level: level,
        message: message
    };

    state.logs.unshift(log);
    if (state.logs.length > CONFIG.LOG_LIMIT) {
        state.logs.pop();
    }

    renderLogs();
}

function renderLogs() {
    const container = document.getElementById('logsContainer');
    container.innerHTML = state.logs.map(log => `
        <div class="log-entry">
            <span class="log-time">[${log.time}]</span>
            <span class="log-level ${log.level}">${log.level.toUpperCase()}</span>
            <span class="log-message">${escapeHtml(log.message)}</span>
        </div>
    `).join('');

    // Auto-scroll to top (newest logs)
    container.scrollTop = 0;
}

// ============================================
// Metrics Management
// ============================================
function updateMetrics() {
    document.getElementById('tasksProcessed').textContent = state.metrics.tasksProcessed;
    document.getElementById('emailsDrafted').textContent = state.metrics.emailsDrafted;
    document.getElementById('socialPosts').textContent = state.metrics.socialPosts;
}

function updateTaskMetrics(type) {
    state.metrics.tasksProcessed++;

    if (type === 'EMAIL') {
        state.metrics.emailsDrafted++;
    } else if (['FACEBOOK', 'LINKEDIN', 'TWITTER', 'INSTAGRAM'].includes(type)) {
        state.metrics.socialPosts++;
    }

    updateMetrics();
}

// ============================================
// Refresh & Update
// ============================================
function refreshAll() {
    loadTasks();
    updateLastUpdateTime();

    // Simulate random log entries
    if (CONFIG.SIMULATED_MODE && Math.random() > 0.7) {
        const messages = [
            'Checking vault for new tasks...',
            'Sync completed successfully',
            'Heartbeat sent to coordinator',
            'No new tasks detected',
            'Agent health check passed'
        ];
        const msg = messages[Math.floor(Math.random() * messages.length)];
        addLog('info', msg);
    }
}

function updateLastUpdateTime() {
    const element = document.getElementById('lastUpdate');
    element.textContent = `Last updated: ${new Date().toLocaleTimeString()}`;
}

// ============================================
// Toast Notifications
// ============================================
function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icon = type === 'success'
        ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>'
        : type === 'error'
        ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>'
        : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>';

    toast.innerHTML = `
        <span class="toast-icon">${icon}</span>
        <span class="toast-message">${escapeHtml(message)}</span>
    `;

    container.appendChild(toast);

    // Remove after 4 seconds
    setTimeout(() => {
        toast.style.animation = 'slideInRight 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// ============================================
// Keyboard Shortcuts
// ============================================
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Enter to add task when input is focused
        if (e.key === 'Enter' && document.activeElement.id === 'taskInput') {
            addTask();
        }

        // R to refresh
        if (e.key === 'r' && !e.ctrlKey && document.activeElement.tagName !== 'INPUT') {
            refreshAll();
            showToast('Dashboard refreshed', 'info');
        }
    });
}

// ============================================
// Simulation Data
// ============================================
function simulateInitialData() {
    // Add some sample tasks
    const sampleTasks = [
        { id: 1, title: 'Review customer inquiry about pricing', type: 'EMAIL', priority: 'high', status: 'done', createdAt: new Date().toISOString() },
        { id: 2, title: 'Post weekly update to LinkedIn', type: 'LINKEDIN', priority: 'normal', status: 'processing', createdAt: new Date().toISOString() },
        { id: 3, title: 'Respond to partnership request', type: 'EMAIL', priority: 'urgent', status: 'pending', createdAt: new Date().toISOString() },
        { id: 4, title: 'Schedule Facebook campaign post', type: 'FACEBOOK', priority: 'normal', status: 'pending', createdAt: new Date().toISOString() }
    ];

    state.tasks = sampleTasks;
    state.metrics = {
        tasksProcessed: 47,
        emailsDrafted: 23,
        socialPosts: 18
    };

    updateTaskList();
    updateMetrics();

    // Add some initial logs
    addLog('success', 'Cloud agent started successfully');
    addLog('info', 'Connected to vault sync service');
    addLog('info', 'Loaded 4 pending tasks from queue');
}

// ============================================
// Utility Functions
// ============================================
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function capitalizeFirst(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
}
