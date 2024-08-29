# from __future__ import annotations

from functools import partial
import logging

from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QKeyCombination, Qt
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QLabel
from vstools import cachedproperty

from ..core import AbstractSettingsWidget, ComboBox, Shortcut, storage_err_msg, try_load
from .abstract import AbtractShortcutSection, Modifier, ModifierModel, ShortCutLineEdit

if TYPE_CHECKING:
    from ..main import MainWindow
else:
    MainWindow = Any


__all__ = [
    'ShortCutsSettings'
]


class ShortCutsSettings(AbstractSettingsWidget):
    main: MainWindow
    sections: dict[str, AbtractShortcutSection]

    def __init__(self, main_window: MainWindow) -> None:
        self.main = main_window

        self.sections = {
            "main": ToolbarMainSection(self),
            # "playback": None,
            # "misc": None,
            # "scening": None,
            # other + plugins ?
        }
        super().__init__()

    def setup_ui(self) -> None:
        super().setup_ui()
        # Title
        self.vlayout.addWidget(QLabel("Toolbars :"))
        # Toolbar main
        self.vlayout.addWidget(QLabel("Main :"))
        self.sections["main"].setup_ui()

        # HBoxLayout(self.vlayout, [QLabel("Playback :")])

        # HBoxLayout(self.vlayout, [QLabel("Misc :")])

        # HBoxLayout(self.vlayout, [QLabel("Scening :")])

        self.main.app_settings.addTab(self, "Shortcuts")

    def set_defaults(self) -> None:
        for section in self.sections.values():
            section.set_defaults()

    def setup_shortcuts(self) -> None:
        for section in self.sections.values():
            section.setup_shortcuts()

    def __getstate__(self) -> dict[str, Any]:
        state = super().__getstate__()

        for name, section in self.sections.items():
            state[name] = section.__getstate__()

        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        for name, section in self.sections.items():
            try:
                storage = state[name]
                if not isinstance(storage, dict):
                    raise TypeError
            except (KeyError, TypeError) as error:
                logging.error(error)
                logging.warning(storage_err_msg(name))
            else:
                section.__setstate__(storage)


