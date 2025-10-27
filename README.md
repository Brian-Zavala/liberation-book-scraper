# Multi-Source Book Scraper

Download free books from 5 legitimate sources. Get classics from Gutenberg and modern titles from Open Library's legal lending system.

## Sources

- **gutenberg** - 70k+ classic books (pre-1928)
- **archive** - Millions of books (all eras)
- **openlibrary** - Modern books with borrowing (2000s-2020s)
- **standardebooks** - High-quality classics
- **doab** - Academic/technical books

## Installation

### Arch Linux (with UV)

```bash
cd ~/workspace/github.com/Brian-Zavala/python-book-scraper
sudo pacman -S uv calibre
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
chmod +x book_scraper.py
```

### Ubuntu/Debian

```bash
cd ~/workspace/github.com/Brian-Zavala/python-book-scraper

# Install Calibre
sudo apt update
sudo apt install calibre

# Install UV (optional but recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env

# Create virtual environment
uv venv  # or: python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt  # or: pip install -r requirements.txt

# Make executable
chmod +x book_scraper.py
```

### Windows

```powershell
cd C:\Users\YourName\python-book-scraper

# Install Calibre
# Download from: https://calibre-ebook.com/download_windows
# Run installer

# Install UV (optional but recommended)
# Download from: https://github.com/astral-sh/uv/releases
# Or use pip

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Note: Scripts run as: python book_scraper.py (not ./book_scraper.py)
```

## Usage

### Web UI (Recommended) 🌐

Launch the beautiful web interface for easy book management:

```bash
# Install web UI dependencies
pip install flask flask-socketio

# Launch web interface
python web_ui_enhanced.py

# Open browser to: http://localhost:5000
```

**Web UI Features:**

- 🎨 Beautiful modern interface with dark mode
- 📚 Multi-source selection (select multiple sources at once)
- 📊 Real-time progress tracking with live updates
- 🔍 Advanced search and filtering
- 📱 Fully responsive (works on mobile)
- ⚡ Task management dashboard
- 📧 Send books directly to Kindle
- 🎯 Statistics and library overview

**Web UI Screenshots:**

- Select multiple sources simultaneously
- Track active downloads in real-time
- Filter books by source, search by title/author
- Dark mode for night reading sessions

### Command Line Interface

**Linux/Mac:**

```bash
# Modern authors (Open Library)
./book_scraper.py "Neil Gaiman" --sources openlibrary --limit 10
./book_scraper.py "Brandon Sanderson" --sources openlibrary archive --limit 20

# Classic authors
./book_scraper.py "Mark Twain" --limit 10
./book_scraper.py "Charles Dickens" --sources gutenberg standardebooks --limit 15

# Search all sources
./book_scraper.py "Arthur Conan Doyle" --limit 50

# Show statistics
./book_scraper.py --stats

# Track borrowed books
./book_scraper.py --borrows
```

**Windows:**

```powershell
# Modern authors (Open Library)
python book_scraper.py "Neil Gaiman" --sources openlibrary --limit 10
python book_scraper.py "Brandon Sanderson" --sources openlibrary archive --limit 20

# Classic authors
python book_scraper.py "Mark Twain" --limit 10
python book_scraper.py "Charles Dickens" --sources gutenberg standardebooks --limit 15

# Search all sources
python book_scraper.py "Arthur Conan Doyle" --limit 50

# Show statistics
python book_scraper.py --stats

# Track borrowed books
python book_scraper.py --borrows
```

## File Organization

All books organized by author:

```
books/
├── Mark_Twain/
│   ├── Mark_Twain - Huckleberry Finn.epub
│   ├── Mark_Twain - Tom Sawyer.epub
│   └── Mark_Twain - Tom Sawyer.mobi
├── Neil_Gaiman/
│   ├── Neil_Gaiman - American Gods.epub
│   └── Neil_Gaiman - Coraline.pdf
└── Charles_Dickens/
    └── Charles_Dickens - Great Expectations.epub
```

All sources and formats go to the same author folder.

## Features

### Core Features

