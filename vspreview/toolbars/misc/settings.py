from __future__ import annotations

from ...core import AbstractToolbarSettings


class MiscSettings(AbstractToolbarSettings):
    __slots__ = ()

    SAVE_TEMPLATE = '{script_name}_{frame}'

    def setup_ui(self) -> None:
        super().setup_ui()

    def set_defaults(self) -> None:
        pass
