"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.utils.translation import gettext_lazy as _
from semconv.rum import common
from semconv.rum.field import FieldSpec
from semconv.rum.registry import FieldRegistry


class SessionSpec(FieldSpec):
    """Session 层级保留维度与派生字段目录。"""

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
    ATTRIBUTES_SESSION_HAS_REPLAY = common.raw_field("attributes.session.has_replay")
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
    VIEW_COUNT = FieldSpec("view_count", _("View 数量"), field_type="long", is_real=False)
    ENTER_URL_TEMPLATE = FieldSpec("enter_url_template", _("入口视图 URL"), field_type="keyword", is_real=False)
    EXIT_URL_TEMPLATE = FieldSpec("exit_url_template", _("退出视图 URL"), field_type="keyword", is_real=False)

    @classmethod
    def fields(cls) -> list[FieldSpec]:
        return _FIELDS.fields()

    @classmethod
    def from_field(cls, field_name: str) -> FieldSpec:
        return _FIELDS.from_field(field_name)


_FIELDS = FieldRegistry(SessionSpec(field_name=""))
