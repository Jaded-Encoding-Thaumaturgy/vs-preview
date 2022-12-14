from __future__ import annotations

from functools import partial
from typing import Any, Mapping

from PyQt6.QtCore import Qt, QKeyCombination
from PyQt6.QtWidgets import QComboBox

from ...core import AbstractMainWindow, AbstractToolbar, CheckBox, Frame, PushButton, Time, VideoOutput, try_load
from ...core.custom import ComboBox, FrameEdit, TimeEdit
from ...models import GeneralModel, VideoOutputs
from ...utils import qt_silent_call
from .dialog import FramePropsDialog


class MainToolbar(AbstractToolbar):
    _no_visibility_choice = True
    storable_attrs = ('outputs', )

    __slots__ = (
        *storable_attrs, 'frame_props_dialog',
        'outputs_combobox', 'frame_control', 'copy_frame_button',
        'time_control', 'copy_timestamp_button', 'zoom_combobox',
        'switch_timeline_mode_button', 'settings_button'
    )

    def __init__(self, main_window: AbstractMainWindow) -> None:
        super().__init__(main_window, main_window.settings)
        self.setup_ui()

        self.outputs: VideoOutputs | None = None

        self.zoom_combobox.setModel(GeneralModel[float](self.settings.zoom_levels))  # type: ignore
        self.zoom_combobox.setCurrentIndex(self.settings.zoom_default_index)

        self.add_shortcuts()

        self.set_qobject_names()

    def setup_ui(self) -> None:
        super().setup_ui()

        self.setVisible(True)

        self.frame_props_dialog = FramePropsDialog(self.main)

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

        self.auto_fit_button = CheckBox('Auto-fit', self, clicked=self.auto_fit_button_clicked)

        self.zoom_combobox = ComboBox[float](self, minimumContentsLength=4)
        self.zoom_combobox.currentTextChanged.connect(self.on_zoom_changed)

        self.switch_timeline_mode_button = PushButton(
            'Switch Timeline Mode', self, clicked=self.on_switch_timeline_mode_clicked
        )

        self.frame_props_tab_button = PushButton(
            'Frame Props', self, clicked=lambda: self.frame_props_dialog.showDialog(self.main.current_output.props)
        )

        self.settings_button = PushButton('Settings', self, clicked=self.main.app_settings.show)

        self.hlayout.addWidgets([
            self.outputs_combobox,
            self.frame_control, self.copy_frame_button,
            self.time_control, self.copy_timestamp_button,
            self.sync_outputs_checkbox,
            self.get_separator(),
            self.auto_fit_button, self.zoom_combobox,
            self.switch_timeline_mode_button,
            self.frame_props_tab_button,
            self.settings_button
        ])

        self.hlayout.addStretch()

    def add_shortcuts(self) -> None:
        for i, key in enumerate(self.num_keys):
            self.add_shortcut(key, partial(self.main.switch_output, i))
            self.add_shortcut(
                QKeyCombination(Qt.Modifier.CTRL, key).toCombined(), partial(self.main.switch_output, -(i + 1))
            )

        self.add_shortcut(Qt.Key.Key_S, self.sync_outputs_checkbox.click)
        self.add_shortcut(
            QKeyCombination(Qt.Modifier.CTRL, Qt.Key.Key_Tab).toCombined(),
            lambda: self.main.switch_output(self.outputs_combobox.currentIndex() + 1)
        )
        self.add_shortcut(
            QKeyCombination(Qt.Modifier.CTRL | Qt.Modifier.SHIFT, Qt.Key.Key_Tab).toCombined(),
            lambda: self.main.switch_output(self.outputs_combobox.currentIndex() - 1)
        )
        self.add_shortcut(Qt.Key.Key_V, self.on_copy_frame_button_clicked)

    def on_sync_outputs_clicked(self, checked: bool | None = None, force_frame: Frame | None = None) -> None:
        if not self.outputs:
            return

        if checked:
            if not force_frame:
                force_frame = self.main.current_output.last_showed_frame

            for output in self.main.outputs:
                output.last_showed_frame = output.to_frame(
                    self.main.current_output.to_time(force_frame)
                )

    def auto_fit_button_clicked(self, checked: bool) -> None:
        self.zoom_combobox.setEnabled(not checked)
        self.main.graphics_view.autofit = checked
        if checked:
            self.main.graphics_view.setZoom(None)
        else:
            self.main.graphics_view.setZoom(self.zoom_combobox.currentData())

    def on_current_frame_changed(self, frame: Frame) -> None:
        qt_silent_call(self.frame_control.setValue, frame)
        qt_silent_call(self.time_control.setValue, Time(frame))

        if len(self.outputs) > 1 and self.sync_outputs_checkbox.isChecked():
            self.on_sync_outputs_clicked(True, force_frame=frame)

        if not self.frame_props_dialog.isHidden():
            self.frame_props_dialog.update_frame_props(self.main.current_output.props)

    def on_current_output_changed(self, index: int, prev_index: int) -> None:
        qt_silent_call(self.outputs_combobox.setCurrentIndex, index)
        qt_silent_call(self.frame_control.setMaximum, self.main.current_output.total_frames - 1)
        qt_silent_call(self.time_control.setMaximum, self.main.current_output.total_time - Frame(1))

        if self.main.graphics_view.autofit:
            self.main.graphics_view.setZoom(None)

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

    def on_sync_outputs_changed(self, state: Qt.CheckState) -> None:
        if not self.outputs:
            return

        if state == Qt.Checked:
            for output in self.outputs:
                output.last_showed_frame = self.main.current_output.last_showed_frame
        if state == Qt.Unchecked:
            for output in self.outputs:
                output.last_showed_frame = None

    def on_zoom_changed(self, text: str | None = None) -> None:
        self.main.graphics_view.setZoom(self.zoom_combobox.currentData())

    def __getstate__(self) -> Mapping[str, Any]:
        return super().__getstate__() | {
            'current_output_index': self.outputs_combobox.currentIndex(),
            'current_zoom_index': self.zoom_combobox.currentIndex(),
            'sync_outputs': self.sync_outputs_checkbox.isChecked()
        }

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        try_load(state, 'outputs', VideoOutputs, self.rescan_outputs)
        try_load(state, 'current_zoom_index', int, self.zoom_combobox.setCurrentIndex)
        try_load(state, 'current_output_index', int, self.main.switch_output)
        try_load(state, 'sync_outputs', bool, self.sync_outputs_checkbox.setChecked)
