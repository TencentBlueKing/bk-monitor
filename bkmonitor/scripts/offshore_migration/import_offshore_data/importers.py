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
        导入关联的轮班配置（从属资源）
        
        注意：duty_rules 是 JSONField，存储 DutyRule 的 ID 列表。
        DutyRule 已在前序步骤（duty_rule 导入阶段）导入，无需在此处理。
        全量迁移模式下，ID 保持不变，UserGroup.duty_rules 字段直接使用原始 ID。
        """
        # 导入轮班配置（从属资源）
        if "duty_arranges" in relations:
            self.import_related_queryset(
                obj, "duty_arranges", relations["duty_arranges"], DutyArrange, "user_group_id"
            )
        
        # duty_rules（独立资源）已在前序步骤导入，无需处理


class DutyRuleImporter(BaseImporter):
    """
    轮值规则导入器
    """
    resource_type = "duty_rule"
    model_class = DutyRule
    
    # 使用基类的 _check_conflict() 方法（优先通过主键ID检查）
    # 无需重写


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
    
    def _check_conflict(self, data: dict):
        """
        检查插件冲突（优先使用主键ID，其次使用 plugin_type）
        
        ActionPlugin 通常是内置插件（notice、webhook、job、sops、common 等）。
        在全量迁移模式下，优先使用主键ID检查；如果ID不存在，再使用 plugin_type 检查。
        """
        # 1. 优先通过主键ID检查（全量迁移模式）
        original_id = data.get("_metadata", {}).get("original_id")
        if original_id is not None:
            try:
                existing = self.model_class.objects.get(id=original_id)
                logger.debug(f"Found existing {self.resource_type} by id: {original_id}")
                return existing
            except self.model_class.DoesNotExist:
                pass
        
        # 2. 通过 plugin_type 检查（兼容模式，避免重复创建内置插件）
        plugin_type = data.get("plugin_type")
        if plugin_type:
            # 使用 filter().first() 避免 MultipleObjectsReturned 异常
            existing = self.model_class.objects.filter(plugin_type=plugin_type).first()
            if existing:
                logger.debug(f"Found existing {self.resource_type} by plugin_type: {plugin_type} (id={existing.id})")
                return existing
        
        return None


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
        检查冲突（优先使用主键ID检查）
        """
        # 1. 通过 time_series_group_id 检查
        original_ts_group_id = data.get("time_series_group_id")
        
        if original_ts_group_id is not None:
            try:
                existing = self.model_class.objects.get(time_series_group_id=original_ts_group_id)
                logger.debug(f"Found existing {self.resource_type} by time_series_group_id: {existing.time_series_group_id}")
                return existing
            except self.model_class.DoesNotExist:
                pass
        
        # 2. 通过 name + bk_biz_id 检查（兼容）
        name = data.get("name")
        bk_biz_id = data.get("bk_biz_id")
        
        if name and bk_biz_id is not None:
            try:
                existing = self.model_class.objects.filter(
                    name=name,
                    bk_biz_id=bk_biz_id
                ).first()
                if existing:
                    logger.debug(f"Found existing {self.resource_type} by name+biz_id: {existing.time_series_group_id}")
                    return existing
            except Exception as e:
                logger.debug(f"Error checking conflict by name+biz_id: {e}")
        
        return None
    
    def _create_object(self, data: dict):
        """
        创建对象（CustomTSTable 的主键 time_series_group_id 需要与 TimeSeriesGroup 保持一致）
        """
        from .import_utils import convert_datetime_to_string
        
        # time_series_group_id 是主键，也是外键
        # 在全量迁移模式下，直接使用原始ID
        original_ts_group_id = data.get("time_series_group_id")
        
        if original_ts_group_id is None:
            raise ValueError(
                f"Cannot create {self.resource_type}: time_series_group_id is required. "
                f"Please ensure custom_ts_group is imported first."
            )
        
        # 移除元数据、关联数据和所有以 _ 开头的内部字段
        import_data = {k: v for k, v in data.items() if not k.startswith("_")}
        
        # 转换 datetime 对象为字符串
        import_data = convert_datetime_to_string(import_data)
        
        # 创建对象
        try:
            obj = self.model_class.objects.create(**import_data)
            logger.debug(f"Created {self.resource_type} with time_series_group_id={original_ts_group_id}")
            return obj
        except Exception as e:
            error_msg = (
                f"Failed to create {self.resource_type} with time_series_group_id={original_ts_group_id}: {e}. "
                f"This usually means the object already exists but _check_conflict() didn't detect it."
            )
            logger.error(error_msg)
            raise
    
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
        检查时序分组冲突（优先使用主键ID检查）
        """
        # 1. 优先通过 time_series_group_id 检查
        original_ts_group_id = data.get("time_series_group_id")
        
        if original_ts_group_id is not None:
            try:
                existing = self.model_class.objects.get(time_series_group_id=original_ts_group_id)
                logger.debug(f"Found existing {self.resource_type} by time_series_group_id: {existing.time_series_group_id}")
                return existing
            except self.model_class.DoesNotExist:
                pass
        
        # 2. 通过 time_series_group_name + bk_biz_id 检查（兼容）
        name = data.get("time_series_group_name")
        bk_biz_id = data.get("bk_biz_id")
        
        if name and bk_biz_id is not None:
            try:
                existing = self.model_class.objects.get(
                    time_series_group_name=name,
                    bk_biz_id=bk_biz_id
                )
                logger.debug(f"Found existing {self.resource_type} by name+biz_id: {existing.time_series_group_id}")
                return existing
            except self.model_class.DoesNotExist:
                pass
        
        return None
    
    def _create_object(self, data: dict):
        """
        创建对象（过滤掉不属于模型字段的数据）
        
        TimeSeriesGroup 导出的数据可能包含动态属性（如 metric_group_dimensions），
        这些属性不是数据库字段，需要在创建对象前过滤掉。
        """
        from .import_utils import convert_datetime_to_string
        
        # 获取模型的所有字段名
        model_field_names = {f.name for f in self.model_class._meta.fields}
        
        # 移除元数据、关联数据和所有以 _ 开头的内部字段
        import_data = {k: v for k, v in data.items() if not k.startswith("_")}
        
        # 过滤掉不属于模型字段的数据（如 metric_group_dimensions）
        invalid_fields = set(import_data.keys()) - model_field_names
        if invalid_fields:
            logger.debug(f"Filtering out non-model fields for {self.resource_type}: {invalid_fields}")
            import_data = {k: v for k, v in import_data.items() if k in model_field_names}
        
        # 转换 datetime 对象为字符串
        import_data = convert_datetime_to_string(import_data)
        
        # 创建对象
        try:
            obj = self.model_class.objects.create(**import_data)
            logger.debug(f"Created {self.resource_type} with time_series_group_id={obj.time_series_group_id}")
            return obj
        except Exception as e:
            error_msg = (
                f"Failed to create {self.resource_type}: {e}. "
                f"Data keys: {list(import_data.keys())}"
            )
            logger.error(error_msg)
            raise


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
