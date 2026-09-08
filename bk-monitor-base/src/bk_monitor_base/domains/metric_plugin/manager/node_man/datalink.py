import random
import re
import string
from abc import ABC
from typing import Any, Literal, cast, final

from typing_extensions import override

from bk_monitor_base.domains.metric_plugin.constants import (
    LOG_DEFAULT_DIMENSIONS,
    PROCESS_BUILD_IN_DIMENSIONS,
    SNMP_TRAP_DEFAULT_DIMENSIONS,
    ETLConfig,
    PluginType,
)
from bk_monitor_base.domains.metric_plugin.define import (
    MetricPluginMetricField,
    MetricPluginMetricGroup,
    format_version_padded,
)
from bk_monitor_base.domains.metric_plugin.manager.datalink import PLUGIN_REVERSED_DIMENSION, MetricPluginDataLinker
from bk_monitor_base.domains.metric_plugin.manager.node_man.define import NodemanPluginParamsMode
from bk_monitor_base.domains.metric_plugin.models import MetricPluginVersionModel
from bk_monitor_base.infras import third_party_api as api
from bk_monitor_base.infras.third_party_api.errors import BkApiError
from bk_monitor_base.infras.third_party_api.metadata.api import (
    CreateDataSourceParams,
    CreateTimeSeriesGroupParams,
    EventInfoConfig,
    GetDataSourceResult,
    ModifyDataSourceParams,
    ModifyTimeSeriesGroupParams,
)

# 服务实例类插件内置维度
SERVICE_PLUGIN_REVERSED_DIMENSION = [
    ("bk_target_service_category_id", "服务类别ID"),
    ("bk_target_service_instance_id", "服务实例"),
]


