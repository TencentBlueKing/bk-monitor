"""strategy 域 CRUD 单元测试框架（表驱动）。

设计目标：
- 用例表驱动：用户后续只需要补齐 test_case 参数与 validator 断言逻辑
- validator 必须存在，且签名统一：
    validator(test_case: dict, result: Any, mockers: dict[str, Any]) -> None
- 第三方接口统一 mock：集中在 setup_strategy_mocks() 内
- 用例隔离：同一测试函数内不同 test_case 之间 mock 互不影响（每次用例执行后 stopall）
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, TypedDict

import pytest
from pytest_mock import MockerFixture

from bk_monitor_base.domains.strategy.models import (
    ActionConfig,
    AlgorithmModel,
    DetectModel,
    ItemModel,
    QueryConfigModel,
    StrategyActionConfigRelation,
    StrategyLabel,
    StrategyModel,
)
from bk_monitor_base.domains.strategy.strategy import Strategy

# 类型别名：Strategy 构造参数的数据字典类型
StrategyDataDict = dict[str, Any]

# 类型别名：Mock 对象字典类型
MockersDict = dict[str, Any]

# 类型别名：验证器函数类型
# 参数：
#   - test_case: 测试用例字典
#   - result: 操作结果，类型取决于测试场景：
#       * Create/Update/ReadById: Strategy | Exception
#       * ReadFromModels: list[Strategy] | Exception
#       * DeleteSingle: int | Exception
#       * DeleteBatch: list[int] | Exception
#   - mockers: Mock 对象字典
Validator = Callable[[dict[str, Any], Any, MockersDict], None]


class BaseTestCase(TypedDict, total=False):
    """所有 test_case 的最小约束。

    Attributes:
        name: 测试用例名称，用于日志和错误信息
        expected_exception: 期望抛出的异常类型（单个类型或元组），如果提供则验证结果是否为该异常
        validator: 验证器函数，用于验证测试结果是否符合预期
    """

    name: str
    expected_exception: type[Exception] | tuple[type[Exception], ...]
    validator: Validator


class CreateTestCase(BaseTestCase, total=False):
    """创建策略测试用例类型。

    Attributes:
        strategy_data: Strategy 构造参数字典，必须包含 bk_biz_id、name、scenario 等必需字段
        rollback: 是否回滚操作，默认 False
        operator: 操作人标识，默认空字符串
        aiops_access_func: 智能检测接入函数，输入策略ID返回异步任务ID，可选
    """

    strategy_data: StrategyDataDict
    rollback: bool
    operator: str
    aiops_access_func: Callable[[int], str] | None


class UpdateTestCase(BaseTestCase, total=False):
    """更新策略测试用例类型。

    Attributes:
        update_data: Strategy 构造参数字典，必须包含 id（>0）以及需要更新的字段
        rollback: 是否回滚操作，默认 False
        operator: 操作人标识，默认空字符串
        aiops_access_func: 智能检测接入函数，输入策略ID返回异步任务ID，可选
    """

    update_data: StrategyDataDict
    rollback: bool
    operator: str
    aiops_access_func: Callable[[int], str] | None


class ReadFromModelsTestCase(BaseTestCase, total=False):
    """从模型列表读取策略测试用例类型。

    Attributes:
        strategies: StrategyModel 实例列表，用于 Strategy.from_models() 方法
    """

    strategies: list[StrategyModel]


class ReadByIdTestCase(BaseTestCase, total=False):
    """按 ID 读取策略测试用例类型。

    Attributes:
        strategy_id: 策略 ID（整数或可转换为整数的字符串）
        bk_biz_id: 业务 ID（整数或可转换为整数的字符串）
    """

    strategy_id: int | str
    bk_biz_id: int | str


class DeleteSingleTestCase(BaseTestCase, total=False):
    """删除单个策略测试用例类型。

    Attributes:
        strategy_data: Strategy 构造参数字典，用于创建待删除的策略
        operator: 操作人标识，默认空字符串
    """

    strategy_data: StrategyDataDict
    operator: str


class DeleteBatchTestCase(BaseTestCase, total=False):
    """批量删除策略测试用例类型。

    Attributes:
        strategies_data: Strategy 构造参数字典列表，用于创建待删除的策略列表
        operator: 操作人标识，默认空字符串
    """

    strategies_data: list[StrategyDataDict]
    operator: str


def _ensure_validator(test_case: BaseTestCase) -> Validator:
    """确保 validator 存在并返回。

    Args:
        test_case: 测试用例字典，必须包含 validator 字段

    Returns:
        Validator: 验证器函数

    Raises:
        AssertionError: 如果 test_case 中不存在 validator 或 validator 为 None
    """
    if "validator" not in test_case or test_case["validator"] is None:
        raise AssertionError("每个 test_case 必须提供 validator(test_case, result, mockers)")
    return test_case["validator"]


def setup_strategy_mocks(mocker: MockerFixture) -> MockersDict:
    """统一设置 strategy 模块所需的第三方接口 mock。

    目前 strategy.py 直接使用的第三方接口包括：
    - bkdata_api.auth_projects_data_check / auth_result_table
    - unify_query_api.promql_to_struct / struct_to_promql

    Args:
        mocker: pytest-mock 的 MockerFixture 实例，用于创建 mock 对象

    Returns:
        MockersDict: Mock 对象字典，键为"稳定的逻辑名"，值为 patch 返回的 Mock 对象
    """

    mockers: MockersDict = {}

    # bkdata API
    mockers["bkdata_api.auth_projects_data_check"] = mocker.patch(
        "bk_monitor_base.infras.third_party_api.bkdata.api.auth_projects_data_check",
        return_value=True,
    )
    mockers["bkdata_api.auth_result_table"] = mocker.patch(
        "bk_monitor_base.infras.third_party_api.bkdata.api.auth_result_table",
        return_value=None,
    )

    # unify_query API（用于 promql 的结构化转换）
    mockers["unify_query_api.promql_to_struct"] = mocker.patch(
        "bk_monitor_base.infras.third_party_api.unify_query.api.promql_to_struct",
        return_value={"query_list": []},
    )
    mockers["unify_query_api.struct_to_promql"] = mocker.patch(
        "bk_monitor_base.infras.third_party_api.unify_query.api.struct_to_promql",
        return_value="",
    )

    return mockers


@contextmanager
def isolated_strategy_mocks(mocker: MockerFixture) -> Iterator[MockersDict]:
    """为单个 test_case 构造隔离的 mockers，并在用例结束后清理所有 patch。

    Args:
        mocker: pytest-mock 的 MockerFixture 实例

    Yields:
        MockersDict: Mock 对象字典，在用例执行期间可用

    Note:
        用例级隔离：避免同一测试函数内多个用例互相污染，用例结束后自动调用 stopall()
    """
    mockers = setup_strategy_mocks(mocker)
    try:
        yield mockers
    finally:
        # 用例级隔离：避免同一测试函数内多个用例互相污染
        mocker.stopall()


# ---------------------------
# 用例表（暂不填充测试数据）
# ---------------------------

CREATE_TEST_CASES: list[CreateTestCase] = []
READ_FROM_MODELS_TEST_CASES: list[ReadFromModelsTestCase] = []
READ_BY_ID_TEST_CASES: list[ReadByIdTestCase] = []
UPDATE_TEST_CASES: list[UpdateTestCase] = []
DELETE_SINGLE_TEST_CASES: list[DeleteSingleTestCase] = []
DELETE_BATCH_TEST_CASES: list[DeleteBatchTestCase] = []


@pytest.mark.django_db(databases=["default"])
class TestCreateStrategy:
    """测试 Strategy.save() 创建（id=0）。"""

    def test_create_strategy_table_driven(self, mocker: MockerFixture) -> None:
        """表驱动：创建策略。

        Args:
            mocker: pytest-mock 的 MockerFixture 实例，用于创建 mock 对象
        """
        for test_case in CREATE_TEST_CASES:
            validator = _ensure_validator(test_case)
            with isolated_strategy_mocks(mocker) as mockers:
                result: Strategy | Exception
                strategy: Strategy | None = None
                try:
                    strategy_data: StrategyDataDict = test_case["strategy_data"]
                    strategy = Strategy(**strategy_data)
                    strategy.save(
                        rollback=bool(test_case.get("rollback", False)),
                        operator=str(test_case.get("operator", "")),
                        aiops_access_func=test_case.get("aiops_access_func"),
                    )
                    result = strategy
                except Exception as e:  # noqa: BLE001 - 测试框架需要捕获并交给 validator
                    result = e

                # 期望异常断言（可选）
                expected_exc = test_case.get("expected_exception")
                if expected_exc is not None:
                    assert isinstance(result, expected_exc), f"期望异常 {expected_exc}，实际：{result!r}"
                else:
                    if isinstance(result, Exception):
                        raise result

                validator(test_case, result, mockers)

                # 清理：若创建成功且用户未在 validator 内自行清理，则这里兜底删除
                if isinstance(result, Strategy) and getattr(result, "id", 0):
                    result.delete()


@pytest.mark.django_db(databases=["default"])
class TestReadStrategy:
    """测试 Strategy.from_models() 与按 ID 读取。"""

    def test_read_from_models_table_driven(self, mocker: MockerFixture) -> None:
        """表驱动：from_models。

        Args:
            mocker: pytest-mock 的 MockerFixture 实例，用于创建 mock 对象
        """
        for test_case in READ_FROM_MODELS_TEST_CASES:
            validator = _ensure_validator(test_case)
            with isolated_strategy_mocks(mocker) as mockers:
                result: list[Strategy] | Exception
                try:
                    strategies: list[StrategyModel] = test_case["strategies"]
                    result = Strategy.from_models(strategies)
                except Exception as e:  # noqa: BLE001
                    result = e

                expected_exc = test_case.get("expected_exception")
                if expected_exc is not None:
                    assert isinstance(result, expected_exc), f"期望异常 {expected_exc}，实际：{result!r}"
                else:
                    if isinstance(result, Exception):
                        raise result

                validator(test_case, result, mockers)

    def test_from_models_large_batch_uses_scoped_related_queries(self, mocker: MockerFixture) -> None:
        """大批量策略转换时，关联模型必须限定在本次策略 ID 范围内查询。

        Args:
            mocker: pytest-mock 的 MockerFixture 实例，用于拦截全表查询。
        """
        unique_prefix = f"test_from_models_large_batch_{id(self)}"
        StrategyModel.objects.bulk_create(
            [
                StrategyModel(
                    bk_biz_id=2,
                    name=f"{unique_prefix}_{index}",
                    scenario="os",
                    type=StrategyModel.StrategyType.Monitor,
                )
                for index in range(501)
            ]
        )
        strategy_models = list(StrategyModel.objects.filter(name__startswith=unique_prefix).order_by("id"))
        assert len(strategy_models) == 501

        for model in (
            ItemModel,
            DetectModel,
            AlgorithmModel,
            QueryConfigModel,
            StrategyLabel,
            StrategyActionConfigRelation,
            ActionConfig,
        ):
            mocker.patch.object(
                model.objects,
                "all",
                side_effect=AssertionError(f"{model.__name__}.objects.all() should not be used for large batches"),
            )

        result = Strategy.from_models(strategy_models)

        assert len(result) == len(strategy_models)
        assert {strategy.id for strategy in result} == {strategy_model.id for strategy_model in strategy_models}

    def test_read_by_id_table_driven(self, mocker: MockerFixture) -> None:
        """表驱动：按 ID 查询并转换为 Strategy。

        Args:
            mocker: pytest-mock 的 MockerFixture 实例，用于创建 mock 对象
        """
        for test_case in READ_BY_ID_TEST_CASES:
            validator = _ensure_validator(test_case)
            with isolated_strategy_mocks(mocker) as mockers:
                result: Strategy | Exception
                try:
                    strategy_id: int = int(test_case["strategy_id"])
                    bk_biz_id: int = int(test_case["bk_biz_id"])
                    model: StrategyModel = StrategyModel.objects.get(id=strategy_id, bk_biz_id=bk_biz_id)
                    result = Strategy.from_models([model])[0]
                except Exception as e:  # noqa: BLE001
                    result = e

                expected_exc = test_case.get("expected_exception")
                if expected_exc is not None:
                    assert isinstance(result, expected_exc), f"期望异常 {expected_exc}，实际：{result!r}"
                else:
                    if isinstance(result, Exception):
                        raise result

                validator(test_case, result, mockers)


@pytest.mark.django_db(databases=["default"])
class TestUpdateStrategy:
    """测试 Strategy.save() 更新（id>0）。"""

    def test_update_strategy_table_driven(self, mocker: MockerFixture) -> None:
        """表驱动：更新策略。

        Args:
            mocker: pytest-mock 的 MockerFixture 实例，用于创建 mock 对象

        Note:
            用户负责在 update_data 中提供完整可保存的 Strategy 构造参数（包含 id）
        """
        for test_case in UPDATE_TEST_CASES:
            validator = _ensure_validator(test_case)
            with isolated_strategy_mocks(mocker) as mockers:
                result: Strategy | Exception
                try:
                    # 用户负责在 update_data 中提供完整可保存的 Strategy 构造参数（包含 id）
                    update_data: StrategyDataDict = test_case["update_data"]
                    strategy = Strategy(**update_data)
                    strategy.save(
                        rollback=bool(test_case.get("rollback", False)),
                        operator=str(test_case.get("operator", "")),
                        aiops_access_func=test_case.get("aiops_access_func"),
                    )
                    result = strategy
                except Exception as e:  # noqa: BLE001
                    result = e

                expected_exc = test_case.get("expected_exception")
                if expected_exc is not None:
                    assert isinstance(result, expected_exc), f"期望异常 {expected_exc}，实际：{result!r}"
                else:
                    if isinstance(result, Exception):
                        raise result

                validator(test_case, result, mockers)


@pytest.mark.django_db(databases=["default"])
class TestDeleteStrategy:
    """测试 Strategy.delete() 删除单个策略（实例方法）。"""

    def test_delete_strategy_table_driven(self, mocker: MockerFixture) -> None:
        """表驱动：删除单个策略。

        Args:
            mocker: pytest-mock 的 MockerFixture 实例，用于创建 mock 对象

        Note:
            约定：test_case.strategy_data 用于创建策略
        """
        for test_case in DELETE_SINGLE_TEST_CASES:
            validator = _ensure_validator(test_case)
            with isolated_strategy_mocks(mocker) as mockers:
                result: int | Exception
                strategy: Strategy | None = None
                try:
                    # 约定：test_case.strategy_data 用于创建策略
                    strategy_data: StrategyDataDict = test_case["strategy_data"]
                    strategy = Strategy(**strategy_data)
                    strategy.save(operator=str(test_case.get("operator", "")))
                    strategy_id: int = strategy.id

                    strategy.delete()
                    result = strategy_id
                except Exception as e:  # noqa: BLE001
                    result = e

                expected_exc = test_case.get("expected_exception")
                if expected_exc is not None:
                    assert isinstance(result, expected_exc), f"期望异常 {expected_exc}，实际：{result!r}"
                else:
                    if isinstance(result, Exception):
                        raise result

                validator(test_case, result, mockers)


@pytest.mark.django_db(databases=["default"])
class TestDeleteStrategiesBatch:
    """测试 Strategy.delete_by_strategy_ids() 批量删除（类方法）。"""

    def test_delete_strategies_batch_table_driven(self, mocker: MockerFixture) -> None:
        """表驱动：批量删除策略。

        Args:
            mocker: pytest-mock 的 MockerFixture 实例，用于创建 mock 对象
        """
        for test_case in DELETE_BATCH_TEST_CASES:
            validator = _ensure_validator(test_case)
            with isolated_strategy_mocks(mocker) as mockers:
                result: list[int] | Exception
                strategies: list[Strategy] = []
                try:
                    strategies_data: list[StrategyDataDict] = test_case["strategies_data"]
                    for strategy_data in strategies_data:
                        s: Strategy = Strategy(**strategy_data)
                        s.save(operator=str(test_case.get("operator", "")))
                        strategies.append(s)

                    strategy_ids: list[int] = [s.id for s in strategies]
                    Strategy.delete_by_strategy_ids(strategy_ids, operator=str(test_case.get("operator", "")))
                    result = strategy_ids
                except Exception as e:  # noqa: BLE001
                    result = e
                finally:
                    # 若批量删除未执行成功，兜底清理已创建的策略
                    for s in strategies:
                        try:
                            if getattr(s, "id", 0):
                                s.delete()
                        except Exception:
                            # 清理失败不影响框架本身，交由用户后续完善验证器/数据
                            pass

                expected_exc = test_case.get("expected_exception")
                if expected_exc is not None:
                    assert isinstance(result, expected_exc), f"期望异常 {expected_exc}，实际：{result!r}"
                else:
                    if isinstance(result, Exception):
                        raise result

                validator(test_case, result, mockers)
