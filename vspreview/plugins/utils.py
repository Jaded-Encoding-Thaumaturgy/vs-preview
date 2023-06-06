from __future__ import annotations

from typing import TYPE_CHECKING, overload

from vstools import vs, vs_object

from ..core import Frame, GraphicsView, VideoOutput, VideoOutputNode, main_window
from .abstract import AbstractPlugin

if TYPE_CHECKING:
    from ..main import MainWindow

__all__ = [
    'PluginVideoOutputs',

    'MappedNodesPlugin', 'MappedNodesViewPlugin'
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


class MappedNodesPlugin(AbstractPlugin):
    def __init__(self, main: MainWindow) -> None:
        super().__init__(main)

        self.outputs = PluginVideoOutputs(main)

    @overload
    def get_node(self, node: vs.VideoNode) -> vs.VideoNode:
        ...

    @overload
    def get_node(self, node: vs.VideoNode) -> VideoOutputNode:
        ...

    @overload
    def get_node(self, node: vs.VideoNode) -> vs.VideoNode | VideoOutputNode:
        ...

    def get_node(self, node: vs.VideoNode) -> vs.VideoNode | VideoOutputNode:
        raise NotImplementedError

    def init_outputs(self) -> None:
        assert self.main.outputs

        self.outputs.clear()

        for output in self.main.outputs:
            self.outputs[output] = output.with_node(self.get_node(output.source.clip))

    def on_current_frame_changed(self, frame: Frame) -> None:
        raise NotImplementedError


class MappedNodesViewPlugin(MappedNodesPlugin, GraphicsView):
    def on_current_frame_changed(self, frame: Frame) -> None:
        self.outputs.current.render_frame(frame, None, None, self.current_scene)
