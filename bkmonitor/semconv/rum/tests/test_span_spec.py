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
    span_attributes,
    common_attributes,
    error_attributes,
    device_attributes,
    vital_attributes,
    http_attributes,
    session_attributes,
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


class TestSpanSpec:
    """SpanSpec 字段树查找行为测试。"""

    def test_root_field_identity(self):
        """根级字段查找返回原始共享对象。"""
        assert SpanSpec.from_field("kind") is SpanSpec.KIND is span_attributes.KIND
        assert SpanSpec.from_field("elapsed_time") is SpanSpec.ELAPSED_TIME is span_attributes.ELAPSED_TIME
        assert SpanSpec.from_field("span_name") is SpanSpec.SPAN_NAME is span_attributes.SPAN_NAME

    def test_composite_field_identity(self):
        """复合字段查找返回原始共享对象。"""
        assert SpanSpec.from_field("status") is SpanSpec.STATUS
        assert SpanSpec.from_field("attributes") is SpanSpec.ATTRIBUTES
        assert SpanSpec.from_field("events") is SpanSpec.EVENTS

    def test_nested_field_identity(self):
        """嵌套字段查找返回原始共享对象。"""
        assert SpanSpec.from_field("status.code") is SpanSpec.STATUS.CODE is Status.CODE
        assert SpanSpec.from_field("status.message") is SpanSpec.STATUS.MESSAGE is Status.MESSAGE

    def test_deep_nested_field_identity(self):
        """深层嵌套字段查找返回原始共享对象。"""
        assert (
            SpanSpec.from_field("attributes.span_type") is SpanSpec.ATTRIBUTES.SPAN_TYPE is common_attributes.SPAN_TYPE
        )
        assert (
            SpanSpec.from_field("attributes.url.template")
            is SpanSpec.ATTRIBUTES.URL_TEMPLATE
            is http_attributes.URL_TEMPLATE
        )
        assert (
            SpanSpec.from_field("attributes.http.request.method")
            is SpanSpec.ATTRIBUTES.HTTP_REQUEST_METHOD
            is http_attributes.HTTP_REQUEST_METHOD
        )

    def test_resource_field_identity(self):
        """resource.* 字段查找返回原始共享对象。"""
        assert (
            SpanSpec.from_field("resource.user_agent.name")
            is SpanSpec.RESOURCE.USER_AGENT_NAME
            is common_attributes.USER_AGENT_NAME
        )
        assert (
            SpanSpec.from_field("resource.device.type")
            is SpanSpec.RESOURCE.DEVICE_TYPE
            is device_attributes.DEVICE_TYPE
        )
        assert SpanSpec.from_field("resource.session.sample_rate") is session_attributes.SESSION_SAMPLE_RATE

    def test_vital_fields_at_root(self):
        """Web Vitals 虚拟字段注册在根级。"""
        assert SpanSpec.from_field("LCP") is SpanSpec.LCP is vital_attributes.LCP
        assert SpanSpec.from_field("CLS") is SpanSpec.CLS is vital_attributes.CLS
        assert SpanSpec.from_field("INP") is SpanSpec.INP is vital_attributes.INP
        assert SpanSpec.from_field("FCP") is SpanSpec.FCP is vital_attributes.FCP
        assert SpanSpec.from_field("TTFB") is SpanSpec.TTFB is vital_attributes.TTFB

    def test_vital_field_unit(self):
        """Web Vitals 字段携带正确单位。"""
        assert SpanSpec.from_field("LCP").field_unit == "ms"
        assert SpanSpec.from_field("CLS").field_unit is None

    def test_vital_field_display_type(self):
        """有单位的 Web Vitals 字段携带 duration 展示类型，CLS 无展示类型。"""
        assert SpanSpec.from_field("LCP").field_display_type == "duration"
        assert SpanSpec.from_field("INP").field_display_type == "duration"
        assert SpanSpec.from_field("FCP").field_display_type == "duration"
        assert SpanSpec.from_field("TTFB").field_display_type == "duration"
        assert SpanSpec.from_field("CLS").field_display_type is None

    def test_vital_rating_config(self):
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

    def test_end_time_display_type(self):
        """end_time 字段携带 datetime 展示类型和 us 单位。"""
        end_time = SpanSpec.from_field("end_time")
        assert end_time.field_display_type == "datetime"
        assert end_time.field_unit == "us"

    def test_elapsed_time_unit(self):
        """elapsed_time 字段携带 us 单位。"""
        assert SpanSpec.from_field("elapsed_time").field_unit == "us"

    def test_option_values_on_enum_field(self):
        """枚举字段携带 option_values 类型。"""
        assert SpanSpec.from_field("attributes.span_type").option_values is RumSpanType
        assert SpanSpec.from_field("kind").option_values is SpanKind
        assert SpanSpec.from_field("status.code").option_values is SpanStatusCode

    def test_links_field(self):
        """links[] 字段可查找。"""
        assert SpanSpec.from_field("links") is SpanSpec.LINKS

    def test_events_field(self):
        """events 字段可查找。"""
        assert SpanSpec.from_field("events") is SpanSpec.EVENTS

    def test_unknown_field_returns_bare_spec(self):
        """未注册字段返回仅含原始字段名的 FieldSpec。"""
        result = SpanSpec.from_field("xxx")
        assert result == FieldSpec("xxx")
        assert result.field_alias == ""
        assert result.field_unit is None
        assert result.field_display_type is None
        assert result.option_values is None
        assert result.rating_config == ()

    def test_vital_field_shared_with_attributes(self):
        """vital.* 字段在 attributes 树下与 vital_attributes 是同一对象。"""
        assert SpanSpec.from_field("attributes.vital.lcp.target") is SpanSpec.ATTRIBUTES.VITAL_LCP_TARGET
        assert SpanSpec.ATTRIBUTES.VITAL_LCP_TARGET is vital_attributes.VITAL_LCP_TARGET
        assert SpanSpec.from_field("attributes.vital.id") is SpanSpec.ATTRIBUTES.VITAL_ID is vital_attributes.VITAL_ID

    def test_new_root_fields(self):
        """新增根级字段可查找。"""
        assert SpanSpec.from_field("start_time") is SpanSpec.START_TIME
        assert SpanSpec.from_field("time") is SpanSpec.TIME
        assert SpanSpec.from_field("app_name") is SpanSpec.APP_NAME
        assert SpanSpec.from_field("bk_biz_id") is SpanSpec.BK_BIZ_ID
        assert SpanSpec.from_field("trace_state") is SpanSpec.TRACE_STATE

    def test_start_time_display_type(self):
        """start_time 字段携带 datetime 展示类型和 us 单位。"""
        start_time = SpanSpec.from_field("start_time")
        assert start_time.field_display_type == "datetime"
        assert start_time.field_unit == "us"

    def test_browser_fields(self):
        """attributes.browser.* 字段可查找。"""
        assert SpanSpec.from_field("attributes.browser.screen.height") is SpanSpec.ATTRIBUTES.BROWSER_SCREEN_HEIGHT
        assert SpanSpec.from_field("attributes.browser.viewport.width") is SpanSpec.ATTRIBUTES.BROWSER_VIEWPORT_WIDTH

    def test_code_fields(self):
        """attributes.code.* 字段可查找。"""
        assert (
            SpanSpec.from_field("attributes.code.lineno")
            is SpanSpec.ATTRIBUTES.ERROR_LINENO
            is error_attributes.ERROR_LINENO
        )
        assert SpanSpec.from_field("attributes.code.filepath") is SpanSpec.ATTRIBUTES.ERROR_FILEPATH

    def test_device_fields(self):
        """attributes.device.* 字段可查找。"""
        assert SpanSpec.from_field("attributes.device.id") is SpanSpec.ATTRIBUTES.DEVICE_ID

    def test_exception_fields(self):
        """attributes.error.* 字段可查找。"""
        assert SpanSpec.from_field("attributes.error.message") is SpanSpec.ATTRIBUTES.ERROR_MESSAGE
        assert SpanSpec.from_field("attributes.error.source") is SpanSpec.ATTRIBUTES.ERROR_SOURCE
        assert SpanSpec.from_field("attributes.error.handled") is SpanSpec.ATTRIBUTES.ERROR_HANDLED

    def test_session_fields(self):
        """attributes.session.* 字段可查找。"""
        assert SpanSpec.from_field("attributes.session.id") is SpanSpec.ATTRIBUTES.SESSION_ID
        assert SpanSpec.from_field("attributes.session.has_replay") is SpanSpec.ATTRIBUTES.SESSION_HAS_REPLAY

    def test_blank_screen_fields(self):
        """attributes.blank_screen.* 字段可查找。"""
        assert SpanSpec.from_field("attributes.blank_screen.reason") is SpanSpec.ATTRIBUTES.BLANK_SCREEN_REASON
        assert (
            SpanSpec.from_field("attributes.blank_screen.empty_ratio") is SpanSpec.ATTRIBUTES.BLANK_SCREEN_EMPTY_RATIO
        )

    def test_extended_view_fields(self):
        """attributes.view.* 补充字段可查找。"""
        assert SpanSpec.from_field("attributes.view.id") is SpanSpec.ATTRIBUTES.VIEW_ID
        assert SpanSpec.from_field("attributes.view.loading_type") is SpanSpec.ATTRIBUTES.VIEW_LOADING_TYPE
        assert SpanSpec.from_field("attributes.view.url") is SpanSpec.ATTRIBUTES.VIEW_URL
        assert SpanSpec.from_field("attributes.view.url_template") is SpanSpec.ATTRIBUTES.VIEW_URL_TEMPLATE
        assert SpanSpec.from_field("attributes.view.end_reason") is SpanSpec.ATTRIBUTES.VIEW_END_REASON

    def test_extended_resource_fields(self):
        """attributes.resource.* 补充字段可查找。"""
        assert (
            SpanSpec.from_field("attributes.resource.decoded_body_size")
            is SpanSpec.ATTRIBUTES.RESOURCE_DECODED_BODY_SIZE
        )
        assert (
            SpanSpec.from_field("attributes.resource.encoded_body_size")
            is SpanSpec.ATTRIBUTES.RESOURCE_ENCODED_BODY_SIZE
        )
        assert SpanSpec.from_field("attributes.resource.transfer_size") is SpanSpec.ATTRIBUTES.RESOURCE_TRANSFER_SIZE
        assert SpanSpec.from_field("attributes.resource.delivery_type") is SpanSpec.ATTRIBUTES.RESOURCE_DELIVERY_TYPE
        assert (
            SpanSpec.from_field("attributes.resource.render_blocking_status")
            is SpanSpec.ATTRIBUTES.RESOURCE_RENDER_BLOCKING_STATUS
        )
        assert SpanSpec.from_field("attributes.resource.cache.hit") is SpanSpec.ATTRIBUTES.RESOURCE_CACHE_HIT

    def test_extended_url_fields(self):
        """attributes.url.* 补充字段可查找。"""
        assert SpanSpec.from_field("attributes.url.full") is SpanSpec.ATTRIBUTES.URL_FULL
        assert SpanSpec.from_field("attributes.url.scheme") is SpanSpec.ATTRIBUTES.URL_SCHEME

    def test_extended_network_fields(self):
        """attributes.network.* 补充字段可查找。"""
        assert SpanSpec.from_field("attributes.network.effective_type") is SpanSpec.ATTRIBUTES.NETWORK_EFFECTIVE_TYPE
        assert SpanSpec.from_field("attributes.network.status").option_values is NetworkStatus
        assert SpanSpec.from_field("attributes.network.connection.type").option_values is NetworkConnectionType

    def test_extended_error_fields(self):
        """attributes.error.* 补充字段可查找。"""
        assert SpanSpec.from_field("attributes.error.handled") is SpanSpec.ATTRIBUTES.ERROR_HANDLED

    def test_vital_sub_fields(self):
        """attributes.vital.* 子指标字段可查找。"""
        assert SpanSpec.from_field("attributes.vital.id") is SpanSpec.ATTRIBUTES.VITAL_ID
        assert SpanSpec.from_field("attributes.vital.metric").option_values is VitalMetric
        assert (
            SpanSpec.from_field("attributes.vital.lcp.element_render_delay")
            is SpanSpec.ATTRIBUTES.VITAL_LCP_ELEMENT_RENDER_DELAY
        )
        assert SpanSpec.from_field("attributes.vital.inp.input_delay") is SpanSpec.ATTRIBUTES.VITAL_INP_INPUT_DELAY
        assert SpanSpec.from_field("attributes.vital.ttfb.dns_duration") is SpanSpec.ATTRIBUTES.VITAL_TTFB_DNS_DURATION

    def test_events_sub_fields(self):
        """events.* 子字段可查找。"""
        assert SpanSpec.from_field("events.name") is SpanSpec.EVENTS.NAME
        assert SpanSpec.from_field("events.timestamp") is SpanSpec.EVENTS.TIMESTAMP
        assert (
            SpanSpec.from_field("events.attributes.exception.message") is SpanSpec.EVENTS.ATTRIBUTES.EXCEPTION_MESSAGE
        )
        assert SpanSpec.from_field("events.attributes.exception.type") is SpanSpec.EVENTS.ATTRIBUTES.EXCEPTION_TYPE

    def test_resource_rum_provider(self):
        """resource.telemetry.* 字段可查找。"""
        assert SpanSpec.from_field("resource.telemetry.sdk.language").option_values is SdkLanguage

    def test_server_address(self):
        """attributes.server.address 字段可查找。"""
        assert SpanSpec.from_field("attributes.server.address") is SpanSpec.ATTRIBUTES.SERVER_ADDRESS

    def test_html_tag(self):
        """attributes.code.filepath 字段可查找。"""
        assert SpanSpec.from_field("attributes.code.filepath") is SpanSpec.ATTRIBUTES.ERROR_FILEPATH

    def test_user_agent_attr_fields(self):
        """resource.user_agent.* 字段可查找。"""
        assert (
            SpanSpec.from_field("resource.user_agent.name")
            is SpanSpec.RESOURCE.USER_AGENT_NAME
            is common_attributes.USER_AGENT_NAME
        )

    def test_outcome_type(self):
        """attributes.outcome.type 字段可查找。"""
        assert SpanSpec.from_field("attributes.outcome.type").option_values is OutcomeType

    def test_required_assertions(self):
        """用户要求的 6 个核心断言。"""
        assert SpanSpec.from_field("kind") is SpanSpec.KIND is span_attributes.KIND
        assert SpanSpec.from_field("attributes") is SpanSpec.ATTRIBUTES
        assert SpanSpec.from_field("events") is SpanSpec.EVENTS
        assert SpanSpec.from_field("events.name") is SpanSpec.EVENTS.NAME
        assert SpanSpec.from_field("xxx") == FieldSpec("xxx")
