#!/usr/bin/env python3
"""
Example usage scripts for common workflows
"""

from book_scraper import (
    BookScraperCLI, GutenbergScraper, ArchiveScraper, 
    BookDownloader, BookDatabase, Book
)
from pathlib import Path
import json


def example_1_simple_scrape():
    """Example 1: Simple author scrape"""
    print("Example 1: Scraping Mark Twain books\n")
    
    cli = BookScraperCLI()
    cli.scrape_author("Mark Twain", limit=3)
    cli.close()


def example_2_multiple_sources():
    """Example 2: Compare sources"""
    print("\nExample 2: Comparing sources for same author\n")
    
    gutenberg = GutenbergScraper()
    archive = ArchiveScraper()
    
    author = "Edgar Allan Poe"
    
    gut_books = gutenberg.get_author_books(author)
    print(f"Gutenberg: {len(gut_books)} books")
    
    arch_books = archive.search_author(author, limit=50)
    print(f"Archive: {len(arch_books)} books")
    
    # Find common titles
    gut_titles = {b.title.lower() for b in gut_books}
    arch_titles = {b.title.lower() for b in arch_books}
    common = gut_titles & arch_titles
    
    print(f"\nBooks available on both: {len(common)}")
    for title in sorted(common)[:5]:
        print(f"  - {title.title()}")


def example_3_filter_by_subject():
    """Example 3: Find books by subject"""
    print("\nExample 3: Finding adventure books\n")
    
    scraper = GutenbergScraper()
    books = scraper.get_author_books("Jules Verne")
    
    # Filter for adventure
    adventure = [
        b for b in books 
        if any('adventure' in s.lower() for s in b.subjects)
    ]
    
    print(f"Found {len(adventure)} adventure books:")
    for book in adventure[:5]:
        print(f"  - {book.title}")
        print(f"    Subjects: {', '.join(book.subjects[:3])}")


def example_4_download_specific_books():
    """Example 4: Download specific books by title"""
    print("\nExample 4: Downloading specific titles\n")
    
    downloader = BookDownloader()
    scraper = GutenbergScraper()
    
    author = "Arthur Conan Doyle"
    books = scraper.get_author_books(author)
    
    # Download only Sherlock Holmes stories
    holmes = [b for b in books if "holmes" in b.title.lower()]
    
    print(f"Downloading {len(holmes)} Sherlock Holmes books...")
    downloaded = downloader.download_books(holmes)
    
    print(f"\nSuccessfully downloaded {len(downloaded)} books")


def example_5_custom_metadata_export():
    """Example 5: Export custom reading list"""
    print("\nExample 5: Creating custom reading list\n")
    
    db = BookDatabase()
    books = db.get_all_books()
    
    # Create reading list grouped by author
    by_author = {}
    for book in books:
        author = book['author']
        by_author.setdefault(author, []).append(book)
    
    reading_list = {
        'total_books': len(books),
        'authors': []
    }
    
    for author, author_books in sorted(by_author.items()):
        reading_list['authors'].append({
            'name': author,
            'book_count': len(author_books),
            'books': [
                {
                    'title': b['title'],
                    'year': b.get('year'),
                    'downloaded': b['downloaded']
                }
                for b in author_books
            ]
        })
    
    # Save to JSON
    with open('reading_list.json', 'w') as f:
        json.dump(reading_list, f, indent=2)
    
    print(f"Exported reading list with {len(books)} books from {len(by_author)} authors")
    db.close()


def example_6_selective_conversion():
    """Example 6: Convert only certain books"""
    print("\nExample 6: Selective MOBI conversion\n")
    
    books_dir = Path("books")
    downloader = BookDownloader()
    
    # Convert only files larger than 1MB (skip short stories)
    epubs = []
    for epub in books_dir.glob("*.epub"):
        size_mb = epub.stat().st_size / (1024 * 1024)
        if size_mb > 1.0:
            epubs.append(epub)
    
    print(f"Converting {len(epubs)} books (>1MB)...")
    converted = downloader.batch_convert(epubs)
    print(f"Converted {len(converted)} books")


