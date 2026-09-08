"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from bkmonitor.nodeman_integration.mode import get_nodeman_integration_mode
from monitor_web.models.collecting import CollectConfigMeta
from monitor_web.plugin.constant import PluginType

from .base import BaseInstaller
from .k8s import K8sInstaller

_NODEMAN_INTEGRATION_MODE = get_nodeman_integration_mode()


if _NODEMAN_INTEGRATION_MODE == "v2":
    from core.drf_resource import api
    from core.errors.api import BKAPIError
    from monitor_web.collecting.constant import CollectStatus

    from .node_man import NodeManInstaller
    from ..utils import fetch_sub_statistics

    def get_collect_installer(collect_config: CollectConfigMeta, *args, **kwargs) -> BaseInstaller:
        """
        获取插件采集安装器
        """
        if collect_config.plugin.plugin_type == PluginType.K8S:
            return K8sInstaller(collect_config, *args, **kwargs)
        else:
            return NodeManInstaller(collect_config, *args, **kwargs)

    def get_collect_status_key(collect_config: CollectConfigMeta) -> int:
        return collect_config.deployment_config.subscription_id

    def fetch_collect_statistics(config_data_list):
        config_by_key, raw_statistics = fetch_sub_statistics(config_data_list)
        statistics = []
        for item in raw_statistics:
            status_counts = {status["status"]: status["count"] for status in item.get("status", [])}
            statistics.append(
                {
                    **item,
                    "key": item["subscription_id"],
                    "error_instance_count": status_counts.get(CollectStatus.FAILED, 0),
                    "total_instance_count": item.get("instances", 0),
                    "pending_instance_count": status_counts.get(CollectStatus.PENDING, 0),
                    "running_instance_count": status_counts.get(CollectStatus.RUNNING, 0),
                }
            )
        return config_by_key, statistics

    def is_collect_task_ready(collect_config: CollectConfigMeta) -> bool:
        subscription_id = collect_config.deployment_config.subscription_id
        if not subscription_id:
            return True
        try:
            return api.node_man.check_task_ready(
                subscription_id=subscription_id,
                task_id_list=collect_config.deployment_config.task_ids,
            )
        except BKAPIError:
            # Older NodeMan deployments do not expose check_task_ready.
            return True

elif _NODEMAN_INTEGRATION_MODE == "v3_fresh":
    from .nodeman_v3.installer import NodeManV3Installer
    from .nodeman_v3.status import NodeManV3CollectStatusService

    _status_service = NodeManV3CollectStatusService()

    def get_collect_installer(collect_config: CollectConfigMeta, *args, **kwargs) -> BaseInstaller:
        """
        获取插件采集安装器
        """
        if collect_config.plugin.plugin_type == PluginType.K8S:
            return K8sInstaller(collect_config, *args, **kwargs)
        else:
            return NodeManV3Installer(collect_config, *args, **kwargs)

    get_collect_status_key = _status_service.status_key
    fetch_collect_statistics = _status_service.fetch_statistics
    is_collect_task_ready = _status_service.is_task_ready
