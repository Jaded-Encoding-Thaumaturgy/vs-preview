from __future__ import annotations

import logging
from pathlib import Path
import vapoursynth as vs
from abc import abstractmethod
from functools import lru_cache
from typing import Any, cast, Mapping, Iterator, TYPE_CHECKING, Tuple, List, Callable, Type, TypeVar

from .better_abc import abstract_attribute
from .bases import AbstractYAMLObjectSingleton, QABC, QAbstractYAMLObjectSingleton

from PyQt5.QtGui import QClipboard
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QDialog, QPushButton, QGraphicsScene, QGraphicsView, QStatusBar
)

if TYPE_CHECKING:
    from ..models import VideoOutputs
    from ..widgets import Timeline, Notches
    from .types import Frame, VideoOutput, Time


T = TypeVar('T')


class AbstractMainWindow(QMainWindow, QAbstractYAMLObjectSingleton):
    __slots__ = ()

    @abstractmethod
    def load_script(
        self, script_path: Path, external_args: List[Tuple[str, str]] | None = [], reloading: bool = False
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def reload_script(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def init_outputs(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def switch_output(self, value: int | VideoOutput) -> None:
        raise NotImplementedError

    @abstractmethod
    def switch_frame(self, pos: Frame | Time | None, *, render_frame: bool | vs.VideoFrame = True) -> None:
        raise NotImplementedError()

    @abstractmethod
    def show_message(self, message: str) -> None:
        raise NotImplementedError

    app_settings: AbstractAppSettings = abstract_attribute()
    central_widget: QWidget = abstract_attribute()
    clipboard: QClipboard = abstract_attribute()
    current_frame: Frame = abstract_attribute()
    current_output: VideoOutput = abstract_attribute()
    display_scale: float = abstract_attribute()
    graphics_scene: QGraphicsScene = abstract_attribute()
    graphics_view: QGraphicsView = abstract_attribute()
    outputs: VideoOutputs = abstract_attribute()
    timeline: Timeline = abstract_attribute()
    toolbars: AbstractToolbars = abstract_attribute()
    save_on_exit: bool = abstract_attribute()
    script_path: Path = abstract_attribute()
    statusbar: QStatusBar = abstract_attribute()


class AbstractToolbar(QWidget, QABC):
    __slots__ = ('main', 'toggle_button',)

    if TYPE_CHECKING:
        notches_changed = pyqtSignal(AbstractToolbar)  # noqa: F821
    else:
        notches_changed = pyqtSignal(object)

    def __init__(self, main: AbstractMainWindow, name: str, settings: QWidget | None = None) -> None:
        super().__init__(main.central_widget)
        self.main = main
        self.settings = settings if settings is not None else QWidget()

        self.main.app_settings.addTab(self.settings, name)
        self.setFocusPolicy(Qt.ClickFocus)

        self.notches_changed.connect(self.main.timeline.update_notches)

        self.toggle_button = QPushButton(self)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setText(name)
        self.toggle_button.clicked.connect(self.on_toggle)

        self.setVisible(False)

    def on_toggle(self, new_state: bool) -> None:
        # invoking order matters
        self.setVisible(new_state)
        self.resize_main_window(new_state)

    def on_current_frame_changed(self, frame: Frame) -> None:
        pass

    def on_current_output_changed(self, index: int, prev_index: int) -> None:
        pass

    def get_notches(self) -> Notches:
        from ..widgets import Notches

        return Notches()

    def is_notches_visible(self) -> bool:
        return self.isVisible()

    def resize_main_window(self, expanding: bool) -> None:
        if self.main.windowState() in map(Qt.WindowStates, {Qt.WindowMaximized, Qt.WindowFullScreen}):
            return

        if expanding:
            self.main.resize(self.main.width(), self.main.height() + self.height() + round(6 * self.main.display_scale))
        if not expanding:
            self.main.resize(self.main.width(), self.main.height() - self.height() - round(6 * self.main.display_scale))
            self.main.timeline.full_repaint()

    def __getstate__(self) -> Mapping[str, Any]:
        return {}

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        pass


class AbstractAppSettings(QDialog, QABC):
    @abstractmethod
    def addTab(self, widget: QWidget, label: str) -> int:
        raise NotImplementedError


class AbstractToolbars(AbstractYAMLObjectSingleton):
    yaml_tag: str = abstract_attribute()

    __slots__ = ()

    # special toolbar ignored by len() and not accessible via subscription and 'in' operator
    main: AbstractToolbar = abstract_attribute()

    playback: AbstractToolbar = abstract_attribute()
    scening: AbstractToolbar = abstract_attribute()
    pipette: AbstractToolbar = abstract_attribute()
    benchmark: AbstractToolbar = abstract_attribute()
    misc: AbstractToolbar = abstract_attribute()
    debug: AbstractToolbar = abstract_attribute()

    toolbars_names = ('playback', 'scening', 'pipette', 'benchmark', 'misc', 'debug')

    # 'main' should be the first
    all_toolbars_names = ['main'] + list(toolbars_names)

    _max = len(all_toolbars_names)
    _cidx = 0

    def __getitem__(self, index: int) -> AbstractToolbar:
        if index >= len(self.toolbars_names):
            raise IndexError
        return cast(AbstractToolbar, getattr(self, self.toolbars_names[index]))

    def __len__(self) -> int:
        return len(self.toolbars_names)

    @abstractmethod
    def __getstate__(self) -> Mapping[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def __setstate__(self, state: Mapping[str, Any]) -> None:
        raise NotImplementedError

    if TYPE_CHECKING:
        # https://github.com/python/mypy/issues/2220
        def __iter__(self) -> Iterator[AbstractToolbar]: ...


@lru_cache()
def main_window() -> AbstractMainWindow:
    app = QApplication.instance()

    if app is not None:
        for widget in app.topLevelWidgets():
            if isinstance(widget, AbstractMainWindow):
                return cast(AbstractMainWindow, widget)
        app.exit()

    logging.critical('main_window() failed')

    raise RuntimeError


def try_load(
        state: Mapping[str, Any],
        name: str, ty: Type[T],
        receiver: T | Callable[[T], Any] | Callable[[str, T], Any],
        error_msg: str) -> None:
    try:
        value = state[name]
        if not isinstance(value, ty):
            raise TypeError
    except (KeyError, TypeError):
        logging.warning(error_msg)
    else:
        if isinstance(receiver, ty):
            receiver = value
        elif callable(receiver):
            try:
                receiver(name, value)  # type: ignore
            except Exception:
                receiver(value)  # type: ignore
        elif hasattr(receiver, name) and isinstance(getattr(receiver, name), ty):
            try:
                receiver.__setattr__(name, value)
            except AttributeError:
                logging.warning(error_msg)
