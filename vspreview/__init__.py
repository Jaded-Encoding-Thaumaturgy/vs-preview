from __future__ import annotations

from fractions import Fraction

from .init import main  # noqa: F401


def set_timecodes(index: int, timecodes: str | dict[tuple[int | None, int | None], Fraction] | list[int]) -> None:
    from .core import main_window

    main_window().update_timecodes_info(index, timecodes)
