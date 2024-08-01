from __future__ import annotations

from ...core import AbstractToolbarSettings

__all__ = [
    'MiscSettings'
]


class MiscSettings(AbstractToolbarSettings):
    __slots__ = ()

    _add_to_tab = False

    SAVE_TEMPLATE = '{script_name}_{frame}'

    def setup_ui(self) -> None:
        super().setup_ui()

    def set_defaults(self) -> None:
        pass
