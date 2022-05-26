from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel

from ...core import AbstractToolbarSettings, Frame, HBoxLayout, SpinBox
from ...main.settings import MainSettings


class PlaybackSettings(AbstractToolbarSettings):
    __slots__ = ('buffer_size_spinbox', )

    CHECKERBOARD_ENABLED = True
    CHECKERBOARD_TILE_COLOR_1 = Qt.white
    CHECKERBOARD_TILE_COLOR_2 = Qt.lightGray
    CHECKERBOARD_TILE_SIZE = 8  # px
    FPS_AVERAGING_WINDOW_SIZE = Frame(100)
    FPS_REFRESH_INTERVAL = 150  # ms
    SEEK_STEP = 1

    def setup_ui(self) -> None:
        super().setup_ui()

        self.buffer_size_spinbox = SpinBox(self, 1, MainSettings.get_usable_cpus_count())

        HBoxLayout(self.vlayout, [QLabel('Playback buffer size (frames)'), self.buffer_size_spinbox])

    def set_defaults(self) -> None:
        self.buffer_size_spinbox.setValue(MainSettings.get_usable_cpus_count())

    @property
    def playback_buffer_size(self) -> int:
        return self.buffer_size_spinbox.value()
