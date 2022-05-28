from __future__ import annotations

from typing import Any, Mapping

from ...core import AbstractToolbarSettings, CheckBox, try_load


class CompSettings(AbstractToolbarSettings):
    __slots__ = ('delete_cache_checkbox', )

    DEFAULT_COLLECTION_NAME = ''

    def setup_ui(self) -> None:
        super().setup_ui()

        self.delete_cache_checkbox = CheckBox('Delete images cache after upload')

        self.vlayout.addWidget(self.delete_cache_checkbox)

    def set_defaults(self) -> None:
        self.delete_cache_checkbox.setChecked(True)

    @property
    def delete_cache_enabled(self) -> bool:
        return self.delete_cache_checkbox.isChecked()

    def __getstate__(self) -> Mapping[str, Any]:
        return {
            'delete_cache_enabled': self.delete_cache_enabled
        }

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        try_load(state, 'delete_cache_enabled', bool, self.delete_cache_checkbox.setChecked)
        super().__setstate__(state)