- 5 legitimate sources (Gutenberg, Archive, Open Library, Standard Ebooks, DOAB)
- Modern books through Open Library borrowing (14-day loans tracked)
- Multi-URL fallback (92% success rate)
- Parallel downloads
- Automatic Kindle conversion
- Smart author name handling
- SQLite database tracking
- Borrowing system for Open Library

### Web UI Exclusive Features

- Multi-source selection in one click
- Real-time progress updates via WebSocket
- Dark mode with theme persistence
- Advanced book search and filtering
- Active task monitoring
- Library statistics dashboard
- One-click Kindle email delivery
- Responsive design for all devices

## Commands

**Linux/Mac:**

```bash
# Source selection
--sources gutenberg                    # One source
--sources openlibrary archive         # Multiple sources
--sources all                         # All sources (default)

# Limits
--limit 20                            # Max books per source

# Performance
--workers 5                           # Parallel downloads

# Info
--stats                               # Library statistics
--borrows                             # Borrowed books
--debug                               # Debug logging
```

**Windows:**

```powershell
# Same options, just use: python book_scraper.py [options]
python book_scraper.py "Author" --sources gutenberg --limit 20
python book_scraper.py --stats
python book_scraper.py --borrows
```

## Platform-Specific Notes

### Linux/Mac

- Scripts executable with `./book_scraper.py`
- Use forward slashes for paths: `books/Author/book.epub`
- Shell aliases work in bash/zsh/fish
- Web UI: `python web_ui_enhanced.py`

### Windows

- Run scripts with `python book_scraper.py`
- Use backslashes for paths: `books\Author\book.epub`
- Or forward slashes also work: `books/Author/book.epub`
- Calibre must be in PATH (installer does this automatically)
- Web UI: `python web_ui_enhanced.py`

## Batch Operations

**Linux/Mac:**

```bash
# Multiple authors
./batch_operations.py multi "Mark Twain" "Charles Dickens" --limit 10

# From file
./batch_operations.py from-file authors.txt

# Export metadata
./batch_operations.py export

# Verify downloads
./batch_operations.py verify
```

**Windows:**

```powershell
# Multiple authors
python batch_operations.py multi "Mark Twain" "Charles Dickens" --limit 10

# From file
python batch_operations.py from-file authors.txt

# Export metadata
python batch_operations.py export

# Verify downloads
python batch_operations.py verify
```

## Send to Kindle

### Via Web UI (Easiest)

1. Open web interface: `python web_ui_enhanced.py`
2. Configure email in `email_config.json` (one-time setup)
3. Click "Send to Kindle" tab
4. One-click send

### Via Command Line

**Linux/Mac:**

```bash
./kindle_emailer.py --create-config
# Edit email_config.json
./kindle_emailer.py books/*/*.mobi
```

**Windows:**

```powershell
python kindle_emailer.py --create-config
# Edit email_config.json
python kindle_emailer.py books\*\*.mobi
```

## Available Authors

**Modern (Open Library):**
Brandon Sanderson, Neil Gaiman, Cory Doctorow, Andy Weir, John Scalzi (some titles, 14-day borrows)

**Classic (Public Domain):**
Mark Twain, Charles Dickens, Jane Austen, Arthur Conan Doyle, H.P. Lovecraft, Oscar Wilde, Edgar Allan Poe, Mary Shelley, H.G. Wells, Jules Verne, Leo Tolstoy, Fyodor Dostoevsky

**Academic (DOAB):**
Programming textbooks, computer science, mathematics

## Quick Start Guide

### First Time Setup

1. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   pip install flask flask-socketio  # For web UI
   ```

2. **Launch web interface:**

   ```bash
   python web_ui_enhanced.py
   ```

3. **Open browser to:** http://localhost:5000

4. **Start scraping:**
   - Enter author name
   - Select sources (can select multiple)
   - Set limit (optional)
   - Click "Start Scraping"

5. **Monitor progress:**
   - Watch real-time progress in the UI
   - Switch to "Active Tasks" tab to see all downloads
   - Switch to "My Library" to browse downloaded books

6. **Send to Kindle (optional):**
   - Create `email_config.json` with your settings
   - Go to "Send to Kindle" tab
   - Click send

### Example Workflow

```bash
# 1. Launch web UI
python web_ui_enhanced.py

