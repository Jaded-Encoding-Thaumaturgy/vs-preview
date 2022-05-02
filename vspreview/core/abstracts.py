from __future__ import annotations

import logging
import inspect
from pathlib import Path
import vapoursynth as vs
from abc import abstractmethod
from functools import lru_cache
from typing import Any, cast, Mapping, TYPE_CHECKING, Tuple, List, Type, TypeVar, Sequence, overload, Callable

from PyQt5.QtGui import QClipboard
from PyQt5.QtGui import QKeySequence
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QDialog, QPushButton, QGraphicsScene, QShortcut, QCheckBox,
    QGraphicsView, QStatusBar, QFrame, QBoxLayout, QVBoxLayout, QHBoxLayout, QSpinBox, QLineEdit,
    QTableView, QSpacerItem
)

from .better_abc import abstract_attribute
from .bases import QABC, QAbstractYAMLObjectSingleton, QYAMLObjectSingleton


if TYPE_CHECKING:
    from ..models import VideoOutputs
    from .types import Frame, VideoOutput, Time
    from ..main.timeline import Timeline, Notches


T = TypeVar('T')


class ExtendedLayout(QBoxLayout):
    @overload
    def __init__(self) -> None: ...
    @overload
    def __init__(self, parent: QWidget | QBoxLayout | None) -> None: ...
    @overload
    def __init__(self, children: Sequence[QWidget] | None) -> None: ...
    @overload
    def __init__(self, children: Sequence[QBoxLayout] | None) -> None: ...

    @overload
    def __init__(
        self, parent: QWidget | QBoxLayout | None = None, children: Sequence[QWidget | QBoxLayout] | None = None
    ) -> None: ...

    def __init__(
        self, arg0: QWidget | QBoxLayout | None = None, arg1: Sequence[QWidget | QBoxLayout] | None = None, **kwargs
    ) -> ExtendedLayout:
        try:
            if isinstance(arg0, QBoxLayout):
                super().__init__(**kwargs)
                arg0.addLayout(self)
                arg0 = []
            elif isinstance(arg0, QWidget):
                super().__init__(arg0, **kwargs)
                arg0 = []
            else:
                raise BaseException()
        except BaseException:
            super().__init__(**kwargs)
            if not any((arg0, arg1)):
                return

        items = [u for s in (t if isinstance(t, Sequence) else [t] if t else [] for t in [arg0, arg1]) for u in s]

        for item in items:
            print(type(item))
            if isinstance(item, QBoxLayout):
                self.addLayout(item)
            elif isinstance(item, QSpacerItem):
                self.addSpacerItem(item)
            else:
                self.addWidget(item)

    def addWidgets(self, widgets: Sequence[QWidget]) -> None:
        for widget in widgets:
            self.addWidget(widget)

    def addLayouts(self, layouts: Sequence[QBoxLayout]) -> None:
        for layout in layouts:
            self.addLayout(layout)


class HBoxLayout(QHBoxLayout, ExtendedLayout):
    ...


class VBoxLayout(QVBoxLayout, ExtendedLayout):
    ...


class SpinBox(QSpinBox):
    def __init__(
        self, parent: QWidget | None = None, minimum: int | None = None,
        maximum: int | None = None, suffix: str | None = None, tooltip: str | None = None, **kwargs
    ) -> None:
        super().__init__(parent, **kwargs)
        for arg, action in (
            (minimum, 'setMinimum'), (maximum, 'setMaximum'), (suffix, 'setSuffix'), (tooltip, 'setToolTip')
        ):
            if arg is not None:
                getattr(self, action)(arg)


class ExtendedItemInit():
    def __init__(self, *args, tooltip: str | None = None, **kwargs) -> None:
        try:
            super().__init__(*args, **kwargs)
        except TypeError:
            super().__init__(*args)
        if tooltip:
            super().setToolTip(tooltip)


class PushButton(ExtendedItemInit, QPushButton):
    ...


class LineEdit(ExtendedItemInit, QLineEdit):
    ...


class CheckBox(ExtendedItemInit, QCheckBox):
    ...


class AbstractQItem():
    storable_attrs = tuple()

    def add_shortcut(self, key: int, handler: Callable[[], None]) -> None:
        QShortcut(QKeySequence(key), self, activated=handler)

    def set_qobject_names(self) -> None:
        if not hasattr(self, '__slots__'):
            return

        slots = list(self.__slots__)

        if isinstance(self, AbstractToolbar) and 'main' in slots:
            slots.remove('main')

        for attr_name in slots:
            attr = getattr(self, attr_name)
            if not isinstance(attr, QObject):
                continue
            attr.setObjectName(type(self).__name__ + '.' + attr_name)

    def __get_storable_attr__(self) -> Tuple[str, ...]:
        return self.storable_attrs

    def __getstate__(self) -> Mapping[str, Any]:
        return {
            attr_name: getattr(self, attr_name)
            for attr_name in self.__get_storable_attr__()
        }


