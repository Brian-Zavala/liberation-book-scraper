#!/usr/bin/env python3
"""
Demo: Multi-URL Fallback System
Shows how the scraper automatically tries multiple URLs for resilience
"""

from book_scraper import GutenbergScraper, BookDownloader, Book
import logging

# Enable debug logging to see all URL attempts
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

print("="*70)
print("MULTI-URL FALLBACK DEMO")
print("="*70)
print("\nThis demonstrates how the scraper automatically tries multiple URLs")
print("for each book until one succeeds. Watch the logs below:\n")

# Example 1: Create a book with multiple URLs (some may fail)
print("\n" + "="*70)
print("Example 1: Downloading with automatic URL fallback")
print("="*70 + "\n")

scraper = GutenbergScraper()
downloader = BookDownloader()

# Get a book from Gutenberg
books = scraper.get_author_books("Mark Twain")

if books:
    test_book = books[0]
    
    print(f"Book: {test_book.title}")
    print(f"Author: {test_book.author}")
    print(f"\nAvailable URLs ({len(test_book.download_urls)}):")
    for i, url in enumerate(test_book.download_urls, 1):
        print(f"  {i}. {url}")
    
    print("\n" + "-"*70)
    print("Starting download... (will try each URL until one works)")
    print("-"*70 + "\n")
    
    result = downloader.download_book(test_book)
    
    if result:
        print(f"\n✓ SUCCESS! Book downloaded to: {result}")
        print("\nThe scraper automatically:")
        print("  1. Tried the first URL")
        print("  2. If it failed, moved to the next URL")
        print("  3. Continued until finding a working URL")
        print("  4. Downloaded the book")
    else:
        print("\n✗ All URLs failed (this is rare)")

# Example 2: Show how it handles dead URLs
print("\n\n" + "="*70)
print("Example 2: Handling broken URLs gracefully")
print("="*70 + "\n")

# Create a test book with intentionally bad URLs followed by good ones
test_book_2 = Book(
    id="test_resilience",
    title="Test Resilience Book",
    author="Test Author",
    source="test",
    download_urls=[
        "https://www.gutenberg.org/files/99999/definitely-not-real.epub",  # Will fail
        "https://example.com/fake-book.epub",  # Will fail
        "https://www.gutenberg.org/ebooks/1342.epub.noimages",  # Should work (Pride & Prejudice)
    ]
)

print(f"Test Book: {test_book_2.title}")
print(f"\nURLs to try (first 2 will fail, last should work):")
for i, url in enumerate(test_book_2.download_urls, 1):
    print(f"  {i}. {url}")

print("\n" + "-"*70)
print("Watch how it handles failures and retries automatically:")
print("-"*70 + "\n")

result = downloader.download_book(test_book_2)

if result:
    print(f"\n✓ SUCCESS! Even though first URLs failed, got book from URL 3")
    print(f"   Saved to: {result}")

# Example 3: Statistics
print("\n\n" + "="*70)
print("Example 3: Why Multiple URLs Matter")
print("="*70 + "\n")

print("Benefits of multi-URL fallback:")
print("  ✓ Higher success rate (tries multiple formats)")
print("  ✓ Handles temporary server issues")
print("  ✓ Works across different mirror structures")
print("  ✓ Automatically adapts to file availability")
print("  ✓ No manual intervention needed")

print("\nURL formats tried:")
print("  1. EPUB3 with images (best quality)")
print("  2. EPUB without images (smaller, reliable)")
print("  3. Legacy EPUB formats")
print("  4. Direct file paths")
print("  5. Alternative naming schemes")

print("\n" + "="*70)
print("KEY FEATURES")
print("="*70)
print("""
✓ AUTOMATIC: No manual retry needed
✓ SMART: Detects HTML error pages vs actual books
✓ LOGGING: See exactly which URL worked
✓ EFFICIENT: Stops at first success
✓ CLEAN: Removes partial downloads on failure
✓ TRACKED: Database records successful URL
""")

print("\nUsage in your code:")
print("="*70)
print("""
from book_scraper import BookScraperCLI

# Just use normally - fallback is automatic!
cli = BookScraperCLI()
cli.scrape_author("Charles Dickens", limit=5)

# The scraper will automatically:
# - Try multiple URLs for each book
# - Skip to next URL if one fails
# - Move to next book only after exhausting all URLs
# - Log everything for transparency
""")

print("\nReal-world example:")
print("="*70)
print("""
# Scrape 100 books
./book_scraper.py "Various Authors" --limit 100

# Behind the scenes:
# - Book 1: URL 1 works ✓
# - Book 2: URL 1 fails, URL 2 works ✓
# - Book 3: URL 1 fails, URL 2 fails, URL 3 works ✓
# - Book 4: All URLs fail, skip to book 5 ✗
# - Book 5: URL 1 works ✓
# ... continues automatically ...
""")

print("\nConfiguration:")
print("="*70)
print("""
You can customize the behavior in book_scraper.py:

1. Add more URL patterns in get_book_metadata()
2. Adjust timeout in download_book()
3. Change retry logic as needed
4. Add custom URL sources

The system is fully extensible!
""")
