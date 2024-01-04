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
import base64

from django.db import models
from django.utils.functional import cached_property

from bkmonitor.models.fta.constant import (
    PluginMainType,
    PluginStatus,
    PluginType,
    Scenario,
)
from bkmonitor.utils.db import JsonField
from bkmonitor.utils.model_manager import AbstractRecordModel


class EventPluginBaseModel(AbstractRecordModel):
    """
    告警源接入插件模型基类
    """

    plugin_display_name = models.CharField("插件别名", max_length=64, default="", blank=True)
    plugin_type = models.CharField("插件类型", max_length=32, choices=PluginType.to_choice(), db_index=True)
    summary = models.TextField("概述", default="", blank=True)
    author = models.CharField("作者", max_length=64, default="", blank=True)
    description = models.TextField("详细描述，markdown文本", default="", blank=True)
    tutorial = models.TextField("配置向导，markdown文本", default="", blank=True)

    logo = models.ImageField("logo文件", null=True)

    package_dir = models.TextField("包路径", default="", blank=True)

    # 业务ID先预留，一期先默认都是公共的
    bk_biz_id = models.IntegerField("业务ID", default=0, blank=True, db_index=True)
    tags = JsonField("插件标签", default=[])
    scenario = models.CharField("场景", max_length=64, choices=Scenario.to_choice(), default=Scenario.MONITOR)

    popularity = models.IntegerField("热度", default=0)
    status = models.CharField("状态", max_length=32, choices=PluginStatus.to_choice(), default=PluginStatus.AVAILABLE)

    # 以下字段的修改，将会触发元数据更新
    # 清洗配置信息
    # 接入配置，根据不同的采集类型会有不同的字段
    # 指定的参数配置
    ingest_config = models.JSONField("接入配置", default=dict)

    # 字段清洗规则
    # Example:
    # [
    #     {
    #         "field": "target",
    #         "expr": "event.dimensions[?field=='ip'].value | [0]"
    #     },
    #     {
    #         "field": "tags",
    #         "expr": "merge(event.tag, event.dimensions[?field=='device_name'].{device: value} | [0])"
    #     }
    # ]
    normalization_config = models.JSONField("字段清洗规则", default=list)

    def __str__(self):
        return f"{self.plugin_type}-{self.plugin_display_name}"

    class Meta:
        abstract = True

    @property
    def logo_base64(self):
        """
        logo content with base64 encoding
        :return:
        """
        if not self.logo:
            return ""
        try:
            logo_str = b"".join(self.logo.chunks())
        except Exception:
            return ""
        return base64.b64encode(logo_str)

    def is_active(self):
        return self.status in PluginStatus.active_statuses()

    @property
    def main_type(self):
        """
        插件所属的大类
        """
        if self.plugin_type.endswith("_pull"):
            return PluginMainType.PULL
        return PluginMainType.PUSH

    def get_main_type_display(self):
        main_type = self.main_type
        for name, display in PluginMainType.to_choice():
            if name == main_type:
                return display


class EventPlugin(EventPluginBaseModel):
    """
    事件源源信息（）
    """

    # 基础信息
    plugin_id = models.CharField("插件ID", max_length=64, primary_key=True)

    data_id = models.IntegerField("数据ID", default=0)

    ingest_config = JsonField("接入配置", default=None)

    # 字段清洗规则
    # Example:
    # [
    #     {
    #         "field": "target",
    #         "expr": "event.dimensions[?field=='ip'].value | [0]"
    #     },
    #     {
    #         "field": "tags",
    #         "expr": "merge(event.tag, event.dimensions[?field=='device_name'].{device: value} | [0])"
    #     }
    # ]
    normalization_config = JsonField("字段清洗规则", default=[])

    def list_alert_config(self):
        return AlertConfig.objects.filter(plugin_id=self.plugin_id, plugin_instance_id=0).order_by("id", "order")

    def is_active(self):
        return self.status in PluginStatus.active_statuses()

    class Meta:
        verbose_name = "插件信息"
        verbose_name_plural = "插件信息"


class EventPluginV2(EventPluginBaseModel):
    plugin_id = models.CharField("插件ID", max_length=64, db_index=True)
    version = models.CharField("版本号", max_length=64, db_index=True)
    is_latest = models.BooleanField("是否最新版本", default=False)
    config_params = models.JSONField("插件配置实例信息", default=list)

    # 条件配置清洗规则
    clean_configs = models.JSONField("条件清洗配置", default=list)

    def list_alert_config(self):
        return AlertConfig.objects.filter(plugin_id=self.plugin_id, plugin_instance_id=0).order_by("id", "order")

    class Meta:
        verbose_name = "插件信息V2"
        verbose_name_plural = "插件信息V2"
        unique_together = ("plugin_id", "version")
        db_table = "event_plugin"


class EventPluginInstance(AbstractRecordModel):
    """
    插件安装实例
    """

    plugin_id = models.CharField("插件ID", max_length=64, db_index=True)
    version = models.CharField("插件版本号", max_length=64, db_index=True)
    name = models.CharField("配置名称", max_length=64, default="", blank=True)
    bk_biz_id = models.IntegerField("业务ID", default=0, blank=True, db_index=True)
    data_id = models.IntegerField("数据ID", default=0)
    token = models.TextField("关联信息token", max_length=64, default="")
    config_params = models.JSONField("插件配置实例信息", default=list)
    ingest_config = models.JSONField("插件配置信息", default=dict)
    normalization_config = models.JSONField("字段清洗规则", default=list)

    # 条件配置清洗规则
    clean_configs = models.JSONField("条件清洗配置", default=list)

    class Meta:
        verbose_name = "插件安装信息"
        verbose_name_plural = "插件安装信息"
        db_table = "event_plugin_instance"

    @cached_property
    def event_plugin(self):
        return EventPluginV2.objects.get(plugin_id=self.plugin_id, version=self.version)

    @cached_property
    def collect_type(self):
        """
        接收类型
        """
        return self.ingest_config.get("collect_type")

    @property
    def updatable(self):
        """
        是否有更新
        """
        return not self.event_plugin.is_latest

    def list_alert_config(self):
        return AlertConfig.objects.filter(plugin_id=self.plugin_id, plugin_instance_id__in=[0, self.id]).order_by(
            "id", "order"
        )


class AlertConfig(AbstractRecordModel):
    """
    告警名称配置信息
    告警名称匹配规则仅做匹配
    """

    plugin_id = models.CharField("插件ID", max_length=64, null=False)
    name = models.CharField("告警名称", max_length=64, null=False)

    # 关联插件ID
    plugin_instance_id = models.IntegerField("插件实例ID", default=0)

    # 名称匹配规则
    # [
    #     {
    #         "key": "event.name",
    #         "value": ["^CPU"],
    #         "method": "reg",
    #         "condition": ""
    #     }
    # ]
    rules = JsonField("名称匹配规则", default=[])

    is_manual = models.BooleanField("是否手动添加", default=False)
    order = models.IntegerField("解析排序", default=0)

    def __str__(self):
        return f"{self.plugin_id}-{self.name}"

    class Meta:
        verbose_name = "告警名称配置管理"
        verbose_name_plural = "告警名称配置管理"
