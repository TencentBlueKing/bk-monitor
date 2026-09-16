"""IssueConfig 领域对象及 Strategy 集成的测试。

覆盖范围：
- IssueConfig 领域对象的构造、序列化、校验
- IssueConfig 与 Strategy 的生命周期集成（save / delete / from_models / to_dict）
- StrategyIssueConfigModel 的 clean 校验
- 表不存在时的兼容性（通过 mock 模拟）
"""

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import OperationalError, ProgrammingError
from pytest_mock import MockerFixture
from rest_framework.exceptions import ValidationError as DRFValidationError

from bk_monitor_base.domains.strategy.models import (
    StrategyIssueConfigModel,
    StrategyModel,
)
from bk_monitor_base.domains.strategy.operation import (
    delete_strategy,
    get_strategy,
    save_strategy,
)
from bk_monitor_base.domains.strategy.strategy import IssueConfig, Strategy

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _StrategyJsonCase:
    case_id: str
    path: Path
    data: dict[str, Any]


def _load_strategy_cases() -> list[_StrategyJsonCase]:
    cases_dir = Path(__file__).resolve().parent / "cases"
    paths = sorted(cases_dir.glob("*.json"))
    cases: list[_StrategyJsonCase] = []
    for p in paths:
        case_id = p.stem
        data = json.loads(p.read_text(encoding="utf-8"))
        cases.append(_StrategyJsonCase(case_id=case_id, path=p, data=data))
    return cases


@pytest.fixture(scope="session")
def strategy_json_cases() -> list[_StrategyJsonCase]:
    return _load_strategy_cases()


def _setup_strategy_third_party_mocks(mocker: MockerFixture) -> None:
    """mock 第三方 API 调用。"""
    mocker.patch(
        "bk_monitor_base.infras.third_party_api.bkdata.api.auth_projects_data_check",
        return_value=True,
    )
    mocker.patch(
        "bk_monitor_base.infras.third_party_api.bkdata.api.auth_result_table",
        return_value=None,
    )
    mocker.patch(
        "bk_monitor_base.infras.third_party_api.unify_query.api.promql_to_struct",
        return_value={"query_list": []},
    )
    mocker.patch(
        "bk_monitor_base.infras.third_party_api.unify_query.api.struct_to_promql",
        return_value="",
    )


# ---------------------------------------------------------------------------
# 1. IssueConfig 领域对象单元测试（不依赖 DB）
# ---------------------------------------------------------------------------


class TestIssueConfigUnit:
    """IssueConfig 领域对象的纯逻辑测试。"""

    def test_constructor_defaults(self) -> None:
        """默认构造应产出合理的零值。"""
        ic = IssueConfig()
        assert ic.strategy_id == 0
        assert ic.bk_biz_id == 0
        assert ic.is_enabled is True
        assert ic.aggregate_dimensions == []
        assert ic.conditions == []
        assert ic.alert_levels == []

    def test_constructor_with_kwargs(self) -> None:
        """通过 kwargs 构造应正确赋值。"""
        ic = IssueConfig(
            strategy_id=10,
            bk_biz_id=2,
            is_enabled=False,
            aggregate_dimensions=["dim_a"],
            conditions=[{"key": "dim_a", "method": "eq", "value": ["x"]}],
            alert_levels=[1, 2],
        )
        assert ic.strategy_id == 10
        assert ic.bk_biz_id == 2
        assert ic.is_enabled is False
        assert ic.aggregate_dimensions == ["dim_a"]
        assert len(ic.conditions) == 1
        assert ic.alert_levels == [1, 2]

    def test_to_dict(self) -> None:
        """to_dict 应返回标准 4 字段字典。"""
        ic = IssueConfig(alert_levels=[1, 3], aggregate_dimensions=["host"])
        d = ic.to_dict()
        assert set(d.keys()) == {"is_enabled", "aggregate_dimensions", "conditions", "alert_levels"}
        assert d["alert_levels"] == [1, 3]
        assert d["aggregate_dimensions"] == ["host"]

    def test_serializer_valid(self) -> None:
        """Serializer 对合法输入应校验通过。"""
        data = {
            "is_enabled": True,
            "aggregate_dimensions": ["dim_a"],
            "conditions": [{"key": "dim_a", "method": "eq", "value": ["x"]}],
            "alert_levels": [1, 2, 3],
        }
        s = IssueConfig.Serializer(data=data)
        assert s.is_valid(), s.errors

    def test_serializer_defaults(self) -> None:
        """Serializer 空输入时应使用默认值。"""
        s = IssueConfig.Serializer(data={})
        assert s.is_valid(), s.errors
        validated = s.validated_data
        assert validated["is_enabled"] is True
        assert validated["aggregate_dimensions"] == []
        assert validated["conditions"] == []
        assert validated["alert_levels"] == []


