"""
测试 CustomNodemanPluginDataLinker 数据链路逻辑。

覆盖范围：
- apply_data_ids：新建数据源/复用旧数据源/已存在数据源的更新检查
- _get_old_data_id：metadata API “不存在”场景返回 None，其它错误需抛出
- _get_time_series_metrics：维度合并（插件维度/内置维度/注入维度）与重复处理
- apply_result_tables：创建/更新时序分组
"""

import pytest
from pytest_mock import MockerFixture

from bk_monitor_base.domains.metric_plugin.constants import SNMP_TRAP_DEFAULT_DIMENSIONS
from bk_monitor_base.domains.metric_plugin.define import (
    MetricPlugin,
    MetricPluginMetricField,
    MetricPluginMetricGroup,
    MetricPluginParams,
    MetricPluginStatus,
    VersionTuple,
    format_version_padded,
)
from bk_monitor_base.domains.metric_plugin.manager.node_man.datalink import (
    CustomNodemanPluginDataLinker,
    LogPluginDataLinker,
    ProcessPluginDataLinker,
    SNMPTrapPluginDataLinker,
)
from bk_monitor_base.domains.metric_plugin.manager.node_man.define import (
    NodemanPluginParamsMode,
    NodemanPluginParamsType,
)
from bk_monitor_base.domains.metric_plugin.manager.node_man.log import LogPluginManager
from bk_monitor_base.domains.metric_plugin.manager.node_man.process import ProcessPluginManager
from bk_monitor_base.domains.metric_plugin.manager.node_man.snmp_trap import SNMPTrapPluginManager
from bk_monitor_base.domains.metric_plugin.models import MetricPluginModel, MetricPluginVersionModel
from bk_monitor_base.infras.third_party_api.errors import BkApiError


def _create_plugin_for_datalink(
    *,
    bk_tenant_id: str = "test_tenant",
    bk_biz_id: int = 2,
    plugin_id: str = "test_plugin",
    plugin_type: str = "script",
    label: str = "service_module",
    enable_metric_discovery: bool = True,
    related_params: dict | None = None,
) -> tuple[MetricPluginModel, MetricPlugin]:
    """构造一个带版本的插件对象，便于测试 datalink。

    Returns:
        (plugin_model, plugin): plugin 为 pydantic 模型对象。
    """
    plugin_model = MetricPluginModel.objects.create(
        bk_tenant_id=bk_tenant_id,
        bk_biz_id=bk_biz_id,
        plugin_id=plugin_id,
        type=plugin_type,
        created_by="admin",
        label=label,
        related_params=related_params or {},
    )

    metrics = [
        MetricPluginMetricGroup(
            table_name="test_metric",
            fields=[
                # 插件定义的维度（包含与内置维度同名的字段，用于验证去重）
                MetricPluginMetricField(
                    name="bk_target_ip",
                    type="string",
                    monitor_type="dimension",
                    unit="none",
                    description="插件定义维度：bk_target_ip",
                    is_active=True,
                ),
                MetricPluginMetricField(
                    name="custom_dim",
                    type="string",
                    monitor_type="dimension",
                    unit="none",
                    description="插件定义维度：custom_dim",
                    is_active=True,
                ),
                MetricPluginMetricField(
                    name="inactive_dim",
                    type="string",
                    monitor_type="dimension",
                    unit="none",
                    description="未启用维度（不应进入tag_list）",
                    is_active=False,
                ),
                # 指标字段
                MetricPluginMetricField(name="cpu_usage", type="double", monitor_type="metric", is_active=True),
            ],
        )
    ]

    params = [
        MetricPluginParams(
            name="host_dms",
            type=NodemanPluginParamsType.HOST,
            mode=NodemanPluginParamsMode.DMS_INSERT,
            description="注入维度：host_dms",
            default="",
            required=False,
        )
    ]

    MetricPluginVersionModel.objects.create(
        bk_tenant_id=bk_tenant_id,
        bk_biz_id=bk_biz_id,
        plugin=plugin_model,
        name="测试插件",
        description_md="# 测试插件",
        params=[p.model_dump() for p in params],
        define={"linux": {"filename": "test.sh", "script_content_base64": ""}},
        metrics=[m.model_dump() for m in metrics],
        enable_metric_discovery=enable_metric_discovery,
        version=format_version_padded(VersionTuple(1, 0)),
        version_log="init",
        status=MetricPluginStatus.DEBUG.value,
        updated_by="admin",
        is_support_remote=False,
    )

    plugin = plugin_model.to_plugin()
    # 注意：to_plugin 不会把 MetricPluginModel.related_params 带入 plugin 对象，需要手动同步。
    plugin.related_params = dict(plugin_model.related_params)
    return plugin_model, plugin


