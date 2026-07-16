"""SQLite-based cache for audio transcriptions.

This module provides a caching layer to avoid reprocessing audio files that
have already been transcribed. It follows the same SQLite pattern used
in the YouTube transcript cache.
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
DEFAULT_CACHE_DIR = STORAGE_DIR / "audio_transcriptions"
DEFAULT_MAX_SIZE_MB = 100
DEFAULT_TTL_DAYS = 30  # 0 = no TTL


class AudioTranscriptionCache:
    """SQLite-based cache for audio transcriptions.

    This cache stores transcriptions locally to avoid repeated processing
    of the same audio. It implements LRU eviction and optional TTL.

    Features:
        - Thread-safe SQLite connections (thread-local storage)
        - LRU eviction when cache exceeds size limit
        - Optional TTL-based invalidation
        - Access tracking for analytics
        - Per-tenant isolation (same audio from different tenants cached separately)

    Usage:
        cache = AudioTranscriptionCache()
        cached = cache.get("audio_hash", "tenant1")
        if cached is None:
            transcription = transcribe_audio()
            cache.set("audio_hash", transcription, "audio/ogg", "tenant1", duration_seconds=5.0)
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        max_size_mb: int = DEFAULT_MAX_SIZE_MB,
        ttl_days: int = DEFAULT_TTL_DAYS,
    ) -> None:
        """Initialize the audio transcription cache.

        Args:
            cache_dir: Directory for the SQLite database.
            max_size_mb: Maximum cache size in megabytes.
            ttl_days: Days before cache entry expires (0 = no TTL).
        """
        self._cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self._db_path = self._cache_dir / "transcriptions.db"
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
            CREATE TABLE IF NOT EXISTS audio_transcription_cache (
                audio_hash TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                transcription TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                duration_seconds REAL,
                cached_at REAL NOT NULL,
                accessed_at REAL NOT NULL,
                access_count INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (audio_hash, tenant_id)
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audio_cached_at
            ON audio_transcription_cache(cached_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audio_tenant
            ON audio_transcription_cache(tenant_id)
        """)
        conn.commit()

    def _init_database(self) -> None:
        """Initialize database and clean up expired entries."""
        try:
            self._get_connection()
            logger.info(f"Initialized audio transcription cache: {self._db_path}")
            if self._ttl_seconds > 0:
                self._cleanup_expired()
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize cache database: {e}")

    def get(self, audio_hash: str, tenant_id: str) -> dict[str, Any] | None:
        """Retrieve a cached transcription.

        Args:
            audio_hash: The SHA256 hash of audio content.
            tenant_id: The tenant ID for multi-tenant isolation.

        Returns:
            Dictionary with transcription data, or None if not cached/expired.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM audio_transcription_cache WHERE audio_hash = ? AND tenant_id = ?",
                (audio_hash, tenant_id),
            )
            row = cursor.fetchone()

            if row is None:
                logger.debug(f"Cache miss for audio: {audio_hash} (tenant: {tenant_id})")
                return None

            # Check TTL
            if self._ttl_seconds > 0:
                if time.time() - row["cached_at"] > self._ttl_seconds:
                    logger.debug(f"Cache entry expired for audio: {audio_hash} (tenant: {tenant_id})")
                    self.delete(audio_hash, tenant_id)
                    return None

            # Update access tracking
            cursor.execute(
                """
                UPDATE audio_transcription_cache
                SET accessed_at = ?, access_count = access_count + 1
                WHERE audio_hash = ? AND tenant_id = ?
                """,
                (time.time(), audio_hash, tenant_id),
            )
            conn.commit()

            logger.debug(f"Cache hit for audio: {audio_hash} (tenant: {tenant_id})")
            return {
                "audio_hash": row["audio_hash"],
                "tenant_id": row["tenant_id"],
                "transcription": row["transcription"],
                "mime_type": row["mime_type"],
                "duration_seconds": row["duration_seconds"],
                "cached_at": row["cached_at"],
                "access_count": row["access_count"] + 1,
            }

        except sqlite3.Error as e:
            logger.error(f"Error reading from cache: {e}")
            return None

    def set(
        self,
        audio_hash: str,
        transcription: str,
        mime_type: str,
        tenant_id: str,
        duration_seconds: float | None = None,
    ) -> bool:
        """Store a transcription in the cache.

        Args:
            audio_hash: The SHA256 hash of audio content.
            transcription: The transcribed text.
            mime_type: The audio MIME type (e.g., "audio/ogg").
            tenant_id: The tenant ID for multi-tenant isolation.
            duration_seconds: Optional audio duration in seconds.

        Returns:
            True if cached successfully, False otherwise.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            current_time = time.time()

            # Check if entry exists
            cursor.execute(
                "SELECT access_count FROM audio_transcription_cache WHERE audio_hash = ? AND tenant_id = ?",
                (audio_hash, tenant_id),
            )
            existing_row = cursor.fetchone()
            new_access_count = (existing_row[0] + 1) if existing_row else 1

            # Insert or replace with calculated access count
            cursor.execute(
                """
                INSERT OR REPLACE INTO audio_transcription_cache
                (audio_hash, tenant_id, transcription, mime_type, duration_seconds,
                 cached_at, accessed_at, access_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    audio_hash,
                    tenant_id,
                    transcription,
                    mime_type,
                    duration_seconds,
                    current_time,
                    current_time,
                    new_access_count,
                ),
            )
            conn.commit()

            logger.info(f"Cached transcription for audio: {audio_hash} (tenant: {tenant_id})")

            # Check cache size and evict if necessary
            self._evict_if_needed()

            return True

        except sqlite3.Error as e:
            logger.error(f"Error writing to cache: {e}")
            return False

    def delete(self, audio_hash: str, tenant_id: str) -> bool:
        """Remove a transcription from the cache.

        Args:
            audio_hash: The SHA256 hash of audio content.
            tenant_id: The tenant ID for multi-tenant isolation.

        Returns:
            True if deleted, False if not found or error.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "DELETE FROM audio_transcription_cache WHERE audio_hash = ? AND tenant_id = ?",
                (audio_hash, tenant_id),
            )
            conn.commit()

            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"Deleted cache entry for audio: {audio_hash} (tenant: {tenant_id})")
            return deleted

        except sqlite3.Error as e:
            logger.error(f"Error deleting from cache: {e}")
            return False

    def clear(self) -> int:
        """Clear all cached transcriptions.

        Returns:
            Number of entries deleted.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM audio_transcription_cache")
            count = cast(int, cursor.fetchone()[0])

            cursor.execute("DELETE FROM audio_transcription_cache")
            conn.commit()

            logger.info(f"Cleared {count} cached transcriptions")
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

            cursor.execute("SELECT COUNT(*) FROM audio_transcription_cache")
            total_entries = cursor.fetchone()[0]

            cursor.execute("SELECT SUM(LENGTH(transcription)) FROM audio_transcription_cache")
            total_size = cursor.fetchone()[0] or 0

            cursor.execute(
                "SELECT audio_hash, tenant_id FROM audio_transcription_cache ORDER BY access_count DESC LIMIT 1"
            )
            most_accessed = cursor.fetchone()

            return {
                "total_entries": total_entries,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "max_size_mb": self._max_size_bytes / (1024 * 1024),
                "most_accessed_audio": f"{most_accessed[0]}@{most_accessed[1]}" if most_accessed else None,
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
                "DELETE FROM audio_transcription_cache WHERE cached_at < ?",
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
            cursor.execute("SELECT SUM(LENGTH(transcription)) FROM audio_transcription_cache")
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
                    DELETE FROM audio_transcription_cache
                    WHERE (audio_hash, tenant_id) = (
                        SELECT audio_hash, tenant_id FROM audio_transcription_cache
                        ORDER BY accessed_at ASC
                        LIMIT 1
                    )
                    RETURNING LENGTH(transcription)
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
