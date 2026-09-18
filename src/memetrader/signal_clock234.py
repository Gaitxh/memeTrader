"""Per-dispatch timestamp reuse. No global cache or change to signal lifetime."""
from __future__ import annotations
from datetime import datetime
from typing import Callable, Any
from .models import parse_time


class SignalClockCache:
    def __init__(self, parser: Callable = parse_time):
        self.parser = parser
        self.values: dict[Any, Any] = {}
        self.hits = 0
        self.misses = 0

    def __call__(self, signal):
        value = signal['recorded_at']
        # Preserve parser fallback/error semantics for unsupported or empty input.
        if not isinstance(value,(str,datetime)) or not value:
            return self.parser(value)
        if value in self.values:
            self.hits += 1
            return self.values[value]
        parsed = self.parser(value)
        self.values[value] = parsed
        self.misses += 1
        return parsed
