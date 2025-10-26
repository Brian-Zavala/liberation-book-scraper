#!/usr/bin/env python3
"""
Multi-source book scraper with progress tracking, metadata extraction, and Kindle conversion
Supports: Project Gutenberg, Archive.org, Standard Ebooks
"""

import requests
from bs4 import BeautifulSoup
import re
from pathlib import Path
import time
import json
import sqlite3
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict
from urllib.parse import urljoin, quote
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import subprocess
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class Book:
    """Book metadata"""
    id: str
    title: str
    author: str
    source: str
    year: Optional[int] = None
    language: str = "en"
    subjects: List[str] = None
    download_url: Optional[str] = None
    download_urls: List[str] = None  # Multiple URL fallbacks
    cover_url: Optional[str] = None
    downloaded: bool = False
    
    def __post_init__(self):
        if self.subjects is None:
            self.subjects = []
        if self.download_urls is None:
            # If download_urls not provided, create list from single URL
            if self.download_url:
                self.download_urls = [self.download_url]
            else:
                self.download_urls = []


class BookDatabase:
    """SQLite database to track downloaded books"""
    
    def __init__(self, db_path="books.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.create_tables()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute("""
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
                downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()
    
    def add_book(self, book: Book, file_path: str = None, file_hash: str = None):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO books 
            (id, title, author, source, year, language, subjects, download_url, 
             cover_url, downloaded, file_path, file_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            book.id, book.title, book.author, book.source, book.year,
            book.language, json.dumps(book.subjects), book.download_url,
            book.cover_url, book.downloaded, file_path, file_hash
        ))
        self.conn.commit()
    
    def is_downloaded(self, book_id: str) -> bool:
        cursor = self.conn.cursor()
        result = cursor.execute(
            "SELECT downloaded FROM books WHERE id = ?", (book_id,)
        ).fetchone()
        return result[0] if result else False
    
    def get_all_books(self) -> List[Dict]:
        cursor = self.conn.cursor()
        results = cursor.execute("SELECT * FROM books").fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in results]
    
    def close(self):
        self.conn.close()


