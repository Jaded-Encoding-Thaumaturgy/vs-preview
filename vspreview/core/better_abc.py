from __future__ import annotations

from abc import ABCMeta as NativeABCMeta
from typing import Any, cast

from vstools import T


class DummyAttribute:
    _is_abstract_attribute_ = True


def abstract_attribute(obj: T | None = None) -> T:
    return cast(T, obj or DummyAttribute())


class ABCMeta(NativeABCMeta):
    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        instance = NativeABCMeta.__call__(cls, *args, **kwargs)

        abstract_attributes = [
            name for name in dir(instance)
            if (attr := getattr(instance, name, None)) is not None and getattr(attr, '_is_abstract_attribute_', False)
        ]

        if len(abstract_attributes) > 0:
            raise NotImplementedError(
                "Class {} doesn't initialize following abstract attributes: {}"
                .format(cls.__name__, ', '.join(abstract_attributes))
            )

        return instance


class ABC(metaclass=ABCMeta):
    pass
