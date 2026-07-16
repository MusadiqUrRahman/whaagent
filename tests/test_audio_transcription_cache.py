"""Tests for AudioTranscriptionCache."""

import hashlib
import time

import pytest

from whaagent.services.audio_transcription_cache import AudioTranscriptionCache


@pytest.fixture
def cache(tmp_path):
    return AudioTranscriptionCache(cache_dir=tmp_path, max_size_mb=10, ttl_days=30)


class TestAudioTranscriptionCache:
    def test_cache_miss_returns_none(self, cache):
        result = cache.get("nonexistent_hash", "tenant1")
        assert result is None

    def test_set_and_get_roundtrip(self, cache):
        audio_hash = hashlib.sha256(b"fake audio data").hexdigest()
        cache.set(
            audio_hash=audio_hash,
            transcription="Hello world",
            mime_type="audio/ogg",
            tenant_id="tenant1",
            duration_seconds=5.0,
        )
        result = cache.get(audio_hash, "tenant1")
        assert result is not None
        assert result["transcription"] == "Hello world"

    def test_same_hash_deduplicated(self, cache):
        audio_hash = hashlib.sha256(b"same audio").hexdigest()
        cache.set(audio_hash=audio_hash, transcription="First", mime_type="audio/ogg", tenant_id="t1")
        cache.set(audio_hash=audio_hash, transcription="First", mime_type="audio/ogg", tenant_id="t1")
        result = cache.get(audio_hash, "t1")
        # First set() creates entry with count=1, second set() updates to count=2, get() increments to count=3
        assert result["access_count"] == 3

    def test_different_hashes_different_transcriptions(self, cache):
        h1 = hashlib.sha256(b"audio one").hexdigest()
        h2 = hashlib.sha256(b"audio two").hexdigest()
        cache.set(audio_hash=h1, transcription="One", mime_type="audio/ogg", tenant_id="t1")
        cache.set(audio_hash=h2, transcription="Two", mime_type="audio/ogg", tenant_id="t1")
        assert cache.get(h1, "t1")["transcription"] == "One"
        assert cache.get(h2, "t1")["transcription"] == "Two"

    def test_per_tenant_isolation(self, cache):
        audio_hash = hashlib.sha256(b"shared audio").hexdigest()
        cache.set(audio_hash=audio_hash, transcription="For tenant1", mime_type="audio/ogg", tenant_id="t1")
        cache.set(audio_hash=audio_hash, transcription="For tenant2", mime_type="audio/ogg", tenant_id="t2")
        assert cache.get(audio_hash, "t1")["transcription"] == "For tenant1"
        assert cache.get(audio_hash, "t2")["transcription"] == "For tenant2"

    def test_ttl_expiration(self, tmp_path):
        # Use a very small TTL (1 microsecond) to test expiration
        cache = AudioTranscriptionCache(cache_dir=tmp_path, ttl_days=0.00000001)
        audio_hash = hashlib.sha256(b"expired audio").hexdigest()
        cache.set(audio_hash=audio_hash, transcription="Old", mime_type="audio/ogg", tenant_id="t1")
        # Wait for TTL to expire
        time.sleep(0.01)
        result = cache.get(audio_hash, "t1")
        assert result is None

    def test_delete_removes_entry(self, cache):
        audio_hash = hashlib.sha256(b"deletable audio").hexdigest()
        cache.set(audio_hash=audio_hash, transcription="Delete me", mime_type="audio/ogg", tenant_id="t1")
        assert cache.get(audio_hash, "t1") is not None
        assert cache.delete(audio_hash, "t1") is True
        assert cache.get(audio_hash, "t1") is None

    def test_delete_nonexistent_returns_false(self, cache):
        assert cache.delete("nonexistent", "tenant1") is False

    def test_clear_removes_all_entries(self, cache):
        h1 = hashlib.sha256(b"audio one").hexdigest()
        h2 = hashlib.sha256(b"audio two").hexdigest()
        cache.set(audio_hash=h1, transcription="One", mime_type="audio/ogg", tenant_id="t1")
        cache.set(audio_hash=h2, transcription="Two", mime_type="audio/ogg", tenant_id="t1")
        count = cache.clear()
        assert count == 2
        assert cache.get(h1, "t1") is None
        assert cache.get(h2, "t1") is None

    def test_get_stats_returns_valid_info(self, cache):
        audio_hash = hashlib.sha256(b"stats audio").hexdigest()
        cache.set(
            audio_hash=audio_hash,
            transcription="Stats test",
            mime_type="audio/ogg",
            tenant_id="tenant1",
            duration_seconds=10.0,
        )
        stats = cache.get_stats()
        assert stats["total_entries"] == 1
        assert stats["total_size_bytes"] > 0
        assert stats["max_size_mb"] == 10
        assert stats["ttl_days"] == 30

    def test_mime_type_storage(self, cache):
        audio_hash = hashlib.sha256(b"mime test").hexdigest()
        cache.set(
            audio_hash=audio_hash,
            transcription="Test",
            mime_type="audio/mpeg",
            tenant_id="tenant1",
        )
        result = cache.get(audio_hash, "tenant1")
        assert result["mime_type"] == "audio/mpeg"

    def test_duration_seconds_optional(self, cache):
        audio_hash = hashlib.sha256(b"duration test").hexdigest()
        cache.set(
            audio_hash=audio_hash,
            transcription="Test",
            mime_type="audio/ogg",
            tenant_id="tenant1",
            duration_seconds=None,
        )
        result = cache.get(audio_hash, "tenant1")
        assert result["duration_seconds"] is None

    def test_access_count_increments(self, cache):
        audio_hash = hashlib.sha256(b"access test").hexdigest()
        cache.set(audio_hash=audio_hash, transcription="Test", mime_type="audio/ogg", tenant_id="t1")
        result1 = cache.get(audio_hash, "t1")
        # set() creates with count=1, get() increments to count=2
        assert result1["access_count"] == 2
        result2 = cache.get(audio_hash, "t1")
        assert result2["access_count"] == 3

    def test_close_connection(self, cache):
        audio_hash = hashlib.sha256(b"close test").hexdigest()
        cache.set(audio_hash=audio_hash, transcription="Test", mime_type="audio/ogg", tenant_id="t1")
        cache.close()
        # Should be able to create new connection after close
        result = cache.get(audio_hash, "t1")
        assert result is not None

    def test_composite_key_primary_key(self, cache):
        """Test that (audio_hash, tenant_id) forms a composite primary key."""
        audio_hash = hashlib.sha256(b"composite test").hexdigest()
        # Insert same audio_hash for different tenants - both should exist
        cache.set(audio_hash=audio_hash, transcription="T1", mime_type="audio/ogg", tenant_id="t1")
        cache.set(audio_hash=audio_hash, transcription="T2", mime_type="audio/ogg", tenant_id="t2")

        result1 = cache.get(audio_hash, "t1")
        result2 = cache.get(audio_hash, "t2")

        assert result1["transcription"] == "T1"
        assert result2["transcription"] == "T2"
        assert result1["tenant_id"] == "t1"
        assert result2["tenant_id"] == "t2"

    def test_lru_eviction(self, tmp_path):
        """Test that LRU eviction works when cache exceeds size limit."""
        # Create a tiny cache (1KB max)
        cache = AudioTranscriptionCache(cache_dir=tmp_path, max_size_mb=0.001, ttl_days=30)

        # Add first entry with large transcription
        h1 = hashlib.sha256(b"first").hexdigest()
        cache.set(audio_hash=h1, transcription="A" * 600, mime_type="audio/ogg", tenant_id="t1")

        # Add second entry with large transcription (this should trigger eviction of first)
        h2 = hashlib.sha256(b"second").hexdigest()
        cache.set(audio_hash=h2, transcription="B" * 600, mime_type="audio/ogg", tenant_id="t1")

        # First entry should be evicted, second should exist
        assert cache.get(h1, "t1") is None
        assert cache.get(h2, "t1") is not None

    def test_cache_persists_across_instances(self, tmp_path):
        """Test that cache persists when creating a new cache instance."""
        audio_hash = hashlib.sha256(b"persistence test").hexdigest()

        # Create first instance and store data
        cache1 = AudioTranscriptionCache(cache_dir=tmp_path, max_size_mb=10, ttl_days=30)
        cache1.set(audio_hash=audio_hash, transcription="Persisted", mime_type="audio/ogg", tenant_id="t1")
        cache1.close()

        # Create second instance and verify data is still there
        cache2 = AudioTranscriptionCache(cache_dir=tmp_path, max_size_mb=10, ttl_days=30)
        result = cache2.get(audio_hash, "t1")
        assert result is not None
        assert result["transcription"] == "Persisted"
        cache2.close()
