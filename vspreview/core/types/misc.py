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
    cache: bool = False

    def __post_init__(self) -> None:
        self.original_clip = self.clip

        if self.cache:
            from vstools import cache_clip

            self.clip = cache_clip(self.clip)

            if self.alpha:
                self.alpha = cache_clip(self.alpha)


@dataclass
class Stretch:
    amount: int = 0
