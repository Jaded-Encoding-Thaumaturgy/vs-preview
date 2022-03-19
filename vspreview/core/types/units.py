from __future__ import annotations

import vapoursynth as vs
from datetime import timedelta
from typing import Any, Mapping, overload, TypeVar, cast

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

    def __add__(self, other: FrameInterval) -> Frame:
        return Frame(self.value + other.value)

    def __iadd__(self, other: FrameInterval) -> Frame:
        self.value += other.value
        return self

    @overload
    def __sub__(self, other: FrameInterval) -> Frame: ...
    @overload
    def __sub__(self, other: Frame) -> FrameInterval: ...

    def __sub__(self, other: Frame | FrameInterval) -> Frame | FrameInterval:
        if isinstance(other, Frame):
            return FrameInterval(self.value - other.value)
        if isinstance(other, FrameInterval):
            return Frame(self.value - other.value)
        raise TypeError

    @overload
    def __isub__(self, other: FrameInterval) -> Frame: ...
    @overload
    def __isub__(self, other: Frame) -> FrameInterval: ...

    def __isub__(self, other: Frame | FrameInterval) -> Frame | FrameInterval:  # type: ignore
        self.value -= other.value
        return self

    def __repr__(self) -> str:
        return f'Frame({self.value})'

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        try_load(
            state, 'value', int, self.__init__,  # type: ignore
            'Failed to load Frame instance'
        )


class FrameInterval(YAMLObjectWrapper):
    yaml_tag = '!FrameInterval'

    __slots__ = ('value',)

    def __init__(self, init_value: FrameInterval | int | TimeInterval) -> None:
        if isinstance(init_value, int):
            self.value = init_value
        elif isinstance(init_value, FrameInterval):
            self.value = init_value.value
        elif isinstance(init_value, TimeInterval):
            self.value = main_window().current_output.to_frame_interval(init_value).value
        else:
            raise TypeError

    def __add__(self, other: FrameInterval) -> FrameInterval:
        return FrameInterval(self.value + other.value)

    def __iadd__(self, other: FrameInterval) -> FrameInterval:
        self.value += other.value
        return self

    def __sub__(self, other: FrameInterval) -> FrameInterval:
        return FrameInterval(self.value - other.value)

    def __isub__(self, other: FrameInterval) -> FrameInterval:
        self.value -= other.value
        return self

    def __mul__(self, other: int) -> FrameInterval:
        return FrameInterval(self.value * other)

    def __imul__(self, other: int) -> FrameInterval:
        self.value *= other
        return self

    def __rmul__(self, other: int) -> FrameInterval:
        return FrameInterval(other * self.value)

    def __floordiv__(self, other: float) -> FrameInterval:
        return FrameInterval(int(self.value // other))

    def __ifloordiv__(self, other: float) -> FrameInterval:
        self.value = int(self.value // other)
        return self

    def __repr__(self) -> str:
        return f'FrameInterval({self.value})'

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        try_load(
            state, 'value', int, self.__init__,  # type: ignore
            'Failed to load FrameInterval instance'
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

    def __add__(self, other: TimeInterval) -> Time:
        return Time(self.value + other.value)

    def __iadd__(self, other: TimeInterval) -> Time:
        self.value += other.value
        return self

    @overload
    def __sub__(self, other: TimeInterval) -> Time: ...
    @overload
    def __sub__(self, other: Time) -> TimeInterval: ...

    def __sub__(self, other: Time | TimeInterval) -> Time | TimeInterval:
        if isinstance(other, Time):
            return TimeInterval(self.value - other.value)
        if isinstance(other, TimeInterval):
            return Time(self.value - other.value)
        raise TypeError

    @overload
    def __isub__(self, other: TimeInterval) -> Time: ...
    @overload
    def __isub__(self, other: Time) -> TimeInterval: ...

    def __isub__(self, other: Time | TimeInterval) -> Time | TimeInterval:  # type: ignore
        self.value -= other.value
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


class TimeInterval(YAMLObjectWrapper):
    yaml_tag = '!TimeInterval'

    __slots__ = (
        'value',
    )

    def __init__(self, init_value: TimeInterval | timedelta | FrameInterval | None = None, **kwargs: Any):
        if isinstance(init_value, timedelta):
            self.value = init_value
        elif isinstance(init_value, TimeInterval):
            self.value = init_value.value
        elif isinstance(init_value, FrameInterval):
            self.value = main_window().current_output.to_time_interval(init_value).value
        elif any(kwargs):
            self.value = timedelta(**kwargs)
        elif init_value is None:
            self.value = timedelta()
        else:
            raise TypeError

    def __add__(self, other: TimeInterval) -> TimeInterval:
        return TimeInterval(self.value + other.value)

    def __iadd__(self, other: TimeInterval) -> TimeInterval:
        self.value += other.value
        return self

    def __sub__(self, other: TimeInterval) -> TimeInterval:
        return TimeInterval(self.value - other.value)

    def __isub__(self, other: TimeInterval) -> TimeInterval:
        self.value -= other.value
        return self

    def __mul__(self, other: int) -> TimeInterval:
        return TimeInterval(self.value * other)

    def __imul__(self, other: int) -> TimeInterval:
        self.value *= other
        return self

    def __rmul__(self, other: int) -> TimeInterval:
        return TimeInterval(other * self.value)

    def __truediv__(self, other: float) -> TimeInterval:
        return TimeInterval(self.value / other)

    def __itruediv__(self, other: float) -> TimeInterval:
        self.value /= other
        return self

    def __str__(self) -> str:
        from ...utils import strfdelta

        return strfdelta(self, '%h:%M:%S.%Z')

    def __float__(self) -> float:
        return cast(float, self.value.total_seconds())

    def __repr__(self) -> str:
        return f'TimeInterval({self.value})'

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        try_load(
            state, 'value', timedelta, self.__init__,  # type: ignore
            'Failed to load TimeInterval instance'
        )


FrameType = TypeVar('FrameType', Frame, FrameInterval)
TimeType = TypeVar('TimeType', Time, TimeInterval)
