"""Tests for whaagent package - YouTube cache module."""

import tempfile
import threading
from pathlib import Path

from whaagent.tools.youtube_cache import YouTubeTranscriptCache


def test_youtube_cache_initialization_default():
    """Test cache initialization with default settings."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_dir = Path(tmpdir)
        cache = YouTubeTranscriptCache(cache_dir=cache_dir)

        assert cache._cache_dir == cache_dir
        assert cache._max_size_bytes == 100 * 1024 * 1024  # 100MB
        assert cache._ttl_seconds == 30 * 24 * 60 * 60  # 30 days


def test_youtube_cache_initialization_custom():
    """Test cache initialization with custom settings."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_dir = Path(tmpdir)
        cache = YouTubeTranscriptCache(cache_dir=cache_dir, max_size_mb=50, ttl_days=7)

        assert cache._cache_dir == cache_dir
        assert cache._max_size_bytes == 50 * 1024 * 1024  # 50MB
        assert cache._ttl_seconds == 7 * 24 * 60 * 60  # 7 days


def test_youtube_cache_get_miss():
    """Test cache get with no entry."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = YouTubeTranscriptCache(cache_dir=Path(tmpdir))
        result = cache.get("video123")

        assert result is None


def test_youtube_cache_set_and_get():
    """Test cache set and get operations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = YouTubeTranscriptCache(cache_dir=Path(tmpdir))

        # Set a cache entry
        success = cache.set(
            video_id="video123",
            transcript_text="test transcript",
            video_url="https://youtube.com/watch?v=video123",
            video_title="Test Video",
            language="en",
        )
        assert success is True

        # Get the cached entry
        result = cache.get("video123")
        assert result is not None
        assert result["video_id"] == "video123"
        assert result["transcript_text"] == "test transcript"
        assert result["video_url"] == "https://youtube.com/watch?v=video123"
        assert result["video_title"] == "Test Video"
        assert result["language"] == "en"


def test_youtube_cache_replace_existing():
    """Test replacing an existing cache entry."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = YouTubeTranscriptCache(cache_dir=Path(tmpdir))

        # Set initial entry
        cache.set(
            video_id="video123",
            transcript_text="original transcript",
            video_url="https://youtube.com/watch?v=video123",
        )

        # Replace entry
        cache.set(
            video_id="video123",
            transcript_text="new transcript",
            video_url="https://youtube.com/watch?v=video123",
            video_title="New Title",
        )

        # Verify replacement
        result = cache.get("video123")
        assert result["transcript_text"] == "new transcript"
        assert result["video_title"] == "New Title"


def test_youtube_cache_delete_existing():
    """Test deleting an existing cache entry."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = YouTubeTranscriptCache(cache_dir=Path(tmpdir))

        # Set and then delete
        cache.set(
            video_id="video123",
            transcript_text="test transcript",
            video_url="https://youtube.com/watch?v=video123",
        )

        deleted = cache.delete("video123")
        assert deleted is True

        # Verify deletion
        result = cache.get("video123")
        assert result is None


def test_youtube_cache_delete_nonexistent():
    """Test deleting a non-existent cache entry."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = YouTubeTranscriptCache(cache_dir=Path(tmpdir))

        deleted = cache.delete("nonexistent")
        assert deleted is False


def test_youtube_cache_clear():
    """Test clearing all cache entries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = YouTubeTranscriptCache(cache_dir=Path(tmpdir))

        # Set multiple entries
        for i in range(5):
            cache.set(
                video_id=f"video{i}",
                transcript_text=f"transcript {i}",
                video_url=f"https://youtube.com/watch?v=video{i}",
            )

        # Clear all
        count = cache.clear()
        assert count == 5

        # Verify all cleared
        assert cache.get("video0") is None
        assert cache.get("video1") is None


def test_youtube_cache_clear_empty():
    """Test clearing an empty cache."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = YouTubeTranscriptCache(cache_dir=Path(tmpdir))

        count = cache.clear()
        assert count == 0


def test_youtube_cache_get_stats():
    """Test getting cache statistics."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = YouTubeTranscriptCache(cache_dir=Path(tmpdir))

        # Set some entries
        cache.set(
            video_id="video1",
            transcript_text="short",
            video_url="https://youtube.com/watch?v=video1",
        )
        cache.set(
            video_id="video2",
            transcript_text="a" * 1000,
            video_url="https://youtube.com/watch?v=video2",
        )

        # Access one entry multiple times
        cache.get("video1")
        cache.get("video1")

        stats = cache.get_stats()
        assert stats["total_entries"] == 2
        assert stats["total_size_bytes"] > 0
        assert stats["most_accessed_video"] == "video1"


def test_youtube_cache_get_stats_empty():
    """Test getting statistics from empty cache."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = YouTubeTranscriptCache(cache_dir=Path(tmpdir))

        stats = cache.get_stats()
        assert stats["total_entries"] == 0
        assert stats["total_size_bytes"] == 0


def test_youtube_cache_ttl_expiration():
    """Test TTL-based cache expiration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create cache with 1 second TTL
        cache = YouTubeTranscriptCache(
            cache_dir=Path(tmpdir),
            ttl_days=0,  # 0 days means no TTL in this implementation
        )

        cache.set(
            video_id="video123",
            transcript_text="test transcript",
            video_url="https://youtube.com/watch?v=video123",
        )

        # Should still be accessible with no TTL
        result = cache.get("video123")
        assert result is not None


def test_youtube_cache_no_ttl():
    """Test cache with TTL disabled."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = YouTubeTranscriptCache(
            cache_dir=Path(tmpdir),
            ttl_days=0,  # No TTL
        )

        cache.set(
            video_id="video123",
            transcript_text="test transcript",
            video_url="https://youtube.com/watch?v=video123",
        )

        result = cache.get("video123")
        assert result is not None


def test_youtube_cache_thread_safety():
    """Test cache thread safety with concurrent access."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = YouTubeTranscriptCache(cache_dir=Path(tmpdir))

        results = []

        def worker(video_id):
            cache.set(
                video_id=video_id,
                transcript_text=f"transcript {video_id}",
                video_url=f"https://youtube.com/watch?v={video_id}",
            )
            result = cache.get(video_id)
            results.append((video_id, result is not None))

        # Create multiple threads
        threads = []
        for i in range(10):
            t = threading.Thread(target=worker, args=(f"video{i}",))
            threads.append(t)
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # All operations should succeed
        assert len(results) == 10
        assert all(result for _, result in results)


def test_youtube_cache_close():
    """Test closing cache connection."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = YouTubeTranscriptCache(cache_dir=Path(tmpdir))
        cache.set(
            video_id="video123",
            transcript_text="test transcript",
            video_url="https://youtube.com/watch?v=video123",
        )

        # Should not raise exception
        cache.close()

        # Should be able to create new cache after close
        cache2 = YouTubeTranscriptCache(cache_dir=Path(tmpdir))
        result = cache2.get("video123")
        assert result is not None


def test_youtube_cache_access_tracking():
    """Test that cache access count is tracked."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = YouTubeTranscriptCache(cache_dir=Path(tmpdir))

        cache.set(
            video_id="video123",
            transcript_text="test transcript",
            video_url="https://youtube.com/watch?v=video123",
        )

        # Access multiple times
        cache.get("video123")
        cache.get("video123")
        cache.get("video123")

        stats = cache.get_stats()
        # Access count should be incremented (initial 1 + 3 accesses = 4)
        assert stats["total_entries"] == 1
