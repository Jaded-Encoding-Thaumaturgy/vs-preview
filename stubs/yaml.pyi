from typing import Any, Callable, Dict, IO, Optional, Type, TypeVar, Tuple

# pylint: skip-file

T = TypeVar('T')


class Node:
    pass


class Dumper:
    ignore_aliases: Callable[[], bool]

    def represent_scalar(self, tag: str, value: Any, style: Optional[str] = None) -> Node: ...


class Loader:
    def construct_scalar(self, node: Node) -> Any: ...


class Mark:
    line: int
    column: int


class YAMLError(Exception):
    pass


class MarkedYAMLError(YAMLError):
    problem_mark: Mark


def dump(data: Any, stream: Optional[IO[Any]] = None, Dumper: Dumper = Dumper(), **kwds: Any) -> Any: ...
def load(stream: IO[Any], Loader: Optional[Type] = Loader) -> Any: ...


class YAMLObjectMetaclass(type):
    def __init__(cls: Type[T], name: str, bases: Tuple[type, ...], dct: Dict[str, Any]) -> None: ...


class YAMLObject(metaclass=YAMLObjectMetaclass):
    @classmethod
    def to_yaml(cls: Type[T], dumper: Dumper, data: T) -> Node: ...

    @classmethod
    def from_yaml(cls: Type[T], loader: Loader, node: Node) -> T: ...


def add_representer(cls: Type[T], method: Callable[[Dumper, T], Node]) -> None: ...
def add_constructor(yaml_tag: str, method: Callable[[Loader, Node], T]) -> None: ...
