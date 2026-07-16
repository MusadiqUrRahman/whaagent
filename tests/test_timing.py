"""Tests for timing instrumentation helpers."""

import time

from whaagent.timing import _timing_local, timing_end, timing_start, timing_summary


class TestTimingHelpers:
    def test_timing_start_creates_phases(self):
        """timing_start should initialize the phases dict."""
        _timing_local.phases = {}

        timing_start("test_phase")
        assert hasattr(_timing_local, "phases")
        assert "test_phase" in _timing_local.phases
        assert "start" in _timing_local.phases["test_phase"]

    def test_timing_end_records_duration(self):
        """timing_end should compute and store duration."""
        _timing_local.phases = {}
        _timing_local.graph_start = time.monotonic()

        timing_start("test_phase")
        time.sleep(0.01)
        timing_end("test_phase")

        assert "duration" in _timing_local.phases["test_phase"]
        assert _timing_local.phases["test_phase"]["duration"] >= 0.01

    def test_timing_end_noop_without_start(self):
        """timing_end should be a no-op if phases not initialized."""
        _timing_local.phases = {}
        timing_end("nonexistent")  # Should not raise

    def test_timing_summary_resets_state(self):
        """timing_summary should reset phases after logging."""
        _timing_local.phases = {}
        _timing_local.graph_start = time.monotonic()

        timing_start("phase_a")
        timing_end("phase_a")
        timing_summary("test")

        assert _timing_local.phases == {}
