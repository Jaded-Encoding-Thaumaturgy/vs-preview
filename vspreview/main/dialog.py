from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import QLabel, QTabWidget, QWidget

from ..core import ExtendedDialog, HBoxLayout, PushButton, VBoxLayout

if TYPE_CHECKING:
    from .window import MainWindow


__all__ = [
    'ScriptErrorDialog',
    'SettingsDialog'
]


class ScriptErrorDialog(ExtendedDialog):
    __slots__ = ('main', 'label', 'reload_button', 'exit_button')

    def __init__(self, main_window: MainWindow) -> None:
        super().__init__(main_window, Qt.WindowType.Dialog)
        self.main = main_window

        self.setWindowTitle('There was an error')
        self.setModal(True)

        self.setup_ui()

        self.set_qobject_names()

    def setup_ui(self) -> None:
        self.vlayout = VBoxLayout(self)

        self.label = QLabel()
        self.reload_button = PushButton(
            'Reload', self, clicked=self.on_reload_clicked, hidden=not self.main.reload_enabled
        )
        self.exit_button = PushButton('Exit', self, clicked=self.on_exit_clicked)

        self.vlayout.addWidget(self.label)
        self.vlayout.addLayout(HBoxLayout(
            [self.reload_button, self.exit_button] if self.main.reload_enabled else [self.exit_button]
        ))

    def on_reload_clicked(self, clicked: bool | None = None) -> None:
        self.hide()
        self.main.reload_script()

    def on_exit_clicked(self, clicked: bool | None = None) -> None:
        self.hide()
        self.script_exec_failed = True

        if not self.main.no_exit:
            sys.exit(1)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.on_exit_clicked()


class SettingsDialog(ExtendedDialog):
    __slots__ = ('main', 'tab_widget',)

    def __init__(self, main_window: MainWindow) -> None:
        super().__init__(main_window)

        self.main = main_window
        self.setWindowTitle('Settings')

        self.setup_ui()

        self.set_qobject_names()

    def setup_ui(self) -> None:
        self.tab_widget = QTabWidget(self)
        self.vlayout = VBoxLayout(self, [self.tab_widget])

    def addTab(self, widget: QWidget, label: str) -> int:
        return self.tab_widget.addTab(widget, label)