# ---------------------------------------------------------------------------
# 2. IssueConfig.validate() 校验逻辑（表驱动）
# ---------------------------------------------------------------------------


class TestIssueConfigValidate:
    """IssueConfig.validate(strategy) 的跨模型约束校验。"""

    @staticmethod
    def _make_strategy_stub(public_dimensions: list[str]) -> Strategy:
        """构造一个只具备 public_dimensions 属性的 Strategy 桩对象。"""
        strategy = Strategy.__new__(Strategy)
        strategy.items = []

        class _FakeItem:
            def __init__(self, dims: list[str]):
                self.public_dimensions = dims

        strategy.items = [_FakeItem(public_dimensions)]
        return strategy

    VALIDATE_PASS_CASES: list[dict[str, Any]] = [
        {
            "id": "minimal_valid",
            "ic_kwargs": {"alert_levels": [1]},
            "public_dims": ["dim_a"],
        },
        {
            "id": "all_levels",
            "ic_kwargs": {"alert_levels": [1, 2, 3]},
            "public_dims": ["dim_a"],
        },
        {
            "id": "with_aggregate_dimensions",
            "ic_kwargs": {"alert_levels": [1], "aggregate_dimensions": ["dim_a"]},
            "public_dims": ["dim_a", "dim_b"],
        },
        {
            "id": "with_conditions",
            "ic_kwargs": {
                "alert_levels": [2],
                "aggregate_dimensions": ["dim_a"],
                "conditions": [{"key": "dim_a", "method": "eq", "value": ["x"]}],
            },
            "public_dims": ["dim_a", "dim_b"],
        },
        {
            "id": "conditions_use_public_dims_when_no_aggregate",
            "ic_kwargs": {
                "alert_levels": [3],
                "conditions": [{"key": "dim_b", "method": "neq", "value": ["y"]}],
            },
            "public_dims": ["dim_a", "dim_b"],
        },
    ]

    @pytest.mark.parametrize("case", VALIDATE_PASS_CASES, ids=lambda c: c["id"])
    def test_validate_pass(self, case: dict[str, Any]) -> None:
        """合法输入 validate 应通过。"""
        ic = IssueConfig(**case["ic_kwargs"])
        strategy = self._make_strategy_stub(case["public_dims"])
        ic.validate(strategy)

    VALIDATE_FAIL_CASES: list[dict[str, Any]] = [
        {
            "id": "empty_alert_levels",
            "ic_kwargs": {"alert_levels": []},
            "public_dims": ["dim_a"],
            "error_fragment": "alert_levels",
        },
        {
            "id": "invalid_alert_level_value",
            "ic_kwargs": {"alert_levels": [4]},
            "public_dims": ["dim_a"],
            "error_fragment": "alert_levels",
        },
        {
            "id": "aggregate_dimension_not_in_public",
            "ic_kwargs": {"alert_levels": [1], "aggregate_dimensions": ["unknown_dim"]},
            "public_dims": ["dim_a"],
            "error_fragment": "aggregate_dimensions",
        },
        {
            "id": "condition_key_not_in_effective_dims",
            "ic_kwargs": {
                "alert_levels": [1],
                "aggregate_dimensions": ["dim_a"],
                "conditions": [{"key": "dim_b", "method": "eq", "value": ["x"]}],
            },
            "public_dims": ["dim_a", "dim_b"],
            "error_fragment": "不在可用维度集合中",
        },
        {
            "id": "condition_invalid_method",
            "ic_kwargs": {
                "alert_levels": [1],
                "conditions": [{"key": "dim_a", "method": "INVALID", "value": ["x"]}],
            },
            "public_dims": ["dim_a"],
            "error_fragment": "不支持的 method",
        },
        {
            "id": "condition_missing_key",
            "ic_kwargs": {
                "alert_levels": [1],
                "conditions": [{"method": "eq", "value": ["x"]}],
            },
            "public_dims": ["dim_a"],
            "error_fragment": "缺少字段",
        },
        {
            "id": "condition_value_none",
            "ic_kwargs": {
                "alert_levels": [1],
                "conditions": [{"key": "dim_a", "method": "eq", "value": None}],
            },
            "public_dims": ["dim_a"],
            "error_fragment": "不能为空",
        },
        {
            "id": "condition_not_dict",
            "ic_kwargs": {
                "alert_levels": [1],
                "conditions": ["not_a_dict"],
            },
            "public_dims": ["dim_a"],
            "error_fragment": "必须为 dict",
        },
    ]

    @pytest.mark.parametrize("case", VALIDATE_FAIL_CASES, ids=lambda c: c["id"])
    def test_validate_fail(self, case: dict[str, Any]) -> None:
        """非法输入 validate 应抛出 DRFValidationError。"""
        ic = IssueConfig(**case["ic_kwargs"])
        strategy = self._make_strategy_stub(case["public_dims"])
        with pytest.raises(DRFValidationError, match=case["error_fragment"]):
            ic.validate(strategy)


