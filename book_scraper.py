#!/usr/bin/env python3
"""
Multi-Source Book Scraper - FIXED VERSION

Supports: Gutenberg, Internet Archive, Open Library, DOAB, Standard Ebooks,
          LibGen, Z-Library, Hoopla
"""

import argparse
import json
import logging
import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote, urljoin
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class Book:
    """Book metadata"""

    id: str
    title: str
    author: str
    source: str
    download_urls: List[str] = field(default_factory=list)
    format: str = "epub"
    year: Optional[int] = None
    description: Optional[str] = None
    cover_url: Optional[str] = None  # For future UI/display purposes
    isbn: Optional[str] = None
    language: str = "en"
    subjects: List[str] = field(default_factory=list)

    # Open Library specific
    is_borrowable: bool = False
    borrow_url: Optional[str] = None


class BookDatabase:
    """Database with borrowing tracking"""

    def __init__(self, db_path: str = "books_enhanced.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        """Create enhanced database schema"""
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS books (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                source TEXT NOT NULL,
                format TEXT,
                year INTEGER,
                description TEXT,
                isbn TEXT,
                language TEXT,
                subjects TEXT,
                file_path TEXT,
                download_date TIMESTAMP,
                file_size INTEGER
            );

            CREATE TABLE IF NOT EXISTS borrows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id TEXT NOT NULL,
                borrow_date TIMESTAMP,
                due_date TIMESTAMP,
                return_date TIMESTAMP,
                status TEXT,
                FOREIGN KEY (book_id) REFERENCES books(id)
            );

            CREATE TABLE IF NOT EXISTS download_urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id TEXT NOT NULL,
                url TEXT NOT NULL,
                url_type TEXT,
                working BOOLEAN,
                last_checked TIMESTAMP,
                FOREIGN KEY (book_id) REFERENCES books(id)
            );

            CREATE INDEX IF NOT EXISTS idx_author ON books(author);
            CREATE INDEX IF NOT EXISTS idx_source ON books(source);
            CREATE INDEX IF NOT EXISTS idx_year ON books(year);
            """
        )
        self.conn.commit()

    def add_book(self, book: Book, file_path: Optional[str] = None):
        """Add or update book in database"""
        try:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO books 
                (id, title, author, source, format, year, description, isbn, language, subjects, file_path, download_date, file_size)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    book.id,
                    book.title,
                    book.author,
                    book.source,
                    book.format,
                    book.year,
                    book.description,
                    book.isbn,
                    book.language,
                    json.dumps(book.subjects),
                    file_path,
                    datetime.now().isoformat() if file_path else None,
                    (
                        Path(file_path).stat().st_size
                        if file_path and Path(file_path).exists()
                        else None
                    ),
                ),
            )

            # Add URLs
            for url in book.download_urls:
                self.conn.execute(
                    """
                    INSERT OR IGNORE INTO download_urls (book_id, url, last_checked)
                    VALUES (?, ?, ?)
                    """,
                    (book.id, url, datetime.now().isoformat()),
                )

            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Database error adding book {book.id}: {e}")
            return False

    def book_exists(self, book_id: str) -> bool:
        """Check if book exists in database"""
        cursor = self.conn.execute(
            "SELECT id FROM books WHERE id = ? AND file_path IS NOT NULL", (book_id,)
        )
        return cursor.fetchone() is not None

    def add_borrow(self, book_id: str, due_date: datetime):
        """Track a borrowed book"""
        self.conn.execute(
            """
            INSERT INTO borrows (book_id, borrow_date, due_date, status)
            VALUES (?, ?, ?, 'active')
            """,
            (book_id, datetime.now().isoformat(), due_date.isoformat()),
        )
        self.conn.commit()

    def get_active_borrows(self) -> List[Dict]:
        """Get all active borrowed books"""
        cursor = self.conn.execute(
            """
            SELECT b.*, bk.title, bk.author, bk.source
            FROM borrows b
            JOIN books bk ON b.book_id = bk.id
            WHERE b.status = 'active'
            ORDER BY b.due_date
            """
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_stats(self) -> Dict:
        """Get download statistics"""
        cursor = self.conn.execute(
            """
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN file_path IS NOT NULL THEN 1 END) as downloaded,
                source,
                COUNT(*) as count
            FROM books
            GROUP BY source
            """
        )
        stats = {"by_source": {}}
        for row in cursor.fetchall():
            stats["by_source"][row["source"]] = row["count"]

        cursor = self.conn.execute(
            "SELECT COUNT(*) as total, SUM(file_size) as total_size FROM books WHERE file_path IS NOT NULL"
        )
        row = cursor.fetchone()
        stats["total_downloaded"] = row["total"]
        stats["total_size_mb"] = (
            row["total_size"] / (1024 * 1024) if row["total_size"] else 0
        )

        return stats

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        """Context manager exit"""
        self.close()
        return False


class OpenLibraryScraper:
    """Scraper for Open Library (modern books, borrowing system)"""

    def __init__(self):
        self.base_url = "https://openlibrary.org"
        self.api_url = "https://openlibrary.org/api"
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "BookScraperBot/2.0 (Educational; Linux)"}
        )

    def search_author(self, author_name: str, limit: int = 50) -> List[Book]:
        """Search for books by author on Open Library"""
        if not author_name or not author_name.strip():
            logger.error("Author name cannot be empty")
            return []

        books = []
        searched_author = author_name.strip().lower()

        try:
            # Search API
            search_url = f"{self.base_url}/search.json"
            params = {
                "author": author_name.strip(),
                "limit": max(1, min(limit, 100)),  # Clamp between 1-100
                "has_fulltext": "true",  # Only books with full text
            }

            logger.info(f"Searching Open Library for '{author_name}'")
            response = self.session.get(search_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if "docs" not in data:
                logger.warning(f"No results from Open Library for '{author_name}'")
                return books

            logger.info(f"Found {len(data['docs'])} potential books on Open Library")

            for doc in data["docs"]:
                try:
                    book_key = doc.get("key", "")
                    if not book_key:
                        continue

                    # CRITICAL: Validate author matches
                    doc_authors = doc.get("author_name", [])
                    if not doc_authors:
                        logger.debug(
                            f"Skipping book with no author: {doc.get('title')}"
                        )
                        continue

                    # Check if searched author is in the book's author list
                    author_match = False
                    for doc_author in doc_authors:
                        doc_author_lower = doc_author.lower()
                        # Check for exact match or if one contains the other
                        if (
                            searched_author in doc_author_lower
                            or doc_author_lower in searched_author
                            or self._fuzzy_author_match(
                                searched_author, doc_author_lower
                            )
                        ):
                            author_match = True
                            break

                    if not author_match:
                        logger.debug(
                            f"Skipping book by different author: {doc.get('title')} by {doc_authors[0]}"
                        )
                        continue

                    # Get detailed info
                    book = self._get_book_details(book_key, doc)
                    if book:
                        books.append(book)

                except Exception as e:
                    logger.debug(f"Error processing book: {e}")
                    continue

            logger.info(
                f"Successfully processed {len(books)} books from Open Library (after author filtering)"
            )

        except Exception as e:
            logger.error(f"Error searching Open Library: {e}")

        return books

    def _fuzzy_author_match(self, searched: str, found: str) -> bool:
        """Check if author names match allowing for variations"""

        prefixes = [
            "dr ",
            "dr. ",
            "mr ",
            "mr. ",
            "mrs ",
            "mrs. ",
            "ms ",
            "ms. ",
            "prof ",
            "prof. ",
        ]
        suffixes = [" jr", " jr.", " sr", " sr.", " ii", " iii", " iv"]

        def normalize(name):
            name = name.lower().strip()
            # Remove punctuation except spaces
            name = re.sub(r"[^\w\s]", " ", name)
            # Remove extra spaces
            name = " ".join(name.split())

            for prefix in prefixes:
                prefix_clean = prefix.strip().replace(".", "")
                if name.startswith(prefix_clean + " "):
                    name = name[len(prefix_clean) :].strip()
            for suffix in suffixes:
                suffix_clean = suffix.strip().replace(".", "")
                if name.endswith(" " + suffix_clean):
                    name = name[: -len(suffix_clean)].strip()
            return name.strip()

        searched_norm = normalize(searched)
        found_norm = normalize(found)

        # Exact match after normalization
        if searched_norm == found_norm:
            return True

        # Split into words for flexible matching
        searched_words = set(searched_norm.split())
        found_words = set(found_norm.split())

        # Remove single letters and very common words
        common_fillers = {
            "a",
            "b",
            "c",
            "d",
            "e",
            "f",
            "g",
            "h",
            "i",
            "j",
            "k",
            "l",
            "m",
            "n",
            "o",
            "p",
            "q",
            "r",
            "s",
            "t",
            "u",
            "v",
            "w",
            "x",
            "y",
            "z",
            "de",
            "van",
            "von",
            "del",
            "la",
            "le",
        }
        searched_words = {
            w for w in searched_words if len(w) > 1 and w not in common_fillers
        }
        found_words = {w for w in found_words if len(w) > 1 and w not in common_fillers}

        if not searched_words or not found_words:
            return False

        # Match if at least 2 significant words match (or all words if less than 2)
        common_words = searched_words & found_words
        min_matches = min(2, len(searched_words))

        return len(common_words) >= min_matches

    def _get_book_details(self, book_key: str, search_doc: Dict) -> Optional[Book]:
        """Get detailed book information"""
        try:
            # Extract ID from key (e.g., '/works/OL123W' -> 'OL123W')
            book_id = book_key.split("/")[-1]

            title = search_doc.get("title", "Unknown")
            author = ", ".join(search_doc.get("author_name", ["Unknown"]))
            year = search_doc.get("first_publish_year")

            # Check if borrowable
            ia_id = search_doc.get("ia", [])
            lending_edition = search_doc.get("lending_edition_s")

            # Build download URLs
            download_urls = []
            is_borrowable = False
            borrow_url = None

            if ia_id and len(ia_id) > 0:
                # Internet Archive identifier available
                ia_identifier = ia_id[0]
                download_urls.append(
                    f"https://archive.org/download/{ia_identifier}/{ia_identifier}.epub"
                )
                download_urls.append(
                    f"https://archive.org/download/{ia_identifier}/{ia_identifier}.pdf"
                )
                is_borrowable = True
                borrow_url = f"https://openlibrary.org{book_key}"

            if lending_edition:
                # Add lending edition URL
                download_urls.append(
                    f"https://openlibrary.org/books/{lending_edition}.epub"
                )
                is_borrowable = True

            # Get cover
            cover_id = search_doc.get("cover_i")
            cover_url = (
                f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
                if cover_id
                else None
            )

            # Get ISBN
            isbn = search_doc.get("isbn", [None])[0] if search_doc.get("isbn") else None

            # Subjects
            subjects = search_doc.get("subject", [])[:5]  # Top 5 subjects

            book = Book(
                id=f"openlibrary_{book_id}",
                title=title,
                author=author,
                source="openlibrary",
                download_urls=download_urls,
                year=year,
                description=None,  # Could fetch from work page
                cover_url=cover_url,
                isbn=isbn,
                subjects=subjects,
                is_borrowable=is_borrowable,
                borrow_url=borrow_url,
            )

            return book if download_urls else None

        except Exception as e:
            logger.debug(f"Error getting book details: {e}")
            return None

    def close(self):
        """Close session"""
        if self.session:
            self.session.close()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        """Context manager exit"""
        self.close()
        return False


class DOABScraper:
    """Scraper for Directory of Open Access Books (academic books)"""

    def __init__(self):
        self.base_url = "https://www.doabooks.org"
        self.api_url = "https://directory.doabooks.org/rest"
        self.session = requests.Session()

    def search_author(self, author_name: str, limit: int = 50) -> List[Book]:
        """Search DOAB for open access books"""
        books = []

        try:
            # DOAB API search
            search_url = f"{self.api_url}/search"
            params = {
                "query": f"author:{author_name}",
                "expand": "metadata",
                "limit": limit,
            }

            logger.info(f"Searching DOAB for '{author_name}'")
            response = self.session.get(search_url, params=params, timeout=30)

            if response.status_code != 200:
                logger.warning(f"DOAB API returned status {response.status_code}")
                return books

            # Parse results (DOAB returns XML/JSON depending on endpoint)
            # This is a simplified version - actual implementation may vary
            data = (
                response.json()
                if "json" in response.headers.get("content-type", "")
                else {}
            )

            # Process results (structure depends on DOAB API version)
            # Note: DOAB API implementation is placeholder
            # Full implementation would parse results here

        except Exception as e:
            logger.error(f"Error searching DOAB: {e}")

        return books

    def close(self):
        """Close session"""
        if self.session:
            self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        self.close()
        return False


class StandardEbooksScraper:
    """Scraper for Standard Ebooks (high-quality public domain)"""

    def __init__(self):
        self.base_url = "https://standardebooks.org"
        self.session = requests.Session()

    def search_author(self, author_name: str, limit: int = 50) -> List[Book]:
        """Search Standard Ebooks"""
        books = []

        try:
            # Standard Ebooks has an OPDS feed
            opds_url = f"{self.base_url}/opds/all"

            logger.info(f"Searching Standard Ebooks for '{author_name}'")

            # Add headers that might be required
            headers = {
                "User-Agent": "BookScraperBot/2.0 (Educational; Linux)",
                "Accept": "application/atom+xml, application/xml, text/xml, */*",
            }

            response = self.session.get(opds_url, headers=headers, timeout=30)

            # Handle 401 Unauthorized - API may have changed or require authentication
            if response.status_code == 401:
                logger.warning(
                    f"Standard Ebooks requires authentication or API has changed"
                )
                logger.info(f"Try: wget {opds_url} to check if accessible")
                return books

            response.raise_for_status()

            soup = BeautifulSoup(response.content, "xml")

            # Parse OPDS feed entries
            entries = soup.find_all("entry")

            for entry in entries[:limit]:
                try:
                    # Get author
                    author_elem = entry.find("author")
                    if not author_elem:
                        continue

                    book_author = (
                        author_elem.find("name").text
                        if author_elem.find("name")
                        else ""
                    )

                    # Check if author matches (case-insensitive)
                    if author_name.lower() not in book_author.lower():
                        continue

                    # Get title
                    title_elem = entry.find("title")
                    title = title_elem.text if title_elem else "Unknown"

                    # Get ID
                    id_elem = entry.find("id")
                    book_id = id_elem.text.split("/")[-1] if id_elem else None

                    if not book_id:
                        continue

                    # Get download link
                    links = entry.find_all("link")
                    download_urls = []

                    for link in links:
                        if link.get("type") == "application/epub+zip":
                            download_urls.append(link.get("href"))

                    if not download_urls:
                        continue

                    # Get cover
                    cover_link = entry.find(
                        "link", {"rel": "http://opds-spec.org/image"}
                    )
                    cover_url = cover_link.get("href") if cover_link else None

                    # Get description
                    summary = entry.find("summary")
                    description = summary.text if summary else None

                    book = Book(
                        id=f"standardebooks_{book_id}",
                        title=title,
                        author=book_author,
                        source="standardebooks",
                        download_urls=download_urls,
                        description=description,
                        cover_url=cover_url,
                    )

                    books.append(book)

                except Exception as e:
                    logger.debug(f"Error processing Standard Ebooks entry: {e}")
                    continue

            logger.info(f"Found {len(books)} books on Standard Ebooks")

        except Exception as e:
            logger.error(f"Error searching Standard Ebooks: {e}")

        return books

    def close(self):
        """Close session"""
        if self.session:
            self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        self.close()
        return False


class GutenbergScraper:
    """Enhanced Gutenberg scraper (keeping original functionality)"""

    def __init__(self):
        self.base_url = "https://www.gutenberg.org"
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "BookScraperBot/2.0 (Educational; Linux)"}
        )

    def get_author_books(self, author_name: str) -> List[Book]:
        """Get books by author from Gutenberg"""
        books = []

        try:
            # Search for author
            search_url = f"{self.base_url}/ebooks/author/"
            author_slug = author_name.lower().replace(" ", "_").replace(".", "")

            logger.info(f"Searching Gutenberg for '{author_name}'")
            response = self.session.get(f"{search_url}{author_slug}", timeout=30)

            if response.status_code != 200:
                logger.warning(f"Author '{author_name}' not found on Gutenberg")
                return books

            soup = BeautifulSoup(response.content, "html.parser")

            # Find all book entries
            book_list = soup.find("ol", class_="results")
            if not book_list:
                return books

            for li in book_list.find_all("li", class_="booklink"):
                try:
                    # Get book title and ID
                    title_link = li.find("a", class_="link")
                    if not title_link:
                        continue

                    title = title_link.find("span", class_="title").text.strip()
                    book_id = title_link.get("href").split("/")[-1]

                    # Build download URLs
                    download_urls = [
                        f"{self.base_url}/ebooks/{book_id}.epub3.images",
                        f"{self.base_url}/ebooks/{book_id}.epub.images",
                        f"{self.base_url}/ebooks/{book_id}.epub.noimages",
                        f"{self.base_url}/files/{book_id}/{book_id}-0.epub",
                    ]

                    book = Book(
                        id=f"gutenberg_{book_id}",
                        title=title,
                        author=author_name,
                        source="gutenberg",
                        download_urls=download_urls,
                    )

                    books.append(book)

                except Exception as e:
                    logger.debug(f"Error processing Gutenberg book: {e}")
                    continue

            logger.info(f"Found {len(books)} books on Gutenberg")

        except Exception as e:
            logger.error(f"Error searching Gutenberg: {e}")

        return books

    def close(self):
        """Close session"""
        if self.session:
            self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        self.close()
        return False


