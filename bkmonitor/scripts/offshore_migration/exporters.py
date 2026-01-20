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
        data["_relations"] = {
            "items": self.export_related_queryset(items)
        }
        
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
        导出关联的轮值规则和轮班配置
        """
        data["_relations"] = {}
        
        # 导出轮班配置
        duty_arranges = DutyArrange.objects.filter(user_group_id=obj.id)
        data["_relations"]["duty_arranges"] = self.export_related_queryset(duty_arranges)
        
        # 导出轮值规则（通过 duty_rules 字段关联）
        if hasattr(obj, "duty_rules") and obj.duty_rules:
            duty_rule_ids = obj.duty_rules
            if isinstance(duty_rule_ids, list) and duty_rule_ids:
                duty_rules = DutyRule.objects.filter(id__in=duty_rule_ids)
                data["_relations"]["duty_rules"] = self.export_related_queryset(duty_rules)
        
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
        data["_relations"] = {
            "rules": self.export_related_queryset(rules)
        }
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
    
    def export_relations(self, obj, data: dict) -> dict:
        """
        导出关联的采集插件信息
        """
        try:
            plugin = CollectorPluginMeta.objects.get(
                plugin_id=obj.plugin_id,
                bk_tenant_id=obj.bk_tenant_id
            )
            plugin_data = model_to_dict(plugin)
            if hasattr(self, 'apply_adapters'):
                plugin_data = self.apply_adapters(plugin_data)
            data["_relations"] = {
                "plugin": plugin_data
            }
        except CollectorPluginMeta.DoesNotExist:
            logger.warning(f"Plugin {obj.plugin_id} not found for collect config {obj.id}")
        
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
        data["_relations"] = {
            "fields": self.export_related_queryset(fields)
        }
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

