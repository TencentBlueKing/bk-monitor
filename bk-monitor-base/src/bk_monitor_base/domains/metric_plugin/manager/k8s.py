import logging
from pathlib import Path
from typing import Any, ClassVar, Self, cast, final

from typing_extensions import override

from bk_monitor_base.domains.metric_plugin.constants import ETLConfig, MetricPluginStatus
from bk_monitor_base.domains.metric_plugin.define import (
    CreatePluginParams,
    CreatePluginVersionParams,
    MetricPlugin,
    MetricPluginDeployment,
    VersionTuple,
)
from bk_monitor_base.domains.metric_plugin.manager.base import BaseMetricPluginManager, OSType
from bk_monitor_base.domains.metric_plugin.models import MetricPluginModel
from bk_monitor_base.infras import third_party_api as api
from bk_monitor_base.infras.third_party_api.errors import BkApiError
from bk_monitor_base.infras.third_party_api.metadata.api import (
    CreateDataSourceParams,
    CreateTimeSeriesGroupParams,
    GetDataSourceResult,
    ModifyDataSourceParams,
    ModifyTimeSeriesGroupParams,
)

logger = logging.getLogger(__name__)


class K8sPluginDataLinker:
    """K8S 插件数据链路管理

    负责 K8S 类型插件的数据源（data_id）和时序分组（time_series_group）的申请与管理。

    与 NodemanPluginDataLinker 的关键差异：
    - ETL 配置使用 bk_standard_v2_time_series
    - 默认开启字段黑名单（enable_field_black_list=True），支持指标自动发现
    - data_label 使用配置传入的值（通常是 TENCENT_CLOUD_METRIC_PLUGIN_ID）
    """

    def __init__(self, plugin: MetricPlugin, plugin_model: MetricPluginModel):
        self.plugin: MetricPlugin = plugin
        self.plugin_model: MetricPluginModel = plugin_model

    def _save_related_params(self, related_params: dict[str, Any]) -> None:
        """将参数持久化到插件的 related_params"""
        self.plugin.related_params.update(related_params)
        self.plugin_model.related_params = self.plugin.related_params
        self.plugin_model.save(update_fields=["related_params"])

    def _get_old_data_id(self) -> GetDataSourceResult | None:
        """兼容查询旧版数据源"""
        data_names = [
            f"k8s_{self.plugin.id}".lower(),
            f"{self.plugin.bk_biz_id}_k8s_{self.plugin.id}".lower(),
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
                raise
        return None

    @property
    def _db_name(self) -> str:
        """与旧 PluginDataAccessor 一致的 db_name: {plugin_type}_{plugin_id} 全小写"""
        return f"k8s_{self.plugin.id}".lower()

    def _create_data_id(self, operator: str) -> tuple[int, str]:
        """创建数据源

        data_name 与旧代码一致，格式为 k8s_{plugin_id}（全小写，无随机后缀）。
        """
        data_name = self._db_name

        params: CreateDataSourceParams = {
            "bk_biz_id": self.plugin.bk_biz_id,
            "data_name": data_name,
            "etl_config": ETLConfig.BK_STANDARD_V2_TIME_SERIES.value,
            "source_label": "bk_monitor",
            "type_label": "time_series",
            "is_custom_source": True,
            "operator": operator,
            "data_description": data_name,
            "is_platform_data_id": self.plugin.is_global,
            "option": {
                "inject_local_time": True,
                "allow_dimensions_missing": True,
                "is_split_measurement": True,
            },
        }

        bk_data_id = api.metadata.create_data_source(bk_tenant_id=self.plugin.bk_tenant_id, **params)
        return bk_data_id, data_name

    def apply_data_ids(self, operator: str) -> None:
        """申请数据 ID（幂等）

        如果 related_params 中没有 bk_data_id，依次尝试查找旧数据源或创建新数据源。
        如果已有，则校准数据源配置。
        """
        bk_data_id = self.plugin.related_params.get("bk_data_id")
        if not bk_data_id:
            data_source = self._get_old_data_id()
            if not data_source:
                bk_data_id, data_name = self._create_data_id(operator)
                self._save_related_params({"bk_data_id": bk_data_id, "data_name": data_name})
                return
            self._save_related_params(
                {
                    "bk_data_id": data_source["bk_data_id"],
                    "data_name": data_source["data_name"],
                }
            )
            data_source_info = data_source
        else:
            data_source_info = api.metadata.get_data_source(
                bk_tenant_id=self.plugin.bk_tenant_id,
                bk_data_id=bk_data_id,
            )
            if self.plugin.related_params.get("data_name") != data_source_info["data_name"]:
                self._save_related_params({"data_name": data_source_info["data_name"]})

        update_params: ModifyDataSourceParams = {
            "data_id": data_source_info["bk_data_id"],
            "is_platform_data_id": self.plugin.is_global,
            "data_description": self._db_name,
            "option": {
                "inject_local_time": True,
                "allow_dimensions_missing": True,
                "is_split_measurement": True,
            },
            "operator": operator,
        }
        is_changed = any(
            data_source_info.get(key) != update_params.get(key)
            for key in ["is_platform_data_id", "data_description", "option"]
        )
        if is_changed:
            api.metadata.modify_data_source(bk_tenant_id=self.plugin.bk_tenant_id, **update_params)

    def apply_result_tables(self, operator: str) -> None:
        """申请结果表（幂等）

        创建或更新 time_series_group，K8S 类型默认开启字段黑名单和单指标单表。
        table_id 和 time_series_group_name 与旧 PluginDataAccessor 一致：
        - time_series_group_name = db_name = k8s_{plugin_id}
        - table_id = k8s_{plugin_id}.__default__
        - data_label 必须通过 related_params["data_label"] 传入（对应旧代码中的
          settings.TENCENT_CLOUD_METRIC_PLUGIN_ID，如 "qcloud_exporter"，不含业务 ID 后缀）
        """
        bk_data_id = self.plugin.related_params.get("bk_data_id")
        if not bk_data_id:
            raise ValueError("bk_data_id is required, call apply_data_ids first")

        db_name = self._db_name
        table_id = f"{db_name}.__default__"
        data_label_raw = self.plugin.related_params.get("data_label")
        if not data_label_raw:
            raise ValueError(  # noqa: TRY003
                "related_params['data_label'] is required for K8S plugin"  # noqa: ISC003
                + " (should be the base plugin ID without biz suffix, e.g. 'qcloud_exporter')"
            )
        data_label: str = str(data_label_raw).lower()

        time_series_groups = cast(
            list[dict[str, Any]],
            api.metadata.query_time_series_group(
                bk_tenant_id=self.plugin.bk_tenant_id,
                time_series_group_name=db_name,
                page_size=0,  # 不分页，获取全部数据以便刷新
            ),
        )

        if not time_series_groups:
            create_params: CreateTimeSeriesGroupParams = {
                "operator": operator,
                "bk_data_id": bk_data_id,
                "bk_biz_id": self.plugin.bk_biz_id,
                "table_id": table_id,
                "time_series_group_name": db_name,
                "label": self.plugin.label,
                "is_split_measurement": True,
                "data_label": data_label,
                "metric_info_list": [],
                "additional_options": {
                    "enable_field_black_list": True,
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
                "enable_field_black_list": True,
                "data_label": data_label,
                "metric_info_list": [],
            }
            api.metadata.modify_time_series_group(bk_tenant_id=self.plugin.bk_tenant_id, **modify_params)

    def delete_data_ids(self) -> None:
        """删除数据 ID（当前为空实现，K8S 数据源不支持物理删除）"""

    def delete_result_tables(self) -> None:
        """删除结果表（当前为空实现，K8S 结果表不支持物理删除）"""


@final
class K8sPluginManager(BaseMetricPluginManager):
    """K8S 插件管理器

    K8S 类型插件的核心特征：
    1. 创建插件时直接将版本状态设为 RELEASE（跳过 DEBUG 流程）
    2. 创建新版本后自动发布（无需手动调用 release）
    3. 首次创建版本时自动申请数据链路（data_id + time_series_group）
    4. 不需要注册到节点管理平台
    5. 不支持从插件包导入和导出
    """

    type: ClassVar[str] = "k8s"

    def _get_data_linker(self) -> K8sPluginDataLinker:
        return K8sPluginDataLinker(plugin=self.plugin, plugin_model=self._get_plugin_model())

    @classmethod
    @override
    def create_plugin(
        cls,
        bk_tenant_id: str,
        bk_biz_id: int,
        params: CreatePluginParams,
        operator: str,
    ) -> Self:
        """创建 K8S 插件

        K8S 插件创建后直接进入 RELEASE 状态。
        数据链路申请在 create_plugin_version / release_plugin_version 中自动完成。

        Note:
            调用方应在创建插件后、调用 apply_data_link 或 create_plugin_version 前，
            通过 set_related_params() 设置 related_params（必须包含 data_label）。
        """
        params = params.model_copy(update={"status": MetricPluginStatus.RELEASE})
        return super().create_plugin(bk_tenant_id, bk_biz_id, params, operator)

    def set_related_params(self, related_params: dict[str, Any]) -> None:
        """设置插件关联参数并持久化

        K8S 插件需要在 apply_data_link 之前设置 data_label 等参数。

        Args:
            related_params: 关联参数（会与已有参数合并）
        """
        plugin_model = self._get_plugin_model()
        plugin_model.related_params.update(related_params)
        plugin_model.save(update_fields=["related_params"])
        self.plugin.related_params.update(related_params)

    @override
    def create_plugin_version(self, params: CreatePluginVersionParams, operator: str) -> tuple[bool, VersionTuple]:
        """创建 K8S 插件版本

        创建版本后自动发布，首次创建时申请数据链路。
        更新版本时跳过数据链路申请（已存在）。
        """
        has_data_link = "bk_data_id" in self.plugin.related_params
        version_changed, version = super().create_plugin_version(params=params, operator=operator)
        if version_changed:
            self.release_plugin_version(
                operator=operator,
                apply_data_link=not has_data_link,
            )
        return version_changed, version

    @override
    def apply_data_link(self, operator: str) -> Any:
        """申请数据链路

        创建数据 ID 和时序分组，结果存入插件的 related_params。函数幂等。
        """
        data_linker = self._get_data_linker()
        data_linker.apply_data_ids(operator)
        data_linker.apply_result_tables(operator)
        return self.plugin.related_params

    @override
    def apply_data_link_with_deployment(self, deployment: MetricPluginDeployment, operator: str) -> Any:
        """K8S 插件的数据链路基于插件级别，不基于部署项"""
        return None

    @override
    def delete_data_link(self, operator: str) -> Any:
        """删除数据链路"""
        data_linker = self._get_data_linker()
        data_linker.delete_data_ids()
        data_linker.delete_result_tables()
        return None

    @override
    def delete_data_link_with_deployment(self, deployment: MetricPluginDeployment, operator: str) -> Any:
        """K8S 插件的数据链路基于插件级别，不基于部署项"""
        return None

    @override
    def get_supported_os_types(self) -> list[OSType]:
        """K8S 插件不依赖操作系统类型"""
        return []

    @override
    def register(self, operator: str) -> list[str]:
        """K8S 插件无需注册到节点管理平台"""
        return []

    @override
    def export_package(self, operator: str) -> str:
        raise NotImplementedError("K8S 插件不支持导出插件包")

    @classmethod
    @override
    def _parse_define(
        cls,
        bk_tenant_id: str,
        operator: str,
        extract_dir: Path,
        plugin_id: str,
        meta_data: dict[str, Any],
    ) -> dict[str, Any]:
        raise NotImplementedError("K8S 插件不支持从插件包导入")