def _create_built_in_plugin_for_datalink(
    *,
    plugin_type: str,
    plugin_id: str,
    label: str = "host_process",
    related_params: dict | None = None,
) -> tuple[MetricPluginModel, MetricPlugin]:
    """构造一个内置插件对象，便于测试 BuiltIn DataLinker。"""
    plugin_model = MetricPluginModel.objects.create(
        bk_tenant_id="test_tenant",
        bk_biz_id=2,
        plugin_id=plugin_id,
        type=plugin_type,
        created_by="admin",
        label=label,
        related_params=related_params or {},
    )

    if plugin_type == "process":
        metrics = [
            MetricPluginMetricGroup(
                table_name="perf",
                fields=[
                    MetricPluginMetricField(
                        name="cpu_total_pct",
                        type="double",
                        monitor_type="metric",
                        unit="percentunit",
                        description="cpu_total_pct",
                        is_active=True,
                    ),
                    MetricPluginMetricField(
                        name="process_name",
                        type="string",
                        monitor_type="dimension",
                        unit="none",
                        description="process_name",
                        is_active=True,
                    ),
                ],
            ),
            MetricPluginMetricGroup(
                table_name="port",
                fields=[
                    MetricPluginMetricField(
                        name="alive",
                        type="double",
                        monitor_type="metric",
                        unit="none",
                        description="alive",
                        is_active=True,
                    ),
                    MetricPluginMetricField(
                        name="listen_port",
                        type="string",
                        monitor_type="dimension",
                        unit="none",
                        description="listen_port",
                        is_active=True,
                    ),
                ],
            ),
        ]
    else:
        metrics = [
            MetricPluginMetricGroup(
                table_name="base",
                fields=[
                    MetricPluginMetricField(
                        name="event.count",
                        type="double",
                        monitor_type="metric",
                        unit="none",
                        description="event.count",
                        is_active=True,
                    ),
                    MetricPluginMetricField(
                        name="bk_target_ip",
                        type="string",
                        monitor_type="dimension",
                        unit="none",
                        description="bk_target_ip",
                        is_active=True,
                    ),
                ],
            )
        ]

    MetricPluginVersionModel.objects.create(
        bk_tenant_id="test_tenant",
        bk_biz_id=2,
        plugin=plugin_model,
        name=f"测试{plugin_type}插件",
        description_md=f"# 测试{plugin_type}插件",
        params=[],
        define={"linux": {"filename": "test.sh", "script_content_base64": ""}},
        metrics=[m.model_dump() for m in metrics],
        enable_metric_discovery=False,
        version=format_version_padded(VersionTuple(1, 0)),
        version_log="init",
        status=MetricPluginStatus.DEBUG.value,
        updated_by="admin",
        is_support_remote=False,
    )

    plugin = plugin_model.to_plugin()
    plugin.related_params = dict(plugin_model.related_params)
    return plugin_model, plugin


