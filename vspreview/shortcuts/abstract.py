from enum import Flag
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QKeyCombination, QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QKeyEvent, QKeySequence, QShortcut
from PyQt6.QtWidgets import QLabel

from ..core import (
    AbstractSettingsWidget, AbstractYAMLObjectSingleton, CheckBox, ComboBox, HBoxLayout, LineEdit,
    PushButton, Shortcut, VBoxLayout, YAMLObjectWrapper, try_load
)
from ..models import GeneralModel

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QBoxLayout, QWidget

    from ..core import Stretch
else:
    Stretch, QWidget, QBoxLayout = Any, Any, Any

__all__ = [
    'AbtractShortcutSection',
    'ShortCutLineEdit', 'ResetPushButton', 'Modifier', 'ModifierModel'
]


MODIFIERS_KEYS = (
    Qt.Key.Key_Control,
    Qt.Key.Key_Alt,
    Qt.Key.Key_Shift,
    Qt.Key.Key_Meta,
)

class ShortCutLineEdit(LineEdit):
    keyPressed = pyqtSignal(str)

    def __init__(
        self, *args: QWidget | QBoxLayout | Stretch, placeholder: str = "", tooltip: str | None = None,
        allow_modifiers: bool = True, **kwargs: Any
    ) -> None:
        super().__init__(placeholder, *args, tooltip=tooltip, **kwargs)

        self.allow_modifiers = allow_modifiers

        self.keyPressed.connect(self.setText)
        self.setMaximumWidth(75)

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if not a0:
            return None

        key = Qt.Key(a0.key())
        modifiers = a0.modifiers()

        if key in MODIFIERS_KEYS:
            keyname = self.text()
        elif self.allow_modifiers:
            keyname = QKeySequence(
                QKeyCombination(modifiers, key).toCombined()
            ).toString()
        else:
            keyname = QKeySequence(key).toString()

        self.keyPressed.emit(keyname)


class ResetPushButton(PushButton):
    def __init__(self, *args: QWidget | QBoxLayout | Stretch, tooltip: str | None = None, **kwargs: Any) -> None:
        super().__init__("Reset", *args, tooltip=tooltip, **kwargs)
        self.setMaximumWidth(55)


# Has to make this because the yaml serializer was writing 
# !!python/object/apply:PyQt6.QtCore.Modifier
# And thus raise this error:
# (while constructing a Python object cannot find 'Modifier' in the module 'PyQt6.QtCore')
class Modifier(Flag):
    META = Qt.Modifier.META.value
    SHIFT = Qt.Modifier.SHIFT.value
    CTRL = Qt.Modifier.CTRL.value
    ALT = Qt.Modifier.ALT.value

    @property
    def modifier(self) -> Qt.Modifier:
        return Qt.Modifier(self.value)


class ModifierModel(GeneralModel[Modifier]):
    def _displayValue(self, value: Modifier) -> str:
        return QKeySequence(value.value).toString()[:-1]


class AbtractShortcutSection(AbstractYAMLObjectSingleton):
    parent: AbstractSettingsWidget

    def setup_ui(self) -> None:
        ...

    def setup_ui_shortcut(self, label: str, widget: QWidget, default: QKeySequence | None = None) -> None:
        childrens: list[QWidget] = [QLabel(label), widget]

        if default and isinstance(widget, ShortCutLineEdit):
            childrens.append(ResetPushButton(self.parent, clicked=lambda: widget.setText(default.toString())))

        HBoxLayout(self.parent.vlayout, childrens, alignment=Qt.AlignmentFlag.AlignLeft)

    def set_defaults(self) -> None:
        ...

    def setup_shortcuts(self) -> None:
        ...

    def __getstate__(self) -> dict[str, Any]:
        return {}

    def __setstate__(self, state: dict[str, Any]) -> None:
        ...
