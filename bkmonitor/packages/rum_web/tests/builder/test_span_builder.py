"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from copy import deepcopy

import pytest

from rum_web.handlers.builder.span import build


REPORT_TIME = 1788451565500000
NAVIGATION_TIME = 1788451565200


def _span(span_type, attrs=None, **root):
    return {
        "span_id": "span-001",
        "span_name": span_type,
        "app_name": "test-app",
        "start_time": REPORT_TIME,
        "end_time": REPORT_TIME,
        "elapsed_time": 0,
        "resource": {"deployment": {"environment": {"name": "prod"}}},
        **root,
        "attributes": {
            "span_type": span_type,
            "session.id": "sess-001",
            "view.id": "view-001",
            "view.url_template": "/order/submit",
            "user.id": "user-001",
            **(attrs or {}),
        },
    }


def _base_view_span(**attrs):
    return _span(
        "view",
        {
            "view.started_at": NAVIGATION_TIME,
            "view.previous_url_template": "/product/:id/",
            "view.loading_time": 200,
            "view.loading_time_source": "auto",
            "view.loading_type": "initial_load",
            "view.first_byte": 101.7,
            "view.dom_content_loaded": 140,
            "view.load_event": 175,
            "view.version": 1,
            **attrs,
        },
    )


def _view_snapshot(version=3, end_time=1788451565999999, started_at=NAVIGATION_TIME, **attrs):
    return _span(
        "view",
        {"view.version": version, "view.started_at": started_at, **attrs},
        span_id=f"view-{version}",
        start_time=end_time,
        end_time=end_time,
    )


def _vital_span(metric, value, end_time=1788451565328000, **ttfb):
    return _span(
        "vital",
        {"vital.metric": metric, "vital.value": value, **{f"vital.ttfb.{key}": value for key, value in ttfb.items()}},
        span_id=f"vital-{metric}",
        start_time=end_time,
        end_time=end_time,
    )


def _resource_span(resource_type="xhr"):
    return _span(
        "resource",
        {
            "resource.type": resource_type,
            "http.request.method": "POST",
            "http.response.status_code": 200,
            "url.template": "/api/orders",
            "url.full": "https://example.com/api/orders",
            "server.address": "example.com",
            "outcome.type": "success",
        },
        span_name="POST /api/orders",
        start_time=1788451565200000,
        end_time=1788451565328000,
        elapsed_time=128000,
    )


def _section(result, key):
    return next((section for section in result["sections"] if section["key"] == key), None)


def _items(result, name="items"):
    return {item["field_name"]: item["value"] for item in result["overview"][name]}


def _assert_hover(hover, *, optional=()):
    assert {"title", "description"} <= hover.keys()
    assert hover["title"]
    assert hover["description"]
    assert set(hover) <= {"title", "description", "user_experience", "source"}
    if "source" in hover:
        assert set(hover["source"]) == {"label", "url"}
        assert hover["source"]["label"]
        assert hover["source"]["url"].startswith("https://")
    for key in optional:
        assert key not in hover


