from __future__ import annotations

from dataclasses import dataclass

from ..bases import SafeYAMLObject

import vapoursynth as vs

__all__ = [
    'CroppingInfo',
    'ArInfo',
    'VideoOutputNode',
    'Stretch'
]


@dataclass
class CroppingInfo(SafeYAMLObject):
    top: int
    left: int
    width: int
    height: int
    active: bool = True
    is_absolute: bool = False


_arinfo_active = False


@dataclass
class ArInfo(SafeYAMLObject):
    sarnum: int
    sarden: int

    @property
    def active(self) -> bool:
        return _arinfo_active

    @active.setter
    def active(self, active: bool) -> None:
        global _arinfo_active

        _arinfo_active = active


@dataclass
class VideoOutputNode:
    clip: vs.VideoNode
    alpha: vs.VideoNode | None
    cache: bool = False

    def __post_init__(self) -> None:
        self.original_clip = self.clip
        self.original_alpha = self.alpha

        if self.cache:
            from vstools import cache_clip

            self.clip = cache_clip(self.clip)

            if self.alpha:
                self.alpha = cache_clip(self.alpha)


@dataclass
class Stretch:
    amount: int = 0