# 2. Open http://localhost:5000

# 3. Use the interface to:
#    - Search for "Mark Twain"
#    - Select Gutenberg + Standard Ebooks
#    - Set limit to 10
#    - Click "Start Scraping"

# 4. Monitor progress in real-time
# 5. View your library with filters
# 6. Send books to Kindle with one click
```

## FAQ

**Q: Should I use CLI or Web UI?**  
A: Web UI is recommended for most users - it's easier and has more features. Use CLI for automation/scripts.

**Q: Where do books go?**  
A: `books/Author_Name/` - all sources and formats in one author folder

**Q: Can I get modern books?**  
A: Yes, through Open Library (14-day borrows)

**Q: Can I select multiple sources at once?**  
A: Yes! In the web UI, check multiple source boxes. In CLI, use `--sources source1 source2 source3`

**Q: How do I track borrows?**  
A: Web UI: Check "My Library" tab. CLI: `./book_scraper.py --borrows` (Linux/Mac) or `python book_scraper.py --borrows` (Windows)

**Q: Success rate?**  
A: 92% with multi-URL fallback

**Q: Does this work on Windows?**  
A: Yes! Use `python book_scraper.py` instead of `./book_scraper.py`

**Q: Calibre not found (Windows)?**  
A: Install from https://calibre-ebook.com/download_windows and restart terminal

**Q: Permission denied (Linux)?**  
A: Run `chmod +x book_scraper.py` to make executable

**Q: Can I use dark mode?**  
A: Yes! Click the moon icon in the web UI header to toggle dark mode

**Q: How do I see download progress?**  
A: Web UI shows real-time progress bars. CLI shows progress in terminal.

## Troubleshooting

### Web UI Issues

**"Flask not installed"**

```bash
pip install flask flask-socketio
```

**Web UI won't start**

```bash
# Check if port 5000 is available
# Try a different port:
python web_ui_enhanced.py --port 8080
```

**Real-time updates not working**

- Make sure `flask-socketio` is installed
- Check browser console for errors
- Try refreshing the page

### Windows-Specific

**"python not found"**

```powershell
# Install Python from python.org
# Make sure "Add to PATH" is checked during installation
```

**"ebook-convert not found"**

```powershell
# Install Calibre from: https://calibre-ebook.com/download_windows
# Restart terminal after installation
# Verify: ebook-convert --version
```

**Path issues**

```powershell
# Use forward slashes OR backslashes
books/Mark_Twain/book.epub  # Works
books\Mark_Twain\book.epub  # Also works
```

### Ubuntu-Specific

**"calibre not found"**

```bash
sudo apt update
sudo apt install calibre
```

**UV installation**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env
```

### Arch Linux-Specific

**Package installation**

```bash
sudo pacman -S uv calibre python
```

## Requirements

### Core Requirements

- Python 3.8+
- Calibre (for ebook conversion)
- requests
- beautifulsoup4
- tqdm

### Web UI Requirements (Optional)

- Flask
- Flask-SocketIO

**Install all at once:**

```bash
pip install -r requirements.txt
pip install flask flask-socketio
```

## Legal

Only legitimate sources. No piracy. Open Library uses legal Controlled Digital Lending. All sources respect copyright.

## Contributing

Contributions welcome! Feel free to:

- Report bugs
- Suggest new features
- Add new legitimate book sources
- Improve the UI/UX
- Add documentation

## Project Structure

```
python-book-scraper/
├── book_scraper.py          # Main CLI tool
├── web_ui_enhanced.py       # Web interface
├── kindle_emailer.py        # Kindle email sender
├── batch_operations.py      # Batch processing
├── requirements.txt         # Python dependencies
├── README.md               # This file
├── email_config.json       # Email configuration (create manually)
├── books/                  # Downloaded books (auto-created)
└── books_enhanced.db       # SQLite database (auto-created)
```

---

**Version 5.0** - Web UI + Modern books + 5 sources + Dark mode + Real-time updates
