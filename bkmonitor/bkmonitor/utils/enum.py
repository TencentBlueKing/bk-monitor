# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from enum import Enum


class FancyEnum:
    @classmethod
    def get_values(cls):
        return [value for key, value in cls.__dict__.items() if not key.startswith("__")]

    @classmethod
    def get_keys(cls):
        return [key for key, value in cls.__dict__.items() if not key.startswith("__")]

    @classmethod
    def get_value_by_key(cls, key: str) -> any:
        return cls.__dict__.get(key, key)


class ChoicesEnum(Enum):
    """
    常量枚举choices
    """

    @classmethod
    def get_choices(cls) -> tuple:
        """
        获取所有_choices_labels的tuple元组
        :return: tuple(tuple(key, value))
        """
        return cls._choices_labels.value

    @classmethod
    def get_choice_label(cls, key: str) -> str:
        """
        获取_choices_labels的某个key值的value
        :param key: 获取choices的key值的value
        :return: str 字典value值
        """
        return dict(cls.get_choices()).get(key, key)

    @classmethod
    def get_dict_choices(cls) -> dict:
        """
        获取dict格式的choices字段
        :return: dict{key, value}
        """
        return dict(cls.get_choices())

    @classmethod
    def get_keys(cls) -> tuple:
        """
        获取所有_choices_keys的tuple元组(关联key值)
        :return: tuple(tuple(key, value))
        """
        return cls._choices_keys.value

    @classmethod
    def get_choice_key(cls, key: str) -> dict:
        """
        获取_choices_keys的某个key值的value
        :param key: 获取choices的key值的value
        :return: str 字典value值
        """
        return dict(cls.get_keys()).get(key, key)

    @classmethod
    def get_choices_list_dict(cls) -> list:
        """
        获取_choices_keys的某个key值的value
        :return: list[dict{id, name}]
        """
        return [{"id": key, "name": value} for key, value in cls.get_dict_choices().items()]
