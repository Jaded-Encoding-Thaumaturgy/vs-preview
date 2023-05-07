from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import vapoursynth as vs

__all__ = [
    'CroppingInfo',
    'VideoOutputNode',
    'ViewMode',
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


class ViewMode(str, Enum):
    NORMAL = 'Normal'
    FFTSPECTRUM = 'FFTSpectrum'
    DESCALING_HELP = 'Descaling Helper'


@dataclass
class Stretch:
    amount: int = 0
