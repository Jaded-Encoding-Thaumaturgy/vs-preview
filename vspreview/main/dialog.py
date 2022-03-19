from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCloseEvent
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QWidget, QHBoxLayout, QPushButton, QTabWidget


from ..utils import add_shortcut, set_qobject_names
from ..core import AbstractMainWindow, AbstractAppSettings


class ScriptErrorDialog(QDialog):
    __slots__ = ('main', 'label', 'reload_button', 'exit_button')

    def __init__(self, main_window: AbstractMainWindow) -> None:
        super().__init__(main_window, Qt.Dialog)
        self.main = main_window

        self.setWindowTitle('Script Loading Error')
        self.setModal(True)

        self.setup_ui()

        self.reload_button.clicked.connect(self.on_reload_clicked)
        self.exit_button.clicked.connect(self.on_exit_clicked)

        add_shortcut(Qt.CTRL + Qt.Key_R, self.reload_button.click, self)

        set_qobject_names(self)

    def setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setObjectName('ScriptErrorDialog.setup_ui.main_layout')

        self.label = QLabel()
        main_layout.addWidget(self.label)

        buttons_widget = QWidget(self)
        buttons_widget.setObjectName('ScriptErrorDialog.setup_ui.buttons_widget')
        buttons_layout = QHBoxLayout(buttons_widget)
        buttons_layout.setObjectName('ScriptErrorDialog.setup_uibuttons_layout')

        self.reload_button = QPushButton(self)
        self.reload_button.setText('Reload')
        buttons_layout.addWidget(self.reload_button)

        self.exit_button = QPushButton(self)
        self.exit_button.setText('Exit')
        buttons_layout.addWidget(self.exit_button)

        main_layout.addWidget(buttons_widget)

    def on_reload_clicked(self, clicked: bool | None = None) -> None:
        self.hide()
        self.main.reload_script()

    def on_exit_clicked(self, clicked: bool | None = None) -> None:
        self.hide()
        self.main.save_on_exit = False
        self.main.app.exit()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.on_exit_clicked()


class SettingsDialog(AbstractAppSettings):
    __slots__ = (
        'main', 'tab_widget',
    )

    def __init__(self, main_window: AbstractMainWindow) -> None:
        super().__init__(main_window)

        self.main = main_window
        self.setWindowTitle('Settings')

        self.setup_ui()

        set_qobject_names(self)

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setObjectName('SettingsDialog.setup_ui.layout')

        self.tab_widget = QTabWidget(self)
        layout.addWidget(self.tab_widget)

    def addTab(self, widget: QWidget, label: str) -> int:
        return self.tab_widget.addTab(widget, label)
