"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from dataclasses import replace
from constants.otel_query import FieldTypeEnum
from semconv.rum import common
from semconv.rum.field import FieldSpec
from semconv.rum.registry import FieldRegistry
from semconv.rum.trace import SpanSpec


class ViewSpec(FieldSpec):
    """View 层级保留维度与派生字段目录。"""

    APP_NAME = common.raw_field("app_name")
    RESOURCE_SERVICE_NAME = common.raw_field("resource.service.name")
    RESOURCE_SERVICE_VERSION = common.raw_field("resource.service.version")
    RESOURCE_DEPLOYMENT_ENVIRONMENT_NAME = common.raw_field("resource.deployment.environment.name")
    RESOURCE_TELEMETRY_SDK_NAME = common.raw_field("resource.telemetry.sdk.name")
    RESOURCE_TELEMETRY_SDK_VERSION = common.raw_field("resource.telemetry.sdk.version")
    RESOURCE_TELEMETRY_SDK_LANGUAGE = common.raw_field("resource.telemetry.sdk.language")
    RESOURCE_DEVICE_TYPE = common.raw_field("resource.device.type")
    RESOURCE_USER_AGENT_NAME = common.raw_field("resource.user_agent.name")
    RESOURCE_USER_AGENT_VERSION = common.raw_field("resource.user_agent.version")
    RESOURCE_USER_AGENT_OS_NAME = common.raw_field("resource.user_agent.os.name")
    ATTRIBUTES_NETWORK_CONNECTION_TYPE = common.raw_field("attributes.network.connection.type")
    ATTRIBUTES_NETWORK_EFFECTIVE_TYPE = common.raw_field("attributes.network.effective_type")
    ATTRIBUTES_USER_ID = common.raw_field("attributes.user.id")
    ATTRIBUTES_SESSION_ID = common.raw_field("attributes.session.id")
    ATTRIBUTES_VIEW_ID = common.raw_field("attributes.view.id")
    ATTRIBUTES_VIEW_NAME = common.raw_field("attributes.view.name")
    ATTRIBUTES_VIEW_LOADING_TYPE = common.raw_field("attributes.view.loading_type")
    ATTRIBUTES_VIEW_URL = common.raw_field("attributes.view.url")
    ATTRIBUTES_VIEW_PREVIOUS = common.raw_field("attributes.view.previous")
    ATTRIBUTES_VIEW_URL_TEMPLATE = common.raw_field("attributes.view.url_template")
    ATTRIBUTES_VIEW_PREVIOUS_URL_TEMPLATE = common.raw_field("attributes.view.previous_url_template")
    ATTRIBUTES_VIEW_LOADING_TIME = common.raw_field("attributes.view.loading_time", FieldTypeEnum.DOUBLE.value)
    TRACE_COUNT = common.TRACE_COUNT
    ERROR_COUNT = common.ERROR_COUNT
    ACTION_COUNT = common.ACTION_COUNT
    FRUSTRATION_COUNT = common.FRUSTRATION_COUNT
    REQUEST_COUNT = common.REQUEST_COUNT
    REQUEST_ERROR_COUNT = common.REQUEST_ERROR_COUNT
    LONG_TASK_COUNT = common.LONG_TASK_COUNT
    IS_ACTIVE = common.IS_ACTIVE
    CLOSE_REASON = common.CLOSE_REASON
    CLOSE_TIME = common.CLOSE_TIME
    DURATION = common.DURATION
    START_TIME = common.START_TIME
    CLS = replace(SpanSpec.from_field("CLS"), field_name="web_vitals.cls")
    LCP = replace(SpanSpec.from_field("LCP"), field_name="web_vitals.lcp")
    FCP = replace(SpanSpec.from_field("FCP"), field_name="web_vitals.fcp")
    INP = replace(SpanSpec.from_field("INP"), field_name="web_vitals.inp")
    TTFB = replace(SpanSpec.from_field("TTFB"), field_name="web_vitals.ttfb")

    @classmethod
    def fields(cls) -> list[FieldSpec]:
        return _FIELDS.fields()

    @classmethod
    def from_field(cls, field_name: str) -> FieldSpec:
        return _FIELDS.from_field(field_name)


_FIELDS = FieldRegistry(ViewSpec(field_name=""))
