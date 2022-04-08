from __future__ import annotations

from ...core import AbstractToolbarSettings


class SceningSettings(AbstractToolbarSettings):
    __slots__ = ()

    ALWAYS_SHOW_SCENE_MARKS = False

    def setup_ui(self) -> None:
        super().setup_ui()

    def set_defaults(self) -> None:
        pass
