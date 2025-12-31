"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import os

from django.utils.translation import gettext as _

from core.errors.plugin import PluginParseError
from monitor_web.plugin.manager.base import PluginManager
from monitor_web.plugin.serializers import JmxSerializer


class JMXPluginManager(PluginManager):
    """
    JMX 插件
    """

    config_files = ["env.yaml.tpl", "config.yaml.tpl"]
    templates_dirname = "jmx_templates"
    serializer_class = JmxSerializer

    def _get_debug_config_context(self, config_version, info_version, param, target_nodes):
        collector_data = param["collector"]
        plugin_data = param["plugin"]
        ssl_enabled = plugin_data.get("ssl_enabled", "false")
        context = {
            "config.yaml": {
                "username": plugin_data.pop("username"),
                "password": plugin_data.pop("password"),
                "jmx_url": plugin_data.pop("jmx_url"),
                "ssl_enabled": ssl_enabled,
            },
            "env.yaml": {
                "host": collector_data["host"],
                "port": collector_data["port"],
                "ssl_enabled": ssl_enabled,
                "ssl_trust_store": plugin_data.get("ssl_trust_store", ""),
                "ssl_trust_store_password": plugin_data.get("ssl_trust_store_password", ""),
                "ssl_key_store": plugin_data.get("ssl_key_store", ""),
                "ssl_key_store_password": plugin_data.get("ssl_key_store_password", ""),
            },
            "bkmonitorbeat_debug.yaml": {
                "host": collector_data["host"],
                "port": collector_data["port"],
                "period": collector_data["period"],
                "metric_url": "{}:{}".format(collector_data["host"], collector_data["port"]),
            },
        }
        return context

    def get_deploy_steps_params(self, plugin_version, param, target_nodes):
        collector_params = param["collector"]
        plugin_params = param["plugin"]
        if collector_params.get("port"):
            plugin_params["port"] = collector_params["port"]
        else:
            plugin_params["port"] = "{{ control_info.listen_port }}"
            collector_params["port"] = f"{{{{ step_data.{self.plugin.plugin_id}.control_info.listen_port }}}}"
        plugin_params["host"] = collector_params["host"]
        collector_params["metric_url"] = "{}:{}".format(collector_params["host"], collector_params["port"])
        diff_metrics = plugin_version.config.diff_fields
        collector_params["diff_metrics"] = diff_metrics.split(",") if diff_metrics else []
        deploy_steps = [
            {
                "id": self.plugin.plugin_id,
                "type": "PLUGIN",
                "config": {
                    "plugin_name": self.plugin.plugin_id,
                    "plugin_version": plugin_version.version,
                    "config_templates": [
                        {"name": "config.yaml", "version": str(plugin_version.config_version)},
                        {"name": "env.yaml", "version": str(plugin_version.config_version)},
                    ],
                },
                "params": {"context": plugin_params},
            },
            self._get_bkmonitorbeat_deploy_step("bkmonitorbeat_prometheus.conf", {"context": collector_params}),
        ]
        return deploy_steps

    def _get_remote_stage(self, meta_dict):
        return True

    def _get_collector_json(self, plugin_params):
        file_name = "config.yaml.tpl"
        config_yaml_path = ""
        for filename in self.filename_list:
            if os.path.basename(str(filename)) == file_name:
                config_yaml_path = filename
                break
        if not config_yaml_path:
            raise PluginParseError({"msg": _("无法获取JMX对应的配置文件")})

        content = self._decode_file(self.plugin_configs[config_yaml_path])
        jmx_collector_json = {
            "config_yaml": content,
        }
        return jmx_collector_json
