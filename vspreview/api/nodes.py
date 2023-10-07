
from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import Any

from vapoursynth import AudioNode, RawNode, VideoNode

from .info import is_preview

__all__ = [
    'set_timecodes',

    'update_node_info'
]


def set_timecodes(
    index: int, timecodes: str | Path | dict[
        tuple[int | None, int | None], float | tuple[int, int] | Fraction
    ] | list[Fraction], node: VideoNode | None = None, den: int = 1001
) -> None:
    if is_preview():
        from ..core import main_window

        if isinstance(node, VideoNode) and node.fps_den and node.fps_num:
            den = node.fps_den

        main_window().update_timecodes_info(index, timecodes, den)


def update_node_info(node_type: type[RawNode] | type[VideoNode] | type[AudioNode], index: int, **kwargs: Any) -> None:
    if is_preview():
        from ..core import main_window
        main_window().set_node_info(node_type, index, **kwargs)
