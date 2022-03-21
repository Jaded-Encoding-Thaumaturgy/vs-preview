from __future__ import annotations

from enum import Enum
from typing import List


class PictureType(bytes, Enum):
    UNSET = b'None'
    I = b'I'  # noqa
    P = b'P'
    B = b'B'

    def __str__(self) -> str:
        if self == PictureType.UNSET:
            return 'None'

        return self.decode('utf-8') + ' Frames'

    @classmethod
    def list(cls) -> List[PictureType]:
        return list(map(lambda c: PictureType(c.value), cls))
