from __future__ import annotations

from typing import Any, Mapping

from .units import Frame
from .yaml import YAMLObjectWrapper


class Scene(YAMLObjectWrapper):
    __slots__ = ('start', 'end', 'label')

    def __init__(self, start: Frame | None = None, end: Frame | None = None, label: str = '') -> None:
        self.setValue(start, end, label)

    def setValue(self, start: Frame | None, end: Frame | None, label: str) -> None:
        if start is not None and end is not None:
            self.start = start
            self.end = end
        elif start is not None:
            self.start = start
            self.end = start
        elif end is not None:
            self.start = end
            self.end = end
        else:
            raise ValueError

        if self.start > self.end:
            self.start, self.end = self.end, self.start

        self.label = label

    def __str__(self) -> str:
        result = ''

        if self.start == self.end:
            result = f'{self.start}'
        else:
            result = f'{self.start} - {self.end}'

        if self.label != '':
            result += f': {self.label}'

        return result

    def __repr__(self) -> str:
        return f"Scene({self.start}, {self.end}, '{self.label}')"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Scene):
            raise NotImplementedError
        return self.start == other.start and self.end == other.end

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Scene):
            raise NotImplementedError
        if self.start != other.start:
            return self.start > other.start
        else:
            return self.end > other.end

    def duration(self) -> Frame:
        return self.end - self.start

    def __contains__(self, frame: Frame) -> bool:
        return self.start <= frame <= self.end

    def __setstate__(self, state: Mapping[str, Any]) -> None:
        try:
            if not isinstance(state['start'], Frame):
                raise TypeError("Start frame of Scene is not a Frame. It's most probably corrupted.")

            if not isinstance(state['end'], Frame):
                raise TypeError("End frame of Scene is not a Frame. It's most probably corrupted.")

            if not isinstance(state['label'], str):
                raise TypeError("Label of Scene is not a string. It's most probably corrupted.")
        except KeyError:
            raise KeyError(
                "Scene lacks one or more of its fields."
                f"It's most probably corrupted. Check those: {', '.join(self.__slots__)}."
            )

        self.setValue(state['start'], state['end'], state['label'])
