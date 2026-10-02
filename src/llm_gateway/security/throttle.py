"""Throttle: in-process request cap. One replica does not share this counter."""

import threading
import time
from collections import defaultdict, deque


class Throttle:
    def __init__(self, rpm: int) -> None:
        self.rpm = rpm
        self._lock = threading.Lock()
        self._hits: dict[str, deque] = defaultdict(deque)

    def allow(self, identity: str) -> bool:
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[identity]
            while bucket and now - bucket[0] >= 60:
                bucket.popleft()
            if len(bucket) >= self.rpm:
                return False
            bucket.append(now)
            return True
