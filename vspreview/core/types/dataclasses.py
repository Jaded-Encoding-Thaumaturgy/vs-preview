from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import vapoursynth as vs
from PyQt5 import sip


@dataclass
class NumpyVideoPHelp:
    data: np.typing.NDArray = None  # type: ignore
    pointer: sip.voidptr = None  # type: ignore
    stride: int = 8


@dataclass
class CroppingInfo:
    top: int
    left: int
    width: int
    height: int
    active: bool = True
    is_absolute: bool = False


@dataclass
class VideoOutputNode():
    clip: vs.VideoNode
    alpha: vs.VideoNode | None
