# -*- coding: utf-8 -*-
import abc
from collections import namedtuple
from enum import Enum
from typing import Any, Dict, List, Tuple

from django.utils.translation import gettext_lazy as _
from rest_framework.decorators import action


def list_route(**kwargs):
    kwargs["detail"] = False
    return action(**kwargs)


def detail_route(**kwargs):
    kwargs["detail"] = True
    return action(**kwargs)


def tuple_choices(tupl):
    """从django-model的choices转换到namedtuple"""
    return [(t, t) for t in tupl]


def dict_to_namedtuple(dic):
    """从dict转换到namedtuple"""
    return namedtuple("AttrStore", list(dic.keys()))(**dic)


def choices_to_namedtuple(choices):
    """从django-model的choices转换到namedtuple"""
    return dict_to_namedtuple(dict(choices))


class EnhanceEnum(Enum):
    """增强枚举类，提供常用的枚举值列举方法"""

    @classmethod
    @abc.abstractmethod
    def _get_member__alias_map(cls) -> Dict[Enum, str]:
        """
        获取枚举成员与释义的映射关系
        :return:
        """
        raise NotImplementedError

    @classmethod
    def list_member_values(cls) -> List[Any]:
        """
        获取所有的枚举成员值
        :return:
        """
        member_values = []
        for member in cls._member_names_:
            member_values.append(cls._member_map_[member].value)
        return member_values

    @classmethod
    def get_member_value__alias_map(cls) -> Dict[Any, str]:
        """
        获取枚举成员值与释义的映射关系，缓存计算结果
        :return:
        """
        member_value__alias_map = {}
        member__alias_map = cls._get_member__alias_map()

        for member, alias in member__alias_map.items():
            if type(member) is not cls:
                raise ValueError(f"except member type -> {cls}, but got -> {type(member)}")
            member_value__alias_map[member.value] = alias

        return member_value__alias_map

    @classmethod
    def list_choices(cls) -> List[Tuple[Any, Any]]:
        """
        获取可选项列表，一般用于序列化器、model的choices选项
        :return:
        """
        return list(cls.get_member_value__alias_map().items())


class ScopeType(EnhanceEnum):
    """作用域类型"""

    BIZ = "biz"
    SPACE = "space"

    @classmethod
    def _get_member__alias_map(cls) -> Dict[Enum, str]:
        return {cls.BIZ: _("业务"), cls.SPACE: _("空间")}


DEFAULT_MAX_WORKERS = 5
