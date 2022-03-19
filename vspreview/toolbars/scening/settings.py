from __future__ import annotations

from typing import Any, Mapping

from PyQt5.QtWidgets import QWidget, QVBoxLayout

from ...utils import set_qobject_names
from ...core import QYAMLObjectSingleton


class SceningSettings(QWidget, QYAMLObjectSingleton):
    yaml_tag = '!SceningSettings'

    __slots__ = ()

    def __init__(self) -> None:
        super().__init__()

        self.setup_ui()
        self.set_defaults()

        set_qobject_names(self)

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setObjectName('SceningSettings.setup_ui.layout')

    def set_defaults(self) -> None:
        pass

    def __getstate__(self) -> Mapping[str, Any]:
        return {}

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        pass
