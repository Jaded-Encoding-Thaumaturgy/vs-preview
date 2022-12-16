from __future__ import annotations

import gc
import logging
from collections import deque
from concurrent.futures import Future
from functools import partial
from math import floor
from time import perf_counter_ns
from typing import Any, Mapping, cast

from PyQt6.QtCore import Qt, QKeyCombination
from PyQt6.QtWidgets import QComboBox, QSlider
from vstools import vs

from ...core import (
    AbstractMainWindow, AbstractToolbar, AudioOutput, CheckBox, DoubleSpinBox, Frame, PushButton, Time, Timer, try_load
)
from ...core.custom import ComboBox, FrameEdit, TimeEdit
from ...models import AudioOutputs
from ...utils import debug, qt_silent_call
from .settings import PlaybackSettings


def _del_future(f: Future[vs.VideoFrame]) -> None:
    f0 = f.result()
    del f, f0


class PlaybackToolbar(AbstractToolbar):
    storable_attrs = ('audio_muted', 'audio_outputs', 'volume')

    __slots__ = (
        *storable_attrs, 'play_timer', 'fps_timer', 'fps_history', 'current_fps',
        'seek_n_frames_b_button', 'seek_to_prev_button', 'play_pause_button',
        'seek_to_next_button', 'seek_n_frames_f_button', 'play_n_frames_button',
        'seek_frame_control', 'seek_time_control',
        'fps_spinbox', 'fps_unlimited_checkbox', 'fps_variable_checkbox', 'fps_reset_button',
        'play_start_time', 'play_start_frame', 'play_end_time',
        'play_end_frame', 'play_buffer', 'toggle_button', 'play_timer_audio',
        'current_audio_frame', 'play_buffer_audio', 'audio_outputs',
        'audio_outputs_combobox', 'seek_to_start_button', 'seek_to_end_button',
        'audio_volume_slider'
    )

    def __init__(self, main: AbstractMainWindow) -> None:
        super().__init__(main, PlaybackSettings())
        self.setup_ui()

        self.play_buffer = deque[tuple[int, Future[vs.VideoFrame]]]()
        self.play_timer = Timer(timeout=self._show_next_frame, timerType=Qt.TimerType.PreciseTimer)

        self.play_timer_audio = Timer(timeout=self._play_next_audio_frame, timerType=Qt.TimerType.PreciseTimer)

        self.current_audio_output = None
        self.current_audio_frame = Frame(0)
        self.play_buffer_audio = deque[Future[vs.AudioFrame]]()

        self.fps_history = deque[int]([], int(self.settings.FPS_AVERAGING_WINDOW_SIZE) + 1)
        self.current_fps = 0.0
        self.fps_timer = Timer(
            timeout=lambda: self.fps_spinbox.setValue(self.current_fps), timerType=Qt.TimerType.PreciseTimer
        )

        self.play_start_time: int | None = None
        self.play_start_frame = Frame(0)
        self.play_end_time = 0
        self.play_end_frame = Frame(0)
        self.audio_outputs: AudioOutputs = []
        self.last_frame = Frame(0)

        self.setVolume(50, True)
        self.setMute(True)

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

        self.fps_spinbox = DoubleSpinBox(self, valueChanged=self.on_fps_changed)
        self.fps_spinbox.setRange(0.001, 9999.0)
        self.fps_spinbox.setDecimals(3)
        self.fps_spinbox.setSuffix(' fps')

        self.fps_reset_button = PushButton('Reset FPS', self, clicked=self.reset_fps)

        self.fps_unlimited_checkbox = CheckBox('Unlimited FPS', self, stateChanged=self.on_fps_unlimited_changed)

        self.fps_variable_checkbox = CheckBox('Variable FPS', self, stateChanged=self.on_fps_variable_changed)

        self.mute_button = PushButton(self, clicked=self.on_mute_clicked)
        self.mute_button.setFixedWidth(18)

        self.audio_outputs_combobox = ComboBox[AudioOutput](
            self, editable=True, insertPolicy=QComboBox.InsertPolicy.InsertAtCurrent,
            duplicatesEnabled=True, sizeAdjustPolicy=QComboBox.SizeAdjustPolicy.AdjustToContents
        )

        self.audio_volume_slider = QSlider(Qt.Orientation.Horizontal, valueChanged=self.setVolume)
        self.audio_volume_slider.setFocusPolicy(Qt.NoFocus)
        self.audio_volume_slider.setFixedWidth(120)
        self.audio_volume_slider.setRange(0, 100)
        self.audio_volume_slider.setPageStep(5)

        self.hlayout.addWidgets([
            self.seek_to_start_button, self.seek_n_frames_b_button, self.seek_to_prev_button,
            self.play_pause_button,
            self.seek_to_next_button, self.seek_n_frames_f_button, self.seek_to_end_button,
            self.seek_frame_control, self.play_n_frames_button,
            self.seek_time_control,
            self.fps_spinbox, self.fps_reset_button,
            self.fps_unlimited_checkbox, self.fps_variable_checkbox,
            self.get_separator(),
            self.audio_outputs_combobox, self.mute_button, self.audio_volume_slider
        ])

        self.hlayout.addStretch()

    def add_shortcuts(self) -> None:
        self.main.add_shortcut(Qt.Key.Key_Space, self.play_pause_button.click)
        self.main.add_shortcut(Qt.Key.Key_Left, self.seek_to_prev_button.click)
        self.main.add_shortcut(Qt.Key.Key_Right, self.seek_to_next_button.click)
        self.main.add_shortcut(QKeyCombination(Qt.SHIFT, Qt.Key.Key_Left), self.seek_n_frames_b_button.click)
        self.main.add_shortcut(QKeyCombination(Qt.SHIFT, Qt.Key.Key_Right), self.seek_n_frames_f_button.click)
        self.main.add_shortcut(Qt.Key.Key_PageUp, self.seek_n_frames_b_button.click)
        self.main.add_shortcut(Qt.Key.Key_PageDown, self.seek_n_frames_f_button.click)
        self.main.add_shortcut(Qt.Key.Key_Home, self.seek_to_start_button.click)
        self.main.add_shortcut(Qt.Key.Key_End, self.seek_to_end_button.click)

    def on_current_output_changed(self, index: int, prev_index: int) -> None:
        qt_silent_call(self.seek_frame_control.setMaximum, self.main.current_output.total_frames)
        qt_silent_call(self.seek_time_control.setMaximum, self.main.current_output.total_time)
        qt_silent_call(self.seek_time_control.setMinimum, Time(Frame(1)))
        qt_silent_call(self.seek_time_control.setValue, Time(self.seek_frame_control.value()))
        qt_silent_call(self.fps_spinbox.setValue, self.main.current_output.play_fps)

    def rescan_outputs(self, outputs: AudioOutputs | None = None) -> None:
        self.audio_outputs = outputs or AudioOutputs(self.main)
        self.audio_outputs_combobox.setModel(self.audio_outputs)

    def get_true_fps(self, n: int, frameprops: vs.FrameProps, force: bool = False) -> float:
        if (
            hasattr(self.main.current_output, 'got_timecodes')
            and self.main.current_output.got_timecodes and not force
        ):
            return float(self.main.current_output.timecodes[n])

        if any({x not in frameprops for x in {'_DurationDen', '_DurationNum'}}):
            raise RuntimeError(
                'Playback: DurationDen and DurationNum frame props are needed for VFR clips!'
            )
        return cast(float, frameprops['_DurationDen']) / cast(float, frameprops['_DurationNum'])

    def allocate_buffer(self, is_alpha: bool = False) -> None:
        if is_alpha:
            play_buffer_size = int(min(
                self.settings.playback_buffer_size, (
                    self.main.current_output.total_frames - self.main.current_output.last_showed_frame - 1
                ) * 2
            ))
            play_buffer_size -= play_buffer_size % 2
        else:
            play_buffer_size = int(min(
                self.settings.playback_buffer_size,
                self.main.current_output.total_frames - self.main.current_output.last_showed_frame - 1
            ))

        self.play_buffer = deque([], play_buffer_size)

    def play(self, stop_at_frame: int | Frame | None = None) -> None:
        if self.main.current_output.last_showed_frame > self.main.current_output.total_frames:
            return

        if self.main.statusbar.label.text() == 'Ready':
            self.main.statusbar.label.setText('Playing')

        if self.main.current_output.prepared.alpha is None:
            self.allocate_buffer(False)
            for i in range(cast(int, self.play_buffer.maxlen)):
                nextFrame = int(Frame(self.main.current_output.last_showed_frame) + i + 1)
                if nextFrame >= self.main.current_output.total_frames:
                    break
                self.play_buffer.appendleft(
                    (nextFrame, self.main.current_output.prepared.clip.get_frame_async(nextFrame))
                )
        else:
            self.allocate_buffer(True)
            for i in range(cast(int, self.play_buffer.maxlen) // 2):
                nextFrame = int(Frame(self.main.current_output.last_showed_frame) + i + 1)
                if nextFrame >= self.main.current_output.total_frames:
                    break
                self.play_buffer.appendleft(
                    (nextFrame, self.main.current_output.prepared.clip.get_frame_async(nextFrame))
                )
                self.play_buffer.appendleft(
                    (nextFrame, self.main.current_output.prepared.alpha.get_frame_async(nextFrame))
                )

        self.last_frame = Frame(stop_at_frame or (self.main.current_output.total_frames - 1))

        if self.fps_unlimited_checkbox.isChecked() or self.main.toolbars.debug.settings.DEBUG_PLAY_FPS:
            self.mute_button.setChecked(True)
            self.play_timer.start(0)
            if self.main.toolbars.debug.settings.DEBUG_PLAY_FPS:
                self.play_start_time = debug.perf_counter_ns()
                self.play_start_frame = Frame(self.main.current_output.last_showed_frame)
            else:
                self.fps_timer.start(self.settings.FPS_REFRESH_INTERVAL)
        else:
            if self.fps_variable_checkbox.isChecked() and self.main.current_output._stateset:
                fps = self.get_true_fps(self.last_frame, self.main.current_output.props)
            else:
                fps = self.main.current_output.play_fps

            self.play_timer.start(floor(1000 / fps))

        self.current_audio_output = self.audio_outputs_combobox.currentValue()

        if not self.audio_muted and self.current_audio_output is not None:
            self.play_audio()

    def play_audio(self) -> None:
        if not len(self.audio_outputs):
            return

        self.current_audio_output = self.audio_outputs_combobox.currentValue()

        self.audio_outputs_combobox.setEnabled(False)
        self.current_audio_frame = self.current_audio_output.to_frame(
            Time(self.main.current_output.last_showed_frame)
        )

        self.current_audio_output.render_audio_frame(self.current_audio_frame)
        self.current_audio_output.render_audio_frame(self.current_audio_frame + Frame(1))
        self.current_audio_output.render_audio_frame(self.current_audio_frame + Frame(2))

        self.play_buffer_audio = deque([], int(min(
            self.settings.playback_buffer_size,
            self.current_audio_output.total_frames - self.current_audio_frame - 1
        )))

        for i in range(2, cast(int, self.play_buffer_audio.maxlen)):
            self.play_buffer_audio.appendleft(
                self.current_audio_output.vs_output.get_frame_async(
                    int(self.current_audio_frame + i + 1)
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
            return self.stop()

        n_frames = 1 if self.main.current_output.prepared.alpha is None else 2
        next_buffered_frame = self.main.current_output.last_showed_frame + (
            self.settings.playback_buffer_size // n_frames
        )

        try:
            frames_futures = [(x[0], x[1].result()) for x in [self.play_buffer.pop() for _ in range(n_frames)]]
        except IndexError:
            return self.play_pause_button.click()

        if next_buffered_frame < self.main.current_output.total_frames:
            self.play_buffer.appendleft(
                (next_buffered_frame, self.main.current_output.prepared.clip.get_frame_async(next_buffered_frame))
            )
            if self.main.current_output.prepared.alpha is not None:
                self.play_buffer.appendleft(
                    (next_buffered_frame, self.main.current_output.prepared.alpha.get_frame_async(next_buffered_frame))
                )

        curr_frame = Frame(frames_futures[0][0])

        if self.fps_variable_checkbox.isChecked():
            self.current_fps = self.get_true_fps(curr_frame.value, frames_futures[0][1].props)
            self.play_timer.start(floor(1000 / self.current_fps))
            self.fps_spinbox.setValue(self.current_fps)
        elif not self.main.toolbars.debug.settings.DEBUG_PLAY_FPS:
            self.update_fps_counter()

        self.main.switch_frame(curr_frame, render_frame=(x[1] for x in frames_futures))

    def _play_next_audio_frame(self) -> None:
        if not self.main.current_output.prepared:
            return

        next_buffered_frame = self.current_audio_frame + self.settings.playback_buffer_size

        try:
            frame_future = self.play_buffer_audio.pop()
        except BaseException:
            self.play_pause_button.click()
            return

        if next_buffered_frame < self.current_audio_output.total_frames:
            self.play_buffer_audio.appendleft(
                self.current_audio_output.vs_output.get_frame_async(int(next_buffered_frame))
            )

        self.current_audio_output.render_raw_audio_frame(frame_future.result())
        self.current_audio_frame += 1

    def stop(self) -> None:
        if not self.play_timer.isActive():
            return

        self.play_timer.stop()

        if self.main.toolbars.debug.settings.DEBUG_PLAY_FPS and self.play_start_time is not None:
            self.play_end_time = debug.perf_counter_ns()
            self.play_end_frame = Frame(self.main.current_output.last_showed_frame)
        if self.main.statusbar.label.text() == 'Playing':
            self.main.statusbar.label.setText('Ready')

        for future in self.play_buffer:
            future[1].add_done_callback(_del_future)

        self.play_buffer.clear()
        del self.play_buffer

        gc.collect(generation=2)

        self.current_audio_output = self.audio_outputs_combobox.currentValue()

        if not self.audio_muted and self.current_audio_output is not None:
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
        if self.current_audio_output is None:
            return

        self.current_audio_output.iodevice.reset()

        self.play_timer_audio.stop()

        for future in self.play_buffer_audio:
            future.add_done_callback(_del_future)

        self.play_buffer_audio.clear()

        self.current_audio_frame = Frame(0)
        self.audio_outputs_combobox.setEnabled(True)

    def seek_to_start(self, checked: bool | None = None) -> None:
        self.stop()
        self.main.current_output.last_showed_frame = Frame(0)

    def seek_to_end(self, checked: bool | None = None) -> None:
        self.stop()
        self.main.current_output.last_showed_frame = self.main.current_output.total_frames - 1

    def seek_offset(self, offset: int) -> None:
        new_pos = self.main.current_output.last_showed_frame + offset

        if not 0 <= new_pos < self.main.current_output.total_frames:
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

        self.current_audio_output.iodevice.reset()
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
            self.play(Frame(self.main.current_output.last_showed_frame) + Frame(self.seek_frame_control.value()))
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

    def updateMuteGui(self) -> None:
        if self.volume == 0 or self.audio_muted:
            self.mute_button.setText('🔇')
        elif self.volume <= 33:
            self.mute_button.setText('🔈')
        elif self.volume <= 66:
            self.mute_button.setText('🔉')
        else:
            self.mute_button.setText('🔊')

    def on_mute_clicked(self) -> None:
        if not hasattr(self, 'audio_outputs_combobox'):
            return

        if self.volume == 0 and self.audio_muted:
            self.setVolume(50, True)
        else:
            self.setMute(not self.audio_muted)

    def setMute(self, isMuted: bool) -> None:
        self.audio_muted = isMuted

        if not isMuted:
            if self.play_timer.isActive() and not self.play_timer_audio.isActive():
                self.play_audio()
        elif self.play_timer_audio.isActive():
            self.stop_audio()

        self.updateMuteGui()

    def setVolume(self, newVolume: float, updateGui: bool = False) -> None:
        self.volume = newVolume

        self.setMute(self.volume == 0)

        if newVolume:
            for output in self.audio_outputs:
                output.volume = newVolume / 100.0

        if updateGui:
            qt_silent_call(self.audio_volume_slider.setValue, self.volume)

    def __getstate__(self) -> Mapping[str, Any]:
        return super().__getstate__() | {
            'seek_interval_frame': self.seek_frame_control.value(),
            'current_audio_output_index': self.audio_outputs_combobox.currentIndex()
        }

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        try_load(state, 'seek_interval_frame', Frame, self.seek_frame_control.setValue)
        try_load(state, 'audio_outputs', AudioOutputs, self.rescan_outputs)
        try_load(state, 'current_audio_output_index', int, self.audio_outputs_combobox.setCurrentIndex)
        try_load(state, 'audio_muted', bool, self.setMute)
        try_load(state, 'volume', int, partial(self.setVolume, updateGui=True))
        super().__setstate__(state)
