from __future__ import annotations

from typing import TYPE_CHECKING, overload

from vstools import vs, vs_object

from ..core import Frame, GraphicsView, VideoOutput, VideoOutputNode, main_window
from .abstract import AbstractPlugin

if TYPE_CHECKING:
    from ..main import MainWindow

__all__ = [
    'PluginVideoOutputs',
]


class PluginVideoOutputs(vs_object, dict[VideoOutput, VideoOutput]):
    def __init__(self, main: MainWindow | None = None) -> None:
        self.main = main or main_window()

    @property
    def current(self) -> VideoOutput:
        return self[self.main.current_output]

    @property
    def source(self) -> vs.VideoNode:
        return self.current.source.clip

    @property
    def prepared(self) -> vs.VideoNode:
        return self.current.prepared.clip

    def __delitem__(self, __key: VideoOutput) -> None:
        if __key not in self:
            return

        return super().__delitem__(__key)

    def __vs_del__(self, core_id: int) -> None:
        self.clear()
