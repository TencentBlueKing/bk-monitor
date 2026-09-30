"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language permissions and limitations under the License.
"""

import pytest

from rum_web.handlers.builder.span import build
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
    """方案 0x04.g 的 View 主记录骨架。"""
    return {
        "span_id": span_id,
        "span_name": "view-001",
        "app_name": "test-app",
        "start_time": 1788451565200000,
        "end_time": 1788451565328000,
        "elapsed_time": 123500,
        "attributes": {
            "span_type": "view",
            "view": {
                "id": "view-001",
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


def _view_snapshot(span_id: str = "vs", version: int = 3, **overrides) -> dict:
    """同 View ID 的最新生命周期快照（含加载时序字段）。"""
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
    attributes["view"].update(overrides)
    return {
        "span_id": span_id,
        "end_time": 1788451565328000,
        "elapsed_time": 123500,
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
        "span_type,builder_attr",
        [
            ("resource", "ResourceSpanBuilder"),
            ("action", "ActionSpanBuilder"),
            ("long_task", "LongTaskSpanBuilder"),
            ("error", "ErrorSpanBuilder"),
            ("vital", "VitalSpanBuilder"),
            ("view", "ViewSpanBuilder"),
        ],
    )
    def test_build_dispatches_to_registered_builder(self, span_type, builder_attr):
        span = {"span_id": "x", "attributes": {"span_type": span_type}}
        result = build(span, [])
        # 未实现类型回落到 DefaultSpanBuilder，仍产出公共 overview
        assert "overview" in result

    def test_unknown_span_type_falls_back_to_overview(self):
        """未知类型回落到 DefaultSpanBuilder，仍保留公共头部（方案 0x03.h 兜底）。"""
        span = {"span_id": "unknown", "span_name": "n/a", "attributes": {"span_type": "websocket"}}
        result = build(span, [])
        assert result["overview"]["title"] == "n/a"
        assert result["sections"] == []

    def test_view_overview_contains_common_items(self):
        span = _base_view_span()
        result = build(span, [])
        items = {it["field_name"]: it["value"] for it in result["overview"]["items"]}
        view = span["attributes"]["view"]
        # 各字段均为源数据直接透传，引用构造对象避免与 fixture 重复硬编码
        assert items["app_name"] == span["app_name"]
        assert items["attributes.view.url_template"] == view["url_template"]
        assert items["attributes.view.previous_url_template"] == view["previous_url_template"]
        assert items["attributes.session.id"] == span["attributes"]["session"]["id"]
        assert items["attributes.view.id"] == view["id"]
        assert items["start_time"] == span["start_time"]
        assert items["end_time"] == span["end_time"]
        assert items["attributes.user.id"] == span["attributes"]["user"]["id"]
        assert items["resource.deployment.environment.name"] == span["resource"]["deployment"]["environment"]["name"]


# ─────────────────────────────────────────────────────────────────────────────
# Resource（方案 0x04.b）
# ─────────────────────────────────────────────────────────────────────────────


class TestResourceSpanBuilder:
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
                "resource.connect.duration": 14,
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

    def test_others_loading_timing_has_resource_info(self):
        span = _resource_span("img")
        result = build(span, [])
        assert _section(result, "resource_info") is not None
        # 跨域资源无时序字段，整段加载时序省略（与「耗时为 0」区分）
        assert _section(result, "loading_timing") is None


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
            "start_time": 1788451565200000,
            "end_time": 1788451565327840,
            "elapsed_time": 2840,
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
        # value 来自 vital.value，而非Span elapsed_time（虽此处巧合相等，但语义来源不同）
        assert rating["attributes.vital.value"] == vital["value"]
        # 评级配置末项省略 value（领域约定，保留字）
        config = rating["display.rating_config"]
        assert config[-1]["rating"] == "poor"
        assert "value" not in config[-1]

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
    def test_view_stay_duration_uses_navigation_start(self):
        """停留时长 = (end_time - start_time) / 1000，start_time 取导航开始时间不随快照更新。"""
        span = _base_view_span()
        # 快照 end_time 与主记录不一致，应沿用主记录 start_time（导航开始）
        result = build(span, [span, _view_snapshot(version=3, loading_time=999, end_time=1788451565999999)])
        duration = _section(result, "key_info")["data"]["duration"]["display.view.duration"]
        # 期望从主记录起止时间推导，而非写死字面量；改样例仅需改构造器
        expected = (span["end_time"] - span["start_time"]) / 1000
        assert duration == pytest.approx(expected)

    def test_view_snapshot_overrides_loading_fields_but_not_start_time(self):
        """快照只补齐 VIEW_SNAPSHOT_FIELDS，start_time 保持主记录导航时间。"""
        span = _base_view_span()
        snapshot = _view_snapshot(version=3, loading_time=333, first_byte=120, dom_content_loaded=160, load_event=200)
        result = ViewSpanBuilder._prepare_flatten_data(span, [span, snapshot])
        assert result["start_time"] == span["start_time"]
        assert result["attributes.view.loading_time"] == 333
        assert result["attributes.view.first_byte"] == 120
        # VIEW_SNAPSHOT_FIELDS 之外字段不被快照覆盖
        assert result["span_name"] == "view-001"

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

        result = build(span, [span, _view_snapshot(), ttfb])
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
        # 仅注入的 TTFB 有值，FCP/LCP 缺失指标不补造
        assert markers == {"TTFB": ttfb_value}

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

    def test_view_vital_missing_metric_not_fabricated(self):
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
        """标记超出总耗时时仅扩展横轴，不改各 phase 时长。"""
        span = _base_view_span()
        view = span["attributes"]["view"]
        loading_time = view["loading_time"]  # 200
        ttfb = _vital_span(
            "TTFB", 500, waiting_duration=1.2, dns_duration=3.8, connection_duration=10, request_duration=83.7
        )
        result = build(span, [span, _view_snapshot(), ttfb])
        timing = _section(result, "loading_timing")["data"]
        # 标记值（500）超出 loading_time（200），横轴扩展为两者较大值
        assert timing["total_duration"] == max(loading_time, ttfb["attributes"]["vital"]["value"])
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
