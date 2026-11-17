"""Trace timing without profile content."""
from time import perf_counter

from app.models import Trace


def trace(agent: str, task: str, source: str, result: str, start: float, **kwargs) -> Trace:
    return Trace(agent=agent, task=task, source=source, result=result,
                 duration_ms=round((perf_counter() - start) * 1000, 3), **kwargs)
