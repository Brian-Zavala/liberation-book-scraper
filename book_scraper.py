#!/usr/bin/env python3
"""
Multi-source book scraper with progress tracking, metadata extraction, and Kindle conversion
Supports: Project Gutenberg, Archive.org
Features: Multi-URL fallback, automatic retry, author organization
"""

import hashlib
import json
import logging
import re
import sqlite3
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def normalize_author_name(author_name: str) -> str:
    """Normalize author name: strip whitespace, title case"""
    return " ".join(author_name.strip().split()).title()


@dataclass
class Book:
    """Book metadata with support for multiple download URLs"""

    id: str
    title: str
    author: str
    source: str
    year: Optional[int] = None
    language: str = "en"
    subjects: List[str] = field(default_factory=list)
    download_url: Optional[str] = None
    download_urls: List[str] = field(default_factory=list)
    cover_url: Optional[str] = None
    downloaded: bool = False
    copyright_status: str = "unknown"
    lending_required: bool = False

    def __post_init__(self):
        """Ensure download_urls is populated from download_url if empty"""
        if not self.download_urls and self.download_url:
            self.download_urls = [self.download_url]


class BookDatabase:
    """SQLite database to track downloaded books"""

    def __init__(self, db_path: str = "books.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.lock = Lock()  # Thread-safe operations
        self.create_tables()

    def create_tables(self) -> None:
        """Create books table if it doesn't exist"""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS books (
                id TEXT PRIMARY KEY,
                title TEXT,
                author TEXT,
                source TEXT,
                year INTEGER,
                language TEXT,
                subjects TEXT,
                download_url TEXT,
                cover_url TEXT,
                downloaded BOOLEAN,
                file_path TEXT,
                file_hash TEXT,
                copyright_status TEXT,
                lending_required BOOLEAN,
                downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        self.conn.commit()

    def add_book(
        self,
        book: Book,
        file_path: Optional[str] = None,
        file_hash: Optional[str] = None,
    ) -> None:
        """Add or update a book in the database"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO books 
                (id, title, author, source, year, language, subjects, download_url, 
                 cover_url, downloaded, file_path, file_hash, copyright_status, lending_required)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    book.id,
                    book.title,
                    book.author,
                    book.source,
                    book.year,
                    book.language,
                    json.dumps(book.subjects),
                    book.download_url,
                    book.cover_url,
                    book.downloaded,
                    file_path,
                    file_hash,
                    book.copyright_status,
                    book.lending_required,
                ),
            )
            self.conn.commit()

    def is_downloaded(self, book_id: str) -> bool:
        """Check if a book has been downloaded"""
        with self.lock:
            cursor = self.conn.cursor()
            result = cursor.execute(
                "SELECT downloaded FROM books WHERE id = ?", (book_id,)
            ).fetchone()
            return bool(result[0]) if result else False

    def get_all_books(self) -> List[Dict]:
        """Get all books from database as dictionaries"""
        with self.lock:
            cursor = self.conn.cursor()
            results = cursor.execute("SELECT * FROM books").fetchall()
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in results]

    def close(self) -> None:
        """Close database connection"""
        self.conn.close()


class GutenbergScraper:
    """Project Gutenberg scraper with multi-URL fallback support"""

    def __init__(self):
        self.base_url = "https://www.gutenberg.org"
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) BookScraper/1.0"}
        )

    def search_author(self, author_name: str) -> Optional[str]:
        """Search for author and return their bibliography page URL"""
        # Normalize author name first
        author_name = normalize_author_name(author_name)
        author_slug = author_name.lower().replace(" ", "_").replace(",", "")
        search_url = f"{self.base_url}/ebooks/author/{author_slug}"

        try:
            response = self.session.get(search_url, timeout=10)
            if response.status_code == 200:
                return response.url
        except Exception as e:
            logger.error(f"Error searching for author: {e}")

        return None

    def get_book_metadata(self, book_id: str) -> Optional[Book]:
        """Get detailed metadata for a book including multiple download URLs"""
        url = f"{self.base_url}/ebooks/{book_id}"

        try:
            response = self.session.get(url, timeout=10)
            soup = BeautifulSoup(response.content, "html.parser")

            title_elem = soup.find("h1", itemprop="name")
            title = title_elem.get_text(strip=True) if title_elem else f"Book {book_id}"

            author_elem = soup.find("a", itemprop="creator")
            author = author_elem.get_text(strip=True) if author_elem else "Unknown"

            # Get subjects
            subjects = [
                subject.get_text(strip=True)
                for subject in soup.find_all(
                    "a", href=re.compile(r"/ebooks/bookshelf/")
                )
            ]

            # Get language
            language_elem = soup.find("tr", {"property": "dcterms:language"})
            if language_elem and language_elem.find("td"):
                language = language_elem.find("td").get_text(strip=True)
            else:
                language = "en"

            # Construct multiple download URLs as fallbacks
            download_urls = [
                f"{self.base_url}/ebooks/{book_id}.epub3.images",  # Best quality
                f"{self.base_url}/ebooks/{book_id}.epub.noimages",  # Most reliable
                f"{self.base_url}/ebooks/{book_id}.epub.images",  # Legacy format
                f"{self.base_url}/files/{book_id}/{book_id}-0.epub",  # Direct download
                f"{self.base_url}/files/{book_id}/{book_id}.epub",  # Alternative path
            ]

            return Book(
                id=f"gutenberg_{book_id}",
                title=title,
                author=author,
                source="gutenberg",
                language=language,
                subjects=subjects,
                download_urls=download_urls,
                download_url=download_urls[0],
                copyright_status="public_domain",
                lending_required=False,
            )

        except Exception as e:
            logger.error(f"Error getting metadata for book {book_id}: {e}")
            return None

    def get_author_books(self, author_name: str) -> List[Book]:
        """Get all books from an author"""
        author_url = self.search_author(author_name)
        if not author_url:
            logger.warning(f"Author '{author_name}' not found")
            return []

        try:
            response = self.session.get(author_url, timeout=10)
            soup = BeautifulSoup(response.content, "html.parser")

            books = []
            book_links = soup.find_all("li", class_="booklink")

            for link in tqdm(book_links, desc="Fetching metadata"):
                book_link = link.find("a", href=re.compile(r"/ebooks/\d+"))
                if book_link:
                    book_id_match = re.search(r"/ebooks/(\d+)", book_link["href"])
                    if book_id_match:
                        book = self.get_book_metadata(book_id_match.group(1))
                        if book:
                            books.append(book)
                        time.sleep(0.5)  # Rate limiting

            return books

        except Exception as e:
            logger.error(f"Error getting books for author: {e}")
            return []


class ArchiveScraper:
    """Internet Archive scraper with multi-format fallback"""

    def __init__(self):
        self.base_url = "https://archive.org"
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) BookScraper/1.0"}
        )

    def search_author(self, author_name: str, limit: int = 50) -> List[Book]:
        """Search for books by author on Archive.org"""
        # Normalize author name first
        author_name = normalize_author_name(author_name)
        search_url = f"{self.base_url}/advancedsearch.php"
        params = {
            "q": f'creator:"{author_name}" AND mediatype:texts',
            "fl[]": [
                "identifier",
                "title",
                "creator",
                "year",
                "subject",
                "possible-copyright-status",
                "lending",
            ],
            "sort[]": "downloads desc",
            "rows": limit,
            "page": 1,
            "output": "json",
        }

        try:
            response = self.session.get(search_url, params=params, timeout=10)
            data = response.json()

            books = []
            pd_count = 0
            restricted_count = 0

            for doc in data["response"]["docs"]:
                identifier = doc["identifier"]

                # Check copyright
                copyright_status = doc.get("possible-copyright-status", "unknown")
                is_pd = copyright_status == "NOT_IN_COPYRIGHT"
                needs_lending = doc.get("lending", False)

                if is_pd:
                    pd_count += 1
                else:
                    restricted_count += 1

                # Multiple URL fallbacks for different formats
                download_urls = [
                    f"{self.base_url}/download/{identifier}/{identifier}.epub",
                    f"{self.base_url}/download/{identifier}/{identifier}.pdf",
                    f"{self.base_url}/download/{identifier}/{identifier}.mobi",
                    f"{self.base_url}/download/{identifier}/{identifier}_text.pdf",
                ]

                # Handle creator field (can be list or string)
                creator = doc.get("creator", "Unknown")
                if isinstance(creator, list):
                    creator = creator[0] if creator else "Unknown"

                # Handle subject field (can be list or string)
                subjects = doc.get("subject", [])
                if not isinstance(subjects, list):
                    subjects = [subjects] if subjects else []

                book = Book(
                    id=f"archive_{identifier}",
                    title=doc.get("title", "Unknown"),
                    author=creator,
                    source="archive",
                    year=doc.get("year"),
                    subjects=subjects,
                    download_urls=download_urls,
                    download_url=download_urls[0],
                    copyright_status="public_domain" if is_pd else "copyrighted",
                    lending_required=needs_lending,
                )
                books.append(book)

            logger.info(f"Found {len(books)} books")
            if pd_count > 0:
                logger.info(f"  Public domain: {pd_count}")
            if restricted_count > 0:
                logger.warning(f"  Copyrighted/Lending required: {restricted_count}")

            return books

        except Exception as e:
            logger.error(f"Error searching Archive.org: {e}")
            return []


class BookDownloader:
    """Download and convert books with multi-URL fallback and author organization"""

    def __init__(
        self,
        output_dir: str = "books",
        db: Optional[BookDatabase] = None,
        organize_by_author: bool = True,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.db = db
        self.organize_by_author = organize_by_author
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) BookScraper/1.0"}
        )

    def sanitize_filename(self, filename: str) -> str:
        """Clean filename for filesystem compatibility"""
        return re.sub(r'[<>:"/\\|?*]', "_", filename)[:200]

    def calculate_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def download_book(self, book: Book, format: str = "epub") -> Optional[Path]:
        """Download a single book, trying multiple URLs if needed"""
        if self.db and self.db.is_downloaded(book.id):
            logger.info(f"Already downloaded: {book.title}")
            return None

        # Skip copyrighted books
        if book.copyright_status == "copyrighted":
            logger.warning(f"⚠️  Skipping '{book.title}' - Copyrighted")
            return None

        if book.lending_required:
            logger.warning(f"⚠️  Skipping '{book.title}' - Requires borrowing/auth")
            return None

        # Create author subdirectory if organizing by author
        if self.organize_by_author:
            author_dir = self.output_dir / self.sanitize_filename(book.author)
            author_dir.mkdir(exist_ok=True)
            base_dir = author_dir
        else:
            base_dir = self.output_dir

        filename = self.sanitize_filename(f"{book.author} - {book.title}")
        file_extension = format
        output_path = base_dir / f"{filename}.{file_extension}"

        if output_path.exists():
            logger.info(f"File already exists: {output_path}")
            return output_path

        # Get all URLs to try
        urls_to_try = book.download_urls if book.download_urls else []
        if not urls_to_try and book.download_url:
            urls_to_try = [book.download_url]

        if not urls_to_try:
            logger.error(f"No download URLs available for: {book.title}")
            return None

        # Try each URL in sequence
        last_error = None
        for i, url in enumerate(urls_to_try, 1):
            try:
                logger.info(f"Attempting download {i}/{len(urls_to_try)}: {book.title}")
                logger.debug(f"URL: {url}")

                response = self.session.get(url, stream=True, timeout=30)

                # Check status code with detailed messages
                if response.status_code == 401:
                    logger.warning(
                        f"URL {i} requires authentication (401), trying next..."
                    )
                    continue
                elif response.status_code == 403:
                    logger.warning(
                        f"URL {i} is forbidden/restricted (403), trying next..."
                    )
                    continue
                elif response.status_code == 404:
                    logger.warning(f"URL {i} not found (404), trying next...")
                    continue
                elif response.status_code != 200:
                    logger.warning(
                        f"URL {i} failed with status {response.status_code}, trying next..."
                    )
                    continue

                # Check if we got actual content (not an error page)
                content_type = response.headers.get("content-type", "").lower()
                if "text/html" in content_type and "epub" in url:
                    logger.warning(
                        f"URL {i} returned HTML instead of book, trying next..."
                    )
                    continue

                # Adjust output path extension based on actual content
                if "application/pdf" in content_type and output_path.suffix != ".pdf":
                    output_path = output_path.with_suffix(".pdf")
                elif (
                    "application/epub" in content_type and output_path.suffix != ".epub"
                ):
                    output_path = output_path.with_suffix(".epub")

                total_size = int(response.headers.get("content-length", 0))

                # Download with progress bar
                with open(output_path, "wb") as f, tqdm(
                    desc=f"{book.title[:50]}",
                    total=total_size,
                    unit="B",
                    unit_scale=True,
                    unit_divisor=1024,
                    disable=total_size == 0,
                ) as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        pbar.update(len(chunk))

                # Verify file was downloaded and has content
                if not output_path.exists() or output_path.stat().st_size < 1000:
                    logger.warning(
                        f"Downloaded file too small or missing, trying next URL..."
                    )
                    if output_path.exists():
                        output_path.unlink()
                    continue

                # Success! Calculate hash and save to database
                file_hash = self.calculate_hash(output_path)

                if self.db:
                    book.downloaded = True
                    self.db.add_book(book, str(output_path), file_hash)

                logger.info(f"✓ Downloaded successfully from URL {i}: {output_path}")
                return output_path

            except requests.exceptions.Timeout:
                logger.warning(f"URL {i} timed out, trying next...")
                last_error = "Timeout"
                if output_path.exists():
                    output_path.unlink()
                continue

            except requests.exceptions.ConnectionError:
                logger.warning(f"URL {i} connection failed, trying next...")
                last_error = "Connection error"
                if output_path.exists():
                    output_path.unlink()
                continue

            except Exception as e:
                logger.warning(f"URL {i} failed with error: {e}, trying next...")
                last_error = str(e)
                if output_path.exists():
                    output_path.unlink()
                continue

        # All URLs failed
        logger.error(
            f"✗ Failed to download {book.title} after trying {len(urls_to_try)} URLs. "
            f"Last error: {last_error}"
        )
        return None

    def download_books(self, books: List[Book], max_workers: int = 3) -> List[Path]:
        """Download multiple books in parallel"""
        downloaded = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_book = {
                executor.submit(self.download_book, book): book for book in books
            }

            for future in as_completed(future_to_book):
                result = future.result()
                if result:
                    downloaded.append(result)

        return downloaded

    def convert_to_kindle(
        self, input_file: Path, output_format: str = "mobi"
    ) -> Optional[Path]:
        """Convert ebook to Kindle format using Calibre"""
        output_path = input_file.with_suffix(f".{output_format}")

        if output_path.exists():
            logger.info(f"Converted file already exists: {output_path}")
            return output_path

        # Skip PDF files - they don't convert well
        if input_file.suffix.lower() == ".pdf":
            logger.warning(
                f"Skipping PDF conversion: {input_file.name} (PDFs convert poorly)"
            )
            return None

        try:
            logger.info(f"Converting {input_file.name} to {output_format}")
            result = subprocess.run(
                [
                    "ebook-convert",
                    str(input_file),
                    str(output_path),
                    "--output-profile=kindle",
                    "--no-inline-toc",
                    "--max-toc-links=0",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )  # 2 min timeout

            logger.info(f"✓ Converted: {output_path}")
            return output_path

        except subprocess.TimeoutExpired:
            logger.error(f"✗ Conversion timed out: {input_file.name}")
            return None
        except subprocess.CalledProcessError as e:
            logger.error(f"✗ Conversion failed: {e.stderr}")
            return None
        except FileNotFoundError:
            logger.error("ebook-convert not found. Install: sudo pacman -S calibre")
            return None

    def batch_convert(
        self, files: List[Path], output_format: str = "mobi"
    ) -> List[Path]:
        """Convert multiple files"""
        converted = []
        for file in tqdm(files, desc="Converting to Kindle format"):
            result = self.convert_to_kindle(file, output_format)
            if result:
                converted.append(result)
            time.sleep(0.5)
        return converted


class BookScraperCLI:
    """Main CLI interface for book scraping"""

    def __init__(self, organize_by_author: bool = True):
        self.db = BookDatabase()
        self.downloader = BookDownloader(
            db=self.db, organize_by_author=organize_by_author
        )
        self.gutenberg = GutenbergScraper()
        self.archive = ArchiveScraper()

    def scrape_author(
        self,
        author_name: str,
        source: str = "gutenberg",
        limit: Optional[int] = None,
        convert: bool = True,
    ) -> None:
        """Main scraping workflow"""
        # Normalize author name for consistent searching
        author_name = normalize_author_name(author_name)
        logger.info(f"Searching for '{author_name}' on {source}")

        # Get books
        if source == "gutenberg":
            books = self.gutenberg.get_author_books(author_name)
        elif source == "archive":
            books = self.archive.search_author(author_name, limit or 50)
        else:
            logger.error(f"Unknown source: {source}")
            return

        if not books:
            logger.warning("No books found")
            return

        logger.info(f"Found {len(books)} books")

        if limit:
            books = books[:limit]

        # Download
        logger.info(f"Downloading {len(books)} books...")
        downloaded = self.downloader.download_books(books)

        logger.info(f"Successfully downloaded {len(downloaded)} books")

        # Convert to Kindle format
        if convert and downloaded:
            logger.info("Converting to Kindle format...")
            converted = self.downloader.batch_convert(downloaded)
            logger.info(f"Converted {len(converted)} books to Kindle format")

    def show_stats(self) -> None:
        """Show download statistics"""
        books = self.db.get_all_books()

        if not books:
            print("No books in database")
            return

        print(f"\n{'='*60}")
        print(f"Total books: {len(books)}")
        print(f"Downloaded: {sum(1 for b in books if b['downloaded'])}")
        print(f"{'='*60}\n")

        # Group by author
        by_author: Dict[str, List[Dict]] = {}
        for book in books:
            author = book["author"]
            by_author.setdefault(author, []).append(book)

        print("Books by author:")
        for author, author_books in sorted(
            by_author.items(), key=lambda x: len(x[1]), reverse=True
        ):
            print(f"  {author}: {len(author_books)} books")

    def close(self) -> None:
        """Close database connection"""
        self.db.close()


def main() -> None:
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Multi-source book scraper with automatic URL fallback"
    )
    parser.add_argument("author", help="Author name to search for")
    parser.add_argument(
        "-s",
        "--source",
        choices=["gutenberg", "archive"],
        default="gutenberg",
        help="Source to scrape from (default: gutenberg)",
    )
    parser.add_argument(
        "-l", "--limit", type=int, help="Limit number of books to download"
    )
    parser.add_argument(
        "--no-convert", action="store_true", help="Skip Kindle conversion"
    )
    parser.add_argument(
        "--no-organize",
        action="store_true",
        help="Don't organize books by author (put all in books/ directory)",
    )
    parser.add_argument("--stats", action="store_true", help="Show download statistics")

    args = parser.parse_args()

    cli = BookScraperCLI(organize_by_author=not args.no_organize)

    try:
        if args.stats:
            cli.show_stats()
        else:
            cli.scrape_author(
                args.author,
                source=args.source,
                limit=args.limit,
                convert=not args.no_convert,
            )
    finally:
        cli.close()


if __name__ == "__main__":
    main()
