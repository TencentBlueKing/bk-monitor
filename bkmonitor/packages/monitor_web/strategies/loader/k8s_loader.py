"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from bkmonitor.models import StrategyLabel
from constants.alert import DEFAULT_NOTICE_MESSAGE_TEMPLATE
from core.drf_resource import api, resource
from monitor_web.strategies.constant import (
    DEFAULT_ALARM_STRATEGY_ATTR_NAME_K8S,
    DEFAULT_ALARM_STRATEGY_LOADER_TYPE_K8S,
    K8S_BUILTIN_LABEL,
)
from monitor_web.strategies.default_settings import default_strategy_settings
from monitor_web.strategies.loader.base import DefaultAlarmStrategyLoaderBase
from monitor_web.strategies.user_groups import get_or_create_ops_notice_group

__all__ = ["K8sDefaultAlarmStrategyLoader"]


class K8sDefaultAlarmStrategyLoader(DefaultAlarmStrategyLoaderBase):
    """加载k8s默认告警策略"""

    CACHE = set()
    LOADER_TYPE = DEFAULT_ALARM_STRATEGY_LOADER_TYPE_K8S
    STRATEGY_ATTR_NAME = DEFAULT_ALARM_STRATEGY_ATTR_NAME_K8S

    def has_default_strategy_for_v1(self) -> bool:
        """第一个版本的内置业务是否已经接入 ."""
        # 获得存在 k8s_系统内置 标签的业务ID
        return bool(
            StrategyLabel.objects.filter(bk_biz_id=self.bk_biz_id, label_name__contains=K8S_BUILTIN_LABEL).exists()
        )

    def get_default_strategy(self):
        """获得默认告警策略 ."""
        strategies_list = default_strategy_settings.DEFAULT_K8S_STRATEGIES_LIST
        if not strategies_list:
            return []
        return strategies_list

    def check_before_set_cache(self) -> bool:
        # 判断业务下是否有集群
        clusters = api.kubernetes.fetch_k8s_cluster_list(
            {"bk_tenant_id": self.bk_tenant_id, "bk_biz_id": self.bk_biz_id}
        )
        return bool(clusters)

    def get_notice_group(self, config_type: str | None = None) -> list:
        """获得告警通知组 ."""
        notice_group_ids = self.notice_group_cache.get(config_type)
        if not notice_group_ids:
            notice_group_id = get_or_create_ops_notice_group(self.bk_biz_id)
            notice_group_ids = [notice_group_id]
            self.notice_group_cache[config_type] = notice_group_ids
        return notice_group_ids

    def load_strategies(self, strategies: list) -> list:
        """加载k8s默认告警策略 ."""
        strategy_config_list = []
        for default_config in strategies:
            # 根据配置类型获得通知组ID
            config_type = default_config.get("type")
            notice_group_ids = self.get_notice_group(config_type)
            if not notice_group_ids:
                continue
            detects = default_config.get("detects")
            notice = default_config.get("notice")
            notice["user_groups"] = notice_group_ids
            notice["config"]["template"] = DEFAULT_NOTICE_MESSAGE_TEMPLATE
            items = default_config.get("items")
            name = str(default_config.get("name"))
            labels = default_config.get("labels")
            if not labels:
                labels = [K8S_BUILTIN_LABEL]
            strategy_config = {
                "bk_biz_id": self.bk_biz_id,
                "name": name,
                "source": "bk_monitorv3",
                "scenario": "kubernetes",
                "type": "monitor",
                "labels": labels,
                "detects": detects,
                "items": items,
                "notice": notice,
                "actions": [],
            }

            # 保存策略
            resource.strategies.save_strategy_v2(**strategy_config)

            strategy_config_list.append(strategy_config)

        return strategy_config_list
