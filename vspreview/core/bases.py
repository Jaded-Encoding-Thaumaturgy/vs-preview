from __future__ import annotations

from abc import ABCMeta
from typing import TYPE_CHECKING, Any, cast, no_type_check

from PyQt6 import sip
from yaml import AliasEvent, SafeLoader, ScalarNode, YAMLObject, YAMLObjectMetaclass

try:
    from yaml import CDumper as yaml_Dumper
except ImportError:
    from yaml import Dumper as yaml_Dumper  # type: ignore

if TYPE_CHECKING:
    from jetpytools import T


__all__ = [
    'AbstractYAMLObjectSingleton',
    'QABC',
    'QYAMLObject',
    'QYAMLObjectSingleton',
    'QAbstractYAMLObjectSingleton',
    'SafeYAMLObject',
    'yaml_Dumper',
    'yaml_Loader',
]


class SaferLoader(SafeLoader):     # type: ignore
    def compose_node(self, parent, index):
        if self.check_event(AliasEvent):
            event = self.peek_event()
            anchor = event.anchor
            if anchor not in self.anchors:
                self.get_event()
                return ScalarNode("tag:yaml.org,2002:null", "null")
        return super().compose_node(parent, index)

yaml_Loader = SaferLoader


class SingletonMeta(type):
    def __init__(cls: type[T], name: str, bases: tuple[type, ...], dct: dict[str, Any]) -> None:
        super().__init__(name, bases, dct)  # type: ignore
        # store the instance in a list rather than directly as a member because otherwise this crashes
        # with PyQt6 on Python 3.12 for reasons I do not pretend to understand
        cls.instance: list[T] = []  # type: ignore

    def __call__(cls, *args: Any, **kwargs: Any) -> T:  # type: ignore
        if not cls.instance:
            cls.instance.append(super().__call__(*args, **kwargs))
        return cls.instance[0]

    def __new__(cls: type[type], name: str, bases: tuple[type, ...], dct: dict[str, Any]) -> type:
        subcls = super(SingletonMeta, cls).__new__(cls, name, bases, dct)  # type: ignore
        singleton_new = None
        for entry in subcls.__mro__:
            if entry.__class__ is SingletonMeta:
                singleton_new = entry.__new__
        if subcls.__new__ is not singleton_new:
            subcls.__default_new__ = subcls.__new__
            subcls.__new__ = singleton_new
        return cast(type, subcls)


class Singleton(metaclass=SingletonMeta):
    @no_type_check
    def __new__(cls: type[T], *args: Any, **kwargs: Any) -> T:
        if not cls.instance:
            if hasattr(cls, '__default_new__'):
                cls.instance.append(cls.__default_new__(cls, *args, **kwargs))
            else:
                cls.instance.append(super(Singleton, cls).__new__(cls))
        return cls.instance[0]


class SafeYAMLObjectMetaclass(YAMLObjectMetaclass):
    def __init__(cls: type[T], name: str, bases: tuple[type, ...], dct: dict[str, Any]) -> None:
        super(SafeYAMLObjectMetaclass, cls).__init__(name, bases, dct)   # type: ignore
        yaml_Loader.add_constructor(f'tag:yaml.org,2002:python/object:{cls.__module__}.{cls.__name__}', cls.from_yaml)

# Fallback constructor for python/object tags that just returns None rather than raising an Error,
# so that invalid or outdated config files can still be parsed.
yaml_Loader.add_multi_constructor('tag:yaml.org,2002:python/object', lambda self, suffix, node: None)


class SafeYAMLObject(YAMLObject, metaclass=SafeYAMLObjectMetaclass):
    pass


class AbstractYAMLObjectMeta(SafeYAMLObjectMetaclass, ABCMeta):
    pass


class AbstractYAMLObjectMetaClass(YAMLObject, metaclass=AbstractYAMLObjectMeta):
    pass


class AbstractYAMLObjectSingletonMeta(SingletonMeta, AbstractYAMLObjectMeta):
    pass


class AbstractYAMLObjectSingleton(AbstractYAMLObjectMetaClass, Singleton, metaclass=AbstractYAMLObjectSingletonMeta):
    pass


class QABCMeta(sip.wrappertype, ABCMeta):
    pass


class QABC(metaclass=QABCMeta):
    pass


class QSingletonMeta(SingletonMeta, sip.wrappertype):
    pass


class QYAMLObjectMeta(SafeYAMLObjectMetaclass, sip.wrappertype):
    pass


class QYAMLObject(YAMLObject, metaclass=QYAMLObjectMeta):
    pass


class QYAMLObjectSingletonMeta(QSingletonMeta, QYAMLObjectMeta):
    pass


class QYAMLObjectSingleton(QYAMLObject, Singleton, metaclass=QYAMLObjectSingletonMeta):
    pass


class QAbstractYAMLObjectSingletonMeta(QYAMLObjectSingletonMeta):
    pass


class QAbstractYAMLObjectSingleton(QYAMLObjectSingleton, metaclass=QAbstractYAMLObjectSingletonMeta):
    pass
