from __future__ import annotations

from bisect import bisect_right
from copy import deepcopy
from typing import Any, Iterator

from PyQt6.QtCore import QAbstractListModel, QAbstractTableModel, QModelIndex, Qt

from ..core import Frame, QYAMLObject, Scene, Time, main_window

__all__ = [
    'SceningList',
    'SceningLists'
]


class SceningList(QAbstractTableModel, QYAMLObject):
    __slots__ = ('name', 'items', 'max_value')

    START_FRAME_COLUMN = 0
    END_FRAME_COLUMN = 1
    START_TIME_COLUMN = 2
    END_TIME_COLUMN = 3
    LABEL_COLUMN = 4
    COLUMN_COUNT = 5

    def __init__(self, name: str = '', max_value: Frame | None = None, items: list[Scene] | None = None, *, temporary: bool = False) -> None:
        self.setValue(name, max_value, items, temporary=temporary)

    def setValue(self, name: str = '', max_value: Frame | None = None, items: list[Scene] | None = None, *, temporary: bool = False) -> None:
        super().__init__()
        self.name = name
        self.max_value = max_value if max_value is not None else Frame(2**31)
        self.items = items if items is not None else []
        self.temporary = temporary

        self.main = main_window()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self.items)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return self.COLUMN_COUNT

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None

        if orientation == Qt.Orientation.Horizontal:
            if section == self.START_FRAME_COLUMN:
                return 'Start'
            if section == self.END_FRAME_COLUMN:
                return 'End'
            if section == self.START_TIME_COLUMN:
                return 'Start'
            if section == self.END_TIME_COLUMN:
                return 'End'
            if section == self.LABEL_COLUMN:
                return 'Label'
        if orientation == Qt.Orientation.Vertical:
            return section + 1
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.UserRole) -> Any:
        if not index.isValid():
            return None
        row = index.row()
        if row >= len(self.items):
            return None
        column = index.column()
        if column >= self.COLUMN_COUNT:
            return None

        if role in {Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole}:
            if column == self.START_FRAME_COLUMN:
                return str(self.items[row].start)
            if column == self.END_FRAME_COLUMN:
                if self.items[row].end != self.items[row].start:
                    return str(self.items[row].end)
                else:
                    return ''
            if column == self.START_TIME_COLUMN:
                return str(Time(self.items[row].start))
            if column == self.END_TIME_COLUMN:
                if self.items[row].end != self.items[row].start:
                    return str(Time(self.items[row].end))
                else:
                    return ''
            if column == self.LABEL_COLUMN:
                return str(self.items[row].label)

        if role == Qt.ItemDataRole.UserRole:
            if column == self.START_FRAME_COLUMN:
                return self.items[row].start
            if column == self.END_FRAME_COLUMN:
                return self.items[row].end
            if column == self.START_TIME_COLUMN:
                return Time(self.items[row].start)
            if column == self.END_TIME_COLUMN:
                return Time(self.items[row].end)
            if column == self.LABEL_COLUMN:
                return self.items[row].label

        return None

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid():
            return False
        if role not in {Qt.ItemDataRole.EditRole, Qt.ItemDataRole.UserRole}:
            return False

        row = index.row()
        column = index.column()
        scene = deepcopy(self.items[row])

        if column == self.START_FRAME_COLUMN:
            if not isinstance(value, Frame):
                raise TypeError
            if value > scene.end:
                return False
            scene.start = value
            proper_update = True
        elif column == self.END_FRAME_COLUMN:
            if not isinstance(value, Frame):
                raise TypeError
            if value < scene.start:
                return False
            scene.end = value
            proper_update = True
        if column == self.START_TIME_COLUMN:
            if not isinstance(value, Time):
                raise TypeError
            frame = Frame(value)
            if frame > scene.end:
                return False
            scene.start = frame
            proper_update = True
        if column == self.END_TIME_COLUMN:
            if not isinstance(value, Time):
                raise TypeError
            frame = Frame(value)
            if frame < scene.start:
                return False
            scene.end = frame
            proper_update = True
        elif column == self.LABEL_COLUMN:
            if not isinstance(value, str):
                raise TypeError
            scene.label = value
            proper_update = False

        if proper_update is True:
            i = bisect_right(self.items, scene)
            if i > row:
                i -= 1
            if i != row:
                self.beginMoveRows(self.createIndex(row, 0), row, row, self.createIndex(i, 0), i)
                del self.items[row]
                self.items.insert(i, scene)
                self.endMoveRows()
            else:
                self.items[index.row()] = scene
                self.dataChanged.emit(index, index)
        else:
            self.items[index.row()] = scene
            self.dataChanged.emit(index, index)
        return True

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, i: int) -> Scene:
        return self.items[i]

    def __setitem__(self, i: int, value: Scene) -> None:
        if i >= len(self.items):
            raise IndexError

        self.items[i] = value
        self.dataChanged.emit(self.createIndex(i, 0), self.createIndex(i, self.COLUMN_COUNT - 1))

    def __contains__(self, item: Scene | Frame) -> bool:
        if isinstance(item, Scene):
            return item in self.items
        if isinstance(item, Frame):
            for scene in self.items:
                if item in scene:
                    return True
            return False
        raise TypeError

    def __iter__(self) -> Iterator[Scene]:
        return iter(self.items)

    def add(self, start: Frame, end: Frame | None = None, label: str = '') -> Scene:
        scene = Scene(start, end, label)

        if scene in self.items:
            return scene

        if scene.end > self.max_value:
            raise ValueError('New Scene is out of bounds of output')

        index = bisect_right(self.items, scene)
        self.beginInsertRows(QModelIndex(), index, index)
        self.items.insert(index, scene)
        self.endInsertRows()

        return scene

    def remove(self, i: int | Scene) -> None:
        if isinstance(i, Scene):
            i = self.items.index(i)

        if i >= 0 and i < len(self.items):
            self.beginRemoveRows(QModelIndex(), i, i)
            del self.items[i]
            self.endRemoveRows()
        else:
            raise IndexError

    def get_prev_frame(self, initial: Frame) -> Frame | None:
        result = None
        result_delta = Frame(int(self.max_value))
        for scene in reversed(self.items):
            if Frame(0) < initial - scene.start < result_delta:
                result = scene.start
                result_delta = scene.start - initial
            if Frame(0) < initial - scene.end < result_delta:
                result = scene.end
                result_delta = scene.end - initial

        return result

    def get_next_frame(self, initial: Frame) -> Frame | None:
        result = None
        result_delta = Frame(int(self.max_value))
        for scene in self.items:
            if Frame(0) < scene.start - initial < result_delta:
                result = scene.start
                result_delta = scene.start - initial
            if Frame(0) < scene.end - initial < result_delta:
                result = scene.end
                result_delta = scene.end - initial

        return result

    def __getstate__(self) -> dict[str, Any]:
        return {name: getattr(self, name)
                for name in self.__slots__}

    def __setstate__(self, state: dict[str, Any]) -> None:
        try:
            max_value = state['max_value']
            if not isinstance(max_value, Frame):
                raise TypeError("'max_value' of a SceningList is not a Frame. It's most probably corrupted.")

            name = state['name']
            if not isinstance(name, str):
                raise TypeError("'name' of a SceningList is not a Frame. It's most probably corrupted.")

            items = state['items']
            if not isinstance(items, list):
                raise TypeError("'items' of a SceningList is not a List. It's most probably corrupted.")
            for item in items:
                if not isinstance(item, Scene):
                    raise TypeError("One of the items of SceningList is not a Scene. It's most probably corrupted.")
        except KeyError:
            raise KeyError(
                "SceningList lacks one or more of its fields. It's most probably corrupted. Check those: {}.".format(
                    ', '.join(self.__slots__)))

        self.setValue(name, max_value, items)


