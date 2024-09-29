"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2024 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from monitor_web.models.collecting import CollectConfigMeta
from monitor_web.plugin.constant import PluginType

from .base import BaseInstaller
from .k8s import K8sInstaller
from .node_man import NodeManInstaller


def get_collect_installer(collect_config: CollectConfigMeta, *args, **kwargs) -> BaseInstaller:
    """
    获取插件采集安装器
    """
    if collect_config.plugin.plugin_type == PluginType.K8S:
        return K8sInstaller(collect_config, *args, **kwargs)
    else:
        return NodeManInstaller(collect_config, *args, **kwargs)
