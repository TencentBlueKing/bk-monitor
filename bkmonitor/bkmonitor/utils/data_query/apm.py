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

from django.utils.translation import gettext_lazy as _

from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder
from constants.data_source import DataSourceLabel, DataTypeLabel


@dataclass(frozen=True)
class APMAppTarget:
    """APM 应用维度目标，承载业务 ID 与应用名称
    独占表、预计算表、历史表对应的 target 可不携带应用上下文（下面两个字段均为 None）
    """

    bk_biz_id: int | None
    app_name: str | None


@dataclass(frozen=True)
class TraceDatasourceTarget:
    """Trace 数据源查询目标，表示一条`table_id -> APM 应用`的绑定关系"""

    table_id: str
    app: APMAppTarget

    @classmethod
    def from_(cls, bk_biz_id: int | None, app_name: str | None, table_id: str) -> "TraceDatasourceTarget":
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

    @classmethod
    def _validate_targets(cls, targets: Sequence[TraceDatasourceTarget]):
        """校验 targets 合法性，共享 Trace 结果表必须携带完整应用上下文"""
        if not targets:
            raise ValueError(_("TraceQueryGuard: targets 不能为空"))

        for target in targets:
            if not cls.is_shared_table(target.table_id):
                continue
            if not target.app.bk_biz_id or not target.app.app_name:
                raise ValueError(
                    _("TraceQueryGuard: 共享 Trace 结果表 {table_id} 查询必须携带 bk_biz_id 与 app_name").format(
                        table_id=target.table_id
                    )
                )

    @classmethod
    def get_q(cls, targets: Sequence[TraceDatasourceTarget]) -> QueryConfigBuilder:
        """基于 targets 构造标准 APM Trace 查询，内部自动完成共享表隔离"""
        q: QueryConfigBuilder = QueryConfigBuilder((DataTypeLabel.LOG, DataSourceLabel.BK_APM)).table(
            *[target.table_id for target in targets]
        )
        return cls.apply_q(q, targets)

    @classmethod
    def apply_q(cls, q: QueryConfigBuilder, targets: Sequence[TraceDatasourceTarget]) -> QueryConfigBuilder:
        """给已有 QueryConfigBuilder 追加共享表隔离条件
        独占 / 预计算 / 历史表对应的 target 不会被追加任何过滤。
        共享 Trace 数据源的查询模型为"单 target"：
            一次查询只会针对某业务某应用在共享表中的数据，因此命中共享 Trace 结果表时直接取首个补充 bk_biz_id / app_name 过滤。
        """
        cls._validate_targets(targets)

        shared_targets: list[TraceDatasourceTarget] = [
            target for target in targets if cls.is_shared_table(target.table_id)
        ]
        if not shared_targets:
            return q

        shared_target: TraceDatasourceTarget = shared_targets[0]
        return q.filter(
            **{
                f"{cls.BK_BIZ_ID_FIELD}__eq": shared_target.app.bk_biz_id,
                f"{cls.APP_NAME_FIELD}__eq": shared_target.app.app_name,
            }
        )

    @classmethod
    def build_dsl(cls, body: dict[str, Any], target: TraceDatasourceTarget) -> dict[str, Any]:
        """给 ES DSL 查询体追加共享表隔离条件
        仅当 target.table_id 命中共享结果表前缀时在 bool.filter 追加 term 条件；否则原样返回
        """
        cls._validate_targets([target])

        if not cls.is_shared_table(target.table_id):
            return body

        new_body: dict[str, Any] = copy.deepcopy(body)
        bool_node: dict[str, Any] = new_body.setdefault("query", {}).setdefault("bool", {})

        # bool.filter 在 ES DSL 中既可为单个 query 对象（dict）也可为 query 数组（list），统一规整为 list 后再追加隔离条件
        raw_filter: list[dict[str, Any]] | dict[str, Any] = bool_node.get("filter", [])
        filter_node: list[dict[str, Any]] = raw_filter if isinstance(raw_filter, list) else [raw_filter]
        filter_node.extend(
            [
                {"term": {cls.BK_BIZ_ID_FIELD: target.app.bk_biz_id}},
                {"term": {cls.APP_NAME_FIELD: target.app.app_name}},
            ]
        )
        bool_node["filter"] = filter_node
        return new_body
