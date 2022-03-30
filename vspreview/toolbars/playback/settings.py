from __future__ import annotations

from PyQt5.QtCore import Qt

from ...utils import get_usable_cpus_count
from ...core import AbstractToolbarSettings, Frame


class PlaybackSettings(AbstractToolbarSettings):
    __slots__ = ()

    CHECKERBOARD_ENABLED = True
    CHECKERBOARD_TILE_COLOR_1 = Qt.white
    CHECKERBOARD_TILE_COLOR_2 = Qt.lightGray
    CHECKERBOARD_TILE_SIZE = 8  # px
    FPS_AVERAGING_WINDOW_SIZE = Frame(100)
    FPS_REFRESH_INTERVAL = 150  # ms
    PLAY_BUFFER_SIZE = Frame(get_usable_cpus_count())
    SEEK_STEP = 1

    def setup_ui(self) -> None:
        super().setup_ui()

    def set_defaults(self) -> None:
        pass