class ToolbarMainSection(AbtractShortcutSection):
    __slots__ = (
        # TODO: Move reload_script_lineedit to ToolbarMiscSection
        'reload_script_lineedit', 'switch_output_lineedit',
        'switch_output_modifier_combobox',
        'switch_output_next_lineedit', 'switch_output_previous_lineedit',
        'sync_ouputs_lineedit', 'copy_frame_lineedit'
    )

    parent: ShortCutsSettings

    def __init__(self, parent: ShortCutsSettings) -> None:
        self.parent = parent
        super().__init__()

    def setup_ui(self) -> None:
        # TODO: Move reload_script_lineedit to ToolbarMiscSection
        self.reload_script_lineedit = ShortCutLineEdit()
        if not self.parent.main.reload_enabled:
            self.reload_script_lineedit.setDisabled(True)

        self.switch_output_lineedit = [ShortCutLineEdit(allow_modifiers=False) for _ in range(len(self.switch_output_default))]
        self.switch_output_modifier_combobox = ComboBox[Modifier](model=ModifierModel([Modifier.CTRL, Modifier.SHIFT, Modifier.ALT]))
        # TODO: The combobox is too small from the get go and I dont know why. It was fine iirc until I decided to use `setup_ui_shortcut`
        self.switch_output_modifier_combobox.setMinimumWidth(100)

        self.switch_output_next_lineedit = ShortCutLineEdit()
        self.switch_output_previous_lineedit = ShortCutLineEdit()

        self.sync_ouputs_lineedit = ShortCutLineEdit()

        self.copy_frame_lineedit = ShortCutLineEdit()

        # TODO: Move reload_script_lineedit to ToolbarMiscSection
        self.setup_ui_shortcut("Reload script :", self.reload_script_lineedit, self.reload_script_default)

        for i, (le, num_key) in enumerate(zip(self.switch_output_lineedit, self.switch_output_default)):
            self.setup_ui_shortcut(f"View output node {i} :", le, num_key)

        self.setup_ui_shortcut("View output node from last index modifier :", self.switch_output_modifier_combobox)

        self.setup_ui_shortcut("View next output node :", self.switch_output_next_lineedit, self.switch_output_next_default)
        self.setup_ui_shortcut("View previous output node :", self.switch_output_previous_lineedit, self.switch_output_previous_default)
        self.setup_ui_shortcut("Toggle whether output nodes are synced :", self.sync_ouputs_lineedit, self.sync_ouputs_default)
        self.setup_ui_shortcut("Copy current frame number to clipboard :", self.copy_frame_lineedit, self.copy_frame_default)

    def set_defaults(self) -> None:
        # TODO: Move reload_script_lineedit to ToolbarMiscSection
        self.reload_script_lineedit.setText(self.reload_script_default.toString())

        for le, num_key in zip(self.switch_output_lineedit, self.switch_output_default):
            le.setText(num_key.toString())

        self.switch_output_modifier_combobox.setCurrentIndex(0)

        self.switch_output_next_lineedit.setText(self.switch_output_next_default.toString())
        self.switch_output_previous_lineedit.setText(self.switch_output_previous_default.toString())
        self.sync_ouputs_lineedit.setText(self.sync_ouputs_default.toString())
        self.copy_frame_lineedit.setText(self.copy_frame_default.toString())

    def setup_shortcuts(self) -> None:
        main = self.parent.main
        main_toolbar = main.toolbars.main

        if main.reload_enabled:
            # TODO: Move this to ToolbarMiscSection
            Shortcut(self.reload_script_lineedit.text(), main, main.toolbars.misc.reload_script_button.click)

        for i, le in enumerate(self.switch_output_lineedit):
            Shortcut(le.text(), main, partial(main.switch_output, i))
            Shortcut(
                QKeySequence(QKeyCombination(
                    self.switch_output_modifier_combobox.currentValue().modifier,
                    QKeySequence(le.text())[0].key()).toCombined()
                ),
                main_toolbar,
                partial(main.switch_output, -(i + 1))
            )

        Shortcut(
            self.switch_output_next_lineedit.text(), main_toolbar,
            lambda: main.switch_output(
                main_toolbar.outputs_combobox.currentIndex() + 1
            )
        )
        Shortcut(
            self.switch_output_previous_lineedit.text(), main_toolbar,
            lambda: main.switch_output(
                main_toolbar.outputs_combobox.currentIndex() - 1
            )
        )
        Shortcut(
            self.sync_ouputs_lineedit.text(), main_toolbar,
            main_toolbar.sync_outputs_checkbox.click
        )

        Shortcut(
            self.copy_frame_lineedit.text(), main_toolbar,
            main_toolbar.on_copy_frame_button_clicked
        )

    @property
    def reload_script_default(self) -> QKeySequence:
        return QKeySequence(QKeyCombination(Qt.Modifier.CTRL, Qt.Key.Key_R).toCombined())

    @property
    def switch_output_default(self) -> list[QKeySequence]:
        return [QKeySequence(k) for k in [
            Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3, Qt.Key.Key_4,
            Qt.Key.Key_5, Qt.Key.Key_6, Qt.Key.Key_7, Qt.Key.Key_8,
            Qt.Key.Key_9, Qt.Key.Key_0
        ]]

    @property
    def switch_output_next_default(self) -> QKeySequence:
        return QKeySequence(QKeyCombination(Qt.Modifier.SHIFT, Qt.Key.Key_Tab).toCombined())

    @property
    def switch_output_previous_default(self) -> QKeySequence:
        return QKeySequence(QKeyCombination(Qt.Modifier.CTRL | Qt.Modifier.SHIFT, Qt.Key.Key_Tab).toCombined())
    
    @property
    def sync_ouputs_default(self) -> QKeySequence:
        return QKeySequence(Qt.Key.Key_S)

    @property
    def copy_frame_default(self) -> QKeySequence:
        return QKeySequence(Qt.Key.Key_V)

    def __getstate__(self) -> dict[str, Any]:
        return super().__getstate__() | {
            # TODO: Move reload_script_lineedit to ToolbarMiscSection
            'reload_script': self.reload_script_lineedit.text(),
            'switch_output_modifier': self.switch_output_modifier_combobox.currentValue(),
            'switch_output_next': self.switch_output_next_lineedit.text(),
            'switch_output_previous': self.switch_output_previous_lineedit.text(),
            'sync_ouputs': self.sync_ouputs_lineedit.text(),
            'copy_frame': self.copy_frame_lineedit.text(),
        } | {
            f'switch_output_{i}': so.text()
            for i, so in enumerate(self.switch_output_lineedit)
        }

    def __setstate__(self, state: dict[str, Any]) -> None:
        # TODO: Move reload_script_lineedit to ToolbarMiscSection
        try_load(state, 'reload_script', str, self.reload_script_lineedit.setText)
        try_load(state, 'switch_output_modifier', Modifier, self.switch_output_modifier_combobox.setCurrentValue)
        try_load(state, 'switch_output_next', str, self.switch_output_next_lineedit.setText)
        try_load(state, 'switch_output_previous', str, self.switch_output_previous_lineedit.setText)
        try_load(state, 'sync_ouputs', str, self.sync_ouputs_lineedit.setText)
        try_load(state, 'copy_frame', str, self.copy_frame_lineedit.setText)
        
        for i, so in enumerate(self.switch_output_lineedit):
            try_load(state, f'switch_output_{i}', str, so.setText)
