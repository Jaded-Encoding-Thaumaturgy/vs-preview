from __future__ import annotations

import vapoursynth as vs
from yaml import YAMLObject
from typing import Any, Mapping


core = vs.core


class YAMLObjectWrapper(YAMLObject):
    value: Any

    def __int__(self) -> int:
        return int(self.value)

    def __float__(self) -> float:
        return float(self.value)

    def __index__(self) -> int:
        return int(self)

    def __str__(self) -> str:
        return str(self.value)

    def __eq__(self, other: object) -> bool:
        if other is None:
            return False
        if not isinstance(other, YAMLObjectWrapper):
            other = self.__class__(other)
        return self.value == other.value

    def __gt__(self, other: object) -> bool:
        if other is None:
            return False
        if not isinstance(other, YAMLObjectWrapper):
            other = self.__class__(other)
        return self.value > other.value

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __le__(self, other: object) -> bool:
        return not self.__gt__(other)

    def __ge__(self, other: object) -> bool:
        if other is None:
            return False
        if not isinstance(other, YAMLObjectWrapper):
            other = self.__class__(other)
        return self.__eq__(other) or self.__gt__(other)

    def __lt__(self, other: object) -> bool:
        return not self.__ge__(other)

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.value})'

    def __getstate__(self) -> Mapping[str, Any]:
        return {
            name: getattr(self, name)
            for name in self.__slots__
        }
