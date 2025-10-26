# Multi-Source Book Scraper for Kindle

Scrape free, public domain books from multiple sources and automatically convert them for Kindle.

## Features

- ✅ Multiple sources (Project Gutenberg, Archive.org)
- ✅ Parallel downloads with progress bars
- ✅ Automatic Kindle format conversion (MOBI)
- ✅ SQLite database to track downloads
- ✅ Metadata extraction (title, author, subjects, year)
- ✅ Email books directly to Kindle
- ✅ Duplicate detection
- ✅ Resume interrupted downloads
- ✅ Proper error handling and retry logic

## Installation

```bash
# Clone or download the files
cd ~/book-scraper

# Install Python dependencies
pip install -r requirements.txt

# Install Calibre for format conversion (Arch Linux)
sudo pacman -S calibre

# Make scripts executable
chmod +x book_scraper.py kindle_emailer.py
```

## Quick Start

### 1. Scrape Books

```bash
# Download all Mark Twain books from Gutenberg
./book_scraper.py "Mark Twain"

# Download from Archive.org with a limit
./book_scraper.py "Edgar Allan Poe" --source archive --limit 10

# Download without converting to MOBI
./book_scraper.py "Jane Austen" --no-convert

# Show statistics
./book_scraper.py --stats "Mark Twain"
```

### 2. Send to Kindle

```bash
# Create email configuration
./kindle_emailer.py --create-config

# Edit email_config.json with your credentials
# For Gmail: Use an App Password (https://myaccount.google.com/apppasswords)
# Find your Kindle email in Amazon account settings

# Send a single book
./kindle_emailer.py books/Mark_Twain_-_Huckleberry_Finn.mobi

# Send multiple books
./kindle_emailer.py books/*.mobi

# Send with custom batch size (wait 60s between batches)
./kindle_emailer.py books/*.mobi --batch-size 3
```

## Usage Examples

### Example 1: Complete Workflow

```bash
# 1. Scrape and convert
./book_scraper.py "H.G. Wells" --limit 5

# 2. Send to Kindle
./kindle_emailer.py books/*.mobi
```

### Example 2: Using as Python Library

```python
from book_scraper import BookScraperCLI, GutenbergScraper, ArchiveScraper, BookDownloader
from pathlib import Path

# Initialize
cli = BookScraperCLI()

# Search and download
cli.scrape_author("Charles Dickens", source="gutenberg", limit=3)

# Show stats
cli.show_stats()

# Manual download
scraper = GutenbergScraper()
books = scraper.get_author_books("Oscar Wilde")

downloader = BookDownloader()
downloaded = downloader.download_books(books[:5])
converted = downloader.batch_convert(downloaded)

cli.close()
```

### Example 3: Archive.org Search

```python
from book_scraper import ArchiveScraper

archive = ArchiveScraper()
books = archive.search_author("Robert Louis Stevenson", limit=20)

for book in books:
    print(f"{book.title} ({book.year})")
    print(f"  Subjects: {', '.join(book.subjects[:3])}")
```

## Email Configuration

Create `email_config.json`:

```json
{
  "provider": "gmail",
  "sender_email": "your-email@gmail.com",
  "sender_password": "your-app-password",
  "kindle_email": "your-kindle@kindle.com"
}
```

### Gmail Setup

1. Go to https://myaccount.google.com/apppasswords
2. Generate an App Password
3. Use that password (not your regular Gmail password)

### Finding Your Kindle Email

1. Go to Amazon account settings
2. Navigate to "Content & Devices" → "Preferences"
3. Look for "Send-to-Kindle Email Settings"
4. Your Kindle email looks like: `username@kindle.com`

**Important**: Add your sender email to approved list in Kindle settings!

## Database

Books are tracked in `books.db` (SQLite). You can query it:

```bash
sqlite3 books.db "SELECT title, author, downloaded FROM books;"
```

Or use Python:

```python
from book_scraper import BookDatabase

db = BookDatabase()
books = db.get_all_books()

for book in books:
    print(f"{book['title']} by {book['author']}")

db.close()
```

## File Formats

### Supported Download Formats

- EPUB (default, best quality)
- MOBI (Kindle native)
- TXT (plaintext)

### Kindle Compatibility

- **MOBI**: Native Kindle format (best choice)
- **AZW3**: Better than MOBI but requires conversion
- **PDF**: Works but not reflowable
- **EPUB**: Not directly supported (auto-converted to MOBI)

