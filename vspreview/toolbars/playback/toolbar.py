from __future__ import annotations

import gc
import logging
from math import floor
import vapoursynth as vs
from collections import deque
from time import perf_counter_ns
from concurrent.futures import Future
from typing import Any, cast, Deque, Mapping

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QDoubleSpinBox, QComboBox

from ...models import AudioOutputs
from ...utils import debug, qt_silent_call
from ...core.custom import ComboBox, FrameEdit, TimeEdit
from ...core import AbstractMainWindow, AbstractToolbar, Frame, AudioOutput, Time, try_load, PushButton, CheckBox

from .settings import PlaybackSettings


class PlaybackToolbar(AbstractToolbar):
    __slots__ = (
        'play_timer', 'fps_timer', 'fps_history', 'current_fps',
        'seek_n_frames_b_button', 'seek_to_prev_button', 'play_pause_button',
        'seek_to_next_button', 'seek_n_frames_f_button', 'play_n_frames_button',
        'seek_frame_control', 'seek_time_control',
        'fps_spinbox', 'fps_unlimited_checkbox', 'fps_variable_checkbox', 'fps_reset_button',
        'play_start_time', 'play_start_frame', 'play_end_time',
        'play_end_frame', 'play_buffer', 'toggle_button', 'play_timer_audio',
        'current_audio_frame', 'play_buffer_audio', 'audio_outputs',
        'audio_outputs_combobox', 'seek_to_start_button', 'seek_to_end_button'
    )

    def __init__(self, main: AbstractMainWindow) -> None:
        super().__init__(main, PlaybackSettings())
        self.setup_ui()

        self.play_buffer: Deque[Future[vs.VideoFrame]] = deque()
        self.play_timer = QTimer(timeout=self._show_next_frame, timerType=Qt.PreciseTimer)

        self.play_timer_audio = QTimer(timeout=self._play_next_audio_frame, timerType=Qt.PreciseTimer)

        self.current_audio_frame = Frame(0)
        self.play_buffer_audio: Deque[Future] = deque()

        self.fps_history: Deque[int] = deque([], int(self.settings.FPS_AVERAGING_WINDOW_SIZE) + 1)
        self.current_fps = 0.0
        self.fps_timer = QTimer(timeout=lambda: self.fps_spinbox.setValue(self.current_fps), timerType=Qt.PreciseTimer)

        self.play_start_time: int | None = None
        self.play_start_frame = Frame(0)
        self.play_end_time = 0
        self.play_end_frame = Frame(0)
        self.audio_outputs: AudioOutputs = []  # type: ignore
        self.last_frame = Frame(0)

        self.main.timeline.clicked.connect(self.on_timeline_clicked)

        self.add_shortcuts()

        self.set_qobject_names()

    def setup_ui(self) -> None:
        super().setup_ui()

        self.seek_to_start_button = PushButton(
            '⏮', self, tooltip='Seek to First Frame', clicked=self.seek_to_start
        )

        self.seek_n_frames_b_button = PushButton(
            '⏪', self, tooltip='Seek N Frames Backwards',
            clicked=lambda _: self.seek_offset(-1 * self.seek_frame_control.value())
        )

        self.seek_to_prev_button = PushButton(
            '⏪', self, tooltip='Seek 1 Frame Backwards', clicked=lambda _: self.seek_offset(-1)
        )

        self.play_pause_button = PushButton(
            '⏯', self, tooltip='Play/Pause', checkable=True, clicked=self.on_play_pause_clicked
        )

        self.seek_to_next_button = PushButton(
            '⏩', self, tooltip='Seek 1 Frame Forward', clicked=lambda _: self.seek_offset(1)
        )

        self.seek_n_frames_f_button = PushButton(
            '⏩', self, tooltip='Seek N Frames Forward',
            clicked=lambda _: self.seek_offset(self.seek_frame_control.value())
        )

        self.seek_to_end_button = PushButton(
            '⏭', self, tooltip='Seek to Last Frame', clicked=self.seek_to_end
        )

        self.seek_frame_control = FrameEdit(
            self, 1, value=self.settings.SEEK_STEP, tooltip='Seek N Frames Step',
            valueChanged=self.on_seek_frame_changed
        )

        self.play_n_frames_button = PushButton(
            '⏯', self, tooltip='Play N Frames', checkable=True, clicked=self.on_play_n_frames_clicked
        )

        self.seek_time_control = TimeEdit(self, valueChanged=self.on_seek_time_changed)

        self.fps_spinbox = QDoubleSpinBox(self, valueChanged=self.on_fps_changed)
        self.fps_spinbox.setRange(0.001, 9999.0)
        self.fps_spinbox.setDecimals(3)
        self.fps_spinbox.setSuffix(' fps')

        self.fps_reset_button = PushButton('Reset FPS', self, clicked=self.reset_fps)

        self.fps_unlimited_checkbox = CheckBox('Unlimited FPS', self, stateChanged=self.on_fps_unlimited_changed)

        self.fps_variable_checkbox = CheckBox('Variable FPS', self, stateChanged=self.on_fps_variable_changed)

        self.mute_checkbox = CheckBox('Mute', self, checked=True, stateChanged=self.on_mute_changed)

        self.audio_outputs_combobox = ComboBox[AudioOutput](
            self, enabled=False, editable=True, insertPolicy=QComboBox.InsertAtCurrent,
            duplicatesEnabled=True, sizeAdjustPolicy=QComboBox.AdjustToContents
        )

        self.hlayout.addWidgets([
            self.seek_to_start_button, self.seek_n_frames_b_button, self.seek_to_prev_button,
            self.play_pause_button,
            self.seek_to_next_button, self.seek_n_frames_f_button, self.seek_to_end_button,
            self.seek_frame_control, self.play_n_frames_button,
            self.seek_time_control,
            self.fps_spinbox, self.fps_reset_button,
            self.fps_unlimited_checkbox, self.fps_variable_checkbox,
            self.get_separator(),
            self.mute_checkbox, self.audio_outputs_combobox
        ])

        self.hlayout.addStretch()

    def add_shortcuts(self) -> None:
        self.main.add_shortcut(Qt.Key_Space, self.play_pause_button.click)
        self.main.add_shortcut(Qt.Key_Left, self.seek_to_prev_button.click)
        self.main.add_shortcut(Qt.Key_Right, self.seek_to_next_button.click)
        self.main.add_shortcut(Qt.SHIFT + Qt.Key_Left, self.seek_n_frames_b_button.click)
        self.main.add_shortcut(Qt.SHIFT + Qt.Key_Right, self.seek_n_frames_f_button.click)
        self.main.add_shortcut(Qt.Key_PageUp, self.seek_n_frames_b_button.click)
        self.main.add_shortcut(Qt.Key_PageDown, self.seek_n_frames_f_button.click)
        self.main.add_shortcut(Qt.Key_Home, self.seek_to_start_button.click)
        self.main.add_shortcut(Qt.Key_End, self.seek_to_end_button.click)

    def on_current_output_changed(self, index: int, prev_index: int) -> None:
        qt_silent_call(self.seek_frame_control.setMaximum, self.main.current_output.total_frames)
        qt_silent_call(self.seek_time_control.setMaximum, self.main.current_output.total_time)
        qt_silent_call(self.seek_time_control.setMinimum, Time(Frame(1)))
        qt_silent_call(self.seek_time_control.setValue, Time(self.seek_frame_control.value()))
        qt_silent_call(self.fps_spinbox.setValue, self.main.current_output.play_fps)

    def update_outputs(self, outputs: AudioOutputs) -> None:
        self.audio_outputs = outputs
        self.audio_outputs_combobox.setModel(self.audio_outputs)

    def rescan_outputs(self) -> None:
        self.update_outputs(AudioOutputs(self.main))

    def get_true_fps(self, frameprops: vs.FrameProps) -> float:
        print(frameprops)
        if any({x not in frameprops for x in {'_DurationDen', '_DurationNum'}}):
            raise RuntimeError(
                'Playback: DurationDen and DurationNum frame props are needed for VFR clips!'
            )
        return cast(float, frameprops['_DurationDen']) / cast(float, frameprops['_DurationNum'])

    def allocate_buffer(self, is_alpha: bool = False) -> None:
        if is_alpha:
            play_buffer_size = int(min(
                self.settings.playback_buffer_size, (
                    self.main.current_output.end_frame - self.main.current_output.last_showed_frame
                ) * 2
            ))
            play_buffer_size -= play_buffer_size % 2
            self.play_buffer = deque([], play_buffer_size)
        else:
            play_buffer_size = int(min(
                self.settings.playback_buffer_size,
                self.main.current_output.end_frame - self.main.current_output.last_showed_frame
            ))
            self.play_buffer = deque([], play_buffer_size)

    def play(self, stop_at_frame: int | Frame | None = None) -> None:
        if self.main.current_output.last_showed_frame == self.main.current_output.end_frame:
            return

        if self.main.statusbar.label.text() == 'Ready':
            self.main.statusbar.label.setText('Playing')

        if self.main.current_output.prepared.alpha is None:
            self.allocate_buffer(False)
            for i in range(cast(int, self.play_buffer.maxlen)):
                nextFrame = int(self.main.current_output.last_showed_frame + Frame(i) + Frame(1))
                self.play_buffer.appendleft(
                    (nextFrame, self.main.current_output.prepared.clip.get_frame_async(nextFrame))
                )
        else:
            self.allocate_buffer(True)
            for i in range(cast(int, self.play_buffer.maxlen) // 2):
                frame = (self.main.current_output.last_showed_frame + Frame(i) + Frame(1))
                self.play_buffer.appendleft(
                    (int(frame), self.main.current_output.prepared.clip.get_frame_async(int(frame)))
                )
                self.play_buffer.appendleft(
                    (int(frame), self.main.current_output.prepared.alpha.get_frame_async(int(frame)))
                )

        self.last_frame = Frame(stop_at_frame or self.main.current_output.end_frame)

        if self.fps_unlimited_checkbox.isChecked() or self.main.toolbars.debug.settings.DEBUG_PLAY_FPS:
            self.mute_checkbox.setChecked(True)
            self.play_timer.start(0)
            if self.main.toolbars.debug.settings.DEBUG_PLAY_FPS:
                self.play_start_time = debug.perf_counter_ns()
                self.play_start_frame = self.main.current_output.last_showed_frame
            else:
                self.fps_timer.start(self.settings.FPS_REFRESH_INTERVAL)
        else:
            if self.fps_variable_checkbox.isChecked() and self.main.current_output._stateset:
                fps = self.get_true_fps(self.main.current_output.props)
            else:
                fps = self.main.current_output.play_fps

            self.play_timer.start(floor(1000 / fps))

        self.current_audio_output = self.audio_outputs_combobox.currentValue()

        if not self.mute_checkbox.isChecked() and self.current_audio_output is not None:
            self.play_audio()

    def play_audio(self) -> None:
        self.current_audio_output = self.audio_outputs_combobox.currentValue()

        self.audio_outputs_combobox.setEnabled(False)
        self.current_audio_frame = self.current_audio_output.to_frame(
            Time(self.main.current_output.last_showed_frame)
        )

        self.current_audio_output.render_audio_frame(self.current_audio_frame)
        self.current_audio_output.render_audio_frame(self.current_audio_frame + Frame(1))
        self.current_audio_output.render_audio_frame(self.current_audio_frame + Frame(2))

        self.play_buffer_audio = deque([], 5)

        for i in range(2, cast(int, self.play_buffer_audio.maxlen)):
            self.play_buffer_audio.appendleft(
                self.current_audio_output.vs_output.get_frame_async(
                    int(self.current_audio_frame + Frame(i) + Frame(1))
                )
            )

        self.play_timer_audio.start(
            floor(
                1000 / self.current_audio_output.fps / self.main.current_output.play_fps * self.main.current_output.fps
            )
        )

    def _show_next_frame(self) -> None:
        if not self.main.current_output.prepared:
            return

        if self.last_frame <= self.main.current_output.last_showed_frame:
            self.play_n_frames_button.click()
            return

        n_frames = 1 if self.main.current_output.prepared.alpha is None else 2
        next_buffered_frame = self.main.current_output.last_showed_frame + (
            self.settings.playback_buffer_size // n_frames
        )

        try:
            frames_futures = [(x[0], x[1].result()) for x in [self.play_buffer.pop() for _ in range(n_frames)]]
        except IndexError:
            self.play_pause_button.click()
            return

        if next_buffered_frame <= self.main.current_output.end_frame:
            self.play_buffer.appendleft(
                (next_buffered_frame, self.main.current_output.prepared.clip.get_frame_async(next_buffered_frame))
            )
            if self.main.current_output.prepared.alpha is not None:
                self.play_buffer.appendleft(
                    (next_buffered_frame, self.main.current_output.prepared.alpha.get_frame_async(next_buffered_frame))
                )

        curr_frame = Frame(frames_futures[0][0])

        if self.fps_variable_checkbox.isChecked():
            self.current_fps = self.get_true_fps(frames_futures[0][1].props)
            self.play_timer.start(floor(1000 / self.current_fps))
            self.fps_spinbox.setValue(self.current_fps)
        elif not self.main.toolbars.debug.settings.DEBUG_PLAY_FPS:
            self.update_fps_counter()

        self.main.switch_frame(curr_frame, render_frame=(x[1] for x in frames_futures))

    def _play_next_audio_frame(self) -> None:
        try:
            frame_future = self.play_buffer_audio.pop()
        except IndexError:
            self.play_pause_button.click()
            return

        next_frame_to_request = self.current_audio_frame + Frame(6)
        if next_frame_to_request <= self.current_audio_output.end_frame:
            self.play_buffer_audio.appendleft(
                self.current_audio_output.vs_output.get_frame_async(int(next_frame_to_request))
            )

        self.audio_outputs_combobox.currentValue().render_raw_audio_frame(frame_future.result())
        self.current_audio_frame += Frame(1)

    def stop(self) -> None:
        if not self.play_timer.isActive():
            return

        self.play_timer.stop()

        if self.main.toolbars.debug.settings.DEBUG_PLAY_FPS and self.play_start_time is not None:
            self.play_end_time = debug.perf_counter_ns()
            self.play_end_frame = self.main.current_output.last_showed_frame
        if self.main.statusbar.label.text() == 'Playing':
            self.main.statusbar.label.setText('Ready')

        def _del(f: Future[vs.VideoFrame]) -> None:
            f0 = f.result()
            del f, f0

        for future in self.play_buffer:
            future[1].add_done_callback(_del)

        self.play_buffer.clear()
        del self.play_buffer

        gc.collect(generation=2)

        current_audio_output = self.audio_outputs_combobox.currentValue()

        if not self.mute_checkbox.isChecked() and current_audio_output is not None:
            self.stop_audio()

        self.fps_history.clear()
        self.fps_timer.stop()

        if self.main.toolbars.debug.settings.DEBUG_PLAY_FPS and self.play_start_time is not None:
            time_interval = (self.play_end_time - self.play_start_time) / 1_000_000_000
            frame_interval = self.play_end_frame - self.play_start_frame
            logging.debug(
                f'{time_interval:.3f} s, {frame_interval} frames, {int(frame_interval) / time_interval:.3f} fps'
            )
            self.play_start_time = None

    def stop_audio(self) -> None:
        current_audio_output = self.audio_outputs_combobox.currentValue()

        self.play_timer_audio.stop()
        for future in self.play_buffer_audio:
            future.add_done_callback(lambda future: future.result())
        self.play_buffer_audio.clear()
        current_audio_output.iodevice.reset()
        self.current_audio_frame = Frame(0)
        self.audio_outputs_combobox.setEnabled(True)

    def seek_to_start(self, checked: bool | None = None) -> None:
        self.stop()
        self.main.current_output.last_showed_frame = Frame(0)

    def seek_to_end(self, checked: bool | None = None) -> None:
        self.stop()
        self.main.current_output.last_showed_frame = self.main.current_output.end_frame

    def seek_offset(self, offset: int) -> None:
        new_pos = self.main.current_output.last_showed_frame + offset

        if new_pos < 0 or new_pos > self.main.current_output.end_frame:
            return

        if self.play_timer.isActive():
            self.stop()

        self.main.switch_frame(new_pos)

    def on_seek_frame_changed(self, frame: Frame | None) -> None:
        if frame is None:
            return
        qt_silent_call(self.seek_time_control.setValue, Time(frame))

    def on_seek_time_changed(self, time: Time | None) -> None:
        if time is None:
            return
        qt_silent_call(self.seek_frame_control.setValue, Frame(time))

    def on_play_pause_clicked(self, checked: bool) -> None:
        if checked:
            self.play()
        else:
            self.stop()

    def on_timeline_clicked(self, frame: Frame, time: Time) -> None:
        if not self.play_timer.isActive() or not self.play_timer_audio.isActive():
            return

        self.audio_outputs_combobox.currentValue().iodevice.reset()
        self.current_audio_frame = self.current_audio_output.to_frame(time)

        for future in self.play_buffer_audio:
            future.add_done_callback(lambda future: future.result())
        self.play_buffer_audio.clear()

        for i in range(0, cast(int, self.play_buffer_audio.maxlen)):
            future = self.current_audio_output.vs_output.get_frame_async(
                int(self.current_audio_frame + Frame(i) + Frame(1))
            )
            self.play_buffer_audio.appendleft(future)

    def on_play_n_frames_clicked(self, checked: bool) -> None:
        if checked:
            self.play(self.main.current_output.last_showed_frame + Frame(self.seek_frame_control.value()))
        else:
            self.stop()

    def on_fps_changed(self, new_fps: float) -> None:
        if not self.fps_spinbox.isEnabled() or not hasattr(self.main, 'current_output'):
            return

        self.main.current_output.play_fps = new_fps

        if self.play_timer.isActive():
            self.stop()
            self.play()

    def reset_fps(self, checked: bool | None = None) -> None:
        self.fps_spinbox.setValue(self.main.current_output.fps_num / self.main.current_output.fps_den)

    def on_fps_unlimited_changed(self, state: int) -> None:
        if state == Qt.Checked:
            self.fps_spinbox.setEnabled(False)
            self.fps_reset_button.setEnabled(False)
            self.fps_variable_checkbox.setChecked(False)
            self.fps_variable_checkbox.setEnabled(False)
        elif state == Qt.Unchecked:
            self.fps_spinbox.setEnabled(True)
            self.fps_reset_button.setEnabled(True)
            self.fps_spinbox.setValue(self.main.current_output.play_fps)
            self.fps_variable_checkbox.setEnabled(True)

        if self.play_timer.isActive():
            self.stop()
            self.play()

    def on_fps_variable_changed(self, state: int) -> None:
        if state == Qt.Checked:
            self.fps_spinbox.setEnabled(False)
            self.fps_reset_button.setEnabled(False)
            self.fps_unlimited_checkbox.setEnabled(False)
            self.fps_unlimited_checkbox.setChecked(False)
        elif state == Qt.Unchecked:
            self.fps_spinbox.setEnabled(True)
            self.fps_reset_button.setEnabled(True)
            self.fps_unlimited_checkbox.setEnabled(True)
            self.fps_spinbox.setValue(self.main.current_output.play_fps)

        if self.play_timer.isActive():
            self.stop()
            self.play()

    def update_fps_counter(self) -> None:
        if self.fps_spinbox.isEnabled():
            return

        self.fps_history.append(perf_counter_ns())
        if len(self.fps_history) == 1:
            return

        elapsed_total = 0
        for i in range(len(self.fps_history) - 1):
            elapsed_total += self.fps_history[i + 1] - self.fps_history[i]

        self.current_fps = 1_000_000_000 / (elapsed_total / len(self.fps_history))

    def on_mute_changed(self, state: int) -> None:
        if not hasattr(self, 'audio_outputs_combox'):
            return

        if state == Qt.Checked:
            self.audio_outputs_combobox.setEnabled(False)
            if self.play_timer_audio.isActive():
                self.stop_audio()
        elif state == Qt.Unchecked:
            self.audio_outputs_combobox.setEnabled(True)
            if self.play_timer.isActive():
                self.play_audio()

    def __getstate__(self) -> Mapping[str, Any]:
        return super().__getstate__() | {
            'seek_interval_frame': self.seek_frame_control.value(),
            'audio_outputs': self.audio_outputs,
            'current_audio_output_index': self.audio_outputs_combobox.currentIndex(),
            'audio_muted': self.mute_checkbox.isChecked(),
        }

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        try_load(state, 'seek_interval_frame', Frame, self.seek_frame_control.setValue)
        try_load(state, 'audio_outputs', AudioOutputs, self.update_outputs)
        try_load(state, 'current_audio_output_index', int, self.audio_outputs_combobox.setCurrentIndex)
        try_load(state, 'audio_muted', bool, self.mute_checkbox.setChecked)
        super().__setstate__(state)