class InternetArchiveScraper:
    """Enhanced Internet Archive scraper"""

    def __init__(self):
        self.base_url = "https://archive.org"
        self.session = requests.Session()

    def search_author(self, author_name: str, limit: int = 50) -> List[Book]:
        """Search Internet Archive for books"""
        books = []
        searched_author = author_name.strip().lower()

        try:
            search_url = f"{self.base_url}/advancedsearch.php"
            params = {
                "q": f'creator:"{author_name}" AND mediatype:texts',
                "fl[]": ["identifier", "title", "creator", "year", "description"],
                "rows": limit,
                "page": 1,
                "output": "json",
            }

            logger.info(f"Searching Internet Archive for '{author_name}'")
            response = self.session.get(search_url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            if "response" not in data or "docs" not in data["response"]:
                logger.warning(f"No results from Internet Archive for '{author_name}'")
                return books

            for doc in data["response"]["docs"]:
                try:
                    identifier = doc.get("identifier")
                    if not identifier:
                        continue

                    title = doc.get("title", "Unknown")

                    # Get creator(s)
                    creators = doc.get("creator", [])
                    if isinstance(creators, str):
                        creators = [creators]
                    elif not isinstance(creators, list):
                        creators = ["Unknown"]

                    if not creators or creators == ["Unknown"]:
                        logger.debug(f"Skipping book with no creator: {title}")
                        continue

                    # Validate at least one creator matches searched author
                    author_match = False
                    matched_author = creators[0]  # Default to first

                    for creator in creators:
                        creator_lower = creator.lower()
                        if (
                            searched_author in creator_lower
                            or creator_lower in searched_author
                            or self._fuzzy_author_match(searched_author, creator_lower)
                        ):
                            author_match = True
                            matched_author = creator
                            break

                    if not author_match:
                        logger.debug(
                            f"Skipping book by different author: {title} by {creators[0]}"
                        )
                        continue

                    year = doc.get("year")
                    description = doc.get("description")

                    # Build download URLs
                    download_urls = [
                        f"{self.base_url}/download/{identifier}/{identifier}.epub",
                        f"{self.base_url}/download/{identifier}/{identifier}.pdf",
                        f"{self.base_url}/download/{identifier}/{identifier}.mobi",
                    ]

                    book = Book(
                        id=f"archive_{identifier}",
                        title=title,
                        author=matched_author,  # Use the matched author
                        source="archive",
                        download_urls=download_urls,
                        year=int(year) if year else None,
                        description=description,
                    )

                    books.append(book)

                except Exception as e:
                    logger.debug(f"Error processing Archive book: {e}")
                    continue

            logger.info(
                f"Found {len(books)} books on Internet Archive (after author filtering)"
            )

        except Exception as e:
            logger.error(f"Error searching Internet Archive: {e}")

        return books

    def _fuzzy_author_match(self, searched: str, found: str) -> bool:

        prefixes = [
            "dr ",
            "dr. ",
            "mr ",
            "mr. ",
            "mrs ",
            "mrs. ",
            "ms ",
            "ms. ",
            "prof ",
            "prof. ",
        ]
        suffixes = [" jr", " jr.", " sr", " sr.", " ii", " iii", " iv"]

        def normalize(name):
            name = name.lower().strip()
            # Remove punctuation except spaces
            name = re.sub(r"[^\w\s]", " ", name)
            # Remove extra spaces
            name = " ".join(name.split())

            for prefix in prefixes:
                prefix_clean = prefix.strip().replace(".", "")
                if name.startswith(prefix_clean + " "):
                    name = name[len(prefix_clean) :].strip()
            for suffix in suffixes:
                suffix_clean = suffix.strip().replace(".", "")
                if name.endswith(" " + suffix_clean):
                    name = name[: -len(suffix_clean)].strip()
            return name.strip()

        searched_norm = normalize(searched)
        found_norm = normalize(found)

        # Exact match after normalization
        if searched_norm == found_norm:
            return True

        # Split into words for flexible matching
        searched_words = set(searched_norm.split())
        found_words = set(found_norm.split())

        # Remove single letters and very common words
        common_fillers = {
            "a",
            "b",
            "c",
            "d",
            "e",
            "f",
            "g",
            "h",
            "i",
            "j",
            "k",
            "l",
            "m",
            "n",
            "o",
            "p",
            "q",
            "r",
            "s",
            "t",
            "u",
            "v",
            "w",
            "x",
            "y",
            "z",
            "de",
            "van",
            "von",
            "del",
            "la",
            "le",
        }
        searched_words = {
            w for w in searched_words if len(w) > 1 and w not in common_fillers
        }
        found_words = {w for w in found_words if len(w) > 1 and w not in common_fillers}

        if not searched_words or not found_words:
            return False

        # Match if at least 2 significant words match (or all words if less than 2)
        common_words = searched_words & found_words
        min_matches = min(2, len(searched_words))

        return len(common_words) >= min_matches

    def close(self):
        """Close session"""
        if self.session:
            self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        self.close()
        return False


class BookDownloader:
    """Enhanced book downloader with resilience"""

    def __init__(self, output_dir: str = "books"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "BookScraperBot/2.0 (Educational; Linux)"}
        )

    def download_book(self, book: Book) -> Optional[str]:
        """Download book with multi-URL fallback"""
        if not book or not book.download_urls:
            logger.warning(
                f"No download URLs for book: {book.title if book else 'Unknown'}"
            )
            return None

        # Handle author names (especially anthologies with multiple authors)
        author_name = book.author.strip()

        # Detect anthologies/collections with multiple authors
        if any(sep in author_name for sep in [",", ";", "/", " and ", " & "]):
            # Multiple authors - extract first or use "Various Authors"
            if "," in author_name:
                first_author = author_name.split(",")[0].strip()
            elif ";" in author_name:
                first_author = author_name.split(";")[0].strip()
            elif " and " in author_name:
                first_author = author_name.split(" and ")[0].strip()
            elif " & " in author_name:
                first_author = author_name.split(" & ")[0].strip()
            elif "/" in author_name:
                first_author = author_name.split("/")[0].strip()
            else:
                first_author = author_name

            # If still too long or multiple authors, use "Various Authors"
            if len(first_author) > 50 or not first_author:
                safe_author = "Various_Authors"
            else:
                safe_author = (
                    "".join(
                        c for c in first_author if c.isalnum() or c in (" ", "-", "_")
                    )
                    .strip()
                    .replace(" ", "_")[:50]
                )  # Max 50 chars
        else:
            # Single author
            safe_author = (
                "".join(c for c in author_name if c.isalnum() or c in (" ", "-", "_"))
                .strip()
                .replace(" ", "_")[:50]
            )  # Max 50 chars

        if not safe_author:
            safe_author = "Unknown_Author"

        # ✅ FIX: Prepare directory path but DON'T create it yet
        # Only create after we have a successful download
        author_dir = self.output_dir / safe_author

        # Sanitize title with length limit
        safe_title = "".join(
            c for c in book.title if c.isalnum() or c in (" ", "-", "_")
        ).strip()[
            :100
        ]  # Max 100 chars

        if not safe_title:
            safe_title = f"Book_{book.id}"[:100]

        # Try each URL
        for i, url in enumerate(book.download_urls, 1):
            try:
                logger.debug(f"Trying URL {i}/{len(book.download_urls)}: {url}")

                response = self.session.get(url, timeout=60, stream=True)

                if response.status_code == 403:
                    logger.debug(
                        f"URL {i} forbidden (403) - may require authentication or borrowing"
                    )
                    continue
                elif response.status_code == 404:
                    logger.debug(f"URL {i} not found (404)")
                    continue
                elif response.status_code == 401:
                    logger.debug(
                        f"URL {i} unauthorized (401) - may require account or borrowing"
                    )
                    continue
                elif response.status_code != 200:
                    logger.debug(f"URL {i} failed with status {response.status_code}")
                    continue

                # ✅ FIX: NOW create directory since we have successful HTTP response
                author_dir.mkdir(exist_ok=True, parents=True)

                # Check if it's actually a book (not an HTML error page or login page)
                content_type = response.headers.get("content-type", "")
                if "text/html" in content_type and "epub" not in url.lower():
                    # Check if it's a "borrow" page
                    if "borrow" in url.lower() or "loan" in url.lower():
                        logger.debug(f"URL {i} is a borrow page, not direct download")
                    else:
                        logger.debug(f"URL {i} returned HTML, not a book file")
                    continue

                # Determine file extension from URL or content-type
                if ".epub" in url:
                    ext = "epub"
                elif ".pdf" in url:
                    ext = "pdf"
                elif ".mobi" in url:
                    ext = "mobi"
                elif "epub" in content_type:
                    ext = "epub"
                elif "pdf" in content_type:
                    ext = "pdf"
                else:
                    ext = "epub"  # default

                # Create filename with length validation
                filename = f"{safe_author} - {safe_title}.{ext}"

                # Ensure total path length is within limits (255 chars for most filesystems)
                # Account for author_dir path length
                max_filename_length = 200  # Conservative limit
                if len(filename) > max_filename_length:
                    # Truncate title further if needed
                    available_for_title = (
                        max_filename_length - len(safe_author) - len(ext) - 5
                    )  # " - " + "."
                    if available_for_title > 20:  # Need reasonable minimum
                        truncated_title = safe_title[:available_for_title]
                        filename = f"{safe_author} - {truncated_title}.{ext}"
                    else:
                        # Use book ID as fallback for very long author names
                        filename = f"{safe_author[:50]} - {book.id}.{ext}"

                filepath = author_dir / filename

                # Final safety check - ensure complete path is valid
                try:
                    # Test if path is valid by checking length
                    str(filepath.resolve())
                    if len(str(filepath)) > 4096:  # Max path length on most systems
                        raise OSError("Path too long")
                except OSError:
                    # Fallback to simple naming
                    filename = f"{book.id}.{ext}"
                    filepath = author_dir / filename
                    logger.warning(
                        f"Using fallback filename due to path length: {filename}"
                    )

                # Download with progress bar
                total_size = int(response.headers.get("content-length", 0))

                with open(filepath, "wb") as f:
                    if total_size > 0:
                        with tqdm(
                            total=total_size,
                            unit="B",
                            unit_scale=True,
                            desc=f"Downloading {book.title[:30]}",
                        ) as pbar:
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                                    pbar.update(len(chunk))
                    else:
                        # No content-length header
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)

                # Verify file size
                if filepath.stat().st_size < 1000:  # Less than 1KB is suspicious
                    logger.debug(
                        f"Downloaded file too small ({filepath.stat().st_size} bytes), probably an error page"
                    )
                    filepath.unlink()
                    # ✅ FIX: Clean up empty directory
                    if author_dir.exists() and not any(author_dir.iterdir()):
                        author_dir.rmdir()
                    continue

                # Validate file format by checking magic bytes
                if not self._validate_file_format(filepath, ext):
                    logger.debug(
                        f"File validation failed - not a valid {ext.upper()} file"
                    )
                    filepath.unlink()
                    # ✅ FIX: Clean up empty directory
                    if author_dir.exists() and not any(author_dir.iterdir()):
                        author_dir.rmdir()
                    continue

                logger.info(f"✓ Successfully downloaded: {filename}")
                return str(filepath)

            except Exception as e:
                logger.debug(f"URL {i} failed: {e}")
                continue

        logger.warning(f"All URLs failed for book: {book.title}")

        # ✅ FIX: Final cleanup - remove empty directory if it was created
        if author_dir.exists() and not any(author_dir.iterdir()):
            logger.debug(f"Removing empty directory: {author_dir}")
            author_dir.rmdir()

        # Check if this was a borrowable book that might need special handling
        if hasattr(book, "is_borrowable") and book.is_borrowable:
            logger.info(f"Note: '{book.title}' may require borrowing from Open Library")
            logger.info(
                f"Visit: {book.borrow_url if hasattr(book, 'borrow_url') and book.borrow_url else 'https://openlibrary.org'}"
            )

        return None

    def _validate_file_format(self, filepath: Path, expected_ext: str) -> bool:
        """Validate file is actually the expected format by checking magic bytes"""
        try:
            with open(filepath, "rb") as f:
                header = f.read(1024)  # Read first 1KB

            # Check for HTML (error pages disguised as books)
            if (
                header.startswith(b"<!DOCTYPE")
                or header.startswith(b"<html")
                or b"<HTML" in header[:100]
            ):
                logger.warning(
                    f"Downloaded file is HTML error page, not a {expected_ext.upper()}"
                )
                # Try to extract error message
                header_str = header.decode("utf-8", errors="ignore")
                if "borrow" in header_str.lower():
                    logger.info("This book may require borrowing from Open Library")
                elif "login" in header_str.lower() or "sign in" in header_str.lower():
                    logger.info("This book may require authentication")
                return False

            # EPUB is a ZIP file with specific structure
            if expected_ext == "epub":
                # EPUB files are ZIP archives starting with PK
                if not header.startswith(b"PK\x03\x04"):
                    logger.warning(
                        f"File claims to be EPUB but doesn't have ZIP magic bytes (got: {header[:4]!r})"
                    )
                    return False
                # Check for mimetype file (required in EPUB)
                if b"mimetype" not in header and b"application/epub+zip" not in header:
                    logger.warning(
                        "File is ZIP but missing EPUB mimetype - may be corrupted"
                    )
                    # Still might be valid, don't fail
                return True

            # PDF files
            elif expected_ext == "pdf":
                if not header.startswith(b"%PDF-"):
                    logger.warning(
                        f"File claims to be PDF but doesn't have PDF magic bytes (got: {header[:5]!r})"
                    )
                    return False
                return True

            # MOBI files
            elif expected_ext == "mobi":
                # MOBI files can have various headers
                if header[60:68] == b"BOOKMOBI" or header[60:68] == b"TEXtREAd":
                    return True
                logger.warning(
                    f"File claims to be MOBI but doesn't have MOBI magic bytes"
                )
                return False

            # Unknown format - allow it
            return True

        except Exception as e:
            logger.debug(f"Error validating file format: {e}")
            return False

    def download_books_parallel(
        self, books: List[Book], max_workers: int = 5
    ) -> List[tuple]:
        """Download multiple books in parallel"""
        results = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all download tasks
            future_to_book = {
                executor.submit(self.download_book, book): book for book in books
            }

            # Process completed downloads
            for future in as_completed(future_to_book):
                book = future_to_book[future]
                try:
                    filepath = future.result()
                    results.append((book, filepath))
                except Exception as e:
                    logger.error(f"Error downloading {book.title}: {e}")
                    results.append((book, None))

        return results

    def close(self):
        """Close session"""
        if self.session:
            self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        self.close()
        return False


