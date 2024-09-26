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
import shutil

import pytest
from django.conf import settings
from django.db.models import Model
from django.db.models.fields.files import FieldFile
from django.db.models.query import QuerySet
from django.template import Context

from monitor_web.models.plugin import (
    CollectorPluginConfig,
    CollectorPluginInfo,
    CollectorPluginMeta,
    OperatorSystem,
    PluginVersionHistory,
)
from monitor_web.plugin.manager import PluginManagerFactory
from monitor_web.plugin.manager.script import ScriptPluginManager

a = os.path.exists("tests")

with open(os.path.join(settings.BASE_DIR, "tests/web/plugin/test_data/create_data.json")) as f:
    CREATE_DATA = json.loads(f.read())

with open(os.path.join(settings.BASE_DIR, "tests/web/plugin/test_data/update_data.json")) as f:
    UPDATE_DATA = json.loads(f.read())

with open(os.path.join(settings.BASE_DIR, "tests/web/plugin/test_data/plugin.json")) as f:
    PLUGIN_DATA = json.loads(f.read())

with open(os.path.join(settings.BASE_DIR, "tests/web/plugin/test_data/info.json")) as f:
    INFO_DATA = json.loads(f.read())

with open(os.path.join(settings.BASE_DIR, "tests/web/plugin/test_data/config.json")) as f:
    CONFIG_DATA = json.loads(f.read())

with open(os.path.join(settings.BASE_DIR, "tests/web/plugin/test_data/current_version.json")) as f:
    CURRENT_VERSION_DATA = json.loads(f.read())
IMPORT_TMP_PATH = os.path.join(settings.BASE_DIR, "tests/web/plugin/test_data/import_test_package/")


@pytest.fixture
def create_plugin_manager(mocker):
    plugin = CollectorPluginMeta(plugin_id="test_plugin", plugin_type="Script")
    config = CollectorPluginConfig()
    info = CollectorPluginInfo()
    version = PluginVersionHistory(plugin=plugin, config=config, info=info)
    mocker.patch.object(PluginVersionHistory.objects, "filter", return_value=QuerySet())
    mocker.patch.object(QuerySet, "last", return_value=version)
    plugin_manager = PluginManagerFactory.get_manager(plugin, "admin")
    return plugin_manager


@pytest.fixture
def update_plugin_manager(mocker):
    create_params = copy.deepcopy(PLUGIN_DATA)
    create_params.pop("scripts")
    create_params.pop("plugin_display_name")
    plugin = CollectorPluginMeta(**create_params)
    config = CollectorPluginConfig(**CONFIG_DATA)
    info = CollectorPluginInfo(**INFO_DATA)
    CURRENT_VERSION_DATA.update({"plugin": plugin, "config": config, "info": info})
    version = PluginVersionHistory(**CURRENT_VERSION_DATA)
    mocker.patch.object(PluginVersionHistory.objects, "filter", return_value=QuerySet())
    mocker.patch.object(QuerySet, "last", return_value=version)
    plugin_manager = PluginManagerFactory.get_manager(plugin, "admin", tmp_path=IMPORT_TMP_PATH)
    return plugin_manager


@pytest.fixture
def mock_save(mocker):
    mocker.patch.object(Model, "save", return_value=None)
    mocker.patch.object(FieldFile, "save", return_value=None)


def new_version(plugin_obj, config_version=None, info_version=None):
    plugin = CollectorPluginMeta(plugin_id="test_plugin", plugin_type="Exporter")
    config = CollectorPluginConfig()
    info = CollectorPluginInfo()
    clear_version = PluginVersionHistory(plugin=plugin, config=config, info=info)
    clear_version.config_version = config_version
    clear_version.info_version = info_version
    return clear_version


