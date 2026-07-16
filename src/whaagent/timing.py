"""Thread-local timing helpers for per-node latency instrumentation."""

import logging
import threading
import time

logger = logging.getLogger(__name__)

# Thread-local storage for accumulating timing data within a single graph run.
_timing_local = threading.local()


def timing_start(phase: str) -> None:
    """Mark the start of a timing phase."""
    if not hasattr(_timing_local, "phases"):
        _timing_local.phases = {}
        _timing_local.graph_start = time.monotonic()
    _timing_local.phases[phase] = {"start": time.monotonic()}


def timing_end(phase: str) -> None:
    """Mark the end of a timing phase and accumulate duration."""
    if not hasattr(_timing_local, "phases") or phase not in _timing_local.phases:
        return
    elapsed = time.monotonic() - _timing_local.phases[phase]["start"]
    _timing_local.phases[phase]["duration"] = elapsed


def timing_summary(intent: str) -> None:
    """Log a structured timing summary and reset state."""
    if not hasattr(_timing_local, "phases"):
        return
    total = time.monotonic() - _timing_local.graph_start
    parts = [f"total={total:.1f}s"]
    for name, data in sorted(_timing_local.phases.items()):
        dur = data.get("duration", 0.0)
        parts.append(f"{name}={dur:.1f}s")
    logger.info("[timing] intent=%s %s", intent, " ".join(parts))
    _timing_local.phases = {}
