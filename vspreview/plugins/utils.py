from __future__ import annotations

from typing import TYPE_CHECKING, Callable, overload

from PyQt6.QtWidgets import QSizePolicy, QWidget
from vstools import vs, vs_object

from ..core import Frame, GraphicsView, VideoOutput, VideoOutputNode, main_window
from .abstract import AbstractPlugin

if TYPE_CHECKING:
    from ..main import MainWindow

__all__ = [
    'PluginVideoOutputs', 'LazyMapPluginVideoOutputs',

    'MappedNodesPlugin', 'MappedNodesViewPlugin',

    'PluginGraphicsView'
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


class LazyMapPluginVideoOutputs(PluginVideoOutputs):
    def __init__(self, main: MainWindow | None, func: Callable[[vs.VideoNode], vs.VideoNode]) -> None:
        super().__init__(main)
        self.func = func

    def __getitem__(self, key: VideoOutput) -> VideoOutput:
        if key not in self:
            self[key] = key.with_node(self.func(key.source.clip))

        return super().__getitem__(key)


class MappedNodesPlugin(AbstractPlugin):
    def __init__(self, main: MainWindow) -> None:
        super().__init__(main)

        self.outputs = LazyMapPluginVideoOutputs(main, self.get_node)

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

    def reset(self) -> None:
        self.init_outputs()

        self.on_current_frame_changed(self.main.current_output.last_showed_frame)

    def on_current_frame_changed(self, frame: Frame) -> None:
        raise NotImplementedError


class PluginGraphicsView(GraphicsView):
    plugin: MappedNodesPlugin

    def __init__(
        self, main: MainWindow | MappedNodesPlugin, plugin: MappedNodesPlugin | None = None,
        parent: QWidget | None = None
    ) -> None:
        if isinstance(main, MappedNodesPlugin):
            plugin = main
            main = main.main

        super().__init__(main, parent)

        if plugin:
            self.plugin = plugin
            self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
        elif isinstance(self, MappedNodesPlugin):
            self.plugin = self
        else:
            raise RuntimeError('This GraphicsView has to be bound to a MappedNodesPlugin!')

        if isinstance(self, AbstractPlugin):
            self.plugin.on_first_load.connect(PluginGraphicsView.first_load.__get__(self))
        else:
            self.plugin.on_first_load.connect(self.first_load)

    def first_load(self) -> None:
        self.graphics_scene.init_scenes()
        self.setup_view()

    @property
    def content_width(self) -> int:
        return self.plugin.outputs.current.width

    @property
    def content_height(self) -> int:
        return self.plugin.outputs.current.height


class MappedNodesViewPlugin(MappedNodesPlugin, PluginGraphicsView):
    def on_current_frame_changed(self, frame: Frame) -> None:
        self.outputs.current.render_frame(frame, None, None, self.current_scene)
