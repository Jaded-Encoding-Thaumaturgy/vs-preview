from __future__ import annotations

from typing import Any, Sequence, cast

from PyQt5.QtCore import QRect, Qt
from PyQt5.QtGui import QBrush, QColor, QPainter, QPaintEvent, QPen
from PyQt5.QtWidgets import QLabel, QStatusBar, QWidget

from ..abstracts import PushButton


class StatusBar(QStatusBar):
    label_names = (
        'total_frames_label', 'duration_label', 'resolution_label',
        'pixel_format_label', 'fps_label', 'frame_props_label', 'label'
    )

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

    def addWidgets(self, widgets: Sequence[QWidget], stretch: int = 0) -> None:
        for widget in widgets:
            self.addWidget(widget, stretch)

    def insertWidget(self, index: int, widget: QWidget, stretch: int = 0) -> int:
        self.permament_start_index += 1
        return super().insertWidget(index, widget, stretch)


class Switch(PushButton):
    def __init__(
        self, radius: int = 10, width: int = 32, border: int = 1,
        state_texts: tuple[str, str, int] = ('OFF', 'ON', 1),
        state_colors: tuple[QColor, QColor] = (QColor(69, 83, 100), QColor(96, 121, 139)),
        border_color: QColor = QColor(69, 83, 100), text_color: QColor = QColor(224, 225, 226),
        background_color: QColor = QColor(25, 35, 45), **kwargs: Any
    ):
        super().__init__(**kwargs)

        self.radius = radius
        self.sw_width = width
        self.border = border
        self.state_texts = state_texts
        self.state_colors = state_colors
        self.border_color = border_color
        self.text_color = text_color
        self.background_color = background_color

        self.setCheckable(True)
        self.setMinimumWidth((width + border) * 2)
        self.setMinimumHeight((radius + border) * 2)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(self.rect().center())
        painter.setBrush(self.background_color)

        pen = QPen(self.border_color)
        pen.setWidth(self.border)
        painter.setPen(pen)

        painter.drawRoundedRect(
            QRect(-self.sw_width, -self.radius, self.sw_width * 2, self.radius * 2), self.radius, self.radius
        )
        painter.setBrush(QBrush(self.state_colors[int(self.isChecked())]))

        switch_rect = QRect(
            -self.radius, -self.radius + self.border, self.sw_width + self.radius, self.radius * 2 - self.border * 2
        )

        if not self.isChecked():
            switch_rect.moveLeft(-self.sw_width)

        painter.setPen(pen)
        painter.drawRoundedRect(switch_rect, self.radius, self.radius)

        textpen = QPen(self.text_color)
        textpen.setWidth(self.state_texts[2])

        painter.setPen(textpen)
        painter.drawText(switch_rect, Qt.AlignCenter, cast(str, self.state_texts[int(self.isChecked())]))
