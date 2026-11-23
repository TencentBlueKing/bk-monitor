"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from bkmonitor.data_source.format import flatten_dict_data
from semconv.rum.constants import RumSpanType

from rum_web.handlers.builder.span import build as build_span
from rum_web.handlers.builder.span.session import session_time_range
from rum_web.handlers.builder.utils import get_safe_number


MAX_DURATION_US = 4 * 60 * 60 * 1_000_000


def summary(
    spans: Sequence[dict[str, Any]],
    start_time: int | float | None,
    end_time: int | float | None,
) -> dict[str, Any]:
    """规范会话或 View 的时间范围，再计算时长和状态。"""
    start: int | float = start_time if start_time is not None else min(span["start_time"] for span in spans)
    end: int | float = end_time if end_time is not None else max(span["end_time"] for span in spans)
    status: str
    if end_time is not None:
        status = "ended"
    elif time.time() * 1_000_000 - start >= MAX_DURATION_US:
        status = "expired"
    else:
        status = "active"
    return {"start_time": start / 1000, "end_time": end / 1000, "duration": (end - start) / 1000, "status": status}


@dataclass
class _Span:
    origin_data: dict[str, Any]
    flatten_data: dict[str, Any]


@dataclass
class ViewGroup:
    snapshots: list[_Span] = field(default_factory=list)
    vitals: list[_Span] = field(default_factory=list)
    members: list[_Span] = field(default_factory=list)


def _partition(spans: Sequence[dict[str, Any]]) -> tuple[list[_Span], dict[tuple[str | None, str], ViewGroup]]:
    """保留会话辅助记录，按 Session 和 View ID 分组，并过滤重复的 Span ID。"""
    sessions: list[_Span] = []
    groups: dict[tuple[str | None, str], ViewGroup] = {}
    seen: set[str] = set()
    for span in spans:
        span_id = span.get("span_id")
        if not span_id or span_id in seen:
            continue
        seen.add(span_id)

        item = _Span(origin_data=span, flatten_data=flatten_dict_data(span))
        span_type = item.flatten_data.get("attributes.span_type")
        if span_type == RumSpanType.SESSION.value:
            sessions.append(item)
            continue
        view_id = item.flatten_data.get("attributes.view.id")
        if not view_id:
            continue
        session_id = item.flatten_data.get("attributes.session.id")
        if not isinstance(session_id, str) or not session_id:
            session_id = None
        group = groups.setdefault((session_id, view_id), ViewGroup())
        if span_type == RumSpanType.VIEW.value:
            group.snapshots.append(item)
        elif span_type == RumSpanType.VITAL.value:
            group.vitals.append(item)
        else:
            group.members.append(item)
    return sessions, groups


def _node(span_id: str, children: Sequence[dict[str, Any]] = ()) -> dict[str, Any]:
    return {"span_id": span_id, **({"children": list(children)} if children else {})}


def _attach(members: Sequence[_Span], session_id: str | None) -> list[dict[str, Any]]:
    """按开始时间挂载成员。新字段只关联同一 Session 和 View 内的 Action。"""
    nodes: dict[str, dict[str, Any]] = {}
    actions: dict[str, dict[str, Any]] = {}
    for item in members:
        span_id: str = item.origin_data["span_id"]
        nodes[span_id] = _node(span_id)
        if item.flatten_data.get("attributes.span_type") != RumSpanType.ACTION.value:
            continue
        action_id = item.flatten_data.get("attributes.action.id")
        if isinstance(action_id, str) and action_id:
            actions.setdefault(action_id, nodes[span_id])
    children: list[dict[str, Any]] = []
    for item in sorted(members, key=lambda item: get_safe_number(item.flatten_data.get("start_time"))):
        node = nodes[item.origin_data["span_id"]]
        flat = item.flatten_data
        if flat.get("attributes.span_type") == RumSpanType.ACTION.value or (
            session_id is None and "attributes.action.ids" in flat
        ):
            children.append(node)
            continue

        action_ids = flat.get("attributes.action.ids") or flat.get("attributes.action.id")
        # 打平后的单元素数组也是字符串，与历史单值字段一起处理。
        if isinstance(action_ids, str):
            action_ids = [action_ids]
        elif not isinstance(action_ids, list):
            action_ids = []
        matched_ids = {action_id for action_id in action_ids if isinstance(action_id, str) and action_id in actions}
        if not matched_ids:
            children.append(node)
        for action_id in matched_ids:
            actions[action_id].setdefault("children", []).append(node)
    return children


def _version(item: _Span) -> int | float:
    return get_safe_number(item.flatten_data.get("attributes.view.version"))


def _started_at(group: ViewGroup) -> int | float:
    """取最早有效导航时间，无有效值时使用 0。"""
    return min(
        (
            started_at
            for item in group.snapshots
            if (started_at := get_safe_number(item.flatten_data.get("attributes.view.started_at"), None)) is not None
        ),
        default=0,
    )


def build(spans: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """复用 Span 详情协议组装时间线，不查询存储，也不修改输入记录。"""
    sessions, groups = _partition(spans)
    tree: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    for (session_id, _), group in sorted(groups.items(), key=lambda item: _started_at(item[1])):
        if not group.snapshots:
            continue
        view = min(group.snapshots, key=_version)
        tree.append(_node(view.origin_data["span_id"], _attach(group.members, session_id)))
        records.append(build_span(view.origin_data, [item.origin_data for item in (*group.snapshots, *group.vitals)]))
        records.extend(build_span(item.origin_data) for item in group.members)
    start_time, end_time = session_time_range([item.flatten_data for item in sessions])
    return {"start_time": start_time, "end_time": end_time, "tree": tree, "records": records}
