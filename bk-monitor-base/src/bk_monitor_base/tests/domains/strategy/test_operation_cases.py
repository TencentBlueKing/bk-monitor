"""strategy.operation 的用例驱动测试（JSON cases/*.json）。

目标：
- 让你后续只需要添加新的策略 JSON 文件到 cases/ 目录即可被自动拾取
- 对于需要验证真实数据库操作的测试，使用 @pytest.mark.django_db 装饰器
- 第三方 API 调用使用 mock，但 Strategy.save() 等核心数据库操作使用真实数据库
"""

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest
from pytest_mock import MockerFixture

from bk_monitor_base.domains.strategy.errors import StrategyNotExistError
from bk_monitor_base.domains.strategy.models import (
    AlgorithmModel,
    DetectModel,
    ItemModel,
    QueryConfigModel,
    StrategyActionConfigRelation,
    StrategyHistoryModel,
    StrategyLabel,
    StrategyModel,
)
from bk_monitor_base.domains.strategy.operation import (
    delete_strategy,
    get_strategy,
    list_strategy,
    save_strategy,
    update_partial_strategy,
    update_strategy_query_config,
)
from bk_monitor_base.domains.strategy.strategy import Item, Strategy


@dataclass(frozen=True)
class StrategyJsonCase:
    case_id: str
    path: Path
    data: dict[str, Any]


def _load_strategy_cases() -> list[StrategyJsonCase]:
    cases_dir = Path(__file__).resolve().parent / "cases"
    paths = sorted(cases_dir.glob("*.json"))
    cases: list[StrategyJsonCase] = []
    for p in paths:
        case_id = p.stem
        data = json.loads(p.read_text(encoding="utf-8"))
        cases.append(StrategyJsonCase(case_id=case_id, path=p, data=data))
    return cases


@pytest.fixture(scope="session")
def strategy_json_cases() -> list[StrategyJsonCase]:
    return _load_strategy_cases()


@pytest.mark.parametrize("case", _load_strategy_cases(), ids=lambda c: c.case_id)
def test_case_serializer_and_domain_constructor(case: StrategyJsonCase) -> None:
    """每个 JSON 用例至少应满足：serializer 校验通过 & 可构造 Strategy 聚合根。"""
    serializer = Strategy.Serializer(data=case.data)
    serializer.is_valid(raise_exception=True)
    validated = cast(dict[str, Any], serializer.validated_data)

    # 关键：Strategy 构造会进一步触发 QueryConfig 等深层校验（不依赖 DB）
    strategy = Strategy(**validated)
    assert isinstance(strategy, Strategy)


class _FakeQuerySet:
    def __init__(self, *, exists: bool | None = None, update_rows: int | None = None):
        self._exists = exists
        self._update_rows = update_rows
        self.update_kwargs: dict[str, Any] | None = None

    def exists(self) -> bool:
        assert self._exists is not None
        return self._exists

    def update(self, **kwargs: Any) -> int:
        assert self._update_rows is not None
        self.update_kwargs = kwargs
        return self._update_rows


NAMED_OUTPUT_CONFIG = {
    "response_contract": "named_outputs/v1",
    "legacy_output_ref": "C",
    "output_list": [
        {"reference_name": "A", "expression": "a"},
        {"reference_name": "C", "expression": "a"},
    ],
}


def _setup_strategy_third_party_mocks(mocker: MockerFixture) -> None:
    """设置 strategy 模块所需的第三方接口 mock。

    目前 strategy.py 直接使用的第三方接口包括：
    - bkdata_api.auth_projects_data_check / auth_result_table
    - unify_query_api.promql_to_struct / struct_to_promql

    Args:
        mocker: pytest-mock 的 MockerFixture 实例，用于创建 mock 对象
    """
    # bkdata API
    mocker.patch(
        "bk_monitor_base.infras.third_party_api.bkdata.api.auth_projects_data_check",
        return_value=True,
    )
    mocker.patch(
        "bk_monitor_base.infras.third_party_api.bkdata.api.auth_result_table",
        return_value=None,
    )

    # unify_query API（用于 promql 的结构化转换）
    mocker.patch(
        "bk_monitor_base.infras.third_party_api.unify_query.api.promql_to_struct",
        return_value={"query_list": []},
    )
    mocker.patch(
        "bk_monitor_base.infras.third_party_api.unify_query.api.struct_to_promql",
        return_value="",
    )


def _assert_auto_priority_group_key(value: str) -> None:
    """断言自动生成的 priority_group_key 格式正确（xxhash64 的 hexdigest）。"""
    assert re.fullmatch(r"[0-9a-f]{16}", value), f"priority_group_key 格式不正确: {value!r}"


@pytest.mark.django_db(databases=["default"])
def test_save_strategy_create_no_exists_check(
    mocker: MockerFixture, strategy_json_cases: list[StrategyJsonCase]
) -> None:
    """id 缺省/0：创建场景不做 exists 校验，验证数据真实写入数据库。

    注意：此测试主要验证 id=0 时的创建流程，完整的 CRUD 流程请参考 test_strategy_crud_full_integration。
    """
    # 设置第三方 API mock
    _setup_strategy_third_party_mocks(mocker)

    case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
    data = deepcopy(case.data)
    data["id"] = 0
    # 使用唯一的策略名称避免冲突
    data["name"] = f"test_create_strategy_{id(data)}"

    # create 场景不应触发 StrategyModel.objects.filter(...).exists()
    # 注意：由于 id=0，operation 层不会调用 exists 检查

    result = save_strategy(bk_biz_id=2, strategy_json=data, operator="pytest")

    assert isinstance(result, dict)
    assert "id" in result
    strategy_id = result["id"]
    assert strategy_id > 0

    # 验证策略是否真的存在于数据库
    assert StrategyModel.objects.filter(id=strategy_id, bk_biz_id=2).exists()


def test_save_strategy_update_not_found_raises(
    mocker: MockerFixture, strategy_json_cases: list[StrategyJsonCase]
) -> None:
    """id>0：如果策略不存在，operation 层直接报错，不进入 Strategy.save。"""
    case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
    data = deepcopy(case.data)
    assert int(data.get("id", 0)) > 0

    def _fake_filter(*args: Any, **kwargs: Any) -> _FakeQuerySet:  # noqa: ARG001
        return _FakeQuerySet(exists=False)

    mocker.patch("bk_monitor_base.domains.strategy.operation.StrategyModel.objects.filter", side_effect=_fake_filter)
    mock_save = mocker.patch("bk_monitor_base.domains.strategy.operation.Strategy.save", return_value=None)

    with pytest.raises(StrategyNotExistError):
        save_strategy(bk_biz_id=2, strategy_json=data, operator="pytest")

    mock_save.assert_not_called()


def test_delete_strategy_not_found_raises(mocker: MockerFixture) -> None:
    def _fake_filter(*args: Any, **kwargs: Any) -> _FakeQuerySet:  # noqa: ARG001
        return _FakeQuerySet(exists=False)

    mocker.patch("bk_monitor_base.domains.strategy.operation.StrategyModel.objects.filter", side_effect=_fake_filter)
    mock_delete = mocker.patch("bk_monitor_base.domains.strategy.operation.Strategy.delete_by_strategy_ids")

    with pytest.raises(StrategyNotExistError):
        delete_strategy(bk_biz_id=2, strategy_id=216, operator="pytest")

    mock_delete.assert_not_called()


def test_get_strategy_not_found_raises(mocker: MockerFixture) -> None:
    mocker.patch(
        "bk_monitor_base.domains.strategy.operation.StrategyModel.objects.get",
        side_effect=StrategyModel.DoesNotExist,
    )

    with pytest.raises(StrategyNotExistError):
        get_strategy(bk_biz_id=2, strategy_id=216, apply_converters=False)


@pytest.mark.django_db(databases=["default"])
def test_list_strategy_filter_id_eq(mocker: MockerFixture, strategy_json_cases: list[StrategyJsonCase]) -> None:
    """list_strategy：测试按 id 精确匹配过滤。"""
    # 设置第三方 API mock
    _setup_strategy_third_party_mocks(mocker)

    # 创建测试策略
    case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
    data = deepcopy(case.data)
    data["id"] = 0
    data["name"] = f"test_list_id_eq_{id(data)}"

    create_result = save_strategy(bk_biz_id=2, strategy_json=data, operator="pytest")
    strategy_id = create_result["id"]
    assert strategy_id > 0

    # 测试按 id 过滤
    result = list_strategy(bk_biz_id=2, conditions=[{"key": "id", "values": [strategy_id], "operator": "eq"}])
    rows = result["data"]
    assert len(rows) == 1
    assert rows[0]["id"] == strategy_id
    assert rows[0]["bk_biz_id"] == 2
    assert rows[0]["name"] == data["name"]

    # 测试不存在的 id
    result_empty = list_strategy(bk_biz_id=2, conditions=[{"key": "id", "values": [99999], "operator": "eq"}])
    assert len(result_empty["data"]) == 0


