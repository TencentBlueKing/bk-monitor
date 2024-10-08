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

"""
插件管理
"""


import os

from django.utils.translation import ugettext as _

from bkmonitor.utils.user import get_global_user
from monitor_web.commons.file_manager import PluginFileManager
from monitor_web.models.plugin import CollectorPluginMeta
from monitor_web.plugin.manager.base import PluginManager
from monitor_web.plugin.manager.built_in import BuiltInPluginManager
from monitor_web.plugin.manager.datadog import (
    DataDogPluginFileManager,
    DataDogPluginManager,
)
from monitor_web.plugin.manager.exporter import (
    ExporterPluginFileManager,
    ExporterPluginManager,
)
from monitor_web.plugin.manager.jmx import JMXPluginManager
from monitor_web.plugin.manager.k8s import K8sPluginManager
from monitor_web.plugin.manager.log import LogPluginManager
from monitor_web.plugin.manager.process import ProcessPluginManager
from monitor_web.plugin.manager.pushgateway import PushgatewayPluginManager
from monitor_web.plugin.manager.script import ScriptPluginManager
from monitor_web.plugin.manager.snmp import SNMPPluginManager
from monitor_web.plugin.manager.snmp_trap import SNMPTrapPluginManager

# 当前支持的插件类型
SUPPORTED_PLUGINS = {
    CollectorPluginMeta.PluginType.BUILT_IN: BuiltInPluginManager,
    CollectorPluginMeta.PluginType.DATADOG: DataDogPluginManager,
    CollectorPluginMeta.PluginType.EXPORTER: ExporterPluginManager,
    CollectorPluginMeta.PluginType.JMX: JMXPluginManager,
    CollectorPluginMeta.PluginType.SCRIPT: ScriptPluginManager,
    CollectorPluginMeta.PluginType.PUSHGATEWAY: PushgatewayPluginManager,
    CollectorPluginMeta.PluginType.LOG: LogPluginManager,
    CollectorPluginMeta.PluginType.SNMP_TRAP: SNMPTrapPluginManager,
    CollectorPluginMeta.PluginType.PROCESS: ProcessPluginManager,
    CollectorPluginMeta.PluginType.SNMP: SNMPPluginManager,
    CollectorPluginMeta.PluginType.K8S: K8sPluginManager,
}

FILE_PLUGINS_FACTORY = {
    CollectorPluginMeta.PluginType.BUILT_IN: PluginFileManager,
    CollectorPluginMeta.PluginType.DATADOG: DataDogPluginFileManager,
    CollectorPluginMeta.PluginType.EXPORTER: ExporterPluginFileManager,
    CollectorPluginMeta.PluginType.JMX: PluginFileManager,
    CollectorPluginMeta.PluginType.SCRIPT: PluginFileManager,
    CollectorPluginMeta.PluginType.PUSHGATEWAY: PluginFileManager,
    CollectorPluginMeta.PluginType.SNMP: PluginFileManager,
}


class PluginManagerFactory(object):
    @classmethod
    def get_manager(cls, plugin=None, plugin_type=None, operator="", tmp_path=None) -> PluginManager:
        """
        根据插件ID和插件类型获取对应的插件管理对象
        :param plugin: CollectorPluginMeta对象或id
        :param plugin_type: 插件类型
        :param operator: 操作者
        :param tmp_path: 临时路径
        :rtype: PluginManager
        """
        if tmp_path and not os.path.exists(tmp_path):
            raise IOError(_("文件夹不存在：%s") % tmp_path)

        if not isinstance(plugin, CollectorPluginMeta):
            plugin_id = plugin
            try:
                plugin = CollectorPluginMeta.objects.get(plugin_id=plugin)
            except CollectorPluginMeta.DoesNotExist:
                plugin = CollectorPluginMeta(plugin_id=plugin_id, plugin_type=plugin_type)

        plugin_type = plugin.plugin_type
        if plugin_type not in SUPPORTED_PLUGINS:
            raise KeyError("Unsupported plugin type: %s" % plugin_type)
        plugin_manager_cls = SUPPORTED_PLUGINS[plugin_type]

        if not operator:
            operator = get_global_user()

        return plugin_manager_cls(plugin, operator, tmp_path)


class PluginFileManagerFactory(object):
    @classmethod
    def get_manager(cls, plugin_type=None):
        """
        :param plugin_type:
        :rtype: PluginFileManager
        """
        return FILE_PLUGINS_FACTORY[plugin_type]
