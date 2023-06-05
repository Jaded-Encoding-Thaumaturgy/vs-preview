from __future__ import annotations

from dataclasses import dataclass

import vapoursynth as vs

__all__ = [
    'CroppingInfo',
    'VideoOutputNode',
    'Stretch'
]


@dataclass
class CroppingInfo:
    top: int
    left: int
    width: int
    height: int
    active: bool = True
    is_absolute: bool = False


@dataclass
class VideoOutputNode:
    clip: vs.VideoNode
    alpha: vs.VideoNode | None


@dataclass
class Stretch:
    amount: int = 0