# ---------------------------------------------------------------------------
# 3. StrategyIssueConfigModel.clean() 模型级校验
# ---------------------------------------------------------------------------


class TestStrategyIssueConfigModelClean:
    """StrategyIssueConfigModel.clean() 的字段级校验。"""

    def test_clean_valid(self) -> None:
        m = StrategyIssueConfigModel(
            strategy_id=1,
            bk_biz_id=2,
            alert_levels=[1, 2],
            aggregate_dimensions=["dim_a"],
            conditions=[{"key": "dim_a", "method": "eq", "value": ["x"]}],
        )
        m.clean()

    def test_clean_invalid_alert_levels_empty(self) -> None:
        m = StrategyIssueConfigModel(strategy_id=1, bk_biz_id=2, alert_levels=[])
        with pytest.raises(DjangoValidationError, match="alert_levels"):
            m.clean()

    def test_clean_invalid_alert_levels_out_of_range(self) -> None:
        m = StrategyIssueConfigModel(strategy_id=1, bk_biz_id=2, alert_levels=[5])
        with pytest.raises(DjangoValidationError, match="alert_levels"):
            m.clean()

    def test_clean_invalid_condition_missing_key(self) -> None:
        m = StrategyIssueConfigModel(
            strategy_id=1,
            bk_biz_id=2,
            alert_levels=[1],
            conditions=[{"method": "eq", "value": ["x"]}],
        )
        with pytest.raises(DjangoValidationError, match="conditions"):
            m.clean()

    def test_clean_invalid_condition_method(self) -> None:
        m = StrategyIssueConfigModel(
            strategy_id=1,
            bk_biz_id=2,
            alert_levels=[1],
            aggregate_dimensions=["dim_a"],
            conditions=[{"key": "dim_a", "method": "INVALID", "value": ["x"]}],
        )
        with pytest.raises(DjangoValidationError, match="conditions"):
            m.clean()


# ---------------------------------------------------------------------------
# 4. Strategy.Serializer 中 issue_config 字段测试
# ---------------------------------------------------------------------------


class TestStrategySerializerIssueConfig:
    """Strategy.Serializer 对 issue_config 字段的处理。"""

    def test_serializer_accepts_issue_config(self, strategy_json_cases: list[_StrategyJsonCase]) -> None:
        """Serializer 应接受含 issue_config 的策略 JSON。"""
        case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
        data = deepcopy(case.data)
        data["issue_config"] = {
            "is_enabled": True,
            "aggregate_dimensions": [],
            "conditions": [],
            "alert_levels": [1, 2, 3],
        }
        s = Strategy.Serializer(data=data)
        assert s.is_valid(), s.errors
        validated = cast(dict[str, Any], s.validated_data)
        assert "issue_config" in validated
        assert validated["issue_config"]["alert_levels"] == [1, 2, 3]

    def test_serializer_accepts_null_issue_config(self, strategy_json_cases: list[_StrategyJsonCase]) -> None:
        """Serializer 应接受 issue_config=null。"""
        case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
        data = deepcopy(case.data)
        data["issue_config"] = None
        s = Strategy.Serializer(data=data)
        assert s.is_valid(), s.errors
        validated = cast(dict[str, Any], s.validated_data)
        assert validated["issue_config"] is None

    def test_serializer_omit_issue_config(self, strategy_json_cases: list[_StrategyJsonCase]) -> None:
        """Serializer 应允许不传 issue_config（required=False）。"""
        case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
        data = deepcopy(case.data)
        data.pop("issue_config", None)
        s = Strategy.Serializer(data=data)
        assert s.is_valid(), s.errors
        validated = cast(dict[str, Any], s.validated_data)
        assert "issue_config" not in validated


