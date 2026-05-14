"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder
from constants.data_source import DataSourceLabel, DataTypeLabel


@dataclass(frozen=True)
class APMAppTarget:
    """APM 应用维度目标，承载业务 ID 与应用名称"""

    bk_biz_id: int
    app_name: str


@dataclass(frozen=True)
class TraceDatasourceTarget:
    """Trace 数据源查询目标，表示一条`table_id -> APM 应用`的绑定关系"""

    table_id: str
    app: APMAppTarget

    @classmethod
    def build(cls, bk_biz_id: int, app_name: str, table_id: str) -> "TraceDatasourceTarget":
        return cls(table_id=table_id, app=APMAppTarget(bk_biz_id=bk_biz_id, app_name=app_name))


class TraceQueryGuard:
    """Trace 原始表查询隔离守卫
    只对共享 Trace 数据源的结果表追加 bk_biz_id 和 app_name 过滤；独占表、预计算表、历史表不追加过滤，避免存量数据缺字段导致查询不到数据
    """

    # 共享 Trace 数据源的结果表前缀，命中该前缀的 table_id 的查询必须携带应用上下文
    SHARED_TRACE_TABLE_PREFIXES: tuple[str, ...] = ("apm_global.shared",)

    # 共享表上用于应用隔离的字段
    BK_BIZ_ID_FIELD: str = "bk_biz_id"
    APP_NAME_FIELD: str = "app_name"

    @classmethod
    def is_shared_table(cls, table_id: str) -> bool:
        """判断 table_id 是否命中共享 Trace 结果表前缀"""
        return table_id.startswith(cls.SHARED_TRACE_TABLE_PREFIXES)

    @staticmethod
    def _normalize_bool_clause(raw_clause: Any) -> list[Any]:
        """将 ES bool 子句统一规整为 list 结构"""
        if raw_clause is None:
            return []
        if isinstance(raw_clause, list):
            return raw_clause
        return [raw_clause]

    @classmethod
    def get_q(cls, targets: Sequence[TraceDatasourceTarget]) -> QueryConfigBuilder:
        """基于 targets 构造标准 APM Trace 查询，内部自动完成共享表隔离
        当前阶段仅支持单 target：取首个元素作为查询目标，预留多 target 入参形态以便后续扩展。
        """
        target: TraceDatasourceTarget = targets[0]
        q: QueryConfigBuilder = QueryConfigBuilder((DataTypeLabel.LOG, DataSourceLabel.BK_APM)).table(target.table_id)
        return cls.apply_q(q, targets)

    @classmethod
    def apply_q(cls, q: QueryConfigBuilder, targets: Sequence[TraceDatasourceTarget]) -> QueryConfigBuilder:
        """给已有 QueryConfigBuilder 追加共享表隔离条件
        针对共享 Trace 数据源的查询为单 target：
            一次查询只会针对某业务某应用在共享表中的数据，因此命中共享 Trace 结果表时直接取首个补充 bk_biz_id / app_name 过滤。
        """
        target: TraceDatasourceTarget = targets[0]
        if not cls.is_shared_table(target.table_id):
            return q

        return q.filter(
            **{
                f"{cls.BK_BIZ_ID_FIELD}__eq": target.app.bk_biz_id,
                f"{cls.APP_NAME_FIELD}__eq": target.app.app_name,
            }
        )

    @classmethod
    def build_dsl(cls, body: dict[str, Any], target: TraceDatasourceTarget) -> dict[str, Any]:
        """给 ES DSL 查询体追加共享表隔离条件
        仅当 target.table_id 命中共享结果表前缀时生效；否则原样返回。

        合并策略：
            将原有 `query` 子树整体包进 `bool.must`，隔离条件追加到 `bool.filter`
            兼容调用方传入任意顶层 query clause（如 `bool` / `match_all` / `range` / `terms` 等）
        """
        if not cls.is_shared_table(target.table_id):
            return body

        new_body: dict[str, Any] = copy.deepcopy(body)
        isolation_filters: list[dict[str, Any]] = [
            {"term": {cls.BK_BIZ_ID_FIELD: target.app.bk_biz_id}},
            {"term": {cls.APP_NAME_FIELD: target.app.app_name}},
        ]

        original_query: dict[str, Any] | None = new_body.get("query")
        # 场景1：调用方未声明 query，仅用隔离条件构造 bool.filter 即可
        if not original_query:
            new_body["query"] = {"bool": {"filter": isolation_filters}}
            return new_body

        # 场景2：原 query 已是 bool 结构，直接合并隔离条件到 bool.filter，避免多套一层
        if "bool" in original_query and len(original_query) == 1:
            bool_node: dict[str, Any] = original_query["bool"]
            for clause_name in ("must", "filter", "should", "must_not"):
                if clause_name not in bool_node:
                    continue
                bool_node[clause_name] = cls._normalize_bool_clause(bool_node[clause_name])

            filter_node: list[dict[str, Any]] = bool_node.get("filter", [])
            filter_node.extend(isolation_filters)
            bool_node["filter"] = filter_node
            return new_body

        # 场景3：原 query 是其他顶层 query clause（match_all / range / terms 等），整体放入新 bool.must，隔离条件放入 bool.filter
        new_body["query"] = {
            "bool": {
                "must": [original_query],
                "filter": isolation_filters,
            }
        }
        return new_body