def _assert_no_calculation_fields(value):
    if isinstance(value, dict):
        assert not {"formula", "calculation"} & value.keys()
        for child in value.values():
            _assert_no_calculation_fields(child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_calculation_fields(child)


class TestSpanBuilderDispatch:
    @pytest.mark.parametrize(
        "span_type,display,sections",
        [
            ("resource", "Resource", ["key_info", "resource_info"]),
            ("action", "Action", ["key_info"]),
            ("long_task", "Long Task", ["key_info"]),
            ("error", "Error", ["key_info"]),
            ("vital", "Web Vital", ["vital_rating"]),
            ("view", "View", ["key_info", "web_vitals"]),
            ("websocket", "WebSocket", []),
            ("unknown", "unknown", []),
        ],
    )
    def test_dispatch_and_common_overview(self, span_type, display, sections):
        span = _span(span_type)
        before = deepcopy(span)
        result = build(span)
        items = _items(result)
        assert result["span_id"] == "span-001"
        assert result["origin_data"] is span
        assert span == before
        assert items["display.span_type"] == display
        assert items["app_name"] == "test-app"
        assert items["attributes.session.id"] == "sess-001"
        assert items["attributes.view.id"] == "view-001"
        assert items["attributes.user.id"] == "user-001"
        assert items["resource.deployment.environment.name"] == "prod"
        assert [section["key"] for section in result["sections"]] == sections

    @pytest.mark.parametrize("span", [{}, {"attributes": None}, {"attributes": {}}])
    def test_missing_attributes_keeps_default_overview(self, span):
        result = build(span)
        assert result["sections"] == []
        assert _items(result)["display.span_type"] == ""

    @pytest.mark.parametrize(
        "attributes",
        [
            {"span_type": "resource", "resource.type": "fetch"},
            {"span_type": "resource", "resource": {"type": "fetch"}},
        ],
    )
    def test_resource_dispatch_accepts_both_attribute_shapes(self, attributes):
        result = build({"span_id": "fetch", "attributes": attributes})
        assert _items(result)["display.span_type"] == "Resource(fetch)"
        assert "request" in _section(result, "key_info")["data"]
        assert _section(result, "resource_info") is None

    def test_dispatch_accepts_flat_record(self):
        result = build({"attributes.span_type": "resource", "attributes.resource.type": "xhr"})
        assert "request" in _section(result, "key_info")["data"]

    def test_view_overview_includes_previous_url(self):
        result = build(_base_view_span())
        assert _items(result)["attributes.view.previous_url_template"] == "/product/:id/"
        fields = [item["field_name"] for item in result["overview"]["items"]]
        assert fields[fields.index("attributes.view.url_template") + 1] == "attributes.view.previous_url_template"


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

    def test_others_loading_timing_has_resource_info(self):
        span = _resource_span("img")
        result = build(span, [])
        assert _section(result, "resource_info") is not None
        # 新旧时序字段均未上报时，整段加载时序省略。
        assert _section(result, "loading_timing") is None


# E 类基线：重定向 + DNS + TCP + TLS，时间点相对 timeOrigin
NETWORK_TIMING = {
    "start_time": 100,
    "redirect_start": 100,
    "redirect_end": 110,
    "fetch_start": 112,
    "domain_lookup_start": 115,
    "domain_lookup_end": 120,
    "connect_start": 120,
    "secure_connection_start": 128,
    "connect_end": 135,
    "request_start": 136,
    "response_start": 180,
    "response_end": 200,
}


def _timing_span(timing, resource_type="script", **attrs):
    span = _resource_span(resource_type)
    span["attributes"].update(
        {
            **{f"resource.timing.{key}": value for key, value in timing.items()},
            "resource.decoded_body_size": 1000,
            "resource.transfer_size": 300,
            **attrs,
        }
    )
    return span


def _timing(span):
    section = _section(build(span), "loading_timing")
    return section and section["data"]


def _phases(data):
    return [(item["key"], item["start"], item["duration"]) for item in data["phases"]]


class TestResourceLoadingTiming:
    @pytest.mark.parametrize("resource_type", ["xhr", "fetch", "img"])
    def test_legacy_phases(self, resource_type):
        span = _resource_span(resource_type)
        span["attributes"].update(
            {
                "resource.redirect.start": 0,
                "resource.dns.start": 2,
                "resource.dns.duration": 3,
                "resource.connect.start": 5,
                "resource.connect.duration": 10,
                "resource.ssl.start": 9,
                "resource.ssl.duration": 6,
                "resource.first_byte.start": 15,
                "resource.first_byte.duration": 85,
                "resource.download.start": 100,
                "resource.download.duration": 28,
            }
        )
        data = _timing(span)
        assert data["unit"] == "ms"
        assert data["total_duration"] == 128
        assert _phases(data) == [
            ("prepare", 0, 2),
            ("dns", 2, 3),
            ("connect", 5, 4),
            ("tls", 9, 6),
            ("first_byte", 15, 85),
            ("download", 100, 28),
        ]
        for item in data["phases"]:
            _assert_hover(item["hover"])

    @pytest.mark.parametrize("timing", [{}, {"start_time": 1000}, {"response_end": 1200}])
    def test_missing_new_boundaries_use_legacy_offsets(self, timing):
        data = _timing(_timing_span(timing, **{"resource.download.start": 80, "resource.download.duration": 20}))
        assert _phases(data) == [("download", 80, 20)]
        assert data["total_duration"] == 100

    @pytest.mark.parametrize("end", [100, 90])
    def test_invalid_new_interval_does_not_fall_back(self, end):
        span = _timing_span(
            {"start_time": 100, "response_end": end},
            **{"resource.download.start": 80, "resource.download.duration": 20},
        )
        assert _timing(span) is None

    def test_new_timing_takes_precedence_over_legacy_fields(self):
        data = _timing(
            _timing_span(NETWORK_TIMING, **{"resource.download.start": 1, "resource.download.duration": 999})
        )
        assert data["total_duration"] == 100
        assert _phases(data)[-1] == ("download", 80, 20)

    def test_network_phases(self):
        data = _timing(_timing_span(NETWORK_TIMING))
        assert data["unit"] == "ms"
        assert data["total_duration"] == 100
        assert _phases(data) == [
            ("redirect", 0, 10),
            ("prepare", 10, 5),
            ("dns", 15, 5),
            ("connect", 20, 8),
            ("tls", 28, 7),
            ("first_byte", 35, 45),
            ("download", 80, 20),
        ]
        assert all(item["alias"] for item in data["phases"])
        _assert_hover(data["phases"][1]["hover"])
        _assert_no_calculation_fields(data)

    def test_network_optional_phases_are_omitted(self):
        """无重定向从 start_time 起算发起前等待；DNS 缓存、无 TLS 时不画对应阶段。"""
        timing = {
            **NETWORK_TIMING,
            "redirect_start": 0,
            "redirect_end": 0,
            "domain_lookup_start": 115,
            "domain_lookup_end": 115,
            "secure_connection_start": 0,
        }
        data = _timing(_timing_span(timing))
        assert _phases(data) == [
            ("prepare", 0, 15),
            ("connect", 20, 15),
            ("first_byte", 35, 45),
            ("download", 80, 20),
        ]

    def test_network_prepare_includes_wait_before_dns(self):
        timing = {
            "start_time": 100,
            "fetch_start": 100,
            "domain_lookup_start": 600,
            "domain_lookup_end": 610,
            "connect_start": 610,
            "connect_end": 630,
            "request_start": 630,
            "response_start": 680,
            "response_end": 700,
        }
        data = _timing(_timing_span(timing))
        assert _phases(data) == [
            ("prepare", 0, 500),
            ("dns", 500, 10),
            ("connect", 510, 20),
            ("first_byte", 530, 50),
            ("download", 580, 20),
        ]
        assert sum(duration for _, _, duration in _phases(data)) == data["total_duration"] == 600

    @pytest.mark.parametrize(
        "tls_start,connection",
        [
            (0, [("connect", 10, 10)]),
            (5, [("connect", 10, 10)]),
            (15, [("connect", 10, 5), ("tls", 15, 5)]),
            (20, [("connect", 10, 10)]),
            (25, [("connect", 10, 10)]),
        ],
    )
    def test_network_tls_with_zero_resource_start(self, tls_start, connection):
        timing = {
            "start_time": 0,
            "fetch_start": 0,
            "domain_lookup_start": 0,
            "domain_lookup_end": 10,
            "connect_start": 10,
            "secure_connection_start": tls_start,
            "connect_end": 20,
            "request_start": 20,
            "response_start": 30,
            "response_end": 40,
        }
        data = _timing(_timing_span(timing))
        assert _phases(data) == [
            ("dns", 0, 10),
            *connection,
            ("first_byte", 20, 10),
            ("download", 30, 10),
        ]
        assert sum(duration for _, _, duration in _phases(data)) == data["total_duration"] == 40

    def test_clamped_tls_start_is_not_a_handshake(self):
        """secureConnectionStart 被钳到 fetchStart 时，不画 TLS，连接建立计算到 connectEnd。"""
        data = _timing(_timing_span({**NETWORK_TIMING, "secure_connection_start": 112}))
        phases = {key: (start, duration) for key, start, duration in _phases(data)}
        assert "tls" not in phases
        assert phases["connect"] == (20, 15)

    def test_reused_connection_outputs_zero_phases(self):
        """D 类：DNS/连接建立/TLS 以 0 耗时输出在 connect_end，前端合并为连接复用提示。"""
        timing = {
            **NETWORK_TIMING,
            "domain_lookup_start": 115,
            "domain_lookup_end": 115,
            "connect_start": 115,
            "secure_connection_start": 112,
            "connect_end": 115,
        }
        data = _timing(_timing_span(timing))
        assert _phases(data) == [
            ("redirect", 0, 10),
            ("prepare", 10, 5),
            ("dns", 15, 0),
            ("connect", 15, 0),
            ("tls", 15, 0),
            ("first_byte", 15, 65),
            ("download", 80, 20),
        ]

    def test_cross_origin_only_total(self):
        timing = {"start_time": 100, "fetch_start": 100, "response_end": 200}
        data = _timing(_timing_span(timing, **{"resource.decoded_body_size": 0, "resource.transfer_size": 0}))
        assert _phases(data) == [("total", 0, 100)]
        assert data["total_duration"] == 100

    @pytest.mark.parametrize(
        "attrs,timing",
        [
            ({"resource.delivery_type": "cache", "resource.transfer_size": 0}, {}),
            ({"resource.transfer_size": 0}, {}),
            ({}, {"worker_start": 101, "worker_final_router_source": "cache"}),
        ],
        ids=["browser-cache", "inferred-cache", "sw-static-router-cache"],
    )
    def test_local_response(self, attrs, timing):
        points = {
            "start_time": 100,
            "fetch_start": 102,
            "domain_lookup_start": 102,
            "domain_lookup_end": 102,
            "connect_start": 102,
            "connect_end": 102,
            "request_start": 102,
            "response_start": 103,
            "response_end": 110,
            **timing,
        }
        data = _timing(_timing_span(points, **attrs))
        assert _phases(data) == [("prepare", 0, 2), ("first_byte", 2, 1), ("download", 3, 7)]

    def test_missing_transfer_size_is_not_cache(self):
        """未上报 transfer_size 的复用连接请求不能被推断为缓存命中。"""
        points = {
            "start_time": 100,
            "fetch_start": 102,
            "domain_lookup_start": 102,
            "domain_lookup_end": 102,
            "connect_start": 102,
            "connect_end": 102,
            "request_start": 102,
            "response_start": 150,
            "response_end": 160,
        }
        span = _timing_span(points)
        del span["attributes"]["resource.transfer_size"]
        assert _phases(_timing(span)) == [
            ("prepare", 0, 2),
            ("dns", 2, 0),
            ("connect", 2, 0),
            ("tls", 2, 0),
            ("first_byte", 2, 48),
            ("download", 50, 10),
        ]

    def test_service_worker_phases(self):
        points = {
            "start_time": 100,
            "worker_start": 105,
            "fetch_start": 110,
            "request_start": 111,
            "response_start": 150,
            "response_end": 170,
        }
        data = _timing(_timing_span(points, **{"resource.timing.worker_matched_router_source": "fetch-event"}))
        assert _phases(data) == [
            ("queueing", 0, 5),
            ("sw_startup", 5, 5),
            ("sw_request", 10, 1),
            ("sw_respond_with", 11, 39),
            ("first_byte", 11, 39),
            ("download", 50, 20),
        ]

    def test_service_worker_without_request_and_response_start(self):
        """requestStart/responseStart 为 0：起点改用 fetchStart，respondWith 与内容下载改用 responseEnd。"""
        points = {"start_time": 100, "worker_start": 105, "fetch_start": 110, "response_end": 170}
        data = _timing(_timing_span(points))
        assert _phases(data) == [
            ("queueing", 0, 5),
            ("sw_startup", 5, 5),
            ("sw_respond_with", 10, 60),
            ("download", 10, 60),
        ]

    def test_service_worker_start_after_fetch_only_drops_startup(self):
        points = {"start_time": 100, "worker_start": 112, "fetch_start": 110, "response_end": 170}
        keys = [key for key, _, _ in _phases(_timing(_timing_span(points)))]
        assert "sw_startup" not in keys
        assert keys[0] == "queueing"

    def test_unmatched_falls_back_to_total(self):
        """有时间点但不满足任何类型（如 connect 缺失且非缓存）时只画总耗时。"""
        points = {
            "start_time": 100,
            "fetch_start": 102,
            "request_start": 103,
            "response_start": 150,
            "response_end": 160,
        }
        data = _timing(_timing_span(points))
        assert _phases(data) == [("total", 0, 60)]

    def test_reversed_points_drop_only_invalid_phases(self):
        data = _timing(
            _timing_span({**NETWORK_TIMING, "domain_lookup_end": 113, "response_start": 140, "response_end": 130})
        )
        keys = [key for key, _, _ in _phases(data)]
        assert "dns" not in keys
        assert "download" not in keys
        assert all(duration > 0 for _, _, duration in _phases(data))
        assert "total_duration" in data

    @pytest.mark.parametrize(
        "timing",
        [
            {},
            {"start_time": 100},
            {"response_end": 200},
            {"start_time": 100, "response_end": 100, "fetch_start": 100},
            {"start_time": "invalid", "response_end": 200},
        ],
        ids=["missing", "missing-end", "missing-start", "zero-total", "invalid-start"],
    )
    def test_without_valid_timing_section_is_omitted(self, timing):
        span = _timing_span(timing, **{"resource.decoded_body_size": 0})
        assert _timing(span) is None


class TestInteractionBuilders:
    def test_action_key_info(self):
        result = build(
            _span(
                "action",
                {
                    "action.type": "click",
                    "action.target.name": ".submit-btn",
                    "action.target.tag": "button",
                    "outcome.type": "success",
                },
                elapsed_time=432000,
            )
        )
        assert _section(result, "key_info")["data"] == {
            "interaction": {"attributes.action.type": "click"},
            "target": {"attributes.action.target.name": ".submit-btn", "attributes.action.target.tag": "button"},
        }
        assert _items(result, "badges")["elapsed_time"] == 432000

    def test_longtask_key_info(self):
        result = build(
            _span(
                "long_task",
                {
                    "long_task.blocking_duration": 42.5,
                    "action.id": "act-1",
                    "long_task.entry_type": "longtask",
                    "long_task.name": "self",
                },
                elapsed_time=123500,
            )
        )
        assert _section(result, "key_info")["data"] == {
            "duration": {"elapsed_time": 123500, "attributes.long_task.blocking_duration": 42.5},
            "action": {"attributes.action.id": "act-1"},
            "attribution": {"attributes.long_task.entry_type": "longtask", "attributes.long_task.name": "self"},
        }

    @pytest.mark.parametrize(
        "types,expected", [([], None), (["TypeError"], "TypeError"), (["TypeError", "RangeError"], "TypeError")]
    )
    def test_error_exception_type_and_badges(self, types, expected):
        span = _span(
            "error",
            {"outcome.type": "failure", "code.filepath": "app.js", "code.lineno": 9, "code.column": 12},
            events=[{"name": "exception", "attributes": {"exception.type": value}} for value in types],
        )
        result = build(span)
        assert _items(result, "badges") == {"attributes.outcome.type": "failure"}
        assert _section(result, "key_info")["data"] == {
            "error_type": {"events.attributes.exception.type": expected},
            "source": {"attributes.code.filepath": "app.js", "attributes.code.lineno": 9, "attributes.code.column": 12},
        }
        assert result["origin_data"]["events"] == span["events"]


class TestVitalSpanBuilder:
    @pytest.mark.parametrize(
        "metric,value,rating,alias,threshold",
        [
            ("LCP", 2500, "good", "良好", 2500),
            ("LCP", 2840, "needs_improvement", "需改进", 2500),
            ("LCP", 9000, "poor", "差", 2500),
            ("LCP", None, None, None, 2500),
            ("LCP", "invalid", None, None, 2500),
            ("cls", 0.2, "needs_improvement", "需改进", 0.1),
            ("unknown", 1, None, None, None),
        ],
    )
    def test_badges_show_metric_value_and_rating(self, metric, value, rating, alias, threshold):
        result = build(_vital_span(metric, value))
        badges = result["overview"]["badges"]
        assert badges == [
            {"field_name": "attributes.vital.value", "value": value},
            {"field_name": "display.rating_level", "value": rating, "alias": alias},
        ]
        data = _section(result, "vital_rating")["data"]
        assert data["attributes.vital.metric"] == metric
        assert data["attributes.vital.value"] == value
        config = data["display.rating_config"]
        if threshold is None:
            assert config == []
            assert "hover" not in data
        else:
            assert config[0]["value"] == threshold
            assert config[-1]["rating"] == "poor"
            assert config[-1]["alias"] == "差"
            _assert_hover(data["hover"])
            _assert_hover(config[0]["hover"], optional=("user_experience", "source"))
            _assert_no_calculation_fields(data)


class TestViewSpanBuilder:
    @pytest.mark.parametrize("selected", [0, 1, 2], ids=["start", "update", "end"])
    def test_stay_duration_is_independent_of_selected_snapshot(self, selected):
        snapshots = [
            _view_snapshot(version=1, end_time=1788451565200000, **{"view.phase": "start"}),
            _view_snapshot(version=2, end_time=1788451565909200, **{"view.phase": "update"}),
            _view_snapshot(version=3, end_time=1788451576648200, **{"view.phase": "end"}),
        ]
        before = deepcopy(snapshots)
        main = snapshots[selected]
        result = build(main, [snapshots[2], snapshots[0], snapshots[1]])
        assert _items(result)["start_time"] == 1788451565200000
        assert _items(result)["end_time"] == 1788451576648200
        assert _items(result, "badges") == {"display.view.duration": pytest.approx(11448.2)}
        assert _section(result, "key_info")["data"]["duration"]["display.view.duration"] == pytest.approx(11448.2)
        assert result["origin_data"] is main
        assert snapshots == before

    @pytest.mark.parametrize(
        "snapshot_start,main_start,expected",
        [
            (100, 50, 100000),
            (100.125, 50, 100125),
            (None, 50, 50000),
            (0, 50, 50000),
            ("invalid", 50, 50000),
            ("NaN", 50, 50000),
            ("Infinity", 50, 50000),
            ("-Infinity", 50, 50000),
            (None, None, REPORT_TIME),
            ("NaN", "NaN", REPORT_TIME),
            (None, "Infinity", REPORT_TIME),
            (None, "-Infinity", REPORT_TIME),
        ],
    )
    def test_navigation_start_fallback(self, snapshot_start, main_start, expected):
        main = _base_view_span(**{"view.started_at": main_start})
        result = build(main, [_view_snapshot(started_at=snapshot_start)])
        assert _items(result)["start_time"] == expected
        duration = (1788451565999999 - expected) / 1000
        assert _items(result, "badges")["display.view.duration"] == pytest.approx(duration)
        assert _section(result, "key_info")["data"]["duration"]["display.view.duration"] == pytest.approx(duration)

    @pytest.mark.parametrize("started_at,expected", [(NAVIGATION_TIME, 300), (None, 0), ("NaN", 0), ("Infinity", 0)])
    def test_duration_without_related_results(self, started_at, expected):
        result = build(_base_view_span(**{"view.started_at": started_at}))
        assert _items(result, "badges")["display.view.duration"] == expected

    def test_missing_root_start_does_not_fabricate_duration(self):
        span = _base_view_span(**{"view.started_at": None})
        del span["start_time"]
        result = build(span)
        assert _items(result, "badges")["display.view.duration"] is None
        assert _section(result, "key_info")["data"]["duration"]["display.view.duration"] is None

    def test_latest_view_version_overrides_display_fields(self):
        main = _base_view_span()
        old = _view_snapshot(version=1, end_time=REPORT_TIME + 1000, **{"view.loading_time": 300})
        newest = _view_snapshot(
            version=5,
            end_time=REPORT_TIME + 2000,
            **{
                "view.loading_time": 333,
                "view.first_byte": 120,
                "view.dom_content_loaded": 160,
                "view.load_event": 200,
                "view.dom_complete": 180,
            },
        )
        result = build(main, [newest, old])
        assert result["overview"]["title"] == "view"
        assert _items(result)["end_time"] == REPORT_TIME + 2000
        loading = _section(result, "key_info")["data"]["loading"]
        assert loading["attributes.view.loading_time"] == 333
        assert loading["attributes.view.first_byte"] == 120
        timing = _section(result, "loading_timing")["data"]
        milestone = timing["milestones"][0]
        assert milestone["key"] == "dom_complete"
        assert milestone["field_name"] == "attributes.view.dom_complete"
        assert milestone["value"] == 180
        _assert_hover(milestone["hover"])

    def test_latest_vitals_are_selected_case_insensitively(self):
        related = [
            _vital_span("LCP", 1000, end_time=1),
            _vital_span("lcp", 2840, end_time=2),
            _vital_span(
                "TTFB", 101.7, waiting_duration=1.2, dns_duration=3.8, connection_duration=10, request_duration=83.7
            ),
            _vital_span("FCP", 180),
            _vital_span("INP", 230),
            _vital_span("CLS", 0.2),
        ]
        data = _section(build(_base_view_span(), related), "web_vitals")["data"]
        assert list(data) == ["ttfb", "fcp", "lcp", "inp", "cls"]
        assert data["lcp"]["attributes.vital.value"] == 2840
        assert data["ttfb"]["attributes.vital.ttfb.waiting_duration"] == 1.2
        assert data["cls"]["attributes.vital.value"] == 0.2
        assert data["ttfb"]["display.rating_config"][-1]["rating"] == "poor"
        for metric in ("ttfb", "fcp", "lcp", "inp", "cls"):
            _assert_hover(data[metric]["hover"])
            for config in data[metric]["display.rating_config"]:
                _assert_hover(config["hover"], optional=("user_experience", "source"))
        assert data["lcp"]["hover"] == _section(build(_vital_span("lcp", 2840)), "vital_rating")["data"]["hover"]
        _assert_no_calculation_fields(data)

    def test_related_spans_are_flattened_once(self, mocker):
        from bkmonitor.data_source.format import flatten_dict_data

        flatten = mocker.patch("rum_web.handlers.builder.span.view.flatten_dict_data", wraps=flatten_dict_data)
        related = [_view_snapshot(), _vital_span("LCP", 2500)]
        build(_base_view_span(), related)
        for span in related:
            assert sum(call.args[0] is span for call in flatten.call_args_list) == 1

    def test_loading_waterfall_phases_and_markers(self):
        vital = _vital_span(
            "TTFB", 101.7, waiting_duration=1.2, dns_duration=3.8, connection_duration=10, request_duration=83.7
        )
        result = build(_base_view_span(), [vital, _vital_span("FCP", 180), _vital_span("LCP", 250)])
        timing = _section(result, "loading_timing")["data"]
        assert timing["unit"] == "ms"
        assert timing["total_duration"] == 200
        expected = [
            ("prepare", 0, 1.2),
            ("dns", 4.2, 3.8),
            ("connect", 8, 10),
            ("first_byte", 18, 83.7),
            ("dom_processing", 101.7, 38.3),
            ("resource_load", 140, 35),
            ("page_stable", 175, 25),
        ]
        assert [item["key"] for item in timing["phases"]] == [key for key, _, _ in expected]
        for item, (_, start, duration) in zip(timing["phases"], expected):
            assert item["start"] == pytest.approx(start)
            assert item["duration"] == pytest.approx(duration)
            assert item["alias"]
            _assert_hover(item["hover"])
        assert [(marker["key"], marker["value"]) for marker in timing["markers"]] == [
            ("TTFB", 101.7),
            ("FCP", 180),
            ("LCP", 250),
        ]
        for marker in timing["markers"]:
            _assert_hover(marker["hover"])
        assert timing["markers"][0]["hover"] == _section(result, "web_vitals")["data"]["ttfb"]["hover"]
        for milestone in timing["milestones"]:
            _assert_hover(milestone["hover"])
        _assert_no_calculation_fields(timing)

    @pytest.mark.parametrize(
        "source,loading,load_event,stable",
        [
            ("auto", 608.800048828125, 608.7999999523163, pytest.approx(0, abs=0.001)),
            ("auto", 608.7999999523163, 608.800048828125, 0),
            ("auto", 200, 175, 25),
            ("manual", 200, 175, None),
        ],
    )
    def test_page_stable_handles_source_and_rounding(self, source, loading, load_event, stable):
        result = build(
            _base_view_span(
                **{"view.loading_time_source": source, "view.loading_time": loading, "view.load_event": load_event}
            )
        )
        data = _section(result, "loading_timing")["data"]
        phases = {phase["key"]: phase for phase in data["phases"]}
        if stable is None:
            assert "page_stable" not in phases
            assert "page_stable" not in [item["key"] for item in data["milestones"]]
        else:
            assert phases["page_stable"]["duration"] == stable
            assert data["milestones"][-1]["key"] == "page_stable"

    @pytest.mark.parametrize("loading", [None, "invalid", -5, 0, 200])
    def test_total_duration_depends_only_on_loading_time(self, loading):
        result = build(_base_view_span(**{"view.loading_time": loading}), [_vital_span("LCP", 500)])
        timing = _section(result, "loading_timing")["data"]
        if loading is None or loading == "invalid" or loading < 0:
            assert "total_duration" not in timing
        else:
            assert timing["total_duration"] == loading
        assert timing["markers"][0]["value"] == 500

    @pytest.mark.parametrize(
        "attrs,omitted",
        [
            ({"view.first_byte": 140, "view.dom_content_loaded": 100}, "dom_processing"),
            ({"view.first_byte": None}, "dom_processing"),
            ({"view.first_byte": -1}, "dom_processing"),
            ({"view.dom_content_loaded": 200, "view.load_event": 175}, "resource_load"),
        ],
    )
    def test_invalid_phase_boundaries_are_omitted(self, attrs, omitted):
        data = _section(build(_base_view_span(**attrs)), "loading_timing")["data"]
        assert omitted not in [phase["key"] for phase in data["phases"]]

    @pytest.mark.parametrize("loading_type", ["route_change", "activity", None])
    def test_non_initial_load_omits_waterfall(self, loading_type):
        assert _section(build(_base_view_span(**{"view.loading_type": loading_type})), "loading_timing") is None

    def test_missing_milestones_and_vitals_are_not_fabricated(self):
        result = build(_base_view_span(**{"view.load_event": None, "view.loading_time": None}))
        data = _section(result, "loading_timing")["data"]
        assert data["markers"] == []
        assert data["milestones"] == []
        assert [phase["key"] for phase in data["phases"]] == ["dom_processing"]
        assert _section(result, "web_vitals")["data"]["lcp"]["attributes.vital.value"] is None
