"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language permissions and limitations under the License.
"""

from copy import deepcopy

import pytest

from rum_web.handlers.builder.span import build
from rum_web.handlers.builder.utils import phase
from rum_web.handlers.builder.span.view import (
    build_vital_source_key,
    ViewSpanBuilder,
    VITAL_METRICS,
    VITAL_METRIC_KEYS,
)


# ─────────────────────────────────────────────────────────────────────────────
# 公共构造器
# ─────────────────────────────────────────────────────────────────────────────


def _base_view_span(span_id: str = "34e3b6ff1943346c") -> dict:
    """模拟 SDK 瞬时 View 快照：根级时间为上报时刻，导航开始时间单独以毫秒保存。"""
    return {
        "span_id": span_id,
        "span_name": "view-001",
        "app_name": "test-app",
        "start_time": 1788451565500000,
        "end_time": 1788451565500000,
        "elapsed_time": 0,
        "attributes": {
            "span_type": "view",
            "view": {
                "id": "view-001",
                "started_at": 1788451565200,
                "url_template": "/order/submit",
                "previous_url_template": "/product/:id/",
                "loading_time": 200,
                "loading_time_source": "auto",
                "loading_type": "initial_load",
                "first_byte": 101.7,
                "dom_content_loaded": 140,
                "load_event": 175,
                "version": 1,
            },
            "session": {"id": "sess-001"},
            "user": {"id": "user-001"},
        },
        "resource": {"deployment": {"environment": {"name": "prod"}}},
    }


def _view_snapshot(
    span_id: str = "vs",
    version: int = 3,
    *,
    end_time: int = 1788451565999999,
    started_at: int | float | None = 1788451565200,
    **view_overrides,
) -> dict:
    """构造同 View ID 的瞬时快照，显式区分根级上报时间与 View 属性覆盖项。"""
    attributes = {
        "span_type": "view",
        "view": {
            "id": "view-001",
            "first_byte": 101.7,
            "dom_content_loaded": 140,
            "load_event": 175,
            "loading_time": 200,
            "loading_time_source": "auto",
            "loading_type": "initial_load",
            "version": version,
        },
    }
    if started_at is not None:
        attributes["view"]["started_at"] = started_at
    attributes["view"].update(view_overrides)
    return {
        "span_id": span_id,
        "start_time": end_time,
        "end_time": end_time,
        "elapsed_time": 0,
        "attributes": attributes,
    }


def _vital_span(metric: str, value: float, end_time: int = 1788451565328000, **ttfb) -> dict:
    """单个 Web Vitals 快照，metric 大小写不敏感。"""
    vital: dict = {"metric": metric, "value": value}
    if ttfb:
        vital["ttfb"] = ttfb
    return {
        "span_id": f"vital-{metric.lower()}",
        "end_time": end_time,
        "attributes": {"span_type": "vital", "vital": vital},
    }


def _resource_span(resource_type: str = "xhr") -> dict:
    return {
        "span_id": "7d2f09b6f8bc31aa",
        "span_name": "POST /api/orders",
        "app_name": "test-app",
        "start_time": 1788451565200000,
        "end_time": 1788451565328000,
        "elapsed_time": 128000,
        "attributes": {
            "span_type": "resource",
            "resource.type": resource_type,
            "resource.deployment.environment.name": "prod",
            "http.request.method": "POST",
            "http.response.status_code": 200,
            "url.template": "/api/orders",
            "url.full": "https://example.com/api/orders",
            "server.address": "example.com",
            "outcome.type": "success",
            "view.id": "view-001",
            "view.url_template": "/order/submit",
            "session.id": "sess-001",
            "user.id": "user-001",
        },
    }


def _section(result: dict, key: str) -> dict | None:
    for section in result.get("sections", []):
        if section.get("key") == key:
            return section
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 分派与通用头部
# ─────────────────────────────────────────────────────────────────────────────


class TestSpanBuilderDispatch:
    """分派表与公共头部（方案 0x03.h）"""

    def test_build_preserves_origin_data_and_span_id(self):
        span = _base_view_span()
        result = build(span, [])
        assert result["origin_data"] is span
        assert result["span_id"] == span["span_id"]

    @pytest.mark.parametrize(
        "span_type,section_keys",
        [
            ("resource", ["key_info", "resource_info"]),
            ("action", ["key_info"]),
            ("long_task", ["key_info"]),
            ("error", ["key_info"]),
            ("vital", ["vital_rating"]),
            ("view", ["key_info", "web_vitals"]),
        ],
    )
    def test_build_dispatches_to_registered_builder(self, span_type, section_keys):
        span = {"span_id": "x", "attributes": {"span_type": span_type}}
        result = build(span, [])
        assert "overview" in result
        # 每种已注册类型还应产出自己的区块，不能全部回落到只有公共头部的默认 Builder。
        assert [section["key"] for section in result["sections"]] == section_keys

    def test_unknown_span_type_falls_back_to_overview(self):
        """未知类型回落到 DefaultSpanBuilder，仍保留公共头部（方案 0x03.h 兜底）。"""
        span = {"span_id": "unknown", "span_name": "n/a", "attributes": {"span_type": "websocket"}}
        result = build(span, [])
        assert result["overview"]["title"] == "n/a"
        assert result["sections"] == []

    def test_view_overview_contains_common_items(self):
        span = _base_view_span()
        result = build(span, [span])
        items = {it["field_name"]: it["value"] for it in result["overview"]["items"]}
        view = span["attributes"]["view"]
        # 各字段均为源数据直接透传，引用构造对象避免与 fixture 重复硬编码
        assert items["app_name"] == span["app_name"]
        assert items["attributes.view.url_template"] == view["url_template"]
        assert items["attributes.view.previous_url_template"] == view["previous_url_template"]
        assert items["attributes.session.id"] == span["attributes"]["session"]["id"]
        assert items["attributes.view.id"] == view["id"]
        assert items["start_time"] == view["started_at"] * 1000
        assert items["end_time"] == span["end_time"]
        assert items["attributes.user.id"] == span["attributes"]["user"]["id"]
        assert items["resource.deployment.environment.name"] == span["resource"]["deployment"]["environment"]["name"]


# ─────────────────────────────────────────────────────────────────────────────
# Resource（方案 0x04.b）
# ─────────────────────────────────────────────────────────────────────────────


class TestResourceSpanBuilder:
    @pytest.mark.parametrize("resource_type", ["xhr", "img"])
    @pytest.mark.parametrize(
        "encoded,decoded,transfer,expected",
        [
            (3120, 8420, 3260, 0.6294536817),
            (280833, 903000, 0, 0.689),
            (42, 42, 60, 0),
            (0, 42, 0, 1),
        ],
        ids=["compressed-body", "cached-image", "uncompressed-body", "empty-body"],
    )
    def test_compression_ratio_uses_body_sizes(self, resource_type, encoded, decoded, transfer, expected):
        """压缩率使用正文大小，传输头部开销与缓存命中不影响结果，真实零值也应保留。"""
        span = _resource_span(resource_type)
        span["attributes"].update(
            {
                "resource.encoded_body_size": encoded,
                "resource.decoded_body_size": decoded,
                "resource.transfer_size": transfer,
            }
        )
        result = build(span)
        transfer_data = _section(result, "key_info")["data"]["transfer"]
        assert transfer_data["display.compression_ratio"] == pytest.approx(expected)

    @pytest.mark.parametrize(
        "body_sizes",
        [
            {},
            {"resource.encoded_body_size": None, "resource.decoded_body_size": 8420},
            {"resource.encoded_body_size": "invalid", "resource.decoded_body_size": 8420},
            {"resource.encoded_body_size": 3120, "resource.decoded_body_size": "invalid"},
            {"resource.encoded_body_size": 3120, "resource.decoded_body_size": 0},
        ],
        ids=["missing-sizes", "null-encoded", "invalid-encoded", "invalid-decoded", "zero-decoded"],
    )
    def test_compression_ratio_without_valid_sizes_is_null(self, body_sizes):
        span = _resource_span()
        span["attributes"].update(body_sizes)
        result = build(span)
        transfer_data = _section(result, "key_info")["data"]["transfer"]
        assert transfer_data["display.compression_ratio"] is None

    def test_xhr_fetch_key_info_fields(self):
        span = _resource_span("xhr")
        result = build(span, [])
        attrs = span["attributes"]
        key_info = _section(result, "key_info")["data"]
        # 各字段均为源数据直接透传，引用构造对象避免与 fixture 重复硬编码
        assert key_info["request"]["attributes.http.request.method"] == attrs["http.request.method"]
        assert key_info["request"]["attributes.url.template"] == attrs["url.template"]
        assert key_info["request"]["attributes.url.full"] == attrs["url.full"]
        assert key_info["request"]["attributes.server.address"] == attrs["server.address"]
        assert key_info["duration"]["elapsed_time"] == span["elapsed_time"]
        assert key_info["http_result"]["attributes.http.response.status_code"] == attrs["http.response.status_code"]
        assert key_info["http_result"]["attributes.outcome.type"] == attrs["outcome.type"]

    def test_xhr_fetch_loading_timing_total(self):
        span = _resource_span("xhr")
        # 方案 0x04.b 通用：total_duration = download.start + download.duration
        # 时序字段置于 attributes.resource.*，打平后为 attributes.resource.redirect.start 等
        span["attributes"].update(
            {
                "resource.type": "xhr",
                "resource.redirect.start": 0,
                "resource.dns.start": 1.2,
                "resource.dns.duration": 3.8,
                "resource.connect.start": 5,
                "resource.connect.duration": 10,
                "resource.ssl.start": 9.1,
                "resource.ssl.duration": 5.9,
                "resource.first_byte.start": 15,
                "resource.first_byte.duration": 86.7,
                "resource.download.start": 101.7,
                "resource.download.duration": 26.3,
            }
        )
        result = build(span, [])
        timing = _section(result, "loading_timing")["data"]
        assert timing["unit"] == "ms"
        assert timing["total_duration"] == pytest.approx(101.7 + 26.3)
        keys = [p["key"] for p in timing["phases"]]
        assert keys == ["prepare", "dns", "connect", "tls", "first_byte", "download"]
        phases = {p["key"]: p for p in timing["phases"]}
        assert phases["connect"]["duration"] == pytest.approx(4.1)
        assert phases["tls"]["start"] == pytest.approx(9.1)
        assert phases["tls"]["duration"] == pytest.approx(5.9)

    def test_others_loading_timing_has_resource_info(self):
        span = _resource_span("img")
        result = build(span, [])
        assert _section(result, "resource_info") is not None
        # 跨域资源无时序字段，整段加载时序省略（与「耗时为 0」区分）
        assert _section(result, "loading_timing") is None

    def test_connect_duration_without_tls_is_preserved(self):
        span = _resource_span()
        span["attributes"].update({"resource.connect.start": 5, "resource.connect.duration": 10})
        result = build(span)
        phases = {p["key"]: p for p in _section(result, "loading_timing")["data"]["phases"]}
        assert "tls" not in phases
        assert phases["connect"]["duration"] == 10


# ─────────────────────────────────────────────────────────────────────────────
# Action（方案 0x04.c）
# ─────────────────────────────────────────────────────────────────────────────


class TestActionSpanBuilder:
    def test_action_key_info(self):
        span = {
            "span_id": "e121536e5ae785a0",
            "span_name": "click .submit-btn",
            "app_name": "test-app",
            "start_time": 1788451565200000,
            "end_time": 1788451565632000,
            "elapsed_time": 432000,
            "attributes": {
                "span_type": "action",
                "action": {
                    "type": "click",
                    "target": {"name": ".submit-btn", "tag": "button"},
                },
                "outcome": {"type": "warning"},
                "view": {"id": "view-001"},
                "session": {"id": "sess-001"},
                "user": {"id": "user-001"},
                "resource": {"deployment": {"environment": {"name": "prod"}}},
            },
        }
        result = build(span, [])
        key_info = _section(result, "key_info")["data"]
        action = span["attributes"]["action"]
        # 各字段均为源数据直接透传，引用构造对象避免与入参重复硬编码
        assert key_info["interaction"]["attributes.action.type"] == action["type"]
        assert key_info["target"]["attributes.action.target.name"] == action["target"]["name"]
        assert key_info["target"]["attributes.action.target.tag"] == action["target"]["tag"]
        badges = {b["field_name"]: b["value"] for b in result["overview"]["badges"]}
        assert badges["elapsed_time"] == span["elapsed_time"]
        assert badges["attributes.action.type"] == action["type"]
        assert badges["attributes.outcome.type"] == span["attributes"]["outcome"]["type"]


# ─────────────────────────────────────────────────────────────────────────────
# LongTask（方案 0x04.d）— 保留上报的阻塞贡献
# ─────────────────────────────────────────────────────────────────────────────


class TestLongTaskSpanBuilder:
    def test_longtask_preserves_blocking_duration(self):
        span = {
            "span_id": "c49ddfc2ac5214d7",
            "span_name": "longTask",
            "app_name": "test-app",
            "start_time": 1788451565200000,
            "end_time": 1788451565323500,
            "elapsed_time": 123500,
            "attributes": {
                "span_type": "long_task",
                "long_task": {
                    "blocking_duration": 42.5,
                    "entry_type": "long-animation-frame",
                    "name": "long-animation-frame",
                },
                "action": {"id": "act-001"},
                "outcome": {"type": "warning"},
                "view": {"id": "view-001"},
                "session": {"id": "sess-001"},
                "user": {"id": "user-001"},
                "resource": {"deployment": {"environment": {"name": "prod"}}},
            },
        }
        result = build(span, [])
        key_info = _section(result, "key_info")["data"]
        long_task = span["attributes"]["long_task"]
        # 各字段均为源数据直接透传，引用构造对象避免与入参重复硬编码
        # 停留时长沿用上报 elapsed_time，不丢弃上报的阻塞贡献
        assert key_info["duration"]["elapsed_time"] == span["elapsed_time"]
        assert key_info["duration"]["attributes.long_task.blocking_duration"] == long_task["blocking_duration"]
        assert key_info["action"]["attributes.action.id"] == span["attributes"]["action"]["id"]
        assert key_info["attribution"]["attributes.long_task.entry_type"] == long_task["entry_type"]
        assert key_info["attribution"]["attributes.long_task.name"] == long_task["name"]


# ─────────────────────────────────────────────────────────────────────────────
# Error（方案 0x04.e）
# ─────────────────────────────────────────────────────────────────────────────


class TestErrorSpanBuilder:
    def test_error_key_info(self):
        span = {
            "span_id": "9d199175096474e4",
            "span_name": "TypeError: Cannot read properties of undefined (reading 'name')",
            "app_name": "test-app",
            "start_time": 1788451565200000,
            "end_time": 1788451565323500,
            "elapsed_time": 123500,
            "attributes": {
                "span_type": "error",
                "outcome": {"type": "error"},
                "code": {"filepath": "https://example.com/static/js/app.js", "lineno": 9, "column": 654249},
                "view": {"id": "view-001"},
                "session": {"id": "sess-001"},
                "user": {"id": "user-001"},
                "resource": {"deployment": {"environment": {"name": "prod"}}},
            },
            "events": [
                {"name": "exception", "attributes": {"exception": {"type": "TypeError"}}},
            ],
        }
        result = build(span, [])
        key_info = _section(result, "key_info")["data"]
        code = span["attributes"]["code"]
        # 各字段均为源数据直接透传，引用构造对象避免与入参重复硬编码
        assert (
            key_info["error_type"]["events.attributes.exception.type"]
            == span["events"][0]["attributes"]["exception"]["type"]
        )
        assert key_info["source"]["attributes.code.filepath"] == code["filepath"]
        assert key_info["source"]["attributes.code.lineno"] == code["lineno"]
        assert key_info["source"]["attributes.code.column"] == code["column"]


# ─────────────────────────────────────────────────────────────────────────────
# Vital（方案 0x04.f）— 不使用 Span 耗时，CLS 无单位
# ─────────────────────────────────────────────────────────────────────────────


class TestVitalSpanBuilder:
    def test_vital_rating_not_uses_span_elapsed_time(self):
        """Vital 的评级来自 attributes.vital.value，而非 Span 的 elapsed_time。"""
        span = {
            "span_id": "ea1ae6490e17fd9d",
            "span_name": "LCP",
            "app_name": "test-app",
            "start_time": 1788451565327840,
            "end_time": 1788451565327840,
            "elapsed_time": 0,
            "attributes": {
                "span_type": "vital",
                "vital": {"metric": "lcp", "value": 2840},
                "view": {"id": "view-001"},
                "session": {"id": "sess-001"},
                "user": {"id": "user-001"},
                "resource": {"deployment": {"environment": {"name": "prod"}}},
            },
        }
        result = build(span, [])
        rating = _section(result, "vital_rating")["data"]
        vital = span["attributes"]["vital"]
        # 各字段均为源数据直接透传，引用构造对象避免与入参重复硬编码
        assert rating["attributes.vital.metric"] == vital["metric"]
        # 瞬时 Vital 的 elapsed_time 为 0，而指标为 2840ms，二者必须明确区分。
        assert rating["attributes.vital.value"] == vital["value"]
        badges = {badge["field_name"]: badge["value"] for badge in result["overview"]["badges"]}
        assert badges["display.rating_level"] == "needs_improvement"
        # 评级配置末项省略 value（领域约定，保留字）
        config = rating["display.rating_config"]
        assert config[-1]["rating"] == "poor"
        assert "value" not in config[-1]

    @pytest.mark.parametrize(
        "value,expected_rating,expected_alias",
        [(0, "good", "良好"), (2840, "needs_improvement", "需改进"), (9000, "poor", "差")],
    )
    def test_vital_badge_outputs_rating_level_not_threshold(self, value, expected_rating, expected_alias):
        """概览徽标 value 为评级标识（如 needs_improvement），而非命中档位的阈值。"""
        span = {
            "span_id": "ea1ae6490e17fd9d",
            "span_name": "LCP",
            "app_name": "test-app",
            "elapsed_time": 1,
            "attributes": {
                "span_type": "vital",
                "vital": {"metric": "lcp", "value": value},
                "view": {"id": "view-001"},
                "resource": {"deployment": {"environment": {"name": "prod"}}},
            },
        }
        result = build(span, [])
        badges = {b["field_name"]: b for b in result["overview"]["badges"]}
        badge = badges["display.rating_level"]
        assert badge["value"] == expected_rating
        assert badge["alias"] == expected_alias

    def test_vital_badge_no_value_not_rated(self):
        """指标值缺失时按不评级处理，输出 EMPTY_VALUE（避免误判良好）。"""
        from rum_web.handlers.builder.base import EMPTY_VALUE

        span = {
            "span_id": "ea1ae6490e17fd9d",
            "span_name": "LCP",
            "app_name": "test-app",
            "elapsed_time": 1,
            "attributes": {
                "span_type": "vital",
                "vital": {"metric": "lcp"},  # 无 value
                "view": {"id": "view-001"},
                "resource": {"deployment": {"environment": {"name": "prod"}}},
            },
        }
        result = build(span, [])
        badges = {b["field_name"]: b for b in result["overview"]["badges"]}
        badge = badges["display.rating_level"]
        assert badge["value"] == EMPTY_VALUE
        assert badge["alias"] == EMPTY_VALUE

    def test_vital_cls_has_no_unit_in_config(self):
        """CLS 评级配置不携带 field_unit，下游按无单位处理。"""
        span = {
            "span_id": "cls-1",
            "span_name": "CLS",
            "app_name": "test-app",
            "elapsed_time": 1,
            "attributes": {
                "span_type": "vital",
                "vital": {"metric": "cls", "value": 0.023},
                "view": {"id": "view-001"},
                "session": {"id": "sess-001"},
                "user": {"id": "user-001"},
                "resource": {"deployment": {"environment": {"name": "prod"}}},
            },
        }
        result = build(span, [])
        rating = _section(result, "vital_rating")["data"]
        # 源数据直接透传，引用构造对象避免与入参重复硬编码
        assert rating["attributes.vital.value"] == span["attributes"]["vital"]["value"]
        # 评级阈值沿用字段单位；CLS 阈值为纯小数（领域约定，保留字）
        assert rating["display.rating_config"][0]["value"] == 0.1


# ─────────────────────────────────────────────────────────────────────────────
# View 详情（方案 0x04.g）
# ─────────────────────────────────────────────────────────────────────────────


class TestViewSpanBuilder:
    @pytest.mark.parametrize("selected_phase", ["start", "update", "end"])
    def test_view_stay_duration_uses_navigation_start(self, selected_phase):
        """点开同一 View 的任意瞬时快照，概览和卡片都展示完整生命周期的停留时长。"""
        navigation_start_us = 1788451565200000
        snapshots = {
            "start": _view_snapshot("start", version=1, end_time=navigation_start_us, phase="start"),
            "update": _view_snapshot("update", version=2, end_time=navigation_start_us + 709200, phase="update"),
            "end": _view_snapshot("end", version=3, end_time=navigation_start_us + 11448200, phase="end"),
        }
        # start 上报时尚无加载耗时，详情应从最新快照补齐这些字段。
        for field in ("first_byte", "dom_content_loaded", "load_event", "loading_time", "loading_time_source"):
            snapshots["start"]["attributes"]["view"].pop(field)
        span = snapshots[selected_phase]
        original_snapshots = deepcopy(snapshots)
        # 关联结果故意乱序，展示时间仍应来自导航开始与最新版本的结束快照。
        result = build(span, [snapshots["end"], snapshots["start"], snapshots["update"]])
        duration = _section(result, "key_info")["data"]["duration"]["display.view.duration"]
        badges = {item["field_name"]: item["value"] for item in result["overview"]["badges"]}
        items = {item["field_name"]: item["value"] for item in result["overview"]["items"]}
        assert duration == pytest.approx(11448.2)
        assert badges["display.view.duration"] == pytest.approx(11448.2)
        assert "elapsed_time" not in badges
        assert items["start_time"] == navigation_start_us
        assert items["end_time"] == snapshots["end"]["end_time"]
        assert result["span_id"] == span["span_id"]
        assert result["origin_data"] is span
        assert snapshots == original_snapshots

    def test_view_snapshot_overrides_loading_and_report_time_fields(self):
        """补齐最新快照的加载与结束时间，概览开始时间取导航开始，其他主记录字段不变。"""
        span = _base_view_span()
        snapshot = _view_snapshot(version=3, loading_time=333, first_byte=120, dom_content_loaded=160, load_event=200)
        result = ViewSpanBuilder._prepare_flatten_data(span, [span, snapshot])
        assert snapshot["end_time"] != span["end_time"]
        assert "end_time" not in snapshot["attributes"]["view"]
        assert result["start_time"] == span["attributes"]["view"]["started_at"] * 1000
        assert result["end_time"] == snapshot["end_time"]
        assert result["elapsed_time"] == 0
        assert result["attributes.view.loading_time"] == 333
        assert result["attributes.view.first_byte"] == 120
        # 主记录的标题不被关联快照覆盖。
        assert result["span_name"] == "view-001"

    def test_view_start_time_uses_navigation_start(self):
        """导航开始时间取最新快照的 attributes.view.started_at（毫秒→微秒），不随瞬时快照变化。"""
        span = _base_view_span()
        started_at_ms = 1788451565200.125
        snapshot = _view_snapshot(version=3, loading_time=333, started_at=started_at_ms)
        result = ViewSpanBuilder._prepare_flatten_data(span, [span, snapshot])
        # 期望以导航开始时间覆盖，而非快照上报时刻（避免停留时长恒为 0）
        assert result["start_time"] == 1788451565200125
        assert result["start_time"] != snapshot["end_time"]

    def test_view_duration_missing_start_time_not_fabricated(self):
        """start_time / end_time 任一缺失时停留时长返回 EMPTY_VALUE，不伪造 0。"""
        from rum_web.handlers.builder.base import EMPTY_VALUE
        from rum_web.handlers.builder.span.view import DisplayViewDurationItem

        item = DisplayViewDurationItem()
        assert item.render({"end_time": 1000})["display.view.duration"] == EMPTY_VALUE
        assert item.render({"start_time": 0})["display.view.duration"] == EMPTY_VALUE

    def test_view_web_vitals_filled_from_latest_snapshot(self):
        """Web Vitals 五项由最新快照填充，TTFB 含四段耗时与评分配置。"""
        span = _base_view_span()
        ttfb = _vital_span(
            "TTFB", 101.7, waiting_duration=1.2, dns_duration=3.8, connection_duration=10, request_duration=83.7
        )
        fcp = _vital_span("FCP", 120)
        lcp = _vital_span("LCP", 250)
        inp = _vital_span("INP", 86)
        cls = _vital_span("CLS", 0.023)
        result = build(span, [span, _view_snapshot(), ttfb, fcp, lcp, inp, cls])
        web_vitals = _section(result, "web_vitals")["data"]
        # 各指标 value 直接引用构造入参，改样例无需逐个同步字面量
        assert web_vitals["ttfb"]["attributes.vital.value"] == ttfb["attributes"]["vital"]["value"]
        assert (
            web_vitals["ttfb"]["attributes.vital.ttfb.waiting_duration"]
            == ttfb["attributes"]["vital"]["ttfb"]["waiting_duration"]
        )
        assert (
            web_vitals["ttfb"]["attributes.vital.ttfb.dns_duration"]
            == ttfb["attributes"]["vital"]["ttfb"]["dns_duration"]
        )
        assert (
            web_vitals["ttfb"]["attributes.vital.ttfb.connection_duration"]
            == ttfb["attributes"]["vital"]["ttfb"]["connection_duration"]
        )
        assert (
            web_vitals["ttfb"]["attributes.vital.ttfb.request_duration"]
            == ttfb["attributes"]["vital"]["ttfb"]["request_duration"]
        )
        assert web_vitals["fcp"]["attributes.vital.value"] == fcp["attributes"]["vital"]["value"]
        assert web_vitals["lcp"]["attributes.vital.value"] == lcp["attributes"]["vital"]["value"]
        assert web_vitals["inp"]["attributes.vital.value"] == inp["attributes"]["vital"]["value"]
        assert web_vitals["cls"]["attributes.vital.value"] == cls["attributes"]["vital"]["value"]
        # 评分配置末项省略 value（领域约定，保留字）
        assert "value" not in web_vitals["ttfb"]["display.rating_config"][-1]

    def test_view_loading_timing_full_waterfall(self):
        """initial_load + auto：完整 7 段 phases + 3 markers，total_duration = loading_time。"""
        span = _base_view_span()
        view = span["attributes"]["view"]
        loading_time = view["loading_time"]
        first_byte = view["first_byte"]
        dom_content_loaded = view["dom_content_loaded"]
        load_event = view["load_event"]
        ttfb = _vital_span(
            "TTFB", 101.7, waiting_duration=1.2, dns_duration=3.8, connection_duration=10, request_duration=83.7
        )
        vital = ttfb["attributes"]["vital"]
        ttfb_value = vital["value"]
        waiting = vital["ttfb"]["waiting_duration"]
        dns = vital["ttfb"]["dns_duration"]
        connect = vital["ttfb"]["connection_duration"]
        request = vital["ttfb"]["request_duration"]

        fcp = _vital_span("FCP", 120)
        lcp = _vital_span("LCP", 250)
        result = build(span, [span, _view_snapshot(), ttfb, fcp, lcp])
        timing = _section(result, "loading_timing")["data"]
        assert timing["unit"] == "ms"
        # total_duration 来自当前快照 loading_time
        assert timing["total_duration"] == loading_time

        phases = {p["key"]: p for p in timing["phases"]}
        # phases 起点由 TTFB 各段耗时反推，全部引用构造入参，改样例自动跟随
        first_byte_start = ttfb_value - request
        connect_start = first_byte_start - connect
        dns_start = connect_start - dns
        assert phases["prepare"]["start"] == 0
        assert phases["prepare"]["duration"] == pytest.approx(waiting)
        assert phases["dns"]["start"] == pytest.approx(dns_start)
        assert phases["dns"]["duration"] == pytest.approx(dns)
        assert phases["connect"]["start"] == pytest.approx(connect_start)
        assert phases["connect"]["duration"] == pytest.approx(connect)
        assert phases["first_byte"]["start"] == pytest.approx(first_byte_start)
        assert phases["first_byte"]["duration"] == pytest.approx(request)
        assert phases["dom_processing"]["start"] == pytest.approx(first_byte)
        assert phases["dom_processing"]["duration"] == pytest.approx(dom_content_loaded - first_byte)
        assert phases["resource_load"]["start"] == pytest.approx(dom_content_loaded)
        assert phases["resource_load"]["duration"] == pytest.approx(load_event - dom_content_loaded)
        assert phases["page_stable"]["start"] == pytest.approx(load_event)
        assert phases["page_stable"]["duration"] == pytest.approx(loading_time - load_event)
        markers = {m["key"]: m["value"] for m in timing["markers"]}
        assert markers == {"TTFB": ttfb_value, "FCP": 120, "LCP": 250}

    def test_view_auto_stable_rounding_error_keeps_zero_duration_phase(self):
        """自动来源的负浮点误差归零，页面稳定阶段仍应保留。"""
        span = _base_view_span()
        snapshot = _view_snapshot(loading_time=608.7999999523163, load_event=608.800048828125)
        result = build(span, [span, snapshot])
        timing = _section(result, "loading_timing")["data"]
        phases = {p["key"]: p for p in timing["phases"]}
        assert phases["page_stable"]["duration"] == 0

    def test_view_loading_timing_manual_source_skips_page_stable(self):
        """手动来源不生成 page_stable 段（方案 0x04.g 约束 [2]）。"""
        span = _base_view_span()
        snapshot = _view_snapshot(version=3, loading_time_source="manual")
        result = build(span, [span, snapshot])
        timing = _section(result, "loading_timing")["data"]
        keys = [p["key"] for p in timing["phases"]]
        assert "page_stable" not in keys
        assert "dom_processing" in keys

    def test_view_loading_timing_non_initial_load_omitted(self):
        """非首次加载无导航原点，整段加载时序省略（phases/markers 均不构造）。"""
        span = _base_view_span()
        snapshot = _view_snapshot(version=3, loading_type="route_change", loading_time_source="manual")
        result = build(span, [span, snapshot])
        # 非 initial_load → loading_timing section 整体不输出
        assert _section(result, "loading_timing") is None

    def test_view_loading_timing_missing_loading_time_omits_total_duration(self):
        """loading_time 缺失时 total_duration 键省略（不输出，而非伪造 0）。"""
        span = _base_view_span()
        snapshot = _view_snapshot(version=3, loading_time=None)
        result = build(span, [span, snapshot])
        timing = _section(result, "loading_timing")["data"]
        assert "total_duration" not in timing

    def test_view_loading_timing_zero_loading_time_keeps_zero(self):
        """loading_time 为有效零值应保留 0（与缺失区分）。"""
        span = _base_view_span()
        snapshot = _view_snapshot(version=3, loading_time=0)
        result = build(span, [span, snapshot])
        timing = _section(result, "loading_timing")["data"]
        assert timing["total_duration"] == 0

    def test_view_milestones_omits_missing_and_manual_page_stable(self):
        """里程碑缺失字段整项省略；page_stable 仅自动计时来源输出。"""
        span = _base_view_span()
        # 手动来源 + dom_complete 缺失
        snapshot = _view_snapshot(version=3, loading_time_source="manual", loading_time=200, dom_complete=None)
        result = build(span, [span, snapshot])
        timing = _section(result, "loading_timing")["data"]
        milestones = {m["key"]: m.get("value") for m in timing["milestones"]}
        # dom_complete 缺失 → 整项省略
        assert "dom_complete" not in milestones
        # load_event 存在
        assert milestones["load_event"] == snapshot["attributes"]["view"]["load_event"]
        # 手动来源 → page_stable 不输出
        assert "page_stable" not in milestones

    def test_view_milestones_includes_page_stable_when_auto(self):
        """自动计时来源输出 page_stable 里程碑。"""
        span = _base_view_span()
        snapshot = _view_snapshot(version=3, loading_time_source="auto", loading_time=200)
        result = build(span, [span, snapshot])
        timing = _section(result, "loading_timing")["data"]
        milestones = {m["key"]: m.get("value") for m in timing["milestones"]}
        assert milestones["page_stable"] == 200

    def test_view_milestones_use_latest_dom_complete(self):
        """早期快照没有 DOM Complete 时，从最新 View 快照补齐里程碑。"""
        span = _base_view_span()
        snapshot = _view_snapshot(dom_complete=166)
        assert "dom_complete" not in span["attributes"]["view"]
        result = build(span, [span, snapshot])
        timing = _section(result, "loading_timing")["data"]
        milestones = {m["key"]: m["value"] for m in timing["milestones"]}
        assert milestones["dom_complete"] == 166

    def test_view_loading_timing_omits_missing_vital_markers(self):
        """缺失某个 Web Vitals 指标时，该指标段不补造（markers 仅含存在的）。"""
        span = _base_view_span()
        ttfb = _vital_span(
            "TTFB", 101.7, waiting_duration=1.2, dns_duration=3.8, connection_duration=10, request_duration=83.7
        )
        # 仅注入 TTFB，FCP/LCP 缺失
        result = build(span, [span, _view_snapshot(), ttfb])
        timing = _section(result, "loading_timing")["data"]
        marker_keys = [m["key"] for m in timing["markers"]]
        assert marker_keys == ["TTFB"]

    def test_view_loading_timing_reversed_boundary_omits_segment(self):
        """倒序边界（dom_content_loaded < first_byte）产生负时长，对应 phase 省略不组装伪时序。"""
        span = _base_view_span()
        view = span["attributes"]["view"]
        # 重写边界使内容传输段时长为负：dom_content_loaded 早于 first_byte
        view.update({"first_byte": 140, "dom_content_loaded": 100, "load_event": 175, "loading_time": 200})
        result = build(span, [span])
        timing = _section(result, "loading_timing")["data"]
        keys = [p["key"] for p in timing["phases"]]
        # 仅耗时为负的一段省略，后续有效段（resource_load / page_stable）仍保留
        assert "dom_processing" not in keys
        assert "resource_load" in keys
        assert "page_stable" in keys

    def test_view_loading_timing_first_byte_missing_omits_dom_processing(self):
        """first_byte 缺失使内容传输段无起点，仅 dom_processing 省略，不阻断后续 DOM 段。"""
        span = _base_view_span()
        view = span["attributes"]["view"]
        # 移除 first_byte，保留后续边界字段
        view.pop("first_byte")
        view.update({"dom_content_loaded": 100, "load_event": 175, "loading_time": 200})
        result = build(span, [span])
        timing = _section(result, "loading_timing")["data"]
        keys = [p["key"] for p in timing["phases"]]
        assert "dom_processing" not in keys
        assert "resource_load" in keys
        assert "page_stable" in keys

    def test_view_loading_timing_negative_loading_time_omits_total(self):
        """loading_time 为非法负值与缺失同口径，total_duration 键省略（不输出）。"""
        span = _base_view_span()
        snapshot = _view_snapshot(version=3, loading_time=-5)
        result = build(span, [span, snapshot])
        timing = _section(result, "loading_timing")["data"]
        assert "total_duration" not in timing

    def test_view_loading_timing_marker_exceeds_total_expands_axis(self):
        """标记超出总耗时时仅扩展横轴，total_duration 仍等于有效 loading_time。"""
        span = _base_view_span()
        view = span["attributes"]["view"]
        loading_time = view["loading_time"]  # 200
        ttfb = _vital_span(
            "TTFB", 500, waiting_duration=1.2, dns_duration=3.8, connection_duration=10, request_duration=83.7
        )
        result = build(span, [span, _view_snapshot(), ttfb])
        timing = _section(result, "loading_timing")["data"]
        # 标记值（500）超出 loading_time（200），但 total_duration 仅取有效 loading_time
        assert timing["total_duration"] == loading_time
        assert timing["total_duration"] != max(loading_time, ttfb["attributes"]["vital"]["value"])
        # 各 phase 按真实边界计算，不被标记拉伸
        first_byte = view["first_byte"]
        phases = {p["key"]: p for p in timing["phases"]}
        assert phases["dom_processing"]["start"] == pytest.approx(first_byte)


# ─────────────────────────────────────────────────────────────────────────────
# View 快照工具方法（方案 0x03.h：关联查询选取规则）
# ─────────────────────────────────────────────────────────────────────────────


class TestViewRelatedSpanSelection:
    def test_latest_view_snapshot_by_version_desc(self):
        """View 生命周期按 version 降序取最新一条。"""
        v1 = _view_snapshot(span_id="v1", version=1, loading_time=100)
        v3 = _view_snapshot(span_id="v3", version=3, loading_time=300)
        v2 = _view_snapshot(span_id="v2", version=2, loading_time=200)
        latest = ViewSpanBuilder._latest_view_snapshot([v1, v3, v2])
        assert latest["span_id"] == v3["span_id"]
        assert latest["attributes.view.loading_time"] == v3["attributes"]["view"]["loading_time"]

    def test_build_vital_map_takes_latest_by_end_time(self):
        """每个指标按 end_time 降序取最新一条，大小写不敏感。"""
        old = _vital_span("TTFB", 50, end_time=100)
        new = _vital_span("TTFB", 101.7, end_time=200, waiting_duration=1.2, request_duration=83.7)
        upper = _vital_span("LCP", 250, end_time=150)
        vital_map = ViewSpanBuilder._build_vital_map([old, new, upper])
        # 期望直接引用构造入参，最新 TTFB 为 new
        assert vital_map["ttfb"]["end_time"] == new["end_time"]
        assert vital_map["ttfb"]["attributes.vital.value"] == new["attributes"]["vital"]["value"]
        assert vital_map["lcp"]["end_time"] == upper["end_time"]

    def test_build_vital_map_case_insensitive_metric(self):
        snap = _vital_span("Cls", 0.05)  # 大写 metric
        vital_map = ViewSpanBuilder._build_vital_map([snap])
        assert "cls" in vital_map
        assert vital_map["cls"]["attributes.vital.value"] == snap["attributes"]["vital"]["value"]

    def test_prepare_flatten_data_mounts_vital_under_display_prefix(self):
        """vital 快照应挂到 display.vitals.{metric}，子字段带 attributes.vital 前缀。"""
        span = _base_view_span()
        ttfb = _vital_span("TTFB", 101.7, waiting_duration=1.2)
        flatten = ViewSpanBuilder._prepare_flatten_data(span, [span, _view_snapshot(), ttfb])
        # 期望引用构造入参，改样例无需同步字面量
        assert flatten[build_vital_source_key("ttfb", "attributes.vital.value")] == ttfb["attributes"]["vital"]["value"]
        assert (
            flatten[build_vital_source_key("ttfb", "attributes.vital.ttfb.waiting_duration")]
            == ttfb["attributes"]["vital"]["ttfb"]["waiting_duration"]
        )


# ─────────────────────────────────────────────────────────────────────────────
# 公共函数 build_vital_source_key
# ─────────────────────────────────────────────────────────────────────────────


class TestBuildVitalSourceKey:
    def test_key_matches_prefix_and_metric(self):
        for metric in VITAL_METRICS:
            assert build_vital_source_key(metric, "attributes.vital.value") == (
                f"{VITAL_METRIC_KEYS[metric]}.attributes.vital.value"
            )

    def test_metric_case_insensitive(self):
        assert build_vital_source_key("TTFB", "x") == build_vital_source_key("ttfb", "x")


# ─────────────────────────────────────────────────────────────────────────────
# 共享 phase（评论 4130729347：合并 View / Resource 两处重复实现）
# ─────────────────────────────────────────────────────────────────────────────


class TestPhase:
    ALIASES = {"dns": "DNS 查询", "tls": "TLS"}

    def _alias(self, key: str) -> str:
        """模拟调用方从别名表取值并以 key 兜底的通用约定。"""
        return self.ALIASES.get(key, key)

    def test_valid_phase_returns_dict_with_alias(self):
        """有效起点与时长返回 phase 字典，并取调用方传入的展示名。"""
        result = phase("dns", self._alias("dns"), 10, 5)
        assert result == {"key": "dns", "alias": "DNS 查询", "start": 10, "duration": 5}

    def test_missing_start_or_duration_omits(self):
        """起点或时长缺失整段不输出。"""
        assert phase("dns", self._alias("dns"), None, 5) is None
        assert phase("dns", self._alias("dns"), 10, None) is None

    def test_negative_duration_omits(self):
        """时长为负整段不输出，避免伪造 0 段。"""
        assert phase("dns", self._alias("dns"), 10, -1) is None

    def test_default_allows_negative_start(self):
        """默认（Resource 侧）不传 min_start，不校验负起点，负起点仍输出。"""
        result = phase("tls", self._alias("tls"), -3, 8)
        assert result == {"key": "tls", "alias": "TLS", "start": -3, "duration": 8}

    def test_min_start_zero_rejects_negative_start(self):
        """View 侧 min_start=0：负起点整段不输出，非负起点正常输出。"""
        assert phase("dns", self._alias("dns"), -3, 8, min_start=0) is None
        assert phase("dns", self._alias("dns"), 0, 8, min_start=0) == {
            "key": "dns",
            "alias": "DNS 查询",
            "start": 0,
            "duration": 8,
        }

    def test_alias_fallback_to_key(self):
        """调用方以 key 兜底时，别名回退到 key 本身。"""
        assert phase("connect", self._alias("connect"), 1, 2)["alias"] == "connect"
