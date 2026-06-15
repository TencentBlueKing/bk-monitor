"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT

platform-source catalog 首个 domain：bkdata（蓝鲸基础计算平台 bk-base，只读）。

能力面：bk_data 数据源"无数据/断流/补录"的归属判定 ——
- get_result_table：结果表元数据（字段/存储），query_data 前的存在性与字段发现
- query_data：bksql 查询结果表；dtEventTime（事件时间）与 localTime（入库时间）
  对比可区分"数据延迟补录"与"真断流"

readonly 防线（在 id 前缀白名单 / domain readonly tag 之上叠加 params_guard）：
- 参数 key 白名单：拒绝一切未声明 key，杜绝 RequestSerializer 隐藏参数
  （如 _user_request 切换鉴权方式）经 CLI 整体透传下发
- query_data：SELECT-only + 单语句 + 禁注释/INTO + 强制末尾 LIMIT（≤ MAX_SQL_LIMIT）
- get_result_table：result_table_id 严格字符集校验（该值经 .format 拼入请求 URL 路径）

guard 用保守字符串规则、不做 SQL 解析：注释标记 / 分号 / INTO 的判定在字符串字面量内
也会命中（如 WHERE name = 'a;b' 会被拒），属有意取舍，改写查询绕开这些字符即可。
"""

from __future__ import annotations

import re
from typing import Any

from core.drf_resource import api

from ._catalog import OperationSpec, ParamsGuardRejected, PlatformSourceCatalog

MAX_SQL_LIMIT = 10000

QUERY_DATA_ALLOWED_KEYS = frozenset({"sql", "prefer_storage"})
GET_RESULT_TABLE_ALLOWED_KEYS = frozenset({"result_table_id", "related"})

_SELECT_RE = re.compile(r"^SELECT\b", re.IGNORECASE)
# 末尾 LIMIT 锚定：子查询内的 LIMIT 不能让外层无界查询过关；[0-9] 拒绝非 ASCII 数字
_TRAILING_LIMIT_RE = re.compile(r"\bLIMIT\s+([0-9]+)\s*$", re.IGNORECASE)
# SELECT ... INTO OUTFILE / DUMPFILE / @var 是 MySQL 系写出/导出形态
_INTO_RE = re.compile(r"\bINTO\b", re.IGNORECASE)
_COMMENT_TOKENS = ("--", "/*", "#")
# 合法结果表 ID 形如 <bk_biz_id>_<表名>；严格字符集防 URL 路径注入
_RESULT_TABLE_ID_RE = re.compile(r"^[A-Za-z0-9_]+$")


def _reject_unknown_keys(params: dict[str, Any], allowed: frozenset[str], op_id: str) -> None:
    unknown = sorted(str(k) for k in params if k not in allowed)
    if unknown:
        raise ParamsGuardRejected(f"{op_id} 仅接受参数 {sorted(allowed)}，拒绝未声明参数: {unknown}")


def guard_query_data(params: dict[str, Any]) -> dict[str, Any]:
    """query_data 参数防线：SELECT-only + 单语句 + 禁注释/INTO + 强制末尾 LIMIT。"""
    _reject_unknown_keys(params, QUERY_DATA_ALLOWED_KEYS, "query_data")

    sql = params.get("sql")
    if not isinstance(sql, str) or not sql.strip():
        raise ParamsGuardRejected("query_data 需要非空字符串参数 sql")
    body = sql.strip()
    for token in _COMMENT_TOKENS:
        if token in body:
            raise ParamsGuardRejected(
                f"sql 不允许包含注释标记 {token!r}（字符串字面量内同样拦截，请改写查询绕开该字符）"
            )
    body = body.rstrip(";").strip()
    if ";" in body:
        raise ParamsGuardRejected("sql 仅允许单条语句（字符串字面量内的分号同样拦截，请改写查询）")
    if not _SELECT_RE.match(body):
        raise ParamsGuardRejected("仅允许 SELECT 查询（readonly enforcement）")
    if _INTO_RE.search(body):
        raise ParamsGuardRejected("不允许 SELECT ... INTO 形态（OUTFILE / DUMPFILE / 变量导出均拒绝）")
    matched_limit = _TRAILING_LIMIT_RE.search(body)
    if matched_limit is None:
        raise ParamsGuardRejected(
            f"sql 必须以 LIMIT <n> 结尾（n ≤ {MAX_SQL_LIMIT}）；子查询内的 LIMIT 不计，"
            "LIMIT offset,n 与 OFFSET 子句不支持"
        )
    if int(matched_limit.group(1)) > MAX_SQL_LIMIT:
        raise ParamsGuardRejected(f"LIMIT 不得超过 {MAX_SQL_LIMIT}")

    normalized: dict[str, Any] = {"sql": body}
    if "prefer_storage" in params:
        prefer_storage = params["prefer_storage"]
        if not isinstance(prefer_storage, str):
            raise ParamsGuardRejected("prefer_storage 必须是字符串")
        normalized["prefer_storage"] = prefer_storage
    return normalized


def guard_get_result_table(params: dict[str, Any]) -> dict[str, Any]:
    """get_result_table 参数防线：result_table_id 严格字符集（值会拼入请求 URL 路径）。"""
    _reject_unknown_keys(params, GET_RESULT_TABLE_ALLOWED_KEYS, "get_result_table")

    result_table_id = params.get("result_table_id")
    if not isinstance(result_table_id, str) or not _RESULT_TABLE_ID_RE.fullmatch(result_table_id):
        raise ParamsGuardRejected("result_table_id 必须为非空 [A-Za-z0-9_]+ 字符串（该值会拼入请求 URL 路径）")
    normalized: dict[str, Any] = {"result_table_id": result_table_id}
    if "related" in params:
        related = params["related"]
        if not isinstance(related, list) or not all(
            isinstance(item, str) and _RESULT_TABLE_ID_RE.fullmatch(item) for item in related
        ):
            raise ParamsGuardRejected("related 必须为 [A-Za-z0-9_]+ 字符串数组（如 ['fields', 'storages']）")
        normalized["related"] = related
    return normalized


def register() -> None:
    """注册 bkdata domain。模块 import 时调用一次；测试 reset() 后可显式重注册。"""
    PlatformSourceCatalog.register_domain(
        id="bkdata",
        summary=(
            "蓝鲸基础计算平台（bk-base）只读查询：结果表元数据 + bksql 数据查询，"
            "服务 bk_data 数据源无数据/断流/补录的归属判定"
        ),
        audit_tags=["readonly", "bkdata"],
        operations=[
            OperationSpec(
                id="get_result_table",
                summary="查询 bkdata 结果表元数据（字段/存储）；query_data 前先做存在性与字段发现",
                handler=api.bkdata.get_result_table,
                params_guard=guard_get_result_table,
                params_schema_override={
                    "type": "object",
                    "properties": {
                        "result_table_id": {
                            "type": "string",
                            "description": "结果表 ID，格式 <bk_biz_id>_<表名>，仅允许 [A-Za-z0-9_]",
                        },
                        "related": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "关联信息，默认 ['fields', 'storages']",
                        },
                    },
                    "required": ["result_table_id"],
                },
                example_params={"result_table_id": "2_demo_table"},
                required_params=["result_table_id"],
                audit_tags=["readonly", "bkdata"],
                notes=(
                    "storages 字段揭示该表可查的存储引擎，可作为 query_data 的 prefer_storage 取值参考。"
                    "返回空对象 {} 表示结果表不存在/未接入（bk-base meta 既有契约），不是链路或权限故障；"
                    "结果表存在性判定以本接口为准"
                ),
            ),
            OperationSpec(
                id="query_data",
                summary=f"bksql 查询 bkdata 结果表（SELECT-only / 单语句 / 强制末尾 LIMIT ≤ {MAX_SQL_LIMIT}）",
                handler=api.bkdata.query_data,
                params_guard=guard_query_data,
                params_schema_override={
                    "type": "object",
                    "properties": {
                        "sql": {
                            "type": "string",
                            "description": (
                                f"bksql SELECT 语句；必须以 LIMIT <n> 结尾（n ≤ {MAX_SQL_LIMIT}）；"
                                "禁止注释 / 分号 / INTO"
                            ),
                        },
                        "prefer_storage": {
                            "type": "string",
                            "description": "可选，指定查询引擎（取值见 get_result_table 的 storages），默认由 bkdata 路由",
                        },
                    },
                    "required": ["sql"],
                },
                example_params={
                    "sql": (
                        "SELECT dtEventTime, localTime FROM 2_demo_table "
                        "WHERE dtEventTime >= '2026-01-01 00:00:00' ORDER BY dtEventTime LIMIT 200"
                    )
                },
                required_params=["sql"],
                audit_tags=["readonly", "bkdata"],
                notes=(
                    "dtEventTime=事件时间 / localTime=入库时间，二者对比可判定数据延迟补录 vs 真断流；"
                    "先用 get_result_table 确认表存在与可查存储。"
                    "注意：错误 1532018（结果表没有配置存储）对不存在的表与仅 pulsar 等不可查存储的表"
                    "是同一文案，不能据此判定表存在性；返回的 totalRecords 是本次查询的结果行数，"
                    "不代表该表落库量"
                ),
            ),
        ],
    )


register()
