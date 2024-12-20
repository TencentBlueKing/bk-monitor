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


from django.db import models
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from bkmonitor.utils.db.fields import JsonField


class GlobalConfig(models.Model):
    """动态配置信息"""

    DATA_TYPE_CHOICES = (
        ("Integer", _("整数")),
        ("Char", _("字符串")),
        ("Boolean", _("布尔值")),
        ("JSON", "JSON"),
        ("List", _("列表")),
        ("Choice", _("单选")),
        ("MultipleChoice", _("多选")),
    )

    key = models.CharField("配置名", max_length=255, unique=True)
    value = JsonField("配置信息", blank=True)
    create_at = models.DateTimeField("创建时间", auto_now_add=True)
    update_at = models.DateTimeField("更新时间", auto_now=True)
    description = models.TextField("描述", default="")
    data_type = models.CharField("数据类型", choices=DATA_TYPE_CHOICES, default="JSON", max_length=32)
    options = JsonField("字段选项", default={}, blank=True)
    is_advanced = models.BooleanField("是否为高级选项", default=False)
    is_internal = models.BooleanField("是否为内置配置", default=False)

    class Meta:
        verbose_name = "动态配置信息"
        verbose_name_plural = "动态配置信息"
        db_table = "global_setting"

    @classmethod
    def get(cls, key, defaults=None):
        try:
            conf = cls.objects.filter(key=key).last()
            if conf:
                return conf.value
        except Exception:
            pass

        return defaults

    @classmethod
    def set(cls, key, value):
        try:
            config = cls.objects.get(key=key)
            config.value = value
            config.save()
        except GlobalConfig.DoesNotExist:
            cls.objects.create(key=key, value=value)
            return

        # cls.objects.update_or_create(key=key, defaults={"value": value})

    def get_serializer(self):
        """
        获取对应字段的 Serializer
        """
        cls_name = "{}Field".format(self.data_type)
        serializer_cls = getattr(serializers, cls_name)
        options = self.options or {}
        return serializer_cls(**options)


class MonitorMigration(models.Model):
    """
    监控迁移记录
    """

    app = models.CharField("应用", max_length=64)
    name = models.CharField("表名", max_length=255)
    applied = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "监控迁移记录"
        verbose_name_plural = "监控迁移记录"
        db_table = "monitor_migration"
        unique_together = ("app", "name")
