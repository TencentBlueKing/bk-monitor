"""strategy.converter 的单元测试。

目标：
- 通过“构造策略数据”验证各转换器的转换逻辑
- 对外部 API 调用使用 mock，避免依赖真实环境

注意：
- 本测试不依赖数据库写入，仅构造领域对象并调用 converter
"""

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from pytest_mock import MockerFixture

from bk_monitor_base.domains.strategy.constants import (
    EVENT_DETECT_LIST,
    EVENT_QUERY_CONFIG_MAP,
    SYSTEM_EVENT_RT_TABLE_ID,
)
from bk_monitor_base.domains.strategy.converter import (
    ActionOptionConvert,
    CMDBTopoNodeAggConvert,
    CMDBTopoNodeAggConvertWithBKData,
    EventTobeClosedConvert,
    FakeEventConvert,
    UptimeCheckConvert,
    convert_strategy,
)
from bk_monitor_base.domains.strategy.strategy import Strategy


def _load_case(case_id: str) -> dict[str, Any]:
    """加载 tests/domains/strategy/cases 下的策略 JSON。"""
    cases_dir = Path(__file__).resolve().parent / "cases"
    return cast(dict[str, Any], json.loads((cases_dir / f"{case_id}.json").read_text(encoding="utf-8")))


def _build_strategy(strategy_json: dict[str, Any]) -> Strategy:
    """通过 serializer 校验并构造 Strategy 聚合根。"""
    serializer = Strategy.Serializer(data=strategy_json)
    serializer.is_valid(raise_exception=True)
    validated = cast(dict[str, Any], serializer.validated_data)
    return Strategy(**validated)


class TestUptimeCheckConvert:
    """拨测策略转换测试。"""

    def test_convert_and_restore_success(self) -> None:
        """验证 convert 后字段/条件/算法被正确转换，restore 可逆。"""
        # Arrange: 使用独立 case（拨测配置差异较大，避免基于其它 case “魔改”）
        data = _load_case("uptimecheck_response_code")
        strategy = _build_strategy(deepcopy(data))

        # Act: convert
        UptimeCheckConvert.convert(strategy)

        # Assert: metric_field 替换为 available 且新增 error_code 条件
        query_config = strategy.items[0].query_configs[0]
        assert query_config.metric_field == "available"
        assert query_config.agg_condition[0]["key"] == "error_code"
        assert query_config.agg_condition[0]["method"] == "eq"
        assert query_config.agg_condition[0]["value"] == ["3003"]

        # task_id 值应被转换为字符串
        task_id_values = [
            c["value"]
            for c in query_config.agg_condition
            if c.get("key") == "task_id" and isinstance(c.get("value"), list)
        ]
        assert task_id_values == [["1"], ["2"]]

        # PartialNodes -> Threshold，threshold 取 count
        algorithm = strategy.items[0].algorithms[0]
        assert algorithm.type == "Threshold"
        assert algorithm.config == [[{"method": "gte", "threshold": 3}]]

        # Act: restore
        UptimeCheckConvert.restore(strategy)

        # Assert: metric_field 恢复为 response_code，error_code 条件被移除
        query_config = strategy.items[0].query_configs[0]
        assert query_config.metric_field == "response_code"
        assert all(c.get("key") != "error_code" for c in query_config.agg_condition)

        # 算法恢复为 PartialNodes 且 count 与 convert 前一致
        algorithm = strategy.items[0].algorithms[0]
        assert algorithm.type == "PartialNodes"
        assert algorithm.config == {"count": 3}

    def test_convert_missing_task_id_dimension_raises(self) -> None:
        """缺少 task_id 维度时应抛出异常。"""
        data = deepcopy(_load_case("uptimecheck_response_code"))

        qc = data["items"][0]["query_configs"][0]
        qc["agg_dimension"] = []  # 关键：缺少 task_id

        strategy = _build_strategy(data)

        with pytest.raises(Exception, match="监控维度请选择任务ID"):
            UptimeCheckConvert.convert(strategy)


