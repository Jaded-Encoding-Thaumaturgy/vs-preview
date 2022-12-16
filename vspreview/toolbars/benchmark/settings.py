from __future__ import annotations

from typing import Any, Mapping

from PyQt6.QtWidgets import QLabel

from ...core import AbstractToolbarSettings, CheckBox, HBoxLayout, Time, try_load
from ...core.custom import TimeEdit


class BenchmarkSettings(AbstractToolbarSettings):
    __slots__ = (
        'clear_cache_checkbox',
        'refresh_interval_control', 'frame_data_sharing_fix_checkbox',
    )

    def setup_ui(self) -> None:
        super().setup_ui()

        self.clear_cache_checkbox = CheckBox('Clear VS frame caches before each run', self)

        self.frame_data_sharing_fix_checkbox = CheckBox('(Debug) Enable frame data sharing fix', self)

        self.refresh_interval_control = TimeEdit(self)

        self.vlayout.addWidgets([
            self.clear_cache_checkbox,
            self.frame_data_sharing_fix_checkbox
        ])
        self.vlayout.addLayout(
            HBoxLayout([
                QLabel('Refresh interval', self),
                self.refresh_interval_control
            ])
        )

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
        super().__setstate__(state)
