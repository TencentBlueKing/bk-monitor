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


import json
import os

pwd = os.path.dirname(__file__)


def update_plugin_data(apps, schema_editor):
    with open(os.path.join(pwd, "prometheus_plugins.json"), "r") as fd:
        prometheus_plugins = json.loads(fd.read())

    with open(os.path.join(pwd, "built_in_plugins.json"), "r") as fd:
        built_in_plugins = json.loads(fd.read())

    data = prometheus_plugins + built_in_plugins

    CollectorPluginMeta = apps.get_model("monitor_web", "CollectorPluginMeta")
    CollectorPluginConfig = apps.get_model("monitor_web", "CollectorPluginConfig")
    CollectorPluginInfo = apps.get_model("monitor_web", "CollectorPluginInfo")
    PluginVersionHistory = apps.get_model("monitor_web", "PluginVersionHistory")

    operator_info = {"create_user": "system", "update_user": "system"}

    for config in data:
        config["meta"]["is_internal"] = True
        plugin_meta, _ = CollectorPluginMeta.objects.update_or_create(
            plugin_id="bkplugin_%s" % config["meta"].pop("plugin_id"),
            defaults=dict(config["meta"], **operator_info),
        )
        plugin_info, _ = CollectorPluginInfo.objects.update_or_create(defaults=operator_info, **config["info"])
        plugin_config, _ = CollectorPluginConfig.objects.update_or_create(defaults=operator_info, **config["config"])
        PluginVersionHistory.objects.update_or_create(
            plugin=plugin_meta,
            defaults=dict(config=plugin_config, info=plugin_info, **operator_info),
            **config["version"]
        )