@pytest.mark.parametrize(
    ("meta", "expected_config"),
    [
        ({"owner": "monitor", "query_output_config": NAMED_OUTPUT_CONFIG}, NAMED_OUTPUT_CONFIG),
        ([], None),
        ([{"legacy": True}], None),
        ({"query_output_config": []}, None),
        ({"query_output_config": "named_outputs/v1"}, None),
        ({"owner": "monitor"}, None),
    ],
    ids=[
        "named_output_config",
        "legacy_empty_list",
        "legacy_non_empty_list",
        "nested_empty_list",
        "nested_string",
        "unrelated_meta",
    ],
)
@pytest.mark.django_db(databases=["default"])
def test_list_strategy_restores_query_output_config_from_item_meta(
    meta: Any, expected_config: dict[str, Any] | None
) -> None:
    """策略列表应恢复命名输出配置，同时兼容历史空列表和无关元数据。"""
    strategy_model = StrategyModel.objects.create(
        bk_biz_id=2,
        name=f"test_named_output_meta_{id(meta)}",
        scenario="os",
        type=StrategyModel.StrategyType.Monitor,
    )
    ItemModel.objects.create(
        strategy_id=strategy_model.id,
        name="AVG(CPU使用率)",
        expression="a",
        functions=[],
        origin_sql="",
        no_data_config={"is_enabled": False},
        target=[[]],
        meta=deepcopy(meta),
        metric_type="time_series",
    )

    result = list_strategy(
        bk_biz_id=2,
        apply_converters=False,
        conditions=[{"key": "id", "values": [strategy_model.id], "operator": "eq"}],
    )

    item_config = result["data"][0]["items"][0]
    if expected_config is None:
        assert "query_output_config" not in item_config
    else:
        assert item_config["query_output_config"] == expected_config


@pytest.mark.django_db(databases=["default"])
def test_restored_query_output_config_is_not_written_when_item_is_recreated() -> None:
    """从模型恢复的命名输出配置是只读信息，Item 重建时不应写入普通模型字段。"""
    strategy_model = StrategyModel.objects.create(
        bk_biz_id=2,
        name="test_recreate_named_output_item",
        scenario="os",
        type=StrategyModel.StrategyType.Monitor,
    )
    item_model = ItemModel.objects.create(
        strategy_id=strategy_model.id,
        name="AVG(CPU使用率)",
        expression="a",
        functions=[],
        origin_sql="",
        no_data_config={"is_enabled": False},
        target=[[]],
        meta={"query_output_config": deepcopy(NAMED_OUTPUT_CONFIG)},
        metric_type="time_series",
    )
    record = Item.from_models([item_model], {item_model.id: []}, {item_model.id: []})[0]

    item_model.delete()
    record.save()

    recreated_item = ItemModel.objects.get(id=record.id)
    assert recreated_item.meta == []
    assert record.to_dict()["query_output_config"] == NAMED_OUTPUT_CONFIG


@pytest.mark.django_db(databases=["default"])
def test_list_strategy_filter_id_in(mocker: MockerFixture, strategy_json_cases: list[StrategyJsonCase]) -> None:
    """list_strategy：测试按 id 列表（IN）过滤。"""
    # 设置第三方 API mock
    _setup_strategy_third_party_mocks(mocker)

    # 创建多个测试策略
    case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
    strategy_ids = []
    for i in range(3):
        data = deepcopy(case.data)
        data["id"] = 0
        data["name"] = f"test_list_id_in_{i}_{id(data)}"

        create_result = save_strategy(bk_biz_id=2, strategy_json=data, operator="pytest")
        strategy_ids.append(create_result["id"])

    # 测试按 id 列表过滤
    result = list_strategy(bk_biz_id=2, conditions=[{"key": "id", "values": strategy_ids, "operator": "eq"}])
    assert len(result["data"]) == 3
    returned_ids = {row["id"] for row in result["data"]}
    assert returned_ids == set(strategy_ids)

    # 测试部分 id
    result_partial = list_strategy(
        bk_biz_id=2, conditions=[{"key": "id", "values": strategy_ids[:2], "operator": "eq"}]
    )
    assert len(result_partial["data"]) == 2


@pytest.mark.django_db(databases=["default"])
def test_list_strategy_filter_name_or_default(
    mocker: MockerFixture, strategy_json_cases: list[StrategyJsonCase]
) -> None:
    """list_strategy：测试按 name 模糊匹配过滤（默认 OR 操作符）。"""
    # 设置第三方 API mock
    _setup_strategy_third_party_mocks(mocker)

    # 创建测试策略
    case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")

    # 创建包含 "cpu" 的策略
    data1 = deepcopy(case.data)
    data1["id"] = 0
    data1["name"] = f"test_cpu_strategy_{id(data1)}"
    create_result1 = save_strategy(bk_biz_id=2, strategy_json=data1, operator="pytest")
    strategy_id1 = create_result1["id"]

    # 创建包含 "mem" 的策略
    data2 = deepcopy(case.data)
    data2["id"] = 0
    data2["name"] = f"test_mem_strategy_{id(data2)}"
    create_result2 = save_strategy(bk_biz_id=2, strategy_json=data2, operator="pytest")
    strategy_id2 = create_result2["id"]

    # 创建不匹配的策略
    data3 = deepcopy(case.data)
    data3["id"] = 0
    data3["name"] = f"test_disk_strategy_{id(data3)}"
    create_result3 = save_strategy(bk_biz_id=2, strategy_json=data3, operator="pytest")
    strategy_id3 = create_result3["id"]

    # 测试默认 OR 操作符：应该匹配包含 "cpu" 或 "mem" 的策略
    result = list_strategy(
        bk_biz_id=2,
        conditions=[{"key": "name", "values": ["cpu", "mem"], "operator": "icontains"}],
    )
    returned_ids = {row["id"] for row in result["data"]}
    assert strategy_id1 in returned_ids
    assert strategy_id2 in returned_ids
    assert strategy_id3 not in returned_ids


@pytest.mark.django_db(databases=["default"])
def test_list_strategy_filter_name_and(mocker: MockerFixture, strategy_json_cases: list[StrategyJsonCase]) -> None:
    """list_strategy：测试按 name 模糊匹配过滤（AND 操作符）。"""
    # 设置第三方 API mock
    _setup_strategy_third_party_mocks(mocker)

    # 创建测试策略
    case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")

    # 创建同时包含 "cpu" 和 "usage" 的策略
    data1 = deepcopy(case.data)
    data1["id"] = 0
    data1["name"] = f"test_cpu_usage_strategy_{id(data1)}"
    create_result1 = save_strategy(bk_biz_id=2, strategy_json=data1, operator="pytest")
    strategy_id1 = create_result1["id"]

    # 创建只包含 "cpu" 的策略
    data2 = deepcopy(case.data)
    data2["id"] = 0
    data2["name"] = f"test_cpu_strategy_{id(data2)}"
    create_result2 = save_strategy(bk_biz_id=2, strategy_json=data2, operator="pytest")
    strategy_id2 = create_result2["id"]

    # 创建只包含 "usage" 的策略
    data3 = deepcopy(case.data)
    data3["id"] = 0
    data3["name"] = f"test_usage_strategy_{id(data3)}"
    create_result3 = save_strategy(bk_biz_id=2, strategy_json=data3, operator="pytest")
    strategy_id3 = create_result3["id"]

    # 测试 AND 操作符：应该只匹配同时包含 "cpu" 和 "usage" 的策略
    result = list_strategy(
        bk_biz_id=2,
        # QueryEngine 多值 icontains 默认为 OR；要表达 AND，需要拆成两条顶层条件
        conditions=[
            {"key": "name", "values": ["cpu"], "operator": "icontains"},
            {"key": "name", "values": ["usage"], "operator": "icontains"},
        ],
    )
    returned_ids = {row["id"] for row in result["data"]}
    assert strategy_id1 in returned_ids
    assert strategy_id2 not in returned_ids
    assert strategy_id3 not in returned_ids


