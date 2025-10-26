#!/usr/bin/env python3
"""
Simple web UI for book scraper using Flask
Run with: python web_ui.py
Then open: http://localhost:5000
"""

try:
    from flask import Flask, render_template_string, request, jsonify, send_from_directory
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    print("Flask not installed. Install with: pip install flask")

from pathlib import Path
import json
import threading
from book_scraper import BookScraperCLI, BookDatabase
from kindle_emailer import KindleEmailer

app = Flask(__name__)

# Global state
scraper = BookScraperCLI()
current_task = None
task_status = {"status": "idle", "progress": 0, "message": ""}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Book Scraper</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 900px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 40px;
        }
        h1 {
            color: #333;
            margin-bottom: 30px;
            font-size: 32px;
            text-align: center;
        }
        .card {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 25px;
            margin-bottom: 25px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #555;
        }
        input, select {
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
            transition: border-color 0.3s;
        }
        input:focus, select:focus {
            outline: none;
            border-color: #667eea;
        }
        button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 14px 28px;
            border-radius: 6px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            width: 100%;
        }
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
        }
        button:active {
            transform: translateY(0);
        }
        button:disabled {
            background: #ccc;
            cursor: not-allowed;
            transform: none;
        }
        .status {
            margin-top: 20px;
            padding: 15px;
            border-radius: 6px;
            display: none;
        }
        .status.active { display: block; }
        .status.success { background: #d4edda; color: #155724; }
        .status.error { background: #f8d7da; color: #721c24; }
        .status.info { background: #d1ecf1; color: #0c5460; }
        .progress-bar {
            width: 100%;
            height: 8px;
            background: #e0e0e0;
            border-radius: 4px;
            overflow: hidden;
            margin-top: 10px;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            width: 0%;
            transition: width 0.3s;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }
        .stat-item {
            background: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            border: 2px solid #f0f0f0;
        }
        .stat-number {
            font-size: 32px;
            font-weight: bold;
            color: #667eea;
        }
        .stat-label {
            color: #666;
            margin-top: 8px;
            font-size: 14px;
        }
        .book-list {
            max-height: 400px;
            overflow-y: auto;
            margin-top: 15px;
        }
        .book-item {
            background: white;
            padding: 15px;
            border-radius: 6px;
            margin-bottom: 10px;
            border-left: 4px solid #667eea;
        }
        .book-title {
            font-weight: 600;
            color: #333;
        }
        .book-author {
            color: #666;
            font-size: 14px;
            margin-top: 5px;
        }
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        .tab {
            padding: 12px 24px;
            background: #f0f0f0;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 600;
            color: #666;
        }
        .tab.active {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .tab-content {
            display: none;
        }
        .tab-content.active {
            display: block;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📚 Book Scraper</h1>
        
        <div class="tabs">
            <button class="tab active" onclick="showTab('scrape')">Scrape Books</button>
            <button class="tab" onclick="showTab('library')">My Library</button>
            <button class="tab" onclick="showTab('send')">Send to Kindle</button>
        </div>
        
        <!-- Scrape Tab -->
        <div id="scrape-tab" class="tab-content active">
            <div class="card">
                <form id="scrape-form">
                    <div class="form-group">
                        <label>Author Name</label>
                        <input type="text" id="author" placeholder="e.g., Mark Twain" required>
                    </div>
                    
                    <div class="form-group">
                        <label>Source</label>
                        <select id="source">
                            <option value="gutenberg">Project Gutenberg</option>
                            <option value="archive">Internet Archive</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label>Limit (optional)</label>
                        <input type="number" id="limit" placeholder="Leave empty for all books" min="1">
                    </div>
                    
                    <button type="submit" id="scrape-btn">Start Scraping</button>
                </form>
                
                <div id="status" class="status"></div>
                <div class="progress-bar" id="progress-container" style="display:none;">
                    <div class="progress-fill" id="progress-bar"></div>
                </div>
            </div>
        </div>
        
        <!-- Library Tab -->
        <div id="library-tab" class="tab-content">
            <div class="card">
                <div class="stats" id="stats"></div>
                <div class="book-list" id="book-list"></div>
            </div>
        </div>
        
        <!-- Send Tab -->
        <div id="send-tab" class="tab-content">
            <div class="card">
                <p style="margin-bottom: 20px; color: #666;">
                    Configure email settings in <code>email_config.json</code> first.
                </p>
                <button onclick="sendToKindle()">Send Recent Books to Kindle</button>
                <div id="send-status" class="status"></div>
            </div>
        </div>
    </div>
    
    <script>
        function showTab(tabName) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            
            event.target.classList.add('active');
            document.getElementById(tabName + '-tab').classList.add('active');
            
            if (tabName === 'library') {
                loadLibrary();
            }
        }
        
        document.getElementById('scrape-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const author = document.getElementById('author').value;
            const source = document.getElementById('source').value;
            const limit = document.getElementById('limit').value;
            
            const btn = document.getElementById('scrape-btn');
            const status = document.getElementById('status');
            const progressContainer = document.getElementById('progress-container');
            const progressBar = document.getElementById('progress-bar');
            
            btn.disabled = true;
            btn.textContent = 'Scraping...';
            status.className = 'status active info';
            status.textContent = 'Starting scrape...';
            progressContainer.style.display = 'block';
            
            try {
                const response = await fetch('/api/scrape', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ author, source, limit: limit || null })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    status.className = 'status active success';
                    status.textContent = data.message;
                    progressBar.style.width = '100%';
                } else {
                    status.className = 'status active error';
                    status.textContent = 'Error: ' + data.message;
                }
            } catch (error) {
                status.className = 'status active error';
                status.textContent = 'Error: ' + error.message;
            } finally {
                btn.disabled = false;
                btn.textContent = 'Start Scraping';
            }
        });
        
        async function loadLibrary() {
            const response = await fetch('/api/stats');
            const data = await response.json();
            
            const statsHtml = `
                <div class="stat-item">
                    <div class="stat-number">${data.total}</div>
                    <div class="stat-label">Total Books</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">${data.downloaded}</div>
                    <div class="stat-label">Downloaded</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">${data.authors}</div>
                    <div class="stat-label">Authors</div>
                </div>
            `;
            document.getElementById('stats').innerHTML = statsHtml;
            
            const booksHtml = data.books.map(book => `
                <div class="book-item">
                    <div class="book-title">${book.title}</div>
                    <div class="book-author">by ${book.author} • ${book.source}</div>
                </div>
            `).join('');
            document.getElementById('book-list').innerHTML = booksHtml || '<p>No books yet. Start scraping!</p>';
        }
        
        async function sendToKindle() {
            const status = document.getElementById('send-status');
            status.className = 'status active info';
            status.textContent = 'Sending books to Kindle...';
            
            try {
                const response = await fetch('/api/send-to-kindle', { method: 'POST' });
                const data = await response.json();
                
                if (data.success) {
                    status.className = 'status active success';
                    status.textContent = data.message;
                } else {
                    status.className = 'status active error';
                    status.textContent = 'Error: ' + data.message;
                }
            } catch (error) {
                status.className = 'status active error';
                status.textContent = 'Error: ' + error.message;
            }
        }
        
        // Load library on page load if on that tab
        if (window.location.hash === '#library') {
            showTab('library');
        }
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/scrape', methods=['POST'])
def scrape():
    data = request.json
    author = data.get('author')
    source = data.get('source', 'gutenberg')
    limit = data.get('limit')
    
    try:
        # Run in background thread
        def run_scrape():
            scraper.scrape_author(author, source, limit, convert=True)
        
        thread = threading.Thread(target=run_scrape)
        thread.start()
        
        # Wait a bit to see if it starts successfully
        thread.join(timeout=2)
        
        return jsonify({
            'success': True,
            'message': f'Started scraping books by {author}. Check the console for progress.'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/stats')
def stats():
    try:
        db = BookDatabase()
        books = db.get_all_books()
        db.close()
        
        authors = set(book['author'] for book in books)
        downloaded = sum(1 for book in books if book['downloaded'])
        
        # Get recent books
        recent = sorted(books, key=lambda x: x.get('downloaded_at', ''), reverse=True)[:20]
        
        return jsonify({
            'total': len(books),
            'downloaded': downloaded,
            'authors': len(authors),
            'books': [
                {
                    'title': book['title'],
                    'author': book['author'],
                    'source': book['source']
                }
                for book in recent
            ]
        })
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/api/send-to-kindle', methods=['POST'])
def send_to_kindle():
    try:
        emailer = KindleEmailer.from_config_file()
        if not emailer:
            return jsonify({
                'success': False,
                'message': 'Email not configured. Create email_config.json'
            })
        
        books_dir = Path("books")
        mobi_files = list(books_dir.glob("*.mobi"))[:5]  # Send 5 most recent
        
        if not mobi_files:
            return jsonify({
                'success': False,
                'message': 'No MOBI files found'
            })
        
        sent = emailer.send_books(mobi_files)
        
        return jsonify({
            'success': True,
            'message': f'Sent {sent} book(s) to Kindle'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/books/<path:filename>')
def download_book(filename):
    return send_from_directory('books', filename)


if __name__ == "__main__":
    if not FLASK_AVAILABLE:
        print("Please install Flask: pip install flask")
        exit(1)
    
    print("\n" + "="*60)
    print("📚 Book Scraper Web UI")
    print("="*60)
    print("\nStarting server on http://localhost:5000")
    print("Press Ctrl+C to stop\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
