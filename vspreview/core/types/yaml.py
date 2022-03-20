from __future__ import annotations

import vapoursynth as vs
from yaml import YAMLObject
from typing import Any, Mapping


core = vs.core


class YAMLObjectWrapper(YAMLObject):
    yaml_tag: str
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
        if not isinstance(other, YAMLObjectWrapper):
            raise NotImplementedError
        return self.value == other.value

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, YAMLObjectWrapper):
            raise NotImplementedError
        return self.value > other.value

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __le__(self, other: YAMLObjectWrapper) -> bool:
        return not self.__gt__(other)

    def __ge__(self, other: YAMLObjectWrapper) -> bool:
        return self.__eq__(other) or self.__gt__(other)

    def __lt__(self, other: YAMLObjectWrapper) -> bool:
        return not self.__ge__(other)

    def __repr__(self) -> str:
        return f'{self.yaml_tag[1:]}({self.value})'

    def __getstate__(self) -> Mapping[str, Any]:
        return {
            name: getattr(self, name)
            for name in self.__slots__
        }