@pytest.mark.django_db(databases=["default"])
def test_list_strategy_with_query_engine_conditions(
    mocker: MockerFixture, strategy_json_cases: list[StrategyJsonCase]
) -> None:
    """list_strategy：当传入 conditions 时，应使用 StrategyQueryEngine 做过滤。

    这里使用 `result_table_id__startswith` 这种旧 filters 不支持的条件，验证确实走了引擎能力。
    """
    from bk_monitor_base.domains.strategy.models import QueryConfigModel

    # 设置第三方 API mock
    _setup_strategy_third_party_mocks(mocker)

    # 创建测试策略
    case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
    data = deepcopy(case.data)
    data["id"] = 0
    data["name"] = f"test_list_conditions_{id(data)}"

    create_result = save_strategy(bk_biz_id=2, strategy_json=data, operator="pytest")
    strategy_id = create_result["id"]
    assert strategy_id > 0

    # 从真实 QueryConfig 里取一个 result_table_id，并构造前缀条件
    qc = QueryConfigModel.objects.filter(strategy_id=strategy_id).only("config").first()
    assert qc is not None
    assert isinstance(qc.config, dict)
    result_table_id = str(qc.config.get("result_table_id", ""))
    assert result_table_id
    prefix = result_table_id.split(".", 1)[0] + "."

    result = list_strategy(
        bk_biz_id=2,
        apply_converters=False,
        conditions=[{"key": "result_table_id", "values": [prefix], "operator": "startswith"}],
    )
    returned_ids = {row["id"] for row in result["data"]}
    assert strategy_id in returned_ids


@pytest.mark.django_db(databases=["default"])
def test_list_strategy_filter_app_condition(mocker: MockerFixture, strategy_json_cases: list[StrategyJsonCase]) -> None:
    """list_strategy：测试 conditions 支持按 app 精确过滤。"""
    _setup_strategy_third_party_mocks(mocker)

    case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
    unique_prefix = uuid4().hex[:8]
    created_strategy_ids: dict[str, int] = {}
    app_mapping = {
        "fta": "fta",
        "bk_monitor": "bk_monitor",
        "empty": "",
    }

    for case_key, app in app_mapping.items():
        data = deepcopy(case.data)
        data["id"] = 0
        data["name"] = f"test_list_app_condition_{unique_prefix}_{case_key}"
        create_result = save_strategy(bk_biz_id=2, strategy_json=data, operator="pytest")
        created_strategy_ids[case_key] = create_result["id"]
        StrategyModel.objects.filter(id=create_result["id"]).update(app=app)

    result = list_strategy(
        bk_biz_id=2,
        apply_converters=False,
        conditions=[{"key": "app", "values": ["fta"], "operator": "eq"}],
    )
    returned_ids = {row["id"] for row in result["data"]}

    assert returned_ids == {created_strategy_ids["fta"]}


@pytest.mark.django_db(databases=["default"])
def test_list_strategy_no_filters(mocker: MockerFixture, strategy_json_cases: list[StrategyJsonCase]) -> None:
    """list_strategy：测试无过滤条件时返回所有策略。"""
    # 设置第三方 API mock
    _setup_strategy_third_party_mocks(mocker)

    # 创建多个测试策略
    case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
    strategy_ids = []
    for i in range(3):
        data = deepcopy(case.data)
        data["id"] = 0
        data["name"] = f"test_list_no_filter_{i}_{id(data)}"

        create_result = save_strategy(bk_biz_id=2, strategy_json=data, operator="pytest")
        strategy_ids.append(create_result["id"])

    # 测试无过滤条件
    result = list_strategy(bk_biz_id=2)
    returned_ids = {row["id"] for row in result["data"]}
    # 应该包含所有创建的策略（可能还有其他测试创建的策略，所以至少包含这些）
    assert all(sid in returned_ids for sid in strategy_ids)


@pytest.mark.django_db(databases=["default"])
def test_list_strategy_filter_bk_biz_ids_and_is_enabled(
    mocker: MockerFixture, strategy_json_cases: list[StrategyJsonCase]
) -> None:
    """list_strategy：测试 bk_biz_ids 与 is_enabled 过滤（含组合过滤）。"""
    # Arrange: 准备第三方 API mock 与多组测试策略数据
    _setup_strategy_third_party_mocks(mocker)
    case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
    unique_prefix = uuid4().hex[:8]

    created_strategy_ids: dict[str, int] = {}
    strategy_inputs: list[dict[str, Any]] = [
        {"case_key": "biz2_enabled", "bk_biz_id": 2, "is_enabled": True},
        {"case_key": "biz2_disabled", "bk_biz_id": 2, "is_enabled": False},
        {"case_key": "biz3_enabled", "bk_biz_id": 3, "is_enabled": True},
        {"case_key": "biz4_disabled", "bk_biz_id": 4, "is_enabled": False},
    ]
    for index, item in enumerate(strategy_inputs):
        data = deepcopy(case.data)
        data["id"] = 0
        data["name"] = f"test_list_biz_enabled_{unique_prefix}_{index}"
        data["is_enabled"] = item["is_enabled"]
        create_result = save_strategy(
            bk_biz_id=item["bk_biz_id"],
            strategy_json=data,
            operator="pytest",
        )
        created_strategy_ids[item["case_key"]] = create_result["id"]

    test_cases: list[dict[str, Any]] = [
        {
            "name": "仅按 bk_biz_ids 过滤",
            "kwargs": {"bk_biz_ids": [2, 3]},
            "expected_case_keys": {"biz2_enabled", "biz2_disabled", "biz3_enabled"},
        },
        {
            "name": "仅按 is_enabled=True 过滤",
            "kwargs": {"is_enabled": True},
            "expected_case_keys": {"biz2_enabled", "biz3_enabled"},
        },
        {
            "name": "仅按 is_enabled=False 过滤",
            "kwargs": {"is_enabled": False},
            "expected_case_keys": {"biz2_disabled", "biz4_disabled"},
        },
        {
            "name": "按 bk_biz_ids + is_enabled=True 组合过滤",
            "kwargs": {"bk_biz_ids": [2, 3], "is_enabled": True},
            "expected_case_keys": {"biz2_enabled", "biz3_enabled"},
        },
        {
            "name": "按 bk_biz_ids + is_enabled=False 组合过滤",
            "kwargs": {"bk_biz_ids": [2, 3], "is_enabled": False},
            "expected_case_keys": {"biz2_disabled"},
        },
    ]

    # Act + Assert: 表格驱动验证每个过滤场景
    for test_case in test_cases:
        result = list_strategy(apply_converters=False, **test_case["kwargs"])
        returned_ids = {row["id"] for row in result["data"]}
        expected_ids = {created_strategy_ids[case_key] for case_key in test_case["expected_case_keys"]}
        assert returned_ids == expected_ids, f"{test_case['name']} 结果不符合预期"


@pytest.mark.django_db(databases=["default"])
def test_strategy_crud_full_integration(mocker: MockerFixture, strategy_json_cases: list[StrategyJsonCase]) -> None:
    """完整的 CRUD 集成测试：创建 -> 获取 -> 更新 -> 获取 -> 删除。

    验证整个策略生命周期的真实数据库操作：
    1. 创建策略（save_strategy with id=0）
    2. 获取策略（get_strategy）
    3. 更新策略（save_strategy with id>0）
    4. 再次获取策略（get_strategy）验证更新
    5. 删除策略（delete_strategy）
    6. 验证策略已被删除
    """
    # 设置第三方 API mock
    _setup_strategy_third_party_mocks(mocker)

    case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
    data = deepcopy(case.data)
    data["id"] = 0  # 创建场景
    # 使用唯一的策略名称避免冲突
    create_name = f"test_crud_create_{id(data)}"
    data["name"] = create_name

    # 步骤 1: 创建策略
    create_result = save_strategy(bk_biz_id=2, strategy_json=data, operator="pytest")
    assert isinstance(create_result, dict)
    assert "id" in create_result
    strategy_id = create_result["id"]
    assert strategy_id > 0

    # 验证策略已创建
    assert StrategyModel.objects.filter(id=strategy_id, bk_biz_id=2).exists()

    # 步骤 2: 获取策略
    strategy_dict_1 = get_strategy(bk_biz_id=2, strategy_id=strategy_id, apply_converters=False)
    assert strategy_dict_1["id"] == strategy_id
    assert strategy_dict_1["bk_biz_id"] == 2
    assert strategy_dict_1["name"] == create_name

    # 步骤 3: 更新策略
    updated_name = f"test_crud_updated_{id(data)}"
    data["id"] = strategy_id
    data["name"] = updated_name

    update_result = save_strategy(bk_biz_id=2, strategy_json=data, operator="pytest")
    assert isinstance(update_result, dict)
    assert update_result["id"] == strategy_id

    # 步骤 4: 再次获取策略，验证更新
    strategy_dict_2 = get_strategy(bk_biz_id=2, strategy_id=strategy_id, apply_converters=False)
    assert strategy_dict_2["id"] == strategy_id
    assert strategy_dict_2["name"] == updated_name
    assert strategy_dict_2["name"] != create_name

    # 验证两次获取的数据一致（除了 name）
    assert strategy_dict_2["bk_biz_id"] == strategy_dict_1["bk_biz_id"]
    assert strategy_dict_2["scenario"] == strategy_dict_1["scenario"]

    # 步骤 5: 删除策略
    delete_strategy(bk_biz_id=2, strategy_id=strategy_id, operator="pytest")

    # 步骤 6: 验证策略已被删除
    assert not StrategyModel.objects.filter(id=strategy_id, bk_biz_id=2).exists()

    # 验证再次获取会抛出异常
    with pytest.raises(StrategyNotExistError):
        get_strategy(bk_biz_id=2, strategy_id=strategy_id, apply_converters=False)

    # 验证再次删除也会抛出异常
    with pytest.raises(StrategyNotExistError):
        delete_strategy(bk_biz_id=2, strategy_id=strategy_id, operator="pytest")