class LibGenScraper:
    """
    Library Genesis Scraper

    LEGAL NOTE: LibGen hosts copyrighted material. This is for educational purposes.
    Use responsibly and consider purchasing books you enjoy to support authors.
    """

    def __init__(self):
        self.mirrors = ["http://libgen.rs", "http://libgen.is", "http://libgen.st"]
        self.base_url = self.mirrors[0]  # Try first mirror
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
        )

    def search_author(self, author_name: str, limit: int = 50) -> List[dict]:
        """Search LibGen by author name"""
        books = []

        try:
            # LibGen search URL
            search_url = f"{self.base_url}/search.php"
            params = {
                "req": author_name,
                "lg_topic": "libgen",
                "open": 0,
                "view": "simple",
                "res": min(limit, 100),  # Max 100 per page
                "phrase": 1,  # Exact phrase
                "column": "author",
            }

            response = self.session.get(search_url, params=params, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")

            # Find all book rows in results table
            rows = soup.select("table.c tr")[1:]  # Skip header row

            for row in rows[:limit]:
                try:
                    cols = row.find_all("td")
                    if len(cols) < 10:
                        continue

                    # Extract book info
                    title_col = cols[2]
                    title_link = title_col.find("a")
                    title = (
                        title_link.text.strip()
                        if title_link
                        else title_col.text.strip()
                    )

                    author = cols[1].text.strip()
                    year = cols[4].text.strip()
                    pages = cols[5].text.strip()
                    language = cols[6].text.strip()
                    size = cols[7].text.strip()
                    extension = cols[8].text.strip().lower()

                    # Get download links
                    mirrors_col = cols[9]
                    mirror_links = mirrors_col.find_all("a")

                    download_urls = []
                    for link in mirror_links:
                        href = link.get("href", "")
                        if href:
                            download_urls.append(urljoin(self.base_url, href))

                    if not download_urls:
                        continue

                    # Create book object
                    book = {
                        "id": f"libgen_{hash(title + author)}",
                        "title": title,
                        "author": author,
                        "source": "libgen",
                        "download_urls": download_urls,
                        "format": extension,
                        "year": int(year) if year.isdigit() else None,
                        "language": language,
                        "pages": pages,
                        "size": size,
                    }

                    books.append(book)

                except Exception as e:
                    print(f"Error parsing LibGen row: {e}")
                    continue

            print(f"Found {len(books)} books on LibGen")
            return books

        except Exception as e:
            print(f"LibGen search error: {e}")
            # Try next mirror
            if len(self.mirrors) > 1:
                self.base_url = self.mirrors[1]
                print(f"Trying mirror: {self.base_url}")
                return self.search_author(author_name, limit)
            return []

    def get_download_url(self, mirror_url: str) -> Optional[str]:
        """Extract actual download URL from LibGen mirror page"""
        try:
            response = self.session.get(mirror_url, timeout=15)
            soup = BeautifulSoup(response.content, "html.parser")

            # Look for download link
            download_link = soup.find("a", string=re.compile(r"GET", re.I))
            if download_link:
                return download_link.get("href")

            # Alternative: look for direct link
            download_link = soup.find(
                "a", href=re.compile(r"\.(?:pdf|epub|mobi)$", re.I)
            )
            if download_link:
                return download_link.get("href")

            return None

        except Exception as e:
            print(f"Error getting download URL: {e}")
            return None


class ZLibraryScraper:
    """
    Z-Library Scraper

    LEGAL NOTE: Z-Library hosts copyrighted material. This is for educational purposes.
    Z-Library domains change frequently due to legal pressure.
    """

    def __init__(self):
        # Z-Library domains (these change frequently)
        self.domains = [
            "https://z-lib.gs",  # Official as of 2024
            "https://z-lib.io",
            "https://singlelogin.re",
        ]
        self.base_url = None
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
        )

        # Find working domain
        for domain in self.domains:
            try:
                response = self.session.get(domain, timeout=10)
                if response.status_code == 200:
                    self.base_url = domain
                    print(f"Using Z-Library domain: {domain}")
                    break
            except:
                continue

        if not self.base_url:
            print("Warning: Could not connect to Z-Library. Domain may have changed.")

    def search_author(self, author_name: str, limit: int = 50) -> List[dict]:
        """Search Z-Library by author"""
        if not self.base_url:
            print("Z-Library unavailable. Check for updated domains.")
            return []

        books = []

        try:
            # Z-Library search
            search_url = f"{self.base_url}/s/{quote(author_name)}"
            params = {"type": "phrase"}

            response = self.session.get(search_url, params=params, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")

            # Find book items (Z-Library structure)
            book_items = soup.select(".book-item, .bookRow, .resItemBox")

            for item in book_items[:limit]:
                try:
                    # Title and link
                    title_elem = item.select_one("h3 a, .itemCover a, .book-title a")
                    if not title_elem:
                        continue

                    title = title_elem.text.strip()
                    book_url = urljoin(self.base_url, title_elem.get("href", ""))

                    # Author
                    author_elem = item.select_one(".authors, .author")
                    author = author_elem.text.strip() if author_elem else author_name

                    # Year and other metadata
                    year_elem = item.select_one(".property_year, .year")
                    year = year_elem.text.strip() if year_elem else None

                    # Format
                    format_elem = item.select_one(".property_extension, .extension")
                    format_type = (
                        format_elem.text.strip().lower() if format_elem else "pdf"
                    )

                    book = {
                        "id": f"zlib_{hash(title + author)}",
                        "title": title,
                        "author": author,
                        "source": "zlibrary",
                        "download_urls": [
                            book_url
                        ],  # Will need to extract actual download
                        "format": format_type,
                        "year": int(year) if year and year.isdigit() else None,
                    }

                    books.append(book)

                except Exception as e:
                    print(f"Error parsing Z-Library item: {e}")
                    continue

            print(f"Found {len(books)} books on Z-Library")
            return books

        except Exception as e:
            print(f"Z-Library search error: {e}")
            return []

    def get_download_url(self, book_url: str) -> Optional[str]:
        """Get actual download URL from book page"""
        try:
            response = self.session.get(book_url, timeout=15)
            soup = BeautifulSoup(response.content, "html.parser")

            # Look for download button
            download_btn = soup.select_one(
                "a.dlButton, .addDownloadedBook, .btn-primary"
            )
            if download_btn:
                return urljoin(self.base_url, download_btn.get("href", ""))

            return None

        except Exception as e:
            print(f"Error getting Z-Library download URL: {e}")
            return None


class HooplaScraper:
    """
    Hoopla Digital Scraper (LEGITIMATE)

    Hoopla is a 100% legal library service with instant borrows.
    Requires a valid library card from a participating library.

    NOTE: Hoopla requires authentication and uses DRM.
    This scraper can search for books but actual borrowing requires:
    1. Valid library card
    2. Hoopla app or authenticated web session
    3. Books are DRM-protected (not downloadable as plain files)
    """

    def __init__(self):
        self.base_url = "https://www.hoopladigital.com"
        self.api_url = "https://hoopla-digital.hoopladigital.com/api"
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
        )

    def search_author(self, author_name: str, limit: int = 50) -> List[dict]:
        """
        Search Hoopla for books by author

        Note: This only searches. Actual borrowing requires:
        - Library card authentication
        - Hoopla app
        """
        books = []

        try:
            # Hoopla API search
            search_url = f"{self.api_url}/search"
            params = {"query": author_name, "kind": "EBOOKS", "limit": min(limit, 100)}

            response = self.session.get(search_url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            if "results" not in data:
                print("No results from Hoopla")
                return []

            for item in data["results"][:limit]:
                try:
                    title = item.get("title", "Unknown")
                    author = item.get("author", author_name)

                    # Hoopla-specific IDs
                    hoopla_id = item.get("id")
                    isbn = item.get("isbn")

                    # Get more details
                    format_type = "epub"  # Most Hoopla books are EPUB

                    book = {
                        "id": f"hoopla_{hoopla_id}",
                        "title": title,
                        "author": author,
                        "source": "hoopla",
                        "download_urls": [],  # Hoopla uses app-based borrowing
                        "format": format_type,
                        "isbn": isbn,
                        "is_borrowable": True,
                        "borrow_url": f"{self.base_url}/title/{hoopla_id}",
                        "requires_auth": True,
                        "note": "Requires Hoopla app and library card",
                    }

                    books.append(book)

                except Exception as e:
                    print(f"Error parsing Hoopla item: {e}")
                    continue

            print(f"Found {len(books)} books on Hoopla")
            print("Note: Hoopla books require authentication and the Hoopla app")
            return books

        except Exception as e:
            print(f"Hoopla search error: {e}")
            return []


# Integration helper functions
def integrate_scrapers():
    """
    Add these scrapers to your EnhancedBookScraperCLI class

    In your book_scraper.py, add to __init__:

    self.scrapers = {
        'gutenberg': GutenbergScraper(),
        'archive': InternetArchiveScraper(),
        'openlibrary': OpenLibraryScraper(),
        'standardebooks': StandardEbooksScraper(),
        'doab': DOABScraper(),

        # NEW: Add these
        'libgen': LibGenScraper(),
        'zlibrary': ZLibraryScraper(),
        'hoopla': HooplaScraper(),
    }
    """
    pass


if __name__ == "__main__":
    print("Book Scraper - Additional Sources")
    print("=" * 60)
    print()
    print("LEGAL DISCLAIMER:")
    print("- LibGen & Z-Library: Gray area sources")
    print("- Hoopla: 100% legitimate, requires library card")
    print()

    # Test LibGen
    print("Testing LibGen...")
    libgen = LibGenScraper()
    books = libgen.search_author("Mark Twain", limit=5)
    print(f"Found {len(books)} books\n")

    # Test Z-Library
    print("Testing Z-Library...")
    zlib = ZLibraryScraper()
    books = zlib.search_author("Mark Twain", limit=5)
    print(f"Found {len(books)} books\n")

    # Test Hoopla
    print("Testing Hoopla...")
    hoopla = HooplaScraper()
    books = hoopla.search_author("Mark Twain", limit=5)
    print(f"Found {len(books)} books\n")


class EnhancedBookScraperCLI:
    """Enhanced CLI with multiple source support"""

    def __init__(self):
        self.db = BookDatabase()
        self.downloader = BookDownloader()

        # Initialize all scrapers (including new sources)
        self.scrapers = {
            "gutenberg": GutenbergScraper(),
            "archive": InternetArchiveScraper(),
            "openlibrary": OpenLibraryScraper(),
            "standardebooks": StandardEbooksScraper(),
            "doab": DOABScraper(),
            # ✅ NEW: Additional sources
            "libgen": LibGenScraper(),
            "zlibrary": ZLibraryScraper(),
            "hoopla": HooplaScraper(),
        }

    def scrape_author(
        self,
        author_name: str,
        sources: List[str] = None,
        limit: int = 50,
        max_workers: int = 5,
    ):
        """Scrape books from multiple sources"""

        if sources is None:
            sources = list(self.scrapers.keys())

        # Validate sources
        invalid_sources = [s for s in sources if s not in self.scrapers]
        if invalid_sources:
            logger.error(f"Invalid sources: {invalid_sources}")
            logger.info(f"Available sources: {list(self.scrapers.keys())}")
            return

        all_books = []

        # Scrape from each source
        for source in sources:
            logger.info(f"\n{'='*70}")
            logger.info(f"Searching {source.upper()}")
            logger.info(f"{'='*70}\n")

            try:
                scraper = self.scrapers[source]

                # Different scrapers have different method names
                if source == "gutenberg":
                    books = scraper.get_author_books(author_name)
                else:
                    books = scraper.search_author(author_name, limit=limit)

                # Filter out already downloaded books
                new_books = [book for book in books if not self.db.book_exists(book.id)]

                logger.info(f"Found {len(books)} books ({len(new_books)} new)")
                all_books.extend(new_books[:limit])

            except Exception as e:
                logger.error(f"Error scraping {source}: {e}")
                continue

        if not all_books:
            logger.warning("No new books found across all sources")
            return

        # Download books
        logger.info(f"\n{'='*70}")
        logger.info(f"Downloading {len(all_books)} books")
        logger.info(f"{'='*70}\n")

        results = self.downloader.download_books_parallel(all_books, max_workers)

        # Update database
        successful = 0
        for book, filepath in results:
            if filepath:
                self.db.add_book(book, filepath)
                successful += 1

                # Track if borrowable
                if hasattr(book, "is_borrowable") and book.is_borrowable:
                    due_date = datetime.now() + timedelta(days=14)
                    self.db.add_borrow(book.id, due_date)
            else:
                # Add to database without file path (failed download)
                self.db.add_book(book, None)

        # Print summary
        logger.info(f"\n{'='*70}")
        logger.info(f"DOWNLOAD SUMMARY")
        logger.info(f"{'='*70}")
        logger.info(f"Total found: {len(all_books)}")
        logger.info(f"Successfully downloaded: {successful}")
        logger.info(f"Failed: {len(all_books) - successful}")

        # Check if there were borrowable books that failed
        failed_borrowable = [
            book
            for book, filepath in results
            if not filepath and hasattr(book, "is_borrowable") and book.is_borrowable
        ]

        if failed_borrowable:
            logger.info(f"\n{'='*70}")
            logger.info(f"BORROWABLE BOOKS (Require Open Library Account)")
            logger.info(f"{'='*70}")
            logger.info(f"Found {len(failed_borrowable)} books that require borrowing:")
            for book in failed_borrowable[:5]:  # Show first 5
                logger.info(f"  - {book.title} by {book.author}")
                if hasattr(book, "borrow_url") and book.borrow_url:
                    logger.info(f"    Borrow at: {book.borrow_url}")
            if len(failed_borrowable) > 5:
                logger.info(f"  ... and {len(failed_borrowable) - 5} more")
            logger.info(f"\nTo borrow these books:")
            logger.info(f"  1. Create free account at https://openlibrary.org")
            logger.info(f"  2. Visit book page and click 'Borrow'")
            logger.info(f"  3. Read online or download for 14 days")

        # Show stats
        self.show_stats()

    def show_stats(self):
        """Display database statistics"""
        stats = self.db.get_stats()

        print(f"\n{'='*70}")
        print("LIBRARY STATISTICS")
        print(f"{'='*70}")
        print(f"Total downloaded: {stats['total_downloaded']} books")
        print(f"Total size: {stats['total_size_mb']:.2f} MB")
        print(f"\nBy source:")
        for source, count in stats["by_source"].items():
            print(f"  {source:15} {count:5} books")

    def list_borrows(self):
        """List all active borrowed books"""
        borrows = self.db.get_active_borrows()

        if not borrows:
            print("No active borrows")
            return

        print(f"\n{'='*70}")
        print("ACTIVE BORROWS")
        print(f"{'='*70}\n")

        for borrow in borrows:
            due_date = datetime.fromisoformat(borrow["due_date"])
            days_left = (due_date - datetime.now()).days

            print(f"Title: {borrow['title']}")
            print(f"Author: {borrow['author']}")
            print(f"Source: {borrow['source']}")
            print(f"Due: {due_date.strftime('%Y-%m-%d')} ({days_left} days left)")
            print()

    def close(self):
        """Close all resources"""
        if hasattr(self, "db"):
            self.db.close()
        if hasattr(self, "downloader"):
            self.downloader.close()
        for scraper in self.scrapers.values():
            if hasattr(scraper, "close"):
                scraper.close()

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        self.close()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Enhanced Book Scraper - Download free books from multiple sources",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Search all sources
  %(prog)s "Neil Gaiman"
  
  # Search specific sources
  %(prog)s "Brandon Sanderson" --sources openlibrary archive
  
  # Limit results
  %(prog)s "Mark Twain" --limit 10
  
  # Show statistics
  %(prog)s --stats
  
  # List borrowed books
  %(prog)s --borrows
  
Available sources:
  LEGITIMATE:
  - gutenberg     : Project Gutenberg (classic public domain)
  - archive       : Internet Archive (wide variety)
  - openlibrary   : Open Library (modern books, borrowing)
  - standardebooks: Standard Ebooks (high-quality public domain)
  - doab          : Directory of Open Access Books (academic)
  - hoopla        : Hoopla Digital (instant borrows, requires library card)
  
  ADDITIONAL (use responsibly):
  - libgen        : Library Genesis (gray area, modern books)
  - zlibrary      : Z-Library (gray area, large collection)
        """,
    )

    parser.add_argument("author", nargs="?", help="Author name to search for")
    parser.add_argument(
        "--sources",
        "-s",
        nargs="+",
        choices=[
            "gutenberg",
            "archive",
            "openlibrary",
            "standardebooks",
            "doab",
            # ✅ NEW: Additional sources
            "libgen",
            "zlibrary",
            "hoopla",
            "all",
        ],
        default=["all"],
        help="Sources to search (default: all)",
    )
    parser.add_argument(
        "--limit", "-l", type=int, default=50, help="Max books per source (default: 50)"
    )
    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=5,
        help="Parallel download workers (default: 5)",
    )
    parser.add_argument("--stats", action="store_true", help="Show library statistics")
    parser.add_argument(
        "--borrows", action="store_true", help="List active borrowed books"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    with EnhancedBookScraperCLI() as cli:
        # Handle different modes
        if args.stats:
            cli.show_stats()
        elif args.borrows:
            cli.list_borrows()
        elif args.author:
            # Determine sources
            sources = None if "all" in args.sources else args.sources

            # Scrape and download
            cli.scrape_author(
                args.author,
                sources=sources,
                limit=args.limit,
                max_workers=args.workers,
            )
        else:
            parser.print_help()


if __name__ == "__main__":
    main()