class TestBaseManager(object):
    CREATE_DATA = CREATE_DATA
    UPDATE_DATA = UPDATE_DATA
    PLUGIN_DATA = PLUGIN_DATA
    INFO_DATA = INFO_DATA
    CONFIG_DATA = CONFIG_DATA
    CURRENT_VERSION_DATA = CURRENT_VERSION_DATA

    def test_create_version(self, mocker, create_plugin_manager, mock_save):
        mocker.patch.object(CollectorPluginMeta, "generate_version", return_value=create_plugin_manager.version)
        version, need_debug = create_plugin_manager.create_version(self.CREATE_DATA)
        assert version.config.config2dict() == {
            "collector_json": {
                "windows": {"file_id": 1, "file_name": "test_exporter", "md5": "7c1d4ddacd44f1fcee4cf353a54c50e6"}
            },
            "config_json": [],
            "is_support_remote": False,
        }
        assert version.info.info2dict() == {
            "metric_json": [],
            "description_md": "this is a test",
            "plugin_display_name": "test_plugin",
            "logo": "",
        }
        assert version.config_version == 1
        assert version.info_version == 1
        assert version.stage == "unregister"
        assert version.signature == ""
        assert need_debug is True

    def test_update_version(self, update_plugin_manager, mock_save, mocker):
        mocker.patch.object(CollectorPluginMeta, "generate_version", new_version)
        version, need_debug = update_plugin_manager.update_version(self.UPDATE_DATA)
        assert version.info_version == 2
        assert version.config_version == 2
        assert need_debug is True
        assert version.version_log == "this is a test"

    def test_make_package(self, update_plugin_manager, mocker):
        try:
            update_plugin_manager.tmp_path = "tests/web/plugin/tmp_path"
            update_plugin_manager.tmp_path = "tmp_path"
            mocker.patch.object(OperatorSystem.objects, "os_type_list", return_value=["windows", "linux", "aix"])
            return_value = update_plugin_manager.make_package()
            assert os.path.basename(return_value) == "test_plugin.tgz"
        finally:
            shutil.rmtree(update_plugin_manager.tmp_path)

    def test_get_context(self, update_plugin_manager):
        assert update_plugin_manager._get_context() == Context(
            {
                "metric_json": [
                    {
                        "fields": [
                            {
                                "name": "a",
                                "is_active": True,
                                "is_diff_metric": False,
                                "type": "double",
                                "monitor_type": "metric",
                                "unit": "",
                                "description": "a",
                            }
                        ],
                        "table_name": "default",
                        "table_desc": "默认分类",
                    }
                ],
                "plugin_id": "test_plugin",
                "plugin_display_name": "test_plugin",
                "version": "1.1",
                "config_version": 1,
                "plugin_type": "Script",
                "tag": "办公应用",
                "description_md": "this is a test",
                "config_json": [
                    {"default": "", "type": "text", "description": "", "name": "param_pos_cmd", "mode": "opt_cmd"},
                    {"default": "", "type": "text", "description": "", "name": "params_env", "mode": "env"},
                    {"default": "", "type": "text", "description": "", "name": "params_opt_cmd", "mode": "opt_cmd"},
                ],
                "collector_json": {
                    "windows": {
                        "script_content_base64": "QGVjaG8gb2ZmDQplY2hvIDExMQ==",
                        "type": "bat",
                        "filename": "test_plugin.bat",
                    }
                },
                "signature": "",
                "is_support_remote": False,
                "version_log": "",
            }
        )

    def test_start_debug(self, update_plugin_manager, mocker):
        get_debug_config_context_mock = mocker.patch.object(
            ScriptPluginManager,
            "_get_debug_config_context",
            return_value={
                "bkmonitorbeat_debug.yaml": {"host": "127.0.0.1", "period": "10"},
                "env.yaml": {"cmd_args": "23"},
            },
        )
        render_config_template_mock = mocker.patch(
            "monitor_web.plugin.manager.base.api.node_man.render_config_template",
            side_effect=[{"id": 1}, {"id": 2}, {"id": 3}],
        )
        start_debug_mock = mocker.patch(
            "monitor_web.plugin.manager.base.api.node_man.start_debug", return_value={"task_id": 11}
        )
        start_debug_params = {"collector": {"host": "127.0.0.1", "period": "10"}, "plugin": {"host_num": "23"}}
        start_debug_host_info = {"bk_cloud_id": 0, "ip": "127.0.0.2", "bk_biz_id": 2}
        assert update_plugin_manager.start_debug(1, 1, start_debug_params, start_debug_host_info) == {"task_id": 11}

        get_debug_config_context_mock.assert_called_once_with(
            1, 1, {"collector": {"host": "127.0.0.1", "period": "10"}, "plugin": {"host_num": "23"}}
        )
        render_config_template_mock.assert_any_call(
            {
                "plugin_name": "test_plugin",
                "plugin_version": "*",
                "name": "env.yaml",
                "version": 1,
                "data": {"cmd_args": "23"},
            }
        )
        render_config_template_mock.assert_any_call(
            {
                "plugin_name": "test_plugin",
                "plugin_version": "*",
                "name": "bkmonitorbeat_debug.yaml",
                "version": 1,
                "data": {"host": "127.0.0.1", "period": "10"},
            }
        )
        start_debug_mock.assert_called_once_with(
            {
                "plugin_name": "test_plugin",
                "version": "1.1",
                "config_ids": [1, 2],
                "host_info": {"bk_cloud_id": 0, "ip": "127.0.0.2", "bk_biz_id": 2},
            }
        )

    def test_stop_debug(self, update_plugin_manager, mocker):
        stop_debug_mock = mocker.patch("monitor_web.plugin.manager.base.api.node_man.stop_debug", return_value=True)
        assert update_plugin_manager.stop_debug(11) is True
        stop_debug_mock.assert_called_once_with(task_id=11)

    def test_query_debug_install(self, update_plugin_manager, mocker):
        query_debug_mock = mocker.patch(
            "monitor_web.plugin.manager.base.api.node_man.query_debug",
            return_value={"status": "INSTALL", "message": "installing", "step": ""},
        )
        assert update_plugin_manager.query_debug(11) == {"status": "INSTALL", "log_content": "installing"}
        query_debug_mock.assert_called_once_with(task_id=11)

    def test_query_debug_failed(self, update_plugin_manager, mocker):
        query_debug_mock = mocker.patch(
            "monitor_web.plugin.manager.base.api.node_man.query_debug",
            return_value={"status": "FAILED", "message": "is_failed"},
        )
        assert update_plugin_manager.query_debug(11) == {"status": "FAILED", "log_content": "is_failed"}
        query_debug_mock.assert_called_once_with(task_id=11)

    def test_query_debug_success(self, update_plugin_manager, mocker):
        query_debug_mock = mocker.patch(
            "monitor_web.plugin.manager.base.api.node_man.query_debug",
            return_value={"status": "SUCCESS", "message": "is_success"},
        )
        assert update_plugin_manager.query_debug(11) == {"status": "SUCCESS", "log_content": "is_success"}
        query_debug_mock.assert_called_once_with(task_id=11)

    def test_query_debug_process(self, update_plugin_manager, mocker):
        query_debug_mock = mocker.patch(
            "monitor_web.plugin.manager.base.api.node_man.query_debug",
            return_value={"status": "DEBUG", "message": "FETCH_DATA", "step": "DEBUG_PROCESS"},
        )
        assert update_plugin_manager.query_debug(11) == {"status": "FETCH_DATA", "log_content": "FETCH_DATA"}
        query_debug_mock.assert_called_once_with(task_id=11)

    def test_release_config(self, update_plugin_manager, mocker):
        release_config_mock = mocker.patch("monitor_web.plugin.manager.base.api.node_man.release_config")
        update_plugin_manager._release_config(1, 1, "env.yaml")
        release_config_mock.assert_called_once_with(
            {"plugin_name": "test_plugin", "plugin_version": "1_1", "name": "env.yaml", "version": 1}
        )

    def test_get_tmp_version(self, update_plugin_manager, mocker):
        assert update_plugin_manager.get_tmp_version() == update_plugin_manager.version