@pytest.mark.django_db(databases=["default"])
def test_save_strategy_with_priority_auto_generate_group_key(
    mocker: MockerFixture, strategy_json_cases: list[StrategyJsonCase]
) -> None:
    """创建策略时设置 priority，验证 priority_group_key 自动生成并落库。"""
    _setup_strategy_third_party_mocks(mocker)

    case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
    data = deepcopy(case.data)
    data["id"] = 0
    data["name"] = f"test_priority_auto_{id(data)}"
    data["priority"] = 10
    data.pop("priority_group_key", None)

    result = save_strategy(bk_biz_id=2, strategy_json=data, operator="pytest")
    strategy_id = int(result["id"])
    model = StrategyModel.objects.get(id=strategy_id, bk_biz_id=2)
    assert model.priority == 10
    assert isinstance(model.priority_group_key, str)
    _assert_auto_priority_group_key(model.priority_group_key)

    strategy_dict = get_strategy(bk_biz_id=2, strategy_id=strategy_id, apply_converters=False)
    assert strategy_dict["priority"] == 10
    assert strategy_dict["priority_group_key"] == model.priority_group_key


@pytest.mark.django_db(databases=["default"])
def test_save_strategy_with_priority_and_custom_group_key(
    mocker: MockerFixture, strategy_json_cases: list[StrategyJsonCase]
) -> None:
    """创建策略时设置 priority + 自定义 PGK: 前缀的 priority_group_key，应按用户指定保存。"""
    _setup_strategy_third_party_mocks(mocker)

    case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
    data = deepcopy(case.data)
    data["id"] = 0
    data["name"] = f"test_priority_custom_{id(data)}"
    data["priority"] = 20
    custom_key = f"PGK:test_{id(data)}"
    data["priority_group_key"] = custom_key

    result = save_strategy(bk_biz_id=2, strategy_json=data, operator="pytest")
    strategy_id = int(result["id"])
    model = StrategyModel.objects.get(id=strategy_id, bk_biz_id=2)
    assert model.priority == 20
    assert model.priority_group_key == custom_key

    strategy_dict = get_strategy(bk_biz_id=2, strategy_id=strategy_id, apply_converters=False)
    assert strategy_dict["priority"] == 20
    assert strategy_dict["priority_group_key"] == custom_key


@pytest.mark.django_db(databases=["default"])
def test_save_strategy_without_priority(mocker: MockerFixture, strategy_json_cases: list[StrategyJsonCase]) -> None:
    """创建策略不设置 priority，应保存 priority=None 且 priority_group_key 为空字符串。"""
    _setup_strategy_third_party_mocks(mocker)

    case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
    data = deepcopy(case.data)
    data["id"] = 0
    data["name"] = f"test_priority_none_{id(data)}"
    data["priority"] = None
    data.pop("priority_group_key", None)

    result = save_strategy(bk_biz_id=2, strategy_json=data, operator="pytest")
    strategy_id = int(result["id"])
    model = StrategyModel.objects.get(id=strategy_id, bk_biz_id=2)
    assert model.priority is None
    assert (model.priority_group_key or "") == ""

    strategy_dict = get_strategy(bk_biz_id=2, strategy_id=strategy_id, apply_converters=False)
    assert strategy_dict["priority"] is None
    assert strategy_dict["priority_group_key"] == ""


@pytest.mark.django_db(databases=["default"])
def test_save_strategy_update_priority(mocker: MockerFixture, strategy_json_cases: list[StrategyJsonCase]) -> None:
    """更新策略修改 priority：从 None -> 有值，验证 group_key 自动生成并落库。"""
    _setup_strategy_third_party_mocks(mocker)

    case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
    create_data = deepcopy(case.data)
    create_data["id"] = 0
    create_data["name"] = f"test_priority_update_create_{id(create_data)}"
    create_data["priority"] = None

    create_result = save_strategy(bk_biz_id=2, strategy_json=create_data, operator="pytest")
    strategy_id = int(create_result["id"])
    model = StrategyModel.objects.get(id=strategy_id, bk_biz_id=2)
    assert model.priority is None
    assert (model.priority_group_key or "") == ""

    update_data = deepcopy(create_data)
    update_data["id"] = strategy_id
    update_data["name"] = f"test_priority_update_updated_{id(update_data)}"
    update_data["priority"] = 30
    update_data.pop("priority_group_key", None)

    update_result = save_strategy(bk_biz_id=2, strategy_json=update_data, operator="pytest")
    assert int(update_result["id"]) == strategy_id

    updated_model = StrategyModel.objects.get(id=strategy_id, bk_biz_id=2)
    assert updated_model.priority == 30
    assert isinstance(updated_model.priority_group_key, str)
    _assert_auto_priority_group_key(updated_model.priority_group_key)


@pytest.mark.django_db(databases=["default"])
def test_save_strategy_update_priority_group_key(
    mocker: MockerFixture, strategy_json_cases: list[StrategyJsonCase]
) -> None:
    """更新策略修改 priority_group_key 为 PGK: 前缀自定义值，应覆盖原自动 group_key。"""
    _setup_strategy_third_party_mocks(mocker)

    case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
    create_data = deepcopy(case.data)
    create_data["id"] = 0
    create_data["name"] = f"test_priority_group_key_create_{id(create_data)}"
    create_data["priority"] = 40

    create_result = save_strategy(bk_biz_id=2, strategy_json=create_data, operator="pytest")
    strategy_id = int(create_result["id"])
    model = StrategyModel.objects.get(id=strategy_id, bk_biz_id=2)
    assert model.priority == 40
    _assert_auto_priority_group_key(cast(str, model.priority_group_key))
    old_key = cast(str, model.priority_group_key)

    update_data = deepcopy(create_data)
    update_data["id"] = strategy_id
    update_data["name"] = f"test_priority_group_key_update_{id(update_data)}"
    update_data["priority"] = 40
    custom_key = f"PGK:override_{id(update_data)}"
    update_data["priority_group_key"] = custom_key

    update_result = save_strategy(bk_biz_id=2, strategy_json=update_data, operator="pytest")
    assert int(update_result["id"]) == strategy_id

    updated_model = StrategyModel.objects.get(id=strategy_id, bk_biz_id=2)
    assert updated_model.priority == 40
    assert updated_model.priority_group_key == custom_key
    assert updated_model.priority_group_key != old_key


@pytest.mark.django_db(databases=["default"])
def test_save_strategy_update_priority_to_none(
    mocker: MockerFixture, strategy_json_cases: list[StrategyJsonCase]
) -> None:
    """更新策略将 priority 从有值改为 None，应清空 priority_group_key。"""
    _setup_strategy_third_party_mocks(mocker)

    case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
    create_data = deepcopy(case.data)
    create_data["id"] = 0
    create_data["name"] = f"test_priority_to_none_create_{id(create_data)}"
    create_data["priority"] = 50

    create_result = save_strategy(bk_biz_id=2, strategy_json=create_data, operator="pytest")
    strategy_id = int(create_result["id"])
    model = StrategyModel.objects.get(id=strategy_id, bk_biz_id=2)
    assert model.priority == 50
    _assert_auto_priority_group_key(cast(str, model.priority_group_key))

    update_data = deepcopy(create_data)
    update_data["id"] = strategy_id
    update_data["name"] = f"test_priority_to_none_update_{id(update_data)}"
    update_data["priority"] = None
    update_data["priority_group_key"] = f"PGK:should_be_cleared_{id(update_data)}"

    update_result = save_strategy(bk_biz_id=2, strategy_json=update_data, operator="pytest")
    assert int(update_result["id"]) == strategy_id

    updated_model = StrategyModel.objects.get(id=strategy_id, bk_biz_id=2)
    assert updated_model.priority is None
    assert (updated_model.priority_group_key or "") == ""


