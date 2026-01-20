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

from .import_base import BaseImporter, RelationImportMixin


class StrategyImporter(BaseImporter, RelationImportMixin):
    """
    告警策略导入器
    """
    resource_type = "strategy"
    model_class = StrategyModel
    
    def import_relations(self, obj, relations: dict):
        """
        导入关联的 Item、Detect、Algorithm
        """
        # 导入监控项
        if "items" in relations:
            self.import_related_queryset(
                obj, "items", relations["items"], Item, "strategy_id"
            )
        
        # 导入检测配置
        if "detects" in relations:
            self.import_related_queryset(
                obj, "detects", relations["detects"], DetectModel, "strategy_id"
            )
        
        # 导入检测算法
        if "algorithms" in relations:
            self.import_related_queryset(
                obj, "algorithms", relations["algorithms"], AlgorithmModel, "strategy_id"
            )


class UserGroupImporter(BaseImporter, RelationImportMixin):
    """
    告警组导入器
    """
    resource_type = "user_group"
    model_class = UserGroup
    
    def import_relations(self, obj, relations: dict):
        """
        导入关联的轮值规则和轮班配置
        """
        # 导入轮班配置
        if "duty_arranges" in relations:
            self.import_related_queryset(
                obj, "duty_arranges", relations["duty_arranges"], DutyArrange, "user_group_id"
            )
        
        # 导入轮值规则（通过 duty_rules 字段关联）
        if "duty_rules" in relations:
            # duty_rules 是 JSONField，需要更新 obj.duty_rules
            duty_rule_data = relations["duty_rules"]
            duty_rule_ids = []
            for rule_data in duty_rule_data:
                # 移除元数据
                rule_data = {k: v for k, v in rule_data.items() if k != "_metadata"}
                
                # 应用适配器
                rule_data = self.adapter_manager.apply_adapters(rule_data)
                # 解析外键
                rule_data = self._resolve_foreign_keys_for_model(rule_data, DutyRule)
                
                # 创建轮值规则
                try:
                    rule = DutyRule.objects.create(**rule_data)
                    duty_rule_ids.append(rule.id)
                except Exception as e:
                    logger.error(f"Failed to import duty_rule for user_group {obj.id}: {e}", exc_info=True)
            
            # 更新 user_group 的 duty_rules 字段
            if duty_rule_ids:
                obj.duty_rules = duty_rule_ids
                obj.save()


class DutyRuleImporter(BaseImporter):
    """
    轮值规则导入器
    """
    resource_type = "duty_rule"
    model_class = DutyRule


class ActionConfigImporter(BaseImporter):
    """
    处理套餐导入器
    """
    resource_type = "action_config"
    model_class = ActionConfig


class ActionPluginImporter(BaseImporter):
    """
    响应动作插件导入器
    """
    resource_type = "action_plugin"
    model_class = ActionPlugin


class AlertAssignImporter(BaseImporter, RelationImportMixin):
    """
    告警分派导入器
    """
    resource_type = "alert_assign_group"
    model_class = AlertAssignGroup
    
    def import_relations(self, obj, relations: dict):
        """
        导入关联的分派规则
        """
        if "rules" in relations:
            self.import_related_queryset(
                obj, "rules", relations["rules"], AlertAssignRule, "assign_group_id"
            )


class ShieldImporter(BaseImporter):
    """
    告警屏蔽导入器
    """
    resource_type = "shield"
    model_class = Shield


class DashboardImporter(BaseImporter):
    """
    仪表盘导入器
    """
    resource_type = "dashboard"
    model_class = Dashboard
    
    def _check_conflict(self, data: dict):
        """
        检查仪表盘冲突（使用 org_id + folder_id + title 作为唯一标识）
        根据数据库唯一键约束: uk_org_folder_title
        """
        org_id = data.get("org_id")
        folder_id = data.get("folder_id", 0)  # 默认值为 0
        title = data.get("title")
        
        if title and org_id is not None:
            try:
                return self.model_class.objects.get(
                    org_id=org_id,
                    folder_id=folder_id,
                    title=title
                )
            except self.model_class.DoesNotExist:
                pass
        
        return None


