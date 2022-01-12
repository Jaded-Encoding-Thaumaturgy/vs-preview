from __future__ import annotations

from vspreview.utils import strfdelta
from   collections import deque
from   concurrent.futures import Future
import logging
from   time        import perf_counter
from   typing      import Deque, Optional, Union

from PyQt5 import Qt

from vspreview.core import (
    AbstractMainWindow, AbstractToolbar, Frame, FrameInterval, Time,
    TimeInterval,
)
from vspreview.utils import (
    debug, get_usable_cpus_count, qt_silent_call, set_qobject_names,
    vs_clear_cache,
)
from vspreview.widgets import FrameEdit, TimeEdit


# TODO: think of proper fix for frame data sharing issue


class BenchmarkToolbar(AbstractToolbar):
    __slots__ = (
        'start_frame_control',
        'end_frame_control',
        'total_frames_control',
        'prefetch_checkbox', 'unsequenced_checkbox',
        'run_abort_button', 'info_label',
        'running', 'unsequenced', 'run_start_time',
        'start_frame', 'end_frame', 'total_frames',
        'frames_left', 'buffer', 'update_info_timer',
    )

    def __init__(self, main: AbstractMainWindow) -> None:
        super().__init__(main, 'Benchmark')

        self.setup_ui()

        self.running = False
        self.unsequenced = False
        self.buffer: Deque[Future] = deque()
        self.run_start_time = 0.0
        self.start_frame  = Frame(0)
        self.  end_frame  = Frame(0)
        self.total_frames = FrameInterval(0)
        self.frames_left  = FrameInterval(0)

        self.sequenced_timer = Qt.QTimer()
        self.sequenced_timer.setTimerType(Qt.Qt.PreciseTimer)
        self.sequenced_timer.setInterval(0)

        self.update_info_timer = Qt.QTimer()
        self.update_info_timer.setTimerType(Qt.Qt.PreciseTimer)
        self.update_info_timer.setInterval(
            self.main.BENCHMARK_REFRESH_INTERVAL)

        self. start_frame_control.valueChanged.connect(lambda value: self.update_controls(start=      value))
        self.   end_frame_control.valueChanged.connect(lambda value: self.update_controls(  end=      value))
        self.total_frames_control.valueChanged.connect(lambda value: self.update_controls(total=              value))
        self.   prefetch_checkbox.stateChanged.connect(self.on_prefetch_changed)
        self.    run_abort_button.     clicked.connect(self.on_run_abort_pressed)
        self.     sequenced_timer.     timeout.connect(self._request_next_frame_sequenced)
        self.   update_info_timer.     timeout.connect(self.update_info)

        set_qobject_names(self)

    def setup_ui(self) -> None:
        layout = Qt.QHBoxLayout(self)
        layout.setObjectName('BenchmarkToolbar.setup_ui.layout')
        layout.setContentsMargins(0, 0, 0, 0)

        start_label = Qt.QLabel(self)
        start_label.setObjectName('BenchmarkToolbar.setup_ui.start_label')
        start_label.setText('Start:')
        layout.addWidget(start_label)

        self.start_frame_control = FrameEdit[Frame](self)
        layout.addWidget(self.start_frame_control)

        end_label = Qt.QLabel(self)
        end_label.setObjectName('BenchmarkToolbar.setup_ui.end_label')
        end_label.setText('End:')
        layout.addWidget(end_label)

        self.end_frame_control = FrameEdit[Frame](self)
        layout.addWidget(self.end_frame_control)

        total_label = Qt.QLabel(self)
        total_label.setObjectName('BenchmarkToolbar.setup_ui.total_label')
        total_label.setText('Total:')
        layout.addWidget(total_label)

        self.total_frames_control = FrameEdit[FrameInterval](self)
        self.total_frames_control.setMinimum(FrameInterval(1))
        layout.addWidget(self.total_frames_control)

        self.prefetch_checkbox = Qt.QCheckBox(self)
        self.prefetch_checkbox.setText('Prefetch')
        self.prefetch_checkbox.setChecked(True)
        self.prefetch_checkbox.setToolTip(
            'Request multiple frames in advance.')
        layout.addWidget(self.prefetch_checkbox)

        self.unsequenced_checkbox = Qt.QCheckBox(self)
        self.unsequenced_checkbox.setText('Unsequenced')
        self.unsequenced_checkbox.setChecked(True)
        self.unsequenced_checkbox.setToolTip(
            "If enabled, next frame will be requested each time "
            "frameserver returns completed frame. "
            "If disabled, first frame that's currently processing "
            "will be waited before requesting next. Like for playback. "
        )
        layout.addWidget(self.unsequenced_checkbox)

        self.run_abort_button = Qt.QPushButton(self)
        self.run_abort_button.setText('Run')
        self.run_abort_button.setCheckable(True)
        layout.addWidget(self.run_abort_button)

        self.info_label = Qt.QLabel(self)
        layout.addWidget(self.info_label)

        layout.addStretch()

    def on_current_output_changed(self, index: int, prev_index: int) -> None:
        self. start_frame_control.setMaximum(self.main.current_output.end_frame)
        self.   end_frame_control.setMaximum(self.main.current_output.end_frame)
        self.total_frames_control.setMaximum(self.main.current_output.total_frames)


    def run(self) -> None:
        from copy import deepcopy

        from vapoursynth import VideoFrame

        if self.main.BENCHMARK_CLEAR_CACHE:
            vs_clear_cache()
        if self.main.BENCHMARK_FRAME_DATA_SHARING_FIX:
            self.main.current_output.graphics_scene_item.setImage(
                self.main.current_output.graphics_scene_item.image().copy())

        self.start_frame  = self.start_frame_control .value()
        self.  end_frame  = self.  end_frame_control .value()
        self.total_frames = self.total_frames_control.value()
        self.frames_left  = deepcopy(self.total_frames)
        if self.prefetch_checkbox.isChecked():
            concurrent_requests_count = get_usable_cpus_count()
        else:
            concurrent_requests_count = 1

        self.unsequenced = self.unsequenced_checkbox.isChecked()
        if not self.unsequenced:
            self.buffer = deque([], concurrent_requests_count)
            self.sequenced_timer.start()

        self.running = True
        self.run_start_time = perf_counter()

        for offset in range(min(int(self.frames_left),
                                concurrent_requests_count)):
            if self.unsequenced:
                self._request_next_frame_unsequenced()
            else:
                frame = self.start_frame + FrameInterval(offset)
                future = self.main.current_output.vs_output.get_frame_async(
                    int(frame))
                self.buffer.appendleft(future)

        self.update_info_timer.start()

    def abort(self) -> None:
        if self.running:
            self.update_info()

        self.running = False
        Qt.QMetaObject.invokeMethod(self.update_info_timer, 'stop',
                                    Qt.Qt.QueuedConnection)

        if self.run_abort_button.isChecked():
            self.run_abort_button.click()

    def _request_next_frame_sequenced(self) -> None:
        if self.frames_left <= FrameInterval(0):
            self.abort()
            return

        self.buffer.pop().result()

        next_frame = self.end_frame + FrameInterval(1) - self.frames_left
        if next_frame <= self.end_frame:
            new_future = self.main.current_output.vs_output.get_frame_async(
                int(next_frame))
            self.buffer.appendleft(new_future)

        self.frames_left -= FrameInterval(1)

    def _request_next_frame_unsequenced(self, future: Optional[Future] = None) -> None:
        if self.frames_left <= FrameInterval(0):
            self.abort()
            return

        if self.running:
            next_frame = self.end_frame + FrameInterval(1) - self.frames_left
            new_future = self.main.current_output.vs_output.get_frame_async(
                int(next_frame))
            new_future.add_done_callback(self._request_next_frame_unsequenced)

        if future is not None:
            future.result()
        self.frames_left -= FrameInterval(1)


    def on_run_abort_pressed(self, checked: bool) -> None:
        if checked:
            self.set_ui_editable(False)
            self.run()
        else:
            self.set_ui_editable(True)
            self.abort()

    def on_prefetch_changed(self, new_state: int) -> None:
        if new_state == Qt.Qt.Checked:
            self.unsequenced_checkbox.setEnabled(True)
        elif new_state == Qt.Qt.Unchecked:
            self.unsequenced_checkbox.setChecked(False)
            self.unsequenced_checkbox.setEnabled(False)

    def set_ui_editable(self, new_state: bool) -> None:
        self. start_frame_control.setEnabled(new_state)
        self.   end_frame_control.setEnabled(new_state)
        self.total_frames_control.setEnabled(new_state)
        self.   prefetch_checkbox.setEnabled(new_state)
        self. unsequenced_checkbox.setEnabled(new_state)

    def update_controls(self, start: Optional[Frame] = None, end: Optional[Frame] = None, total: Optional[FrameInterval] = None) -> None:
        if start is not None:
            end   = self.   end_frame_control.value()
            total = self.total_frames_control.value()

            if start > end:
                end = start
            total = end - start + FrameInterval(1)

        elif end is not None:
            start = self. start_frame_control.value()
            total = self.total_frames_control.value()

            if end < start:
                start = end
            total = end - start + FrameInterval(1)

        elif total is not None:
            start = self.start_frame_control.value()
            end   = self.  end_frame_control.value()
            old_total = end - start + FrameInterval(1)
            delta = total - old_total

            end += delta
            if end > self.main.current_output.end_frame:
                start -= end - self.main.current_output.end_frame
                end    = self.main.current_output.end_frame
        else:
            return

        qt_silent_call(self. start_frame_control.setValue, start)
        qt_silent_call(self.   end_frame_control.setValue, end)
        qt_silent_call(self.total_frames_control.setValue, total)

    def update_info(self) -> None:
        run_time = TimeInterval(seconds=(perf_counter() - self.run_start_time))
        frames_done = self.total_frames - self.frames_left
        fps = int(frames_done) / float(run_time)

        info_str = (f"{frames_done}/{self.total_frames} frames in {strfdelta(run_time, '%M:%S.%Z')}, {fps:.4f} fps")
        self.info_label.setText(info_str)
