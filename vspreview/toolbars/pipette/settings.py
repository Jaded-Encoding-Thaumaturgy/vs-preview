from __future__ import annotations

from PyQt5.QtWidgets import QVBoxLayout

from ...core import AbstractToolbarSettings


class PipetteSettings(AbstractToolbarSettings):
    yaml_tag = '!PipetteSettings'

    __slots__ = ()

    def setup_ui(self) -> None:
        super().setup_ui()

    def set_defaults(self) -> None:
        pass
