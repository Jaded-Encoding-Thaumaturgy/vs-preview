from __future__ import annotations

from fractions import Fraction
from typing import Dict, List, Tuple

from .init import main  # noqa: F401


def set_timecodes(index: int, timecodes: str | Dict[Tuple[int | None, int | None], Fraction] | List[int]) -> None:
    from .core import main_window

    main_window()
