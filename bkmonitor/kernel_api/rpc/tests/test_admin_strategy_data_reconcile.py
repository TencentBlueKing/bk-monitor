from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from types import ModuleType

import pytest

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc.registry import KernelRPCRegistry

MODULE_PATH = Path(__file__).resolve().parents[1] / "functions" / "admin" / "strategy_data_reconcile.py"
SPEC = spec_from_file_location("admin_strategy_data_reconcile_for_test", MODULE_PATH)
admin_strategy_data_reconcile = module_from_spec(SPEC)
SPEC.loader.exec_module(admin_strategy_data_reconcile)


def test_collect_strategy_data_reconcile_stats_passes_normalized_params(monkeypatch):
    received = {}
    fake_module = ModuleType("monitor_web.data_migrate.strategy_data_reconcile")

    def fake_collect_strategy_data_stats(**kwargs):
        received.update(kwargs)
        return {
            "bk_biz_id": kwargs["bk_biz_id"],
            "strategy_count": 1,
            "skipped_strategy_count": 0,
            "raw_data_point_count": 3,
            "data_point_count": 2,
            "dimension_combination_count": 1,
            "strategies": [],
            "skipped": [],
            "errors": [],
        }

    fake_module.collect_strategy_data_stats = fake_collect_strategy_data_stats
    monkeypatch.setitem(sys.modules, "monitor_web.data_migrate.strategy_data_reconcile", fake_module)

    result = admin_strategy_data_reconcile.collect_strategy_data_reconcile_stats(
        {
            "bk_tenant_id": "tenant-a",
            "bk_biz_id": "2",
            "start_time": "100",
            "end_time": "200",
            "strategy_ids": "3, 1,3",
            "include_dimension_keys": "true",
            "max_workers": "8",
        }
    )

    assert received == {
        "bk_biz_id": 2,
        "start_time": 100,
        "end_time": 200,
        "strategy_ids": [1, 3],
        "include_dimension_keys": True,
        "max_workers": 8,
    }
    assert result["data"]["bk_biz_id"] == 2
    assert result["meta"]["func_name"] == admin_strategy_data_reconcile.FUNC_STRATEGY_DATA_RECONCILE_COLLECT
    assert result["meta"]["effective_bk_tenant_id"] == "tenant-a"


def test_collect_strategy_data_reconcile_stats_rejects_invalid_time_range():
    with pytest.raises(CustomException, match="start_time 必须小于 end_time"):
        admin_strategy_data_reconcile.collect_strategy_data_reconcile_stats(
            {"bk_biz_id": 2, "start_time": 200, "end_time": 100}
        )


def test_collect_strategy_data_reconcile_stats_rejects_invalid_max_workers():
    with pytest.raises(CustomException, match="max_workers 必须大于等于 1"):
        admin_strategy_data_reconcile.collect_strategy_data_reconcile_stats({"bk_biz_id": 2, "max_workers": 0})


def test_strategy_data_reconcile_rpc_registered():
    function = KernelRPCRegistry._functions.get(admin_strategy_data_reconcile.FUNC_STRATEGY_DATA_RECONCILE_COLLECT)
    detail = function.to_detail() if function else None

    assert detail is not None
    assert detail["summary"] == "Admin 统计业务策略查询数据"
    assert "include_dimension_keys" in detail["params_schema"]
    assert "max_workers" in detail["params_schema"]
