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

import abc
from typing import Type

from bkmonitor.event_plugin.accessor import EventPluginInstAccessor
from bkmonitor.event_plugin.constant import CollectType
from bkmonitor.event_plugin.serializers import (
    AlertConfigSerializer,
    EventPluginBaseSerializer,
)
from bkmonitor.models import EventPluginInstance
from bkmonitor.utils.cipher import transform_data_id_to_token


class BaseEventPluginManager(metaclass=abc.ABCMeta):
    """
    事件插件管理器
    """

    def __init__(self, plugin_inst: EventPluginInstance):
        self.plugin_inst = plugin_inst
        self.accessor = EventPluginInstAccessor(plugin_inst)

    @classmethod
    def get_serializer_class(cls) -> Type[EventPluginBaseSerializer]:
        raise NotImplementedError

    def get_datasource_option(self) -> dict:
        """
        转换为数据源配置
        """
        serializer_cls = self.get_serializer_class()
        serializer = serializer_cls(self.plugin_inst)
        data = serializer.data

        data.update({"alert_config": AlertConfigSerializer(self.plugin_inst.list_alert_config(), many=True).data})
        normalization_config = [
            {"field": field["field"], "expr": field["expr"], "option": field["option"]}
            for field in data["normalization_config"]
        ]

        option = {
            "plugin_id": data["plugin_id"],
            "plugin_type": self.plugin_inst.event_plugin.plugin_type,
            "bk_biz_id": self.plugin_inst.bk_biz_id,
            "alert_config": data["alert_config"],
            "normalization_config": normalization_config,
            "clean_configs": data["clean_configs"],
        }

        option.update(data["ingest_config"] or {})

        return option

    def access(self):
        """
        接入metadata，并生成data_id
        """
        data_id = self.accessor.access(self.get_datasource_option())
        if data_id == self.plugin_inst.data_id:
            return
        if self.plugin_inst.collect_type == CollectType.BK_COLLECTOR:
            # 仅当data_id发生变化之后才更新
            self.plugin_inst.token = transform_data_id_to_token(
                data_id, bk_biz_id=self.plugin_inst.bk_biz_id, app_name=self.plugin_inst.plugin_id
            )
        self.plugin_inst.data_id = data_id
        self.plugin_inst.save(update_fields=["data_id", "token"])

    def switch(self, is_enabled: bool):
        """
        启停 dataid
        """
        self.accessor.switch_dataid(is_enabled)
        self.plugin_inst.is_enabled = is_enabled
        self.plugin_inst.save(update_fields=["is_enabled"])
