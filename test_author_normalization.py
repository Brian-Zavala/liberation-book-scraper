#!/usr/bin/env python3
"""
Author Name Normalization Examples
Shows how the scraper handles various input formats
"""

from book_scraper import normalize_author_name

print("=" * 70)
print("Author Name Normalization Examples")
print("=" * 70)
print()

test_cases = [
    "  mark   twain  ",  # Extra whitespace
    "CHARLES DICKENS",  # All uppercase
    "jane austen",  # All lowercase
    "Edgar Allan Poe",  # Already correct
    "  MARK  TWAIN  ",  # Multiple issues
    "h.g. wells",  # Initials
    "j.r.r. tolkien",  # Multiple initials
    "e e cummings",  # Unusual formatting
    "Alexandre Dumas",  # Accented characters
]

print("Input → Normalized Output")
print("-" * 70)

for name in test_cases:
    normalized = normalize_author_name(name)
    print(f"'{name}' → '{normalized}'")

print()
print("=" * 70)
print("All author names are automatically normalized when scraping!")
print("=" * 70)
print()
print("Examples of usage:")
print()
print("  ./book_scraper.py 'MARK TWAIN'")
print("  ./book_scraper.py '  charles dickens  '")
print("  ./book_scraper.py 'jane austen'")
print()
print("All work the same way! ✓")
