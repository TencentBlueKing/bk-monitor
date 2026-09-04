"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest

from semconv.constants import SpanKind, SpanStatusCode
from semconv.rum.constants import (
    RumSpanType,
    SdkLanguage,
    VitalMetric,
    OutcomeType,
    NetworkStatus,
    NetworkConnectionType,
)
from semconv.rum.attributes import (
    common_attributes,
    error_attributes,
    device_attributes,
    vital_attributes,
    virtual_attributes,
    http_attributes,
)
from semconv.rum.field import FieldSpec, RatingLevel
from semconv.rum.registry import FieldRegistry
from semconv.rum.trace import SpanSpec
from semconv.rum.trace.status import Status


class TestRatingLevel:
    """RatingLevel 基础行为测试。"""

    def test_frozen_immutable(self):
        """RatingLevel 为 frozen dataclass，不可修改。"""
        level = RatingLevel(rating="good", value=2500)
        with pytest.raises((AttributeError, TypeError)):
            level.rating = "poor"  # type: ignore[misc]

    def test_poor_level_no_value(self):
        """末项省略 value 并兜底。"""
        level = RatingLevel(rating="poor")
        assert level.value is None

    def test_equality(self):
        """相同参数的 RatingLevel 相等。"""
        a = RatingLevel(rating="good", value=2500)
        b = RatingLevel(rating="good", value=2500)
        assert a == b


class TestFieldSpec:
    """FieldSpec 基础行为测试。"""

    def test_default_alias_is_empty(self):
        """原子字段不含结构前缀，field_alias 默认空串。"""
        spec = FieldSpec(field_name="foo")
        assert spec.field_alias == ""

    def test_default_display_type_is_none(self):
        """field_display_type 默认为 None。"""
        spec = FieldSpec(field_name="foo")
        assert spec.field_display_type is None

    def test_default_rating_config_is_empty(self):
        """rating_config 默认为空元组。"""
        spec = FieldSpec(field_name="foo")
        assert spec.rating_config == ()

    def test_frozen_immutable(self):
        """FieldSpec 为 frozen dataclass，不可修改。"""
        spec = FieldSpec(field_name="foo")
        with pytest.raises((AttributeError, TypeError)):
            spec.field_name = "bar"  # type: ignore[misc]

    def test_children_only_uppercase_fieldspec(self):
        """children() 只返回大写类属性中的 FieldSpec 实例。"""
        children = list(SpanSpec.KIND.children())
        assert children == []

    def test_children_composite(self):
        """复合字段的 children() 返回直接子字段。"""
        children = list(Status(field_name="status").children())
        assert Status.CODE in children
        assert Status.MESSAGE in children


class TestFieldRegistry:
    """FieldRegistry 注册与查找行为测试。"""

    def test_duplicate_path_raises(self):
        """重复路径注册时明确失败。"""

        class DupSpec(FieldSpec):
            A = FieldSpec(field_name="x")
            B = FieldSpec(field_name="x")

        with pytest.raises(ValueError, match="重复注册"):
            FieldRegistry(DupSpec(field_name=""))

    def test_unknown_field_returns_bare_spec(self):
        """未注册路径返回仅含原始字段名的 FieldSpec。"""
        result = SpanSpec.from_field("xxx.unknown")
        assert result == FieldSpec("xxx.unknown")
        assert result.field_alias == ""

    def test_unknown_field_is_not_cached(self):
        """未注册路径每次返回新对象（不共享引用）。"""
        a = SpanSpec.from_field("not_exist")
        b = SpanSpec.from_field("not_exist")
        assert a == b
        assert a is not b

    def test_known_field_returns_bound_spec(self):
        """已注册路径返回 bound spec，get_full_field_name() 返回完整路径。"""
        spec = SpanSpec.from_field("attributes.span_type")
        assert spec.get_full_field_name() == "attributes.span_type"
        # bound spec 是新对象，不与原始 FieldSpec 实例共享引用
        assert spec is not SpanSpec.ATTRIBUTES.SPAN_TYPE
        # 但字段语义相同
        assert spec.field_name == SpanSpec.ATTRIBUTES.SPAN_TYPE.field_name
        assert spec.field_alias == SpanSpec.ATTRIBUTES.SPAN_TYPE.field_alias


