from __future__ import annotations
import logging

from PyQt5 import Qt


class StatusBar(Qt.QStatusBar):
    def __init__(self, parent: Qt.QWidget) -> None:
        super().__init__(parent)

        self.permament_start_index = 0

    def addPermanentWidget(self, widget: Qt.QWidget, stretch: int = 0) -> None:
        self.insertPermanentWidget(self.permament_start_index, widget, stretch)

    def addWidget(self, widget: Qt.QWidget, stretch: int = 0) -> None:
        self.permament_start_index += 1
        super().addWidget(widget, stretch)

    def insertWidget(self, index: int, widget: Qt.QWidget, stretch: int = 0) -> int:
        self.permament_start_index += 1
        return super().insertWidget(index, widget, stretch)
