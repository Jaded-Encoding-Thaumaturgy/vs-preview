from __future__ import annotations

import vapoursynth as vs
from time import perf_counter
from collections import deque
from concurrent.futures import Future
from typing import Any, Deque, Mapping

from PyQt5.QtCore import Qt, QTimer, QMetaObject
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QLabel, QPushButton

from vspreview.core import (
    AbstractMainWindow, AbstractToolbar, Frame, FrameInterval, Time,
    TimeInterval, QYAMLObjectSingleton,
)
from vspreview.utils import (
    get_usable_cpus_count, qt_silent_call, set_qobject_names,
    vs_clear_cache, try_load, strfdelta
)
from vspreview.widgets import FrameEdit, TimeEdit


# TODO: think of proper fix for frame data sharing issue


class BenchmarkSettings(QWidget, QYAMLObjectSingleton):
    yaml_tag = '!BenchmarkSettings'

    __slots__ = (
        'clear_cache_checkbox', 'refresh_interval_label',
        'refresh_interval_control', 'frame_data_sharing_fix_checkbox',
    )

    def __init__(self) -> None:
        super().__init__()

        self.setup_ui()

        self.set_defaults()

        set_qobject_names(self)

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setObjectName('BenchmarkSettings.setup_ui.layout')

        self.clear_cache_checkbox = QCheckBox(self)
        self.clear_cache_checkbox.setText(
            'Clear VS frame caches before each run'
        )
        layout.addWidget(self.clear_cache_checkbox)

        refresh_interval_layout = QHBoxLayout()
        refresh_interval_layout.setObjectName(
            'BenchmarkSettings.setup_ui.refresh_interval_layout'
        )
        layout.addLayout(refresh_interval_layout)

        self.refresh_interval_label = QLabel(self)
        self.refresh_interval_label.setText('Refresh interval')
        refresh_interval_layout.addWidget(self.refresh_interval_label)

        self.refresh_interval_control = TimeEdit[TimeInterval](self)
        refresh_interval_layout.addWidget(self.refresh_interval_control)

        self.frame_data_sharing_fix_checkbox = QCheckBox(self)
        self.frame_data_sharing_fix_checkbox.setText(
            '(Debug) Enable frame data sharing fix'
        )
        layout.addWidget(self.frame_data_sharing_fix_checkbox)

    def set_defaults(self) -> None:
        self.clear_cache_checkbox.setChecked(False)
        self.refresh_interval_control.setValue(TimeInterval(milliseconds=150))
        self.frame_data_sharing_fix_checkbox.setChecked(True)

    @property
    def clear_cache_enabled(self) -> bool:
        return self.clear_cache_checkbox.isChecked()

    @property
    def refresh_interval(self) -> TimeInterval:
        return self.refresh_interval_control.value()

    @property
    def frame_data_sharing_fix_enabled(self) -> bool:
        return self.frame_data_sharing_fix_checkbox.isChecked()

    def __getstate__(self) -> Mapping[str, Any]:
        return {
            'clear_cache_enabled': self.clear_cache_enabled,
            'refresh_interval': self.refresh_interval,
            'frame_data_sharing_fix_enabled':
            self.frame_data_sharing_fix_enabled,
        }

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        try_load(
            state, 'clear_cache_enabled', bool,
            self.clear_cache_checkbox.setChecked,
            'Storage loading: Benchmark settings: failed to parse clear cache flag.'
        )
        try_load(
            state, 'refresh_interval', TimeInterval,
            self.refresh_interval_control.setValue,
            'Storage loading: Benchmark settings: failed to parse refresh interval.'
        )
        try_load(
            state, 'frame_data_sharing_fix_enabled', bool,
            self.frame_data_sharing_fix_checkbox.setChecked,
            'Storage loading: Benchmark settings: failed to parse frame_data_sharing_fix_enabled flag.'
        )


