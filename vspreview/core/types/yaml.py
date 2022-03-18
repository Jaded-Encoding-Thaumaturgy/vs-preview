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

    def __eq__(self, other: YAMLObjectWrapper) -> bool:  # type: ignore
        return self.value == other.value  # type: ignore

    def __gt__(self, other: YAMLObjectWrapper) -> bool:
        return self.value > other.value  # type: ignore

    def __ne__(self, other: YAMLObjectWrapper) -> bool:  # type: ignore
        return not self.__eq__(other)

    def __le__(self, other: YAMLObjectWrapper) -> bool:
        return not self.__gt__(other)

    def __ge__(self, other: YAMLObjectWrapper) -> bool:
        return self.__eq__(other) or self.__gt__(other)

    def __lt__(self, other: YAMLObjectWrapper) -> bool:
        return not self.__ge__(other)

    def __getstate__(self) -> Mapping[str, Any]:
        return {
            name: getattr(self, name)
            for name in self.__slots__
        }
