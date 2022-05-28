from typing import Iterator

# pylint: skip-file


class SSAEvent:
    start: int
    end: int


class SSAFile:
    @classmethod
    def load(self, path: str) -> 'SSAFile': ...

    def __iter__(self) -> Iterator[SSAEvent]: ...

    def __len__(self) -> int: ...


load = SSAFile.load
