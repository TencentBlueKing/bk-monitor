"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging

from bk_dataview.api import get_or_create_org

logger = logging.getLogger(__name__)

from bkmonitor.models.strategy import (
    StrategyModel,
    DetectModel,
    AlgorithmModel,
    UserGroup,
    DutyRule,
    DutyArrange,
)
from bkmonitor.models import Item, Shield
from bkmonitor.models.fta.action import ActionConfig, ActionPlugin
from bkmonitor.models.fta.assign import AlertAssignGroup, AlertAssignRule
from bk_dataview.models import Dashboard
from monitor_web.models.collecting import CollectConfigMeta
from monitor_web.models.plugin import CollectorPluginMeta
from monitor_web.models.custom_report import CustomTSTable, CustomTSField
from metadata.models.custom_report.time_series import TimeSeriesGroup


from .export_base import BaseExporter, RelationMixin
from .export_utils import model_to_dict


class StrategyExporter(BaseExporter, RelationMixin):
    """
    告警策略导出器
    """

    resource_type = "strategy"
    model_class = StrategyModel

    def export_relations(self, obj, data: dict) -> dict:
        """
        导出关联的 Item、Detect、Algorithm
        """
        # 导出监控项
        items = Item.objects.filter(strategy_id=obj.id)
        data["_relations"] = {"items": self.export_related_queryset(items)}

        # 导出检测配置
        detects = DetectModel.objects.filter(strategy_id=obj.id)
        data["_relations"]["detects"] = self.export_related_queryset(detects)

        # 导出检测算法
        algorithms = AlgorithmModel.objects.filter(strategy_id=obj.id)
        data["_relations"]["algorithms"] = self.export_related_queryset(algorithms)

        return data


class UserGroupExporter(BaseExporter, RelationMixin):
    """
    告警组导出器
    """

    resource_type = "user_group"
    model_class = UserGroup

    def export_relations(self, obj, data: dict) -> dict:
        """
        导出关联的轮班配置（从属资源）

        注意：duty_rules 是 JSONField，存储 DutyRule 的 ID 列表。
        DutyRule 已作为独立资源导出（resources.duty_rule），无需在 _relations 中重复导出。
        全量迁移模式下，ID 保持不变，可直接使用。
        """
        data["_relations"] = {}

        # 导出轮班配置（从属资源）
        duty_arranges = DutyArrange.objects.filter(user_group_id=obj.id)
        data["_relations"]["duty_arranges"] = self.export_related_queryset(duty_arranges)

        # duty_rules（独立资源）已在 resources.duty_rule 中导出，无需重复

        return data


class DutyRuleExporter(BaseExporter):
    """
    轮值规则导出器
    """

    resource_type = "duty_rule"
    model_class = DutyRule


class ActionConfigExporter(BaseExporter):
    """
    处理套餐导出器
    """

    resource_type = "action_config"
    model_class = ActionConfig


class ActionPluginExporter(BaseExporter):
    """
    响应动作插件导出器
    """

    resource_type = "action_plugin"
    model_class = ActionPlugin

    # 使用基类的默认查询逻辑，不需要额外过滤


class AlertAssignExporter(BaseExporter, RelationMixin):
    """
    告警分派导出器
    """

    resource_type = "alert_assign_group"
    model_class = AlertAssignGroup

    def export_relations(self, obj, data: dict) -> dict:
        """
        导出关联的分派规则
        """
        rules = AlertAssignRule.objects.filter(assign_group_id=obj.id)
        data["_relations"] = {"rules": self.export_related_queryset(rules)}
        return data


class ShieldExporter(BaseExporter):
    """
    告警屏蔽导出器

    注意：数据迁移场景导出所有屏蔽记录（包括已禁用的），保证数据完整性
    """

    resource_type = "shield"
    model_class = Shield


class DashboardExporter(BaseExporter):
    """
    仪表盘导出器
    """

    resource_type = "dashboard"
    model_class = Dashboard

    def query_objects(self, bk_biz_ids=None):
        """
        按 org_id 过滤仪表盘
        """
        queryset = self.model_class.objects.all()

        org_ids: list[int] = []
        for bk_biz_id in bk_biz_ids:
            org_name = str(bk_biz_id)  # 将业务ID转为字符串作为组织名称
            org = get_or_create_org(org_name)  # 获取或创建组织
            org_id = org["id"]  # 获取组织的数字ID
            org_ids.append(org_id)

        queryset = queryset.filter(org_id__in=org_ids)
        return queryset


