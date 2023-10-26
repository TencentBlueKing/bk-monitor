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

import os

from monitor_web.models import CollectorPluginMeta, PluginVersionHistory
from monitor_web.plugin.signature import load_plugin_signature_manager

pwd = os.path.dirname(__file__)


def signature2db(apps, schema_editor):
    # CollectorPluginMeta = apps.get_model("monitor_web", "CollectorPluginMeta")
    # PluginVersionHistory = apps.get_model("monitor_web", "PluginVersionHistory")
    protocols = ["default", "strict"]
    plugins = CollectorPluginMeta.objects.filter(is_internal=True)
    for plugin in plugins:
        version = PluginVersionHistory.objects.filter(stage="release", plugin=plugin).last()
        p = load_plugin_signature_manager(version)
        version.signature = p.signature(protocols).dumps2python()
        version.save()