class BenchmarkToolbar(AbstractToolbar):
    _storable_attrs = [
        'settings',
    ]
    __slots__ = _storable_attrs + [
        'start_frame_control', 'start_time_control',
        'end_frame_control', 'end_time_control',
        'total_frames_control', 'total_time_control',
        'prefetch_checkbox', 'unsequenced_checkbox',
        'run_abort_button', 'info_label',
        'running', 'unsequenced', 'run_start_time',
        'start_frame', 'end_frame', 'total_frames',
        'frames_left', 'buffer', 'update_info_timer',
        'sequenced_timer',
    ]

    def __init__(self, main: AbstractMainWindow) -> None:
        super().__init__(main, 'Benchmark', BenchmarkSettings())

        self.setup_ui()

        self.running = False
        self.unsequenced = False
        self.buffer: Deque[Future[vs.VideoFrame]] = deque()
        self.run_start_time = 0.0
        self.start_frame = Frame(0)
        self.end_frame = Frame(0)
        self.total_frames = FrameInterval(0)
        self.frames_left = FrameInterval(0)

        self.sequenced_timer = QTimer()
        self.sequenced_timer.setTimerType(Qt.PreciseTimer)
        self.sequenced_timer.setInterval(0)

        self.update_info_timer = QTimer()
        self.update_info_timer.setTimerType(Qt.PreciseTimer)

        self.start_frame_control.valueChanged.connect(lambda value: self.update_controls(start=value))
        self.start_time_control.valueChanged.connect(
            lambda value: self.update_controls(start=Frame(value))
        )
        self.end_frame_control.valueChanged.connect(lambda value: self.update_controls(end=value))
        self.end_time_control.valueChanged.connect(lambda value: self.update_controls(end=Frame(value)))
        self.total_frames_control.valueChanged.connect(lambda value: self.update_controls(total=value))
        self.total_time_control.valueChanged.connect(
            lambda value: self.update_controls(total=FrameInterval(value))
        )
        self.prefetch_checkbox.stateChanged.connect(self.on_prefetch_changed)
        self.run_abort_button.clicked.connect(self.on_run_abort_pressed)
        self.sequenced_timer.timeout.connect(self._request_next_frame_sequenced)
        self.update_info_timer.timeout.connect(self.update_info)

        set_qobject_names(self)

    def setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setObjectName('BenchmarkToolbar.setup_ui.layout')
        layout.setContentsMargins(0, 0, 0, 0)

        start_label = QLabel(self)
        start_label.setObjectName('BenchmarkToolbar.setup_ui.start_label')
        start_label.setText('Start:')
        layout.addWidget(start_label)

        self.start_frame_control = FrameEdit[Frame](self)
        layout.addWidget(self.start_frame_control)

        self.start_time_control = TimeEdit[Time](self)
        layout.addWidget(self.start_time_control)

        end_label = QLabel(self)
        end_label.setObjectName('BenchmarkToolbar.setup_ui.end_label')
        end_label.setText('End:')
        layout.addWidget(end_label)

        self.end_frame_control = FrameEdit[Frame](self)
        layout.addWidget(self.end_frame_control)

        self.end_time_control = TimeEdit[Time](self)
        layout.addWidget(self.end_time_control)

        total_label = QLabel(self)
        total_label.setObjectName('BenchmarkToolbar.setup_ui.total_label')
        total_label.setText('Total:')
        layout.addWidget(total_label)

        self.total_frames_control = FrameEdit[FrameInterval](self)
        self.total_frames_control.setMinimum(FrameInterval(1))
        layout.addWidget(self.total_frames_control)

        self.total_time_control = TimeEdit[TimeInterval](self)
        layout.addWidget(self.total_time_control)

        self.prefetch_checkbox = QCheckBox(self)
        self.prefetch_checkbox.setText('Prefetch')
        self.prefetch_checkbox.setChecked(True)
        self.prefetch_checkbox.setToolTip(
            'Request multiple frames in advance.'
        )
        layout.addWidget(self.prefetch_checkbox)

        self.unsequenced_checkbox = QCheckBox(self)
        self.unsequenced_checkbox.setText('Unsequenced')
        self.unsequenced_checkbox.setChecked(True)
        self.unsequenced_checkbox.setToolTip(
            "If enabled, next frame will be requested each time "
            "frameserver returns completed frame. "
            "If disabled, first frame that's currently processing "
            "will be waited before requesting next. Like for playback. "
        )
        layout.addWidget(self.unsequenced_checkbox)

        self.run_abort_button = QPushButton(self)
        self.run_abort_button.setText('Run')
        self.run_abort_button.setCheckable(True)
        layout.addWidget(self.run_abort_button)

        self.info_label = QLabel(self)
        layout.addWidget(self.info_label)

        layout.addStretch()

    def on_current_output_changed(self, index: int, prev_index: int) -> None:
        self.start_frame_control.setMaximum(self.main.current_output.end_frame)
        self.start_time_control.setMaximum(self.main.current_output.end_time)
        self.end_frame_control.setMaximum(self.main.current_output.end_frame)
        self.end_time_control.setMaximum(self.main.current_output.end_time)
        self.total_frames_control.setMaximum(self.main.current_output.total_frames)
        self.total_time_control.setMaximum(self.main.current_output.total_time)
        self.total_time_control.setMaximum(TimeInterval(FrameInterval(1)))

    def run(self) -> None:
        from copy import deepcopy

        if self.settings.clear_cache_enabled:
            vs_clear_cache()

        if self.settings.frame_data_sharing_fix_enabled:
            self.main.current_output.graphics_scene_item.setPixmap(
                self.main.current_output.graphics_scene_item.pixmap().copy()
            )

        self.start_frame = self.start_frame_control.value()
        self.end_frame = self.end_frame_control.value()
        self.total_frames = self.total_frames_control.value()
        self.frames_left = deepcopy(self.total_frames)
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

        for offset in range(min(int(self.frames_left), concurrent_requests_count)):
            if self.unsequenced:
                self._request_next_frame_unsequenced()
            else:
                frame = self.start_frame + FrameInterval(offset)
                future = self.main.current_output.prepared.clip.get_frame_async(int(frame))
                self.buffer.appendleft(future)

        self.update_info_timer.setInterval(
            round(float(self.settings.refresh_interval) * 1000)
        )
        self.update_info_timer.start()

    def abort(self) -> None:
        if self.running:
            self.update_info()

        self.running = False
        QMetaObject.invokeMethod(self.update_info_timer, 'stop', Qt.QueuedConnection)

        if self.run_abort_button.isChecked():
            self.run_abort_button.click()

    def _request_next_frame_sequenced(self) -> None:
        if self.frames_left <= FrameInterval(0):
            self.abort()
            return

        self.buffer.pop().result()

        next_frame = self.end_frame + FrameInterval(1) - self.frames_left
        if next_frame <= self.end_frame:
            new_future = self.main.current_output.prepared.clip.get_frame_async(
                int(next_frame)
            )
            self.buffer.appendleft(new_future)

        self.frames_left -= FrameInterval(1)

    def _request_next_frame_unsequenced(self, future: Future | None = None) -> None:
        if self.frames_left <= FrameInterval(0):
            self.abort()
            return

        if self.running:
            next_frame = self.end_frame + FrameInterval(1) - self.frames_left
            new_future = self.main.current_output.prepared.clip.get_frame_async(
                int(next_frame)
            )
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
        if new_state == Qt.Checked:
            self.unsequenced_checkbox.setEnabled(True)
        elif new_state == Qt.Unchecked:
            self.unsequenced_checkbox.setChecked(False)
            self.unsequenced_checkbox.setEnabled(False)

    def set_ui_editable(self, new_state: bool) -> None:
        self. start_frame_control.setEnabled(new_state)
        self.start_time_control.setEnabled(new_state)
        self.end_frame_control.setEnabled(new_state)
        self.end_time_control.setEnabled(new_state)
        self.total_frames_control.setEnabled(new_state)
        self.total_time_control.setEnabled(new_state)
        self.prefetch_checkbox.setEnabled(new_state)
        self. unsequenced_checkbox.setEnabled(new_state)

    def update_controls(
        self, start: Frame | None = None, end: Frame | None = None, total: FrameInterval | None = None
    ) -> None:
        if start is not None:
            end = self.end_frame_control.value()
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
            end = self.end_frame_control.value()
            old_total = end - start + FrameInterval(1)
            delta = total - old_total

            end += delta
            if end > self.main.current_output.end_frame:
                start -= end - self.main.current_output.end_frame
                end = self.main.current_output.end_frame
        else:
            return

        qt_silent_call(self. start_frame_control.setValue, start)
        qt_silent_call(self.start_time_control.setValue, Time(start))
        qt_silent_call(self.end_frame_control.setValue, end)
        qt_silent_call(self.end_time_control.setValue, Time(end))
        qt_silent_call(self.total_frames_control.setValue, total)
        qt_silent_call(self.total_time_control.setValue, TimeInterval(total))

    def update_info(self) -> None:
        run_time = TimeInterval(seconds=(perf_counter() - self.run_start_time))
        frames_done = self.total_frames - self.frames_left
        fps = int(frames_done) / float(run_time)

        info_str = (f"{frames_done}/{self.total_frames} frames in {strfdelta(run_time, '%M:%S.%Z')}, {fps:.4f} fps")
        self.info_label.setText(info_str)

    def __getstate__(self) -> Mapping[str, Any]:
        return {
            attr_name: getattr(self, attr_name)
            for attr_name in self._storable_attrs
        }

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        try_load(
            state, 'settings', BenchmarkSettings, self.settings,
            'Storage loading: Benchmark toolbar: failed to parse settings.'
        )
