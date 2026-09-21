"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from collections import defaultdict

from bk_monitor_base.nodeman import CollectionStatistics

from monitor_web.models.collecting import CollectConfigMeta
from monitor_web.plugin.constant import PluginType

from .base import BaseInstaller
from .k8s import K8sInstaller
from .node_man import NodeManInstaller


def get_collect_installer_class(collect_config: CollectConfigMeta) -> type[BaseInstaller]:
    """按采集类型选择部署和结果能力，当前节点管理采集统一使用 V2。"""
    if collect_config.collect_type == PluginType.K8S:
        return K8sInstaller
    return NodeManInstaller


def get_collect_installer(collect_config: CollectConfigMeta, *args, **kwargs) -> BaseInstaller:
    """沿用安装器扩展点，统一生命周期、执行详情和状态查询的后端。"""
    return get_collect_installer_class(collect_config)(collect_config, *args, **kwargs)


def fetch_collection_statistics(config_data_list: list[CollectConfigMeta]) -> dict[int, CollectionStatistics]:
    """按安装器批量查询，业务调用方不再处理远端订阅身份。"""
    groups = defaultdict(list)
    for config in config_data_list:
        groups[get_collect_installer_class(config)].append(config)
    result = {}
    for installer_class, configs in groups.items():
        result.update(installer_class.statistics(configs))
    return result
