from __future__ import annotations

from datetime import timedelta
from typing import Any, SupportsFloat, SupportsInt, Union, cast

from ..abstracts import main_window, try_load
from ..bases import yaml_Loader
from .yaml import YAMLObjectWrapper

__all__ = [
    'Frame', 'Time'
]


Number = Union[int, float, SupportsInt, SupportsFloat]

yaml_Loader.add_constructor('tag:yaml.org,2002:python/object/apply:datetime.timedelta', lambda self, node: timedelta(*self.construct_sequence(node)))

class Frame(YAMLObjectWrapper):
    __slots__ = ('value',)

    def __init__(self, init_value: Number | Frame | Time | None = 0) -> None:
        if isinstance(init_value, float):
            init_value = int(init_value)
        if isinstance(init_value, int):
            self.value = init_value
        elif isinstance(init_value, Frame):
            self.value = init_value.value
        elif isinstance(init_value, Time):
            self.value = main_window().current_output.to_frame(init_value).value
        else:
            raise TypeError

    def __add__(self, other: Number | Frame) -> Frame:
        if not isinstance(other, Frame):
            other = Frame(other)
        return Frame(self.value + other.value)

    def __iadd__(self, other: Number | Frame) -> Frame:
        if not isinstance(other, Frame):
            other = Frame(other)
        self.value += other.value
        return self

    def __sub__(self, other: Number | Frame) -> Frame:
        if isinstance(other, Frame):
            return Frame(self.value - other.value)
        return self - Frame(other)

    def __isub__(self, other: Number | Frame) -> Frame:
        if not isinstance(other, Frame):
            other = Frame(other)
        self.value -= other.value
        return self

    def __mul__(self, other: Number | Frame) -> Frame:
        if not isinstance(other, Frame):
            other = Frame(other)
        return Frame(self.value * other.value)

    def __imul__(self, other: Number | Frame) -> Frame:
        if not isinstance(other, Frame):
            other = Frame(other)
        self.value *= other.value
        return self

    def __rmul__(self, other: Number | Frame) -> Frame:
        if not isinstance(other, Frame):
            other = Frame(other)
        return Frame(other.value * self.value)

    def __floordiv__(self, other: Number | Frame) -> Frame:
        if not isinstance(other, Frame):
            other = Frame(other)
        return Frame(int(self.value // other.value))

    def __ifloordiv__(self, other: Number | Frame) -> Frame:
        if not isinstance(other, Frame):
            other = Frame(other)
        self.value = int(self.value // other.value)
        return self

    def __setstate__(self, state: dict[str, Any]) -> None:
        try_load(
            state, 'value', int, self.__init__,  # type: ignore
            'Failed to load Frame instance'
        )

    def __hash__(self) -> int:
        return hash(self.value)


class Time(YAMLObjectWrapper):
    __slots__ = ('value', )

    def __init__(self, init_value: int | Time | timedelta | Frame | None = None, **kwargs: Any):
        if isinstance(init_value, int):
            init_value = Frame(init_value)

        if isinstance(init_value, timedelta):
            self.value = init_value
        elif isinstance(init_value, Time):
            self.value = init_value.value
        elif isinstance(init_value, Frame):
            self.value = main_window().current_output.to_time(init_value).value
        elif any(kwargs):
            self.value = timedelta(**kwargs)
        elif init_value is None:
            self.value = timedelta()
        else:
            raise TypeError

    def __add__(self, other: Time) -> Time:
        return Time(self.value + other.value)

    def __iadd__(self, other: Time) -> Time:
        self.value += other.value
        return self

    def __sub__(self, other: int | Time | timedelta | Frame | None) -> Time:
        if isinstance(other, Time):
            return Time(self.value - other.value)
        return self - Time(other)

    def __isub__(self, other: int | Time | timedelta | Frame | None) -> Time:
        if not isinstance(other, Time):
            other = Time(other)
        self.value -= other.value
        return self

    def __mul__(self, other: int) -> Time:
        return Time(self.value * other)

    def __imul__(self, other: int) -> Time:
        self.value *= other
        return self

    def __rmul__(self, other: int) -> Time:
        return Time(other * self.value)

    def __truediv__(self, other: float) -> Time:
        return Time(self.value / other)

    def __itruediv__(self, other: float) -> Time:
        self.value /= other
        return self

    def __str__(self) -> str:
        from ...utils import strfdelta

        return strfdelta(self, '%h:%M:%S.%Z')

    def to_str_minimal(self, max_value: Time | None = None) -> str:
        from ...utils import strfdelta

        max_value = (max_value or self).value

        fmt = ''

        if max_value.seconds > 3600:
            fmt += '%h:'

        if max_value.seconds > 60:
            fmt += '%M:'

        return strfdelta(self, f'{fmt}%S.%Z')

    def __float__(self) -> float:
        return cast(float, self.value.total_seconds())

    def __setstate__(self, state: dict[str, Any]) -> None:
        try_load(
            state, 'value', timedelta, self.__init__,  # type: ignore
            'Failed to load Time instance'
        )

    def __hash__(self) -> int:
        return hash(self.value)
