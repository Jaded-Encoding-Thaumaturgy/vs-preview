from __future__ import annotations


from PyQt5.QtWidgets import QWidget, QStatusBar, QLabel


class StatusBar(QStatusBar):
    total_frames_label: QLabel
    duration_label: QLabel
    resolution_label: QLabel
    pixel_format_label: QLabel
    fps_label: QLabel
    frame_props_label: QLabel
    label: QLabel

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)

        self.permament_start_index = 0

    def addPermanentWidget(self, widget: QWidget, stretch: int = 0) -> None:
        self.insertPermanentWidget(self.permament_start_index, widget, stretch)

    def addWidget(self, widget: QWidget, stretch: int = 0) -> None:
        self.permament_start_index += 1
        super().addWidget(widget, stretch)

    def insertWidget(self, index: int, widget: QWidget, stretch: int = 0) -> int:
        self.permament_start_index += 1
        return super().insertWidget(index, widget, stretch)
