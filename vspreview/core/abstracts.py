from __future__ import annotations

from abc import abstractmethod
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Callable, ClassVar, Literal, Sequence, TypeAlias, cast, overload

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication, QBoxLayout, QCheckBox, QDialog, QDoubleSpinBox, QFrame, QHBoxLayout, QLineEdit,
    QProgressBar, QPushButton, QScrollArea, QSpacerItem, QSpinBox, QTableView, QVBoxLayout, QWidget
)

from .bases import QABC, QYAMLObjectSingleton, SafeYAMLObject

if TYPE_CHECKING:
    from jetpytools import T

    from ..main import MainWindow
    from .custom import Notches
    from .types import Frame, Stretch

    LayoutChildT: TypeAlias = QWidget | QBoxLayout | Stretch | QSpacerItem
else:
    LayoutChildT: TypeAlias = Any


__all__ = [
    'HBoxLayout', 'VBoxLayout',

    'SpinBox', 'PushButton', 'LineEdit', 'CheckBox', 'Timer', 'ProgressBar', 'DoubleSpinBox',

    'Shortcut',

    'AbstractQItem', 'AbstractYAMLObject',

    'ExtendedWidgetBase', 'ExtendedWidget', 'ExtendedDialog', 'ExtendedTableView', 'ExtendedScrollArea',

    'NotchProvider',

    'AbstractSettingsWidget', 'AbstractSettingsScrollArea',

    'AbstractToolbar', 'AbstractToolbarSettings',

    'main_window', 'storage_err_msg', 'try_load',
]


class ExtendedLayout(QBoxLayout):
    @overload
    def __init__(self) -> None:
        ...

    @overload
    def __init__(self, init_value: QWidget | QBoxLayout | None, **kwargs: Any) -> None:
        ...

    @overload
    def __init__(self, init_value: LayoutChildT | Sequence[LayoutChildT] | None, **kwargs: Any) -> None:
        ...

    @overload
    def __init__(
        self, parent: QWidget | QBoxLayout | None = None,
        children: LayoutChildT | Sequence[LayoutChildT] | None = None, **kwargs: Any
    ) -> None:
        ...

    def __init__(  # type: ignore
        self, arg0: QWidget | QBoxLayout | None = None,
        arg1: LayoutChildT | Sequence[LayoutChildT] | None = None,
        spacing: int | None = None, alignment: Qt.AlignmentFlag | None = None, **kwargs: Any
    ) -> ExtendedLayout:
        from .types import Stretch

        try:
            if isinstance(arg0, QBoxLayout):
                super().__init__(**kwargs)
                arg0.addLayout(self)
                arg0 = None
            elif isinstance(arg0, QWidget):
                super().__init__(arg0, **kwargs)  # type: ignore
                arg0 = None
            else:
                raise BaseException()
        except BaseException:
            super().__init__(**kwargs)

            if not any((arg0, arg1)):
                return  # type: ignore

        items = [u for s in (t if isinstance(t, Sequence) else [t] if t else [] for t in [arg0, arg1]) for u in s]

        for item in items:
            if isinstance(item, QBoxLayout):
                self.addLayout(item)
            elif isinstance(item, QSpacerItem):
                self.addSpacerItem(item)
            elif isinstance(item, Stretch):
                self.addStretch(item.amount)
            else:
                self.addWidget(item)

        for arg, action in ((spacing, 'setSpacing'), (alignment, 'setAlignment')):
            if arg is not None:
                getattr(self, action)(arg)

    def addWidgets(self, widgets: Sequence[QWidget]) -> None:
        for widget in widgets:
            self.addWidget(widget)

    def addLayouts(self, layouts: Sequence[QBoxLayout]) -> None:
        for layout in layouts:
            self.addLayout(layout)

    def clear(self) -> None:
        for i in reversed(range(self.count())):
            item = self.itemAt(i)
            widget = item.widget()
            self.removeItem(item)
            if widget:
                # removeItem only takes it out of the layout. The widget
                # still exists inside its parent widget.
                widget.deleteLater()
            else:
                # Clear and delete sub-layouts
                if isinstance(item, ExtendedLayout):
                    item.clear()
                item.deleteLater()  # type: ignore

    @staticmethod
    def stretch(amount: int | None) -> Stretch:  # type: ignore
        from .types import Stretch

        return Stretch(amount)  # type: ignore


