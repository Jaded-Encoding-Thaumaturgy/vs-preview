from __future__ import annotations

from PyQt5 import sip
from yaml import YAMLObject, YAMLObjectMetaclass
from typing import Any, Dict, no_type_check, Type, TypeVar, Tuple, cast

from .better_abc import ABCMeta


T = TypeVar('T')


class SingletonMeta(type):
    def __init__(cls: Type[T], name: str, bases: Tuple[type, ...], dct: Dict[str, Any]) -> None:
        super().__init__(name, bases, dct)  # type: ignore
        cls.instance: T | None = None  # type: ignore

    def __call__(cls, *args: Any, **kwargs: Any) -> T:
        if cls.instance is None:
            cls.instance = super().__call__(*args, **kwargs)
        return cls.instance

    def __new__(cls: Type[type], name: str, bases: Tuple[type, ...], dct: Dict[str, Any]) -> type:
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
    def __new__(cls: Type[T], *args: Any, **kwargs: Any) -> T:
        if cls.instance is None:
            if hasattr(cls, '__default_new__'):
                cls.instance = cls.__default_new__(cls, *args, **kwargs)
            else:
                cls.instance = super(Singleton, cls).__new__(cls)
        return cls.instance


class AbstractYAMLObjectMeta(YAMLObjectMetaclass, ABCMeta):
    pass


class AbstractYAMLObject(YAMLObject, metaclass=AbstractYAMLObjectMeta):
    pass


class AbstractYAMLObjectSingletonMeta(SingletonMeta, AbstractYAMLObjectMeta):
    pass


class AbstractYAMLObjectSingleton(AbstractYAMLObject, Singleton, metaclass=AbstractYAMLObjectSingletonMeta):
    pass


class QABCMeta(sip.wrappertype, ABCMeta):
    pass


class QABC(metaclass=QABCMeta):
    pass


class QSingletonMeta(SingletonMeta, sip.wrappertype):
    pass


class QSingleton(Singleton, metaclass=QSingletonMeta):
    pass


class QAbstractSingletonMeta(QSingletonMeta):
    pass


class QAbstractSingleton(Singleton, metaclass=QAbstractSingletonMeta):
    pass


class QYAMLObjectMeta(YAMLObjectMetaclass, sip.wrappertype):
    pass


class QYAMLObject(YAMLObject, metaclass=QYAMLObjectMeta):
    pass


class QAbstractYAMLObjectMeta(QYAMLObjectMeta, QABC):
    pass


class QAbstractYAMLObject(YAMLObject, metaclass=QAbstractYAMLObjectMeta):
    pass


class QYAMLObjectSingletonMeta(QSingletonMeta, QYAMLObjectMeta):
    pass


class QYAMLObjectSingleton(QYAMLObject, Singleton, metaclass=QYAMLObjectSingletonMeta):
    pass


class QAbstractYAMLObjectSingletonMeta(QYAMLObjectSingletonMeta):
    pass


class QAbstractYAMLObjectSingleton(QYAMLObjectSingleton, metaclass=QAbstractYAMLObjectSingletonMeta):
    pass
