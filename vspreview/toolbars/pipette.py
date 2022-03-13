import ctypes
from weakref import WeakKeyDictionary
from typing import cast, TypeVar, Union

from PyQt5 import Qt
import vapoursynth as vs

from vspreview.core import AbstractMainWindow, AbstractToolbar, Output
from vspreview.utils import set_qobject_names
from vspreview.widgets import ColorView


Number = TypeVar('Number', int, float)


class PipetteToolbar(AbstractToolbar):
    __slots__ = (
        'color_view', 'outputs', 'position', 'pos_fmt', 'tracking',
        'rgb_dec', 'rgb_hex', 'rgb_label',
        'src_dec', 'src_dec_fmt', 'src_hex', 'src_hex_fmt', 'src_label',
    )

    data_types = {
        vs.INTEGER: {
            1: ctypes.c_uint8,
            2: ctypes.c_uint16,
            # 4: ctypes.c_char * 4,
        },
        vs.FLOAT: {
            # 2: ctypes.c_char * 2,
            4: ctypes.c_float,
        }
    }

    def __init__(self, main: AbstractMainWindow) -> None:
        super().__init__(main, 'Pipette')

        self.setup_ui()

        self.pos_fmt = '{},{}'
        self.src_hex_fmt = '{:2X}'
        self.src_max_val: Union[int, float] = 2**8 - 1
        self.src_dec_fmt = '{:3d}'
        self.src_norm_fmt = '{:0.5f}'
        self.outputs = WeakKeyDictionary[Output, vs.VideoNode]()
        self.tracking = False

        main.reload_signal.connect(self.clear_outputs)

        set_qobject_names(self)

    def clear_outputs(self) -> None:
        self.outputs.clear()

    def setup_ui(self) -> None:
        layout = Qt.QHBoxLayout(self)
        layout.setObjectName('PipetteToolbar.setup_ui.layout')
        layout.setContentsMargins(0, 0, 0, 0)

        self.color_view = ColorView(self)
        self.color_view.setFixedSize(self.height() // 2, self.height() // 2)
        layout.addWidget(self.color_view)

        font = Qt.QFont('Consolas', 9)
        font.setStyleHint(Qt.QFont.Monospace)

        self.position = Qt.QLabel(self)
        self.position.setFont(font)
        self.position.setTextInteractionFlags(Qt.Qt.TextSelectableByMouse)
        layout.addWidget(self.position)

        self.rgb_label = Qt.QLabel(self)
        self.rgb_label.setText('Rendered (RGB):')
        layout.addWidget(self.rgb_label)

        self.rgb_hex = Qt.QLabel(self)
        self.rgb_hex.setFont(font)
        self.rgb_hex.setTextInteractionFlags(Qt.Qt.TextSelectableByMouse)
        layout.addWidget(self.rgb_hex)

        self.rgb_dec = Qt.QLabel(self)
        self.rgb_dec.setFont(font)
        self.rgb_dec.setTextInteractionFlags(Qt.Qt.TextSelectableByMouse)
        layout.addWidget(self.rgb_dec)

        self.rgb_norm = Qt.QLabel(self)
        self.rgb_norm.setFont(font)
        self.rgb_norm.setTextInteractionFlags(Qt.Qt.TextSelectableByMouse)
        layout.addWidget(self.rgb_norm)

        self.src_label = Qt.QLabel(self)
        layout.addWidget(self.src_label)

        self.src_hex = Qt.QLabel(self)
        self.src_hex.setFont(font)
        self.src_hex.setTextInteractionFlags(Qt.Qt.TextSelectableByMouse)
        layout.addWidget(self.src_hex)

        self.src_dec = Qt.QLabel(self)
        self.src_dec.setFont(font)
        self.src_dec.setTextInteractionFlags(Qt.Qt.TextSelectableByMouse)
        layout.addWidget(self.src_dec)

        self.src_norm = Qt.QLabel(self)
        self.src_norm.setFont(font)
        self.src_norm.setTextInteractionFlags(Qt.Qt.TextSelectableByMouse)
        layout.addWidget(self.src_norm)

        layout.addStretch()

    def subscribe_on_mouse_events(self) -> None:
        self.main.graphics_view.mouseMoved   .connect(self.mouse_moved)
        self.main.graphics_view.mousePressed .connect(self.mouse_pressed)
        self.main.graphics_view.mouseReleased.connect(self.mouse_released)

    def unsubscribe_from_mouse_events(self) -> None:
        self.main.graphics_view.mouseMoved   .disconnect(self.mouse_moved)
        self.main.graphics_view.mousePressed .disconnect(self.mouse_pressed)
        self.main.graphics_view.mouseReleased.disconnect(self.mouse_released)

    def on_script_unloaded(self) -> None:
        self.outputs.clear()

    def mouse_moved(self, event: Qt.QMouseEvent) -> None:
        if self.tracking and not event.buttons():
            self.update_labels(event.pos())

    def mouse_pressed(self, event: Qt.QMouseEvent) -> None:
        if event.buttons() == Qt.Qt.RightButton:
            self.tracking = False

    def mouse_released(self, event: Qt.QMouseEvent) -> None:
        if event.buttons() == Qt.Qt.RightButton:
            self.tracking = True
        self.update_labels(event.pos())

    def update_labels(self, local_pos: Qt.QPoint) -> None:
        from math import floor
        from struct import unpack

        pos_f = self.main.graphics_view.mapToScene(local_pos)
        pos = Qt.QPoint(floor(pos_f.x()), floor(pos_f.y()))
        if not self.main.current_output.graphics_scene_item.contains(pos_f):
            return
        color = self.main.current_output.graphics_scene_item.image() \
                    .pixelColor(pos)
        self.color_view.color = color

        self.position.setText(self.pos_fmt.format(pos.x(), pos.y()))

        self.rgb_hex.setText('{:2X},{:2X},{:2X}'.format(
            color.red(), color.green(), color.blue()))
        self.rgb_dec.setText('{:3d},{:3d},{:3d}'.format(
            color.red(), color.green(), color.blue()))
        self.rgb_norm.setText('{:0.5f},{:0.5f},{:0.5f}'.format(
            color.red() / 255, color.green() / 255, color.blue() / 255))

        if not self.src_label.isVisible():
            return

        def extract_value(vs_frame: vs.VideoFrame, plane: int,
                          pos: Qt.QPoint) -> Union[int, float]:
            fmt = vs_frame.format
            stride = vs_frame.get_stride(plane)
            if fmt.sample_type == vs.FLOAT and fmt.bytes_per_sample == 2:
                ptr = ctypes.cast(vs_frame.get_read_ptr(plane), ctypes.POINTER(
                    ctypes.c_char * (stride * vs_frame.height)))
                offset = pos.y() * stride + pos.x() * 2
                val = unpack('e', ptr.contents[offset:(offset + 2)])[0]
                return cast(float, val)
            else:
                ptr = ctypes.cast(vs_frame.get_read_ptr(plane), ctypes.POINTER(
                    self.data_types[fmt.sample_type][fmt.bytes_per_sample] * (  # type:ignore
                        stride * vs_frame.height)))
                logical_stride = stride // fmt.bytes_per_sample
                idx = pos.y() * logical_stride + pos.x()
                return ptr.contents[idx]

        vs_frame = self.outputs[self.main.current_output].get_frame(
            int(self.main.current_frame))
        fmt = vs_frame.format

        src_vals = [extract_value(vs_frame, i, pos) for i in range(fmt.num_planes)]
        if self.main.current_output.source.alpha:
            vs_alpha = self.main.current_output.source.alpha.get_frame(int(self.main.current_frame))
            src_vals.append(extract_value(vs_alpha, 0, pos))

        self.src_dec.setText(self.src_dec_fmt.format(*src_vals))
        if fmt.sample_type == vs.INTEGER:
            self.src_hex.setText(self.src_hex_fmt.format(*src_vals))
            self.src_norm.setText(self.src_norm_fmt.format(
                *[src_val / self.src_max_val for src_val in src_vals]))
        elif fmt.sample_type == vs.FLOAT:
            self.src_norm.setText(self.src_norm_fmt.format(*[
                self.clip(val, 0.0, 1.0) if i in (0, 3) else
                self.clip(val, -0.5, 0.5) + 0.5
                for i, val in enumerate(src_vals)
            ]))

    def on_current_output_changed(self, index: int, prev_index: int) -> None:
        from math import ceil, log

        super().on_current_output_changed(index, prev_index)

        fmt = self.main.current_output.source.clip.format
        assert fmt

        src_label_text = ''
        if fmt.color_family == vs.RGB:
            src_label_text = 'Raw (RGB{}):'
        elif fmt.color_family == vs.YUV:
            src_label_text = 'Raw (YUV{}):'
        elif fmt.color_family == vs.GRAY:
            src_label_text = 'Raw (Gray{}):'

        self.src_label.setText(src_label_text.format(' + Alpha'if self.main.current_output.source.alpha else ''))

        self.pos_fmt = '{:4d},{:4d}'

        if self.main.current_output not in self.outputs:
            self.outputs[self.main.current_output] = self.prepare_vs_output(
                self.main.current_output.source.clip
            )
        src_fmt = self.outputs[self.main.current_output].format

        if src_fmt.sample_type == vs.INTEGER:
            self.src_max_val = 2**src_fmt.bits_per_sample - 1
        elif src_fmt.sample_type == vs.FLOAT:
            self.src_hex.setVisible(False)
            self.src_max_val = 1.0

        src_num_planes = src_fmt.num_planes + int(bool(self.main.current_output.source.alpha))
        self.src_hex_fmt = ','.join(('{{:{w}X}}',) * src_num_planes) \
                           .format(w=ceil(log(self.src_max_val, 16)))
        if src_fmt.sample_type == vs.INTEGER:
            self.src_dec_fmt = ','.join(('{{:{w}d}}',) * src_num_planes) \
                               .format(w=ceil(log(self.src_max_val, 10)))
        elif src_fmt.sample_type == vs.FLOAT:
            self.src_dec_fmt = ','.join(('{: 0.5f}',) * src_num_planes)
        self.src_norm_fmt = ','.join(('{:0.5f}',) * src_num_planes)

        self.update_labels(self.main.graphics_view.mapFromGlobal(
            self.main.cursor().pos()))

    def on_toggle(self, new_state: bool) -> None:
        super().on_toggle(new_state)
        self.main.graphics_view.setMouseTracking(new_state)
        if new_state is True:
            self.subscribe_on_mouse_events()
            self.main.graphics_view.setDragMode(Qt.QGraphicsView.NoDrag)
        else:
            self.unsubscribe_from_mouse_events()
            self.main.graphics_view.setDragMode(
                Qt.QGraphicsView.ScrollHandDrag)
        self.tracking = new_state

    @staticmethod
    def prepare_vs_output(vs_output: vs.VideoNode) -> vs.VideoNode:
        assert vs_output.format

        def non_subsampled_format(fmt: vs.VideoFormat) -> vs.VideoFormat:
            return vs.core.query_video_format(fmt.color_family, fmt.sample_type, fmt.bits_per_sample, 0, 0)

        return vs.core.resize.Bicubic(vs_output, format=non_subsampled_format(vs_output.format).id)

    @staticmethod
    def clip(value: Number, lower_bound: Number, upper_bound: Number) -> Number:
        return max(lower_bound, min(value, upper_bound))
