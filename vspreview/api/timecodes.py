
from __future__ import annotations

from fractions import Fraction
from pathlib import Path

from .info import is_preview

__all__ = [
    'set_timecodes'
]


def set_timecodes(
    index: int, timecodes: str | Path | dict[
        tuple[int | None, int | None], float | tuple[int, int] | Fraction
    ] | list[Fraction], den: int = 1001
) -> None:
    if is_preview():
        from ..core import main_window
        main_window().update_timecodes_info(index, timecodes, den)  # type: ignore