@pytest.mark.django_db(databases=["default"])
class TestCustomNodemanPluginDataLinker:
    """测试 CustomNodemanPluginDataLinker 类。"""

    def test_get_old_data_id_not_found_returns_none(self, mocker: MockerFixture):
        """当 metadata 返回“DataSource 不存在”时，_get_old_data_id 应返回 None。"""
        plugin_model, plugin = _create_plugin_for_datalink()
        linker = CustomNodemanPluginDataLinker(plugin, plugin_model=plugin_model)

        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.datalink.api.metadata.get_data_source",
            side_effect=BkApiError(
                module="metadata",
                action="get_data_source",
                method="GET",
                url="/",
                message="DataSource matching query does not exist",
            ),
        )

        assert linker._get_old_data_id() is None

    def test_get_old_data_id_other_error_raises(self, mocker: MockerFixture):
        """当 metadata 返回其它错误时，_get_old_data_id 应抛出异常以避免重复创建数据源。"""
        plugin_model, plugin = _create_plugin_for_datalink()
        linker = CustomNodemanPluginDataLinker(plugin, plugin_model=plugin_model)

        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.datalink.api.metadata.get_data_source",
            side_effect=BkApiError(
                module="metadata",
                action="get_data_source",
                method="GET",
                url="/",
                message="Some other error",
            ),
        )

        with pytest.raises(BkApiError):
            linker._get_old_data_id()

    def test_apply_data_ids_create_when_no_old_data_source(self, mocker: MockerFixture):
        """当没有 bk_data_id 且旧数据源不存在时，应创建新数据源并写回 related_params。"""
        plugin_model, plugin = _create_plugin_for_datalink(related_params={})
        linker = CustomNodemanPluginDataLinker(plugin, plugin_model=plugin_model)

        mocker.patch.object(linker, "_get_old_data_id", return_value=None)
        mocker.patch.object(linker, "_create_data_id", return_value=(123, "script_test_plugin_ABCDEFGH"))
        modify_mocker = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.datalink.api.metadata.modify_data_source"
        )

        linker.apply_data_ids(operator="admin")

        # 断言：创建后立即返回，不应尝试 modify
        modify_mocker.assert_not_called()

        assert plugin.related_params["bk_data_id"] == 123
        assert plugin.related_params["data_name"] == "script_test_plugin_ABCDEFGH"

        plugin_model.refresh_from_db()
        assert plugin_model.related_params["bk_data_id"] == 123
        assert plugin_model.related_params["data_name"] == "script_test_plugin_ABCDEFGH"

    def test_apply_data_ids_use_old_data_source_and_modify_when_changed(self, mocker: MockerFixture):
        """当复用旧数据源且数据源配置与期望不一致时，应调用 modify_data_source。"""
        plugin_model, plugin = _create_plugin_for_datalink(related_params={})
        plugin.is_global = True  # 触发 is_platform_data_id 的变化
        linker = CustomNodemanPluginDataLinker(plugin, plugin_model=plugin_model)

        data_source = {
            "bk_data_id": 101,
            "data_name": "script_test_plugin",
            "is_platform_data_id": False,
            "data_description": "old desc",
            "option": {"inject_local_time": False, "allow_dimensions_missing": False, "is_split_measurement": False},
        }
        mocker.patch.object(linker, "_get_old_data_id", return_value=data_source)
        modify_mocker = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.datalink.api.metadata.modify_data_source"
        )

        linker.apply_data_ids(operator="admin")

        modify_mocker.assert_called_once()
        call_kwargs = modify_mocker.call_args.kwargs
        assert call_kwargs["bk_tenant_id"] == plugin.bk_tenant_id
        assert call_kwargs["operator"] == "admin"
        assert call_kwargs["data_id"] == 101
        assert call_kwargs["is_platform_data_id"] is True

        assert plugin.related_params["bk_data_id"] == 101
        assert plugin.related_params["data_name"] == "script_test_plugin"

    def test_apply_data_ids_existing_updates_data_name_and_skip_modify_when_not_changed(self, mocker: MockerFixture):
        """当 bk_data_id 已存在且配置一致时，不应调用 modify_data_source；若 data_name 不一致需同步。"""
        plugin_model, plugin = _create_plugin_for_datalink(
            related_params={"bk_data_id": 101, "data_name": "old_name"},
            enable_metric_discovery=True,
        )
        plugin.related_params = {"bk_data_id": 101, "data_name": "old_name"}
        plugin.is_global = False
        linker = CustomNodemanPluginDataLinker(plugin, plugin_model=plugin_model)

        expected_option = {
            "inject_local_time": True,
            "allow_dimensions_missing": True,
            "is_split_measurement": True,
        }
        data_source = {
            "bk_data_id": 101,
            "data_name": "new_name",
            "is_platform_data_id": False,
            "data_description": f"plugin_type: {plugin.type}, plugin_id: {plugin.id}",
            "option": expected_option,
        }

        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.datalink.api.metadata.get_data_source",
            return_value=data_source,
        )
        modify_mocker = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.datalink.api.metadata.modify_data_source"
        )

        linker.apply_data_ids(operator="admin")

        # 仅 data_name 需要同步；数据源配置一致，不应 modify
        modify_mocker.assert_not_called()
        assert plugin.related_params["bk_data_id"] == 101
        assert plugin.related_params["data_name"] == "new_name"

    def test_get_time_series_metrics_merge_dimensions(self):
        """_get_time_series_metrics 应合并维度（插件/内置/注入），并避免内置维度重复。"""
        plugin_model, plugin = _create_plugin_for_datalink()
        linker = CustomNodemanPluginDataLinker(plugin, plugin_model=plugin_model)

        metric_info_list = linker._get_time_series_metrics()

        # 只有一个 metric 字段，因此只应生成 1 条 metric_info
        assert len(metric_info_list) == 1
        metric_info = metric_info_list[0]
        assert metric_info["field_name"] == "cpu_usage"
        assert metric_info["label"] == plugin.label

        tag_fields = {tag["field_name"] for tag in metric_info["tag_list"]}

        # 插件定义的维度应存在（active）
        assert "custom_dim" in tag_fields
        # 未启用维度不应进入 tag_list
        assert "inactive_dim" not in tag_fields
        # 注入维度应存在
        assert "host_dms" in tag_fields
        # service_module 标签下，服务实例类内置维度应存在
        assert "bk_target_service_instance_id" in tag_fields
        # 插件中已定义 bk_target_ip，因此内置维度同名项不会重复添加（集合判断即可）
        assert "bk_target_ip" in tag_fields

    def test_apply_result_tables_create_when_not_exists(self, mocker: MockerFixture):
        """当时序分组不存在时，应调用 create_time_series_group。"""
        plugin_model, plugin = _create_plugin_for_datalink(
            related_params={"bk_data_id": 101, "data_name": "script_test_plugin_x"},
            enable_metric_discovery=True,
        )
        plugin.related_params = {"bk_data_id": 101, "data_name": "script_test_plugin_x"}
        linker = CustomNodemanPluginDataLinker(plugin, plugin_model=plugin_model)

        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.datalink.api.metadata.query_time_series_group",
            return_value=[],
        )
        create_mocker = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.datalink.api.metadata.create_time_series_group"
        )
        modify_mocker = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.datalink.api.metadata.modify_time_series_group"
        )

        linker.apply_result_tables(operator="admin")

        modify_mocker.assert_not_called()
        create_mocker.assert_called_once()
        call_kwargs = create_mocker.call_args.kwargs
        assert call_kwargs["bk_tenant_id"] == plugin.bk_tenant_id
        assert call_kwargs["bk_data_id"] == 101
        assert call_kwargs["time_series_group_name"] == "script_test_plugin_x"
        assert call_kwargs["bk_biz_id"] == plugin.bk_biz_id
        assert call_kwargs["label"] == plugin.label
        assert call_kwargs["additional_options"]["enable_field_black_list"] is True

        # metric_info_list 由 _get_time_series_metrics 生成，不做全量断言，只确认关键字段存在
        assert isinstance(call_kwargs["metric_info_list"], list)
        assert call_kwargs["metric_info_list"][0]["field_name"] == "cpu_usage"

    def test_apply_result_tables_modify_when_exists(self, mocker: MockerFixture):
        """当时序分组已存在时，应调用 modify_time_series_group。"""
        plugin_model, plugin = _create_plugin_for_datalink(
            related_params={"bk_data_id": 101, "data_name": "script_test_plugin_x"},
            enable_metric_discovery=False,
        )
        plugin.related_params = {"bk_data_id": 101, "data_name": "script_test_plugin_x"}
        linker = CustomNodemanPluginDataLinker(plugin, plugin_model=plugin_model)

        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.datalink.api.metadata.query_time_series_group",
            return_value=[{"time_series_group_id": 42}],
        )
        create_mocker = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.datalink.api.metadata.create_time_series_group"
        )
        modify_mocker = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.datalink.api.metadata.modify_time_series_group"
        )

        linker.apply_result_tables(operator="admin")

        create_mocker.assert_not_called()
        modify_mocker.assert_called_once()
        call_kwargs = modify_mocker.call_args.kwargs
        assert call_kwargs["bk_tenant_id"] == plugin.bk_tenant_id
        assert call_kwargs["time_series_group_id"] == 42
        assert call_kwargs["enable_field_black_list"] is False

    def test_apply_result_tables_missing_related_params_raise(self):
        """当缺少 bk_data_id 或 data_name 时，应抛出 ValueError。"""
        plugin_model, plugin = _create_plugin_for_datalink(related_params={})
        plugin.related_params = {}
        linker = CustomNodemanPluginDataLinker(plugin, plugin_model=plugin_model)

        with pytest.raises(ValueError, match="bk_data_id and data_name are required"):
            linker.apply_result_tables(operator="admin")

    def test_refresh_metrics_no_op_when_metric_discovery_disabled(self, mocker: MockerFixture):
        """未开启自动发现时，应直接返回且不查询 metadata。"""
        plugin_model, plugin = _create_plugin_for_datalink(
            related_params={"data_name": "script_test_plugin_x"},
            enable_metric_discovery=False,
        )
        linker = CustomNodemanPluginDataLinker(plugin, plugin_model=plugin_model)
        query_mocker = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.datalink.api.metadata.query_time_series_group"
        )

        linker.refresh_metrics(operator="admin")

        query_mocker.assert_not_called()

    def test_refresh_metrics_no_op_when_metadata_is_empty(self, mocker: MockerFixture):
        """metadata 无返回数据时，应保持 metrics 不变。"""
        plugin_model, plugin = _create_plugin_for_datalink(
            related_params={"data_name": "script_test_plugin_x"},
            enable_metric_discovery=True,
        )
        linker = CustomNodemanPluginDataLinker(plugin, plugin_model=plugin_model)
        version_model = MetricPluginVersionModel.objects.get(plugin=plugin_model)
        original_metrics = version_model.metrics
        query_mocker = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.datalink.api.metadata.query_time_series_group",
            return_value=[],
        )

        linker.refresh_metrics(operator="admin")

        query_mocker.assert_called_once()
        version_model.refresh_from_db()
        assert version_model.metrics == original_metrics
        assert version_model.updated_by == "admin"

    def test_refresh_metrics_can_fallback_to_old_data_source(self, mocker: MockerFixture):
        """缺少 data_name 时，应兼容通过旧数据源名称回补后继续刷新。"""
        plugin_model, plugin = _create_plugin_for_datalink(
            related_params={},
            enable_metric_discovery=True,
        )
        linker = CustomNodemanPluginDataLinker(plugin, plugin_model=plugin_model)
        old_data_source = {
            "bk_data_id": 201,
            "data_name": "script_test_plugin",
        }
        get_old_data_id_mocker = mocker.patch.object(linker, "_get_old_data_id", return_value=old_data_source)
        query_mocker = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.datalink.api.metadata.query_time_series_group",
            return_value=[],
        )

        linker.refresh_metrics(operator="admin")

        get_old_data_id_mocker.assert_called_once()
        query_mocker.assert_called_once_with(
            bk_tenant_id=plugin.bk_tenant_id,
            time_series_group_name="script_test_plugin",
            page_size=0,
        )
        assert plugin.related_params["bk_data_id"] == 201
        assert plugin.related_params["data_name"] == "script_test_plugin"

    def test_refresh_metrics_can_fill_data_name_from_bk_data_id(self, mocker: MockerFixture):
        """仅有 bk_data_id 时，应先反查 data_name 再继续刷新。"""
        plugin_model, plugin = _create_plugin_for_datalink(
            related_params={"bk_data_id": 202},
            enable_metric_discovery=True,
        )
        linker = CustomNodemanPluginDataLinker(plugin, plugin_model=plugin_model)
        get_data_source_mocker = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.datalink.api.metadata.get_data_source",
            return_value={
                "bk_data_id": 202,
                "data_name": "script_test_plugin_by_id",
            },
        )
        query_mocker = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.datalink.api.metadata.query_time_series_group",
            return_value=[],
        )

        linker.refresh_metrics(operator="admin")

        get_data_source_mocker.assert_called_once_with(
            bk_tenant_id=plugin.bk_tenant_id,
            bk_data_id=202,
        )
        query_mocker.assert_called_once_with(
            bk_tenant_id=plugin.bk_tenant_id,
            time_series_group_name="script_test_plugin_by_id",
            page_size=0,
        )
        assert plugin.related_params["bk_data_id"] == 202
        assert plugin.related_params["data_name"] == "script_test_plugin_by_id"

    def test_refresh_metrics_patch_existing_and_add_new_fields(self, mocker: MockerFixture):
        """刷新 metrics 时应仅回填白名单字段，并补充新增指标、维度与默认分组。"""
        plugin_model, plugin = _create_plugin_for_datalink(
            related_params={"data_name": "script_test_plugin_x"},
            enable_metric_discovery=True,
        )
        plugin.metrics = [
            MetricPluginMetricGroup(
                table_name="cpu",
                table_desc="CPU",
                rules=[r"^cpu_"],
                fields=[
                    MetricPluginMetricField(
                        name="cpu_usage",
                        type="double",
                        monitor_type="metric",
                        description="old metric desc",
                        unit="none",
                        is_active=False,
                        is_diff_metric=True,
                        source_name="manual_source",
                    ),
                    MetricPluginMetricField(
                        name="host_name",
                        type="string",
                        monitor_type="dimension",
                        description="old host desc",
                        unit="none",
                        is_active=False,
                        source_name="host_source",
                    ),
                    MetricPluginMetricField(
                        name="legacy_dim",
                        type="string",
                        monitor_type="dimension",
                        description="legacy",
                        unit="none",
                        is_active=True,
                    ),
                ],
            )
        ]

        version_model = MetricPluginVersionModel.objects.get(plugin=plugin_model)
        version_model.metrics = [metric_group.model_dump() for metric_group in plugin.metrics]
        version_model.enable_metric_discovery = True
        version_model.save(update_fields=["metrics", "enable_metric_discovery"])

        linker = CustomNodemanPluginDataLinker(plugin, plugin_model=plugin_model)
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.datalink.api.metadata.query_time_series_group",
            return_value=[
                {
                    "metric_info_list": [
                        {
                            "field_name": "cpu_usage",
                            "description": "new metric desc",
                            "unit": "percent",
                            "is_active": "true",
                            "tag_list": [
                                {
                                    "field_name": "host_name",
                                    "description": "host desc new",
                                    "unit": "none",
                                    "type": "string",
                                    "is_disabled": False,
                                },
                                {
                                    "field_name": "zone",
                                    "description": "zone desc",
                                    "unit": "none",
                                    "type": "string",
                                    "is_disabled": False,
                                },
                                {
                                    "field_name": "bk_target_ip",
                                    "description": "目标IP",
                                    "unit": "none",
                                    "type": "string",
                                    "is_disabled": False,
                                },
                            ],
                        },
                        {
                            "field_name": "cpu_load",
                            "description": "cpu load desc",
                            "unit": "count",
                            "is_active": False,
                            "tag_list": [
                                {
                                    "field_name": "region",
                                    "description": "region desc",
                                    "unit": "none",
                                    "type": "string",
                                    "is_disabled": False,
                                }
                            ],
                        },
                    ]
                },
                {
                    "metric_info_list": [
                        {
                            "field_name": "disk_used",
                            "description": "disk used desc",
                            "unit": "MB",
                            "is_active": True,
                            "tag_list": [
                                {
                                    "field_name": "mount_point",
                                    "description": "mount point",
                                    "unit": "none",
                                    "type": "string",
                                    "is_disabled": False,
                                }
                            ],
                        }
                    ]
                },
            ],
        )

        linker.refresh_metrics(operator="operator")

        version_model.refresh_from_db()
        assert version_model.updated_by == "operator"

        groups = {
            group.table_name: group
            for group in [
                MetricPluginMetricGroup.model_validate(metric_group) for metric_group in version_model.metrics
            ]
        }

        cpu_group = groups["cpu"]
        cpu_fields = {field.name: field for field in cpu_group.fields}
        assert cpu_fields["cpu_usage"].description == "new metric desc"
        assert cpu_fields["cpu_usage"].unit == "percent"
        assert cpu_fields["cpu_usage"].is_active is True
        assert cpu_fields["cpu_usage"].is_diff_metric is True
        assert cpu_fields["cpu_usage"].source_name == "manual_source"

        assert cpu_fields["host_name"].description == "host desc new"
        assert cpu_fields["host_name"].is_active is True
        assert "legacy_dim" in cpu_fields
        assert "zone" in cpu_fields
        assert "region" in cpu_fields
        assert "bk_target_ip" not in cpu_fields
        assert cpu_fields["cpu_load"].description == "cpu load desc"
        assert cpu_fields["cpu_load"].is_active is False

        default_group = groups["group_default"]
        default_fields = {field.name: field for field in default_group.fields}
        assert default_group.table_desc == "默认分组"
        assert "disk_used" in default_fields
        assert "mount_point" in default_fields


