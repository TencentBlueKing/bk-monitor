"""导出 Handler 定义

说明:
    - 表级 handlers: `TABLE_HANDLER_MAPPING`，按 model_label 配置（例如 `metadata.ResultTable`）
    - 通配 handlers: key='*'，会被追加到每张表 handlers 的最后执行
    - 全局 handlers: `GLOBAL_HANDLERS`，用于跨表处理
      - 必须通过 required_models 显式声明依赖的模型集合
      - 框架只会为被依赖模型收集内存数据，其他模型会直接落地
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from bkmonitor.data_migration.utils.types import RowDict, RowHandlerFn

# 表级别 Handler 映射
#
# key 支持两类：
# - "app_label.ModelName"：指定单张表的 handlers
# - "*"：通配 handlers，会被追加到每张表 handlers 的最后执行
TABLE_HANDLER_MAPPING: dict[str, list[RowHandlerFn]] = {}


class GlobalHandlerContext:
    """全局 handler 执行上下文

    说明：
        - 全局 handler 必须提前声明依赖的模型（required_models）
        - 框架只会为被依赖的模型收集内存数据，并通过 ctx.get/ctx.set 交互
        - ctx.set 覆盖整张表的数据，丢弃/过滤可在 handler 内自行完成
    """

    def __init__(self, data_by_model: dict[str, list[RowDict]], allowed_models: set[str]):
        self._data_by_model = data_by_model
        self._allowed_models = allowed_models

    def get(self, model_label: str) -> list[RowDict]:
        """获取某张表的导出数据"""
        if model_label not in self._allowed_models:
            raise KeyError(f"全局 handler 未声明依赖模型: {model_label}")
        return self._data_by_model.get(model_label, [])

    def set(self, model_label: str, rows: list[RowDict]) -> None:
        """覆盖某张表的导出数据"""
        if model_label not in self._allowed_models:
            raise KeyError(f"全局 handler 未声明依赖模型: {model_label}")
        self._data_by_model[model_label] = rows


class GlobalHandlerFn(Protocol):
    """全局 handler 函数签名"""

    def __call__(self, ctx: GlobalHandlerContext) -> None: ...


@dataclass(frozen=True)
class GlobalHandlerSpec:
    """全局 handler 定义"""

    name: str
    required_models: set[str]
    fn: GlobalHandlerFn


# 全局 handler 列表（按顺序执行）
GLOBAL_HANDLERS: list[GlobalHandlerSpec] = []


def disable_enable_fields(row: RowDict) -> RowDict | None:
    """将 enable/is_enable 字段置为 False

    Args:
        row: 原始数据行

    Returns:
        处理后的数据行
    """

    if "enable" not in row and "is_enable" not in row:
        return row
    if row.get("enable") is False and row.get("is_enable") is False:
        return row
    updated = dict(row)
    if "enable" in updated:
        updated["enable"] = False
    if "is_enable" in updated:
        updated["is_enable"] = False
    return updated


# metadata 的 ResultTable / DataSource：将 enable 全部置为 False
TABLE_HANDLER_MAPPING.update(
    {
        "metadata.ResultTable": [disable_enable_fields],
        "metadata.DataSource": [disable_enable_fields],
    }
)