class CollectConfigExporter(BaseExporter, RelationMixin):
    """
    数据采集配置导出器
    """

    resource_type = "collect_config"
    model_class = CollectConfigMeta

    def _export_plugin_version(self, plugin_version) -> dict:
        """
        导出插件版本及其关联的 config 和 info
        """
        from monitor_web.models.plugin import CollectorPluginConfig, CollectorPluginInfo

        version_data = model_to_dict(plugin_version)
        if hasattr(self, "apply_adapters"):
            version_data = self.apply_adapters(version_data)

        # 导出关联的 config (CollectorPluginConfig)
        config_id = plugin_version.config_id
        if config_id:
            config_obj = CollectorPluginConfig.objects.filter(id=config_id).first()
            if config_obj:
                config_data = model_to_dict(config_obj)
                if hasattr(self, "apply_adapters"):
                    config_data = self.apply_adapters(config_data)
                version_data["_config"] = config_data

        # 导出关联的 info (CollectorPluginInfo)
        info_id = plugin_version.info_id
        if info_id:
            info_obj = CollectorPluginInfo.objects.filter(id=info_id).first()
            if info_obj:
                info_data = model_to_dict(info_obj)
                if hasattr(self, "apply_adapters"):
                    info_data = self.apply_adapters(info_data)
                version_data["_info"] = info_data

        return version_data

    def export_relations(self, obj, data: dict) -> dict:
        """
        导出关联的部署配置（DeploymentConfigVersion 及其嵌套数据）
        """
        from monitor_web.models.collecting import DeploymentConfigVersion
        from monitor_web.models.plugin import PluginVersionHistory

        relations = {}

        # 导出部署配置（包含完整嵌套数据，因为 DeploymentConfigVersion 未作为独立资源导出）
        deployment_config_id = obj.deployment_config_id
        if deployment_config_id:
            deployment_config = DeploymentConfigVersion.objects.filter(id=deployment_config_id).first()
            if deployment_config:
                deployment_config_data = model_to_dict(deployment_config)
                if hasattr(self, "apply_adapters"):
                    deployment_config_data = self.apply_adapters(deployment_config_data)

                # 导出关联的 plugin_version (PluginVersionHistory)
                plugin_version_id = deployment_config.plugin_version_id
                if plugin_version_id:
                    plugin_version = PluginVersionHistory.objects.filter(id=plugin_version_id).first()
                    if plugin_version:
                        deployment_config_data["_plugin_version"] = self._export_plugin_version(plugin_version)

                relations["deployment_config"] = deployment_config_data

        if relations:
            data["_relations"] = relations

        return data


class CollectorPluginExporter(BaseExporter):
    """
    采集插件导出器

    注意：数据迁移场景导出所有插件（包括内置插件），保证数据完整性
    """

    resource_type = "collector_plugin"
    model_class = CollectorPluginMeta


class CustomTSTableExporter(BaseExporter, RelationMixin):
    """
    自定义时序表导出器
    """

    resource_type = "custom_ts_table"
    model_class = CustomTSTable

    def export_relations(self, obj, data: dict) -> dict:
        """
        导出关联的字段定义
        """
        fields = CustomTSField.objects.filter(time_series_group_id=obj.time_series_group_id)
        data["_relations"] = {"fields": self.export_related_queryset(fields)}
        return data


class CustomTSGroupExporter(BaseExporter):
    """
    自定义时序分组导出器
    """

    resource_type = "custom_ts_group"
    model_class = TimeSeriesGroup

    def query_objects(self, bk_biz_ids=None):
        """
        按业务 ID 过滤
        """
        queryset = self.model_class.objects.all()

        if bk_biz_ids:
            queryset = queryset.filter(bk_biz_id__in=bk_biz_ids)

        return queryset


# 导出器注册表
EXPORTER_REGISTRY = {
    "strategy": StrategyExporter,
    "user_group": UserGroupExporter,
    "duty_rule": DutyRuleExporter,
    "action_config": ActionConfigExporter,
    "action_plugin": ActionPluginExporter,
    "alert_assign_group": AlertAssignExporter,
    "shield": ShieldExporter,
    "dashboard": DashboardExporter,
    "collect_config": CollectConfigExporter,
    "collector_plugin": CollectorPluginExporter,
    "custom_ts_table": CustomTSTableExporter,
    "custom_ts_group": CustomTSGroupExporter,
}
