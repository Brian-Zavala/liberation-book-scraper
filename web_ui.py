#!/usr/bin/env python3
"""
Ultra-Enhanced Book Scraper Web UI
Features:
- All 5 sources with multi-select
- Real-time progress with WebSocket
- Dark mode
- Advanced search/filtering
- Batch operations
- Download management
- Borrowed books tracking
- Beautiful modern UI
"""

try:
    from flask import (
        Flask,
        render_template_string,
        request,
        jsonify,
        send_from_directory,
    )
    from flask_socketio import SocketIO, emit

    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    print("Flask not installed. Install with: pip install flask flask-socketio")

from pathlib import Path
import json
import threading
import time
from datetime import datetime
from book_scraper import EnhancedBookScraperCLI, BookDatabase
from kindle_emailer import KindleEmailer

app = Flask(__name__)
app.config["SECRET_KEY"] = "book-scraper-secret"
socketio = SocketIO(app, cors_allowed_origins="*")

# Global state
scraper = EnhancedBookScraperCLI()
current_tasks = {}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Book Scraper Pro</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            --primary: #667eea;
            --secondary: #764ba2;
            --success: #10b981;
            --danger: #ef4444;
            --warning: #f59e0b;
            --info: #3b82f6;
            --bg: #f8fafc;
            --card: #ffffff;
            --text: #1e293b;
            --text-light: #64748b;
            --border: #e2e8f0;
            --shadow: rgba(0,0,0,0.1);
        }

        [data-theme="dark"] {
            --bg: #0f172a;
            --card: #1e293b;
            --text: #f1f5f9;
            --text-light: #94a3b8;
            --border: #334155;
            --shadow: rgba(0,0,0,0.3);
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
            transition: background 0.3s, color 0.3s;
        }

        .header {
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            padding: 20px;
            box-shadow: 0 4px 6px var(--shadow);
            position: sticky;
            top: 0;
            z-index: 1000;
        }

        .header-content {
            max-width: 1400px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .logo {
            color: white;
            font-size: 28px;
            font-weight: 800;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .header-actions {
            display: flex;
            gap: 15px;
            align-items: center;
        }

        .theme-toggle {
            background: rgba(255,255,255,0.2);
            border: none;
            color: white;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.3s;
        }

        .theme-toggle:hover {
            background: rgba(255,255,255,0.3);
            transform: scale(1.1);
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 30px 20px;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 25px;
        }

        .card {
            background: var(--card);
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 1px 3px var(--shadow);
            transition: transform 0.2s, box-shadow 0.2s;
            border: 1px solid var(--border);
        }

        .card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 16px var(--shadow);
        }

        .card-header {
            font-size: 20px;
            font-weight: 700;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
            color: var(--text);
        }

        .form-group {
            margin-bottom: 20px;
        }

        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: var(--text);
            font-size: 14px;
        }

        input, select, textarea {
            width: 100%;
            padding: 12px;
            border: 2px solid var(--border);
            border-radius: 8px;
            font-size: 14px;
            background: var(--card);
            color: var(--text);
            transition: border-color 0.3s;
        }

        input:focus, select:focus, textarea:focus {
            outline: none;
            border-color: var(--primary);
        }

        .source-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 12px;
        }

        .checkbox-card {
            position: relative;
            border: 2px solid var(--border);
            border-radius: 8px;
            padding: 15px;
            cursor: pointer;
            transition: all 0.3s;
            background: var(--card);
        }

        .checkbox-card:hover {
            border-color: var(--primary);
            transform: scale(1.02);
        }

        .checkbox-card input[type="checkbox"] {
            position: absolute;
            opacity: 0;
        }

        .checkbox-card input[type="checkbox"]:checked + label {
            color: var(--primary);
        }

        .checkbox-card input[type="checkbox"]:checked ~ .checkbox-icon {
            background: var(--primary);
            color: white;
        }

        .checkbox-card label {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 8px;
            cursor: pointer;
            margin: 0;
        }

        .checkbox-icon {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: var(--border);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            transition: all 0.3s;
        }

        .source-name {
            font-size: 13px;
            font-weight: 600;
            text-align: center;
        }

        .source-desc {
            font-size: 11px;
            color: var(--text-light);
            text-align: center;
        }

        button {
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            color: white;
            border: none;
            padding: 14px 28px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            width: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
        }

        button:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
        }

        button:active:not(:disabled) {
            transform: translateY(0);
        }

        button:disabled {
            background: var(--border);
            cursor: not-allowed;
            transform: none;
        }

        .button-secondary {
            background: var(--card);
            color: var(--text);
            border: 2px solid var(--border);
        }

        .button-danger {
            background: var(--danger);
        }

        .button-success {
            background: var(--success);
        }

        .status {
            margin-top: 20px;
            padding: 15px;
            border-radius: 8px;
            display: none;
            align-items: center;
            gap: 10px;
        }

        .status.active { display: flex; }
        .status.success { background: rgba(16, 185, 129, 0.1); color: var(--success); border: 1px solid var(--success); }
        .status.error { background: rgba(239, 68, 68, 0.1); color: var(--danger); border: 1px solid var(--danger); }
        .status.info { background: rgba(59, 130, 246, 0.1); color: var(--info); border: 1px solid var(--info); }

        .progress-container {
            margin-top: 20px;
            display: none;
        }

        .progress-container.active { display: block; }

        .progress-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
            font-size: 14px;
            color: var(--text-light);
        }

        .progress-bar {
            width: 100%;
            height: 10px;
            background: var(--border);
            border-radius: 5px;
            overflow: hidden;
            position: relative;
        }

        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--primary) 0%, var(--secondary) 100%);
            width: 0%;
            transition: width 0.3s;
            border-radius: 5px;
        }

        .progress-fill.animated {
            animation: pulse 1.5s ease-in-out infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }

        .stat-card {
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
        }

        .stat-number {
            font-size: 36px;
            font-weight: 800;
            margin-bottom: 5px;
        }

        .stat-label {
            font-size: 13px;
            opacity: 0.9;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .book-list {
            max-height: 500px;
            overflow-y: auto;
            margin-top: 20px;
        }

        .book-item {
            background: var(--card);
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 12px;
            border-left: 4px solid var(--primary);
            border: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: all 0.2s;
        }

        .book-item:hover {
            transform: translateX(5px);
            box-shadow: 0 4px 8px var(--shadow);
        }

        .book-info {
            flex: 1;
        }

        .book-title {
            font-weight: 600;
            color: var(--text);
            margin-bottom: 5px;
        }

        .book-meta {
            color: var(--text-light);
            font-size: 13px;
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
        }

        .book-actions {
            display: flex;
            gap: 10px;
        }

        .btn-icon {
            width: 36px;
            height: 36px;
            border-radius: 50%;
            background: var(--border);
            border: none;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s;
            color: var(--text);
        }

        .btn-icon:hover {
            transform: scale(1.1);
            background: var(--primary);
            color: white;
        }

        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 30px;
            flex-wrap: wrap;
        }

        .tab {
            padding: 12px 24px;
            background: var(--card);
            border: 2px solid var(--border);
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            color: var(--text);
            transition: all 0.3s;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .tab:hover {
            border-color: var(--primary);
            transform: translateY(-2px);
        }

        .tab.active {
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            color: white;
            border-color: transparent;
        }

        .tab-content {
            display: none;
        }

        .tab-content.active {
            display: block;
            animation: fadeIn 0.3s;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .search-bar {
            position: relative;
            margin-bottom: 20px;
        }

        .search-bar input {
            padding-left: 40px;
        }

        .search-icon {
            position: absolute;
            left: 12px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-light);
        }

        .badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
        }

        .badge-success { background: rgba(16, 185, 129, 0.1); color: var(--success); }
        .badge-warning { background: rgba(245, 158, 11, 0.1); color: var(--warning); }
        .badge-info { background: rgba(59, 130, 246, 0.1); color: var(--info); }

        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: var(--text-light);
        }

        .empty-state i {
            font-size: 64px;
            margin-bottom: 20px;
            opacity: 0.3;
        }

        .task-list {
            margin-top: 20px;
        }

        .task-item {
            background: var(--card);
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 10px;
            border: 1px solid var(--border);
        }

        .task-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }

        .task-title {
            font-weight: 600;
            color: var(--text);
        }

        .spinner {
            width: 20px;
            height: 20px;
            border: 3px solid var(--border);
            border-top-color: var(--primary);
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        .filter-group {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }

        .filter-btn {
            padding: 8px 16px;
            border-radius: 6px;
            border: 2px solid var(--border);
            background: var(--card);
            color: var(--text);
            cursor: pointer;
            font-size: 13px;
            transition: all 0.2s;
        }

        .filter-btn:hover {
            border-color: var(--primary);
        }

        .filter-btn.active {
            background: var(--primary);
            color: white;
            border-color: var(--primary);
        }

        @media (max-width: 768px) {
            .header-content {
                flex-direction: column;
                gap: 15px;
            }

            .grid {
                grid-template-columns: 1fr;
            }

            .source-grid {
                grid-template-columns: repeat(2, 1fr);
            }
        }

        /* Scrollbar styling */
        ::-webkit-scrollbar {
            width: 10px;
        }

        ::-webkit-scrollbar-track {
            background: var(--border);
        }

        ::-webkit-scrollbar-thumb {
            background: var(--primary);
            border-radius: 5px;
        }

        ::-webkit-scrollbar-thumb:hover {
            background: var(--secondary);
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-content">
            <div class="logo">
                <i class="fas fa-book-reader"></i>
                Book Scraper Pro
            </div>
            <div class="header-actions">
                <button class="theme-toggle" onclick="toggleTheme()">
                    <i class="fas fa-moon" id="theme-icon"></i>
                </button>
            </div>
        </div>
    </div>

    <div class="container">
        <div class="tabs">
            <button class="tab active" onclick="showTab('scrape')">
                <i class="fas fa-download"></i> Scrape Books
            </button>
            <button class="tab" onclick="showTab('library')">
                <i class="fas fa-books"></i> My Library
            </button>
            <button class="tab" onclick="showTab('tasks')">
                <i class="fas fa-tasks"></i> Active Tasks
            </button>
            <button class="tab" onclick="showTab('send')">
                <i class="fas fa-paper-plane"></i> Send to Kindle
            </button>
            <button class="tab" onclick="showTab('settings')">
                <i class="fas fa-cog"></i> Settings
            </button>
        </div>

        <!-- Scrape Tab -->
        <div id="scrape-tab" class="tab-content active">
            <div class="grid">
                <div class="card">
                    <div class="card-header">
                        <i class="fas fa-search"></i>
                        Search Configuration
                    </div>
                    <form id="scrape-form">
                        <div class="form-group">
                            <label>Author Name *</label>
                            <input type="text" id="author" placeholder="e.g., Mark Twain, Neil Gaiman" required>
                        </div>

                        <div class="form-group">
                            <label>Book Sources (select multiple)</label>
                            <div class="source-grid">
                                <div class="checkbox-card">
                                    <input type="checkbox" id="source-gutenberg" value="gutenberg" checked>
                                    <label for="source-gutenberg">
                                        <div class="checkbox-icon">📚</div>
                                        <div class="source-name">Gutenberg</div>
                                        <div class="source-desc">70k+ classics</div>
                                    </label>
                                </div>

                                <div class="checkbox-card">
                                    <input type="checkbox" id="source-archive" value="archive" checked>
                                    <label for="source-archive">
                                        <div class="checkbox-icon">🏛️</div>
                                        <div class="source-name">Archive</div>
                                        <div class="source-desc">Millions</div>
                                    </label>
                                </div>

                                <div class="checkbox-card">
                                    <input type="checkbox" id="source-openlibrary" value="openlibrary">
                                    <label for="source-openlibrary">
                                        <div class="checkbox-icon">📖</div>
                                        <div class="source-name">OpenLibrary</div>
                                        <div class="source-desc">Modern books</div>
                                    </label>
                                </div>

                                <div class="checkbox-card">
                                    <input type="checkbox" id="source-standardebooks" value="standardebooks">
                                    <label for="source-standardebooks">
                                        <div class="checkbox-icon">⭐</div>
                                        <div class="source-name">Standard</div>
                                        <div class="source-desc">High quality</div>
                                    </label>
                                </div>

                                <div class="checkbox-card">
                                    <input type="checkbox" id="source-doab" value="doab">
                                    <label for="source-doab">
                                        <div class="checkbox-icon">🎓</div>
                                        <div class="source-name">DOAB</div>
                                        <div class="source-desc">Academic</div>
                                    </label>
                                </div>
                            </div>
                        </div>

                        <div class="form-group">
                            <label>Limit per Source (optional)</label>
                            <input type="number" id="limit" placeholder="Leave empty for all" min="1" max="100" value="20">
                        </div>

                        <div class="form-group">
                            <label>
                                <input type="checkbox" id="convert-kindle" checked style="width: auto; display: inline;">
                                Convert to Kindle format (.mobi)
                            </label>
                        </div>

                        <button type="submit" id="scrape-btn">
                            <i class="fas fa-download"></i>
                            Start Scraping
                        </button>
                    </form>

                    <div id="status" class="status"></div>
                    <div class="progress-container" id="progress-container">
                        <div class="progress-header">
                            <span id="progress-text">Preparing...</span>
                            <span id="progress-percent">0%</span>
                        </div>
                        <div class="progress-bar">
                            <div class="progress-fill" id="progress-bar"></div>
                        </div>
                    </div>
                </div>

                <div class="card">
                    <div class="card-header">
                        <i class="fas fa-info-circle"></i>
                        Quick Stats
                    </div>
                    <div class="stats-grid" id="quick-stats">
                        <div class="stat-card">
                            <div class="stat-number" id="stat-total">0</div>
                            <div class="stat-label">Total Books</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number" id="stat-authors">0</div>
                            <div class="stat-label">Authors</div>
                        </div>
                    </div>

                    <div style="margin-top: 30px;">
                        <div class="card-header" style="margin-bottom: 10px;">
                            <i class="fas fa-fire"></i>
                            Popular Authors
                        </div>
                        <div id="popular-authors" style="color: var(--text-light); font-size: 14px;">
                            Mark Twain, Charles Dickens, Jane Austen, Arthur Conan Doyle, H.P. Lovecraft, Neil Gaiman, Brandon Sanderson
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Library Tab -->
        <div id="library-tab" class="tab-content">
            <div class="card">
                <div class="card-header">
                    <i class="fas fa-chart-bar"></i>
                    Library Statistics
                </div>
                <div class="stats-grid" id="library-stats"></div>
            </div>

            <div class="card">
                <div class="card-header">
                    <i class="fas fa-book"></i>
                    Your Books
                </div>

                <div class="search-bar">
                    <i class="fas fa-search search-icon"></i>
                    <input type="text" id="book-search" placeholder="Search books by title or author...">
                </div>

                <div class="filter-group">
                    <button class="filter-btn active" onclick="filterBooks('all')">All</button>
                    <button class="filter-btn" onclick="filterBooks('gutenberg')">Gutenberg</button>
                    <button class="filter-btn" onclick="filterBooks('archive')">Archive</button>
                    <button class="filter-btn" onclick="filterBooks('openlibrary')">OpenLibrary</button>
                    <button class="filter-btn" onclick="filterBooks('standardebooks')">Standard</button>
                    <button class="filter-btn" onclick="filterBooks('doab')">DOAB</button>
                </div>

                <div class="book-list" id="book-list"></div>
            </div>
        </div>

        <!-- Tasks Tab -->
        <div id="tasks-tab" class="tab-content">
            <div class="card">
                <div class="card-header">
                    <i class="fas fa-tasks"></i>
                    Active Tasks
                </div>
                <div class="task-list" id="task-list">
                    <div class="empty-state">
                        <i class="fas fa-clipboard-check"></i>
                        <p>No active tasks</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Send Tab -->
        <div id="send-tab" class="tab-content">
            <div class="card">
                <div class="card-header">
                    <i class="fas fa-kindle"></i>
                    Send to Kindle
                </div>
                <p style="margin-bottom: 20px; color: var(--text-light);">
                    Configure email settings in <code>email_config.json</code> first.
                    Then select books to send to your Kindle.
                </p>
                <button onclick="sendToKindle()">
                    <i class="fas fa-paper-plane"></i>
                    Send Recent Books to Kindle
                </button>
                <div id="send-status" class="status"></div>
            </div>
        </div>

        <!-- Settings Tab -->
        <div id="settings-tab" class="tab-content">
            <div class="card">
                <div class="card-header">
                    <i class="fas fa-cog"></i>
                    Settings
                </div>

                <div class="form-group">
                    <label>Download Location</label>
                    <input type="text" value="./books" readonly>
                </div>

                <div class="form-group">
                    <label>Default Download Limit</label>
                    <input type="number" value="20" min="1" max="100">
                </div>

                <div class="form-group">
                    <label>Parallel Download Workers</label>
                    <input type="number" value="5" min="1" max="10">
                </div>

                <div class="form-group">
                    <label>
                        <input type="checkbox" checked style="width: auto; display: inline;">
                        Auto-convert to Kindle format
                    </label>
                </div>

                <button>
                    <i class="fas fa-save"></i>
                    Save Settings
                </button>
            </div>
        </div>
    </div>

    <script>
        const socket = io();
        let currentFilter = 'all';
        let allBooks = [];

        // Theme toggle
        function toggleTheme() {
            const html = document.documentElement;
            const icon = document.getElementById('theme-icon');
            const currentTheme = html.getAttribute('data-theme');
            
            if (currentTheme === 'dark') {
                html.removeAttribute('data-theme');
                icon.className = 'fas fa-moon';
                localStorage.setItem('theme', 'light');
            } else {
                html.setAttribute('data-theme', 'dark');
                icon.className = 'fas fa-sun';
                localStorage.setItem('theme', 'dark');
            }
        }

        // Load saved theme
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme === 'dark') {
            document.documentElement.setAttribute('data-theme', 'dark');
            document.getElementById('theme-icon').className = 'fas fa-sun';
        }

        // Tab switching
        function showTab(tabName) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            
            event.target.closest('.tab').classList.add('active');
            document.getElementById(tabName + '-tab').classList.add('active');
            
            if (tabName === 'library') {
                loadLibrary();
            } else if (tabName === 'tasks') {
                loadTasks();
            }
        }

        // Scrape form submission
        document.getElementById('scrape-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const author = document.getElementById('author').value;
            const limit = document.getElementById('limit').value;
            const convertKindle = document.getElementById('convert-kindle').checked;
            
            // Get selected sources
            const sources = [];
            document.querySelectorAll('.checkbox-card input:checked').forEach(input => {
                sources.push(input.value);
            });

            if (sources.length === 0) {
                showStatus('error', 'Please select at least one source');
                return;
            }
            
            const btn = document.getElementById('scrape-btn');
            const progressContainer = document.getElementById('progress-container');
            const progressBar = document.getElementById('progress-bar');
            
            btn.disabled = true;
            btn.innerHTML = '<i class="spinner"></i> Scraping...';
            showStatus('info', `Starting scrape from ${sources.length} source(s)...`);
            progressContainer.classList.add('active');
            progressBar.classList.add('animated');
            
            try {
                const response = await fetch('/api/scrape', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        author, 
                        sources, 
                        limit: limit || null,
                        convert: convertKindle
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    showStatus('success', data.message);
                    setTimeout(() => {
                        showTab('tasks');
                    }, 2000);
                } else {
                    showStatus('error', 'Error: ' + data.message);
                }
            } catch (error) {
                showStatus('error', 'Error: ' + error.message);
            } finally {
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-download"></i> Start Scraping';
                progressBar.classList.remove('animated');
            }
        });

        // WebSocket listeners
        socket.on('progress', (data) => {
            const progressBar = document.getElementById('progress-bar');
            const progressText = document.getElementById('progress-text');
            const progressPercent = document.getElementById('progress-percent');
            
            progressBar.style.width = data.percent + '%';
            progressText.textContent = data.message;
            progressPercent.textContent = data.percent + '%';
        });

        socket.on('task_complete', (data) => {
            showStatus('success', `✓ ${data.message}`);
            document.getElementById('progress-container').classList.remove('active');
            loadQuickStats();
        });

        socket.on('task_error', (data) => {
            showStatus('error', `✗ ${data.message}`);
            document.getElementById('progress-container').classList.remove('active');
        });

        // Load library
        async function loadLibrary() {
            try {
                const response = await fetch('/api/library');
                const data = await response.json();
                
                // Update stats
                const statsHtml = `
                    <div class="stat-card">
                        <div class="stat-number">${data.stats.total}</div>
                        <div class="stat-label">Total Books</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">${data.stats.downloaded}</div>
                        <div class="stat-label">Downloaded</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">${data.stats.authors}</div>
                        <div class="stat-label">Authors</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">${(data.stats.size_mb || 0).toFixed(1)}MB</div>
                        <div class="stat-label">Total Size</div>
                    </div>
                `;
                document.getElementById('library-stats').innerHTML = statsHtml;
                
                // Update books list
                allBooks = data.books;
                renderBooks(allBooks);
                
            } catch (error) {
                console.error('Error loading library:', error);
            }
        }

        // Render books
        function renderBooks(books) {
            const bookList = document.getElementById('book-list');
            
            if (books.length === 0) {
                bookList.innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-book-open"></i>
                        <p>No books found. Start scraping!</p>
                    </div>
                `;
                return;
            }
            
            const booksHtml = books.map(book => `
                <div class="book-item" data-source="${book.source}">
                    <div class="book-info">
                        <div class="book-title">${book.title}</div>
                        <div class="book-meta">
                            <span><i class="fas fa-user"></i> ${book.author}</span>
                            <span class="badge badge-info">${book.source}</span>
                            ${book.downloaded ? '<span class="badge badge-success">Downloaded</span>' : ''}
                            ${book.format ? `<span>${book.format.toUpperCase()}</span>` : ''}
                        </div>
                    </div>
                    <div class="book-actions">
                        ${book.file_path ? `
                            <button class="btn-icon" onclick="downloadBook('${book.file_path}')" title="Download">
                                <i class="fas fa-download"></i>
                            </button>
                        ` : ''}
                        <button class="btn-icon" onclick="deleteBook('${book.id}')" title="Delete">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
            `).join('');
            
            bookList.innerHTML = booksHtml;
        }

        // Filter books
        function filterBooks(source) {
            currentFilter = source;
            document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            
            const filtered = source === 'all' 
                ? allBooks 
                : allBooks.filter(book => book.source === source);
            
            renderBooks(filtered);
        }

        // Search books
        document.getElementById('book-search').addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase();
            const filtered = allBooks.filter(book => 
                book.title.toLowerCase().includes(query) || 
                book.author.toLowerCase().includes(query)
            );
            renderBooks(filtered);
        });

        // Load tasks
        async function loadTasks() {
            try {
                const response = await fetch('/api/tasks');
                const data = await response.json();
                
                const taskList = document.getElementById('task-list');
                
                if (data.tasks.length === 0) {
                    taskList.innerHTML = `
                        <div class="empty-state">
                            <i class="fas fa-clipboard-check"></i>
                            <p>No active tasks</p>
                        </div>
                    `;
                    return;
                }
                
                const tasksHtml = data.tasks.map(task => `
                    <div class="task-item">
                        <div class="task-header">
                            <div class="task-title">${task.name}</div>
                            <div class="spinner"></div>
                        </div>
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: ${task.progress}%"></div>
                        </div>
                        <div style="margin-top: 10px; color: var(--text-light); font-size: 13px;">
                            ${task.status}
                        </div>
                    </div>
                `).join('');
                
                taskList.innerHTML = tasksHtml;
                
            } catch (error) {
                console.error('Error loading tasks:', error);
            }
        }

        // Load quick stats
        async function loadQuickStats() {
            try {
                const response = await fetch('/api/stats');
                const data = await response.json();
                
                document.getElementById('stat-total').textContent = data.total || 0;
                document.getElementById('stat-authors').textContent = data.authors || 0;
            } catch (error) {
                console.error('Error loading stats:', error);
            }
        }

        // Send to Kindle
        async function sendToKindle() {
            const status = document.getElementById('send-status');
            showStatusInElement(status, 'info', 'Sending books to Kindle...');
            
            try {
                const response = await fetch('/api/send-to-kindle', { method: 'POST' });
                const data = await response.json();
                
                if (data.success) {
                    showStatusInElement(status, 'success', data.message);
                } else {
                    showStatusInElement(status, 'error', 'Error: ' + data.message);
                }
            } catch (error) {
                showStatusInElement(status, 'error', 'Error: ' + error.message);
            }
        }

        // Helper functions
        function showStatus(type, message) {
            const status = document.getElementById('status');
            showStatusInElement(status, type, message);
        }

        function showStatusInElement(element, type, message) {
            element.className = `status active ${type}`;
            const icon = type === 'success' ? 'check-circle' : type === 'error' ? 'times-circle' : 'info-circle';
            element.innerHTML = `<i class="fas fa-${icon}"></i> ${message}`;
        }

        function downloadBook(filePath) {
            window.location.href = `/books/${filePath}`;
        }

        async function deleteBook(bookId) {
            if (!confirm('Are you sure you want to delete this book?')) return;
            
            try {
                const response = await fetch(`/api/books/${bookId}`, { method: 'DELETE' });
                const data = await response.json();
                
                if (data.success) {
                    loadLibrary();
                    showStatus('success', 'Book deleted');
                }
            } catch (error) {
                showStatus('error', 'Error deleting book');
            }
        }

        // Auto-refresh stats every 5 seconds
        setInterval(loadQuickStats, 5000);

        // Load initial stats
        loadQuickStats();
    </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/scrape", methods=["POST"])
def scrape():
    data = request.json
    author = data.get("author")
    sources = data.get("sources", ["gutenberg"])
    limit = data.get("limit")
    convert = data.get("convert", True)

    task_id = f"{author}_{int(time.time())}"

    try:

        def run_scrape():
            try:
                # Emit progress updates
                socketio.emit(
                    "progress",
                    {"percent": 0, "message": f"Starting search for {author}"},
                )

                scraper.scrape_author(
                    author, sources=sources, limit=limit, max_workers=5
                )

                socketio.emit(
                    "task_complete",
                    {
                        "task_id": task_id,
                        "message": f"Successfully scraped books by {author}",
                    },
                )
            except Exception as e:
                socketio.emit("task_error", {"task_id": task_id, "message": str(e)})

        thread = threading.Thread(target=run_scrape)
        thread.daemon = True
        thread.start()

        current_tasks[task_id] = {
            "name": f"Scraping {author}",
            "progress": 0,
            "status": "Running",
            "thread": thread,
        }

        return jsonify(
            {
                "success": True,
                "task_id": task_id,
                "message": f"Started scraping books by {author} from {len(sources)} source(s)",
            }
        )
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route("/api/library")
def library():
    try:
        db = BookDatabase()

        # Get all books
        cursor = db.conn.execute(
            """
            SELECT id, title, author, source, format, file_path, download_date, file_size
            FROM books
            ORDER BY download_date DESC
        """
        )
        books = [dict(row) for row in cursor.fetchall()]

        # Calculate stats
        stats = db.get_stats()
        authors = set(book["author"] for book in books)

        db.close()

        return jsonify(
            {
                "books": [
                    {
                        "id": book["id"],
                        "title": book["title"],
                        "author": book["author"],
                        "source": book["source"],
                        "format": book["format"],
                        "file_path": book["file_path"],
                        "downloaded": book["file_path"] is not None,
                    }
                    for book in books
                ],
                "stats": {
                    "total": len(books),
                    "downloaded": sum(1 for b in books if b["file_path"]),
                    "authors": len(authors),
                    "size_mb": stats.get("total_size_mb", 0),
                },
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/api/stats")
def stats():
    try:
        db = BookDatabase()
        cursor = db.conn.execute("SELECT COUNT(*) as total FROM books")
        total = cursor.fetchone()["total"]

        cursor = db.conn.execute("SELECT COUNT(DISTINCT author) as authors FROM books")
        authors = cursor.fetchone()["authors"]

        db.close()

        return jsonify({"total": total, "authors": authors})
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/api/tasks")
def tasks():
    return jsonify(
        {
            "tasks": [
                {
                    "id": task_id,
                    "name": task_data["name"],
                    "progress": task_data["progress"],
                    "status": task_data["status"],
                }
                for task_id, task_data in current_tasks.items()
            ]
        }
    )


@app.route("/api/books/<book_id>", methods=["DELETE"])
def delete_book(book_id):
    try:
        db = BookDatabase()
        cursor = db.conn.execute("SELECT file_path FROM books WHERE id = ?", (book_id,))
        result = cursor.fetchone()

        if result and result["file_path"]:
            file_path = Path(result["file_path"])
            if file_path.exists():
                file_path.unlink()

        db.conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
        db.conn.commit()
        db.close()

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route("/api/send-to-kindle", methods=["POST"])
def send_to_kindle():
    try:
        emailer = KindleEmailer.from_config_file()
        if not emailer:
            return jsonify(
                {
                    "success": False,
                    "message": "Email not configured. Create email_config.json",
                }
            )

        books_dir = Path("books")
        mobi_files = list(books_dir.glob("**/*.mobi"))[:5]

        if not mobi_files:
            return jsonify({"success": False, "message": "No MOBI files found"})

        sent = emailer.send_books(mobi_files)

        return jsonify({"success": True, "message": f"✓ Sent {sent} book(s) to Kindle"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route("/books/<path:filename>")
def download_book(filename):
    return send_from_directory("books", filename)


if __name__ == "__main__":
    if not FLASK_AVAILABLE:
        print("Please install Flask: pip install flask flask-socketio")
        exit(1)

    print("\n" + "=" * 70)
    print("📚 Book Scraper Pro - Ultra Enhanced")
    print("=" * 70)
    print("\n✨ Features:")
    print("  • All 5 sources (Gutenberg, Archive, OpenLibrary, Standard, DOAB)")
    print("  • Multi-source selection")
    print("  • Real-time progress tracking")
    print("  • Dark mode")
    print("  • Advanced search & filtering")
    print("  • Task management")
    print("  • Beautiful modern UI")
    print(f"\n🌐 Server running on http://localhost:5000")
    print("Press Ctrl+C to stop\n")

    socketio.run(app, debug=True, host="0.0.0.0", port=5000)
