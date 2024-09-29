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

import copy
import json
import os

import pytest
from django.db.models import QuerySet

import settings
from monitor_web.models.plugin import (
    CollectorPluginConfig,
    CollectorPluginInfo,
    CollectorPluginMeta,
    PluginVersionHistory,
)
from monitor_web.plugin.manager import PluginManagerFactory

from .test_base_manager import CURRENT_VERSION_DATA, INFO_DATA

with open(os.path.join(settings.BASE_DIR, "tests/web/plugin/test_data/jmx_plugin.json")) as f:
    PLUGIN_DATA = json.loads(f.read())

with open(os.path.join(settings.BASE_DIR, "tests/web/plugin/test_data/jmx_config.json")) as f:
    CONFIG_DATA = json.loads(f.read())


@pytest.fixture
def update_plugin_manager(mocker):
    create_params = copy.deepcopy(PLUGIN_DATA)
    create_params.pop("plugin_display_name")
    plugin = CollectorPluginMeta(**create_params)
    config = CollectorPluginConfig(**CONFIG_DATA)
    info = CollectorPluginInfo(**INFO_DATA)
    CURRENT_VERSION_DATA.update({"plugin": plugin, "config": config, "info": info})
    version = PluginVersionHistory(**CURRENT_VERSION_DATA)
    mocker.patch.object(PluginVersionHistory.objects, "filter", return_value=QuerySet())
    mocker.patch.object(QuerySet, "last", return_value=version)
    plugin_manager = PluginManagerFactory.get_manager(plugin, "admin")
    return plugin_manager


class TestJmxPlugin(object):
    def test_get_debug_config_context(self, mocker, update_plugin_manager):
        params = {
            "collector": {"period": "10", "port": "5987", "host": "127.0.0.1"},
            "plugin": {"jmx_url": "", "username": "", "password": ""},
        }
        assert update_plugin_manager._get_debug_config_context(1, 1, params) == {
            "bkmonitorbeat_debug.yaml": {"host": "127.0.0.1", "period": "10", "port": "5987"},
            "config.yaml": {"jmx_url": "", "password": "", "username": ""},
            "env.yaml": {"host": "127.0.0.1", "port": "5987"},
        }
