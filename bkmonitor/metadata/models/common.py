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

import datetime
import json

import six
from django.db import models
from django.utils.translation import gettext as _


class Label(models.Model):
    """结果表及数据源标签配置"""

    LABEL_TYPE_SOURCE = "source_label"
    LABEL_TYPE_RESULT_TABLE = "result_table_label"
    LABEL_TYPE_TYPE = "type_label"

    # 结果表标签为【其他】的ID值，方便在其他依赖处使用
    RESULT_TABLE_LABEL_OTHER = "others"

    label_id = models.CharField(verbose_name="标签ID", max_length=128, primary_key=True)
    label_name = models.CharField(verbose_name="标签名", max_length=128)
    label_type = models.CharField(
        verbose_name="标签类型",
        max_length=64,
        choices=(
            (LABEL_TYPE_SOURCE, "数据源标签"),
            (LABEL_TYPE_RESULT_TABLE, "结果表标签"),
            (LABEL_TYPE_TYPE, "数据类型标签"),
        ),
    )
    is_admin_only = models.BooleanField(verbose_name="是否只允许管理员配置使用", default=False)
    parent_label = models.CharField(verbose_name="父级标签ID", max_length=128, null=True)
    level = models.IntegerField(verbose_name="标签层级", null=True)
    index = models.IntegerField(verbose_name="标签排序", null=True)

    @classmethod
    def exists_label(cls, label_id, label_type=None):
        """
        判断是否存在一个指定的label, 也可以指定查询的标签类型
        :param label_id: 标签ID
        :param label_type: 标签类型
        :return: True | False
        """
        label_query = cls.objects.filter(label_id=label_id)

        if label_type is not None:
            label_query = label_query.filter(label_type=label_type)

        return label_query.exists()

    @classmethod
    def get_label_info(cls, include_admin_only=False, label_type=None, level=None):
        """
        获取标签信息
        :param include_admin_only: 是否只需要返回全部标签, 包含只管理员可用的配置标签
        :param label_type: 标签类型，可选参数
        :param level: 标签层级，可选参数
        :return: {
            "source_label": [{
                "label_id": "bk_monitor_collector",
                "label_name": "蓝鲸监控采集器",
                "label_type": "source_label",
                "level": null,
                "parent_label": null,
                "index": 0
            }],
            "type_label": [{
                "label_id": "time_series",
                "label_name": "时序数据",
                "label_type": "type_label",
                "level": null,
                "parent_label": null,
                "index": 0
            }],
            "result_table_label": [{
                "label_id": "OS",
                "label_name": "操作系统",
                "label_type": "result_table_label",
                "level": 2,
                "parent_label": "host",
                "index": 0
            }, {
                "label_id": "host",
                "label_name": "主机",
                "label_type": "result_table_label",
                "level": 1,
                "parent_label": null,
                "index": 1
            }]
        }
        """
        label_list = cls.objects.all()

        if not include_admin_only:
            # 如果不需要包含管理员可用的标签，则需要将管理员可用的标签进行过滤
            label_list = label_list.filter(is_admin_only=False)

        if label_type is not None:
            label_list = label_list.filter(label_type=label_type)

        if level is not None:
            label_list = label_list.filter(level=level)

        result = {}
        for label_info in label_list:
            # 需要将不同类别通过不同的数组进行返回
            try:
                result[label_info.label_type].append(label_info.to_json())

            except KeyError:
                result[label_info.label_type] = [label_info.to_json()]

        return result

    def to_json(self):
        """
        返回json格式化数据
        :return: {
            "label_id": "host",
            "label_name": "主机",
            "label_type": "result_table_label",
            "level": 1,
            "parent_label": null,
            "index": 1
        }
        """
        return {
            "label_id": self.label_id,
            "label_name": _(self.label_name),
            "label_type": self.label_type,
            "level": self.level,
            "parent_label": self.parent_label,
            "index": self.index,
        }


class OptionBase(models.Model):
    """各种选项配置的基类，供结果表选项，结果表字段选项，数据源选项继承"""

    QUERY_NAME = None

    # 选项类型
    TYPE_BOOL = "bool"
    TYPE_STRING = "string"
    TYPE_LIST = "list"
    TYPE_DICT = "dict"
    TYPE_INT = "int"

    TYPE_OPTION_DICT = {TYPE_STRING: str}

    value_type = models.CharField(
        "option对应类型",
        choices=((TYPE_BOOL, TYPE_BOOL), (TYPE_STRING, TYPE_STRING), (TYPE_LIST, TYPE_LIST), (TYPE_INT, TYPE_INT)),
        max_length=64,
    )
    value = models.TextField("option配置内容")
    creator = models.CharField("创建者", max_length=32)
    create_time = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        abstract = True

    @classmethod
    def get_option(cls, query_id):
        """
        返回一个指定的option配置内容
        :param query_id: 查询的ID名
        :return: {
            "option_name": option_value
        }
        """
        query_dict = {cls.QUERY_NAME: query_id}
        option_dict = {}

        for option_list in cls.objects.filter(**query_dict):
            option_dict.update(option_list.to_json())

        return option_dict

    @classmethod
    def _parse_value(cls, value):
        if type(value) in (bool, list, dict):
            val = json.dumps(value)
            if isinstance(value, bool):
                val_type = cls.TYPE_BOOL
            elif isinstance(value, list):
                val_type = cls.TYPE_LIST
            else:
                val_type = cls.TYPE_DICT

        elif type(value) in (int,):
            val = json.dumps(value)
            val_type = cls.TYPE_INT

        else:
            val, val_type = value, cls.TYPE_STRING
        return val, val_type

    @classmethod
    def _create_option(cls, value, creator):
        """
        创建字段
        :param value: 选项值
        :param creator: 创建者
        :return: object
        """
        new_object = cls()

        new_object.value, new_object.value_type = cls._parse_value(value)

        new_object.creator = creator
        new_object.create_time = datetime.datetime.now()

        return new_object

    def _trans_list(self):
        """
        将保存的内容按照list的类型进行返回
        :return: list object
        """

        return json.loads(self.value)

    def _trans_bool(self):
        """
        将保存的内容按照list的类型进行返回
        :return: list object
        """

        return json.loads(self.value)

    def _trans_dict(self):
        """
        将保存的内容按照dict的类型进行返回
        :return: dict object
        """

        return json.loads(self.value)

    def _trans_int(self):
        return json.loads(self.value)

    def to_json(self):
        """
        将一个配置变为字典内容返回
        :return: {
            "option_name": option_value
        }
        """
        try:
            option_value = self.TYPE_OPTION_DICT[self.value_type]
            real_value = option_value(self.value) if self.value_type != "string" else six.text_type(self.value)

        except KeyError:
            # 如果找不到对应的配置，表示不是简单的基本功能，需要依赖函数实现
            trans_method = getattr(self, "_trans_{}".format(self.value_type))
            real_value = trans_method()

        return {self.name: real_value}


class BaseModel(models.Model):
    """基本表属性"""

    creator = models.CharField("创建者", max_length=64)
    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    updater = models.CharField("更新者", max_length=64)
    update_time = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        abstract = True


class BaseModelWithTime(models.Model):
    """包含用户及时间"""

    creator = models.CharField("创建者", max_length=64)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updater = models.CharField("更新者", max_length=64)
    updated_at = models.DateTimeField("更新时间", auto_now=True)
    STORAGE_TYPE = "victoria_metrics"

    class Meta:
        abstract = True
