from __future__ import annotations

import logging
import inspect
from pathlib import Path
import vapoursynth as vs
from abc import abstractmethod
from functools import lru_cache
from typing import Any, cast, Mapping, Iterator, TYPE_CHECKING, Tuple, List, Type, TypeVar

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

    if TYPE_CHECKING:
        @property
        def app_settings(self) -> AbstractAppSettings: ...
        @app_settings.setter
        def app_settings(self) -> None: ...
        @property
        def central_widget(self) -> QWidget: ...
        @central_widget.setter
        def central_widget(self) -> None: ...
        @property
        def clipboard(self) -> QClipboard: ...
        @clipboard.setter
        def clipboard(self) -> None: ...
        @property
        def current_frame(self) -> Frame: ...
        @current_frame.setter
        def current_frame(self) -> None: ...
        @property
        def current_output(self) -> VideoOutput: ...
        @current_output.setter
        def current_output(self) -> None: ...
        @property
        def display_scale(self) -> float: ...
        @display_scale.setter
        def display_scale(self) -> None: ...
        @property
        def graphics_scene(self) -> QGraphicsScene: ...
        @graphics_scene.setter
        def graphics_scene(self) -> None: ...
        @property
        def graphics_view(self) -> QGraphicsView: ...
        @graphics_view.setter
        def graphics_view(self) -> None: ...
        @property
        def outputs(self) -> VideoOutputs: ...
        @property
        def timeline(self) -> Timeline: ...
        @timeline.setter
        def timeline(self) -> None: ...
        @property
        def toolbars(self) -> AbstractToolbars: ...
        @toolbars.setter
        def toolbars(self) -> None: ...
        @property
        def save_on_exit(self) -> bool: ...
        @save_on_exit.setter
        def save_on_exit(self) -> None: ...
        @property
        def script_path(self) -> Path: ...
        @script_path.setter
        def script_path(self) -> None: ...
        @property
        def statusbar(self) -> QStatusBar: ...
        @statusbar.setter
        def statusbar(self) -> None: ...
    else:
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

    def __init__(self, main: AbstractMainWindow, name: str, settings: QWidget) -> None:
        super().__init__(main.central_widget)
        self.main = main
        self.settings = settings

        self.main.app_settings.addTab(self.settings, name)
        self.setFocusPolicy(Qt.ClickFocus)

        self.notches_changed.connect(self.main.timeline.update_notches)

        self.toggle_button = QPushButton(self)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setText(name)
        self.toggle_button.clicked.connect(self.on_toggle)

        self.setVisible(False)
        self.visibility = False

    def on_toggle(self, new_state: bool) -> None:
        if new_state == self.visibility:
            return
        # invoking order matters
        self.setVisible(new_state)
        self.visibility = new_state
        self.toggle_button.setChecked(new_state)
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


class _OneArgumentFunction():
    def __call__(self, _arg0: T) -> Any:
        ...


class _SetterFunction():
    def __call__(self, _arg0: str, _arg1: T) -> Any:
        ...


def storage_err_msg(name: str, level: int = 0) -> str:
    pretty_name = name.replace('current_', ' ').replace('_enabled', ' ').replace('_', ' ').strip()
    caller_name = inspect.stack()[level + 1][0].f_locals['self'].__class__.__name__

    return f'Storage loading ({caller_name}): failed to parse {pretty_name}. Using default.'


def try_load(
    state: Mapping[str, Any], name: str, expected_type: Type[T],
    receiver: T | _OneArgumentFunction | _SetterFunction,
    error_msg: str | None = None, nullable: bool = False
) -> None:
    if error_msg is None:
        error_msg = storage_err_msg(name, 1)

    error = False

    try:
        value = state[name]
        if not isinstance(value, expected_type) and not (nullable and value is None):
            raise TypeError
    except (KeyError, TypeError):
        error = True
        logging.warning(error_msg)
    finally:
        if nullable:
            error = False
            value = None

    if not error:
        if isinstance(receiver, expected_type):
            receiver = value
        elif callable(receiver):
            try:
                cast(_SetterFunction, receiver)(name, value)
            except Exception:
                cast(_OneArgumentFunction, receiver)(value)
        elif hasattr(receiver, name) and isinstance(getattr(receiver, name), expected_type):
            try:
                receiver.__setattr__(name, value)
            except AttributeError:
                logging.warning(error_msg)