class CustomNodemanPluginDataLinker(MetricPluginDataLinker):
    """自定义节点管理插件数据链路"""

    _DEFAULT_GROUP_NAME: str = "group_default"
    _DEFAULT_GROUP_DESC: str = "默认分组"

    def _get_old_data_id(self) -> GetDataSourceResult | None:
        """获取旧版本的数据ID

        为了向前兼容，尝试通过data_name获取data_id
        """
        data_names = [
            f"{self.plugin.type}_{self.plugin.id}".lower(),
            f"{self.plugin.bk_biz_id}_{self.plugin.type}_{self.plugin.id}".lower(),
        ]
        for data_name in data_names:
            try:
                return api.metadata.get_data_source(
                    bk_tenant_id=self.plugin.bk_tenant_id,
                    data_name=data_name,
                )
            except BkApiError as e:
                if "DataSource matching query does not exist" in e.message:
                    continue
                raise e
        return None

    def check_data_id_exists(self) -> bool:
        """检查数据ID是否存在"""
        return "bk_data_id" in self.plugin.related_params

    def _save_related_params(self, related_params: dict[str, Any]) -> None:
        """保存相关参数

        Args:
            related_params: 相关参数
        """
        self.plugin.related_params.update(related_params)
        self.plugin_model.related_params = self.plugin.related_params
        self.plugin_model.save(update_fields=["related_params"])

    def _get_etl_config(self) -> str:
        """获取ETL配置"""
        if self.plugin.type in [PluginType.SCRIPT, PluginType.DATADOG]:
            return ETLConfig.BK_STANDARD.value
        else:
            return ETLConfig.BK_EXPORTER.value

    def get_etl_config(self) -> str:
        """获取ETL配置。"""
        return self._get_etl_config()

    @override
    def apply_data_ids(self, operator: str) -> None:
        """申请数据ID

        Args:
            operator: 操作人
        """

        # 获取数据ID
        bk_data_id = self.plugin.related_params.get("bk_data_id")
        if not bk_data_id:
            # 如果未获取到数据ID，则尝试获取旧版本的数据源
            data_source = self._get_old_data_id()
            if not data_source:
                # 如果旧版本的数据源也不存在，则创建新数据源
                bk_data_id, data_name = self._create_data_id(operator)
                self._save_related_params({"bk_data_id": bk_data_id, "data_name": data_name})
                return
            self._save_related_params({"bk_data_id": data_source["bk_data_id"], "data_name": data_source["data_name"]})
        else:
            # 获取数据源信息
            data_source = api.metadata.get_data_source(
                bk_tenant_id=self.plugin.bk_tenant_id,
                bk_data_id=bk_data_id,
            )
            # 如果数据源名称不一致，则更新数据源名称
            if self.plugin.related_params.get("data_name") != data_source["data_name"]:
                self._save_related_params({"data_name": data_source["data_name"]})

        # 检查数据源是否有变更，如果有变更，则更新数据源
        update_params: ModifyDataSourceParams = {
            "data_id": data_source["bk_data_id"],
            "is_platform_data_id": self.plugin.is_global,
            "data_description": f"plugin_type: {self.plugin.type}, plugin_id: {self.plugin.id}",
            "option": {
                "inject_local_time": True,
                "allow_dimensions_missing": True,
                "is_split_measurement": True,
            },
            "operator": operator,
        }
        is_changed = False
        for key in ["is_platform_data_id", "data_description", "option"]:
            if data_source.get(key) != update_params.get(key):
                is_changed = True
                break
        if is_changed:
            api.metadata.modify_data_source(bk_tenant_id=self.plugin.bk_tenant_id, **update_params)

    def _get_dms_fields(self) -> list[str]:
        """获取注入的维度字段信息"""
        dms_fields: set[str] = set()
        for param in self.plugin.params:
            if param.mode == NodemanPluginParamsMode.DMS_INSERT:
                dms_fields.add(param.name)
        return list(dms_fields)

    @staticmethod
    def _normalize_bool(value: Any, default: bool = True) -> bool:
        """兼容 metadata 布尔字段的多种表示。"""
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes"}:
                return True
            if lowered in {"false", "0", "no"}:
                return False
        return bool(value)

    @staticmethod
    def _normalize_field_type(value: Any) -> Literal["string", "double", "int"]:
        """兼容 metadata 字段类型，仅返回受支持的类型。"""
        field_type = str(value or "string")
        if field_type not in {"string", "double", "int"}:
            return "string"
        return cast(Literal["string", "double", "int"], field_type)

    def _get_reserved_dimension_names(self) -> set[str]:
        """获取不应回填到 metrics 的保留维度。"""
        if self.plugin.label in ["component", "service_module"]:
            built_in_dimension_list = PLUGIN_REVERSED_DIMENSION + SERVICE_PLUGIN_REVERSED_DIMENSION
        else:
            built_in_dimension_list = PLUGIN_REVERSED_DIMENSION
        return {field_name for field_name, _ in built_in_dimension_list} | set(self._get_dms_fields())

    @classmethod
    def _get_default_group(cls, metric_groups: list[MetricPluginMetricGroup]) -> MetricPluginMetricGroup:
        """获取或创建默认分组。"""
        for metric_group in metric_groups:
            if metric_group.table_name == cls._DEFAULT_GROUP_NAME:
                return metric_group
        default_group = MetricPluginMetricGroup(
            table_name=cls._DEFAULT_GROUP_NAME,
            table_desc=cls._DEFAULT_GROUP_DESC,
            fields=[],
            rules=[],
        )
        metric_groups.append(default_group)
        return default_group

    @staticmethod
    def _patch_field_metadata(field: MetricPluginMetricField, source: dict[str, Any]) -> None:
        """仅对白名单字段做回填。"""
        field.description = str(source.get("description", field.description) or "")
        field.unit = str(source.get("unit", field.unit) or "")
        if "is_active" in source or "is_disabled" in source:
            field.is_active = CustomNodemanPluginDataLinker._normalize_bool(
                source.get("is_active"),
                default=not CustomNodemanPluginDataLinker._normalize_bool(source.get("is_disabled"), default=False),
            )

    @staticmethod
    def _build_metric_field(metric: dict[str, Any]) -> MetricPluginMetricField:
        """将 metadata 指标转换为插件指标字段。"""
        return MetricPluginMetricField(
            name=str(metric.get("field_name", "") or ""),
            type="double",
            description=str(metric.get("description", "") or ""),
            monitor_type="metric",
            unit=str(metric.get("unit", "") or ""),
            is_diff_metric=False,
            is_active=CustomNodemanPluginDataLinker._normalize_bool(metric.get("is_active"), default=True),
            source_name="",
        )

    @staticmethod
    def _build_dimension_field(tag: dict[str, Any]) -> MetricPluginMetricField:
        """将 metadata 维度转换为插件维度字段。"""
        return MetricPluginMetricField(
            name=str(tag.get("field_name", "") or ""),
            type=CustomNodemanPluginDataLinker._normalize_field_type(tag.get("type", "string")),
            description=str(tag.get("description", "") or ""),
            monitor_type="dimension",
            unit=str(tag.get("unit", "") or ""),
            is_diff_metric=False,
            is_active=not CustomNodemanPluginDataLinker._normalize_bool(tag.get("is_disabled"), default=False),
            source_name="",
        )

    @staticmethod
    def _collect_metric_info_map(group_list: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """按指标名收集 metadata 指标信息。"""
        metric_info_map: dict[str, dict[str, Any]] = {}
        for group in group_list:
            metric_info_list: list[dict[str, Any]] = group.get("metric_info_list") or []
            for metric in metric_info_list:
                if not metric:
                    continue
                field_name = str(metric.get("field_name", "") or "").strip()
                if field_name:
                    metric_info_map[field_name] = metric
        return metric_info_map

    @staticmethod
    def _match_metric_group(
        metric_name: str, metric_groups: list[MetricPluginMetricGroup]
    ) -> MetricPluginMetricGroup | None:
        """根据分组规则为新增指标匹配目标分组。"""
        for metric_group in metric_groups:
            for rule in metric_group.rules:
                if re.search(rule, metric_name):
                    return metric_group
        return None

    def _get_current_version_model(self) -> MetricPluginVersionModel:
        """获取当前插件版本模型。"""
        return MetricPluginVersionModel.objects.get(
            bk_tenant_id=self.plugin.bk_tenant_id,
            plugin=self.plugin_model,
            version=format_version_padded(self.plugin.version),
        )

    def _get_data_name_for_refresh(self) -> str | None:
        """获取刷新 metrics 所需的数据源名称，兼容旧版本 related_params。"""
        data_name = self.plugin.related_params.get("data_name")
        if data_name:
            return str(data_name)

        bk_data_id = self.plugin.related_params.get("bk_data_id")
        data_source: GetDataSourceResult | None = None
        if bk_data_id:
            data_source = api.metadata.get_data_source(
                bk_tenant_id=self.plugin.bk_tenant_id,
                bk_data_id=bk_data_id,
            )
        else:
            data_source = self._get_old_data_id()

        if not data_source:
            return None

        refreshed_related_params: dict[str, Any] = {"data_name": data_source["data_name"]}
        if not self.plugin.related_params.get("bk_data_id"):
            refreshed_related_params["bk_data_id"] = data_source["bk_data_id"]
        self._save_related_params(refreshed_related_params)
        return str(data_source["data_name"])

    def refresh_metrics(self, operator: str) -> None:
        """从 metadata 刷新当前版本的 metrics。"""
        if not self.plugin.enable_metric_discovery:
            return

        data_name = self._get_data_name_for_refresh()
        if not data_name:
            return

        time_series_groups = api.metadata.query_time_series_group(
            bk_tenant_id=self.plugin.bk_tenant_id,
            time_series_group_name=data_name,
            page_size=0,  # 不分页，获取全部数据以便刷新
        )
        if not time_series_groups:
            return

        metric_info_map = self._collect_metric_info_map(cast(list[dict[str, Any]], time_series_groups))
        if not metric_info_map:
            return

        metric_groups = [metric_group.model_copy(deep=True) for metric_group in self.plugin.metrics]
        existing_metric_names = {
            field.name
            for metric_group in metric_groups
            for field in metric_group.fields
            if field.monitor_type == "metric"
        }

        for metric_name, metric_info in metric_info_map.items():
            if metric_name in existing_metric_names:
                continue
            target_group = self._match_metric_group(metric_name, metric_groups)
            if target_group is None:
                target_group = self._get_default_group(metric_groups)
            target_group.fields.append(self._build_metric_field(metric_info))
            existing_metric_names.add(metric_name)

        reserved_dimension_names = self._get_reserved_dimension_names()

        for metric_group in metric_groups:
            group_tag_map: dict[str, dict[str, Any]] = {}
            existing_field_map = {field.name: field for field in metric_group.fields}

            for field in metric_group.fields:
                if field.monitor_type != "metric":
                    continue
                metric_info = metric_info_map.get(field.name)
                if metric_info:
                    self._patch_field_metadata(field, metric_info)
                tag_list: list[dict[str, Any]] = metric_info.get("tag_list", []) if metric_info else []
                for tag in tag_list:
                    tag_name = str(tag.get("field_name", "") or "").strip()
                    if not tag_name or tag_name in reserved_dimension_names:
                        continue
                    group_tag_map.setdefault(tag_name, tag)

            for field in metric_group.fields:
                if field.monitor_type == "dimension" and field.name in group_tag_map:
                    self._patch_field_metadata(field, group_tag_map[field.name])

            for tag_name, tag in group_tag_map.items():
                if tag_name in existing_field_map:
                    continue
                dimension_field = self._build_dimension_field(tag)
                metric_group.fields.append(dimension_field)
                existing_field_map[tag_name] = dimension_field

        current_version_model = self._get_current_version_model()
        updated_metrics = [metric_group.model_dump() for metric_group in metric_groups]
        if updated_metrics == current_version_model.metrics:
            return

        current_version_model.metrics = updated_metrics
        current_version_model.updated_by = operator
        current_version_model.save(update_fields=["metrics", "updated_by"])

    def _get_time_series_metrics(self) -> list[dict[str, Any]]:
        """获取自定义指标字段信息

        1. 将metrics信息转换为time_series_group的字段信息格式
        2. 将维度注入的维度加入到time_series_group的字段列表中

        Returns:
            time_series_group_fields: time_series_group字段列表
            Example:
            [
                {
                    "field_name": "metric1",
                    "tag_list": [{"field_name": "dimension1", "unit": "none", "type": "string", "description": "dimension1_description"}]
                    "label": "os",
                    "is_active": True,
                }
            ]
        """
        time_series_group_fields: list[dict[str, Any]] = []
        dms_fields = self._get_dms_fields()

        # 将字段信息转换为time_series_group的字段信息格式
        for metric_group in self.plugin.metrics:
            tag_list: list[dict[str, Any]] = []
            existing_dimension_fields: set[str] = set()

            # 先收集“插件定义”的维度（仅收集启用的维度）
            for metric_field in metric_group.fields:
                if metric_field.monitor_type != "dimension" or not metric_field.is_active:
                    continue
                existing_dimension_fields.add(metric_field.name)
                tag_list.append(
                    {
                        "field_name": metric_field.name,
                        "unit": metric_field.unit,
                        "type": metric_field.type,
                        "description": metric_field.description,
                    }
                )

            # 添加内置维度（避免重复）
            if self.plugin.label in ["component", "service_module"]:
                built_in_dimension_list = PLUGIN_REVERSED_DIMENSION + SERVICE_PLUGIN_REVERSED_DIMENSION
            else:
                built_in_dimension_list = PLUGIN_REVERSED_DIMENSION
            for builtin_field, builtin_desc in built_in_dimension_list:
                if builtin_field in existing_dimension_fields:
                    continue
                tag_list.append(
                    {
                        "field_name": builtin_field,
                        "unit": "none",
                        "type": "string",
                        "description": builtin_desc,
                    }
                )

            # 添加注入维度（避免重复）
            for dms_field in dms_fields:
                if dms_field in existing_dimension_fields:
                    continue
                tag_list.append(
                    {
                        "field_name": dms_field,
                        "unit": "none",
                        "type": "string",
                        "description": dms_field,
                    }
                )

            # 再生成指标字段（共享同一个 tag_list）
            for metric_field in metric_group.fields:
                if metric_field.monitor_type != "metric":
                    continue
                time_series_group_fields.append(
                    {
                        "field_name": metric_field.name,
                        "tag_list": tag_list,
                        "label": self.plugin.label,
                        "is_active": metric_field.is_active,
                    }
                )

        return time_series_group_fields

    @override
    def apply_result_tables(self, operator: str) -> None:
        """申请结果表

        默认创建自定义指标结果表，当插件未开启自动发现时，需要传入指标/维度白名单配置。

        Args:
            operator: 操作人
        """
        bk_data_id = self.plugin.related_params.get("bk_data_id")
        data_name = self.plugin.related_params.get("data_name")
        # 兼容老版本的查询语句 固定模板为 plugin_type_plugin_id.__default__
        table_id = f"{self.plugin.type.lower()}_{self.plugin.id.lower()}.__default__"
        if not bk_data_id or not data_name:
            raise ValueError("bk_data_id and data_name are required")

        # 查询时序分组
        time_series_groups = cast(
            list[dict[str, Any]],
            api.metadata.query_time_series_group(
                bk_tenant_id=self.plugin.bk_tenant_id,
                time_series_group_name=data_name,
                page_size=0,  # 不分页，获取全部数据以便刷新
            ),
        )

        time_series_group_fields = self._get_time_series_metrics()

        if not time_series_groups:
            create_params: CreateTimeSeriesGroupParams = {
                "operator": operator,
                "bk_data_id": bk_data_id,
                "bk_biz_id": self.plugin.bk_biz_id,
                "table_id": table_id,
                "time_series_group_name": data_name,
                "label": self.plugin.label,
                "is_split_measurement": True,
                "data_label": self.plugin.id,
                "metric_info_list": time_series_group_fields,
                "additional_options": {
                    "enable_field_black_list": self.plugin.enable_metric_discovery,
                    "enable_default_value": False,
                },
            }
            api.metadata.create_time_series_group(bk_tenant_id=self.plugin.bk_tenant_id, **create_params)
        else:
            time_series_group = time_series_groups[0]
            modify_params: ModifyTimeSeriesGroupParams = {
                "time_series_group_id": time_series_group["time_series_group_id"],
                "operator": operator,
                "label": self.plugin.label,
                "enable_field_black_list": self.plugin.enable_metric_discovery,
                "data_label": self.plugin.id,
                "metric_info_list": time_series_group_fields,
            }
            api.metadata.modify_time_series_group(bk_tenant_id=self.plugin.bk_tenant_id, **modify_params)

        # TODO: 如果存在分组的老表，需要更新老表的data_label，以便后续可以正常查询历史数据
        # 新表还需要将老表添加为data_label，保证老表的查询语句也能查询到新数据

    def _create_data_id(self, operator: str) -> tuple[int, str]:
        """创建数据ID

        默认创建时序数据源，使用自定义数据源类型

        Args:
            operator: 操作人

        Returns:
            bk_data_id: 数据ID
            data_name: 数据源名称
        """

        # 数据源名称
        random_suffix = "".join(random.choices(string.ascii_letters + string.digits, k=8))
        data_name = f"{self.plugin.type.lower()}_{self.plugin.id}_{random_suffix}"

        params: CreateDataSourceParams = {
            "bk_biz_id": self.plugin.bk_biz_id,
            "data_name": data_name,
            "etl_config": self._get_etl_config(),
            "source_label": "bk_monitor",
            "type_label": "time_series",
            "is_custom_source": True,
            "operator": operator,
            "data_description": f"plugin_type: {self.plugin.type}, plugin_id: {self.plugin.id}",
            "is_platform_data_id": self.plugin.is_global,
            "option": {
                "inject_local_time": True,
                "allow_dimensions_missing": True,
                "is_split_measurement": True,
            },
        }

        bk_data_id = api.metadata.create_data_source(bk_tenant_id=self.plugin.bk_tenant_id, **params)
        return bk_data_id, data_name

    @override
    def delete_data_ids(self) -> None:
        """删除数据ID"""

    @override
    def delete_result_tables(self) -> None:
        """删除结果表"""


class BuiltInPluginDataLinker(MetricPluginDataLinker, ABC):
    """内置插件数据链路"""

    def _save_related_params(self, related_params: dict[str, Any]) -> None:
        """保存相关参数。"""
        self.plugin.related_params.update(related_params)
        self.plugin_model.related_params = self.plugin.related_params
        self.plugin_model.save(update_fields=["related_params"])

    def _get_old_data_id(self, data_name: str) -> api.metadata.GetDataSourceResult | None:
        """获取旧版本的数据ID。"""
        try:
            return api.metadata.get_data_source(
                bk_tenant_id=self.plugin.bk_tenant_id,
                data_name=data_name,
            )
        except BkApiError as e:
            if "DataSource matching query does not exist" in e.message:
                return None
            raise e

    def _create_data_id(
        self,
        *,
        operator: str,
        data_name: str,
        etl_config: ETLConfig,
        type_label: str,
        data_description: str,
        additional_options: dict[str, Any],
    ) -> tuple[int, str]:
        """创建数据ID。"""
        params: api.metadata.CreateDataSourceParams = {
            "bk_biz_id": self.plugin.bk_biz_id,
            "data_name": data_name,
            "etl_config": etl_config.value,
            "source_label": "bk_monitor",
            "type_label": type_label,
            "is_custom_source": True,
            "operator": operator,
            "data_description": data_description,
            "is_platform_data_id": self.plugin.is_global,
            "option": additional_options,
        }
        bk_data_id = api.metadata.create_data_source(bk_tenant_id=self.plugin.bk_tenant_id, **params)
        return bk_data_id, data_name

    def _apply_data_id(
        self,
        *,
        operator: str,
        data_id_key: str,
        data_name_key: str,
        data_name: str,
        etl_config: ETLConfig,
        type_label: str,
        data_description: str,
        additional_options: dict[str, Any],
    ) -> tuple[int, str]:
        """申请并校正单个数据源。"""
        bk_data_id = self.plugin.related_params.get(data_id_key)
        if not bk_data_id:
            data_source = self._get_old_data_id(data_name)
            if not data_source:
                bk_data_id, data_name = self._create_data_id(
                    operator=operator,
                    data_name=data_name,
                    etl_config=etl_config,
                    type_label=type_label,
                    data_description=data_description,
                    additional_options=additional_options,
                )
                self._save_related_params({data_id_key: bk_data_id, data_name_key: data_name})
                return bk_data_id, data_name

            bk_data_id = data_source["bk_data_id"]
            self._save_related_params({data_id_key: data_source["bk_data_id"], data_name_key: data_source["data_name"]})
        else:
            data_source = api.metadata.get_data_source(
                bk_tenant_id=self.plugin.bk_tenant_id,
                bk_data_id=bk_data_id,
            )
            if self.plugin.related_params.get(data_name_key) != data_source["data_name"]:
                self._save_related_params({data_name_key: data_source["data_name"]})

        modify_params: api.metadata.ModifyDataSourceParams = {
            "data_id": bk_data_id,
            "is_platform_data_id": self.plugin.is_global,
            "data_description": data_description,
            "option": additional_options,
        }

        is_changed = False
        for key in ["is_platform_data_id", "data_description", "option"]:
            if data_source.get(key) != modify_params.get(key):
                is_changed = True
                break

        if is_changed:
            api.metadata.modify_data_source(
                bk_tenant_id=self.plugin.bk_tenant_id,
                operator=operator,
                data_id=bk_data_id,
                is_platform_data_id=self.plugin.is_global,
                data_description=data_description,
                option=additional_options,
            )

        return bk_data_id, data_name

    @override
    def delete_data_ids(self) -> None:
        """删除数据ID。"""

    @override
    def delete_result_tables(self, **kwargs: Any) -> None:
        """删除结果表。"""


@final
class ProcessPluginDataLinker(BuiltInPluginDataLinker):
    """进程插件数据链路"""

    _DATA_NAME_TEMPLATE = "{bk_biz_id}_custom_time_series_process_{metric_group_name}"
    _ADDITIONAL_OPTIONS = {"is_split_measurement": True}

    def get_metric_groups(self) -> list[str]:
        """获取进程插件指标组。"""
        metric_groups: list[str] = []
        for metric_group in self.plugin.metrics:
            has_metrics = any(field.monitor_type == "metric" for field in metric_group.fields)
            if has_metrics:
                metric_groups.append(metric_group.table_name)
        return metric_groups

    @override
    def apply_data_ids(self, operator: str) -> None:
        """申请进程插件数据ID（按指标组拆分）。"""
        for metric_group_name in self.get_metric_groups():
            data_name = self._DATA_NAME_TEMPLATE.format(
                bk_biz_id=self.plugin.bk_biz_id,
                metric_group_name=metric_group_name,
            )
            self._apply_data_id(
                operator=operator,
                data_id_key=f"{metric_group_name}_data_id",
                data_name_key=f"{metric_group_name}_data_name",
                data_name=data_name,
                etl_config=ETLConfig.BK_STANDARD_V2_TIME_SERIES,
                type_label="time_series",
                data_description=(
                    f"plugin_type: {self.plugin.type}, plugin_id: {self.plugin.id}, "
                    f"metric_group_name: {metric_group_name}"
                ),
                additional_options=self._ADDITIONAL_OPTIONS,
            )

    @override
    def apply_result_tables(self, operator: str) -> None:
        """申请进程插件结果表。"""
        metric_groups = self.get_metric_groups()

        for metric_group_name in metric_groups:
            data_id_key = f"{metric_group_name}_data_id"
            bk_data_id = self.plugin.related_params.get(data_id_key)
            if not bk_data_id:
                raise ValueError(f"指标组 {metric_group_name} 的 bk_data_id是必需的")

            time_series_group_name = f"process_{metric_group_name}"
            time_series_groups = cast(
                list[dict[str, Any]],
                api.metadata.query_time_series_group(
                    bk_tenant_id=self.plugin.bk_tenant_id,
                    time_series_group_name=time_series_group_name,
                    page_size=0,  # 不分页，获取全部数据以便刷新
                ),
            )

            time_series_group_fields = self._get_process_time_series_metrics(metric_group_name)
            if time_series_groups:
                time_series_group_id = time_series_groups[0]["time_series_group_id"]
                existing_metric_info_list = time_series_groups[0].get("metric_info_list", [])
                if self._normalize_metric_info(existing_metric_info_list) != self._normalize_metric_info(
                    time_series_group_fields
                ):
                    api.metadata.modify_time_series_group(
                        bk_tenant_id=self.plugin.bk_tenant_id,
                        operator=operator,
                        time_series_group_id=time_series_group_id,
                        metric_info_list=time_series_group_fields,
                    )
                continue

            api.metadata.create_time_series_group(
                bk_tenant_id=self.plugin.bk_tenant_id,
                operator=operator,
                bk_data_id=bk_data_id,
                bk_biz_id=self.plugin.bk_biz_id,
                time_series_group_name=time_series_group_name,
                label="host_process",
                is_split_measurement=True,
                data_label=f"process.{metric_group_name},process",
                metric_info_list=time_series_group_fields,
            )

    @staticmethod
    def _normalize_metric_info(metric_list: list[dict[str, Any]]) -> list[Any]:
        """标准化指标信息列表，用于准确比较。"""
        normalized: list[tuple[Any, Any, tuple[tuple[Any, Any, Any], ...], tuple[tuple[Any, Any, Any], ...]]] = []
        for metric in metric_list:
            field_list = cast(list[dict[str, Any]], metric.get("field_list", []))
            tag_list = cast(list[dict[str, Any]], metric.get("tag_list", []))
            field_list = sorted(field_list, key=lambda x: str(x.get("field_name", "")))
            tag_list = sorted(tag_list, key=lambda x: str(x.get("field_name", "")))
            normalized.append(
                (
                    metric.get("field_name"),
                    metric.get("table_id"),
                    tuple((f.get("field_name"), f.get("type"), f.get("description")) for f in field_list),
                    tuple((t.get("field_name"), t.get("type"), t.get("description")) for t in tag_list),
                )
            )
        return sorted(normalized, key=lambda item: str(item))

    def _get_process_time_series_metrics(self, metric_group_name: str) -> list[dict[str, Any]]:
        """获取进程插件指定指标组的时序指标字段信息。"""
        time_series_group_fields: list[dict[str, Any]] = []

        target_metric_group = None
        for metric_group in self.plugin.metrics:
            if metric_group.table_name == metric_group_name:
                target_metric_group = metric_group
                break

        if not target_metric_group:
            return time_series_group_fields

        dimension_fields: list[dict[str, Any]] = []
        for field in target_metric_group.fields:
            if field.monitor_type == "dimension":
                dimension_fields.append(
                    {
                        "field_name": field.name,
                        "unit": field.unit,
                        "type": field.type,
                        "description": field.description,
                    }
                )

        existing_dimension_names = {dim["field_name"] for dim in dimension_fields}
        for builtin_dimension in PROCESS_BUILD_IN_DIMENSIONS:
            if builtin_dimension in existing_dimension_names:
                continue
            dimension_fields.append(
                {
                    "field_name": builtin_dimension,
                    "unit": "none",
                    "type": "string",
                    "description": builtin_dimension,
                }
            )

        for field in target_metric_group.fields:
            if field.monitor_type != "metric":
                continue
            time_series_group_fields.append(
                {
                    "field_name": field.name,
                    "tag_list": dimension_fields,
                }
            )

        return time_series_group_fields

    @override
    def delete_result_tables(self, **kwargs: Any) -> None:
        """删除进程插件结果表。"""
        operator = kwargs.get("operator")
        time_series_group_id = kwargs.get("time_series_group_id")
        if not operator:
            raise ValueError("operator参数是必需的")
        if time_series_group_id is None:
            raise ValueError("Process插件删除结果表需要提供time_series_group_id参数")

        api.metadata.delete_time_series_group(
            bk_tenant_id=self.plugin.bk_tenant_id,
            operator=operator,
            time_series_group_id=time_series_group_id,
        )


@final
class LogPluginDataLinker(BuiltInPluginDataLinker):
    """日志插件数据链路"""

    _PLUGIN_TYPE_PREFIX = "Log"
    _DATA_NAME_TEMPLATE = "{plugin_type}_{plugin_id}_{bk_biz_id}"
    _ADDITIONAL_OPTIONS = {"inject_local_time": True}

    @override
    def apply_data_ids(self, operator: str) -> None:
        """申请日志插件数据ID。"""
        data_name = self._DATA_NAME_TEMPLATE.format(
            plugin_type=self._PLUGIN_TYPE_PREFIX,
            plugin_id=self.plugin.id,
            bk_biz_id=self.plugin.bk_biz_id,
        )
        self._apply_data_id(
            operator=operator,
            data_id_key="bk_data_id",
            data_name_key="data_name",
            data_name=data_name,
            etl_config=ETLConfig.BK_STANDARD_V2_EVENT,
            type_label="log",
            data_description=f"plugin_type: {self.plugin.type}, plugin_id: {self.plugin.id}",
            additional_options=self._ADDITIONAL_OPTIONS,
        )

    @override
    def apply_result_tables(self, operator: str) -> None:
        """申请日志插件结果表。"""
        bk_data_id = self.plugin.related_params.get("bk_data_id")
        if not bk_data_id:
            raise ValueError("bk_data_id 是必需的")

        event_group_name = f"{self._PLUGIN_TYPE_PREFIX}_{self.plugin.id}"
        event_groups = api.metadata.query_event_group(
            bk_tenant_id=self.plugin.bk_tenant_id,
            event_group_name=event_group_name,
        )
        event_info_list = self._get_log_event_info_list()

        if event_groups:
            event_group = event_groups[0]
            event_group_id = event_group["event_group_id"]
            existing_event_info_list = event_group.get("event_info_list", [])
            is_changed = self._normalize_event_info(existing_event_info_list) != self._normalize_event_info(
                event_info_list
            )
            if is_changed:
                api.metadata.modify_event_group(
                    bk_tenant_id=self.plugin.bk_tenant_id,
                    operator=operator,
                    event_group_id=event_group_id,
                    event_info_list=event_info_list,
                )
            return

        api.metadata.create_event_group(
            bk_tenant_id=self.plugin.bk_tenant_id,
            operator=operator,
            bk_data_id=bk_data_id,
            bk_biz_id=self.plugin.bk_biz_id,
            event_group_name=event_group_name,
            label="bk_monitor",
            data_label="log",
            event_info_list=event_info_list,
        )

    @staticmethod
    def _normalize_event_info(
        event_info_list: list[dict[str, Any]] | list[EventInfoConfig],
    ) -> list[tuple[str, tuple[str, ...]]]:
        """标准化事件信息列表，用于比较。"""
        normalized: list[tuple[str, tuple[str, ...]]] = []
        for event_info in event_info_list:
            event_name = str(event_info.get("event_name", ""))
            raw_dimension_list = event_info.get("dimension_list", [])
            if isinstance(raw_dimension_list, list):
                dimension_values: list[str] = []
                for item in cast(list[Any], raw_dimension_list):
                    dimension_values.append(str(item))
            else:
                dimension_values = []
            dimension_list = tuple(sorted(dimension_values))
            normalized.append((event_name, dimension_list))
        return sorted(normalized)

    def _get_default_dimensions(self) -> set[str]:
        """获取日志插件默认维度。"""
        dimensions = set(LOG_DEFAULT_DIMENSIONS)
        if self.plugin.label in ["component", "service_module"]:
            dimensions.add("bk_target_service_instance_id")
        return dimensions

    def _get_log_event_info_list(self) -> list[EventInfoConfig]:
        """获取日志插件事件列表。"""
        event_info_list: list[EventInfoConfig] = []
        rules = self.plugin.related_params.get("rules", [])
        if not rules:
            return event_info_list

        pattern_regex = re.compile(r"(?<=<)[^<>]+(?=>)")
        default_dimensions = self._get_default_dimensions()
        for rule in rules:
            rule_name = str(rule.get("name", ""))
            pattern_value = rule.get("pattern", "")
            rule_pattern = pattern_value if isinstance(pattern_value, str) else ""
            rule_dimensions: set[str] = set(pattern_regex.findall(rule_pattern))
            rule_dimensions.update(default_dimensions)
            event_info_list.append(
                {
                    "event_name": rule_name,
                    "dimension_list": sorted(list(rule_dimensions)),
                }
            )
        return event_info_list

    @override
    def delete_result_tables(self, **kwargs: Any) -> None:
        """删除日志插件结果表。"""
        operator = kwargs.get("operator")
        event_group_id = kwargs.get("event_group_id")
        if not operator:
            raise ValueError("operator参数是必需的")
        if event_group_id is None:
            raise ValueError(f"{self.plugin.type}插件删除结果表需要提供event_group_id参数")

        api.metadata.delete_event_group(
            bk_tenant_id=self.plugin.bk_tenant_id,
            operator=operator,
            event_group_id=event_group_id,
        )


@final
class SNMPTrapPluginDataLinker(LogPluginDataLinker):
    """SNMP Trap插件数据链路"""

    _PLUGIN_TYPE_PREFIX = "SNMP_Trap"
    etl_config = ETLConfig.BK_STANDARD_V2_EVENT

    @override
    def _get_log_event_info_list(self) -> list[EventInfoConfig]:
        """获取 SNMP Trap 插件事件列表。"""
        return [
            {
                "event_name": "TrapOID",
                "dimension_list": SNMP_TRAP_DEFAULT_DIMENSIONS,
            }
        ]
