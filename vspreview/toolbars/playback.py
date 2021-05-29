from __future__ import annotations

from   collections import deque
import logging
from   time        import perf_counter_ns
from   typing      import Any, cast, Deque, Mapping, Optional, Union

from PyQt5 import Qt

from vspreview.core import (
    AbstractMainWindow, AbstractToolbar, Frame, FrameInterval, Time,
    TimeInterval,
)
from vspreview.utils import (
    add_shortcut, debug, qt_silent_call, set_qobject_names,
)
from vspreview.widgets import FrameEdit, TimeEdit


class PlaybackToolbar(AbstractToolbar):
    yaml_tag = '!PlaybackToolbar'

    __slots__ = (
        'play_timer', 'fps_timer', 'fps_history', 'current_fps',
        'seek_n_frames_b_button', 'seek_to_prev_button', 'play_pause_button',
        'seek_to_next_button', 'seek_n_frames_f_button',
        'seek_frame_control', 'seek_time_control',
        'fps_spinbox', 'fps_unlimited_checkbox', 'fps_reset_button',
        'play_start_time', 'play_start_frame', 'play_end_time',
        'play_end_frame', 'play_buffer', 'toggle_button',
    )

    def __init__(self, main: AbstractMainWindow) -> None:
        from concurrent.futures import Future

        super().__init__(main, 'Playback')
        self.setup_ui()

        self.play_buffer: Deque[Future] = deque()
        self.play_timer = Qt.QTimer()
        self.play_timer.setTimerType(Qt.Qt.PreciseTimer)
        self.play_timer.timeout.connect(self._show_next_frame)

        self.fps_history: Deque[int] = deque(
            [], int(self.main.FPS_AVERAGING_WINDOW_SIZE) + 1)
        self.current_fps = 0.0
        self.fps_timer = Qt.QTimer()
        self.fps_timer.setTimerType(Qt.Qt.PreciseTimer)
        self.fps_timer.timeout.connect(
            lambda: self.fps_spinbox.setValue(self.current_fps))

        self.play_start_time: Optional[int] = None
        self.play_start_frame = Frame(0)
        self.play_end_time = 0
        self.play_end_frame = Frame(0)

        self.play_pause_button          .clicked.connect(self.on_play_pause_clicked)
        self.seek_to_prev_button        .clicked.connect(self.seek_to_prev)
        self.seek_to_next_button        .clicked.connect(self.seek_to_next)
        self.seek_n_frames_b_button     .clicked.connect(self.seek_n_frames_b)
        self.seek_n_frames_f_button     .clicked.connect(self.seek_n_frames_f)
        self.seek_to_start_button       .clicked.connect(self.seek_to_start)
        self.seek_to_end_button         .clicked.connect(self.seek_to_end)
        self.seek_frame_control    .valueChanged.connect(self.on_seek_frame_changed)
        self.seek_time_control     .valueChanged.connect(self.on_seek_time_changed)
        self.fps_spinbox           .valueChanged.connect(self.on_fps_changed)
        self.fps_reset_button           .clicked.connect(self.reset_fps)
        self.fps_unlimited_checkbox.stateChanged.connect(self.on_fps_unlimited_changed)

        add_shortcut(              Qt.Qt.Key_Space, self.play_pause_button     .click)
        add_shortcut(              Qt.Qt.Key_Left , self.seek_to_prev_button   .click)
        add_shortcut(              Qt.Qt.Key_Right, self.seek_to_next_button   .click)
        add_shortcut(Qt.Qt.SHIFT + Qt.Qt.Key_Left , self.seek_n_frames_b_button.click)
        add_shortcut(Qt.Qt.SHIFT + Qt.Qt.Key_Right, self.seek_n_frames_f_button.click)
        add_shortcut(              Qt.Qt.Key_Home,  self.seek_to_start_button  .click)
        add_shortcut(              Qt.Qt.Key_End,   self.seek_to_end_button    .click)

        set_qobject_names(self)

    def setup_ui(self) -> None:
        layout = Qt.QHBoxLayout(self)
        layout.setObjectName('PlaybackToolbar.setup_ui.layout')
        layout.setContentsMargins(0, 0, 0, 0)

        self.seek_to_start_button = Qt.QToolButton(self)
        self.seek_to_start_button.setText('⏮')
        self.seek_to_start_button.setToolTip('Seek to First Frame')
        layout.addWidget(self.seek_to_start_button)

        self.seek_n_frames_b_button = Qt.QToolButton(self)
        self.seek_n_frames_b_button.setText('⏪')
        self.seek_n_frames_b_button.setToolTip('Seek N Frames Backwards')
        layout.addWidget(self.seek_n_frames_b_button)

        self.seek_to_prev_button = Qt.QToolButton(self)
        self.seek_to_prev_button.setText('◂')
        self.seek_to_prev_button.setToolTip('Seek 1 Frame Backwards')
        layout.addWidget(self.seek_to_prev_button)

        self.play_pause_button = Qt.QToolButton(self)
        self.play_pause_button.setText('⏯')
        self.play_pause_button.setToolTip('Play/Pause')
        self.play_pause_button.setCheckable(True)
        layout.addWidget(self.play_pause_button)

        self.seek_to_next_button = Qt.QToolButton(self)
        self.seek_to_next_button.setText('▸')
        self.seek_to_next_button.setToolTip('Seek 1 Frame Forward')
        layout.addWidget(self.seek_to_next_button)

        self.seek_n_frames_f_button = Qt.QToolButton(self)
        self.seek_n_frames_f_button.setText('⏩')
        self.seek_n_frames_f_button.setToolTip('Seek N Frames Forward')
        layout.addWidget(self.seek_n_frames_f_button)

        self.seek_to_end_button = Qt.QToolButton(self)
        self.seek_to_end_button.setText('⏭')
        self.seek_to_end_button.setToolTip('Seek to Last Frame')
        layout.addWidget(self.seek_to_end_button)

        self.seek_frame_control = FrameEdit[FrameInterval](self)
        self.seek_frame_control.setMinimum(FrameInterval(1))
        self.seek_frame_control.setToolTip('Seek N Frames Step')
        layout.addWidget(self.seek_frame_control)

        self.seek_time_control = TimeEdit[TimeInterval](self)
        layout.addWidget(self.seek_time_control)

        self.fps_spinbox = Qt.QDoubleSpinBox(self)
        self.fps_spinbox.setRange(0.001, 9999.0)
        self.fps_spinbox.setDecimals(3)
        self.fps_spinbox.setSuffix(' fps')
        layout.addWidget(self.fps_spinbox)

        self.fps_reset_button = Qt.QPushButton(self)
        self.fps_reset_button.setText('Reset FPS')
        layout.addWidget(self.fps_reset_button)

        self.fps_unlimited_checkbox = Qt.QCheckBox(self)
        self.fps_unlimited_checkbox.setText('Unlimited FPS')
        layout.addWidget(self.fps_unlimited_checkbox)

        layout.addStretch()

    def on_current_output_changed(self, index: int, prev_index: int) -> None:
        qt_silent_call(self.seek_frame_control.setMaximum, self.main.current_output.total_frames)
        qt_silent_call(self. seek_time_control.setMaximum, self.main.current_output.total_time)
        qt_silent_call(self. seek_time_control.setMinimum, TimeInterval(FrameInterval(1)))
        qt_silent_call(self.       fps_spinbox.setValue  , self.main.current_output.play_fps)


    def play(self) -> None:
        if self.main.current_frame == self.main.current_output.end_frame:
            return

        if self.main.statusbar.label.text() == 'Ready':
            self.main.statusbar.label.setText('Playing')

        if not self.main.current_output.has_alpha:
            play_buffer_size = int(min(
                self.main.PLAY_BUFFER_SIZE,
                self.main.current_output.end_frame - self.main.current_frame
            ))
            self.play_buffer = deque([], play_buffer_size)
            for i in range(cast(int, self.play_buffer.maxlen)):
                future = self.main.current_output.vs_output.get_frame_async(
                    int(self.main.current_frame + FrameInterval(i)
                        + FrameInterval(1)))
                self.play_buffer.appendleft(future)
        else:
            play_buffer_size = int(min(
                self.main.PLAY_BUFFER_SIZE,
                (self.main.current_output.end_frame - self.main.current_frame) * 2
            ))
            # buffer size needs to be even in case alpha is present
            play_buffer_size -= play_buffer_size % 2
            self.play_buffer = deque([], play_buffer_size)

            for i in range(cast(int, self.play_buffer.maxlen) // 2):
                frame = (self.main.current_frame + FrameInterval(i)
                         + FrameInterval(1))
                future = self.main.current_output.vs_output.get_frame_async(
                    int(frame))
                self.play_buffer.appendleft(future)
                future = self.main.current_output.vs_alpha.get_frame_async(
                    int(frame))
                self.play_buffer.appendleft(future)

        if self.fps_unlimited_checkbox.isChecked() or self.main.DEBUG_PLAY_FPS:
            self.play_timer.start(0)
            if self.main.DEBUG_PLAY_FPS:
                self.play_start_time  = debug.perf_counter_ns()
                self.play_start_frame = self.main.current_frame
            else:
                self.fps_timer.start(self.main.FPS_REFRESH_INTERVAL)
        else:
            self.play_timer.start(
                round(1000 / self.main.current_output.play_fps))

    def _show_next_frame(self) -> None:
        if not self.main.current_output.has_alpha:
            try:
                frame_future = self.play_buffer.pop()
            except IndexError:
                self.play_pause_button.click()
                return

            next_frame_for_buffer = (self.main.current_frame
                                     + self.main.PLAY_BUFFER_SIZE)
            if next_frame_for_buffer <= self.main.current_output.end_frame:
                self.play_buffer.appendleft(
                    self.main.current_output.vs_output.get_frame_async(
                        next_frame_for_buffer))

            self.main.switch_frame(
                self.main.current_frame + FrameInterval(1), render_frame=False)
            image = self.main.current_output.render_raw_videoframe(
                frame_future.result())
        else:
            try:
                frame_future = self.play_buffer.pop()
                alpha_future = self.play_buffer.pop()
            except IndexError:
                self.play_pause_button.click()
                return

            next_frame_for_buffer = (self.main.current_frame
                                     + self.main.PLAY_BUFFER_SIZE // 2)
            if next_frame_for_buffer <= self.main.current_output.end_frame:
                self.play_buffer.appendleft(
                    self.main.current_output.vs_output.get_frame_async(
                        next_frame_for_buffer))
                self.play_buffer.appendleft(
                    self.main.current_output.vs_alpha.get_frame_async(
                        next_frame_for_buffer))

            self.main.switch_frame(
                self.main.current_frame + FrameInterval(1), render_frame=False)
            image = self.main.current_output.render_raw_videoframe(
                frame_future.result(), alpha_future.result())

        self.main.current_output.graphics_scene_item.setImage(image)

        if not self.main.DEBUG_PLAY_FPS:
            self.update_fps_counter()

    def stop(self) -> None:
        self.play_timer.stop()
        if self.main.DEBUG_PLAY_FPS and self.play_start_time is not None:
            self.play_end_time = debug.perf_counter_ns()
            self.play_end_frame = self.main.current_frame
        if self.main.statusbar.label.text() == 'Playing':
            self.main.statusbar.label.setText('Ready')

        for future in self.play_buffer:
            future.add_done_callback(lambda future: future.result())
        self.play_buffer.clear()

        self.fps_history.clear()
        self.fps_timer.stop()

        if self.main.DEBUG_PLAY_FPS and self.play_start_time is not None:
            time_interval  = ((self.play_end_time - self.play_start_time)
                              / 1_000_000_000)
            frame_interval = self.play_end_frame - self.play_start_frame
            logging.debug(
                f'{time_interval:.3f} s, {frame_interval} frames, {int(frame_interval) / time_interval:.3f} fps')
            self.play_start_time = None

    def seek_to_start(self, checked: Optional[bool] = None) -> None:
        self.stop()
        self.main.current_frame = Frame(0)

    def seek_to_end(self, checked: Optional[bool] = None) -> None:
        self.stop()
        self.main.current_frame = self.main.current_output.end_frame

    def seek_to_prev(self, checked: Optional[bool] = None) -> None:
        try:
            new_pos = self.main.current_frame - FrameInterval(1)
        except ValueError:
            return
        self.stop()
        self.main.current_frame = new_pos

    def seek_to_next(self, checked: Optional[bool] = None) -> None:
        new_pos = self.main.current_frame + FrameInterval(1)
        if new_pos > self.main.current_output.end_frame:
            return
        self.stop()
        self.main.current_frame = new_pos

    def seek_n_frames_b(self, checked: Optional[bool] = None) -> None:
        try:
            new_pos = (self.main.current_frame
                       - FrameInterval(self.seek_frame_control.value()))
        except ValueError:
            return
        self.stop()
        self.main.current_frame = new_pos

    def seek_n_frames_f(self, checked: Optional[bool] = None) -> None:
        new_pos = (self.main.current_frame
                   + FrameInterval(self.seek_frame_control.value()))
        if new_pos > self.main.current_output.end_frame:
            return
        self.stop()
        self.main.current_frame = new_pos

    def on_seek_frame_changed(self, frame: FrameInterval) -> None:
        qt_silent_call(self.seek_time_control.setValue, TimeInterval(frame))

    def on_seek_time_changed(self, time: TimeInterval) -> None:
        qt_silent_call(self.seek_frame_control.setValue, FrameInterval(time))

    def on_play_pause_clicked(self, checked: bool) -> None:
        if checked:
            self.play()
        else:
            self.stop()

    def on_fps_changed(self, new_fps: float) -> None:
        if not self.fps_spinbox.isEnabled():
            return

        self.main.current_output.play_fps = new_fps
        if self.play_timer.isActive():
            self.stop()
            self.play()

    def reset_fps(self, checked: Optional[bool] = None) -> None:
        self.fps_spinbox.setValue(self.main.current_output.fps_num
                                  / self.main.current_output.fps_den)

    def on_fps_unlimited_changed(self, state: int) -> None:
        if state == Qt.Qt.Checked:
            self.fps_spinbox.setEnabled(False)
            self.fps_reset_button.setEnabled(False)
        if state == Qt.Qt.Unchecked:
            self.fps_spinbox.setEnabled(True)
            self.fps_reset_button.setEnabled(True)
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

        self.current_fps = (1_000_000_000
                            / (elapsed_total / len(self.fps_history)))

    def __getstate__(self) -> Mapping[str, Any]:
        state = {
            'seek_interval_frame': self.seek_frame_control.value()
        }
        state.update(super().__getstate__())
        return state

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        try:
            seek_interval_frame = state['seek_interval_frame']
            if not isinstance(seek_interval_frame, FrameInterval):
                raise TypeError
            self.seek_frame_control.setValue(seek_interval_frame)
        except (KeyError, TypeError):
            logging.warning(
                'Storage loading: PlaybackToolbar: failed to parse seek_interval_frame')

        super().__setstate__(state)
