from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import vapoursynth as vs

__all__ = [
    'CroppingInfo',
    'VideoOutputNode',
    'PictureType',
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


class PictureType(bytes, Enum):
    ALL = b'All'
    Intra = b'I'
    Predicted = b'P'
    Bipredictive = b'B'

    def __str__(self) -> str:
        if self == PictureType.ALL:
            return 'All'

        return self.decode('utf-8') + ' Frames'

    @classmethod
    def list(cls) -> list[PictureType]:
        return [PictureType(e.value) for e in cls]


class ViewMode(str, Enum):
    NORMAL = 'Normal'
    FFTSPECTRUM = 'FFTSpectrum'


@dataclass
class Stretch:
    amount: int = 0
