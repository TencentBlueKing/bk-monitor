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
from typing import Type, Dict

from bkmonitor.event_plugin.manager.base import BaseEventPluginManager
from bkmonitor.event_plugin.manager.http_pull import HttpPullManager
from bkmonitor.event_plugin.manager.http_push import HttpPushManager
from bkmonitor.event_plugin.serializers import HttpPullPluginSerializer, HttpPushPluginSerializer, EventPluginSerializer
from bkmonitor.models import EventPluginInstance
from bkmonitor.models.fta.constant import PluginType

_manager_registry: Dict[str, Type[BaseEventPluginManager]] = {}


def register_manager(plugin_type: str, manager_cls: Type[BaseEventPluginManager]):
    _manager_registry[plugin_type] = manager_cls


def get_manager(
    plugin_inst: EventPluginInstance = None, plugin_inst_id: str = None, plugin_type: str = None
) -> BaseEventPluginManager:
    if plugin_inst:
        plugin_type = plugin_inst.event_plugin.plugin_type
    elif plugin_inst_id:
        plugin_inst = EventPluginInstance.objects.get(id=plugin_inst_id)
        plugin_type = plugin_inst.event_plugin.plugin_type
    elif not plugin_type:
        raise ValueError("must provide param `plugin` or `plugin_id`")

    if plugin_type not in _manager_registry:
        raise ValueError("unsupported plugin type: %s" % plugin_type)

    manager_cls = _manager_registry[plugin_type]
    return manager_cls(plugin_inst)


def get_serializer(plugin_type: str, *args, **kwargs) -> EventPluginSerializer:
    serializer_cls = plugin_serializers.get(plugin_type)
    if not serializer_cls:
        raise ValueError("unsupported plugin type: %s" % plugin_type)
    return serializer_cls(*args, **kwargs)


register_manager(PluginType.HTTP_PULL, HttpPullManager)
register_manager(PluginType.HTTP_PUSH, HttpPushManager)

plugin_serializers = {
    PluginType.HTTP_PULL: HttpPullPluginSerializer,
    PluginType.HTTP_PUSH: HttpPushPluginSerializer,
}
