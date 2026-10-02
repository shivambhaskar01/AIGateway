"""Chronos: stage clock. Values are milliseconds."""

import time
from contextlib import contextmanager


class Chronos:
    def __init__(self) -> None:
        self._start = time.perf_counter()
        self.stages: dict[str, float] = {}

    @contextmanager
    def stage(self, name: str):
        started = time.perf_counter()
        try:
            yield
        finally:
            self.stages[name] = (time.perf_counter() - started) * 1000

    def snapshot(self) -> dict[str, float]:
        data = {name: round(elapsed, 2) for name, elapsed in self.stages.items()}
        data["total"] = round((time.perf_counter() - self._start) * 1000, 2)
        return data
