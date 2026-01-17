"""URL store for collecting and managing conference URLs."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel
from rich.console import Console

console = Console()

STORE_DIR = Path(__file__).parent.parent.parent / ".cache"
STORE_FILE = STORE_DIR / "url_store.json"


class StoredURL(BaseModel):
    """A URL entry in the store."""

    url: str
    source: str  # Where we got this URL from
    name: Optional[str] = None  # Conference name if known
    cfp_url: Optional[str] = None  # Direct CFP submission URL if different

    # Extraction status
    extracted: bool = False
    extraction_failed: bool = False
    last_attempt: Optional[float] = None

    # Retry tracking
    retry_count: int = 0  # Number of retry attempts
    max_retries_reached: bool = False  # True if we've given up

    # Fetch method tracking (spa vs classic)
    fetch_method: Optional[str] = None  # "httpx" or "playwright"
    is_spa: bool = False  # True if needed JS rendering

    # Error tracking
    http_status: Optional[int] = None  # Last HTTP status code
    error_reason: Optional[str] = None  # "404", "timeout", "connection", etc.

    # Timestamps
    added_at: float

    class Config:
        extra = "ignore"


# Error classification for retry logic
RETRYABLE_ERRORS = {
    "timeout",       # Server slow, might recover
    "connection",    # Network glitch
    "429",           # Rate limited
    "500",           # Server error
    "502",           # Bad gateway
    "503",           # Service unavailable
    "504",           # Gateway timeout
    "sslerror",      # SSL issues (sometimes transient)
}

PERMANENT_ERRORS = {
    "404",           # Page doesn't exist
    "403",           # Forbidden
    "401",           # Unauthorized
    "410",           # Gone
    "low_confidence",  # Page exists but no CFP data (won't improve without code changes)
}

DEFAULT_MAX_RETRIES = 3
RETRY_BACKOFF_HOURS = [1, 6, 24]  # Wait 1h, 6h, 24h between retries


def is_retryable_error(error_reason: Optional[str]) -> bool:
    """Check if an error is worth retrying."""
    if not error_reason:
        return True  # Unknown error, try again
    return error_reason.lower() in RETRYABLE_ERRORS


def get_retry_delay_hours(retry_count: int) -> float:
    """Get delay in hours before next retry (exponential backoff)."""
    if retry_count >= len(RETRY_BACKOFF_HOURS):
        return RETRY_BACKOFF_HOURS[-1]
    return RETRY_BACKOFF_HOURS[retry_count]


class URLStore:
    """Manages a persistent store of conference URLs for extraction."""

    def __init__(self, store_path: Optional[Path] = None):
        self.store_path = store_path or STORE_FILE
        self._urls: dict[str, StoredURL] = {}
        self._load()

    def _load(self) -> None:
        """Load store from disk."""
        if self.store_path.exists():
            try:
                with open(self.store_path) as f:
                    data = json.load(f)
                for url_data in data.get("urls", []):
                    entry = StoredURL.model_validate(url_data)
                    self._urls[entry.url] = entry
                console.print(f"[dim]Loaded {len(self._urls)} URLs from store[/dim]")
            except Exception as e:
                console.print(f"[yellow]Failed to load URL store: {e}[/yellow]")
                self._urls = {}

    def _save(self) -> None:
        """Save store to disk."""
        STORE_DIR.mkdir(parents=True, exist_ok=True)
        with open(self.store_path, "w") as f:
            json.dump({
                "updated_at": datetime.now().timestamp(),
                "urls": [entry.model_dump() for entry in self._urls.values()],
            }, f, indent=2)

    def add(
        self,
        url: str,
        source: str,
        name: Optional[str] = None,
        cfp_url: Optional[str] = None,
    ) -> bool:
        """Add a URL to the store.

        Returns True if URL was new, False if already existed.
        """
        # Normalize URL
        url = url.rstrip("/")

        if url in self._urls:
            # Update name/cfp_url if we have better info
            existing = self._urls[url]
            if name and not existing.name:
                existing.name = name
            if cfp_url and not existing.cfp_url:
                existing.cfp_url = cfp_url
            return False

        self._urls[url] = StoredURL(
            url=url,
            source=source,
            name=name,
            cfp_url=cfp_url,
            added_at=datetime.now().timestamp(),
        )
        return True

    def add_many(
        self,
        urls: list[dict],
        source: str,
    ) -> int:
        """Add multiple URLs to the store.

        Args:
            urls: List of dicts with 'url' and optional 'name', 'cfp_url'
            source: Source identifier

        Returns:
            Number of new URLs added
        """
        new_count = 0
        for url_info in urls:
            if isinstance(url_info, str):
                url_info = {"url": url_info}

            if self.add(
                url=url_info["url"],
                source=source,
                name=url_info.get("name"),
                cfp_url=url_info.get("cfp_url"),
            ):
                new_count += 1

        self._save()
        return new_count

    def mark_extracted(self, url: str, fetch_method: str = None, is_spa: bool = False) -> None:
        """Mark URL as successfully extracted."""
        url = url.rstrip("/")
        if url in self._urls:
            self._urls[url].extracted = True
            self._urls[url].extraction_failed = False
            self._urls[url].last_attempt = datetime.now().timestamp()
            if fetch_method:
                self._urls[url].fetch_method = fetch_method
            self._urls[url].is_spa = is_spa
            self._save()

    def mark_failed(
        self,
        url: str,
        http_status: Optional[int] = None,
        error_reason: Optional[str] = None,
        is_retry: bool = False,
    ) -> None:
        """Mark URL as extraction failed with error details.

        Args:
            url: The URL that failed
            http_status: HTTP status code if available
            error_reason: Error type (timeout, 404, low_confidence, etc.)
            is_retry: True if this was a retry attempt (increments counter)
        """
        url = url.rstrip("/")
        if url in self._urls:
            entry = self._urls[url]
            entry.extraction_failed = True
            entry.last_attempt = datetime.now().timestamp()

            if http_status:
                entry.http_status = http_status
            if error_reason:
                entry.error_reason = error_reason

            # Increment retry count if this was a retry
            if is_retry:
                entry.retry_count += 1

            # Mark as permanently failed if error is not retryable or max retries reached
            if not is_retryable_error(error_reason) or entry.retry_count >= DEFAULT_MAX_RETRIES:
                entry.max_retries_reached = True

            self._save()

    def get_pending(self, limit: Optional[int] = None) -> list[StoredURL]:
        """Get URLs that haven't been extracted yet."""
        pending = [
            entry for entry in self._urls.values()
            if not entry.extracted and not entry.extraction_failed
        ]
        # Sort by added_at (oldest first)
        pending.sort(key=lambda x: x.added_at)

        if limit:
            pending = pending[:limit]

        return pending

    def get_failed(self) -> list[StoredURL]:
        """Get all URLs that failed extraction."""
        return [
            entry for entry in self._urls.values()
            if entry.extraction_failed
        ]

    def get_retryable(self, limit: Optional[int] = None, ignore_backoff: bool = False) -> list[StoredURL]:
        """Get URLs eligible for retry based on error type and backoff timing.

        Args:
            limit: Max URLs to return
            ignore_backoff: If True, ignore time-based backoff (for manual retries)

        Returns:
            List of URLs ready for retry, sorted by oldest attempt first
        """
        now = datetime.now().timestamp()
        retryable = []

        for entry in self._urls.values():
            # Skip if not failed or already gave up
            if not entry.extraction_failed or entry.max_retries_reached:
                continue

            # Skip if error is permanent
            if not is_retryable_error(entry.error_reason):
                continue

            # Check backoff timing (unless ignored)
            if not ignore_backoff and entry.last_attempt:
                delay_hours = get_retry_delay_hours(entry.retry_count)
                delay_seconds = delay_hours * 3600
                if now - entry.last_attempt < delay_seconds:
                    continue  # Not enough time has passed

            retryable.append(entry)

        # Sort by oldest attempt first (prioritize long-waiting URLs)
        retryable.sort(key=lambda x: x.last_attempt or 0)

        if limit:
            retryable = retryable[:limit]

        return retryable

    def get_all(self) -> list[StoredURL]:
        """Get all URLs in store."""
        return list(self._urls.values())

    def stats(self) -> dict:
        """Get store statistics."""
        total = len(self._urls)
        extracted = sum(1 for e in self._urls.values() if e.extracted)
        failed = sum(1 for e in self._urls.values() if e.extraction_failed)
        pending = total - extracted - failed

        # By source
        by_source: dict[str, int] = {}
        for entry in self._urls.values():
            by_source[entry.source] = by_source.get(entry.source, 0) + 1

        # SPA vs Classic stats (only for extracted URLs)
        extracted_entries = [e for e in self._urls.values() if e.extracted]
        spa_count = sum(1 for e in extracted_entries if e.is_spa)
        classic_count = len(extracted_entries) - spa_count

        # By fetch method
        by_method: dict[str, int] = {}
        for entry in extracted_entries:
            method = entry.fetch_method or "unknown"
            by_method[method] = by_method.get(method, 0) + 1

        # Error breakdown for failed URLs
        failed_entries = [e for e in self._urls.values() if e.extraction_failed]
        by_error: dict[str, int] = {}
        for entry in failed_entries:
            reason = entry.error_reason or "unknown"
            by_error[reason] = by_error.get(reason, 0) + 1

        # HTTP status codes
        by_status: dict[int, int] = {}
        for entry in failed_entries:
            if entry.http_status:
                by_status[entry.http_status] = by_status.get(entry.http_status, 0) + 1

        # Retry stats
        retryable_count = len(self.get_retryable(ignore_backoff=True))
        ready_for_retry = len(self.get_retryable(ignore_backoff=False))
        permanently_failed = sum(1 for e in failed_entries if e.max_retries_reached)
        by_retry_count: dict[int, int] = {}
        for entry in failed_entries:
            by_retry_count[entry.retry_count] = by_retry_count.get(entry.retry_count, 0) + 1

        return {
            "total": total,
            "extracted": extracted,
            "failed": failed,
            "pending": pending,
            "by_source": by_source,
            "spa_count": spa_count,
            "classic_count": classic_count,
            "spa_percentage": round(spa_count / len(extracted_entries) * 100, 1) if extracted_entries else 0,
            "by_fetch_method": by_method,
            "by_error_reason": by_error,
            "by_http_status": by_status,
            # Retry stats
            "retryable_count": retryable_count,
            "ready_for_retry": ready_for_retry,
            "permanently_failed": permanently_failed,
            "by_retry_count": by_retry_count,
        }

    def clear_failed(self) -> int:
        """Reset failed URLs to pending state."""
        count = 0
        for entry in self._urls.values():
            if entry.extraction_failed:
                entry.extraction_failed = False
                entry.last_attempt = None
                count += 1
        self._save()
        return count
