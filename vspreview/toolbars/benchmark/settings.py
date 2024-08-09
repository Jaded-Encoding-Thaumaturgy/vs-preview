from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import QLabel

from ...core import AbstractToolbarSettings, CheckBox, HBoxLayout, SpinBox, Time, TimeEdit, try_load

__all__ = [
    'BenchmarkSettings'
]


class BenchmarkSettings(AbstractToolbarSettings):
    __slots__ = (
        'clear_cache_checkbox',
        'refresh_interval_control', 'frame_data_sharing_fix_checkbox',
    )

    def setup_ui(self) -> None:
        from ...main import MainSettings

        super().setup_ui()

        self.clear_cache_checkbox = CheckBox('Clear VS frame caches before each run', self)

        self.frame_data_sharing_fix_checkbox = CheckBox('(Debug) Enable frame data sharing fix', self)

        self.refresh_interval_control = TimeEdit(self)

        self.default_usable_cpus_spinbox = SpinBox(self, 1, MainSettings.get_usable_cpus_count())

        self.vlayout.addWidgets([
            self.clear_cache_checkbox,
            self.frame_data_sharing_fix_checkbox
        ])
        self.vlayout.addLayout(
            HBoxLayout([
                QLabel('Refresh interval'),
                self.refresh_interval_control
            ])
        )
        self.vlayout.addLayout(
            HBoxLayout([
                QLabel('Default usable CPUs count'),
                self.default_usable_cpus_spinbox
            ])
        )

    def set_defaults(self) -> None:
        from ...main import MainSettings

        self.clear_cache_checkbox.setChecked(False)
        self.refresh_interval_control.setValue(Time(milliseconds=150))
        self.frame_data_sharing_fix_checkbox.setChecked(True)
        self.default_usable_cpus_spinbox.setValue(max(1, MainSettings.get_usable_cpus_count() // 2))

    @property
    def clear_cache_enabled(self) -> bool:
        return self.clear_cache_checkbox.isChecked()

    @property
    def refresh_interval(self) -> Time:
        return self.refresh_interval_control.value()

    @property
    def frame_data_sharing_fix_enabled(self) -> bool:
        return self.frame_data_sharing_fix_checkbox.isChecked()

    @property
    def default_usable_cpus_count(self) -> int:
        return self.default_usable_cpus_spinbox.value()

    def __getstate__(self) -> dict[str, Any]:
        return {
            'clear_cache_enabled': self.clear_cache_enabled,
            'refresh_interval': self.refresh_interval,
            'frame_data_sharing_fix_enabled': self.frame_data_sharing_fix_enabled,
        }

    def __setstate__(self, state: dict[str, Any]) -> None:
        try_load(state, 'clear_cache_enabled', bool, self.clear_cache_checkbox.setChecked)
        try_load(state, 'refresh_interval', Time, self.refresh_interval_control.setValue)
        try_load(state, 'frame_data_sharing_fix_enabled', bool, self.frame_data_sharing_fix_checkbox.setChecked)
