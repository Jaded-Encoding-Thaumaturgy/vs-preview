from __future__ import annotations

from colorsys import rgb_to_hls, rgb_to_hsv
from math import ceil, floor, log
from typing import TYPE_CHECKING, Generator, cast
from weakref import WeakKeyDictionary

import vapoursynth as vs
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QFont, QMouseEvent
from PyQt6.QtWidgets import QFrame, QGraphicsView, QLabel

from ...core import AbstractToolbar, Frame, PushButton, VideoOutput
from .colorview import ColorView
from .settings import PipetteSettings

if TYPE_CHECKING:
    from ...main import MainWindow


__all__ = [
    'PipetteToolbar'
]


class PipetteToolbar(AbstractToolbar):
    labels = [
        'position',
        'rgb_label', 'rgb_hex', 'rgb_dec', 'rgb_norm',
        'src_label', 'src_hex', 'src_dec', 'src_norm'
    ]

    __slots__ = (
        'color_view', 'outputs', 'tracking',
        'src_dec_fmt', 'src_hex_fmt', *labels,
        'copy_position_button'
    )

    settings: PipetteSettings

    def __init__(self, main: MainWindow) -> None:
        import ctypes

        super().__init__(main, PipetteSettings(self))

        self.setup_ui()
        self.src_max_val: float = 2**8 - 1
        self.pos_fmt = self.src_hex_fmt = self.src_dec_fmt = self.src_norm_fmt = ''
        self.outputs = WeakKeyDictionary[VideoOutput, vs.VideoNode]()
        self.tracking = False
        self._curr_frame_cache = WeakKeyDictionary[VideoOutput, tuple[int, vs.VideoFrame]]()
        self._curr_alphaframe_cache = WeakKeyDictionary[VideoOutput, tuple[int, vs.VideoFrame]]()
        self._mouse_is_subscribed = False

        self.last_pos: tuple[VideoOutput, QPoint] | None = None

        self.set_qobject_names()

        self.data_types = {
            vs.INTEGER: {
                1: ctypes.c_uint8,
                2: ctypes.c_uint16,
                4: ctypes.c_uint32,
            },
            vs.FLOAT: {
                2: ctypes.c_char,
                4: ctypes.c_float,
            }
        }

    def setup_ui(self) -> None:
        super().setup_ui()

        self.color_view = ColorView(self)
        self.color_view.setFixedSize(self.height() // 2, self.height() // 2)

        font = QFont('Consolas', 9)
        font.setStyleHint(QFont.StyleHint.Monospace)

        self.position = QLabel(self)

        self.rgb_label = QLabel('Rendered (RGB):', self)

        self.rgb_hex = QLabel(self)
        self.rgb_dec = QLabel(self)
        self.rgb_norm = QLabel(self)

        self.src_label = QLabel(self)

        self.src_hex = QLabel(self)
        self.src_dec = QLabel(self)
        self.src_norm = QLabel(self)

        self.rgb_hls = QLabel(self)
        self.rgb_hsv = QLabel(self)

        for label in [
            self.position,
            self.rgb_hex, self.rgb_dec, self.rgb_norm,
            self.src_hex, self.src_dec, self.src_norm
        ]:
            label.setFont(font)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.copy_position_button = PushButton('⎘', self, clicked=self.on_copy_position_clicked)

        self.hlayout.addWidgets([
            QFrame(),
            self.color_view, self.position, self.copy_position_button,
            self.get_separator(),
            self.rgb_label, self.rgb_hex, self.rgb_dec, self.rgb_norm,
            self.get_separator(),
            self.src_label, self.src_hex, self.src_dec, self.src_norm,
            self.get_separator(),
            QLabel('HLS:'), self.rgb_hls, QLabel('HSV:'), self.rgb_hsv,
        ])

        self.hlayout.addStretch()

    def on_current_frame_changed(self, frame: Frame) -> None:
        if self.last_pos and self.last_pos[0] is self.main.current_output:
            self.update_labels(self.last_pos[1])

    def subscribe_on_mouse_events(self) -> None:
        if not self._mouse_is_subscribed:
            self.main.graphics_view.mouseMoved.connect(self.mouse_moved)
            self.main.graphics_view.mousePressed.connect(self.mouse_pressed)
            self.main.graphics_view.mouseReleased.connect(self.mouse_released)
        self._mouse_is_subscribed = True

    def unsubscribe_from_mouse_events(self) -> None:
        if self._mouse_is_subscribed:
            self.main.graphics_view.mouseMoved.disconnect(self.mouse_moved)
            self.main.graphics_view.mousePressed.disconnect(self.mouse_pressed)
            self.main.graphics_view.mouseReleased.disconnect(self.mouse_released)
        self._mouse_is_subscribed = False

    def mouse_moved(self, event: QMouseEvent) -> None:
        if self.tracking and not event.buttons():
            self.update_labels(event.pos())

    def mouse_pressed(self, event: QMouseEvent) -> None:
        if event.buttons() == Qt.MouseButton.RightButton:
            self.tracking = not self.tracking

        if self.tracking:
            self.update_labels(event.pos())

    def mouse_released(self, event: QMouseEvent) -> None:
        pass

    @property
    def current_source_frame(self) -> vs.VideoFrame:
        if self.main.current_output in self._curr_frame_cache:
            cache = self._curr_frame_cache[self.main.current_output]
        else:
            cache = None

        last_showed_frame = min(
            int(self.main.current_output.last_showed_frame), int(self.main.current_output.total_frames) - 1
        )

        if cache is None or cache[0] != last_showed_frame:
            cache = self._curr_frame_cache[self.main.current_output] = (
                last_showed_frame, self.outputs[self.main.current_output].get_frame(last_showed_frame)
            )

        return cache[1]

    @property
    def current_source_alpha_frame(self) -> vs.VideoFrame:
        assert self.main.current_output.source.alpha

        if self.main.current_output in self._curr_alphaframe_cache:
            cache = self._curr_alphaframe_cache[self.main.current_output]
        else:
            cache = None

        last_showed_frame = min(
            int(self.main.current_output.last_showed_frame), int(self.main.current_output.total_frames) - 1
        )

        if cache is None or cache[0] != last_showed_frame:
            cache = self._curr_alphaframe_cache[self.main.current_output] = (
                last_showed_frame, self.main.current_output.source.alpha.get_frame(last_showed_frame)
            )

        return cache[1]

    def update_labels(self, local_pos: QPoint) -> None:
        self.last_pos = (self.main.current_output, local_pos)

        pos_f = self.main.graphics_view.mapToScene(local_pos)

        if not self.main.current_scene.contains(pos_f):
            return

        pos = QPoint(floor(pos_f.x()), floor(pos_f.y()))
        color = self.main.current_scene.pixmap().toImage().pixelColor(pos)
        components = color.red(), color.green(), color.blue()
        components_float = tuple[float, ...](x / 255 for x in components)

        self.color_view.color = color
        self.position.setText('{:4d},{:4d}'.format(pos.x(), pos.y()))

        self.rgb_hex.setText('{:2X},{:2X},{:2X}'.format(*components))
        self.rgb_dec.setText('{:3d},{:3d},{:3d}'.format(*components))
        self.rgb_norm.setText('{:0.5f},{:0.5f},{:0.5f}'.format(*components_float))
        self.rgb_hls.setText('{}%,{}%,{}%'.format(*(int(x * 255) for x in rgb_to_hls(*components_float))))
        self.rgb_hsv.setText('{}%,{}%,{}%'.format(*(int(x * 255) for x in rgb_to_hsv(*components_float))))

        if not self.src_label.isVisible():
            return

        fmt = self.current_source_frame.format

        src_vals = list(self.extract_value(self.current_source_frame, pos))
        if self.main.current_output.source.alpha:
            src_vals.append(next(self.extract_value(self.current_source_alpha_frame, pos)))

        self.src_dec.setText(self.src_dec_fmt.format(*src_vals))
        if fmt.sample_type == vs.INTEGER:
            self.src_hex.setText(self.src_hex_fmt.format(*src_vals))
            self.src_norm.setText(self.src_norm_fmt.format(*[
                src_val / self.src_max_val for src_val in src_vals
            ]))
        elif fmt.sample_type == vs.FLOAT:
            self.src_norm.setText(self.src_norm_fmt.format(*[
                max(0.0, min(val, 1.0)) if i in {0, 3} else max(-.5, min(val, .5)) + .5
                for i, val in enumerate(src_vals)
            ]))

    def on_current_output_changed(self, index: int, prev_index: int) -> None:
        super().on_current_output_changed(index, prev_index)

        if self.main.current_output not in self.outputs:
            self.outputs[self.main.current_output] = self.prepare_vs_output(self.main.current_output.source.clip)

        assert (src_fmt := self.outputs[self.main.current_output].format)

        has_alpha = bool(self.main.current_output.source.alpha)

        self.src_label.setText(f"Raw ({src_fmt.color_family.name}{' + Alpha' if has_alpha else ''}):")
        self.src_hex.setVisible(src_fmt.sample_type == vs.INTEGER)

        if src_fmt.sample_type == vs.INTEGER:
            self.src_max_val = 2**src_fmt.bits_per_sample - 1
        elif src_fmt.sample_type == vs.FLOAT:
            self.src_max_val = 1.0

        src_num_planes = src_fmt.num_planes + int(has_alpha)

        self.src_hex_fmt = ('{{:{w}X}},' * src_num_planes)[:-1].format(w=ceil(log(self.src_max_val, 16)))
        if src_fmt.sample_type == vs.INTEGER:
            self.src_dec_fmt = ('{{:{w}d}},' * src_num_planes)[:-1].format(w=ceil(log(self.src_max_val, 10)))
        elif src_fmt.sample_type == vs.FLOAT:
            self.src_dec_fmt = ('{: 0.5f},' * src_num_planes)[:-1]
        self.src_norm_fmt = ('{:0.5f},' * src_num_planes)[:-1]

        self.update_labels(self.main.graphics_view.mapFromGlobal(self.main.cursor().pos()))

    def on_copy_position_clicked(self, checked: bool | None = None) -> None:
        self.main.clipboard.setText(self.position.text().strip())
        self.main.show_message('Coordinates successfully copied to clipboard')

    def on_toggle(self, new_state: bool) -> None:
        super().on_toggle(new_state)
        self.tracking = new_state
        self.main.graphics_view.setMouseTracking(new_state)

        if new_state:
            self.subscribe_on_mouse_events()
            self.main.graphics_view.setDragMode(QGraphicsView.DragMode.NoDrag)
        else:
            self.unsubscribe_from_mouse_events()
            self.main.graphics_view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

    @staticmethod
    def prepare_vs_output(vs_output: vs.VideoNode) -> vs.VideoNode:
        assert (fmt := vs_output.format)

        if fmt.subsampling_w == fmt.subsampling_h == 0:
            return vs_output

        return vs.core.resize.Bicubic(
            vs_output, format=vs.core.query_video_format(
                fmt.color_family, fmt.sample_type, fmt.bits_per_sample, 0, 0
            ).id, dither_type='none'
        )

    def extract_value(self, vs_frame: vs.VideoFrame, pos: QPoint) -> Generator[float, None, None]:
        from ctypes import POINTER
        from ctypes import cast as ccast
        from struct import unpack

        fmt = vs_frame.format

        for plane in range(fmt.num_planes):
            stride = vs_frame.get_stride(plane)
            pointer = ccast(vs_frame.get_read_ptr(plane), POINTER(
                self.data_types[fmt.sample_type][fmt.bytes_per_sample] * (stride * vs_frame.height)  # type: ignore
            ))

            if fmt.sample_type == vs.FLOAT and fmt.bytes_per_sample == 2:
                offset = pos.y() * stride + pos.x() * fmt.bytes_per_sample
                yield cast(float, unpack('e', cast(bytearray, pointer.contents[
                    slice(offset, offset + fmt.bytes_per_sample)
                ]))[0])
            else:
                yield cast(int, pointer.contents[pos.y() * (stride // fmt.bytes_per_sample) + pos.x()])