@pytest.mark.django_db(databases=["default"])
def test_save_strategy_priority_group_key_validation(
    mocker: MockerFixture, strategy_json_cases: list[StrategyJsonCase]
) -> None:
    """priority_group_key 非 PGK: 前缀应被清空，并触发自动生成。"""
    _setup_strategy_third_party_mocks(mocker)

    case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
    data = deepcopy(case.data)
    data["id"] = 0
    data["name"] = f"test_priority_group_key_validation_{id(data)}"
    data["priority"] = 60
    invalid_key = f"INVALID_{id(data)}"
    data["priority_group_key"] = invalid_key

    result = save_strategy(bk_biz_id=2, strategy_json=data, operator="pytest")
    strategy_id = int(result["id"])
    model = StrategyModel.objects.get(id=strategy_id, bk_biz_id=2)
    assert model.priority == 60
    assert isinstance(model.priority_group_key, str)
    _assert_auto_priority_group_key(model.priority_group_key)
    assert model.priority_group_key != invalid_key
    assert not model.priority_group_key.startswith("PGK:")


@pytest.mark.django_db(databases=["default"])
def test_strategy_priority_in_crud_flow(mocker: MockerFixture, strategy_json_cases: list[StrategyJsonCase]) -> None:
    """在 CRUD 流程中验证 priority/priority_group_key：创建->获取->更新->获取->删除。"""
    _setup_strategy_third_party_mocks(mocker)

    case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
    data = deepcopy(case.data)
    data["id"] = 0
    data["name"] = f"test_priority_crud_create_{id(data)}"
    data["priority"] = 70
    data.pop("priority_group_key", None)

    create_result = save_strategy(bk_biz_id=2, strategy_json=data, operator="pytest")
    strategy_id = int(create_result["id"])
    model = StrategyModel.objects.get(id=strategy_id, bk_biz_id=2)
    assert model.priority == 70
    _assert_auto_priority_group_key(cast(str, model.priority_group_key))
    group_key_1 = cast(str, model.priority_group_key)

    got_1 = get_strategy(bk_biz_id=2, strategy_id=strategy_id, apply_converters=False)
    assert got_1["priority"] == 70
    assert got_1["priority_group_key"] == group_key_1

    update_data = deepcopy(data)
    update_data["id"] = strategy_id
    update_data["name"] = f"test_priority_crud_update_{id(update_data)}"
    update_data["priority"] = 80
    update_data.pop("priority_group_key", None)

    update_result = save_strategy(bk_biz_id=2, strategy_json=update_data, operator="pytest")
    assert int(update_result["id"]) == strategy_id

    model_after = StrategyModel.objects.get(id=strategy_id, bk_biz_id=2)
    assert model_after.priority == 80
    # group_key 的生成不依赖 priority 数值，items 不变时应保持稳定
    assert cast(str, model_after.priority_group_key) == group_key_1

    got_2 = get_strategy(bk_biz_id=2, strategy_id=strategy_id, apply_converters=False)
    assert got_2["priority"] == 80
    assert got_2["priority_group_key"] == group_key_1

    delete_strategy(bk_biz_id=2, strategy_id=strategy_id, operator="pytest")
    assert not StrategyModel.objects.filter(id=strategy_id, bk_biz_id=2).exists()


@pytest.mark.django_db(databases=["default"])
def test_save_strategy_with_aiops_access_func_called(
    mocker: MockerFixture, strategy_json_cases: list[StrategyJsonCase]
) -> None:
    """测试当策略包含 AIOPS 算法时，aiops_access_func 会被调用。

    验证：
    1. 当策略包含 AIOPS 算法（如 IntelligentDetect）时，aiops_access_func 会被调用
    2. aiops_access_func 被调用时传入的参数是策略 ID
    3. 返回的任务 ID 会被保存到查询配置的 intelligent_detect.task_id 中
    """
    # 设置第三方 API mock
    _setup_strategy_third_party_mocks(mocker)

    # Mock bkbase 配置为启用状态
    mock_config = mocker.MagicMock()
    mock_config.blueking.bkbase.enabled = True
    mocker.patch("bk_monitor_base.domains.strategy.strategy.get_config", return_value=mock_config)

    # 创建包含 AIOPS 算法的策略数据
    case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
    data = deepcopy(case.data)
    data["id"] = 0
    data["name"] = f"test_aiops_strategy_{id(data)}"

    # 修改算法为 IntelligentDetect（AIOPS 算法）
    if data["items"] and data["items"][0].get("algorithms"):
        data["items"][0]["algorithms"][0]["type"] = "IntelligentDetect"
        data["items"][0]["algorithms"][0]["config"] = {
            "args": {"sensitivity": 5},
            "plan_id": 1,
            "visual_type": "none",
        }

    # 确保查询配置满足 AIOPS 接入条件
    if data["items"] and data["items"][0].get("query_configs"):
        query_config = data["items"][0]["query_configs"][0]
        query_config["data_source_label"] = "bk_monitor"
        query_config["data_type_label"] = "time_series"
        query_config["result_table_id"] = "test.result_table"

    # 创建 mock 的 aiops_access_func
    mock_task_id = f"task_{id(data)}"
    aiops_access_func_called = False
    aiops_access_func_strategy_id = None

    def aiops_access_func(strategy_id: int) -> str:
        nonlocal aiops_access_func_called, aiops_access_func_strategy_id
        aiops_access_func_called = True
        aiops_access_func_strategy_id = strategy_id
        return mock_task_id

    # 保存策略
    result = save_strategy(bk_biz_id=2, strategy_json=data, operator="pytest", aiops_access_func=aiops_access_func)

    assert isinstance(result, dict)
    assert "id" in result
    strategy_id = result["id"]
    assert strategy_id > 0

    # 验证 aiops_access_func 被调用
    assert aiops_access_func_called, "aiops_access_func 应该被调用"
    assert aiops_access_func_strategy_id == strategy_id, f"传入的策略 ID 应该是 {strategy_id}"

    # 验证任务 ID 被保存到查询配置中
    strategy_dict = get_strategy(bk_biz_id=2, strategy_id=strategy_id, apply_converters=False)
    if strategy_dict["items"] and strategy_dict["items"][0].get("query_configs"):
        query_config = strategy_dict["items"][0]["query_configs"][0]
        intelligent_detect = query_config.get("intelligent_detect", {})
        # 如果使用 SDK，则不会调用 aiops_access_func
        if not intelligent_detect.get("use_sdk", False):
            assert intelligent_detect.get("task_id") == mock_task_id, "任务 ID 应该被保存到查询配置中"


@pytest.mark.django_db(databases=["default"])
def test_save_strategy_without_aiops_algorithm_aiops_access_func_not_called(
    mocker: MockerFixture, strategy_json_cases: list[StrategyJsonCase]
) -> None:
    """测试当策略不包含 AIOPS 算法时，aiops_access_func 不会被调用。

    验证：
    1. 当策略不包含 AIOPS 算法时，aiops_access_func 不会被调用
    2. 即使提供了 aiops_access_func 参数，也不会被调用
    """
    # 设置第三方 API mock
    _setup_strategy_third_party_mocks(mocker)

    # Mock bkbase 配置为启用状态
    mock_config = mocker.MagicMock()
    mock_config.blueking.bkbase.enabled = True
    mocker.patch("bk_monitor_base.domains.strategy.strategy.get_config", return_value=mock_config)

    # 创建不包含 AIOPS 算法的策略数据（使用默认的 Threshold 算法）
    case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
    data = deepcopy(case.data)
    data["id"] = 0
    data["name"] = f"test_no_aiops_strategy_{id(data)}"

    # 确保算法是 Threshold（非 AIOPS 算法）
    if data["items"] and data["items"][0].get("algorithms"):
        data["items"][0]["algorithms"][0]["type"] = "Threshold"

    # 创建 mock 的 aiops_access_func
    aiops_access_func_called = False

    def aiops_access_func(strategy_id: int) -> str:
        nonlocal aiops_access_func_called
        aiops_access_func_called = True
        return f"task_{strategy_id}"

    # 保存策略
    result = save_strategy(bk_biz_id=2, strategy_json=data, operator="pytest", aiops_access_func=aiops_access_func)

    assert isinstance(result, dict)
    assert "id" in result
    strategy_id = result["id"]
    assert strategy_id > 0

    # 验证 aiops_access_func 没有被调用
    assert not aiops_access_func_called, "当策略不包含 AIOPS 算法时，aiops_access_func 不应该被调用"