# ---------------------------------------------------------------------------
# 5. Strategy 构造与 to_dict 测试（不依赖 DB）
# ---------------------------------------------------------------------------


class TestStrategyIssueConfigConstruction:
    """Strategy 对象构造和 to_dict 中 issue_config 的行为。"""

    def test_init_with_issue_config(self, strategy_json_cases: list[_StrategyJsonCase]) -> None:
        """Strategy.__init__ 传入 issue_config dict 应构建 IssueConfig 对象。"""
        case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
        data = deepcopy(case.data)
        s = Strategy.Serializer(data=data)
        s.is_valid(raise_exception=True)
        validated = cast(dict[str, Any], s.validated_data)

        validated["issue_config"] = {
            "is_enabled": True,
            "alert_levels": [1, 2],
            "aggregate_dimensions": [],
            "conditions": [],
        }
        strategy = Strategy(**validated)
        assert isinstance(strategy.issue_config, IssueConfig)
        assert strategy.issue_config.alert_levels == [1, 2]

    def test_init_without_issue_config(self, strategy_json_cases: list[_StrategyJsonCase]) -> None:
        """Strategy.__init__ 不传 issue_config 应为 None。"""
        case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
        data = deepcopy(case.data)
        s = Strategy.Serializer(data=data)
        s.is_valid(raise_exception=True)
        validated = cast(dict[str, Any], s.validated_data)
        validated.pop("issue_config", None)
        strategy = Strategy(**validated)
        assert strategy.issue_config is None

    def test_to_dict_with_issue_config(self, strategy_json_cases: list[_StrategyJsonCase]) -> None:
        """to_dict 中 issue_config 应为字典。"""
        case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
        data = deepcopy(case.data)
        s = Strategy.Serializer(data=data)
        s.is_valid(raise_exception=True)
        validated = cast(dict[str, Any], s.validated_data)
        validated["issue_config"] = {"alert_levels": [1], "aggregate_dimensions": [], "conditions": []}
        strategy = Strategy(**validated)
        d = strategy.to_dict()
        assert d["issue_config"] is not None
        assert d["issue_config"]["alert_levels"] == [1]

    def test_to_dict_without_issue_config(self, strategy_json_cases: list[_StrategyJsonCase]) -> None:
        """to_dict 中 issue_config 为 None 时应输出 None。"""
        case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
        data = deepcopy(case.data)
        s = Strategy.Serializer(data=data)
        s.is_valid(raise_exception=True)
        validated = cast(dict[str, Any], s.validated_data)
        validated.pop("issue_config", None)
        strategy = Strategy(**validated)
        d = strategy.to_dict()
        assert d["issue_config"] is None


# ---------------------------------------------------------------------------
# 6. 集成测试：issue_config 随策略 CRUD 的完整生命周期
# ---------------------------------------------------------------------------


