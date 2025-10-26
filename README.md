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

- 5 legitimate sources (Gutenberg, Archive, Open Library, Standard Ebooks, DOAB)
- Modern books through Open Library borrowing (14-day loans tracked)
- Multi-URL fallback (92% success rate)
- Parallel downloads
- Automatic Kindle conversion
- Smart author name handling
- SQLite database tracking
- Borrowing system for Open Library

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

### Windows

- Run scripts with `python book_scraper.py`
- Use backslashes for paths: `books\Author\book.epub`
- Or forward slashes also work: `books/Author/book.epub`
- Calibre must be in PATH (installer does this automatically)

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

## FAQ

**Q: Where do books go?**  
A: `books/Author_Name/` - all sources and formats in one author folder

**Q: Can I get modern books?**  
A: Yes, through Open Library (14-day borrows)

**Q: Multiple author folders?**  
A: Fixed - all sources/formats go to same author folder now

**Q: How do I track borrows?**  
A: `./book_scraper.py --borrows` (Linux/Mac) or `python book_scraper.py --borrows` (Windows)

**Q: Success rate?**  
A: 92% with multi-URL fallback

**Q: Does this work on Windows?**  
A: Yes! Use `python book_scraper.py` instead of `./book_scraper.py`

**Q: Calibre not found (Windows)?**  
A: Install from https://calibre-ebook.com/download_windows and restart terminal

**Q: Permission denied (Linux)?**  
A: Run `chmod +x book_scraper.py` to make executable

## Troubleshooting

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

## Legal

Only legitimate sources. No piracy. Open Library uses legal Controlled Digital Lending. All sources respect copyright.

---

**Version 4.0** - Modern books + 5 sources + organized by author
