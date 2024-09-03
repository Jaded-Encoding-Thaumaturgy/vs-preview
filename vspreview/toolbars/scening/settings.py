from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import QLabel

from ...core import AbstractToolbarSettings, CheckBox, HBoxLayout, LineEdit, try_load

__all__ = [
    'SceningSettings'
]


class SceningSettings(AbstractToolbarSettings):
    __slots__ = (
        'export_template_lineedit', 'always_show_scene_marks_checkbox',
        'export_multiline_checkbox'
    )

    def setup_ui(self) -> None:
        super().setup_ui()

        self.export_template_lineedit = LineEdit('Export Template')

        self.always_show_scene_marks_checkbox = CheckBox('Always show scene marks')

        self.export_multiline_checkbox = CheckBox('Export as multiple lines')

        HBoxLayout(self.vlayout, [QLabel('Default Export Template'), self.export_template_lineedit])

        HBoxLayout(self.vlayout, self.always_show_scene_marks_checkbox)

        HBoxLayout(self.vlayout, self.export_multiline_checkbox)

    def set_defaults(self) -> None:
        self.export_template_lineedit.setText(r'({start},{end}),')
        self.always_show_scene_marks_checkbox.setChecked(False)
        self.export_multiline_checkbox.setChecked(True)

    @property
    def default_export_template(self) -> str:
        return self.export_template_lineedit.text()

    @property
    def always_show_scene_marks(self) -> bool:
        return self.always_show_scene_marks_checkbox.isChecked()

    @property
    def export_multiline(self) -> bool:
        return self.export_multiline_checkbox.isChecked()

    def __getstate__(self) -> dict[str, Any]:
        return super().__getstate__() | {
            'default_export_template': self.default_export_template,
            'always_show_scene_marks': self.always_show_scene_marks,
            'export_multiline': self.export_multiline
        }

    def __setstate__(self, state: dict[str, Any]) -> None:
        try_load(state, 'default_export_template', str, self.export_template_lineedit.setText)
        try_load(state, 'always_show_scene_marks', bool, self.always_show_scene_marks_checkbox.setChecked)
        try_load(state, 'export_multiline', bool, self.export_multiline_checkbox.setChecked)
