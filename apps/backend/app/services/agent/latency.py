"""Per-call latency instrumentation for the voice hot path.

Log-only: no DB writes, no network calls, no work in the audio loop
beyond reading a monotonic clock. Each phase records a duration in
milliseconds; the call-end summary is one INFO log line.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


def monotonic_ms(start: float) -> int:
    """Milliseconds elapsed since a monotonic start time."""
    return round((time.monotonic() - start) * 1000)


@dataclass(slots=True)
class CallLatency:
    """Collect named phase durations for one call, flushed as one log line."""

    _durations: dict[str, list[int]] = field(default_factory=dict)

    def span(self, name: str, start: float) -> int:
        """Record the duration since ``start`` (a ``time.monotonic()`` value)."""
        value = monotonic_ms(start)
        self._durations.setdefault(name, []).append(value)
        return value

    def record(self, name: str, value_ms: int) -> None:
        """Record an externally measured duration."""
        self._durations.setdefault(name, []).append(value_ms)

    def format(self) -> str:
        """Render all recorded metrics as ``name=min/avg/max`` tokens."""
        tokens = []
        for name, values in self._durations.items():
            if len(values) == 1:
                tokens.append(f"{name}={values[0]}ms")
                continue
            tokens.append(
                f"{name}={min(values)}/{sum(values) / len(values):.0f}/{max(values)}ms"
            )
        return " ".join(tokens)