@pytest.mark.django_db(databases=["default"])
def test_save_strategy_aiops_with_bkbase_disabled(
    mocker: MockerFixture, strategy_json_cases: list[StrategyJsonCase]
) -> None:
    """测试当 bkbase 未启用时，即使策略包含 AIOPS 算法，aiops_access_func 也不会被调用。

    验证：
    1. 当 bkbase.enabled = False 时，即使策略包含 AIOPS 算法，aiops_access_func 也不会被调用
    """
    # 设置第三方 API mock
    _setup_strategy_third_party_mocks(mocker)

    # Mock bkbase 配置为禁用状态
    mock_config = mocker.MagicMock()
    mock_config.blueking.bkbase.enabled = False
    mocker.patch("bk_monitor_base.domains.strategy.strategy.get_config", return_value=mock_config)

    # 创建包含 AIOPS 算法的策略数据
    case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
    data = deepcopy(case.data)
    data["id"] = 0
    data["name"] = f"test_aiops_disabled_{id(data)}"

    # 修改算法为 IntelligentDetect（AIOPS 算法）
    if data["items"] and data["items"][0].get("algorithms"):
        data["items"][0]["algorithms"][0]["type"] = "IntelligentDetect"
        data["items"][0]["algorithms"][0]["config"] = {
            "args": {"sensitivity": 5},
            "plan_id": 1,
            "visual_type": "none",
        }

    # 创建 mock 的 aiops_access_func
    aiops_access_func_called = False

    def aiops_access_func(strategy_id: int) -> str:
        nonlocal aiops_access_func_called
        aiops_access_func_called = True
        return f"task_{strategy_id}"

    # 保存策略
    result = save_strategy(bk_biz_id=2, strategy_json=data, operator="pytest", aiops_access_func=aiops_access_func)

    assert isinstance(result, dict)
    assert "id" in result
    strategy_id = result["id"]
    assert strategy_id > 0

    # 验证 aiops_access_func 没有被调用（因为 bkbase 未启用）
    assert not aiops_access_func_called, "当 bkbase 未启用时，aiops_access_func 不应该被调用"


@pytest.mark.django_db(databases=["default"])
def test_save_strategy_aiops_update_scenario(
    mocker: MockerFixture, strategy_json_cases: list[StrategyJsonCase]
) -> None:
    """测试更新策略时，如果包含 AIOPS 算法，aiops_access_func 也会被调用。

    验证：
    1. 更新策略时，如果包含 AIOPS 算法，aiops_access_func 会被调用
    2. 传入的参数是更新后的策略 ID
    """
    # 设置第三方 API mock
    _setup_strategy_third_party_mocks(mocker)

    # Mock bkbase 配置为启用状态
    mock_config = mocker.MagicMock()
    mock_config.blueking.bkbase.enabled = True
    mocker.patch("bk_monitor_base.domains.strategy.strategy.get_config", return_value=mock_config)

    # 先创建一个不包含 AIOPS 算法的策略
    case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
    data = deepcopy(case.data)
    data["id"] = 0
    data["name"] = f"test_aiops_update_{id(data)}"

    create_result = save_strategy(bk_biz_id=2, strategy_json=data, operator="pytest")
    strategy_id = create_result["id"]

    # 更新策略，添加 AIOPS 算法
    data["id"] = strategy_id
    if data["items"] and data["items"][0].get("algorithms"):
        data["items"][0]["algorithms"][0]["type"] = "IntelligentDetect"
        data["items"][0]["algorithms"][0]["config"] = {
            "args": {"sensitivity": 5},
            "plan_id": 1,
            "visual_type": "none",
        }

    # 确保查询配置满足 AIOPS 接入条件
    if data["items"] and data["items"][0].get("query_configs"):
        query_config = data["items"][0]["query_configs"][0]
        query_config["data_source_label"] = "bk_monitor"
        query_config["data_type_label"] = "time_series"
        query_config["result_table_id"] = "test.result_table"

    # 创建 mock 的 aiops_access_func
    mock_task_id = f"task_update_{id(data)}"
    aiops_access_func_called = False
    aiops_access_func_strategy_id = None

    def aiops_access_func(strategy_id: int) -> str:
        nonlocal aiops_access_func_called, aiops_access_func_strategy_id
        aiops_access_func_called = True
        aiops_access_func_strategy_id = strategy_id
        return mock_task_id

    # 更新策略
    update_result = save_strategy(
        bk_biz_id=2, strategy_json=data, operator="pytest", aiops_access_func=aiops_access_func
    )

    assert isinstance(update_result, dict)
    assert update_result["id"] == strategy_id

    # 验证 aiops_access_func 被调用
    assert aiops_access_func_called, "更新策略时，如果包含 AIOPS 算法，aiops_access_func 应该被调用"
    assert aiops_access_func_strategy_id == strategy_id, f"传入的策略 ID 应该是 {strategy_id}"


@pytest.mark.django_db(databases=["default"])
def test_update_strategy_query_config_merge_update_without_history(
    mocker: MockerFixture, strategy_json_cases: list[StrategyJsonCase]
) -> None:
    """验证按策略合并更新 query_config.config，且不新增策略历史。"""
    _setup_strategy_third_party_mocks(mocker)

    case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
    data = deepcopy(case.data)
    data["id"] = 0
    data["name"] = f"test_update_query_config_{id(data)}"

    create_result = save_strategy(bk_biz_id=2, strategy_json=data, operator="pytest")
    strategy_id = int(create_result["id"])
    assert strategy_id > 0

    try:
        before_query_configs = list(QueryConfigModel.objects.filter(strategy_id=strategy_id).order_by("id"))
        assert before_query_configs
        before_config_map = {int(qc.id): deepcopy(qc.config) for qc in before_query_configs}
        before_history_count = StrategyHistoryModel.objects.filter(strategy_id=strategy_id).count()

        result = update_strategy_query_config(
            strategy_id=strategy_id,
            config={"new_flag": "x", "result_table_id": "patched.rt"},
        )
        assert result["strategy_id"] == strategy_id
        assert result["updated_count"] == len(before_query_configs)

        after_query_configs = list(QueryConfigModel.objects.filter(strategy_id=strategy_id).order_by("id"))
        assert len(after_query_configs) == len(before_query_configs)
        for query_config in after_query_configs:
            assert isinstance(query_config.config, dict)
            assert query_config.config.get("new_flag") == "x"
            assert query_config.config.get("result_table_id") == "patched.rt"

            before_config = before_config_map[int(query_config.id)]
            for key, value in before_config.items():
                if key == "result_table_id":
                    continue
                assert key in query_config.config
                assert query_config.config[key] == value

        after_history_count = StrategyHistoryModel.objects.filter(strategy_id=strategy_id).count()
        assert after_history_count == before_history_count
    finally:
        if StrategyModel.objects.filter(id=strategy_id, bk_biz_id=2).exists():
            delete_strategy(bk_biz_id=2, strategy_id=strategy_id, operator="pytest")
        assert not StrategyModel.objects.filter(id=strategy_id, bk_biz_id=2).exists()


