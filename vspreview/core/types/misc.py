from __future__ import annotations

from enum import Enum


class PictureType(bytes, Enum):
    ALL = b'All'
    Intra = b'I'
    Predicted = b'P'
    Bipredictive = b'B'

    def __str__(self) -> str:
        if self == PictureType.ALL:
            return 'All'

        return self.decode('utf-8') + ' Frames'

    @classmethod
    def list(cls) -> list[PictureType]:
        return [PictureType(e.value) for e in cls]