class GutenbergScraper:
    """Project Gutenberg scraper"""
    
    def __init__(self):
        self.base_url = "https://www.gutenberg.org"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) BookScraper/1.0'
        })
    
    def search_author(self, author_name: str) -> Optional[str]:
        """Search for author and return their bibliography page"""
        # Try direct author page
        author_slug = author_name.lower().replace(' ', '_').replace(',', '')
        search_url = f"{self.base_url}/ebooks/author/{author_slug}"
        
        try:
            response = self.session.get(search_url, timeout=10)
            if response.status_code == 200:
                return response.url
        except Exception as e:
            logger.error(f"Error searching for author: {e}")
        
        return None
    
    def get_book_metadata(self, book_id: str) -> Optional[Book]:
        """Get detailed metadata for a book"""
        url = f"{self.base_url}/ebooks/{book_id}"
        
        try:
            response = self.session.get(url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            title = soup.find('h1', itemprop='name')
            title = title.get_text(strip=True) if title else f"Book {book_id}"
            
            author = soup.find('a', itemprop='creator')
            author = author.get_text(strip=True) if author else "Unknown"
            
            # Get subjects
            subjects = []
            for subject in soup.find_all('a', href=re.compile(r'/ebooks/bookshelf/')):
                subjects.append(subject.get_text(strip=True))
            
            # Get language
            language = soup.find('tr', {'property': 'dcterms:language'})
            language = language.find('td').get_text(strip=True) if language else "en"
            
            # Construct multiple download URLs as fallbacks
            download_urls = [
                # Try EPUB with images first (best quality)
                f"{self.base_url}/ebooks/{book_id}.epub3.images",
                # Then EPUB without images (smaller, always available)
                f"{self.base_url}/ebooks/{book_id}.epub.noimages",
                # Then old EPUB format
                f"{self.base_url}/ebooks/{book_id}.epub.images",
                # Direct file download as last resort
                f"{self.base_url}/files/{book_id}/{book_id}-0.epub",
                # Alternative mirror structure
                f"{self.base_url}/files/{book_id}/{book_id}.epub",
            ]
            
            return Book(
                id=f"gutenberg_{book_id}",
                title=title,
                author=author,
                source="gutenberg",
                language=language,
                subjects=subjects,
                download_urls=download_urls,
                download_url=download_urls[0]  # Keep for backwards compatibility
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
            soup = BeautifulSoup(response.content, 'html.parser')
            
            books = []
            book_links = soup.find_all('li', class_='booklink')
            
            for link in tqdm(book_links, desc="Fetching metadata"):
                book_link = link.find('a', href=re.compile(r'/ebooks/\d+'))
                if book_link:
                    book_id = re.search(r'/ebooks/(\d+)', book_link['href'])
                    if book_id:
                        book = self.get_book_metadata(book_id.group(1))
                        if book:
                            books.append(book)
                        time.sleep(0.5)  # Rate limiting
            
            return books
        
        except Exception as e:
            logger.error(f"Error getting books for author: {e}")
            return []


class ArchiveScraper:
    """Internet Archive scraper"""
    
    def __init__(self):
        self.base_url = "https://archive.org"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) BookScraper/1.0'
        })
    
    def search_author(self, author_name: str, limit: int = 50) -> List[Book]:
        """Search for books by author"""
        search_url = f"{self.base_url}/advancedsearch.php"
        params = {
            'q': f'creator:"{author_name}" AND mediatype:texts',
            'fl[]': ['identifier', 'title', 'creator', 'year', 'subject'],
            'sort[]': 'downloads desc',
            'rows': limit,
            'page': 1,
            'output': 'json'
        }
        
        try:
            response = self.session.get(search_url, params=params, timeout=10)
            data = response.json()
            
            books = []
            for doc in data['response']['docs']:
                identifier = doc['identifier']
                
                # Multiple URL fallbacks for Archive.org
                download_urls = [
                    # Try EPUB first
                    f"{self.base_url}/download/{identifier}/{identifier}.epub",
                    # Then PDF
                    f"{self.base_url}/download/{identifier}/{identifier}.pdf",
                    # Then MOBI
                    f"{self.base_url}/download/{identifier}/{identifier}.mobi",
                    # Alternative naming
                    f"{self.base_url}/download/{identifier}/{identifier}_text.pdf",
                ]
                
                book = Book(
                    id=f"archive_{identifier}",
                    title=doc.get('title', 'Unknown'),
                    author=doc.get('creator', ['Unknown'])[0] if isinstance(doc.get('creator'), list) else doc.get('creator', 'Unknown'),
                    source="archive",
                    year=doc.get('year'),
                    subjects=doc.get('subject', []) if isinstance(doc.get('subject'), list) else [doc.get('subject', '')],
                    download_urls=download_urls,
                    download_url=download_urls[0]  # Keep for backwards compatibility
                )
                books.append(book)
            
            return books
        
        except Exception as e:
            logger.error(f"Error searching Archive.org: {e}")
            return []