class SceningLists(QAbstractListModel, QYAMLObject):
    __slots__ = ('items',)

    def __init__(self, items: list[SceningList] | None = None) -> None:
        self.setValue(items)

    def setValue(self, items: list[SceningList] | None = None) -> None:
        super().__init__()
        self.main = main_window()
        self.main.reload_before_signal.connect(self.clean_items)
        self.items = (items if items is not None else []) + self.main.temporary_scenes

    def clean_items(self) -> None:
        self.items = [item for item in self.items if not item.temporary]

    def __getitem__(self, i: int) -> SceningList:
        return self.items[i]

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self) -> Iterator[SceningList]:
        return iter(self.items)

    def index_of(self, item: SceningList, start_i: int = 0, end_i: int = 0) -> int:
        if end_i == 0:
            end_i = len(self.items)
        return self.items.index(item, start_i, end_i)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self.items)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.UserRole) -> Any:
        if not index.isValid():
            return None
        if index.row() >= len(self.items):
            return None

        if role in {Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole}:
            return self.items[index.row()].name
        if role == Qt.ItemDataRole.UserRole:
            return self.items[index.row()]
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.ItemIsEnabled

        return super().flags(index) | Qt.ItemFlag.ItemIsEditable

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid():
            return False
        if role not in {Qt.ItemDataRole.EditRole, Qt.ItemDataRole.UserRole}:
            return False
        if not isinstance(value, str):
            return False

        self.items[index.row()].name = value
        self.dataChanged.emit(index, index)
        return True

    def insertRow(self, i: int, parent: QModelIndex = QModelIndex()) -> bool:
        self.add(i=i)
        return True

    def removeRow(self, i: int, parent: QModelIndex = QModelIndex()) -> bool:
        try:
            self.remove(i)
        except IndexError:
            return False

        return True

    def add(
        self, name: str | None = None, max_value: Frame | None = None, i: int | None = None
    ) -> tuple[SceningList, int]:
        if max_value is None:
            max_value = self.main.current_output.total_frames - 1
        if i is None:
            i = len(self.items)

        self.beginInsertRows(QModelIndex(), i, i)
        if name is None:
            self.items.insert(i, SceningList(f'List {len(self.items) + 1}', max_value))
        else:
            self.items.insert(i, SceningList(name, max_value))
        self.endInsertRows()
        return self.items[i], i

    def add_list(self, scening_list: SceningList) -> int:
        i = len(self.items)
        self.beginInsertRows(QModelIndex(), i, i)
        self.items.insert(i, scening_list)
        self.endInsertRows()
        return i

    def remove(self, item: int | SceningList) -> None:
        i = item
        if isinstance(i, SceningList):
            i = self.items.index(i)

        if i >= 0 and i < len(self.items):
            self.beginRemoveRows(QModelIndex(), i, i)
            del self.items[i]
            self.endRemoveRows()
        else:
            raise IndexError

    def __getstate__(self) -> dict[str, Any]:
        self.clean_items()

        return {
            name: getattr(self, name)
            for name in self.__slots__
        }

    def __setstate__(self, state: dict[str, Any]) -> None:
        try:
            items = state['items']
            if not isinstance(items, list):
                raise TypeError('\'items\' of a SceningLists is not a List. It\'s most probably corrupted.')
            for item in items:
                if not isinstance(item, SceningList):
                    raise TypeError(
                        'One of the items of a SceningLists is not a SceningList. It\'s most probably corrupted.'
                    )
        except KeyError:
            raise KeyError(
                'SceningLists lacks one or more of its fields. It\'s most probably corrupted. Check those: {}.'
                .format(', '.join(self.__slots__))
            )

        self.setValue(items)
