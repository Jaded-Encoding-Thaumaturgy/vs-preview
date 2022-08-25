from __future__ import annotations

from dataclasses import dataclass

import vapoursynth as vs


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
