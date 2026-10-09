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

from monitor_web.models.collecting import CollectConfigMeta
from monitor_web.plugin.constant import PluginType

from .base import BaseInstaller, CollectionStatistics
from .k8s import K8sInstaller
from .node_man import NodeManInstaller


def get_collect_installer_class(collect_config: CollectConfigMeta) -> type[BaseInstaller]:
    """统一选择生命周期和结果查询实现；本期非 K8s 采集保持 V2。"""
    if collect_config.collect_type == PluginType.K8S:
        return K8sInstaller
    return NodeManInstaller


def get_collect_installer(collect_config: CollectConfigMeta, *args, **kwargs) -> BaseInstaller:
    return get_collect_installer_class(collect_config)(collect_config, *args, **kwargs)


def fetch_collection_statistics(config_data_list: list[CollectConfigMeta]) -> dict[int, CollectionStatistics]:
    """按安装器分组查询，业务调用方不再处理远端订阅身份。"""
    groups = defaultdict(list)
    for config in config_data_list:
        groups[get_collect_installer_class(config)].append(config)
    result = {}
    for installer_class, configs in groups.items():
        result.update(installer_class.statistics(configs))
    return result