class AbstractYAMLObject(AbstractQItem):
    ...


class ExtendedWidget(AbstractQItem, QWidget):
    vlayout: VBoxLayout
    hlayout: HBoxLayout

    def setup_ui(self) -> None:
        self.vlayout = VBoxLayout(self)
        self.hlayout = HBoxLayout(self.vlayout)

    def add_shortcuts(self) -> None:
        pass

    def get_separator(self) -> QFrame:
        separator = QFrame(self)
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Sunken)
        return separator


class ExtendedMainWindow(AbstractQItem, QMainWindow):
    def setup_ui(self) -> None:
        ...


class ExtendedDialog(AbstractQItem, QDialog):
    ...


class ExtendedTableView(AbstractQItem, QTableView):
    ...


class AbstractAppSettings(ExtendedDialog):
    @abstractmethod
    def addTab(self, widget: QWidget, label: str) -> int:
        raise NotImplementedError


class AbstractToolbarSettings(ExtendedWidget, QYAMLObjectSingleton):
    __slots__ = ()

    def __init__(self) -> None:
        super().__init__()

        self.setup_ui()
        self.set_defaults()

        self.set_qobject_names()

    def set_defaults(self) -> None:
        pass

    def __getstate__(self) -> Mapping[str, Any]:
        return {}

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        pass


class AbstractMainWindow(ExtendedMainWindow, QAbstractYAMLObjectSingleton):
    __slots__ = ()

    @abstractmethod
    def load_script(
        self, script_path: Path, external_args: List[Tuple[str, str]] | None = None, reloading: bool = False
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
    def switch_frame(
        self, pos: Frame | Time | None, *, render_frame: bool | Tuple[vs.VideoFrame, vs.VideoFrame | None] = True
    ) -> None:
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
        current_output: VideoOutput = abstract_attribute()
        display_scale: float = abstract_attribute()
        graphics_scene: QGraphicsScene = abstract_attribute()
        graphics_view: QGraphicsView = abstract_attribute()
        outputs: VideoOutputs = abstract_attribute()
        timeline: Timeline = abstract_attribute()
        script_path: Path = abstract_attribute()
        statusbar: QStatusBar = abstract_attribute()


class AbstractToolbar(ExtendedWidget, QWidget, QABC):
    _no_visibility_choice = False
    _storable_attrs: Tuple[str, ...] = tuple()
    _class_storable_attrs: Tuple[str, ...] = ('settings', 'visibility')
    num_keys = [
        Qt.Key_1, Qt.Key_2, Qt.Key_3, Qt.Key_4, Qt.Key_5, Qt.Key_6, Qt.Key_7, Qt.Key_8, Qt.Key_9, Qt.Key_0
    ]

    __slots__ = ('main', 'toggle_button', *_class_storable_attrs)

    notches_changed = pyqtSignal(ExtendedWidget)

    def __init__(self, main: AbstractMainWindow, settings: QWidget) -> None:
        super().__init__(main.central_widget)
        self.main = main
        self.settings = settings
        self.name = self.__class__.__name__[:-7]

        self.main.app_settings.addTab(self.settings, self.name)
        self.setFocusPolicy(Qt.ClickFocus)

        self.notches_changed.connect(self.main.timeline.update_notches)

        self.toggle_button = PushButton(
            self.name, self, checkable=True, clicked=self.on_toggle
        )
        self.toggle_button.setVisible(not self._no_visibility_choice)

        self.setVisible(False)
        self.visibility = False

    def setup_ui(self) -> None:
        self.hlayout = HBoxLayout(self)
        self.vlayout = VBoxLayout(self.hlayout)

        self.hlayout.setContentsMargins(0, 0, 0, 0)

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
        from ..main.timeline import Notches

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

    def __get_storable_attr__(self) -> Tuple[str, ...]:
        attributes = list(self._class_storable_attrs + self._storable_attrs)

        if self._no_visibility_choice:
            attributes.remove('visibility')

        return tuple(attributes)

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        if not self._no_visibility_choice:
            try_load(state, 'visibility', bool, self.on_toggle)
        try_load(state, 'settings', AbstractToolbarSettings, self.__setattr__)


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
            except BaseException:
                cast(_OneArgumentFunction, receiver)(value)
        elif hasattr(receiver, name) and isinstance(getattr(receiver, name), expected_type):
            try:
                receiver.__setattr__(name, value)
            except AttributeError:
                logging.warning(error_msg)
