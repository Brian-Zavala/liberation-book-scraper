#!/usr/bin/env python3
"""
Batch operations and advanced utilities for book scraping
"""

from pathlib import Path
from typing import List, Dict
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from book_scraper import (
    BookScraperCLI,
    GutenbergScraper,
    ArchiveScraper,
    BookDownloader,
    BookDatabase,
    Book,
    normalize_author_name,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BatchOperations:
    """Advanced batch operations"""

    def __init__(self, organize_by_author=True):
        self.db = BookDatabase()
        self.downloader = BookDownloader(
            db=self.db, organize_by_author=organize_by_author
        )
        self.gutenberg = GutenbergScraper()
        self.archive = ArchiveScraper()

    def scrape_multiple_authors(
        self,
        authors: List[str],
        source: str = "gutenberg",
        limit_per_author: int = None,
    ):
        """Scrape books from multiple authors"""
        # Normalize all author names
        authors = [normalize_author_name(a) for a in authors]
        logger.info(f"Scraping {len(authors)} authors from {source}")

        all_books = []
        for i, author in enumerate(authors, 1):
            logger.info(f"\n[{i}/{len(authors)}] Processing: {author}")

            if source == "gutenberg":
                books = self.gutenberg.get_author_books(author)
            else:
                books = self.archive.search_author(author, limit_per_author or 50)

            if limit_per_author:
                books = books[:limit_per_author]

            all_books.extend(books)
            logger.info(f"Found {len(books)} books by {author}")

        logger.info(f"\nTotal books found: {len(all_books)}")

        # Download all
        downloaded = self.downloader.download_books(all_books, max_workers=3)
        logger.info(f"Downloaded {len(downloaded)} books")

        # Convert all
        converted = self.downloader.batch_convert(downloaded)
        logger.info(f"Converted {len(converted)} books")

        return downloaded, converted

    def scrape_from_list(self, list_file: str, source: str = "gutenberg"):
        """Scrape authors from a text file (one per line)"""
        try:
            with open(list_file) as f:
                authors = [line.strip() for line in f if line.strip()]

            logger.info(f"Loaded {len(authors)} authors from {list_file}")
            return self.scrape_multiple_authors(authors, source)

        except FileNotFoundError:
            logger.error(f"File not found: {list_file}")
            return [], []

    def export_metadata(self, output_file: str = "books_metadata.json"):
        """Export all book metadata to JSON"""
        books = self.db.get_all_books()

        # Clean up for JSON serialization
        for book in books:
            if book.get("subjects"):
                try:
                    book["subjects"] = json.loads(book["subjects"])
                except:
                    pass

        with open(output_file, "w") as f:
            json.dump(books, f, indent=2, default=str)

        logger.info(f"Exported {len(books)} books to {output_file}")

    def filter_books_by_subject(self, subject: str) -> List[Dict]:
        """Find all books matching a subject"""
        books = self.db.get_all_books()

        matching = []
        for book in books:
            subjects = book.get("subjects", "[]")
            try:
                subjects_list = json.loads(subjects)
                if any(subject.lower() in s.lower() for s in subjects_list):
                    matching.append(book)
            except:
                continue

        return matching

    def generate_reading_list(
        self, subjects: List[str] = None, min_year: int = None, max_year: int = None
    ) -> List[Dict]:
        """Generate a curated reading list based on criteria"""
        books = self.db.get_all_books()

        filtered = []
        for book in books:
            # Filter by year
            if min_year and book.get("year") and book["year"] < min_year:
                continue
            if max_year and book.get("year") and book["year"] > max_year:
                continue

            # Filter by subjects
            if subjects:
                book_subjects = book.get("subjects", "[]")
                try:
                    subjects_list = json.loads(book_subjects)
                    if not any(
                        any(s.lower() in bs.lower() for bs in subjects_list)
                        for s in subjects
                    ):
                        continue
                except:
                    continue

            filtered.append(book)

        return filtered

    def deduplicate_downloads(self):
        """Find and remove duplicate book files"""
        from collections import defaultdict

        books = self.db.get_all_books()
        by_hash = defaultdict(list)

        for book in books:
            if book.get("file_hash"):
                by_hash[book["file_hash"]].append(book)

        duplicates = {h: b for h, b in by_hash.items() if len(b) > 1}

        logger.info(f"Found {len(duplicates)} sets of duplicate files")

        for hash_val, dupe_books in duplicates.items():
            logger.info(f"\nDuplicates (hash: {hash_val[:8]}...):")
            for book in dupe_books:
                logger.info(f"  - {book['title']} by {book['author']}")

        return duplicates

    def verify_downloads(self) -> Dict[str, List]:
        """Verify integrity of downloaded files"""
        books = self.db.get_all_books()

        results = {"valid": [], "missing": [], "corrupted": []}

        for book in books:
            if not book.get("file_path"):
                continue

            file_path = Path(book["file_path"])

            if not file_path.exists():
                results["missing"].append(book)
                continue

            # Verify hash if available
            if book.get("file_hash"):
                actual_hash = self.downloader.calculate_hash(file_path)
                if actual_hash != book["file_hash"]:
                    results["corrupted"].append(book)
                    continue

            results["valid"].append(book)

        logger.info(f"Valid: {len(results['valid'])}")
        logger.info(f"Missing: {len(results['missing'])}")
        logger.info(f"Corrupted: {len(results['corrupted'])}")

        return results

    def cleanup_unconverted(self, delete: bool = False):
        """Find EPUB files without corresponding MOBI conversions"""
        books_dir = Path("books")

        epubs = list(books_dir.glob("*.epub"))
        unconverted = []

        for epub in epubs:
            mobi = epub.with_suffix(".mobi")
            if not mobi.exists():
                unconverted.append(epub)

        logger.info(f"Found {len(unconverted)} unconverted EPUBs")

        if delete:
            for epub in unconverted:
                logger.info(f"Deleting: {epub}")
                epub.unlink()

        return unconverted

    def archive_old_books(self, archive_dir: str = "archive"):
        """Move old/read books to archive directory"""
        books_dir = Path("books")
        archive_path = Path(archive_dir)
        archive_path.mkdir(exist_ok=True)

        # This is a placeholder - you'd implement logic to determine
        # which books to archive (e.g., based on last access time,
        # user input, etc.)
        logger.info("Archive feature not fully implemented")
        logger.info("Implement your own logic to determine which books to archive")

    def close(self):
        self.db.close()


def create_author_list_template():
    """Create a template author list"""
    template = """# Author List
# One author per line
# Lines starting with # are comments

Mark Twain
Charles Dickens
Jane Austen
Edgar Allan Poe
Oscar Wilde
Arthur Conan Doyle
H.G. Wells
Jules Verne
Leo Tolstoy
Fyodor Dostoevsky
"""

    with open("authors.txt", "w") as f:
        f.write(template)

    logger.info("Created authors.txt template")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Batch operations for book scraper")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Multiple authors
    multi = subparsers.add_parser("multi", help="Scrape multiple authors")
    multi.add_argument("authors", nargs="+", help="Author names")
    multi.add_argument(
        "-s", "--source", choices=["gutenberg", "archive"], default="gutenberg"
    )
    multi.add_argument("-l", "--limit", type=int, help="Books per author")

    # From file
    file_cmd = subparsers.add_parser("from-file", help="Scrape from author list file")
    file_cmd.add_argument("file", help="File with author list")
    file_cmd.add_argument(
        "-s", "--source", choices=["gutenberg", "archive"], default="gutenberg"
    )

    # Export
    export = subparsers.add_parser("export", help="Export metadata to JSON")
    export.add_argument("-o", "--output", default="books_metadata.json")

    # Subject search
    subject = subparsers.add_parser("subject", help="Find books by subject")
    subject.add_argument("subject", help="Subject to search for")

    # Verify
    subparsers.add_parser("verify", help="Verify download integrity")

    # Deduplicate
    subparsers.add_parser("dedupe", help="Find duplicate downloads")

    # Cleanup
    cleanup = subparsers.add_parser("cleanup", help="Clean up unconverted EPUBs")
    cleanup.add_argument("--delete", action="store_true", help="Actually delete files")

    # Create template
    subparsers.add_parser("create-list", help="Create author list template")

    args = parser.parse_args()

    if args.command == "create-list":
        create_author_list_template()
    else:
        batch = BatchOperations()

        try:
            if args.command == "multi":
                batch.scrape_multiple_authors(args.authors, args.source, args.limit)

            elif args.command == "from-file":
                batch.scrape_from_list(args.file, args.source)

            elif args.command == "export":
                batch.export_metadata(args.output)

            elif args.command == "subject":
                books = batch.filter_books_by_subject(args.subject)
                logger.info(f"\nFound {len(books)} books:")
                for book in books[:20]:  # Show first 20
                    print(f"  - {book['title']} by {book['author']}")

            elif args.command == "verify":
                batch.verify_downloads()

            elif args.command == "dedupe":
                batch.deduplicate_downloads()

            elif args.command == "cleanup":
                batch.cleanup_unconverted(args.delete)

        finally:
            batch.close()