@pytest.mark.django_db(databases=["default"])
class TestBuiltInPluginDataLinker:
    """测试内置插件 DataLinker 的拆分实现与 API 传参。"""

    def test_process_manager_apply_data_link(self, mocker: MockerFixture):
        """进程插件管理器应直接调用 ProcessPluginDataLinker。"""
        _, process_plugin = _create_built_in_plugin_for_datalink(plugin_type="process", plugin_id="process_plugin")
        fake_manager = mocker.Mock()
        fake_manager.plugin = process_plugin
        fake_linker = mocker.Mock()
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.process.ProcessPluginDataLinker",
            return_value=fake_linker,
        )

        result = ProcessPluginManager.apply_data_link(fake_manager, operator="admin")

        fake_linker.apply_data_ids.assert_called_once_with("admin")
        fake_linker.apply_result_tables.assert_called_once_with("admin")
        assert result == process_plugin.related_params

    def test_log_manager_apply_data_link(self, mocker: MockerFixture):
        """日志插件管理器应直接调用 LogPluginDataLinker。"""
        _, log_plugin = _create_built_in_plugin_for_datalink(plugin_type="log", plugin_id="log_plugin")
        fake_manager = mocker.Mock()
        fake_manager.plugin = log_plugin
        fake_linker = mocker.Mock()
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.log.LogPluginDataLinker",
            return_value=fake_linker,
        )

        result = LogPluginManager.apply_data_link(fake_manager, operator="admin")

        fake_linker.apply_data_ids.assert_called_once_with("admin")
        fake_linker.apply_result_tables.assert_called_once_with("admin")
        assert result == log_plugin.related_params

    def test_snmp_trap_manager_apply_data_link(self, mocker: MockerFixture):
        """SNMP Trap 插件管理器应直接调用 SNMPTrapPluginDataLinker。"""
        _, snmp_plugin = _create_built_in_plugin_for_datalink(plugin_type="snmp_trap", plugin_id="snmp_plugin")
        fake_manager = mocker.Mock()
        fake_manager.plugin = snmp_plugin
        fake_linker = mocker.Mock()
        mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.snmp_trap.SNMPTrapPluginDataLinker",
            return_value=fake_linker,
        )

        result = SNMPTrapPluginManager.apply_data_link(fake_manager, operator="admin")

        fake_linker.apply_data_ids.assert_called_once_with("admin")
        fake_linker.apply_result_tables.assert_called_once_with("admin")
        assert result == snmp_plugin.related_params

    def test_process_apply_data_ids_create_data_source_use_flat_args(self, mocker: MockerFixture):
        """进程插件创建数据源应使用扁平参数，不应使用 params/bk_username。"""
        plugin_model, plugin = _create_built_in_plugin_for_datalink(
            plugin_type="process",
            plugin_id="process_plugin_data_id",
            related_params={},
        )
        linker = ProcessPluginDataLinker(plugin, plugin_model=plugin_model)
        mocker.patch.object(linker, "_get_old_data_id", return_value=None)
        create_mocker = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.datalink.api.metadata.create_data_source",
            side_effect=[101, 102],
        )

        linker.apply_data_ids(operator="admin")

        assert create_mocker.call_count == 2
        for call in create_mocker.call_args_list:
            call_kwargs = call.kwargs
            assert "params" not in call_kwargs
            assert "bk_username" not in call_kwargs
            assert call_kwargs["operator"] == "admin"
            assert "data_name" in call_kwargs

        assert plugin.related_params["perf_data_id"] == 101
        assert plugin.related_params["port_data_id"] == 102
        assert [call.kwargs["data_name"] for call in create_mocker.call_args_list] == [
            "2_custom_time_series_process_perf",
            "2_custom_time_series_process_port",
        ]

    def test_log_apply_data_ids_uses_legacy_data_name_prefix(self, mocker: MockerFixture):
        """日志插件申请 data_id 时应保持旧链路的 Log 前缀。"""
        plugin_model, plugin = _create_built_in_plugin_for_datalink(
            plugin_type="log",
            plugin_id="log_plugin_data_link",
            related_params={},
        )
        linker = LogPluginDataLinker(plugin, plugin_model=plugin_model)
        mocker.patch.object(linker, "_get_old_data_id", return_value=None)
        create_mocker = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.datalink.api.metadata.create_data_source",
            return_value=200,
        )

        linker.apply_data_ids(operator="admin")

        assert create_mocker.call_args.kwargs["data_name"] == "Log_log_plugin_data_link_2"
        assert plugin.related_params["bk_data_id"] == 200
        assert plugin.related_params["data_name"] == "Log_log_plugin_data_link_2"

    def test_log_apply_result_tables_use_flat_args(self, mocker: MockerFixture):
        """日志插件申请事件分组时应使用扁平参数，并正确处理 query_event_group 返回值。"""
        plugin_model, plugin = _create_built_in_plugin_for_datalink(
            plugin_type="log",
            plugin_id="log_plugin_data_link",
            label="service_module",
            related_params={
                "bk_data_id": 200,
                "rules": [{"name": "rule1", "pattern": "<biz_module> <path>"}],
            },
        )
        linker = LogPluginDataLinker(plugin, plugin_model=plugin_model)
        query_mocker = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.datalink.api.metadata.query_event_group",
            return_value=[],
        )
        create_mocker = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.datalink.api.metadata.create_event_group"
        )

        linker.apply_result_tables(operator="admin")

        query_kwargs = query_mocker.call_args.kwargs
        assert "params" not in query_kwargs
        assert query_kwargs["event_group_name"] == f"Log_{plugin.id}"

        create_kwargs = create_mocker.call_args.kwargs
        assert "params" not in create_kwargs
        assert create_kwargs["operator"] == "admin"
        assert create_kwargs["bk_data_id"] == 200
        assert create_kwargs["event_group_name"] == f"Log_{plugin.id}"
        assert "event_info_list" in create_kwargs
        assert "bk_target_service_instance_id" in create_kwargs["event_info_list"][0]["dimension_list"]

    def test_snmp_trap_apply_data_ids_uses_legacy_data_name_prefix(self, mocker: MockerFixture):
        """SNMP Trap 插件申请 data_id 时应保持旧链路的 SNMP_Trap 前缀。"""
        plugin_model, plugin = _create_built_in_plugin_for_datalink(
            plugin_type="snmp_trap",
            plugin_id="snmp_plugin_data_link",
            related_params={},
        )
        linker = SNMPTrapPluginDataLinker(plugin, plugin_model=plugin_model)
        mocker.patch.object(linker, "_get_old_data_id", return_value=None)
        create_mocker = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.datalink.api.metadata.create_data_source",
            return_value=300,
        )

        linker.apply_data_ids(operator="admin")

        assert create_mocker.call_args.kwargs["data_name"] == "SNMP_Trap_snmp_plugin_data_link_2"
        assert plugin.related_params["bk_data_id"] == 300
        assert plugin.related_params["data_name"] == "SNMP_Trap_snmp_plugin_data_link_2"

    def test_snmp_trap_apply_result_tables_use_legacy_event_group_name(self, mocker: MockerFixture):
        """SNMP Trap 插件申请事件分组时应保持旧链路的 SNMP_Trap 前缀。"""
        plugin_model, plugin = _create_built_in_plugin_for_datalink(
            plugin_type="snmp_trap",
            plugin_id="snmp_plugin_data_link",
            related_params={"bk_data_id": 300},
        )
        linker = SNMPTrapPluginDataLinker(plugin, plugin_model=plugin_model)
        query_mocker = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.datalink.api.metadata.query_event_group",
            return_value=[],
        )
        create_mocker = mocker.patch(
            "bk_monitor_base.domains.metric_plugin.manager.node_man.datalink.api.metadata.create_event_group"
        )

        linker.apply_result_tables(operator="admin")

        assert query_mocker.call_args.kwargs["event_group_name"] == "SNMP_Trap_snmp_plugin_data_link"
        assert create_mocker.call_args.kwargs["event_group_name"] == "SNMP_Trap_snmp_plugin_data_link"

    def test_snmp_trap_event_info_list(self):
        """SNMP Trap 插件应返回固定事件维度。"""
        plugin_model, plugin = _create_built_in_plugin_for_datalink(
            plugin_type="snmp_trap",
            plugin_id="snmp_plugin_data_link",
            related_params={"bk_data_id": 300},
        )
        linker = SNMPTrapPluginDataLinker(plugin, plugin_model=plugin_model)

        event_info_list = linker._get_log_event_info_list()
        assert event_info_list == [{"event_name": "TrapOID", "dimension_list": SNMP_TRAP_DEFAULT_DIMENSIONS}]