class TestCMDBTopoNodeAggConvert:
    """拓扑层级聚合策略转换测试（create_result_table_metric_split）。"""

    def test_convert_calls_metadata_and_records_origin_config(self, mocker: MockerFixture) -> None:
        """满足条件时应调用 metadata API，并补充维度与 origin_config；restore 可逆。"""
        # Arrange: mock bkbase 配置开启 + 允许全量 cmdb_level
        fake_config = SimpleNamespace(
            blueking=SimpleNamespace(bkbase=SimpleNamespace(enabled=True, allow_all_cmdb_level=True))
        )
        mocker.patch("bk_monitor_base.domains.strategy.converter.get_config", return_value=fake_config)
        mocker.patch("bk_monitor_base.domains.strategy.converter.bk_biz_id_to_bk_tenant_id", return_value="tenant_2")
        mock_create_split = mocker.patch(
            "bk_monitor_base.domains.strategy.converter.api.metadata.create_result_table_metric_split",
            return_value={"table_id": "mock.split.table"},
        )

        base = _load_case("cpu_total_usage")
        data = deepcopy(base)

        # 关键：target 需要是拓扑节点，且 agg_dimension 不能包含 NOT_SPLIT_DIMENSIONS（如 bk_target_ip）
        data["items"][0]["target"] = [
            [
                {
                    "field": "host_topo_node",
                    "method": "eq",
                    "value": [{"bk_obj_id": "set", "bk_inst_id": 1}],
                }
            ]
        ]

        qc = data["items"][0]["query_configs"][0]
        qc["result_table_id"] = "bkmonitor.test_table"
        qc["metric_field"] = "usage"
        qc["agg_dimension"] = ["bk_target_cloud_id"]
        qc["agg_condition"] = []
        qc["metric_id"] = "bk_monitor.bkmonitor.test_table.usage"

        strategy = _build_strategy(data)
        # Strategy.Serializer 不暴露 update_user 字段，这里直接在对象上设置
        strategy.update_user = "pytest"

        # Act
        CMDBTopoNodeAggConvert.convert(strategy)

        # Assert: API 调用 + 参数校验
        mock_create_split.assert_called_once_with(
            bk_tenant_id="tenant_2",
            cmdb_level="bk_set_id",
            table_id="bkmonitor.test_table",
            operator="pytest",
        )

        query_config = strategy.items[0].query_configs[0]
        assert query_config.result_table_id == "mock.split.table"
        assert "bk_obj_id" in query_config.agg_dimension
        assert "bk_inst_id" in query_config.agg_dimension
        assert query_config.origin_config == {
            "result_table_id": "bkmonitor.test_table",
            "agg_dimension": ["bk_target_cloud_id"],
        }

        # Act: restore
        CMDBTopoNodeAggConvert.restore(strategy)

        # Assert: 结果表与维度恢复，origin_config 被清理
        query_config = strategy.items[0].query_configs[0]
        assert query_config.result_table_id == "bkmonitor.test_table"
        assert query_config.agg_dimension == ["bk_target_cloud_id"]
        assert not hasattr(query_config, "origin_config")

    def test_convert_system_table_raises(self, mocker: MockerFixture) -> None:
        """result_table_id 以 system. 开头时应抛异常。"""
        fake_config = SimpleNamespace(
            blueking=SimpleNamespace(bkbase=SimpleNamespace(enabled=True, allow_all_cmdb_level=True))
        )
        mocker.patch("bk_monitor_base.domains.strategy.converter.get_config", return_value=fake_config)

        base = _load_case("cpu_total_usage")
        data = deepcopy(base)
        data["items"][0]["target"] = [
            [{"field": "host_topo_node", "method": "eq", "value": [{"bk_obj_id": "set", "bk_inst_id": 1}]}]
        ]

        qc = data["items"][0]["query_configs"][0]
        qc["result_table_id"] = "system.cpu_summary"
        qc["agg_dimension"] = ["bk_target_cloud_id"]  # 避免 NOT_SPLIT_DIMENSIONS 导致提前 continue
        qc["metric_id"] = "bk_monitor.system.cpu_summary.usage"

        strategy = _build_strategy(data)
        strategy.update_user = "pytest"

        with pytest.raises(Exception, match="主机性能指标按CMDB动态节点聚合暂不可用"):
            CMDBTopoNodeAggConvert.convert(strategy)


