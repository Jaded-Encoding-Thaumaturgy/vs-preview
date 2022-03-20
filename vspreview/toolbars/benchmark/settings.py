from __future__ import annotations

from typing import Any, Mapping

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QLabel

from ...widgets import TimeEdit
from ...utils import set_qobject_names
from ...core import Time, QYAMLObjectSingleton, try_load


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
        refresh_interval_layout.setObjectName('BenchmarkSettings.setup_ui.refresh_interval_layout')
        layout.addLayout(refresh_interval_layout)

        self.refresh_interval_label = QLabel(self)
        self.refresh_interval_label.setText('Refresh interval')
        refresh_interval_layout.addWidget(self.refresh_interval_label)

        self.refresh_interval_control = TimeEdit(self)
        refresh_interval_layout.addWidget(self.refresh_interval_control)

        self.frame_data_sharing_fix_checkbox = QCheckBox(self)
        self.frame_data_sharing_fix_checkbox.setText('(Debug) Enable frame data sharing fix')
        layout.addWidget(self.frame_data_sharing_fix_checkbox)

    def set_defaults(self) -> None:
        self.clear_cache_checkbox.setChecked(False)
        self.refresh_interval_control.setValue(Time(milliseconds=150))
        self.frame_data_sharing_fix_checkbox.setChecked(True)

    @property
    def clear_cache_enabled(self) -> bool:
        return self.clear_cache_checkbox.isChecked()

    @property
    def refresh_interval(self) -> Time:
        return self.refresh_interval_control.value()

    @property
    def frame_data_sharing_fix_enabled(self) -> bool:
        return self.frame_data_sharing_fix_checkbox.isChecked()

    def __getstate__(self) -> Mapping[str, Any]:
        return {
            'clear_cache_enabled': self.clear_cache_enabled,
            'refresh_interval': self.refresh_interval,
            'frame_data_sharing_fix_enabled': self.frame_data_sharing_fix_enabled,
        }

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        try_load(state, 'clear_cache_enabled', bool, self.clear_cache_checkbox.setChecked)
        try_load(state, 'refresh_interval', Time, self.refresh_interval_control.setValue)
        try_load(state, 'frame_data_sharing_fix_enabled', bool, self.frame_data_sharing_fix_checkbox.setChecked)