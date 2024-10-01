from __future__ import annotations

from typing import Any

from ...core import AbstractToolbarSettings

__all__ = [
    'DebugSettings'
]


class DebugSettings(AbstractToolbarSettings):
    __slots__ = ()

    _add_to_tab = False

    DEBUG_PLAY_FPS = False
    DEBUG_TOOLBAR = False
    DEBUG_TOOLBAR_BUTTONS_PRINT_STATE = False

    def setup_ui(self) -> None:
        super().setup_ui()

    def set_defaults(self) -> None:
        pass

    def __getstate__(self) -> dict[str, Any]:
        return {
            'DEBUG_PLAY_FPS': self.DEBUG_PLAY_FPS,
            'DEBUG_TOOLBAR': self.DEBUG_TOOLBAR,
            'DEBUG_TOOLBAR_BUTTONS_PRINT_STATE': self.DEBUG_TOOLBAR_BUTTONS_PRINT_STATE
        }
