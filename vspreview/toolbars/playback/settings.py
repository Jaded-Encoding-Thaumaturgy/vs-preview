from __future__ import annotations

from ...core import AbstractToolbarSettings


class PlaybackSettings(AbstractToolbarSettings):
    __slots__ = ()

    def setup_ui(self) -> None:
        super().setup_ui()

    def set_defaults(self) -> None:
        pass
