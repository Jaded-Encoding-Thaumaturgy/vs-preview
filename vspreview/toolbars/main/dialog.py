from __future__ import annotations

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent
from PyQt6.QtWidgets import QLabel
from vapoursynth import FrameProps
from vstools import ChromaLocation, ColorRange, FieldBased, Matrix, Primaries, PropEnum, Transfer

from ...core import AbstractMainWindow, ExtendedWidget, HBoxLayout, PushButton, Stretch, VBoxLayout

_frame_props_excluded_keys = {
    # vs internals
    '_AbsoluteTime', '_DurationNum', '_DurationDen', '_PictType', '_Alpha',
    # Handled separately
    '_SARNum', '_SARDen',
    # source filters
    '_FrameNumber',
    # vstools set_output
    'Name'
}


def _create_enum_props_lut(enum: PropEnum, pretty_name: str) -> tuple[str, dict[str, dict[int, str]]]:
    return enum.prop_key, {
        pretty_name: {
            idx: enum.from_param(idx).pretty_string if enum.is_valid(idx) else 'Invalid'
            for idx in range(min(enum) - 1, max(enum) + 1)
        }
    }


_frame_props_lut = {
    '_Combed': {
        'Is Combed': [
            'No',
            'Yes'
        ]
    },
    '_Field': {
        'Frame Field Type': [
            'Bottom Field',
            'Top Field'
        ]
    },
    '_SceneChangeNext': {
        'Scene Cut': [
            'Current Scene',
            'End of Scene'
        ]
    },
    '_SceneChangePrev': {
        'Scene Change': [
            'Current Scene',
            'Start of Scene'
        ]
    }
} | dict([
    _create_enum_props_lut(enum, name)
    for enum, name in [
        (FieldBased, 'Field Type'),
        (Matrix, 'Matrix'),
        (Transfer, 'Transfer'),
        (Primaries, 'Primaries'),
        (ChromaLocation, 'Chroma Location'),
        (ColorRange, 'Color Range')
    ]
])


class FramePropsDialog(ExtendedWidget):
    __slots__ = (
        'main_window', 'clicked', 'old_pos', 'header', 'framePropsVLayout'
    )

    def __init__(self, main_window: AbstractMainWindow) -> None:
        super().__init__(main_window)

        self.main_window = main_window
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.clicked = False
        self.old_pos = QPointF(0.0, 0.0)
        self.setGeometry(100, 100, 300, 450)
        self.setStyleSheet('.QLabel { font-size: 12px; background-color: none }')

        self.setup_ui()

        self.set_qobject_names()
        self.hide()

    def setup_ui(self) -> None:
        self.framePropsVLayout = VBoxLayout()
        self.header = QLabel()
        font = self.header.font()
        font.setPixelSize(15)
        self.header.setFont(font)
        VBoxLayout(self, [
            HBoxLayout([
                Stretch(), self.header, Stretch(), PushButton(' X ', clicked=self.hide)
            ]),
            self.framePropsVLayout,
            Stretch()
        ])

    def showDialog(self, props: FrameProps | None) -> None:
        if props is not None:
            self.update_frame_props(props)

        super().show()

    def update_frame_props(self, props: FrameProps) -> None:
        node_idx = self.main_window.toolbars.main.outputs_combobox.currentIndex()
        self.header.setText(
            f'Frame Props - Node {node_idx} / Frame {self.main_window.current_output.last_showed_frame}'
        )
        self.framePropsVLayout.clear()

        def _add_prop_row(key: str, value: str) -> None:
            self.framePropsVLayout.addLayout(
                HBoxLayout([QLabel(key), QLabel(value)], spacing=5)
            )

        for key in sorted(props.keys()):
            if key in _frame_props_excluded_keys:
                continue

            if key in _frame_props_lut:
                title = list(_frame_props_lut[key].keys())[0]
                value_str = _frame_props_lut[key][title][props[key]]
            else:
                title = key[1:] if key.startswith('_') else key
                value_str = str(props[key])

            if value_str is not None:
                _add_prop_row(title, value_str)

        if '_SARNum' in props and '_SARDen' in props:
            _add_prop_row('Pixel aspect ratio', f"{props['_SARNum']}/{props['_SARDen']}")

    def paintEvent(self, event: QPaintEvent) -> None:
        QPainter(self).fillRect(self.rect(), QColor(45, 55, 65, 168))
        self.main_window.timeline.full_repaint()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.clicked = True

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self.clicked = False

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.clicked:
            new_x = int(self.pos().x() - (self.old_pos.x() - event.globalPosition().x()))
            new_y = int(self.pos().y() - (self.old_pos.y() - event.globalPosition().y()))

            if 0 < new_x < self.main_window.width() and 0 < new_y < self.main_window.height():
                self.move(new_x, new_y)
            else:
                return

        self.old_pos = event.globalPosition()

        return super().mouseMoveEvent(event)
