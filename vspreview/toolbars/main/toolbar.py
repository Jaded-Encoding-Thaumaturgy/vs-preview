from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PyQt6.QtWidgets import QComboBox

from ...core import (
    AbstractToolbar, CheckBox, ComboBox, Frame, FrameEdit, PushButton, Time, TimeEdit, VideoOutput,
    try_load
)
from ...models import VideoOutputs
from ...utils import qt_silent_call

if TYPE_CHECKING:
    from ...main import MainSettings, MainWindow


__all__ = [
    'MainToolbar'
]


class MainToolbar(AbstractToolbar):
    _no_visibility_choice = True
    storable_attrs = ('outputs', )

    __slots__ = (
        *storable_attrs,
        'outputs_combobox', 'frame_control', 'copy_frame_button',
        'time_control', 'copy_timestamp_button',
        'sync_outputs_checkbox',
        'switch_timeline_mode_button', 'settings_button'
    )

    outputs: VideoOutputs | None

    settings: MainSettings

    def __init__(self, main_window: MainWindow) -> None:
        super().__init__(main_window, main_window.settings)
        self.setup_ui()

        self.outputs = None

        self.set_qobject_names()

    def setup_ui(self) -> None:
        super().setup_ui()

        self.setVisible(True)

        self.outputs_combobox = ComboBox[VideoOutput](
            self, editable=True, insertPolicy=QComboBox.InsertPolicy.InsertAtCurrent,
            duplicatesEnabled=True, sizeAdjustPolicy=QComboBox.SizeAdjustPolicy.AdjustToContents
        )
        self.outputs_combobox.currentIndexChanged.connect(self.main.switch_output)
        self.outputs_combobox.view().setMinimumWidth(
            self.outputs_combobox.minimumSizeHint().width()
        )

        self.frame_control = FrameEdit(self, valueChanged=self.main.switch_frame)
        if not self.settings.INSTANT_FRAME_UPDATE:
            self.frame_control.setKeyboardTracking(False)

        self.copy_frame_button = PushButton('⎘', self, clicked=self.on_copy_frame_button_clicked)

        self.time_control = TimeEdit(self, valueChanged=self.main.switch_frame)

        self.copy_timestamp_button = PushButton('⎘', self, clicked=self.on_copy_timestamp_button_clicked)

        self.sync_outputs_checkbox = CheckBox(
            'Sync Outputs', self, checked=self.settings.SYNC_OUTPUTS, clicked=self.on_sync_outputs_clicked
        )

        self.switch_timeline_mode_button = PushButton(
            'Switch Timeline Mode', self, clicked=self.on_switch_timeline_mode_clicked
        )

        self.settings_button = PushButton('Settings', self, clicked=self.main.app_settings.show)

        self.hlayout.addWidgets([
            self.outputs_combobox,
            self.frame_control, self.copy_frame_button,
            self.time_control, self.copy_timestamp_button,
            self.sync_outputs_checkbox,
            self.get_separator(),
            self.main.graphics_view.controls,
            self.switch_timeline_mode_button,
            self.settings_button
        ])

        self.hlayout.addStretch()

    def on_sync_outputs_clicked(self, checked: bool | None = None, force_frame: Frame | None = None) -> None:
        if not self.outputs:
            return

        if checked:
            from ...main.timeline import Timeline

            if not force_frame:
                force_frame = self.main.current_output.last_showed_frame

            if self.main.timeline.mode == Timeline.Mode.TIME:
                for output in self.outputs:
                    output.last_showed_frame = output.to_frame(
                        self.main.current_output.to_time(force_frame)
                    )
            else:
                for output in self.outputs:
                    output.last_showed_frame = force_frame

    def on_current_frame_changed(self, frame: Frame) -> None:
        qt_silent_call(self.frame_control.setValue, frame)
        qt_silent_call(self.time_control.setValue, Time(frame))

        if self.outputs and len(self.outputs) > 1 and self.sync_outputs_checkbox.isChecked():
            self.on_sync_outputs_clicked(True, force_frame=frame)

    def on_current_output_changed(self, index: int, prev_index: int) -> None:
        qt_silent_call(self.outputs_combobox.setCurrentIndex, index)
        qt_silent_call(self.frame_control.setMaximum, self.main.current_output.total_frames - 1)
        qt_silent_call(self.time_control.setMaximum, self.main.current_output.total_time)

    def rescan_outputs(self, outputs: VideoOutputs | None = None) -> None:
        self.outputs = outputs if isinstance(outputs, VideoOutputs) else VideoOutputs(self.main)
        self.main.init_outputs()
        self.outputs_combobox.setModel(self.outputs)

    def on_copy_frame_button_clicked(self, checked: bool | None = None) -> None:
        self.main.clipboard.setText(str(self.main.current_output.last_showed_frame))
        self.main.show_message('Current frame number copied to clipboard')

    def on_copy_timestamp_button_clicked(self, checked: bool | None = None) -> None:
        self.main.clipboard.setText(self.time_control.text())
        self.main.show_message('Current timestamp copied to clipboard')

    def on_switch_timeline_mode_clicked(self, checked: bool | None = None) -> None:
        if self.main.timeline.mode == self.main.timeline.Mode.TIME:
            self.main.timeline.mode = self.main.timeline.Mode.FRAME
        elif self.main.timeline.mode == self.main.timeline.Mode.FRAME:
            self.main.timeline.mode = self.main.timeline.Mode.TIME

    def __getstate__(self) -> dict[str, Any]:
        return super().__getstate__() | {
            'current_output_index': self.outputs_combobox.currentIndex(),
            'sync_outputs': self.sync_outputs_checkbox.isChecked()
        }

    def __setstate__(self, state: dict[str, Any]) -> None:
        try_load(state, 'outputs', VideoOutputs, self.rescan_outputs)
        try_load(state, 'current_output_index', int, self.main.switch_output)
        try_load(state, 'sync_outputs', bool, self.sync_outputs_checkbox.setChecked)
