"""数据处理 Pipeline 定义

说明:
    - 本模块提供统一的数据处理管道（pipeline），供 export 和 handle 命令共用
    - 表级处理: `TABLE_PIPELINE_MAPPING`，按 model_label 配置（例如 `metadata.ResultTable`）
    - 通配处理: key='*'，会被追加到每张表处理链的最后执行
    - 全局处理: `GLOBAL_PIPELINES`，用于跨表处理
      - 必须通过 required_models 显式声明依赖的模型集合
      - 框架只会为被依赖模型收集内存数据，其他模型会直接落地

使用示例:
    >>> # 批次处理：过滤/变更
    >>> def drop_deleted(rows: list[RowDict], model_label: str) -> list[RowDict]:
    ...     return [row for row in rows if not row.get("is_deleted")]
    >>>
    >>> TABLE_PIPELINE_MAPPING = {
    ...     "bkmonitor.ApiAuthToken": [drop_deleted],
    ...     "*": [replace_bk_tenant_id],
    ... }
    >>>
    >>> # 跨表处理：多表联动
    >>> def rewrite_table_ids(ctx: GlobalPipelineContext) -> None:
    ...     tables = ctx.get("metadata.ResultTable")
    ...     # ... 处理逻辑 ...
    ...     ctx.set("metadata.ResultTable", tables)
    >>>
    >>> GLOBAL_PIPELINES = [
    ...     GlobalPipelineSpec(
    ...         name="rewrite_table_ids",
    ...         required_models={"metadata.ResultTable", "metadata.ResultTableField"},
    ...         fn=rewrite_table_ids,
    ...     )
    ... ]
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Protocol

from ...utils.types import RowDict

# =============================================================================
# 类型定义
# =============================================================================

# 批次变换函数：输入行列表和模型标签，返回处理后的行列表（可过滤）
RowTransformer = Callable[[list[RowDict], str], list[RowDict]]


class GlobalPipelineFn(Protocol):
    """全局处理函数签名"""

    def __call__(self, ctx: GlobalPipelineContext) -> None: ...


@dataclass(frozen=True)
class GlobalPipelineSpec:
    """全局处理定义

    Attributes:
        name: 处理器名称，用于日志和错误提示
        required_models: 依赖的模型集合，只有这些模型会被加载到内存
        fn: 处理函数
    """

    name: str
    required_models: set[str]
    fn: GlobalPipelineFn


# =============================================================================
# 全局处理上下文
# =============================================================================


class GlobalPipelineContext:
    """全局处理执行上下文

    说明：
        - 全局处理必须提前声明依赖的模型（required_models）
        - 框架只会为被依赖的模型收集内存数据，并通过 ctx.get/ctx.set 交互
        - ctx.set 覆盖整张表的数据，丢弃/过滤可在处理函数内自行完成
    """

    def __init__(self, data_by_model: dict[str, list[RowDict]], allowed_models: set[str]):
        """初始化上下文

        Args:
            data_by_model: 模型数据映射，key 为 model_label，value 为行列表
            allowed_models: 允许访问的模型集合
        """

        self._data_by_model = data_by_model
        self._allowed_models = allowed_models

    def get(self, model_label: str) -> list[RowDict]:
        """获取某张表的数据

        Args:
            model_label: 模型标签（app_label.ModelName）

        Returns:
            该表的行数据列表

        Raises:
            KeyError: 未声明依赖该模型
        """
        if model_label not in self._allowed_models:
            raise KeyError(f"全局处理未声明依赖模型: {model_label}")
        return self._data_by_model.get(model_label, [])

    def set(self, model_label: str, rows: list[RowDict]) -> None:
        """覆盖某张表的数据

        Args:
            model_label: 模型标签（app_label.ModelName）
            rows: 新的行数据列表

        Raises:
            KeyError: 未声明依赖该模型
        """
        if model_label not in self._allowed_models:
            raise KeyError(f"全局处理未声明依赖模型: {model_label}")
        self._data_by_model[model_label] = rows

    def models(self) -> set[str]:
        """获取所有允许访问的模型标签"""
        return self._allowed_models.copy()


# =============================================================================
# 表级处理管道
# =============================================================================


class TablePipeline:
    """单表处理管道

    将多个 RowTransformer 按顺序编排，对批量数据依次执行。
    每个 transformer 接收 (rows, model_label) 并返回处理后的行列表。
    """

    def __init__(self, transformers: list[RowTransformer] | None = None):
        """初始化管道

        Args:
            transformers: 批次变换函数列表，按顺序执行
        """
        self._transformers: list[RowTransformer] = list(transformers) if transformers else []

    def add(self, transformer: RowTransformer) -> TablePipeline:
        """添加变换函数

        Args:
            transformer: 批次变换函数

        Returns:
            self，支持链式调用
        """
        self._transformers.append(transformer)
        return self

    def extend(self, transformers: Iterable[RowTransformer]) -> TablePipeline:
        """批量添加变换函数

        Args:
            transformers: 批次变换函数可迭代对象

        Returns:
            self，支持链式调用
        """
        self._transformers.extend(transformers)
        return self

    def process_batch(self, rows: list[RowDict], model_label: str) -> tuple[list[RowDict], int]:
        """处理批量数据

        Args:
            rows: 输入行列表
            model_label: 模型标签（app_label.ModelName）

        Returns:
            (处理后的行列表, 被过滤的行数)
        """
        input_count = len(rows)
        current = rows
        for fn in self._transformers:
            current = fn(current, model_label)
        dropped = input_count - len(current)
        return current, dropped

    @property
    def transformers(self) -> list[RowTransformer]:
        """获取变换函数列表（只读副本）"""
        return list(self._transformers)

    def __len__(self) -> int:
        return len(self._transformers)

    def __bool__(self) -> bool:
        return len(self._transformers) > 0


# =============================================================================
# 辅助函数
# =============================================================================


def get_table_pipeline(model_label: str) -> TablePipeline:
    """获取指定模型的处理管道

    会自动合并该模型专属的处理链和通配处理链。

    Args:
        model_label: 模型标签（app_label.ModelName）

    Returns:
        TablePipeline 实例
    """
    from .config import TABLE_PIPELINE_MAPPING

    pipeline = TablePipeline()
    # 先添加该模型专属的处理链
    if model_label in TABLE_PIPELINE_MAPPING:
        pipeline.extend(TABLE_PIPELINE_MAPPING[model_label])
    # 再添加通配处理链
    if "*" in TABLE_PIPELINE_MAPPING:
        pipeline.extend(TABLE_PIPELINE_MAPPING["*"])
    return pipeline


def get_global_required_models() -> set[str]:
    """获取所有全局处理依赖的模型集合

    Returns:
        所有全局处理依赖的模型标签集合
    """
    from .config import GLOBAL_PIPELINES

    required: set[str] = set()
    for spec in GLOBAL_PIPELINES:
        required |= spec.required_models
    return required


def run_global_pipelines(data_by_model: dict[str, list[RowDict]]) -> None:
    """执行所有全局处理

    Args:
        data_by_model: 模型数据映射，会被原地修改

    Raises:
        RuntimeError: 全局处理执行失败
    """
    from .config import GLOBAL_PIPELINES

    for spec in GLOBAL_PIPELINES:
        ctx = GlobalPipelineContext(data_by_model, allowed_models=spec.required_models)
        try:
            spec.fn(ctx)
        except Exception as exc:
            raise RuntimeError(f"全局处理执行失败: {spec.name}: {exc}") from exc