class CollectConfigImporter(BaseImporter, RelationImportMixin):
    """
    数据采集配置导入器
    """
    resource_type = "collect_config"
    model_class = CollectConfigMeta
    
    def import_single(self, data: dict) -> Model:
        """
        导入单个对象，特殊处理 deployment_config 的循环依赖
        """
        # 获取原始ID
        original_id = data.get("_metadata", {}).get("original_id")
        
        # 1. 应用导入适配器
        data = self.adapter_manager.apply_adapters(data)
        
        # 2. 处理 deployment_config（从 _relations 中获取）
        deployment_config_data = None
        if "_relations" in data and "deployment_config" in data["_relations"]:
            deployment_config_data = data["_relations"].pop("deployment_config")
        
        # 3. 移除 deployment_config 字段（先不设置，避免循环依赖）
        deployment_config_id = data.pop("deployment_config", None)
        deployment_config_id_field = data.pop("deployment_config_id", None)
        
        # 4. 解析外键字段（将原始ID转换为新ID）
        data = self._resolve_foreign_keys(data)
        
        # 5. 检查冲突
        existing_obj = self._check_conflict(data)
        if existing_obj:
            obj = self._handle_conflict(data, existing_obj)
        else:
            # 6. 创建对象（不设置 deployment_config）
            obj = self._create_object(data)
        
        # 7. 创建 DeploymentConfigVersion（如果存在）
        if deployment_config_data:
            from monitor_web.models.collecting import DeploymentConfigVersion
            # 移除元数据和主键
            deployment_config_data = {k: v for k, v in deployment_config_data.items() 
                                     if k not in ["_metadata", "id"]}
            
            # 设置 config_meta_id 为新创建的 CollectConfigMeta 的ID
            deployment_config_data["config_meta_id"] = obj.id
            
            # 应用适配器
            deployment_config_data = self.adapter_manager.apply_adapters(deployment_config_data)
            
            # 解析外键（plugin_version 等）
            deployment_config_data = self._resolve_foreign_keys_for_model(
                deployment_config_data, DeploymentConfigVersion
            )
            
            # 创建 DeploymentConfigVersion
            try:
                deployment_config = DeploymentConfigVersion.objects.create(**deployment_config_data)
                # 更新 CollectConfigMeta.deployment_config
                obj.deployment_config = deployment_config
                obj.save()
            except Exception as e:
                logger.error(f"Failed to create deployment_config for collect_config {obj.id}: {e}", exc_info=True)
        
        # 8. 记录ID映射
        new_id = self._get_primary_key_value(obj)
        if original_id is not None:
            self.id_mapper.add_mapping(self.resource_type, original_id, new_id)
        
        # 9. 导入关联数据（plugin 等）
        relations = data.get("_relations", {})
        if relations:
            self.import_relations(obj, relations)
        
        return obj
    
    def import_relations(self, obj, relations: dict):
        """
        导入关联的采集插件信息
        """
        if "plugin" in relations:
            plugin_data = relations["plugin"]
            # 移除元数据
            plugin_data = {k: v for k, v in plugin_data.items() if k != "_metadata"}
            
            # 应用适配器
            plugin_data = self.adapter_manager.apply_adapters(plugin_data)
            # 解析外键
            plugin_data = self._resolve_foreign_keys_for_model(plugin_data, CollectorPluginMeta)
            
            # 检查插件是否已存在
            plugin_id = plugin_data.get("plugin_id")
            bk_tenant_id = plugin_data.get("bk_tenant_id")
            
            if plugin_id and bk_tenant_id:
                try:
                    plugin = CollectorPluginMeta.objects.get(
                        plugin_id=plugin_id,
                        bk_tenant_id=bk_tenant_id
                    )
                    logger.info(f"Plugin {plugin_id} already exists, skipping import")
                except CollectorPluginMeta.DoesNotExist:
                    # 创建插件
                    try:
                        CollectorPluginMeta.objects.create(**plugin_data)
                        logger.info(f"Created plugin {plugin_id}")
                    except Exception as e:
                        logger.error(f"Failed to import plugin {plugin_id}: {e}", exc_info=True)


