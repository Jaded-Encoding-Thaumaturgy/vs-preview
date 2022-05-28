from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import vapoursynth as vs
from PyQt5 import sip


@dataclass
class NumpyVideoPHelp:
    if TYPE_CHECKING:
        import numpy as np

        data: np.typing.NDArray = None  # type: ignore
    else:
        data: Any = None
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
