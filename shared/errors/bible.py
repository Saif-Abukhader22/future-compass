from enum import Enum


class BibleCode(str, Enum):
    # General categories
    BOOK_NOT_FOUND = "book_not_found"
    BOOKS_NOT_FOUND = "bible_books_not_found"
    VERSE_NOT_FOUND = "verse_not_found"
    BIBLE_NOT_FOUND = "bible_version_not_found"
    INTERNET_SERVER_ERROR = "internal_server_error"
    CHAPTER_NOT_FOUND = "chapter_not_found"