class TestCMDBTopoNodeAggConvertWithBKData:
    """基于计算平台的 CMDB 预聚合转换测试（full_cmdb_node_info）。"""

    def test_convert_calls_full_cmdb_node_info_and_extend_dimensions(self, mocker: MockerFixture) -> None:
        """满足条件时应调用 full_cmdb_node_info，并补充 SPLIT_DIMENSIONS。"""
        fake_config = SimpleNamespace(blueking=SimpleNamespace(bkbase=SimpleNamespace(enabled=True)))
        mocker.patch("bk_monitor_base.domains.strategy.converter.get_config", return_value=fake_config)
        mocker.patch("bk_monitor_base.domains.strategy.converter.bk_biz_id_to_bk_tenant_id", return_value="tenant_2")
        mock_full_cmdb = mocker.patch(
            "bk_monitor_base.domains.strategy.converter.api.metadata.full_cmdb_node_info", return_value=None
        )

        base = _load_case("cpu_total_usage")
        data = deepcopy(base)
        # target：拓扑节点（host_topo_node）
        data["items"][0]["target"] = [[{"field": "host_topo_node", "method": "eq", "value": [{"bk_obj_id": "set"}]}]]

        qc = data["items"][0]["query_configs"][0]
        qc["result_table_id"] = "bkmonitor.test_table"
        qc["agg_dimension"] = ["bk_target_cloud_id"]  # 不包含 NOT_SPLIT_DIMENSIONS，触发逻辑
        qc["metric_id"] = "bk_monitor.bkmonitor.test_table.usage"

        strategy = _build_strategy(data)

        CMDBTopoNodeAggConvertWithBKData.convert(strategy)

        mock_full_cmdb.assert_called_once_with(bk_tenant_id="tenant_2", table_id="bkmonitor.test_table")
        query_config = strategy.items[0].query_configs[0]
        assert "bk_obj_id" in query_config.agg_dimension
        assert "bk_inst_id" in query_config.agg_dimension

    def test_convert_api_error_is_swallowed(self, mocker: MockerFixture) -> None:
        """API 调用异常应被捕获并吞掉（仅记录日志），不影响后续流程。"""
        fake_config = SimpleNamespace(blueking=SimpleNamespace(bkbase=SimpleNamespace(enabled=True)))
        mocker.patch("bk_monitor_base.domains.strategy.converter.get_config", return_value=fake_config)
        mocker.patch("bk_monitor_base.domains.strategy.converter.bk_biz_id_to_bk_tenant_id", return_value="tenant_2")
        mocker.patch(
            "bk_monitor_base.domains.strategy.converter.api.metadata.full_cmdb_node_info",
            side_effect=Exception("boom"),
        )

        base = _load_case("cpu_total_usage")
        data = deepcopy(base)
        data["items"][0]["target"] = [[{"field": "host_topo_node", "method": "eq", "value": [{"bk_obj_id": "set"}]}]]

        qc = data["items"][0]["query_configs"][0]
        qc["result_table_id"] = "bkmonitor.test_table"
        qc["agg_dimension"] = ["bk_target_cloud_id"]
        qc["metric_id"] = "bk_monitor.bkmonitor.test_table.usage"

        strategy = _build_strategy(data)
        before_dims = strategy.items[0].query_configs[0].agg_dimension.copy()

        # 不应抛异常
        CMDBTopoNodeAggConvertWithBKData.convert(strategy)

        after_dims = strategy.items[0].query_configs[0].agg_dimension
        assert after_dims == before_dims