class CollectorPluginImporter(BaseImporter):
    """
    采集插件导入器
    """
    resource_type = "collector_plugin"
    model_class = CollectorPluginMeta
    
    def _check_conflict(self, data: dict):
        """
        检查插件冲突（使用 plugin_id + bk_tenant_id 作为唯一标识）
        """
        plugin_id = data.get("plugin_id")
        bk_tenant_id = data.get("bk_tenant_id")
        
        if plugin_id and bk_tenant_id:
            try:
                return self.model_class.objects.get(
                    plugin_id=plugin_id,
                    bk_tenant_id=bk_tenant_id
                )
            except self.model_class.DoesNotExist:
                pass
        
        return None


class CustomTSTableImporter(BaseImporter, RelationImportMixin):
    """
    自定义时序表导入器
    """
    resource_type = "custom_ts_table"
    model_class = CustomTSTable
    
    def _create_object(self, data: dict):
        """
        创建对象，特殊处理 time_series_group_id（既是主键也是外键）
        """
        # 获取主键字段名
        pk_field = self._get_primary_key_field(self.model_class)
        
        # time_series_group_id 是主键，也是外键，需要从ID映射中获取
        # 如果已经通过 _resolve_foreign_keys 映射，应该已经有新ID
        if pk_field in data and data[pk_field] is not None:
            # 移除元数据、关联数据和所有以 _ 开头的内部字段
            import_data = {k: v for k, v in data.items() if not k.startswith("_")}
            # 确保 time_series_group_id 被包含
            import_data[pk_field] = data[pk_field]
        else:
            # 如果映射失败，抛出错误
            raise ValueError(f"time_series_group_id is required but not found or mapped in data")
        
        # 创建对象
        obj = self.model_class.objects.create(**import_data)
        return obj
    
    def import_relations(self, obj, relations: dict):
        """
        导入关联的字段定义
        """
        if "fields" in relations:
            # 获取主键字段名（time_series_group_id）
            pk_field = obj._meta.pk
            new_id = getattr(obj, pk_field.name)
            
            for field_data in relations["fields"]:
                # 移除元数据
                field_data = {k: v for k, v in field_data.items() if k != "_metadata"}
                
                # 应用适配器
                field_data = self.adapter_manager.apply_adapters(field_data)
                # 解析外键（关联到主对象）
                field_data["time_series_group_id"] = new_id
                # 解析其他外键
                field_data = self._resolve_foreign_keys_for_model(field_data, CustomTSField)
                
                # 创建字段
                try:
                    CustomTSField.objects.create(**field_data)
                except Exception as e:
                    logger.error(f"Failed to import field for custom_ts_table {new_id}: {e}", exc_info=True)


class CustomTSGroupImporter(BaseImporter):
    """
    自定义时序分组导入器
    """
    resource_type = "custom_ts_group"
    model_class = TimeSeriesGroup
    
    def _check_conflict(self, data: dict):
        """
        检查时序分组冲突（使用 time_series_group_name + bk_biz_id 作为唯一标识）
        """
        name = data.get("time_series_group_name")
        bk_biz_id = data.get("bk_biz_id")
        
        if name and bk_biz_id is not None:
            try:
                return self.model_class.objects.get(
                    time_series_group_name=name,
                    bk_biz_id=bk_biz_id
                )
            except self.model_class.DoesNotExist:
                pass
        
        return None


# 导入器注册表
IMPORTER_REGISTRY = {
    "strategy": StrategyImporter,
    "user_group": UserGroupImporter,
    "duty_rule": DutyRuleImporter,
    "action_config": ActionConfigImporter,
    "action_plugin": ActionPluginImporter,
    "alert_assign_group": AlertAssignImporter,
    "shield": ShieldImporter,
    "dashboard": DashboardImporter,
    "collect_config": CollectConfigImporter,
    "collector_plugin": CollectorPluginImporter,
    "custom_ts_table": CustomTSTableImporter,
    "custom_ts_group": CustomTSGroupImporter,
}