class HBoxLayout(QHBoxLayout, ExtendedLayout):
    if TYPE_CHECKING:
        @overload
        def __init__(self) -> None:
            ...

        @overload
        def __init__(self, init_value: QWidget | QBoxLayout | None, **kwargs: Any) -> None:
            ...

        @overload
        def __init__(self, init_value: LayoutChildT | Sequence[LayoutChildT] | None, **kwargs: Any) -> None:
            ...

        @overload
        def __init__(
            self, parent: QWidget | QBoxLayout | None = None,
            children: LayoutChildT | Sequence[LayoutChildT] | None = None, **kwargs: Any
        ) -> None:
            ...

        def __init__(  # type: ignore
            self, arg0: QWidget | QBoxLayout | None = None,
            arg1: LayoutChildT | Sequence[LayoutChildT] | None = None,
            spacing: int | None = None, alignment: Qt.AlignmentFlag | None = None, **kwargs: Any
        ) -> ExtendedLayout:
            ...


class VBoxLayout(QVBoxLayout, ExtendedLayout):
    if TYPE_CHECKING:
        @overload
        def __init__(self) -> None:
            ...

        @overload
        def __init__(self, init_value: QWidget | QBoxLayout | None, **kwargs: Any) -> None:
            ...

        @overload
        def __init__(self, init_value: LayoutChildT | Sequence[LayoutChildT] | None, **kwargs: Any) -> None:
            ...

        @overload
        def __init__(
            self, parent: QWidget | QBoxLayout | None = None,
            children: LayoutChildT | Sequence[LayoutChildT] | None = None, **kwargs: Any
        ) -> None:
            ...

        def __init__(  # type: ignore
            self, arg0: QWidget | QBoxLayout | None = None,
            arg1: LayoutChildT | Sequence[LayoutChildT] | None = None,
            spacing: int | None = None, alignment: Qt.AlignmentFlag | None = None, **kwargs: Any
        ) -> ExtendedLayout:
            ...


class SpinBox(QSpinBox):
    def __init__(
        self, parent: QWidget | None = None, minimum: int | None = None,
        maximum: int | None = None, suffix: str | None = None, tooltip: str | None = None, **kwargs: Any
    ) -> None:
        super().__init__(parent, **kwargs)
        for arg, action in (
            (minimum, 'setMinimum'), (maximum, 'setMaximum'), (suffix, 'setSuffix'), (tooltip, 'setToolTip')
        ):
            if arg is not None:
                getattr(self, action)(arg)


if TYPE_CHECKING:
    ExtItemBase = QWidget
else:
    ExtItemBase = object


class ExtendedItemInit(ExtItemBase):
    def __init__(
        self, *args: QWidget | QBoxLayout | Stretch, tooltip: str | None = None, hidden: bool = False, **kwargs: Any
    ) -> None:
        try:
            super().__init__(*args, **kwargs)  # type: ignore
        except TypeError:
            super().__init__(*args)  # type: ignore

        if tooltip:
            super().setToolTip(tooltip)

        if hidden:
            super().hide()


class ExtendedItemWithName(ExtendedItemInit):
    if TYPE_CHECKING:
        def __init__(
            self, name: str, *args: QWidget | QBoxLayout | Stretch, tooltip: str | None = None, **kwargs: Any
        ) -> None:
            ...


class PushButton(ExtendedItemWithName, QPushButton):
    ...


class LineEdit(ExtendedItemInit, QLineEdit):
    def __init__(
        self, placeholder: str, *args: QWidget | QBoxLayout | Stretch, tooltip: str | None = None, **kwargs: Any
    ) -> None:
        return super().__init__(*args, tooltip=tooltip, **kwargs, placeholderText=placeholder)


class CheckBox(ExtendedItemWithName, QCheckBox):
    ...


class Timer(ExtendedItemInit, QTimer):
    ...


class ProgressBar(ExtendedItemInit, QProgressBar):
    ...


class DoubleSpinBox(ExtendedItemInit, QDoubleSpinBox):
    ...


