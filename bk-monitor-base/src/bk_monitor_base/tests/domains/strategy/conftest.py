"""strategy 域测试公共 fixture。

目前仅提供最小化的测试基础设施：
- 统一生成唯一的用例前缀，便于用户后续填充测试数据并在验证器中定位/清理数据
- 提供占位的策略数据模板（不保证可直接用于 save，仅作为填充参考）

注意：本文件不包含任何具体的测试数据，后续由使用者在 test_case 中填充。
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import uuid4

import pytest


@dataclass(frozen=True)
class StrategyTestContext:
    """strategy CRUD 用例上下文。

    Attributes:
        case_prefix: 每个测试用例的唯一前缀，建议用于 name/path 等字段，便于定位与清理。
        now: 生成前缀时的 UTC 时间戳（可用于时间相关字段的填充）。
    """

    case_prefix: str
    now: datetime


@pytest.fixture
def strategy_test_context(request: pytest.FixtureRequest) -> StrategyTestContext:
    """生成每个测试函数共享的上下文（同一测试函数内用例可复用）。"""
    now = datetime.now(tz=datetime.UTC)
    case_prefix = f"pytest_strategy_{request.node.name}_{uuid4().hex[:8]}"
    return StrategyTestContext(case_prefix=case_prefix, now=now)


@pytest.fixture
def strategy_data_template(strategy_test_context: StrategyTestContext) -> dict[str, Any]:
    """返回策略数据模板（占位）。

    说明：
    - Strategy.__init__ 需要的最小字段是：bk_biz_id/name/scenario
    - Strategy.save() 实际校验通常要求 items/detects/notice 等字段有效
      （取决于 serializer 与下游逻辑），因此该模板只作为“结构提示”，不保证可直接使用。
    """

    return {
        "bk_biz_id": 2,
        "name": f"{strategy_test_context.case_prefix}_name",
        "scenario": "host",
        # 下列字段通常需要用户补齐为可用配置
        "items": [],
        "detects": [],
        "actions": [],
        "notice": {},
        "labels": [],
        "app": "",
        "path": "",
        "priority": None,
        "priority_group_key": "",
    }
