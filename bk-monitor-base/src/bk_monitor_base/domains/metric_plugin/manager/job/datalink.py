import random
import re
import string
from typing import Any, Literal, cast

from typing_extensions import override

from bk_monitor_base.domains.metric_plugin.constants import ETLConfig
from bk_monitor_base.domains.metric_plugin.define import (
    JOB_PLUGIN_BUILT_IN_DIMENSIONS,
    MetricPluginMetricField,
    MetricPluginMetricGroup,
    format_version_padded,
)
from bk_monitor_base.domains.metric_plugin.manager.datalink import MetricPluginDataLinker
from bk_monitor_base.domains.metric_plugin.models import MetricPluginVersionModel
from bk_monitor_base.infras import third_party_api as api
from bk_monitor_base.infras.third_party_api.errors import BkApiError
from bk_monitor_base.infras.third_party_api.metadata.api import (
    CreateDataSourceParams,
    CreateTimeSeriesGroupParams,
    GetDataSourceResult,
    ModifyDataSourceParams,
    ModifyTimeSeriesGroupParams,
)


class CustomSQLPluginDataLinker(MetricPluginDataLinker):
    """自定义SQL插件数据链路"""

    _DEFAULT_GROUP_NAME: str = "group_default"
    _DEFAULT_GROUP_DESC: str = "默认分组"
    _DMS_INSERT_MODE: str = "dms_insert"

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
        return ETLConfig.BK_STANDARD.value

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
        """获取 SQL 插件通过 dms_insert 额外注入的 label 名称。"""
        dms_fields: set[str] = set()
        for param in self.plugin.params:
            if param.mode != self._DMS_INSERT_MODE:
                continue

            default_value = param.default
            if isinstance(default_value, dict):
                # SQL 下发时 dms_insert 参数值是 {label_key: target_field}，结果表需要注册 label_key。
                default_mapping = cast(dict[Any, Any], default_value)
                dms_fields.update(str(field_name) for field_name in default_mapping if field_name)
                continue

            # 兼容旧配置：未声明默认映射时，用参数名作为注入维度名。
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

    def _get_auto_discovery_excluded_dimension_names(self) -> set[str]:
        """获取自动发现时不应回填到插件 metrics 配置的系统注入维度。"""

        return {dimension.field_name for dimension in JOB_PLUGIN_BUILT_IN_DIMENSIONS} | set(self._get_dms_fields())

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
            field.is_active = CustomSQLPluginDataLinker._normalize_bool(
                source.get("is_active"),
                default=not CustomSQLPluginDataLinker._normalize_bool(source.get("is_disabled"), default=False),
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
            is_active=CustomSQLPluginDataLinker._normalize_bool(metric.get("is_active"), default=True),
            source_name="",
        )

    @staticmethod
    def _build_dimension_field(tag: dict[str, Any]) -> MetricPluginMetricField:
        """将 metadata 维度转换为插件维度字段。"""
        return MetricPluginMetricField(
            name=str(tag.get("field_name", "") or ""),
            type=CustomSQLPluginDataLinker._normalize_field_type(tag.get("type", "string")),
            description=str(tag.get("description", "") or ""),
            monitor_type="dimension",
            unit=str(tag.get("unit", "") or ""),
            is_diff_metric=False,
            is_active=not CustomSQLPluginDataLinker._normalize_bool(tag.get("is_disabled"), default=False),
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

        excluded_dimension_names = self._get_auto_discovery_excluded_dimension_names()

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
                    if not tag_name or tag_name in excluded_dimension_names:
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

            # 结果表维度必须覆盖安装器实际注入的固定 labels，否则按目标查询会缺字段。
            for dimension in JOB_PLUGIN_BUILT_IN_DIMENSIONS:
                builtin_field = dimension.field_name
                if builtin_field in existing_dimension_fields:
                    continue
                existing_dimension_fields.add(builtin_field)
                tag_list.append(
                    {
                        "field_name": builtin_field,
                        "unit": "none",
                        "type": "string",
                        "description": dimension.description,
                    }
                )

            # 添加注入维度（避免重复）
            for dms_field in dms_fields:
                if dms_field in existing_dimension_fields:
                    continue
                existing_dimension_fields.add(dms_field)
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
