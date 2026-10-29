"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from bkmonitor.data_source.format import flatten_dict_data
from semconv.rum.constants import RumSpanType, SessionPhase

from rum_web.handlers.builder.span import build as build_span
from rum_web.handlers.builder.utils import get_safe_number


@dataclass
class _Span:
    origin_data: dict[str, Any]
    flatten_data: dict[str, Any]


@dataclass
class ViewGroup:
    snapshots: list[_Span] = field(default_factory=list)
    vitals: list[_Span] = field(default_factory=list)
    members: list[_Span] = field(default_factory=list)


def _partition(spans: Sequence[dict[str, Any]]) -> tuple[list[_Span], dict[str, ViewGroup]]:
    """保留会话辅助记录，按 View ID 分组，并过滤重复的 Span ID。"""
    sessions: list[_Span] = []
    groups: dict[str, ViewGroup] = {}
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
        group = groups.setdefault(view_id, ViewGroup())
        if span_type == RumSpanType.VIEW.value:
            group.snapshots.append(item)
        elif span_type == RumSpanType.VITAL.value:
            group.vitals.append(item)
        else:
            group.members.append(item)
    return sessions, groups


def _node(span_id: str, children: Sequence[dict[str, Any]] = ()) -> dict[str, Any]:
    return {"span_id": span_id, **({"children": list(children)} if children else {})}


def _attach(members: Sequence[_Span]) -> list[dict[str, Any]]:
    """按开始时间排序。非 Action 成员命中同一 View 的 Action 时挂到该 Action，其余节点直属 View。"""
    nodes: dict[str, dict[str, Any]] = {}
    actions: dict[str, dict[str, Any]] = {}
    for item in members:
        span_id: str = item.origin_data["span_id"]
        nodes[span_id] = _node(span_id)
        if item.flatten_data.get("attributes.span_type") != RumSpanType.ACTION.value:
            continue
        if action_id := item.flatten_data.get("attributes.action.id"):
            actions.setdefault(action_id, nodes[span_id])
    children: list[dict[str, Any]] = []
    for item in sorted(members, key=lambda item: get_safe_number(item.flatten_data.get("start_time"))):
        node = nodes[item.origin_data["span_id"]]
        action = actions.get(item.flatten_data.get("attributes.action.id"))
        if item.flatten_data.get("attributes.span_type") != RumSpanType.ACTION.value and action is not None:
            action.setdefault("children", []).append(node)
        else:
            children.append(node)
    return children


def _session_times(sessions: Sequence[_Span]) -> tuple[int | float | None, int | float | None]:
    """会话开始取 start/rotate 的最早起点，结束取 end 的最晚终点。"""
    starts: list[int | float] = []
    ends: list[int | float] = []
    for item in sessions:
        phase = item.flatten_data.get("attributes.session.phase")
        if phase in (SessionPhase.START.value, SessionPhase.ROTATE.value):
            if (start := get_safe_number(item.flatten_data.get("start_time"), None)) is not None:
                starts.append(start)
        elif phase == SessionPhase.END.value:
            if (end := get_safe_number(item.flatten_data.get("end_time"), None)) is not None:
                ends.append(end)
    return min(starts, default=None), max(ends, default=None)


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
    for group in sorted(groups.values(), key=_started_at):
        if not group.snapshots:
            continue
        view = min(group.snapshots, key=_version)
        tree.append(_node(view.origin_data["span_id"], _attach(group.members)))
        records.append(build_span(view.origin_data, [item.origin_data for item in (*group.snapshots, *group.vitals)]))
        records.extend(build_span(item.origin_data) for item in group.members)
    start_time, end_time = _session_times(sessions)
    return {"start_time": start_time, "end_time": end_time, "tree": tree, "records": records}
