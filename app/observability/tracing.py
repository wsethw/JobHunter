from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter


@contextmanager
def measure_duration() -> Iterator[dict[str, int]]:
    data = {"duration_ms": 0}
    started = perf_counter()
    try:
        yield data
    finally:
        data["duration_ms"] = int((perf_counter() - started) * 1000)
