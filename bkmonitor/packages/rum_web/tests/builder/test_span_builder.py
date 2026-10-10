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

    @pytest.mark.parametrize(
        "tls",
        [
            {},
            {"resource.ssl.duration": 5},
            {"resource.ssl.start": 9},
            {"resource.ssl.start": 9, "resource.ssl.duration": -5},
        ],
    )
    def test_invalid_tls_does_not_reduce_connect_duration(self, tls):
        span = _resource_span()
        span["attributes"].update({"resource.connect.start": 5, "resource.connect.duration": 10, **tls})
        timing = _section(build(span), "loading_timing")["data"]
        phases = {phase["key"]: phase for phase in timing["phases"]}
        assert "tls" not in phases
        assert phases["connect"]["duration"] == 10

    @pytest.mark.parametrize(
        "attrs", [{}, {"resource.dns.start": 2}, {"resource.dns.start": 2, "resource.dns.duration": -1}]
    )
    def test_missing_or_invalid_timings_are_omitted(self, attrs):
        span = _resource_span()
        span["attributes"].update(attrs)
        assert _section(build(span), "loading_timing") is None

    def test_reversed_boundaries_omit_invalid_phases(self):
        span = _resource_span()
        span["attributes"].update(
            {
                "resource.redirect.start": 10,
                "resource.dns.start": 5,
                "resource.dns.duration": 2,
                "resource.connect.start": 7,
                "resource.connect.duration": 1,
                "resource.ssl.start": 7,
                "resource.ssl.duration": 3,
            }
        )
        phases = {item["key"] for item in _section(build(span), "loading_timing")["data"]["phases"]}
        assert phases == {"dns", "tls"}


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
        else:
            assert config[0]["value"] == threshold
            assert config[-1] == {"rating": "poor", "alias": "差"}


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
        assert timing["milestones"][0] == {
            "key": "dom_complete",
            "field_name": "attributes.view.dom_complete",
            "value": 180,
        }

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
        assert data["ttfb"]["display.rating_config"][-1] == {"rating": "poor", "alias": "差"}

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
        assert [(marker["key"], marker["value"]) for marker in timing["markers"]] == [
            ("TTFB", 101.7),
            ("FCP", 180),
            ("LCP", 250),
        ]

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
