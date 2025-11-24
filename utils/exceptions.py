class ScraperError(Exception):
    """Base exception for scraper-related errors.

    Parameters
    ----------
    message : str | None
        Human readable message for the error. If None, a default message will be used.
    code : int | None
        Optional numeric error code.
    context : dict | None
        Optional dict with additional context (e.g. {'url': url}).
    """
    def __init__(self, message: str | None = None, code: int | None = None, context: dict | None = None):
        default = "An error occurred in the scraper."
        self.message = message or default
        self.code = code
        self.context = context
        # Keep Exception base behavior (message available via args)
        super().__init__(self.message)

    def __str__(self) -> str:
        parts = [self.message]
        if self.code is not None:
            parts.append(f"(code={self.code})")
        if self.context:
            parts.append(f"context={self.context}")
        return " ".join(parts)


class PrivateProfileError(ScraperError):
    """Raised when a profile is private and cannot be accessed."""
    def __init__(self, message: str | None = None, code: int | None = None, context: dict | None = None):
        default = "Private job posting or structure changed."
        super().__init__(message or default, code=code or 403, context=context)


class LoginPageNotFound(ScraperError):
    """Raised when the login / expected page is not found."""
    def __init__(self, message: str | None = None, code: int | None = None, context: dict | None = None):
        default = "Login page not found or page structure changed."
        super().__init__(message or default, code=code or 404, context=context)