@pytest.mark.django_db(databases=["default"])
class TestIssueConfigCRUDIntegration:
    """issue_config 随策略保存/读取/更新/删除的集成测试。"""

    BK_BIZ_ID = 2

    def test_create_strategy_with_issue_config(
        self, mocker: MockerFixture, strategy_json_cases: list[_StrategyJsonCase]
    ) -> None:
        """创建策略时携带 issue_config，应落库到 StrategyIssueConfigModel。"""
        _setup_strategy_third_party_mocks(mocker)

        case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
        data = deepcopy(case.data)
        data["id"] = 0
        data["name"] = f"test_ic_create_{id(data)}"
        data["issue_config"] = {
            "is_enabled": True,
            "aggregate_dimensions": [],
            "conditions": [],
            "alert_levels": [1, 2, 3],
        }

        result = save_strategy(bk_biz_id=self.BK_BIZ_ID, strategy_json=data, operator="pytest")
        strategy_id = result["id"]

        try:
            assert StrategyIssueConfigModel.objects.filter(strategy_id=strategy_id).exists()
            ic_model = StrategyIssueConfigModel.objects.get(strategy_id=strategy_id)
            assert ic_model.bk_biz_id == self.BK_BIZ_ID
            assert ic_model.is_enabled is True
            assert ic_model.alert_levels == [1, 2, 3]

            strategy_dict = get_strategy(bk_biz_id=self.BK_BIZ_ID, strategy_id=strategy_id, apply_converters=False)
            assert strategy_dict["issue_config"] is not None
            assert strategy_dict["issue_config"]["alert_levels"] == [1, 2, 3]
        finally:
            delete_strategy(bk_biz_id=self.BK_BIZ_ID, strategy_id=strategy_id, operator="pytest")

    def test_create_strategy_without_issue_config(
        self, mocker: MockerFixture, strategy_json_cases: list[_StrategyJsonCase]
    ) -> None:
        """创建策略不带 issue_config，StrategyIssueConfigModel 不应有记录。"""
        _setup_strategy_third_party_mocks(mocker)

        case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
        data = deepcopy(case.data)
        data["id"] = 0
        data["name"] = f"test_ic_none_{id(data)}"
        data.pop("issue_config", None)

        result = save_strategy(bk_biz_id=self.BK_BIZ_ID, strategy_json=data, operator="pytest")
        strategy_id = result["id"]

        try:
            assert not StrategyIssueConfigModel.objects.filter(strategy_id=strategy_id).exists()

            strategy_dict = get_strategy(bk_biz_id=self.BK_BIZ_ID, strategy_id=strategy_id, apply_converters=False)
            assert strategy_dict["issue_config"] is None
        finally:
            delete_strategy(bk_biz_id=self.BK_BIZ_ID, strategy_id=strategy_id, operator="pytest")

    def test_update_strategy_add_issue_config(
        self, mocker: MockerFixture, strategy_json_cases: list[_StrategyJsonCase]
    ) -> None:
        """更新策略时新增 issue_config。"""
        _setup_strategy_third_party_mocks(mocker)

        case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
        data = deepcopy(case.data)
        data["id"] = 0
        data["name"] = f"test_ic_add_{id(data)}"
        data.pop("issue_config", None)

        result = save_strategy(bk_biz_id=self.BK_BIZ_ID, strategy_json=data, operator="pytest")
        strategy_id = result["id"]

        try:
            assert not StrategyIssueConfigModel.objects.filter(strategy_id=strategy_id).exists()

            data["id"] = strategy_id
            data["issue_config"] = {
                "is_enabled": True,
                "aggregate_dimensions": [],
                "conditions": [],
                "alert_levels": [2],
            }
            save_strategy(bk_biz_id=self.BK_BIZ_ID, strategy_json=data, operator="pytest")

            assert StrategyIssueConfigModel.objects.filter(strategy_id=strategy_id).exists()
            ic_model = StrategyIssueConfigModel.objects.get(strategy_id=strategy_id)
            assert ic_model.alert_levels == [2]
        finally:
            delete_strategy(bk_biz_id=self.BK_BIZ_ID, strategy_id=strategy_id, operator="pytest")

    def test_update_strategy_modify_issue_config(
        self, mocker: MockerFixture, strategy_json_cases: list[_StrategyJsonCase]
    ) -> None:
        """更新策略时修改 issue_config。"""
        _setup_strategy_third_party_mocks(mocker)

        case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
        data = deepcopy(case.data)
        data["id"] = 0
        data["name"] = f"test_ic_modify_{id(data)}"
        data["issue_config"] = {
            "is_enabled": True,
            "aggregate_dimensions": [],
            "conditions": [],
            "alert_levels": [1],
        }

        result = save_strategy(bk_biz_id=self.BK_BIZ_ID, strategy_json=data, operator="pytest")
        strategy_id = result["id"]

        try:
            data["id"] = strategy_id
            data["issue_config"]["alert_levels"] = [1, 2, 3]
            save_strategy(bk_biz_id=self.BK_BIZ_ID, strategy_json=data, operator="pytest")

            ic_model = StrategyIssueConfigModel.objects.get(strategy_id=strategy_id)
            assert ic_model.alert_levels == [1, 2, 3]
        finally:
            delete_strategy(bk_biz_id=self.BK_BIZ_ID, strategy_id=strategy_id, operator="pytest")

    def test_delete_strategy_soft_deletes_issue_config(
        self, mocker: MockerFixture, strategy_json_cases: list[_StrategyJsonCase]
    ) -> None:
        """删除策略时应软删除 StrategyIssueConfigModel 记录（is_deleted=True）。"""
        _setup_strategy_third_party_mocks(mocker)

        case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
        data = deepcopy(case.data)
        data["id"] = 0
        data["name"] = f"test_ic_delete_{id(data)}"
        data["issue_config"] = {
            "is_enabled": True,
            "aggregate_dimensions": [],
            "conditions": [],
            "alert_levels": [1, 2],
        }

        result = save_strategy(bk_biz_id=self.BK_BIZ_ID, strategy_json=data, operator="pytest")
        strategy_id = result["id"]
        assert StrategyIssueConfigModel.objects.filter(strategy_id=strategy_id, is_deleted=False).exists()

        delete_strategy(bk_biz_id=self.BK_BIZ_ID, strategy_id=strategy_id, operator="pytest")
        ic_model = StrategyIssueConfigModel.objects.get(strategy_id=strategy_id)
        assert ic_model.is_deleted is True
        assert ic_model.is_enabled is False

    def test_update_strategy_without_issue_config_preserves_existing(
        self, mocker: MockerFixture, strategy_json_cases: list[_StrategyJsonCase]
    ) -> None:
        """更新策略时不传 issue_config（字段缺失），已有 issue_config 不应被删除。

        这是 P1 修复的核心场景：字段缺失 != 显式 null，不应触发 save_issue_config。
        """
        _setup_strategy_third_party_mocks(mocker)

        case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
        data = deepcopy(case.data)
        data["id"] = 0
        data["name"] = f"test_ic_preserve_{id(data)}"
        data["issue_config"] = {
            "is_enabled": True,
            "aggregate_dimensions": [],
            "conditions": [],
            "alert_levels": [1, 2, 3],
        }

        result = save_strategy(bk_biz_id=self.BK_BIZ_ID, strategy_json=data, operator="pytest")
        strategy_id = result["id"]

        try:
            assert StrategyIssueConfigModel.objects.filter(strategy_id=strategy_id).exists()

            update_data = deepcopy(case.data)
            update_data["id"] = strategy_id
            update_data["name"] = f"test_ic_preserve_updated_{id(update_data)}"
            update_data.pop("issue_config", None)

            save_strategy(bk_biz_id=self.BK_BIZ_ID, strategy_json=update_data, operator="pytest")

            assert StrategyIssueConfigModel.objects.filter(strategy_id=strategy_id).exists()
            ic_model = StrategyIssueConfigModel.objects.get(strategy_id=strategy_id)
            assert ic_model.alert_levels == [1, 2, 3]
        finally:
            delete_strategy(bk_biz_id=self.BK_BIZ_ID, strategy_id=strategy_id, operator="pytest")

    def test_update_strategy_with_null_issue_config_soft_deletes_existing(
        self, mocker: MockerFixture, strategy_json_cases: list[_StrategyJsonCase]
    ) -> None:
        """更新策略时显式传 issue_config=null，应软删除已有 issue_config。"""
        _setup_strategy_third_party_mocks(mocker)

        case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
        data = deepcopy(case.data)
        data["id"] = 0
        data["name"] = f"test_ic_null_delete_{id(data)}"
        data["issue_config"] = {
            "is_enabled": True,
            "aggregate_dimensions": [],
            "conditions": [],
            "alert_levels": [1],
        }

        result = save_strategy(bk_biz_id=self.BK_BIZ_ID, strategy_json=data, operator="pytest")
        strategy_id = result["id"]

        try:
            assert StrategyIssueConfigModel.objects.filter(strategy_id=strategy_id, is_deleted=False).exists()

            update_data = deepcopy(case.data)
            update_data["id"] = strategy_id
            update_data["name"] = f"test_ic_null_delete_updated_{id(update_data)}"
            update_data["issue_config"] = None

            save_strategy(bk_biz_id=self.BK_BIZ_ID, strategy_json=update_data, operator="pytest")

            ic_model = StrategyIssueConfigModel.objects.get(strategy_id=strategy_id)
            assert ic_model.is_deleted is True
            assert ic_model.is_enabled is False

            strategy_dict = get_strategy(bk_biz_id=self.BK_BIZ_ID, strategy_id=strategy_id, apply_converters=False)
            assert strategy_dict["issue_config"] is None
        finally:
            if StrategyModel.objects.filter(id=strategy_id).exists():
                delete_strategy(bk_biz_id=self.BK_BIZ_ID, strategy_id=strategy_id, operator="pytest")

    def test_soft_deleted_issue_config_can_be_restored(
        self, mocker: MockerFixture, strategy_json_cases: list[_StrategyJsonCase]
    ) -> None:
        """软删除后重新添加 issue_config，应恢复记录（is_deleted=False）。"""
        _setup_strategy_third_party_mocks(mocker)

        case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
        data = deepcopy(case.data)
        data["id"] = 0
        data["name"] = f"test_ic_restore_{id(data)}"
        data["issue_config"] = {
            "is_enabled": True,
            "aggregate_dimensions": [],
            "conditions": [],
            "alert_levels": [1],
        }

        result = save_strategy(bk_biz_id=self.BK_BIZ_ID, strategy_json=data, operator="pytest")
        strategy_id = result["id"]

        try:
            data["id"] = strategy_id
            data["issue_config"] = None
            save_strategy(bk_biz_id=self.BK_BIZ_ID, strategy_json=data, operator="pytest")

            ic_model = StrategyIssueConfigModel.objects.get(strategy_id=strategy_id)
            assert ic_model.is_deleted is True

            data["issue_config"] = {
                "is_enabled": True,
                "aggregate_dimensions": [],
                "conditions": [],
                "alert_levels": [2, 3],
            }
            save_strategy(bk_biz_id=self.BK_BIZ_ID, strategy_json=data, operator="pytest")

            ic_model.refresh_from_db()
            assert ic_model.is_deleted is False
            assert ic_model.is_enabled is True
            assert ic_model.alert_levels == [2, 3]

            strategy_dict = get_strategy(bk_biz_id=self.BK_BIZ_ID, strategy_id=strategy_id, apply_converters=False)
            assert strategy_dict["issue_config"] is not None
            assert strategy_dict["issue_config"]["alert_levels"] == [2, 3]
        finally:
            delete_strategy(bk_biz_id=self.BK_BIZ_ID, strategy_id=strategy_id, operator="pytest")

    def test_get_strategy_returns_issue_config(
        self, mocker: MockerFixture, strategy_json_cases: list[_StrategyJsonCase]
    ) -> None:
        """get_strategy 返回的 dict 中应包含 issue_config。"""
        _setup_strategy_third_party_mocks(mocker)

        case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
        data = deepcopy(case.data)
        data["id"] = 0
        data["name"] = f"test_ic_get_{id(data)}"
        data["issue_config"] = {
            "is_enabled": False,
            "aggregate_dimensions": [],
            "conditions": [],
            "alert_levels": [3],
        }

        result = save_strategy(bk_biz_id=self.BK_BIZ_ID, strategy_json=data, operator="pytest")
        strategy_id = result["id"]

        try:
            strategy_dict = get_strategy(bk_biz_id=self.BK_BIZ_ID, strategy_id=strategy_id, apply_converters=False)
            ic = strategy_dict["issue_config"]
            assert ic is not None
            assert ic["is_enabled"] is False
            assert ic["alert_levels"] == [3]
            assert ic["aggregate_dimensions"] == []
            assert ic["conditions"] == []
        finally:
            delete_strategy(bk_biz_id=self.BK_BIZ_ID, strategy_id=strategy_id, operator="pytest")