class Shortcut(QShortcut):
    def __init__(
        self, key: QKeySequence | QKeySequence.StandardKey | str | int | None,
        parent: QObject | None, handler: Callable[[], None]
    ) -> None:
        super().__init__(key, parent)
        self.activated.connect(handler)


class AbstractQItem:
    __slots__: tuple[str, ...]
    storable_attrs: ClassVar[tuple[str, ...]] = ()

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

    def __get_storable_attr__(self) -> tuple[str, ...]:
        return self.storable_attrs

    def __getstate__(self) -> dict[str, Any]:
        return {
            attr_name: getattr(self, attr_name)
            for attr_name in self.__get_storable_attr__()
        }


class AbstractYAMLObject(AbstractQItem, SafeYAMLObject):
    @abstractmethod
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError


class ExtendedWidgetBase(AbstractQItem):
    vlayout: VBoxLayout
    hlayout: HBoxLayout

    def setup_ui(self) -> None:
        self.vlayout = VBoxLayout(self)
        self.hlayout = HBoxLayout(self.vlayout)

    def get_separator(self, horizontal: bool = False) -> QFrame:
        separator = QFrame(self)
        separator.setFrameShape(QFrame.Shape.HLine if horizontal else QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        return separator


class ExtendedWidget(ExtendedWidgetBase, QWidget):
    ...


class ExtendedDialog(AbstractQItem, QDialog):
    ...


class ExtendedTableView(AbstractQItem, QTableView):
    ...


class ExtendedScrollArea(ExtendedWidgetBase, QScrollArea):
    frame: QFrame

    def setup_ui(self) -> None:
        self.setWidgetResizable(True)

        self.frame = QFrame(self)

        super().setup_ui()

        self.frame.setLayout(self.vlayout)

        self.setWidget(self.frame)


class AbstractSettingsWidget(ExtendedWidget, QYAMLObjectSingleton):
    __slots__ = ()

    def __init__(self) -> None:
        super().__init__()

        self.setup_ui()

        self.vlayout.addStretch(1)

        self.set_defaults()

        self.set_qobject_names()

    def set_defaults(self) -> None:
        pass

    def __getstate__(self) -> dict[str, Any]:
        return {}


class AbstractSettingsScrollArea(ExtendedScrollArea, QYAMLObjectSingleton):
    def __init__(self) -> None:
        super().__init__()

        self.setup_ui()

        self.set_defaults()

        self.set_qobject_names()

    def set_defaults(self) -> None:
        pass

    def __getstate__(self) -> dict[str, Any]:
        return {}


class AbstractToolbarSettings(AbstractSettingsWidget):
    _add_to_tab = True

    def __init__(self, parent: type[AbstractToolbar] | AbstractToolbar) -> None:
        self.parent_toolbar_type = parent if isinstance(parent, type) else parent.__class__

        super().__init__()


class NotchProvider(QABC):
    notches_changed = pyqtSignal(ExtendedWidget)

    def init_notches(self, main: MainWindow = ...) -> None:
        self.notches_changed.connect(main.timeline.update_notches)

    def get_notches(self) -> Notches:
        from .custom import Notches
        return Notches()

    @property
    @abstractmethod
    def is_notches_visible(self) -> bool:
        ...


class AbstractToolbar(ExtendedWidget, NotchProvider):
    _no_visibility_choice = False
    storable_attrs = tuple[str, ...]()
    class_storable_attrs = tuple[str, ...](('settings', 'visibility'))
    num_keys = [
        Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3, Qt.Key.Key_4, Qt.Key.Key_5, Qt.Key.Key_6,
        Qt.Key.Key_7, Qt.Key.Key_8, Qt.Key.Key_9, Qt.Key.Key_0
    ]

    __slots__ = ('main', 'toggle_button', *class_storable_attrs)

    main: MainWindow
    name: str

    def __init__(self, main: MainWindow, settings: QWidget | None = None) -> None:
        super().__init__(main.central_widget)

        if settings is None:
            from jetpytools import CustomValueError

            raise CustomValueError('Missing settings widget!')

        self.main = main
        self.settings = settings
        self.name = self.__class__.__name__[:-7]

        if settings._add_to_tab:
            self.main.app_settings.addTab(settings, self.name)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

        self.toggle_button = PushButton(
            self.name, self, checkable=True, clicked=self.on_toggle
        )
        self.toggle_button.setVisible(not self._no_visibility_choice)

        self.setVisible(False)
        self.visibility = False

        self.init_notches(self.main)

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

    @property
    def is_notches_visible(self) -> bool:
        return self.visibility

    def resize_main_window(self, expanding: bool) -> None:
        if self.main.windowState() in {Qt.WindowState.WindowMaximized, Qt.WindowState.WindowFullScreen}:
            return

        if expanding:
            self.main.resize(self.main.width(), self.main.height() + self.height() + round(6 * self.main.display_scale))
        if not expanding:
            self.main.resize(self.main.width(), self.main.height() - self.height() - round(6 * self.main.display_scale))
            self.main.timeline.update()

    def __get_storable_attr__(self) -> tuple[str, ...]:
        attributes = list(self.class_storable_attrs + self.storable_attrs)

        if self._no_visibility_choice:
            attributes.remove('visibility')

        return tuple(attributes)

    def __setstate__(self, state: dict[str, Any]) -> None:
        if not self._no_visibility_choice:
            try_load(state, 'visibility', bool, self.on_toggle)
        try_load(state, 'settings', AbstractToolbarSettings, self.__setattr__)


@lru_cache()
def main_window() -> MainWindow:
    import logging

    from ..main.window import MainWindow

    app = QApplication.instance()

    if app is not None:
        for widget in app.topLevelWidgets():  # type: ignore
            if isinstance(widget, MainWindow):
                return cast(MainWindow, widget)
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
    import inspect

    pretty_name = name.replace('current_', ' ').replace('_enabled', ' ').replace('_', ' ').strip()
    frame = inspect.stack()[level + 1]
    caller_name = frame[0].f_locals['self'].__class__.__name__
    frame = None

    return f'Storage loading ({caller_name}): failed to parse {pretty_name}. Using default.'


@overload
def try_load(
    state: dict[str, Any], name: str, expected_type: type[T],
    receiver: Literal[None] = ...,
    error_msg: str | None = None, nullable: bool = False
) -> T:
    ...


@overload
def try_load(
    state: dict[str, Any], name: str, expected_type: type[T],
    receiver: T | _OneArgumentFunction | _SetterFunction = ...,
    error_msg: str | None = None, nullable: bool = False
) -> None:
    ...


def try_load(
    state: dict[str, Any], name: str, expected_type: type[T],
    receiver: T | _OneArgumentFunction | _SetterFunction | None = None,
    error_msg: str | None = None, nullable: bool = False
) -> None:
    import logging

    if error_msg is None:
        error_msg = storage_err_msg(name, 1)

    try:
        value = state[name]
        if not isinstance(value, expected_type) and not (nullable and value is None):
            raise TypeError
    except (KeyError, TypeError) as e:
        logging.error(e)
        logging.warning(error_msg)
        return
    finally:
        if nullable:
            value = None

    if receiver is None:
        return value

    if isinstance(receiver, expected_type):
        receiver = value
    elif callable(receiver):
        from inspect import Signature, _ParameterKind

        try:
            len_params = len([
                x for x in Signature.from_callable(receiver).parameters.values()
                if x.kind in (_ParameterKind.POSITIONAL_ONLY, _ParameterKind.POSITIONAL_OR_KEYWORD)
            ])

            if len_params >= 2:
                param_tries = [2, 1, 0]
            elif len_params >= 1:
                param_tries = [1, 0, 2]
            else:
                param_tries = [0, 1, 2]
        except ValueError:
            param_tries = [2, 1, 0]

        exceptions = []

        for ptry in param_tries:
            try:
                if ptry == 2:
                    receiver(name, value)
                elif ptry == 1:
                    receiver(value)
                elif ptry == 0:
                    receiver()
            except Exception as e:
                exceptions.append(e)
            else:
                exceptions.clear()
                break

        if exceptions:
            filtered = [
                e for e in exceptions if 'positional arguments but' not in str(e)
            ]

            return main_window().handle_error(filtered[0] if filtered else exceptions[0])
    elif hasattr(receiver, name) and isinstance(getattr(receiver, name), expected_type):
        try:
            receiver.__setattr__(name, value)
        except AttributeError as e:
            logging.error(e)
            logging.warning(error_msg)
