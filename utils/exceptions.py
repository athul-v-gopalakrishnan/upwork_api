class ScraperError(Exception):
    """Base exception for scraper-related errors."""
    pass

class PrivateProfileError(ScraperError):
    """Raised when a profile is private and cannot be accessed."""
    pass