# ---------------------------------------------------------------------------
# 7. 表不存在兼容性测试（mock 模拟）
# ---------------------------------------------------------------------------


class TestIssueConfigTableNotExistCompat:
    """表不存在兼容性：仅读取侧（from_models）静默降级，写入/删除侧正常抛异常。"""

    def test_delete_propagates_exception(self, mocker: MockerFixture) -> None:
        """IssueConfig.delete 在数据库异常时应正常抛出，不吞异常。"""
        mocker.patch.object(
            StrategyIssueConfigModel.objects,
            "filter",
            side_effect=OperationalError("connection refused"),
        )
        with pytest.raises(OperationalError):
            IssueConfig.delete(strategy_id=999)

    def test_delete_by_strategy_ids_propagates_exception(self, mocker: MockerFixture) -> None:
        """IssueConfig.delete_by_strategy_ids 在数据库异常时应正常抛出，不吞异常。"""
        mocker.patch.object(
            StrategyIssueConfigModel.objects,
            "filter",
            side_effect=ProgrammingError("relation does not exist"),
        )
        with pytest.raises(ProgrammingError):
            IssueConfig.delete_by_strategy_ids([1, 2, 3])

    def test_from_models_tolerates_programming_error(self, mocker: MockerFixture) -> None:
        """Strategy.from_models 中查询 issue_config 表不存在（ProgrammingError）时，issue_config 应为 None。"""
        strategy_model = StrategyModel(
            id=1,
            bk_biz_id=2,
            name="test",
            scenario="os",
            type="monitor",
            source="monitor",
        )
        strategy_model.pk = 1

        mocker.patch.object(
            StrategyIssueConfigModel.objects,
            "filter",
            side_effect=ProgrammingError("relation does not exist"),
        )

        strategies = Strategy.from_models([strategy_model])
        assert len(strategies) == 1
        assert strategies[0].issue_config is None

    def test_from_models_tolerates_operational_error(self, mocker: MockerFixture) -> None:
        """Strategy.from_models 中查询 issue_config 表不存在（OperationalError）时，issue_config 应为 None。"""
        strategy_model = StrategyModel(
            id=1,
            bk_biz_id=2,
            name="test",
            scenario="os",
            type="monitor",
            source="monitor",
        )
        strategy_model.pk = 1

        mocker.patch.object(
            StrategyIssueConfigModel.objects,
            "filter",
            side_effect=OperationalError("no such table"),
        )

        strategies = Strategy.from_models([strategy_model])
        assert len(strategies) == 1
        assert strategies[0].issue_config is None

    def test_from_models_does_not_swallow_other_db_exceptions(self, mocker: MockerFixture) -> None:
        """Strategy.from_models 中非"表不存在"的数据库异常应正常抛出。"""
        strategy_model = StrategyModel(
            id=1,
            bk_biz_id=2,
            name="test",
            scenario="os",
            type="monitor",
            source="monitor",
        )
        strategy_model.pk = 1

        mocker.patch.object(
            StrategyIssueConfigModel.objects,
            "filter",
            side_effect=OperationalError("connection refused"),
        )

        with pytest.raises(OperationalError, match="connection refused"):
            Strategy.from_models([strategy_model])

    def test_strategy_delete_tolerates_table_not_exist(self, mocker: MockerFixture) -> None:
        """Strategy.delete 中 issue_config 表不存在时应静默降级。"""
        strategy = Strategy.__new__(Strategy)
        strategy._id = 999
        strategy.bk_biz_id = 2

        mocker.patch.object(StrategyModel.objects, "filter", return_value=StrategyModel.objects.none())
        for model_cls in (StrategyModel,):
            mocker.patch.object(model_cls.objects, "filter", return_value=model_cls.objects.none())

        mocker.patch.object(IssueConfig, "delete", side_effect=ProgrammingError("relation does not exist"))
        strategy.delete()

    def test_strategy_delete_raises_on_other_db_error(self, mocker: MockerFixture) -> None:
        """Strategy.delete 中非"表不存在"的数据库异常应正常抛出。"""
        strategy = Strategy.__new__(Strategy)
        strategy._id = 999
        strategy.bk_biz_id = 2

        mocker.patch.object(IssueConfig, "delete", side_effect=OperationalError("connection refused"))

        with pytest.raises(OperationalError, match="connection refused"):
            strategy.delete()

    def test_strategy_delete_by_ids_tolerates_table_not_exist(self, mocker: MockerFixture) -> None:
        """Strategy.delete_by_strategy_ids 中 issue_config 表不存在时应静默降级。"""
        mocker.patch.object(
            IssueConfig, "delete_by_strategy_ids", side_effect=OperationalError("no such table: strategy_issue_config")
        )
        Strategy.delete_by_strategy_ids([1, 2], operator="test")

    def test_strategy_delete_by_ids_raises_on_other_db_error(self, mocker: MockerFixture) -> None:
        """Strategy.delete_by_strategy_ids 中非"表不存在"的数据库异常应正常抛出。"""
        mocker.patch.object(
            IssueConfig, "delete_by_strategy_ids", side_effect=ProgrammingError("permission denied")
        )

        with pytest.raises(ProgrammingError, match="permission denied"):
            Strategy.delete_by_strategy_ids([1, 2], operator="test")
