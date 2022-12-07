from __future__ import annotations

from ...core import AbstractToolbarSettings


class DebugSettings(AbstractToolbarSettings):
    __slots__ = ()

    DEBUG_PLAY_FPS = False
    DEBUG_TOOLBAR = False
    DEBUG_TOOLBAR_BUTTONS_PRINT_STATE = False

    def setup_ui(self) -> None:
        super().setup_ui()

    def set_defaults(self) -> None:
        pass