## Troubleshooting

### "ebook-convert not found"

```bash
# Install Calibre
sudo pacman -S calibre

# Verify installation
which ebook-convert
```

### "Authentication failed" (Email)

- Gmail: Use an App Password, not your regular password
- Ensure 2FA is enabled on your Google account
- Check that sender email is approved in Kindle settings

### "File too large" (Email)

Kindle email has a 50MB limit per attachment. For larger files:

- Use USB transfer instead
- Compress files
- Use Calibre's "Send to Device" feature

### Books Not Appearing on Kindle

1. Check your Kindle email address is correct
2. Verify sender is approved in Amazon settings
3. Check "Docs" section on Kindle (not "Books")
4. Sync your Kindle (Settings → Sync)

### Rate Limiting

If you get blocked:

- Add longer delays: `time.sleep(2)` between requests
- Reduce `max_workers` in parallel downloads
- Use `--batch-size 1` when emailing

## Advanced Usage

### Custom Download Directory

```python
from book_scraper import BookDownloader, BookDatabase

db = BookDatabase("my_books.db")
downloader = BookDownloader(output_dir="custom_books", db=db)

# ... rest of your code
```

### Filtering by Subject

```python
from book_scraper import GutenbergScraper

scraper = GutenbergScraper()
books = scraper.get_author_books("Arthur Conan Doyle")

# Filter for Sherlock Holmes stories
detective_books = [
    b for b in books
    if any('detective' in s.lower() for s in b.subjects)
]
```

### Parallel Processing

Adjust the number of parallel downloads:

```python
downloader = BookDownloader()
downloaded = downloader.download_books(books, max_workers=5)  # Default is 3
```

## Legal & Ethics

### ✅ Allowed

- Public domain books (published before 1929 in US)
- Books with expired copyrights
- Creative Commons licensed content
- Explicitly free content from Archive.org

### ❌ Not Allowed

- Copyrighted content without permission
- Pirated books
- DRM-protected content
- Books behind paywalls

### Best Practices

- Check `robots.txt` for each site
- Add delays between requests (`time.sleep()`)
- Use descriptive User-Agent strings
- Respect rate limits
- Only download what you need

## Sources

### Project Gutenberg

- 70,000+ free ebooks
- Public domain works
- Multiple formats available
- Best for classic literature

### Internet Archive

- Millions of texts
- Some have lending restrictions
- Includes modern works
- Best for variety

## Performance Tips

1. **Use SSD storage** for faster file operations
2. **Increase `max_workers`** for faster parallel downloads (but be respectful)
3. **Convert in batch** rather than one-by-one
4. **Cache metadata** to avoid re-fetching book info

## Project Structure

```
book-scraper/
├── book_scraper.py       # Main scraper
├── kindle_emailer.py     # Email automation
├── requirements.txt      # Python dependencies
├── README.md            # This file
├── books/               # Downloaded books (created automatically)
├── books.db             # SQLite database (created automatically)
└── email_config.json    # Email credentials (you create this)
```

## Contributing

Found a bug? Want to add a source? Feel free to extend the scrapers:

```python
class NewSourceScraper:
    def __init__(self):
        self.base_url = "https://newsource.com"
        # ... implement search_author() and get_book_metadata()
```

## License

MIT License - Do whatever you want with this code.

## Resources

- [Project Gutenberg](https://www.gutenberg.org)
- [Internet Archive](https://archive.org)
- [Calibre Documentation](https://manual.calibre-ebook.com/)
- [Kindle Email Documentation](https://www.amazon.com/sendtokindle)
- [Standard Ebooks](https://standardebooks.org) (high-quality public domain books)

## FAQ

**Q: Can I scrape from any website?**  
A: Only scrape from sites that allow it. Check their `robots.txt` and terms of service.

**Q: Why do conversions take so long?**  
A: Calibre does extensive processing. For batch conversions, go make coffee.

**Q: Can I use this on Windows?**  
A: Yes, but you'll need to install Calibre manually and adjust some Path handling.

**Q: How do I update an author's books?**  
A: Just run the same command again. The database tracks what's already downloaded.

**Q: Can I search by genre instead of author?**  
A: Not in the current version, but you can modify the scrapers to support subject/genre searches.

**Q: Is there a GUI?**  
A: No, this is CLI-only. But you could build one with tkinter or Flask pretty easily.

---

Happy reading! 📚
