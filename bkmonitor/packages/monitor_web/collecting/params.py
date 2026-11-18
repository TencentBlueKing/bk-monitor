"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from copy import deepcopy

from monitor_web.models import CollectConfigMeta


def stored_detail(config: CollectConfigMeta):
    """按源部署的字段定义脱敏，沿用该配置版本对应的已发布插件详情。"""
    source = config.deployment_config
    params = deepcopy(source.params)
    for field in source.plugin_version.config.config_json:
        if field["type"] not in ("password", "encrypt"):
            continue
        mode = "collector" if field["mode"] == "collector" else "plugin"
        key = field.get("key", field["name"])
        present = bool(params.get(mode, {}).get(key) or field["default"])
        params[mode][field["name"]] = present
        if key in params[mode]:
            params[mode][key] = present

    release = config.plugin.get_release_ver_by_config_ver(source.plugin_version.config_version)
    return params, release.get_plugin_version_detail()


def update_password_inplace(data: dict, config_meta: CollectConfigMeta) -> None:
    """将密码参数的值替换为实际值。"""
    config_params = config_meta.plugin.current_version.config.config_json
    deployment_params = config_meta.deployment_config.params

    for param in config_params:
        if param["type"] not in ["password", "encrypt"]:
            continue

        param_name = param["name"]
        param_mode = "plugin" if param["mode"] != "collector" else "collector"
        received_password = data["params"][param_mode].get(param_name)

        # mode 为 "plugin" 时，如果密码不改变，不会传入，获取到 None
        # mode 为 "collector" 时，如果密码不改变，传入值为 bool 类型（由详情接口返回的）
        # 这两种情况要替换为实际值（默认值兜底）
        if isinstance(received_password, type(None) | bool):
            default_password = param["default"]
            actual_password = deployment_params[param_mode].get(param_name, default_password)
            data["params"][param_mode][param_name] = actual_password
