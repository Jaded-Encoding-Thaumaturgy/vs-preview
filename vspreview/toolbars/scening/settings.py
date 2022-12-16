from __future__ import annotations

from PyQt6.QtWidgets import QLabel

from ...core import AbstractToolbarSettings, CheckBox, HBoxLayout, LineEdit


class SceningSettings(AbstractToolbarSettings):
    __slots__ = ('export_template_lineedit', 'always_show_scene_marks_checkbox')

    def setup_ui(self) -> None:
        super().setup_ui()

        self.export_template_lineedit = LineEdit(placeholderText='Export Template')

        self.always_show_scene_marks_checkbox = CheckBox('Always show scene marks')

        HBoxLayout(self.vlayout, [QLabel('Default Export Template'), self.export_template_lineedit])

        HBoxLayout(self.vlayout, self.always_show_scene_marks_checkbox)

    def set_defaults(self) -> None:
        self.export_template_lineedit.setText(r'({start},{end}),')
        self.always_show_scene_marks_checkbox.setChecked(False)

    @property
    def default_export_template(self) -> str:
        return self.export_template_lineedit.text()

    @property
    def always_show_scene_marks(self) -> bool:
        return self.always_show_scene_marks_checkbox.isChecked()
