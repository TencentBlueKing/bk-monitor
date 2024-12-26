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

from furl import furl

from monitor_web.plugin.constant import ParamMode
from monitor_web.plugin.manager.base import PluginManager
from monitor_web.plugin.serializers import PushgatewaySerializer


class PushgatewayPluginManager(PluginManager):
    """
    BK-Pull 插件
    """

    templates_dirname = "pushgateway_templates"
    serializer_class = PushgatewaySerializer

    def _get_debug_config_context(self, config_version, info_version, param, target_nodes):
        specific_version = self.plugin.get_version(config_version, info_version)
        config_json = specific_version.config.config_json

        # 采集器参数上下文
        collector_data = param["collector"]
        plugin_data = param["plugin"]

        username = collector_data.get("username", "")
        password = collector_data.get("password", "") or ""
        metrics_url = collector_data.get("metrics_url")

        # 对存量数据进行处理
        # 如果 password 为 True 抛出异常让用户修改密码
        # 如果 password 为 False 则在上面转成 ""
        if password is True:
            raise TypeError("Please reset your password")

        if username:
            # 如果用户填写了用户名，则在url中添加基础认证
            url = furl(metrics_url)
            url.username = username
            url.password = password
            metrics_url = url.tostr()

        dms_insert_params = {}

        debug_params = {"metric_url": metrics_url, "period": collector_data["period"]}

        for param in config_json:
            param_name = param["name"]
            param_mode = param["mode"]
            param_value = plugin_data.get(param_name)

            if param_mode == ParamMode.DMS_INSERT:
                # 维度注入参数，更新至labels的模板中
                for dms_key, dms_value in list(param_value.items()):
                    if param["type"] == "host":
                        dms_insert_params[dms_key] = "{{ " + f"cmdb_instance.host.{dms_value} or '-'" + " }}"
                    else:
                        dms_insert_params[dms_key] = (
                            "{{ " + f"cmdb_instance.service.labels['{dms_value}'] or '-'" + " }}"
                        )

        if dms_insert_params:
            debug_params.update(
                {"labels": {"$for": "cmdb_instance.scope", "$item": "scope", "$body": {**dms_insert_params}}}
            )

        context = {
            "bkmonitorbeat_debug.yaml": debug_params,
            "env.yaml": {},
        }
        return context

    def get_deploy_steps_params(self, plugin_version, param, target_nodes):
        collector_params = param["collector"]

        username = collector_params.get("username", "")
        collector_params["metric_url"] = collector_params.pop("metrics_url", "")
        if username:
            # 如果用户填写了用户名，则在url中添加基础认证
            url = furl(collector_params["metric_url"])
            url.username = username
            url.password = collector_params.get("password", "")
            collector_params["metric_url"] = url.tostr()

        diff_metrics = plugin_version.config.diff_fields
        collector_params["diff_metrics"] = diff_metrics.split(",") if diff_metrics else []
        deploy_steps = [
            self._get_bkmonitorbeat_deploy_step("bkmonitorbeat_prometheus.conf", {"context": collector_params})
        ]
        return deploy_steps

    def _get_remote_stage(self, meta_dict):
        return True

    def _get_collector_json(self, plugin_params):
        return {}
