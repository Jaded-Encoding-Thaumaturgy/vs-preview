from __future__ import annotations

from collections import defaultdict
from enum import Flag
from typing import TYPE_CHECKING, Any, Callable

from PyQt6.QtCore import QKeyCombination, QObject, Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent, QKeySequence, QMouseEvent
from PyQt6.QtWidgets import QBoxLayout, QLabel, QWidget

from ..core import (
    AbstractSettingsScrollArea, HBoxLayout, LineEdit, PushButton, QAbstractYAMLObjectSingleton,
    QYAMLObject, Shortcut, yaml_Loader
)
from ..models import GeneralModel

if TYPE_CHECKING:
    from ..core import Stretch


__all__ = [
    "AbtractShortcutSection",
    "AbtractShortcutSectionYAMLObjectSingleton",
    "AbtractShortcutSectionQYAMLObject",
    "ShortCutLineEdit",
    "ResetPushButton",
    "TitleLabel",
    "Modifier",
    "ModifierModel",
]


MODIFIERS_KEYS = (
    Qt.Key.Key_Control,
    Qt.Key.Key_Alt,
    Qt.Key.Key_Shift,
    Qt.Key.Key_Meta,
)


MAX_WIDTH_LINE_EDIT = 90


class ShortCutLineEdit(LineEdit):
    keyPressed = pyqtSignal(str)
    _shortcuts: defaultdict[str, set[ShortCutLineEdit]] = defaultdict(set)

    def __init__(
        self,
        *args: QWidget | QBoxLayout | Stretch,
        placeholder: str = "",
        tooltip: str | None = None,
        allow_modifiers: bool = True,
        conflictable: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(placeholder, *args, tooltip=tooltip, **kwargs)

        self.allow_modifiers = allow_modifiers
        self._conflictable = conflictable

        self.keyPressed.connect(self.setText)
        self.textChanged.connect(self.highlight_conflits)

        self.setMaximumWidth(MAX_WIDTH_LINE_EDIT)

        self._old_text = self.text()

    def highlight_conflits(self, text: str | None) -> None:
        if text is None:
            return

        if text and self._conflictable:
            self.setProperty("conflictShortcut", False)
            self.repolish()

            self._shortcuts[self._old_text].discard(self)

            if len(shorcuts := self._shortcuts[self._old_text]) <= 1:
                for sc in shorcuts:
                    sc.setProperty("conflictShortcut", False)
                    sc.repolish()

            self._shortcuts[text].add(self)

            if len(conflicts := self._shortcuts[text]) > 1:
                for c in conflicts:
                    c.setProperty("conflictShortcut", True)
                    c.repolish()

        self._old_text = text

    def keyPressEvent(self, a0: QKeyEvent | None) -> None:
        if not a0:
            return None

        key = Qt.Key(a0.key())
        modifiers = a0.modifiers()

        if key in MODIFIERS_KEYS:
            keyname = self.text()
        elif self.allow_modifiers:
            keyname = QKeySequence(QKeyCombination(modifiers, key).toCombined()).toString()
        else:
            keyname = QKeySequence(key).toString()

        self.keyPressed.emit(keyname)

    def mouseDoubleClickEvent(self, a0: QMouseEvent | None) -> None:
        if not a0:
            return None

        self.setText(None)

    def repolish(self) -> None:
        if style := self.style():
            style.unpolish(self)
            style.polish(self)


class ResetPushButton(PushButton):
    def __init__(
        self, name: str = "Reset", *args: QWidget | QBoxLayout | Stretch, tooltip: str | None = None, **kwargs: Any
    ) -> None:
        super().__init__(name, *args, tooltip=tooltip, **kwargs)
        self.setMaximumWidth(55)

    def make_hidden(self) -> None:
        self.setText(None)
        self.setFlat(True)
        self.setEnabled(False)


class TitleLabel(QLabel):
    def __init__(self, text: str, md_header: str = "##") -> None:
        super().__init__()
        self.setTextFormat(Qt.TextFormat.MarkdownText)
        self.setText(f"{md_header} {text}")
        self.updateGeometry()


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

yaml_Loader.add_constructor(
    'tag:yaml.org,2002:python/object/apply:vspreview.shortcuts.abstract.Modifier',
    lambda self, node: Modifier(self.construct_sequence(node)[0])  # type: ignore
)


class ModifierModel(GeneralModel[Modifier]):
    def _displayValue(self, value: Modifier) -> str:
        return QKeySequence(value.value).toString()[:-1]


class AbtractShortcutSection:
    parent: AbstractSettingsScrollArea

    def setup_ui(self) -> None: ...

    def setup_ui_shortcut(
        self, label: str, widget: QWidget, default: QKeySequence | None = None, hide_reset: bool = False
    ) -> None:
        button = ResetPushButton("Reset", self.parent)

        if not isinstance(widget, ShortCutLineEdit) or hide_reset or default is None:
            button.make_hidden()
        else:
            widget.setText(default.toString())
            button.clicked.connect(lambda: widget.setText(default.toString()))
    
        HBoxLayout(self.parent.vlayout, [QLabel(label), widget, button])

    def setup_shortcuts(self) -> None: ...

    def create_shortcut(
        self,
        key: ShortCutLineEdit | QKeySequence | QKeySequence.StandardKey | str | int | None,
        parent: QObject | None,
        handler: Callable[[], None],
    ) -> None:
        if isinstance(key, str) and not key:
            return None

        if isinstance(key, ShortCutLineEdit):
            key = key.text()

        Shortcut(key, parent, handler)

    @property
    def unassigned_default(self) -> QKeySequence:
        return QKeySequence()

    def __getstate__(self) -> dict[str, Any]:
        return {}

    def __setstate__(self, state: dict[str, Any]) -> None: ...


class AbtractShortcutSectionYAMLObjectSingleton(AbtractShortcutSection, QAbstractYAMLObjectSingleton): ...


class AbtractShortcutSectionQYAMLObject(AbtractShortcutSection, QYAMLObject): ...