@pytest.mark.django_db(databases=["default"])
@pytest.mark.parametrize(
    ("update_kwargs", "expected_alias", "expected_metric_id", "expect_config_change"),
    [
        (
            {"config": None, "alias": "alias_new"},
            "alias_new",
            None,
            False,
        ),
        (
            {"config": None, "metric_id": "patched.metric.id"},
            None,
            "patched.metric.id",
            False,
        ),
        (
            {
                "config": {"new_flag": "x", "result_table_id": "patched.rt"},
                "alias": "alias_new",
                "metric_id": "patched.metric.id",
            },
            "alias_new",
            "patched.metric.id",
            True,
        ),
    ],
    ids=["update_alias_only", "update_metric_id_only", "update_config_alias_metric_id"],
)
def test_update_strategy_query_config_optional_fields_update_without_history(
    mocker: MockerFixture,
    strategy_json_cases: list[StrategyJsonCase],
    update_kwargs: dict[str, Any],
    expected_alias: str | None,
    expected_metric_id: str | None,
    expect_config_change: bool,
) -> None:
    """验证 query_config 可选字段更新能力，并确保策略历史不变。"""
    _setup_strategy_third_party_mocks(mocker)

    case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
    data = deepcopy(case.data)
    data["id"] = 0
    data["name"] = f"test_update_query_config_optional_{id(data)}"

    create_result = save_strategy(bk_biz_id=2, strategy_json=data, operator="pytest")
    strategy_id = int(create_result["id"])
    assert strategy_id > 0

    try:
        before_query_configs = list(QueryConfigModel.objects.filter(strategy_id=strategy_id).order_by("id"))
        assert before_query_configs

        first_query_config = before_query_configs[0]
        QueryConfigModel.objects.create(
            strategy_id=strategy_id,
            item_id=first_query_config.item_id,
            alias=f"{first_query_config.alias}_copy",
            data_source_label=first_query_config.data_source_label,
            data_type_label=first_query_config.data_type_label,
            metric_id=f"{first_query_config.metric_id}_copy",
            config=deepcopy(first_query_config.config),
        )

        before_query_configs = list(QueryConfigModel.objects.filter(strategy_id=strategy_id).order_by("id"))
        assert len(before_query_configs) >= 2

        before_config_map = {
            int(query_config.id): deepcopy(query_config.config) for query_config in before_query_configs
        }
        before_alias_map = {int(query_config.id): query_config.alias for query_config in before_query_configs}
        before_metric_id_map = {int(query_config.id): query_config.metric_id for query_config in before_query_configs}
        before_history_count = StrategyHistoryModel.objects.filter(strategy_id=strategy_id).count()

        result = update_strategy_query_config(strategy_id=strategy_id, **update_kwargs)
        assert result["strategy_id"] == strategy_id
        assert result["updated_count"] == len(before_query_configs)

        after_query_configs = list(QueryConfigModel.objects.filter(strategy_id=strategy_id).order_by("id"))
        assert len(after_query_configs) == len(before_query_configs)
        for query_config in after_query_configs:
            query_config_id = int(query_config.id)
            if expected_alias is None:
                assert query_config.alias == before_alias_map[query_config_id]
            else:
                assert query_config.alias == expected_alias

            if expected_metric_id is None:
                assert query_config.metric_id == before_metric_id_map[query_config_id]
            else:
                assert query_config.metric_id == expected_metric_id

            if expect_config_change:
                assert query_config.config.get("new_flag") == "x"
                assert query_config.config.get("result_table_id") == "patched.rt"
            else:
                assert query_config.config == before_config_map[query_config_id]

        after_history_count = StrategyHistoryModel.objects.filter(strategy_id=strategy_id).count()
        assert after_history_count == before_history_count
    finally:
        if StrategyModel.objects.filter(id=strategy_id, bk_biz_id=2).exists():
            delete_strategy(bk_biz_id=2, strategy_id=strategy_id, operator="pytest")
        assert not StrategyModel.objects.filter(id=strategy_id, bk_biz_id=2).exists()


@pytest.mark.django_db(databases=["default"])
def test_update_strategy_query_config_not_exist_strategy_raises() -> None:
    """策略不存在时应抛出 StrategyNotExistError。"""
    with pytest.raises(StrategyNotExistError):
        update_strategy_query_config(strategy_id=99999999, config={"k": "v"})


@pytest.mark.django_db(databases=["default"])
def test_update_strategy_query_config_empty_config_skip_update(
    mocker: MockerFixture, strategy_json_cases: list[StrategyJsonCase]
) -> None:
    """空 config 时应直接返回，不更新 query_config 且不新增策略历史。"""
    _setup_strategy_third_party_mocks(mocker)

    case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
    data = deepcopy(case.data)
    data["id"] = 0
    data["name"] = f"test_update_query_config_empty_{id(data)}"

    create_result = save_strategy(bk_biz_id=2, strategy_json=data, operator="pytest")
    strategy_id = int(create_result["id"])
    assert strategy_id > 0

    try:
        before_query_configs = list(QueryConfigModel.objects.filter(strategy_id=strategy_id).order_by("id"))
        assert before_query_configs
        before_config_map = {int(qc.id): deepcopy(qc.config) for qc in before_query_configs}
        before_history_count = StrategyHistoryModel.objects.filter(strategy_id=strategy_id).count()

        result = update_strategy_query_config(strategy_id=strategy_id, config={})
        assert result == {"strategy_id": strategy_id, "updated_count": 0}

        after_query_configs = list(QueryConfigModel.objects.filter(strategy_id=strategy_id).order_by("id"))
        assert len(after_query_configs) == len(before_query_configs)
        for query_config in after_query_configs:
            assert query_config.config == before_config_map[int(query_config.id)]

        after_history_count = StrategyHistoryModel.objects.filter(strategy_id=strategy_id).count()
        assert after_history_count == before_history_count
    finally:
        if StrategyModel.objects.filter(id=strategy_id, bk_biz_id=2).exists():
            delete_strategy(bk_biz_id=2, strategy_id=strategy_id, operator="pytest")
        assert not StrategyModel.objects.filter(id=strategy_id, bk_biz_id=2).exists()


@pytest.mark.django_db(databases=["default"])
def test_update_strategy_query_config_all_none_skip_update(
    mocker: MockerFixture, strategy_json_cases: list[StrategyJsonCase]
) -> None:
    """config/alias/metric_id 都不传时应直接返回，不更新 query_config 且不新增策略历史。"""
    _setup_strategy_third_party_mocks(mocker)

    case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
    data = deepcopy(case.data)
    data["id"] = 0
    data["name"] = f"test_update_query_config_all_none_{id(data)}"

    create_result = save_strategy(bk_biz_id=2, strategy_json=data, operator="pytest")
    strategy_id = int(create_result["id"])
    assert strategy_id > 0

    try:
        before_query_configs = list(QueryConfigModel.objects.filter(strategy_id=strategy_id).order_by("id"))
        assert before_query_configs
        before_config_map = {int(qc.id): deepcopy(qc.config) for qc in before_query_configs}
        before_alias_map = {int(qc.id): qc.alias for qc in before_query_configs}
        before_metric_id_map = {int(qc.id): qc.metric_id for qc in before_query_configs}
        before_history_count = StrategyHistoryModel.objects.filter(strategy_id=strategy_id).count()

        result = update_strategy_query_config(strategy_id=strategy_id)
        assert result == {"strategy_id": strategy_id, "updated_count": 0}

        after_query_configs = list(QueryConfigModel.objects.filter(strategy_id=strategy_id).order_by("id"))
        assert len(after_query_configs) == len(before_query_configs)
        for query_config in after_query_configs:
            query_config_id = int(query_config.id)
            assert query_config.config == before_config_map[query_config_id]
            assert query_config.alias == before_alias_map[query_config_id]
            assert query_config.metric_id == before_metric_id_map[query_config_id]

        after_history_count = StrategyHistoryModel.objects.filter(strategy_id=strategy_id).count()
        assert after_history_count == before_history_count
    finally:
        if StrategyModel.objects.filter(id=strategy_id, bk_biz_id=2).exists():
            delete_strategy(bk_biz_id=2, strategy_id=strategy_id, operator="pytest")
        assert not StrategyModel.objects.filter(id=strategy_id, bk_biz_id=2).exists()