class TestFakeEventConvert:
    """伪系统事件型策略转换测试。"""

    def test_convert_and_restore_success(self) -> None:
        """事件型 query_config 应被转换为真实时序配置，且 restore 可逆。"""
        data = deepcopy(_load_case("fake_event_os_restart"))
        strategy = _build_strategy(data)

        # Act: convert
        FakeEventConvert.convert(strategy)

        # Assert: query_config 字段映射为 EVENT_QUERY_CONFIG_MAP 中的真实时序配置
        query_config = strategy.items[0].query_configs[0]
        mapped = EVENT_QUERY_CONFIG_MAP["os_restart"]
        assert query_config.data_type_label == "time_series"
        assert query_config.result_table_id == mapped["result_table_id"]
        assert query_config.metric_field == mapped["metric_field"]
        assert query_config.agg_method == mapped["agg_method"]
        assert query_config.agg_interval == mapped["agg_interval"]
        assert query_config.agg_dimension == mapped["agg_dimension"]

        # 算法应调整为事件对应的检测算法
        algorithm = strategy.items[0].algorithms[0]
        assert algorithm.type == EVENT_DETECT_LIST["os_restart"][0]["type"]
        assert algorithm.config == EVENT_DETECT_LIST["os_restart"][0]["config"]

        # Act: restore
        FakeEventConvert.restore(strategy)

        # Assert: 恢复为 event 类型与 system.event 表，metric_field 还原为伪事件名
        query_config = strategy.items[0].query_configs[0]
        assert query_config.data_type_label == "event"
        assert query_config.result_table_id == SYSTEM_EVENT_RT_TABLE_ID
        assert query_config.metric_field == "os_restart"


class TestEventTobeClosedConvert:
    """事件恢复机制最终状态为关闭的转换测试。"""

    def test_convert_sets_recovery_status_close(self) -> None:
        """当所有 query_config 的 metric_id 命中关闭列表时，应设置 status_setter=close。"""
        # 该逻辑依赖 QueryConfig.get_metric_id() 的生成规则（event 型为 bk_monitor.<metric_field>），
        # 因此使用独立 event 型 case，避免在 time_series case 上做大幅度删改。
        strategy = _build_strategy(deepcopy(_load_case("event_close_gse_process_event")))
        assert strategy.detects[0].recovery_config.get("status_setter") == "recovery"

        # Act
        EventTobeClosedConvert.convert(strategy)

        # Assert
        assert strategy.detects[0].recovery_config.get("status_setter") == "close"


class TestActionOptionConvert:
    """处理套餐部分配置与通知配置对齐的转换测试。"""

    def test_convert_aligns_user_groups_and_time_options(self) -> None:
        """action.user_groups 应对齐 notice.user_groups，且补齐 start/end_time。"""
        strategy = _build_strategy(deepcopy(_load_case("action_option_align")))

        # sanity: action 初始 user_groups 与 notice 不一致
        assert strategy.actions[0].user_groups != strategy.notice.user_groups

        ActionOptionConvert.convert(strategy)

        action = strategy.actions[0]
        assert action.user_groups == strategy.notice.user_groups
        assert action.options["start_time"] == "00:00:00"
        assert action.options["end_time"] == "23:59:59"


class TestConvertStrategy:
    """convert_strategy 的组合/顺序集成测试。"""

    def test_convert_strategy_calls_all_converters_in_order(self, mocker: MockerFixture) -> None:
        """通过替换 Converters 列表为哨兵 converter，验证调用顺序。"""

        calls: list[str] = []

        class _C1:
            @classmethod
            def convert(cls, strategy: Strategy) -> None:  # noqa: ARG003
                calls.append("c1")

            @classmethod
            def restore(cls, strategy: Strategy) -> None:  # noqa: ARG003
                raise AssertionError("not used")

        class _C2:
            @classmethod
            def convert(cls, strategy: Strategy) -> None:  # noqa: ARG003
                calls.append("c2")

            @classmethod
            def restore(cls, strategy: Strategy) -> None:  # noqa: ARG003
                raise AssertionError("not used")

        # Arrange
        mocker.patch("bk_monitor_base.domains.strategy.converter.Converters", [_C1, _C2])
        strategy = _build_strategy(deepcopy(_load_case("cpu_total_usage")))

        # Act
        convert_strategy(strategy)

        # Assert
        assert calls == ["c1", "c2"]
