from __future__ import annotations

import vapoursynth as vs
from datetime import timedelta
from typing import Any, Mapping, cast

from .yaml import YAMLObjectWrapper
from ..abstracts import main_window, try_load


core = vs.core


class Frame(YAMLObjectWrapper):
    yaml_tag = '!Frame'

    __slots__ = ('value',)

    def __init__(self, init_value: Frame | int | Time) -> None:
        if isinstance(init_value, int):
            if init_value < 0:
                raise ValueError
            self.value = init_value
        elif isinstance(init_value, Frame):
            self.value = init_value.value
        elif isinstance(init_value, Time):
            self.value = main_window().current_output.to_frame(init_value).value
        else:
            raise TypeError

    def __add__(self, other: Frame) -> Frame:
        return Frame(self.value + other.value)

    def __iadd__(self, other: Frame) -> Frame:
        self.value += other.value
        return self

    def __sub__(self, other: Frame) -> Frame:
        if isinstance(other, Frame):
            return Frame(self.value - other.value)
        raise TypeError

    def __isub__(self, other: Frame) -> Frame:
        self.value -= other.value
        return self

    def __mul__(self, other: int) -> Frame:
        return Frame(self.value * other)

    def __imul__(self, other: int) -> Frame:
        self.value *= other
        return self

    def __rmul__(self, other: int) -> Frame:
        return Frame(other * self.value)

    def __floordiv__(self, other: float) -> Frame:
        return Frame(int(self.value // other))

    def __ifloordiv__(self, other: float) -> Frame:
        self.value = int(self.value // other)
        return self

    def __repr__(self) -> str:
        return f'Frame({self.value})'

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        try_load(
            state, 'value', int, self.__init__,  # type: ignore
            'Failed to load Frame instance'
        )


class Time(YAMLObjectWrapper):
    yaml_tag = '!Time'

    __slots__ = (
        'value',
    )

    def __init__(self, init_value: Time | timedelta | Frame | None = None, **kwargs: Any):
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

    def __sub__(self, other: Time) -> Time:
        if isinstance(other, Time):
            return Time(self.value - other.value)
        if isinstance(other, Time):
            return Time(self.value - other.value)
        raise TypeError

    def __isub__(self, other: Time) -> Time:
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

    def __float__(self) -> float:
        return cast(float, self.value.total_seconds())

    def __repr__(self) -> str:
        return f'Time({self.value})'

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        try_load(
            state, 'value', timedelta, self.__init__,  # type: ignore
            'Failed to load Time instance'
        )