@pytest.mark.django_db(databases=["default"])
class TestUpdatePartialStrategy:
    """覆盖 update_partial_strategy 支持的全部字段

    每个测试用例都会创建两条独立策略用于验证
    测试结束后显式删除策略，避免数据残留与并发冲突
    """

    BK_BIZ_ID = 2
    OPERATOR = "pytest"

    @pytest.fixture
    def _strategy_pair(self, mocker: MockerFixture, strategy_json_cases: list[StrategyJsonCase], request):
        """为单个测试用例创建两条独立策略，并在结束后销毁"""
        _setup_strategy_third_party_mocks(mocker)

        case = next(c for c in strategy_json_cases if c.case_id == "cpu_total_usage")
        strategy_ids: list[int] = []
        try:
            for idx in (1, 2):
                data = deepcopy(case.data)
                data["id"] = 0
                random_suffix = uuid4().hex[:8]
                name = f"{request.node.name}-{random_suffix}-{idx}"
                data["name"] = name[:128]
                result = save_strategy(bk_biz_id=self.BK_BIZ_ID, strategy_json=data, operator=self.OPERATOR)
                strategy_ids.append(int(result["id"]))

            yield self.BK_BIZ_ID, strategy_ids
        finally:
            for sid in strategy_ids:
                if StrategyModel.objects.filter(id=sid, bk_biz_id=self.BK_BIZ_ID).exists():
                    delete_strategy(bk_biz_id=self.BK_BIZ_ID, strategy_id=sid, operator=self.OPERATOR)
                assert not StrategyModel.objects.filter(id=sid, bk_biz_id=self.BK_BIZ_ID).exists()

    def test_update_is_enabled(self, _strategy_pair) -> None:
        bk_biz_id, ids = _strategy_pair
        updated = update_partial_strategy(
            bk_biz_id=bk_biz_id,
            ids=ids,
            edit_data={"is_enabled": True},
            operator=self.OPERATOR,
        )
        assert sorted(updated) == sorted(ids)
        assert StrategyModel.objects.filter(id__in=ids, bk_biz_id=bk_biz_id, is_enabled=True).count() == 2
        assert StrategyHistoryModel.objects.filter(strategy_id__in=ids, operate="update").count() >= 2

    def test_update_notice_group_list(self, _strategy_pair) -> None:
        bk_biz_id, ids = _strategy_pair
        update_partial_strategy(
            bk_biz_id=bk_biz_id,
            ids=ids,
            edit_data={"notice_group_list": [101, 102]},
            operator=self.OPERATOR,
        )
        for sid in ids:
            rels = StrategyActionConfigRelation.objects.filter(strategy_id=sid)
            assert rels.exists()
            assert all(rel.user_groups == [101, 102] for rel in rels)

    def test_update_labels_append(self, _strategy_pair) -> None:
        bk_biz_id, ids = _strategy_pair
        update_partial_strategy(
            bk_biz_id=bk_biz_id,
            ids=ids,
            edit_data={"labels": {"labels": ["b"], "append_keys": ["labels"]}},
            operator=self.OPERATOR,
        )
        for sid in ids:
            labels = list(
                StrategyLabel.objects.filter(strategy_id=sid, bk_biz_id=bk_biz_id).values_list("label_name", flat=True)
            )
            assert "/aaa/" in labels
            assert "/b/" in labels

    def test_update_labels_replace(self, _strategy_pair) -> None:
        bk_biz_id, ids = _strategy_pair
        update_partial_strategy(
            bk_biz_id=bk_biz_id,
            ids=ids,
            edit_data={"labels": {"labels": ["c"]}},
            operator=self.OPERATOR,
        )
        for sid in ids:
            labels = list(
                StrategyLabel.objects.filter(strategy_id=sid, bk_biz_id=bk_biz_id).values_list("label_name", flat=True)
            )
            assert labels == ["/c/"]

    def test_update_trigger_config(self, _strategy_pair) -> None:
        bk_biz_id, ids = _strategy_pair
        update_partial_strategy(
            bk_biz_id=bk_biz_id,
            ids=ids,
            edit_data={"trigger_config": {"count": 5}},
            operator=self.OPERATOR,
        )
        detects = list(DetectModel.objects.filter(strategy_id__in=ids))
        assert detects
        for d in detects:
            assert d.trigger_config["count"] == 5
            assert d.trigger_config["check_window"] == 5

    def test_update_recovery_config(self, _strategy_pair) -> None:
        bk_biz_id, ids = _strategy_pair
        update_partial_strategy(
            bk_biz_id=bk_biz_id,
            ids=ids,
            edit_data={"recovery_config": {"check_window": 7, "status_setter": "recovery"}},
            operator=self.OPERATOR,
        )
        detects = list(DetectModel.objects.filter(strategy_id__in=ids))
        assert detects
        for d in detects:
            assert d.recovery_config["check_window"] == 7

    def test_update_alarm_interval(self, _strategy_pair) -> None:
        bk_biz_id, ids = _strategy_pair
        update_partial_strategy(
            bk_biz_id=bk_biz_id,
            ids=ids,
            edit_data={"alarm_interval": 10},
            operator=self.OPERATOR,
        )
        for sid in ids:
            strategy_dict = get_strategy(bk_biz_id=bk_biz_id, strategy_id=sid, apply_converters=False)
            assert strategy_dict["notice"]["config"]["notify_interval"] == 10 * 60

    def test_update_send_recovery_alarm(self, _strategy_pair) -> None:
        bk_biz_id, ids = _strategy_pair
        update_partial_strategy(
            bk_biz_id=bk_biz_id,
            ids=ids,
            edit_data={"send_recovery_alarm": True},
            operator=self.OPERATOR,
        )
        for sid in ids:
            strategy_dict = get_strategy(bk_biz_id=bk_biz_id, strategy_id=sid, apply_converters=False)
            assert "recovered" in strategy_dict["notice"]["signal"]

        update_partial_strategy(
            bk_biz_id=bk_biz_id,
            ids=ids,
            edit_data={"send_recovery_alarm": False},
            operator=self.OPERATOR,
        )
        for sid in ids:
            strategy_dict = get_strategy(bk_biz_id=bk_biz_id, strategy_id=sid, apply_converters=False)
            assert "recovered" not in strategy_dict["notice"]["signal"]

    def test_update_message_template(self, _strategy_pair) -> None:
        bk_biz_id, ids = _strategy_pair
        update_partial_strategy(
            bk_biz_id=bk_biz_id,
            ids=ids,
            edit_data={"message_template": "hello"},
            operator=self.OPERATOR,
        )
        for sid in ids:
            strategy_dict = get_strategy(bk_biz_id=bk_biz_id, strategy_id=sid, apply_converters=False)
            templates = strategy_dict["notice"]["config"]["template"]
            assert templates
            assert all(t["message_tmpl"] == "hello" for t in templates)

    def test_update_no_data_config(self, _strategy_pair) -> None:
        bk_biz_id, ids = _strategy_pair
        update_partial_strategy(
            bk_biz_id=bk_biz_id,
            ids=ids,
            edit_data={"no_data_config": {"continuous": 9, "extra": {"a": 1}}},
            operator=self.OPERATOR,
        )
        items = list(ItemModel.objects.filter(strategy_id__in=ids))
        assert items
        for item in items:
            assert item.no_data_config["continuous"] == 9
            assert item.no_data_config["extra"]["a"] == 1

    def test_update_notice_append_keys(self, _strategy_pair) -> None:
        bk_biz_id, ids = _strategy_pair
        before = get_strategy(bk_biz_id=bk_biz_id, strategy_id=ids[0], apply_converters=False)
        old_groups = before["notice"]["user_groups"]

        update_partial_strategy(
            bk_biz_id=bk_biz_id,
            ids=ids,
            edit_data={"notice": {"append_keys": ["user_groups"], "user_groups": [999]}},
            operator=self.OPERATOR,
        )
        for sid in ids:
            after = get_strategy(bk_biz_id=bk_biz_id, strategy_id=sid, apply_converters=False)
            new_groups = after["notice"]["user_groups"]
            assert 999 in new_groups
            for g in old_groups:
                assert g in new_groups
            assert after["actions"][0]["user_groups"] == new_groups

    def test_update_target(self, _strategy_pair) -> None:
        bk_biz_id, ids = _strategy_pair
        target = [
            [
                {
                    "field": "ip",
                    "method": "eq",
                    "value": [{"ip": "127.0.0.1", "bk_cloud_id": 0}],
                }
            ]
        ]
        update_partial_strategy(bk_biz_id=bk_biz_id, ids=ids, edit_data={"target": target}, operator=self.OPERATOR)
        for sid in ids:
            items = list(ItemModel.objects.filter(strategy_id=sid))
            assert items
            assert items[0].target == target

        update_partial_strategy(bk_biz_id=bk_biz_id, ids=ids, edit_data={"target": []}, operator=self.OPERATOR)
        for sid in ids:
            items = list(ItemModel.objects.filter(strategy_id=sid))
            assert items[0].target == []

    def test_update_actions(self, _strategy_pair) -> None:
        bk_biz_id, ids = _strategy_pair
        before = get_strategy(bk_biz_id=bk_biz_id, strategy_id=ids[0], apply_converters=False)
        action = deepcopy(before["actions"][0])
        action.setdefault("options", {})
        action["options"]["skip_delay"] = 5

        update_partial_strategy(bk_biz_id=bk_biz_id, ids=ids, edit_data={"actions": [action]}, operator=self.OPERATOR)
        for sid in ids:
            rel = StrategyActionConfigRelation.objects.get(
                strategy_id=sid, relate_type=StrategyActionConfigRelation.RelateType.ACTION
            )
            assert rel.options.get("skip_delay") == 5

    def test_update_algorithms(self, _strategy_pair) -> None:
        bk_biz_id, ids = _strategy_pair
        before = get_strategy(bk_biz_id=bk_biz_id, strategy_id=ids[0], apply_converters=False)
        algorithms = deepcopy(before["items"][0]["algorithms"])
        # Threshold 算法配置：调整阈值
        for group in algorithms[0]["config"]:
            for cond in group:
                cond["threshold"] = 90

        update_partial_strategy(
            bk_biz_id=bk_biz_id,
            ids=ids,
            edit_data={"algorithms": algorithms},
            operator=self.OPERATOR,
        )
        algos = list(AlgorithmModel.objects.filter(strategy_id__in=ids))
        assert algos
        for algo in algos:
            assert algo.config[0][0]["threshold"] == 90