class BookDownloader:
    """Download and convert books"""
    
    def __init__(self, output_dir="books", db: Optional[BookDatabase] = None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.db = db
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) BookScraper/1.0'
        })
    
    def sanitize_filename(self, filename: str) -> str:
        """Clean filename for filesystem"""
        return re.sub(r'[<>:"/\\|?*]', '_', filename)[:200]
    
    def calculate_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def download_book(self, book: Book, format: str = 'epub') -> Optional[Path]:
        """Download a single book, trying multiple URLs if needed"""
        if self.db and self.db.is_downloaded(book.id):
            logger.info(f"Already downloaded: {book.title}")
            return None
        
        filename = self.sanitize_filename(f"{book.author} - {book.title}")
        
        # Determine file extension from URLs or use provided format
        file_extension = format
        output_path = self.output_dir / f"{filename}.{file_extension}"
        
        if output_path.exists():
            logger.info(f"File already exists: {output_path}")
            return output_path
        
        # Get all URLs to try
        urls_to_try = book.download_urls if book.download_urls else [book.download_url]
        
        # Filter out None values
        urls_to_try = [url for url in urls_to_try if url]
        
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
                
                # Check if response is successful
                if response.status_code != 200:
                    logger.warning(f"URL {i} failed with status {response.status_code}, trying next...")
                    continue
                
                # Check if we got actual content (not an error page)
                content_type = response.headers.get('content-type', '').lower()
                if 'text/html' in content_type and 'epub' in url:
                    # Likely an error page, not actual book
                    logger.warning(f"URL {i} returned HTML instead of book, trying next...")
                    continue
                
                # Adjust output path extension based on actual content
                if 'application/pdf' in content_type and not output_path.suffix == '.pdf':
                    output_path = output_path.with_suffix('.pdf')
                elif 'application/epub' in content_type and not output_path.suffix == '.epub':
                    output_path = output_path.with_suffix('.epub')
                
                total_size = int(response.headers.get('content-length', 0))
                
                # Download with progress bar
                with open(output_path, 'wb') as f, tqdm(
                    desc=f"{book.title[:50]}",
                    total=total_size,
                    unit='B',
                    unit_scale=True,
                    unit_divisor=1024,
                    disable=total_size == 0  # Disable if size unknown
                ) as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        pbar.update(len(chunk))
                
                # Verify file was downloaded and has content
                if not output_path.exists() or output_path.stat().st_size < 1000:
                    logger.warning(f"Downloaded file too small or missing, trying next URL...")
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
        logger.error(f"✗ Failed to download {book.title} after trying {len(urls_to_try)} URLs. Last error: {last_error}")
        return None
    
    def download_books(self, books: List[Book], max_workers: int = 3) -> List[Path]:
        """Download multiple books in parallel"""
        downloaded = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_book = {
                executor.submit(self.download_book, book): book 
                for book in books
            }
            
            for future in as_completed(future_to_book):
                result = future.result()
                if result:
                    downloaded.append(result)
        
        return downloaded
    
    def convert_to_kindle(self, input_file: Path, output_format: str = 'mobi') -> Optional[Path]:
        """Convert ebook to Kindle format using Calibre"""
        output_path = input_file.with_suffix(f'.{output_format}')
        
        if output_path.exists():
            logger.info(f"Converted file already exists: {output_path}")
            return output_path
        
        try:
            logger.info(f"Converting {input_file.name} to {output_format}")
            subprocess.run([
                'ebook-convert',
                str(input_file),
                str(output_path),
                '--output-profile=kindle',
                '--no-inline-toc',
                '--max-toc-links=0'
            ], check=True, capture_output=True, text=True)
            
            logger.info(f"✓ Converted: {output_path}")
            return output_path
        
        except subprocess.CalledProcessError as e:
            logger.error(f"✗ Conversion failed: {e.stderr}")
            return None
        except FileNotFoundError:
            logger.error("ebook-convert not found. Install Calibre: sudo pacman -S calibre")
            return None
    
    def batch_convert(self, files: List[Path], output_format: str = 'mobi') -> List[Path]:
        """Convert multiple files"""
        converted = []
        for file in tqdm(files, desc="Converting to Kindle format"):
            result = self.convert_to_kindle(file, output_format)
            if result:
                converted.append(result)
            time.sleep(0.5)
        return converted


class BookScraperCLI:
    """Main CLI interface"""
    
    def __init__(self):
        self.db = BookDatabase()
        self.downloader = BookDownloader(db=self.db)
        self.gutenberg = GutenbergScraper()
        self.archive = ArchiveScraper()
    
    def scrape_author(self, author_name: str, source: str = 'gutenberg', 
                     limit: Optional[int] = None, convert: bool = True):
        """Main scraping workflow"""
        logger.info(f"Searching for '{author_name}' on {source}")
        
        # Get books
        if source == 'gutenberg':
            books = self.gutenberg.get_author_books(author_name)
        elif source == 'archive':
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
    
    def show_stats(self):
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
        by_author = {}
        for book in books:
            author = book['author']
            by_author.setdefault(author, []).append(book)
        
        print("Books by author:")
        for author, author_books in sorted(by_author.items(), key=lambda x: len(x[1]), reverse=True):
            print(f"  {author}: {len(author_books)} books")
    
    def close(self):
        self.db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Multi-source book scraper")
    parser.add_argument('author', help='Author name to search for')
    parser.add_argument('-s', '--source', choices=['gutenberg', 'archive'], 
                       default='gutenberg', help='Source to scrape from')
    parser.add_argument('-l', '--limit', type=int, help='Limit number of books')
    parser.add_argument('--no-convert', action='store_true', 
                       help='Skip Kindle conversion')
    parser.add_argument('--stats', action='store_true', 
                       help='Show download statistics')
    
    args = parser.parse_args()
    
    cli = BookScraperCLI()
    
    try:
        if args.stats:
            cli.show_stats()
        else:
            cli.scrape_author(
                args.author, 
                source=args.source, 
                limit=args.limit,
                convert=not args.no_convert
            )
    finally:
        cli.close()
