from __future__ import annotations

from typing import Any, Mapping

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QLabel
from vstools import DitherType

from ...core import AbstractToolbarSettings, Frame, HBoxLayout, SpinBox, try_load
from ...core.custom import ComboBox
from ...main.settings import MainSettings
from ...models import GeneralModel


class PlaybackSettings(AbstractToolbarSettings):
    __slots__ = ('buffer_size_spinbox', 'dither_type_combobox')

    CHECKERBOARD_ENABLED = True
    CHECKERBOARD_TILE_COLOR_1 = Qt.GlobalColor.white
    CHECKERBOARD_TILE_COLOR_2 = Qt.GlobalColor.lightGray
    CHECKERBOARD_TILE_SIZE = 8  # px
    FPS_AVERAGING_WINDOW_SIZE = Frame(100)
    FPS_REFRESH_INTERVAL = 150  # ms
    SEEK_STEP = 1

    def setup_ui(self) -> None:
        from ...core import main_window
        super().setup_ui()

        self.buffer_size_spinbox = SpinBox(self, 1, MainSettings.get_usable_cpus_count())
        self.dither_type_combobox = ComboBox[str](
            self, model=GeneralModel[str]([x.value for x in DitherType][1:]),
            currentIndex=3, sizeAdjustPolicy=QComboBox.SizeAdjustPolicy.AdjustToContents
        )

        self.dither_type_combobox.currentTextChanged.connect(lambda _: main_window().refresh_video_outputs())

        HBoxLayout(self.vlayout, [QLabel('Playback buffer size (frames)'), self.buffer_size_spinbox])
        HBoxLayout(self.vlayout, [QLabel('Dithering Type'), self.dither_type_combobox])

    def set_defaults(self) -> None:
        self.buffer_size_spinbox.setValue(MainSettings.get_usable_cpus_count())
        self.dither_type_combobox.setCurrentValue(DitherType.ERROR_DIFFUSION)

    @property
    def playback_buffer_size(self) -> int:
        return self.buffer_size_spinbox.value()

    @property
    def dither_type(self) -> str:
        return self.dither_type_combobox.currentValue()

    def __getstate__(self) -> Mapping[str, Any]:
        return super().__getstate__() | {
            'playback_buffer_size': self.playback_buffer_size, 'dither_type': self.dither_type
        }

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        try_load(state, 'playback_buffer_size', int, self.buffer_size_spinbox.setValue)
        try_load(state, 'dither_type', str, self.dither_type_combobox.setCurrentValue)
