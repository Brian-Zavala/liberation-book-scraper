#!/usr/bin/env python3
"""
Test script to verify installation and functionality
"""

import sys
import subprocess
from pathlib import Path


def check_python_version():
    """Check Python version"""
    print("Checking Python version...", end=" ")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"✓ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"✗ Python {version.major}.{version.minor} (need 3.8+)")
        return False


def check_dependencies():
    """Check if required Python packages are installed"""
    required = [
        'requests',
        'bs4',  # beautifulsoup4
        'tqdm',
        'PIL',  # Pillow
    ]
    
    print("\nChecking Python dependencies:")
    all_good = True
    
    for package in required:
        try:
            __import__(package)
            print(f"  ✓ {package}")
        except ImportError:
            print(f"  ✗ {package} (missing)")
            all_good = False
    
    return all_good


def check_calibre():
    """Check if Calibre is installed"""
    print("\nChecking Calibre installation...", end=" ")
    try:
        result = subprocess.run(
            ['ebook-convert', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.split()[0]
            print(f"✓ Calibre {version}")
            return True
        else:
            print("✗ Not working")
            return False
    except FileNotFoundError:
        print("✗ Not installed")
        print("  Install with: sudo pacman -S calibre")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def check_network():
    """Check network connectivity to sources"""
    print("\nChecking network connectivity:")
    
    sources = [
        ('Project Gutenberg', 'https://www.gutenberg.org'),
        ('Internet Archive', 'https://archive.org'),
    ]
    
    import requests
    all_good = True
    
    for name, url in sources:
        try:
            response = requests.head(url, timeout=5)
            if response.status_code < 400:
                print(f"  ✓ {name}")
            else:
                print(f"  ✗ {name} (status {response.status_code})")
                all_good = False
        except Exception as e:
            print(f"  ✗ {name} ({str(e)[:30]}...)")
            all_good = False
    
    return all_good


def check_files():
    """Check if all required files exist"""
    print("\nChecking files:")
    
    required_files = [
        'book_scraper.py',
        'kindle_emailer.py',
        'batch_operations.py',
        'requirements.txt',
        'README.md',
    ]
    
    all_good = True
    for file in required_files:
        path = Path(file)
        if path.exists():
            print(f"  ✓ {file}")
        else:
            print(f"  ✗ {file} (missing)")
            all_good = False
    
    return all_good


def test_basic_functionality():
    """Test basic scraper functionality"""
    print("\nTesting basic functionality:")
    
    try:
        from book_scraper import GutenbergScraper, Book
        
        # Test scraper initialization
        scraper = GutenbergScraper()
        print("  ✓ Scraper initialization")
        
        # Test Book dataclass
        test_book = Book(
            id="test_1",
            title="Test Book",
            author="Test Author",
            source="test"
        )
        print("  ✓ Book dataclass")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def test_database():
    """Test database functionality"""
    print("\nTesting database:")
    
    try:
        from book_scraper import BookDatabase, Book
        
        # Create test database
        db = BookDatabase("test.db")
        
        # Test adding a book
        test_book = Book(
            id="test_1",
            title="Test Book",
            author="Test Author",
            source="test"
        )
        db.add_book(test_book)
        
        # Test retrieval
        is_downloaded = db.is_downloaded("test_1")
        
        db.close()
        
        # Cleanup
        Path("test.db").unlink()
        
        print("  ✓ Database operations")
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        # Cleanup on error
        if Path("test.db").exists():
            Path("test.db").unlink()
        return False


def show_next_steps():
    """Show what to do next"""
    print("\n" + "="*60)
    print("NEXT STEPS")
    print("="*60)
    
    print("\n1. Quick test:")
    print("   ./book_scraper.py 'Mark Twain' --limit 1")
    
    print("\n2. Set up email (optional):")
    print("   ./kindle_emailer.py --create-config")
    print("   # Edit email_config.json with your credentials")
    
    print("\n3. Try examples:")
    print("   python examples.py 1")
    
    print("\n4. Web interface:")
    print("   python web_ui.py")
    print("   # Open http://localhost:5000")
    
    print("\n5. Read documentation:")
    print("   cat README.md")
    print("   cat CHEATSHEET.sh")


def main():
    print("="*60)
    print("BOOK SCRAPER - INSTALLATION TEST")
    print("="*60)
    
    results = []
    
    results.append(("Python version", check_python_version()))
    results.append(("Dependencies", check_dependencies()))
    results.append(("Calibre", check_calibre()))
    results.append(("Network", check_network()))
    results.append(("Files", check_files()))
    results.append(("Basic functionality", test_basic_functionality()))
    results.append(("Database", test_database()))
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓" if result else "✗"
        print(f"{status} {name}")
    
    print(f"\nPassed: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 All tests passed! You're ready to go.")
        show_next_steps()
    elif passed >= total - 1:
        print("\n⚠️  Almost ready! Fix the failing test above.")
    else:
        print("\n❌ Several tests failed. Check the output above.")
        print("\nCommon fixes:")
        print("  - Install dependencies: pip install -r requirements.txt")
        print("  - Install Calibre: sudo pacman -S calibre")
        print("  - Check internet connection")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