def example_7_series_detection():
    """Example 7: Detect book series"""
    print("\nExample 7: Detecting book series\n")
    
    scraper = GutenbergScraper()
    books = scraper.get_author_books("L. Frank Baum")
    
    # Group by series (simple keyword matching)
    series = {}
    keywords = ['oz', 'dorothy', 'emerald']
    
    for book in books:
        title_lower = book.title.lower()
        for keyword in keywords:
            if keyword in title_lower:
                series.setdefault(keyword.title(), []).append(book)
                break
    
    print("Detected series:")
    for series_name, series_books in series.items():
        print(f"\n{series_name} series ({len(series_books)} books):")
        for book in sorted(series_books, key=lambda x: x.title)[:3]:
            print(f"  - {book.title}")


def example_8_year_based_collection():
    """Example 8: Download books from specific era"""
    print("\nExample 8: Creating Victorian literature collection\n")
    
    db = BookDatabase()
    books = db.get_all_books()
    
    # Victorian era: 1837-1901
    victorian = [
        b for b in books 
        if b.get('year') and 1837 <= b['year'] <= 1901
    ]
    
    print(f"Found {len(victorian)} Victorian-era books:")
    
    # Group by decade
    by_decade = {}
    for book in victorian:
        decade = (book['year'] // 10) * 10
        by_decade.setdefault(decade, []).append(book)
    
    for decade in sorted(by_decade.keys()):
        print(f"\n{decade}s: {len(by_decade[decade])} books")
    
    db.close()


def example_9_download_monitoring():
    """Example 9: Monitor download progress"""
    print("\nExample 9: Download with custom monitoring\n")
    
    from tqdm import tqdm
    import time
    
    scraper = GutenbergScraper()
    downloader = BookDownloader()
    
    books = scraper.get_author_books("H.G. Wells")[:5]
    
    print(f"Downloading {len(books)} books with custom progress tracking...")
    
    successful = []
    failed = []
    
    for book in tqdm(books, desc="Overall progress"):
        result = downloader.download_book(book)
        if result:
            successful.append(book)
        else:
            failed.append(book)
        time.sleep(1)  # Rate limiting
    
    print(f"\n✓ Success: {len(successful)}")
    print(f"✗ Failed: {len(failed)}")
    
    if failed:
        print("\nFailed downloads:")
        for book in failed:
            print(f"  - {book.title}")


def example_10_smart_recommendations():
    """Example 10: Get book recommendations based on library"""
    print("\nExample 10: Smart recommendations\n")
    
    db = BookDatabase()
    books = db.get_all_books()
    
    # Count subject frequencies
    subject_count = {}
    for book in books:
        subjects = book.get('subjects', '[]')
        try:
            subjects_list = json.loads(subjects)
            for subject in subjects_list:
                subject_count[subject] = subject_count.get(subject, 0) + 1
        except:
            continue
    
    # Top subjects
    top_subjects = sorted(subject_count.items(), key=lambda x: x[1], reverse=True)[:5]
    
    print("Your reading preferences (by subject):")
    for subject, count in top_subjects:
        print(f"  {subject}: {count} books")
    
    print("\nRecommended search: Look for more books in these genres!")
    
    db.close()


if __name__ == "__main__":
    import sys
    
    examples = {
        '1': ('Simple scrape', example_1_simple_scrape),
        '2': ('Multiple sources', example_2_multiple_sources),
        '3': ('Filter by subject', example_3_filter_by_subject),
        '4': ('Specific downloads', example_4_download_specific_books),
        '5': ('Custom export', example_5_custom_metadata_export),
        '6': ('Selective conversion', example_6_selective_conversion),
        '7': ('Series detection', example_7_series_detection),
        '8': ('Year-based collection', example_8_year_based_collection),
        '9': ('Download monitoring', example_9_download_monitoring),
        '10': ('Smart recommendations', example_10_smart_recommendations),
    }
    
    if len(sys.argv) > 1 and sys.argv[1] in examples:
        name, func = examples[sys.argv[1]]
        print(f"\n{'='*60}")
        print(f"Running: {name}")
        print('='*60)
        func()
    else:
        print("\nAvailable examples:")
        print("=" * 60)
        for num, (name, _) in examples.items():
            print(f"  {num}. {name}")
        print("\nUsage: python examples.py [number]")
        print("Example: python examples.py 1")
