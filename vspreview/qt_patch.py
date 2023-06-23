from PyQt6.QtCore import Qt

if not getattr(Qt, '_vspreview_patch', False):
    from enum import Enum

    for name in dir(Qt):
        value = getattr(Qt, name)

        if not isinstance(value, type):
            continue

        if not issubclass(value, Enum):
            continue

        if any(not isinstance(x.value, int) for x in value.__members__.values()):
            continue

        def _new_eq(self, other, conv: bool = False) -> bool:
            try:  # fast path
                return int.__eq__(self, other)
            except TypeError:  # slow path
                ...

            if isinstance(self, Enum):
                self = self.value

            if isinstance(other, Enum):
                other = other.value

            if conv:
                self = int(self)
                other = int(other)

            try:
                return _new_eq(self, other, conv)
            except Exception:
                return _new_eq(self, other, True)

        setattr(value, '__eq__', _new_eq)

    setattr(Qt, '_vspreview_patch', True)
