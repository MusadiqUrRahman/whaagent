"""SQLite-based cache for YouTube video transcripts.

This module provides a caching layer to avoid reprocessing videos that
have already been transcribed. It follows the same SQLite pattern used
in the WhatsApp channel for message deduplication.
"""

import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, cast

from whaagent.constants import STORAGE_DIR

logger = logging.getLogger(__name__)

# Default cache settings
DEFAULT_CACHE_DIR = STORAGE_DIR / "youtube"
DEFAULT_MAX_SIZE_MB = 100
DEFAULT_TTL_DAYS = 30  # 0 = no TTL


class YouTubeTranscriptCache:
    """SQLite-based cache for YouTube video transcripts.

    This cache stores transcripts locally to avoid repeated API calls
    for the same video. It implements LRU eviction and optional TTL.

    Features:
        - Thread-safe SQLite connections (thread-local storage)
        - LRU eviction when cache exceeds size limit
        - Optional TTL-based invalidation
        - Access tracking for analytics

    Usage:
        cache = YouTubeTranscriptCache()
        cached = cache.get("video_id")
        if cached is None:
            transcript = fetch_from_api()
            cache.set("video_id", transcript, "https://...", "Video Title")
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        max_size_mb: int = DEFAULT_MAX_SIZE_MB,
        ttl_days: int = DEFAULT_TTL_DAYS,
    ) -> None:
        """Initialize the transcript cache.

        Args:
            cache_dir: Directory for the SQLite database.
            max_size_mb: Maximum cache size in megabytes.
            ttl_days: Days before cache entry expires (0 = no TTL).
        """
        self._cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self._db_path = self._cache_dir / "transcripts.db"
        self._max_size_bytes = max_size_mb * 1024 * 1024
        self._ttl_seconds = ttl_days * 24 * 60 * 60 if ttl_days > 0 else 0

        # Thread-local storage for SQLite connections
        self._db_local = threading.local()
        self._db_lock = threading.Lock()

        self._ensure_cache_dir()
        self._init_database()

    def _ensure_cache_dir(self) -> None:
        """Create cache directory if it doesn't exist."""
        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Cache directory: {self._cache_dir}")
        except OSError as e:
            logger.error(f"Failed to create cache directory: {e}")
            raise

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create a thread-local SQLite connection.

        Each thread gets its own connection to avoid SQLite threading issues.

        Returns:
            A SQLite connection for the current thread.
        """
        if not hasattr(self._db_local, "conn") or self._db_local.conn is None:
            self._db_local.conn = sqlite3.connect(str(self._db_path))
            self._db_local.conn.row_factory = sqlite3.Row
            self._init_schema(self._db_local.conn)
            logger.debug(f"Created thread-local DB connection for thread {threading.get_ident()}")
        return cast(sqlite3.Connection, self._db_local.conn)

    def _init_schema(self, conn: sqlite3.Connection) -> None:
        """Initialize the database schema."""
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transcript_cache (
                video_id TEXT PRIMARY KEY,
                video_url TEXT NOT NULL,
                video_title TEXT,
                transcript_text TEXT NOT NULL,
                language TEXT NOT NULL DEFAULT 'en',
                cached_at REAL NOT NULL,
                accessed_at REAL NOT NULL,
                access_count INTEGER NOT NULL DEFAULT 1
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_cached_at
            ON transcript_cache(cached_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_access_count
            ON transcript_cache(access_count)
        """)
        conn.commit()

    def _init_database(self) -> None:
        """Initialize database and clean up expired entries."""
        try:
            self._get_connection()
            logger.info(f"Initialized transcript cache: {self._db_path}")
            if self._ttl_seconds > 0:
                self._cleanup_expired()
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize cache database: {e}")

    def get(self, video_id: str) -> dict[str, Any] | None:
        """Retrieve a cached transcript.

        Args:
            video_id: The YouTube video ID.

        Returns:
            Dictionary with transcript data, or None if not cached/expired.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM transcript_cache WHERE video_id = ?",
                (video_id,),
            )
            row = cursor.fetchone()

            if row is None:
                logger.debug(f"Cache miss for video: {video_id}")
                return None

            # Check TTL
            if self._ttl_seconds > 0:
                if time.time() - row["cached_at"] > self._ttl_seconds:
                    logger.debug(f"Cache entry expired for video: {video_id}")
                    self.delete(video_id)
                    return None

            # Update access tracking
            cursor.execute(
                """
                UPDATE transcript_cache
                SET accessed_at = ?, access_count = access_count + 1
                WHERE video_id = ?
                """,
                (time.time(), video_id),
            )
            conn.commit()

            logger.debug(f"Cache hit for video: {video_id}")
            return {
                "video_id": row["video_id"],
                "video_url": row["video_url"],
                "video_title": row["video_title"],
                "transcript_text": row["transcript_text"],
                "language": row["language"],
                "cached_at": row["cached_at"],
                "access_count": row["access_count"] + 1,
            }

        except sqlite3.Error as e:
            logger.error(f"Error reading from cache: {e}")
            return None

    def set(
        self,
        video_id: str,
        transcript_text: str,
        video_url: str,
        video_title: str | None = None,
        language: str = "en",
    ) -> bool:
        """Store a transcript in the cache.

        Args:
            video_id: The YouTube video ID.
            transcript_text: The full transcript text.
            video_url: The original video URL.
            video_title: Optional video title.
            language: The transcript language code.

        Returns:
            True if cached successfully, False otherwise.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            current_time = time.time()

            # Check if entry exists
            cursor.execute(
                "SELECT access_count FROM transcript_cache WHERE video_id = ?",
                (video_id,),
            )
            existing_row = cursor.fetchone()
            new_access_count = (existing_row[0] + 1) if existing_row else 1

            # Insert or replace with calculated access count
            cursor.execute(
                """
                INSERT OR REPLACE INTO transcript_cache
                (video_id, video_url, video_title, transcript_text, language,
                 cached_at, accessed_at, access_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    video_id,
                    video_url,
                    video_title,
                    transcript_text,
                    language,
                    current_time,
                    current_time,
                    new_access_count,
                ),
            )
            conn.commit()

            logger.info(f"Cached transcript for video: {video_id}")

            # Check cache size and evict if necessary
            self._evict_if_needed()

            return True

        except sqlite3.Error as e:
            logger.error(f"Error writing to cache: {e}")
            return False

    def delete(self, video_id: str) -> bool:
        """Remove a transcript from the cache.

        Args:
            video_id: The YouTube video ID.

        Returns:
            True if deleted, False if not found or error.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "DELETE FROM transcript_cache WHERE video_id = ?",
                (video_id,),
            )
            conn.commit()

            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"Deleted cache entry for video: {video_id}")
            return deleted

        except sqlite3.Error as e:
            logger.error(f"Error deleting from cache: {e}")
            return False

    def clear(self) -> int:
        """Clear all cached transcripts.

        Returns:
            Number of entries deleted.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM transcript_cache")
            count = cast(int, cursor.fetchone()[0])

            cursor.execute("DELETE FROM transcript_cache")
            conn.commit()

            logger.info(f"Cleared {count} cached transcripts")
            return count

        except sqlite3.Error as e:
            logger.error(f"Error clearing cache: {e}")
            return 0

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM transcript_cache")
            total_entries = cursor.fetchone()[0]

            cursor.execute("SELECT SUM(LENGTH(transcript_text)) FROM transcript_cache")
            total_size = cursor.fetchone()[0] or 0

            cursor.execute("SELECT video_id FROM transcript_cache ORDER BY access_count DESC LIMIT 1")
            most_accessed = cursor.fetchone()

            return {
                "total_entries": total_entries,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "max_size_mb": self._max_size_bytes / (1024 * 1024),
                "most_accessed_video": most_accessed[0] if most_accessed else None,
                "ttl_days": self._ttl_seconds / (24 * 60 * 60) if self._ttl_seconds > 0 else 0,
            }

        except sqlite3.Error as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}

    def _cleanup_expired(self) -> int:
        """Remove expired entries based on TTL.

        Returns:
            Number of entries removed.
        """
        if self._ttl_seconds <= 0:
            return 0

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cutoff_time = time.time() - self._ttl_seconds

            cursor.execute(
                "DELETE FROM transcript_cache WHERE cached_at < ?",
                (cutoff_time,),
            )
            conn.commit()

            deleted = cast(int, cursor.rowcount)
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} expired cache entries")
            return deleted

        except sqlite3.Error as e:
            logger.error(f"Error cleaning up expired entries: {e}")
            return 0

    def _evict_if_needed(self) -> int:
        """Evict least-recently-used entries if cache exceeds size limit.

        Returns:
            Number of entries evicted.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Get current cache size
            cursor.execute("SELECT SUM(LENGTH(transcript_text)) FROM transcript_cache")
            current_size = cursor.fetchone()[0] or 0

            if current_size <= self._max_size_bytes:
                return 0

            logger.info(
                f"Cache size ({current_size / (1024 * 1024):.1f}MB) exceeds limit "
                f"({self._max_size_bytes / (1024 * 1024):.1f}MB), evicting LRU entries"
            )

            evicted = 0
            # Evict LRU entries until we're under limit
            while current_size > self._max_size_bytes * 0.9:  # Target 90% of limit
                cursor.execute(
                    """
                    DELETE FROM transcript_cache
                    WHERE video_id = (
                        SELECT video_id FROM transcript_cache
                        ORDER BY accessed_at ASC
                        LIMIT 1
                    )
                    RETURNING LENGTH(transcript_text)
                    """
                )
                row = cursor.fetchone()
                if row is None:
                    break
                current_size -= row[0]
                evicted += 1

            conn.commit()
            logger.info(f"Evicted {evicted} LRU cache entries")
            return evicted

        except sqlite3.Error as e:
            logger.error(f"Error during cache eviction: {e}")
            return 0

    def close(self) -> None:
        """Close database connection for the current thread."""
        if hasattr(self._db_local, "conn") and self._db_local.conn is not None:
            try:
                self._db_local.conn.close()
            except sqlite3.Error as e:
                logger.warning(f"Error closing cache connection: {e}")
            self._db_local.conn = None
            logger.debug("Closed cache database connection")