class TestSpanSpec:
    """SpanSpec 字段树查找行为测试。"""

    # ------------------------------------------------------------------
    # 字段路径可查找（get_full_field_name() 返回完整路径）
    # ------------------------------------------------------------------

    @pytest.mark.parametrize(
        "path",
        [
            # 根级标量字段
            "kind",
            "elapsed_time",
            "span_name",
            "start_time",
            "end_time",
            "time",
            "app_name",
            "bk_biz_id",
            "trace_state",
            # 根级复合字段
            "status",
            "attributes",
            "events",
            "links",
            # status.*
            "status.code",
            "status.message",
            # attributes 深层嵌套
            "attributes.span_type",
            "attributes.url.template",
            "attributes.url.full",
            "attributes.url.scheme",
            "attributes.http.request.method",
            "attributes.server.address",
            "attributes.browser.screen.height",
            "attributes.browser.viewport.width",
            "attributes.code.lineno",
            "attributes.code.filepath",
            "attributes.device.id",
            "attributes.error.message",
            "attributes.error.source",
            "attributes.error.handled",
            "attributes.session.id",
            "attributes.session.has_replay",
            "attributes.blank_screen.reason",
            "attributes.blank_screen.empty_ratio",
            "attributes.view.id",
            "attributes.view.loading_type",
            "attributes.view.url",
            "attributes.view.url_template",
            "attributes.view.end_reason",
            "attributes.resource.decoded_body_size",
            "attributes.resource.encoded_body_size",
            "attributes.resource.transfer_size",
            "attributes.resource.delivery_type",
            "attributes.resource.render_blocking_status",
            "attributes.resource.cache.hit",
            "attributes.network.effective_type",
            "attributes.outcome.type",
            "attributes.vital.id",
            "attributes.vital.lcp.target",
            "attributes.vital.lcp.element_render_delay",
            "attributes.vital.inp.input_delay",
            "attributes.vital.ttfb.dns_duration",
            # resource.*
            "resource.user_agent.name",
            "resource.device.type",
            "resource.session.sample_rate",
            "resource.telemetry.sdk.language",
            # events.*
            "events.name",
            "events.timestamp",
            "events.attributes.exception.message",
            "events.attributes.exception.type",
            # Web Vitals 虚拟字段（根级）
            "LCP",
            "CLS",
            "INP",
            "FCP",
            "TTFB",
        ],
    )
    def test_field_full_name(self, path: str):
        """所有已注册字段路径，get_full_field_name() 均返回完整路径。"""
        assert SpanSpec.from_field(path).get_full_field_name() == path

    # ------------------------------------------------------------------
    # 字段语义与原始 spec 一致（field_name 对齐）
    # ------------------------------------------------------------------

    def test_field_name_semantics(self):
        """bound spec 的 field_name 与原始 FieldSpec 实例保持一致。"""
        assert SpanSpec.from_field("kind").field_name == SpanSpec.KIND.field_name
        assert SpanSpec.from_field("links").field_name == SpanSpec.LINKS.field_name
        assert SpanSpec.from_field("events").field_name == SpanSpec.EVENTS.field_name
        assert SpanSpec.from_field("status.code").field_name == Status.CODE.field_name
        assert SpanSpec.from_field("status.message").field_name == Status.MESSAGE.field_name
        assert SpanSpec.from_field("attributes.span_type").field_name == common_attributes.SPAN_TYPE.field_name
        assert SpanSpec.from_field("attributes.url.template").field_name == http_attributes.URL_TEMPLATE.field_name
        assert SpanSpec.from_field("attributes.code.lineno").field_name == error_attributes.ERROR_LINENO.field_name
        assert SpanSpec.from_field("attributes.vital.id").field_name == vital_attributes.VITAL_ID.field_name
        assert (
            SpanSpec.from_field("attributes.vital.lcp.target").field_name
            == vital_attributes.VITAL_LCP_TARGET.field_name
        )
        assert (
            SpanSpec.from_field("resource.user_agent.name").field_name == common_attributes.USER_AGENT_NAME.field_name
        )
        assert SpanSpec.from_field("resource.device.type").field_name == device_attributes.DEVICE_TYPE.field_name
        assert SpanSpec.from_field("LCP").field_name == virtual_attributes.LCP.field_name
        assert SpanSpec.from_field("CLS").field_name == virtual_attributes.CLS.field_name

    # ------------------------------------------------------------------
    # 枚举字段的 option_values
    # ------------------------------------------------------------------

    @pytest.mark.parametrize(
        "path, expected",
        [
            ("attributes.span_type", RumSpanType),
            ("kind", SpanKind),
            ("status.code", SpanStatusCode),
            ("attributes.vital.metric", VitalMetric),
            ("attributes.network.status", NetworkStatus),
            ("attributes.network.connection.type", NetworkConnectionType),
            ("attributes.outcome.type", OutcomeType),
            ("resource.telemetry.sdk.language", SdkLanguage),
        ],
    )
    def test_enum_option_values(self, path: str, expected):
        """枚举字段携带正确的 option_values 类型。"""
        assert SpanSpec.from_field(path).option_values is expected

    # ------------------------------------------------------------------
    # 时间字段的单位与展示类型
    # ------------------------------------------------------------------

    @pytest.mark.parametrize(
        "path, unit, display_type",
        [
            ("start_time", "us", "datetime"),
            ("end_time", "us", "datetime"),
            ("elapsed_time", "us", "duration"),
        ],
    )
    def test_time_field_metadata(self, path: str, unit: str, display_type):
        """时间字段携带正确的单位和展示类型。"""
        spec = SpanSpec.from_field(path)
        assert spec.field_unit == unit
        assert spec.field_display_type == display_type

    # ------------------------------------------------------------------
    # Web Vitals 单位、展示类型与评级阈值
    # ------------------------------------------------------------------

    @pytest.mark.parametrize(
        "path, unit, display_type",
        [
            ("LCP", "ms", "duration"),
            ("INP", "ms", "duration"),
            ("FCP", "ms", "duration"),
            ("TTFB", "ms", "duration"),
            ("CLS", None, None),
        ],
    )
    def test_vital_field_metadata(self, path: str, unit, display_type):
        """Web Vitals 字段携带正确的单位和展示类型。"""
        spec = SpanSpec.from_field(path)
        assert spec.field_unit == unit
        assert spec.field_display_type == display_type

    def test_lcp_rating_config(self):
        """LCP 评级阈值使用字段单位（ms），末项省略 value 并兜底。"""
        lcp = SpanSpec.from_field("LCP")
        assert len(lcp.rating_config) == 3
        assert lcp.rating_config[0] == RatingLevel(rating="good", value=2500)
        assert lcp.rating_config[1] == RatingLevel(rating="needs_improvement", value=4000)
        assert lcp.rating_config[2] == RatingLevel(rating="poor")
        assert lcp.rating_config[2].value is None

    def test_cls_rating_config(self):
        """CLS 评级阈值无单位，数值为小数。"""
        cls_spec = SpanSpec.from_field("CLS")
        assert len(cls_spec.rating_config) == 3
        assert cls_spec.rating_config[0] == RatingLevel(rating="good", value=0.1)
        assert cls_spec.rating_config[1] == RatingLevel(rating="needs_improvement", value=0.25)
        assert cls_spec.rating_config[2] == RatingLevel(rating="poor")

    # ------------------------------------------------------------------
    # 未注册字段
    # ------------------------------------------------------------------

    def test_unknown_field_returns_bare_spec(self):
        """未注册字段返回仅含原始字段名的 FieldSpec，所有元数据为默认值。"""
        result = SpanSpec.from_field("xxx")
        assert result == FieldSpec("xxx")
        assert result.field_alias == ""
        assert result.field_unit is None
        assert result.field_display_type is None
        assert result.option_values is None
        assert result.rating_config == ()
