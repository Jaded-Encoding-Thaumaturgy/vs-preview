from __future__ import annotations

from typing import Mapping, Any

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QHBoxLayout, QPushButton, QComboBox, QCheckBox

from ...models import VideoOutputs, ZoomLevels
from ...widgets import ComboBox, TimeEdit, FrameEdit
from ...utils import add_shortcut, qt_silent_call, set_qobject_names
from ...core import AbstractMainWindow, AbstractToolbar, Time, Frame, VideoOutput, try_load


class MainToolbar(AbstractToolbar):
    _storable_attrs = ('settings',)

    __slots__ = (
        *_storable_attrs, 'outputs', 'zoom_levels',
        'outputs_combobox', 'frame_control', 'copy_frame_button',
        'time_control', 'copy_timestamp_button', 'zoom_combobox',
        'switch_timeline_mode_button', 'settings_button'
    )

    def __init__(self, main_window: AbstractMainWindow) -> None:
        super().__init__(main_window, main_window.settings)
        self.setup_ui()

        self.outputs = VideoOutputs()

        self.outputs_combobox.setModel(self.outputs)
        self.zoom_levels = ZoomLevels([
            0.25, 0.5, 0.68, 0.75, 0.85, 1.0, 1.5, 2.0,
            4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 20.0, 32.0
        ])
        self.zoom_combobox.setModel(self.zoom_levels)
        self.zoom_combobox.setCurrentIndex(3)

        self.sync_outputs_checkbox.clicked.connect(self.on_sync_outputs_clicked)
        self.outputs_combobox.currentIndexChanged.connect(self.main.switch_output)
        self.frame_control.valueChanged.connect(self.main.switch_frame)
        self.time_control.valueChanged.connect(self.main.switch_frame)
        self.copy_frame_button.clicked.connect(self.on_copy_frame_button_clicked)
        self.copy_timestamp_button.clicked.connect(self.on_copy_timestamp_button_clicked)
        self.zoom_combobox.currentTextChanged.connect(self.on_zoom_changed)
        self.switch_timeline_mode_button.clicked.connect(self.on_switch_timeline_mode_clicked)
        self.settings_button.clicked.connect(self.main.app_settings.show)

        add_shortcut(Qt.Key_1, lambda: self.main.switch_output(0))
        add_shortcut(Qt.Key_2, lambda: self.main.switch_output(1))
        add_shortcut(Qt.Key_3, lambda: self.main.switch_output(2))
        add_shortcut(Qt.Key_4, lambda: self.main.switch_output(3))
        add_shortcut(Qt.Key_5, lambda: self.main.switch_output(4))
        add_shortcut(Qt.Key_6, lambda: self.main.switch_output(5))
        add_shortcut(Qt.Key_7, lambda: self.main.switch_output(6))
        add_shortcut(Qt.Key_8, lambda: self.main.switch_output(7))
        add_shortcut(Qt.Key_9, lambda: self.main.switch_output(8))
        add_shortcut(Qt.Key_0, lambda: self.main.switch_output(9))
        add_shortcut(Qt.Key_S, self.sync_outputs_checkbox.click)
        add_shortcut(
            Qt.CTRL + Qt.Key_Tab,
            lambda: self.main.switch_output(self.outputs_combobox.currentIndex() + 1)
        )
        add_shortcut(
            Qt.CTRL + Qt.SHIFT + Qt.Key_Tab,
            lambda: self.main.switch_output(self.outputs_combobox.currentIndex() - 1)
        )
        add_shortcut(Qt.Key_V, self.on_copy_frame_button_clicked)

        set_qobject_names(self)

    def setup_ui(self) -> None:
        self.setVisible(True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.outputs_combobox = ComboBox[VideoOutput](self)
        self.outputs_combobox.setEditable(True)
        self.outputs_combobox.setInsertPolicy(QComboBox.InsertAtCurrent)
        self.outputs_combobox.setDuplicatesEnabled(True)
        self.outputs_combobox.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.outputs_combobox.view().setMinimumWidth(
            self.outputs_combobox.minimumSizeHint().width()
        )
        layout.addWidget(self.outputs_combobox)

        self.frame_control = FrameEdit(self)
        if not self.main.INSTANT_FRAME_UPDATE:
            self.frame_control.setKeyboardTracking(False)
        layout.addWidget(self.frame_control)

        self.copy_frame_button = QPushButton(self)
        self.copy_frame_button.setText('⎘')
        layout.addWidget(self.copy_frame_button)

        self.time_control = TimeEdit(self)
        layout.addWidget(self.time_control)

        self.copy_timestamp_button = QPushButton(self)
        self.copy_timestamp_button.setText('⎘')
        layout.addWidget(self.copy_timestamp_button)

        self.sync_outputs_checkbox = QCheckBox(self)
        self.sync_outputs_checkbox.setText('Sync Outputs')
        self.sync_outputs_checkbox.setChecked(self.main.SYNC_OUTPUTS)
        layout.addWidget(self.sync_outputs_checkbox)

        self.zoom_combobox = ComboBox[float](self)
        self.zoom_combobox.setMinimumContentsLength(4)
        layout.addWidget(self.zoom_combobox)

        self.switch_timeline_mode_button = QPushButton(self)
        self.switch_timeline_mode_button.setText('Switch Timeline Mode')
        layout.addWidget(self.switch_timeline_mode_button)

        self.settings_button = QPushButton(self)
        self.settings_button.setText('Settings')
        layout.addWidget(self.settings_button)

        layout.addStretch()

        self.toggle_button.setVisible(False)

    def on_sync_outputs_clicked(self, checked: bool | None = None, force_frame: Frame | None = None) -> None:
        if checked:
            if not force_frame:
                force_frame = self.main.current_frame
            for output in self.main.outputs:
                output.frame_to_show = force_frame

    def on_current_frame_changed(self, frame: Frame) -> None:
        qt_silent_call(self.frame_control.setValue, frame)
        qt_silent_call(self.time_control.setValue, Time(frame))

        if self.sync_outputs_checkbox.isChecked():
            self.on_sync_outputs_clicked(True, force_frame=frame)

    def on_current_output_changed(self, index: int, prev_index: int) -> None:
        qt_silent_call(self.outputs_combobox.setCurrentIndex, index)
        qt_silent_call(self.frame_control.setMaximum, self.main.current_output.end_frame)
        qt_silent_call(self.time_control.setMaximum, self.main.current_output.end_time)

    def rescan_outputs(self, outputs: VideoOutputs | None = None) -> None:
        self.outputs = outputs or VideoOutputs()
        self.main.init_outputs()
        self.outputs_combobox.setModel(self.outputs)

    def on_copy_frame_button_clicked(self, checked: bool | None = None) -> None:
        self.main.clipboard.setText(str(self.main.current_frame))
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
        if state == Qt.Checked:
            for output in self.main.outputs:
                output.frame_to_show = self.main.current_frame
        if state == Qt.Unchecked:
            for output in self.main.outputs:
                output.frame_to_show = None

    def on_zoom_changed(self, text: str | None = None) -> None:
        self.main.graphics_view.setZoom(self.zoom_combobox.currentData())

    def __getstate__(self) -> Mapping[str, Any]:
        return {
            attr_name: getattr(self, attr_name)
            for attr_name in self._storable_attrs
        } | {
            'current_output_index': self.outputs_combobox.currentIndex(),
            'outputs': self.outputs,
            'sync_outputs': self.sync_outputs_checkbox.isChecked()
        }

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        try_load(state, 'outputs', VideoOutputs, self.rescan_outputs)
        try_load(state, 'current_output_index', int, self.main.switch_output)
        try_load(state, 'sync_outputs', bool, self.sync_outputs_checkbox.setChecked)
