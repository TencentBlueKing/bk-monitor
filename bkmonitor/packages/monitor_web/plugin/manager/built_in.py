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


from monitor_web.plugin.manager.base import PluginManager


class BuiltInPluginManager(PluginManager):
    """
    内置插件
    """

    def make_package(self, **kwargs):
        return ""

    def _get_debug_config_context(self, config_version, info_version, param, target_nodes):
        pass

    def _get_remote_stage(self, meta_dict):
        return True

    def _get_collector_json(self, plugin_params):
        return {}

    def get_deploy_steps_params(self, plugin_version, param, target_nodes):
        return []

    @staticmethod
    def release_collector_plugin(current_version):
        current_version.stage = "release"
        current_version.is_packaged = True
        current_version.save()

    def delete_result_table(self, current_version):
        pass
