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
        from scripts.offshore_migration.import_offshore_data.import_utils import generate_import_hash
        
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
                # 获取原始 ID
                original_id = rule_data.get("_metadata", {}).get("original_id")
                
                # 生成导入标记（与 DutyRuleImporter 保持一致）
                import_hash = generate_import_hash(rule_data)
                
                # 1. 优先通过导入标记查找已存在的 duty_rule
                existing_rule = None
                if import_hash:
                    try:
                        existing_rule = DutyRule.objects.get(hash=import_hash)
                        duty_rule_ids.append(existing_rule.id)
                        logger.debug(f"Found existing duty_rule {existing_rule.id} by import hash for user_group {obj.id}")
                        continue
                    except DutyRule.DoesNotExist:
                        pass
                
                # 2. 尝试从 ID 映射中获取新的 duty_rule_id
                new_duty_rule_id = None
                if original_id is not None:
                    new_duty_rule_id = self.id_mapper.get_new_id("duty_rule", original_id)
                
                # 如果找到了映射的 ID，说明 duty_rule 已经被导入过了
                if new_duty_rule_id is not None:
                    duty_rule_ids.append(new_duty_rule_id)
                    logger.debug(f"Using existing duty_rule {new_duty_rule_id} (original_id={original_id}) for user_group {obj.id}")
                    continue
                
                # 3. 尝试通过 name + bk_biz_id 查找已存在的 duty_rule
                name = rule_data.get("name")
                bk_biz_id = rule_data.get("bk_biz_id")
                if name and bk_biz_id is not None:
                    try:
                        existing_rule = DutyRule.objects.filter(
                            name=name, 
                            bk_biz_id=bk_biz_id
                        ).order_by('-create_time').first()
                        
                        if existing_rule:
                            duty_rule_ids.append(existing_rule.id)
                            # 记录 ID 映射
                            if original_id is not None:
                                self.id_mapper.add_mapping("duty_rule", original_id, existing_rule.id)
                            logger.debug(f"Found existing duty_rule {existing_rule.id} (name={name}) for user_group {obj.id}")
                            continue
                    except Exception as e:
                        logger.debug(f"Error finding existing duty_rule: {e}")
                
                # 4. 如果都没找到，则创建新的 duty_rule
                # 移除元数据、主键字段和所有以 _ 开头的内部字段
                rule_data = {k: v for k, v in rule_data.items() if not k.startswith("_") and k != "id"}
                
                # 应用适配器
                rule_data = self.adapter_manager.apply_adapters(rule_data)
                # 解析外键
                rule_data = self._resolve_foreign_keys_for_model(rule_data, DutyRule)
                
                # 添加导入标记到 hash 字段
                if import_hash and 'hash' not in rule_data:
                    rule_data['hash'] = import_hash
                
                # 创建轮值规则
                try:
                    rule = DutyRule.objects.create(**rule_data)
                    duty_rule_ids.append(rule.id)
                    # 记录 ID 映射
                    if original_id is not None:
                        self.id_mapper.add_mapping("duty_rule", original_id, rule.id)
                    logger.info(f"Created new duty_rule {rule.id} (name={rule.name}) for user_group {obj.id}")
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
    
    def _check_conflict(self, data: dict):
        """
        检查轮值规则冲突
        优先使用导入标记（hash字段）检查，避免重复导入
        """
        from scripts.offshore_migration.import_offshore_data.import_utils import generate_import_hash
        
        # 1. 首先检查是否已经通过导入标记导入过
        import_hash = generate_import_hash(data)
        if import_hash:
            try:
                existing = self.model_class.objects.get(hash=import_hash)
                logger.debug(f"Found existing {self.resource_type} by import hash: {existing.id}")
                return existing
            except self.model_class.DoesNotExist:
                pass
        
        # 2. 其次使用 name + bk_biz_id 检查（兼容旧数据）
        name = data.get("name")
        bk_biz_id = data.get("bk_biz_id")
        
        if name and bk_biz_id is not None:
            try:
                # 查找最近创建的同名记录（可能是刚导入的）
                existing = self.model_class.objects.filter(
                    name=name,
                    bk_biz_id=bk_biz_id
                ).order_by('-create_time').first()
                
                if existing:
                    logger.debug(f"Found existing {self.resource_type} by name+biz_id: {existing.id}")
                    return existing
            except Exception as e:
                logger.debug(f"Error checking conflict by name+biz_id: {e}")
        
        return None
    
    def _create_object(self, data: dict):
        """
        创建对象（添加导入标记）
        """
        from scripts.offshore_migration.import_offshore_data.import_utils import generate_import_hash
        
        # 生成导入标记并添加到 hash 字段
        import_hash = generate_import_hash(data)
        if import_hash and 'hash' not in data:
            data['hash'] = import_hash
        
        return super()._create_object(data)


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
    
    def import_single(self, data: dict):
        """
        导入单个对象，特殊处理 deployment_config 的循环依赖
        
        由于 CollectConfigMeta.deployment_config 是必填外键（不能为 null），
        而 DeploymentConfigVersion.config_meta_id 也关联到 CollectConfigMeta，
        需要按以下顺序处理：
        1. 先创建 DeploymentConfigVersion（config_meta_id 设为 None 或临时值）
        2. 再创建 CollectConfigMeta（设置 deployment_config）
        3. 最后更新 DeploymentConfigVersion.config_meta_id
        """
        from monitor_web.models.collecting import DeploymentConfigVersion
        from .import_utils import convert_datetime_to_string
        
        # 获取原始ID
        original_id = data.get("_metadata", {}).get("original_id")
        
        # 1. 应用导入适配器
        data = self.adapter_manager.apply_adapters(data)
        
        # 2. 处理 deployment_config（从 _relations 中获取）
        deployment_config_data = None
        if "_relations" in data and "deployment_config" in data["_relations"]:
            deployment_config_data = data["_relations"].pop("deployment_config")
        
        # 3. 移除 deployment_config 字段
        data.pop("deployment_config", None)
        data.pop("deployment_config_id", None)
        
        # 4. 解析外键字段（将原始ID转换为新ID）
        data = self._resolve_foreign_keys(data)
        
        # 5. 检查冲突
        existing_obj = self._check_conflict(data)
        if existing_obj:
            # 如果对象已存在，直接处理
            obj = self._handle_conflict(data, existing_obj)
            # 记录ID映射
            new_id = self._get_primary_key_value(obj)
            if original_id is not None:
                self.id_mapper.add_mapping(self.resource_type, original_id, new_id)
            return obj
        
        # 6. 先创建 DeploymentConfigVersion（如果存在）
        deployment_config = None
        if deployment_config_data:
            # 移除元数据和主键
            deployment_config_data = {k: v for k, v in deployment_config_data.items() 
                                     if k not in ["_metadata", "id"]}
            
            # config_meta_id 先设为 0（临时值，稍后更新）
            # 因为 config_meta_id 是 IntegerField 不是 ForeignKey，所以可以设置临时值
            deployment_config_data.pop("config_meta_id", None)
            deployment_config_data.pop("config_meta", None)
            deployment_config_data["config_meta_id"] = 0  # 临时值
            
            # 处理 plugin_version：先导入 _plugin_version 数据，然后使用 plugin_version_id
            plugin_version_data = deployment_config_data.pop("_plugin_version", None)
            plugin_version_id = deployment_config_data.pop("plugin_version", None)
            
            if plugin_version_data:
                # 在创建 PluginVersionHistory 之前，先确保 CollectorPluginMeta 已存在
                # 因为 PluginVersionHistory.save() 会查找关联的 CollectorPluginMeta
                self._ensure_plugin_exists(data, plugin_version_data)
                # 导入 PluginVersionHistory 数据
                plugin_version_id = self._import_plugin_version(plugin_version_data, original_id)
            
            if plugin_version_id:
                # 使用 plugin_version_id 字段（Django 外键的 _id 后缀字段）可以直接设置整数值
                deployment_config_data["plugin_version_id"] = plugin_version_id
            
            # 应用适配器
            deployment_config_data = self.adapter_manager.apply_adapters(deployment_config_data)
            
            # 解析外键（除了 plugin_version，因为我们已经手动处理了）
            deployment_config_data = self._resolve_foreign_keys_for_model(
                deployment_config_data, DeploymentConfigVersion
            )
            
            # 转换 datetime 对象为字符串
            deployment_config_data = convert_datetime_to_string(deployment_config_data)
            
            # 创建 DeploymentConfigVersion
            try:
                deployment_config = DeploymentConfigVersion.objects.create(**deployment_config_data)
            except Exception as e:
                logger.error(f"Failed to create deployment_config for collect_config {original_id}: {e}", exc_info=True)
                raise
        
        if not deployment_config:
            # 如果没有 deployment_config，记录警告并跳过此采集配置
            logger.warning(f"Cannot import collect_config {original_id}: deployment_config is required but not provided in export data. Skipping.")
            return None
        
        # 7. 创建 CollectConfigMeta（设置 deployment_config）
        # 获取主键字段名
        pk_field = self._get_primary_key_field(self.model_class)
        
        # 移除元数据、关联数据、主键字段
        import_data = {k: v for k, v in data.items() if not k.startswith("_") and k != pk_field}
        
        # 转换 datetime 对象为字符串
        import_data = convert_datetime_to_string(import_data)
        
        # 设置 deployment_config
        import_data["deployment_config"] = deployment_config
        
        # 创建对象
        obj = self.model_class.objects.create(**import_data)
        
        # 8. 更新 DeploymentConfigVersion.config_meta_id
        deployment_config.config_meta_id = obj.id
        deployment_config.save(update_fields=["config_meta_id"])
        
        # 9. 记录ID映射
        new_id = self._get_primary_key_value(obj)
        if original_id is not None:
            self.id_mapper.add_mapping(self.resource_type, original_id, new_id)
        
        # 10. 导入关联数据（plugin 等）
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
    
    def _ensure_plugin_exists(self, data: dict, plugin_version_data: dict):
        """
        确保 CollectorPluginMeta 已存在（在创建 PluginVersionHistory 之前调用）
        
        PluginVersionHistory.save() 方法会通过 plugin 属性查找关联的 CollectorPluginMeta，
        如果 CollectorPluginMeta 不存在会报错，所以需要先确保它存在。
        """
        from .import_utils import convert_datetime_to_string
        
        # 从 plugin_version_data 中获取 plugin_id 和 bk_tenant_id
        plugin_id = plugin_version_data.get("plugin_id")
        bk_tenant_id = plugin_version_data.get("bk_tenant_id")
        
        if not plugin_id or not bk_tenant_id:
            return
        
        # 检查是否已存在
        if CollectorPluginMeta.objects.filter(plugin_id=plugin_id, bk_tenant_id=bk_tenant_id).exists():
            return
        
        # 从 _relations.plugin 中获取插件数据
        plugin_data = None
        if "_relations" in data and "plugin" in data["_relations"]:
            plugin_data = data["_relations"].get("plugin")
        
        if not plugin_data:
            logger.warning(f"Plugin {plugin_id} not found in _relations, cannot create")
            return
        
        # 准备插件数据
        plugin_data = {k: v for k, v in plugin_data.items() if not k.startswith("_") and k != "id"}
        plugin_data = self.adapter_manager.apply_adapters(plugin_data)
        plugin_data = convert_datetime_to_string(plugin_data)
        
        # 创建插件
        try:
            CollectorPluginMeta.objects.create(**plugin_data)
            logger.info(f"Pre-created plugin {plugin_id} for PluginVersionHistory")
        except Exception as e:
            logger.error(f"Failed to pre-create plugin {plugin_id}: {e}", exc_info=True)
    
    def _import_plugin_version(self, plugin_version_data: dict, collect_config_id) -> int:
        """
        导入 PluginVersionHistory 及其关联的 CollectorPluginConfig 和 CollectorPluginInfo
        
        Args:
            plugin_version_data: 插件版本数据（包含 _config 和 _info）
            collect_config_id: 采集配置原始ID（用于日志）
        
        Returns:
            新创建或已存在的 PluginVersionHistory ID
        """
        from monitor_web.models.plugin import (
            PluginVersionHistory, 
            CollectorPluginConfig, 
            CollectorPluginInfo
        )
        from .import_utils import convert_datetime_to_string
        
        # 获取原始 plugin_version_id
        original_version_id = plugin_version_data.get("id")
        plugin_id = plugin_version_data.get("plugin_id")
        bk_tenant_id = plugin_version_data.get("bk_tenant_id")
        config_version = plugin_version_data.get("config_version")
        info_version = plugin_version_data.get("info_version")
        
        # 检查是否已存在相同的 PluginVersionHistory
        try:
            existing_version = PluginVersionHistory.objects.get(
                plugin_id=plugin_id,
                bk_tenant_id=bk_tenant_id,
                config_version=config_version,
                info_version=info_version
            )
            logger.info(f"PluginVersionHistory for plugin {plugin_id} v{config_version}.{info_version} already exists (id={existing_version.id})")
            return existing_version.id
        except PluginVersionHistory.DoesNotExist:
            pass
        
        # 提取 _config 和 _info 数据
        config_data = plugin_version_data.pop("_config", None)
        info_data = plugin_version_data.pop("_info", None)
        
        # 创建 CollectorPluginConfig
        config_obj = None
        if config_data:
            config_data = {k: v for k, v in config_data.items() if not k.startswith("_") and k != "id"}
            config_data = self.adapter_manager.apply_adapters(config_data)
            config_data = convert_datetime_to_string(config_data)
            try:
                config_obj = CollectorPluginConfig.objects.create(**config_data)
                logger.debug(f"Created CollectorPluginConfig (id={config_obj.id}) for plugin {plugin_id}")
            except Exception as e:
                logger.error(f"Failed to create CollectorPluginConfig for collect_config {collect_config_id}: {e}", exc_info=True)
                raise
        
        # 创建 CollectorPluginInfo
        info_obj = None
        if info_data:
            info_data = {k: v for k, v in info_data.items() if not k.startswith("_") and k != "id"}
            info_data = self.adapter_manager.apply_adapters(info_data)
            # 移除 logo 字段（ImageField 需要特殊处理，暂时跳过）
            info_data.pop("logo", None)
            info_data = convert_datetime_to_string(info_data)
            try:
                info_obj = CollectorPluginInfo.objects.create(**info_data)
                logger.debug(f"Created CollectorPluginInfo (id={info_obj.id}) for plugin {plugin_id}")
            except Exception as e:
                logger.error(f"Failed to create CollectorPluginInfo for collect_config {collect_config_id}: {e}", exc_info=True)
                raise
        
        if not config_obj or not info_obj:
            raise ValueError(f"Cannot create PluginVersionHistory: config or info data missing for collect_config {collect_config_id}")
        
        # 创建 PluginVersionHistory
        version_data = {k: v for k, v in plugin_version_data.items() if not k.startswith("_") and k != "id"}
        version_data = self.adapter_manager.apply_adapters(version_data)
        # 移除原始的 config 和 info 字段（整数ID），使用新创建的对象
        version_data.pop("config", None)
        version_data.pop("info", None)
        version_data["config_id"] = config_obj.id
        version_data["info_id"] = info_obj.id
        version_data = convert_datetime_to_string(version_data)
        
        try:
            version_obj = PluginVersionHistory.objects.create(**version_data)
            logger.info(f"Created PluginVersionHistory (id={version_obj.id}) for plugin {plugin_id} v{config_version}.{info_version}")
            return version_obj.id
        except Exception as e:
            logger.error(f"Failed to create PluginVersionHistory for collect_config {collect_config_id}: {e}", exc_info=True)
            raise


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
    
    注意：CustomTSTable 的主键是 time_series_group_id（不是 id），且与 TimeSeriesGroup 共享
    """
    resource_type = "custom_ts_table"
    model_class = CustomTSTable
    
    def _get_primary_key_value(self, obj) -> int:
        """
        获取对象的主键值
        CustomTSTable 的主键是 time_series_group_id
        """
        return obj.time_series_group_id
    
    def _check_conflict(self, data: dict):
        """
        检查冲突（使用多种方式检查）
        1. 优先使用映射后的 time_series_group_id 检查
        2. 其次使用 name + bk_biz_id 检查
        
        注意：当找到已存在的对象时，立即建立 ID 映射，避免后续重复创建
        """
        original_ts_group_id = data.get("time_series_group_id")
        
        # 1. 通过 time_series_group_id 检查（如果已经映射过）
        if original_ts_group_id is not None:
            # 尝试从 ID 映射中获取新的 time_series_group_id
            new_ts_group_id = self.id_mapper.get_new_id("custom_ts_group", original_ts_group_id)
            if new_ts_group_id is not None:
                try:
                    existing = self.model_class.objects.get(time_series_group_id=new_ts_group_id)
                    logger.debug(f"Found existing {self.resource_type} by mapped time_series_group_id: {new_ts_group_id}")
                    # 建立 custom_ts_table 的 ID 映射（使用 time_series_group_id 作为主键）
                    if original_ts_group_id != new_ts_group_id:
                        self.id_mapper.add_mapping(self.resource_type, original_ts_group_id, new_ts_group_id)
                    return existing
                except self.model_class.DoesNotExist:
                    pass
        
        # 2. 通过 name + bk_biz_id 检查
        name = data.get("name")
        bk_biz_id = data.get("bk_biz_id")
        
        if name and bk_biz_id is not None:
            try:
                existing = self.model_class.objects.filter(
                    name=name,
                    bk_biz_id=bk_biz_id
                ).first()
                if existing:
                    existing_ts_group_id = existing.time_series_group_id
                    logger.debug(f"Found existing {self.resource_type} by name+biz_id: {existing_ts_group_id}")
                    # 立即建立 ID 映射（custom_ts_group 和 custom_ts_table 都需要）
                    if original_ts_group_id is not None:
                        self.id_mapper.add_mapping("custom_ts_group", original_ts_group_id, existing_ts_group_id)
                        self.id_mapper.add_mapping(self.resource_type, original_ts_group_id, existing_ts_group_id)
                    return existing
            except Exception as e:
                logger.debug(f"Error checking conflict by name+biz_id: {e}")
        
        return None
    
    def _create_object(self, data: dict):
        """
        创建对象，特殊处理 time_series_group_id（既是主键也是外键）
        CustomTSTable 的主键 time_series_group_id 需要与 TimeSeriesGroup 保持一致
        """
        from .import_utils import convert_datetime_to_string
        
        # time_series_group_id 是主键，也是外键，需要从ID映射中获取
        original_ts_group_id = data.get("time_series_group_id")
        
        # 尝试从 ID 映射中获取新的 time_series_group_id
        new_ts_group_id = self.id_mapper.get_new_id("custom_ts_group", original_ts_group_id)
        
        if new_ts_group_id is None:
            # 如果没有找到映射，检查是否可以使用原始 ID
            # 1. 先检查原始 ID 是否已存在
            if original_ts_group_id is not None:
                try:
                    existing = self.model_class.objects.filter(time_series_group_id=original_ts_group_id).exists()
                    if not existing:
                        # 原始 ID 不存在，可以直接使用
                        new_ts_group_id = original_ts_group_id
                        logger.debug(f"Using original time_series_group_id={original_ts_group_id} for {self.resource_type}")
                except Exception as e:
                    logger.debug(f"Error checking time_series_group_id existence: {e}")
            
            # 2. 如果还是没有确定 ID，尝试通过业务逻辑查找对应的 TimeSeriesGroup
            if new_ts_group_id is None:
                bk_data_id = data.get("bk_data_id")
                bk_biz_id = data.get("bk_biz_id")
                
                if bk_data_id and bk_biz_id is not None:
                    try:
                        # 尝试通过 bk_data_id 查找对应的 TimeSeriesGroup
                        from packages.monitor_web.models.custom_report import TimeSeriesGroup
                        ts_group = TimeSeriesGroup.objects.filter(
                            bk_data_id=bk_data_id,
                            bk_biz_id=bk_biz_id
                        ).first()
                        
                        if ts_group:
                            new_ts_group_id = ts_group.time_series_group_id
                            # 记录 ID 映射
                            self.id_mapper.add_mapping("custom_ts_group", original_ts_group_id, new_ts_group_id)
                            logger.debug(f"Found TimeSeriesGroup {new_ts_group_id} by bk_data_id={bk_data_id}")
                    except Exception as e:
                        logger.debug(f"Error finding TimeSeriesGroup by bk_data_id: {e}")
            
            # 如果还是没找到，抛出错误
            if new_ts_group_id is None:
                raise ValueError(
                    f"Cannot find or map time_series_group_id for custom_ts_table: "
                    f"original_id={original_ts_group_id}, bk_data_id={bk_data_id}. "
                    f"Please ensure custom_ts_group is imported first."
                )
        
        # 移除元数据、关联数据和所有以 _ 开头的内部字段
        import_data = {k: v for k, v in data.items() if not k.startswith("_")}
        
        # 设置主键（使用映射后的新ID或原始ID）
        import_data["time_series_group_id"] = new_ts_group_id
        
        # 转换 datetime 对象为字符串
        import_data = convert_datetime_to_string(import_data)
        
        # 创建对象
        obj = self.model_class.objects.create(**import_data)
        return obj
    
    def import_relations(self, obj, relations: dict):
        """
        导入关联的字段定义（使用 savepoint 保护每个字段的导入）
        """
        from django.db import transaction
        
        if "fields" in relations:
            # 获取主键值（time_series_group_id）
            new_id = obj.time_series_group_id
            
            for field_data in relations["fields"]:
                # 为每个字段创建 savepoint，避免单个字段失败影响其他字段
                sid = transaction.savepoint()
                try:
                    # 移除元数据和主键字段（让数据库自动生成新的主键）
                    field_data = {k: v for k, v in field_data.items() if not k.startswith("_") and k != "id"}
                    
                    # 检查字段是否已存在（使用 time_series_group_id + name 作为唯一标识）
                    field_name = field_data.get("name")
                    if field_name:
                        existing_field = CustomTSField.objects.filter(
                            time_series_group_id=new_id,
                            name=field_name
                        ).first()
                        
                        if existing_field:
                            logger.debug(f"Field {field_name} already exists for custom_ts_table {new_id}, skipping")
                            transaction.savepoint_commit(sid)
                            continue
                    
                    # 应用适配器
                    field_data = self.adapter_manager.apply_adapters(field_data)
                    # 解析外键（关联到主对象）
                    field_data["time_series_group_id"] = new_id
                    # 解析其他外键
                    field_data = self._resolve_foreign_keys_for_model(field_data, CustomTSField)
                    
                    # 创建字段
                    CustomTSField.objects.create(**field_data)
                    transaction.savepoint_commit(sid)
                    
                except Exception as e:
                    transaction.savepoint_rollback(sid)
                    logger.error(f"Failed to import field for custom_ts_table {new_id}: {e}", exc_info=True)


class CustomTSGroupImporter(BaseImporter):
    """
    自定义时序分组导入器
    
    注意：TimeSeriesGroup 的主键是 time_series_group_id（不是 id）
    """
    resource_type = "custom_ts_group"
    model_class = TimeSeriesGroup
    
    def _get_primary_key_value(self, obj) -> int:
        """
        获取对象的主键值
        TimeSeriesGroup 的主键是 time_series_group_id（不是 id）
        """
        return obj.time_series_group_id
    
    def _check_conflict(self, data: dict):
        """
        检查时序分组冲突
        1. 优先使用 time_series_group_id 检查（如果已存在）
        2. 其次使用 time_series_group_name + bk_biz_id 作为唯一标识
        
        注意：当找到已存在的对象时，立即建立 ID 映射，避免后续重复创建
        """
        original_ts_group_id = data.get("time_series_group_id")
        
        # 1. 优先通过 time_series_group_id 检查
        if original_ts_group_id is not None:
            try:
                existing = self.model_class.objects.get(time_series_group_id=original_ts_group_id)
                logger.debug(f"Found existing {self.resource_type} by time_series_group_id: {existing.time_series_group_id}")
                # ID 相同，无需映射
                return existing
            except self.model_class.DoesNotExist:
                pass
        
        # 2. 通过 time_series_group_name + bk_biz_id 检查
        name = data.get("time_series_group_name")
        bk_biz_id = data.get("bk_biz_id")
        
        if name and bk_biz_id is not None:
            try:
                existing = self.model_class.objects.get(
                    time_series_group_name=name,
                    bk_biz_id=bk_biz_id
                )
                existing_ts_group_id = existing.time_series_group_id
                logger.debug(f"Found existing {self.resource_type} by name+biz_id: {existing_ts_group_id}")
                # 立即建立 ID 映射，供后续 custom_ts_table 使用
                if original_ts_group_id is not None and original_ts_group_id != existing_ts_group_id:
                    self.id_mapper.add_mapping(self.resource_type, original_ts_group_id, existing_ts_group_id)
                    logger.debug(f"Mapped {self.resource_type} ID: {original_ts_group_id} -> {existing_ts_group_id}")
                return existing
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
