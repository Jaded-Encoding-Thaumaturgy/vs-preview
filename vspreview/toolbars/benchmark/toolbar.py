from __future__ import annotations

from collections import deque
from concurrent.futures import Future
from copy import deepcopy
from time import perf_counter

from PyQt6.QtCore import QMetaObject, Qt
from PyQt6.QtWidgets import QLabel
from vstools import vs

from ...core import AbstractMainWindow, AbstractToolbar, CheckBox, Frame, PushButton, Time, Timer
from ...core.custom import FrameEdit
from ...utils import qt_silent_call, strfdelta, vs_clear_cache
from .settings import BenchmarkSettings


class BenchmarkToolbar(AbstractToolbar):
    __slots__ = (
        'start_frame_control',
        'end_frame_control', 'total_frames_control',
        'prefetch_checkbox', 'unsequenced_checkbox',
        'run_abort_button', 'info_label', 'running',
        'unsequenced', 'run_start_time', 'start_frame',
        'end_frame', 'total_frames', 'frames_left', 'buffer',
        'update_info_timer', 'sequenced_timer'
    )

    def __init__(self, main: AbstractMainWindow) -> None:
        super().__init__(main, BenchmarkSettings())

        self.setup_ui()

        self.running = False
        self.unsequenced = False
        self.buffer = deque[Future[vs.VideoFrame]]()
        self.run_start_time = 0.0
        self.start_frame = Frame(0)
        self.end_frame = Frame(0)
        self.total_frames = Frame(0)
        self.frames_left = Frame(0)

        self.sequenced_timer = Timer(
            timeout=self._request_next_frame_sequenced, timerType=Qt.TimerType.PreciseTimer, interval=0
        )

        self.update_info_timer = Timer(timeout=self.update_info, timerType=Qt.TimerType.PreciseTimer)

        self.set_qobject_names()

    def setup_ui(self) -> None:
        super().setup_ui()

        self.start_frame_control = FrameEdit(self, valueChanged=lambda value: self.update_controls(start=value))

        self.end_frame_control = FrameEdit(self, valueChanged=lambda value: self.update_controls(end=value))

        self.total_frames_control = FrameEdit(self, 1, valueChanged=lambda value: self.update_controls(total=value))

        self.unsequenced_checkbox = CheckBox(
            'Unsequenced', self, checked=True, tooltip=(
                "If enabled, next frame will be requested each time frameserver returns completed frame.\n"
                "If disabled, first frame that's currently processing will be waited before requesting the next one."
            )
        )

        self.prefetch_checkbox = CheckBox(
            'Prefetch', self, checked=True, tooltip='Request multiple frames in advance.',
            stateChanged=self.on_prefetch_changed
        )

        self.run_abort_button = PushButton('Run', self, checkable=True, clicked=self.on_run_abort_pressed)

        self.info_label = QLabel(self)

        self.hlayout.addWidgets([
            QLabel('Start:'), self.start_frame_control,
            QLabel('End:'), self.end_frame_control,
            QLabel('Total:'), self.total_frames_control,
            self.prefetch_checkbox,
            self.unsequenced_checkbox,
            self.run_abort_button,
            self.info_label,
        ])
        self.hlayout.addStretch()

    def on_current_output_changed(self, index: int, prev_index: int) -> None:
        self.start_frame_control.setMaximum(self.main.current_output.total_frames - 1)
        self.end_frame_control.setMaximum(self.main.current_output.total_frames - 1)
        self.total_frames_control.setMaximum(self.main.current_output.total_frames - Frame(1))

    def run(self) -> None:
        if self.settings.clear_cache_enabled:
            vs_clear_cache()

        if self.settings.frame_data_sharing_fix_enabled:
            self.main.current_output.update_graphic_item(
                self.main.current_output.graphics_scene_item.pixmap().copy()
            )

        self.start_frame = self.start_frame_control.value()
        self.end_frame = self.end_frame_control.value()
        self.total_frames = self.total_frames_control.value()
        self.frames_left = deepcopy(self.total_frames)
        if self.prefetch_checkbox.isChecked():
            concurrent_requests_count = self.main.settings.usable_cpus_count
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
                frame = self.start_frame + Frame(offset)
                future = self.main.current_output.prepared.clip.get_frame_async(int(frame))
                self.buffer.appendleft(future)

        self.update_info_timer.setInterval(round(float(self.settings.refresh_interval) * 1000))
        self.update_info_timer.start()

    def abort(self) -> None:
        if self.running:
            self.update_info()

        self.running = False
        QMetaObject.invokeMethod(self.update_info_timer, 'stop', Qt.QueuedConnection)

        if self.run_abort_button.isChecked():
            self.run_abort_button.click()

    def _request_next_frame_sequenced(self) -> None:
        if self.frames_left <= Frame(0):
            self.abort()
            return

        self.buffer.pop().result()

        next_frame = self.end_frame + Frame(1) - self.frames_left
        if next_frame <= self.end_frame:
            new_future = self.main.current_output.prepared.clip.get_frame_async(int(next_frame))
            self.buffer.appendleft(new_future)

        self.frames_left -= Frame(1)

    def _request_next_frame_unsequenced(self, future: Future | None = None) -> None:
        if self.frames_left <= Frame(0):
            self.abort()
            return

        if self.running:
            next_frame = self.end_frame + Frame(1) - self.frames_left
            new_future = self.main.current_output.prepared.clip.get_frame_async(int(next_frame))
            new_future.add_done_callback(self._request_next_frame_unsequenced)

        if future is not None:
            future.result()
        self.frames_left -= Frame(1)

    def on_run_abort_pressed(self, checked: bool) -> None:
        self.set_ui_editable(not checked)
        if checked:
            self.run()
        else:
            self.abort()

    def on_prefetch_changed(self, new_state: int) -> None:
        if new_state == Qt.Checked:
            self.unsequenced_checkbox.setEnabled(True)
        elif new_state == Qt.Unchecked:
            self.unsequenced_checkbox.setChecked(False)
            self.unsequenced_checkbox.setEnabled(False)

    def set_ui_editable(self, new_state: bool) -> None:
        self. start_frame_control.setEnabled(new_state)
        self.end_frame_control.setEnabled(new_state)
        self.total_frames_control.setEnabled(new_state)
        self.prefetch_checkbox.setEnabled(new_state)
        self. unsequenced_checkbox.setEnabled(new_state)

    def update_controls(
        self, start: Frame | None = None, end: Frame | None = None, total: Frame | None = None
    ) -> None:
        if not hasattr(self.main, 'current_output'):
            return

        if start is not None:
            end = self.end_frame_control.value()
            total = self.total_frames_control.value()

            if start > end:
                end = start
            total = end - start + Frame(1)
        elif end is not None:
            start = self.start_frame_control.value()
            total = self.total_frames_control.value()

            if end < start:
                start = end
            total = end - start + Frame(1)
        elif total is not None:
            start = self.start_frame_control.value()
            end = self.end_frame_control.value()
            old_total = end - start + Frame(1)
            delta = total - old_total

            end += delta
            if end > (e := self.main.current_output.total_frames - 1):
                start -= end - e
                end = e
        else:
            return

        qt_silent_call(self.start_frame_control.setValue, start)
        qt_silent_call(self.end_frame_control.setValue, end)
        qt_silent_call(self.total_frames_control.setValue, total)

    def update_info(self) -> None:
        run_time = Time(seconds=(perf_counter() - self.run_start_time))
        frames_done = self.total_frames - self.frames_left
        fps = int(frames_done) / float(run_time)

        info_str = (f"{frames_done}/{self.total_frames} frames in {strfdelta(run_time, '%M:%S.%Z')}, {fps:.4f} fps")
        self.info_label.setText(info_str)
