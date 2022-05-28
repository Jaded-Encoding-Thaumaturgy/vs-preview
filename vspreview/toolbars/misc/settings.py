from __future__ import annotations

from ...core import AbstractToolbarSettings


class MiscSettings(AbstractToolbarSettings):
    __slots__ = ()

    SAVE_TEMPLATE = '{script_name}_{frame}'
    STORAGE_BACKUPS_COUNT = 2

    def setup_ui(self) -> None:
        super().setup_ui()

    def set_defaults(self) -> None:
        pass
