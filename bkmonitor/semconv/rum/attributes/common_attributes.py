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

from rum_web.constants import RumSpanType
from semconv.constants import OutcomeType, SdkLanguage
from semconv.rum.field import FieldSpec

# ── 领域无关字段 ──────────────────────────────────────────────────────
# service
SERVICE_NAME = FieldSpec(field_name="service.name", field_alias=_("服务名称"))
SERVICE_VERSION = FieldSpec(field_name="service.version", field_alias=_("服务版本"))

# deployment
DEPLOYMENT_ENVIRONMENT_NAME = FieldSpec(field_name="deployment.environment.name", field_alias=_("环境名称"))

# telemetry
TELEMETRY_SDK_VERSION = FieldSpec(field_name="telemetry.sdk.version", field_alias=_("SDK 版本"))
TELEMETRY_SDK_LANGUAGE = FieldSpec(
    field_name="telemetry.sdk.language", field_alias=_("语言"), option_values=SdkLanguage
)
TELEMETRY_SDK_NAME = FieldSpec(field_name="telemetry.sdk.name", field_alias=_("SDK 名称"))

# user_agent
USER_AGENT_NAME = FieldSpec(field_name="user_agent.name", field_alias=_("代理名称"))
USER_AGENT_VERSION = FieldSpec(field_name="user_agent.version", field_alias=_("代理版本"))
USER_AGENT_OS_NAME = FieldSpec(field_name="user_agent.os.name", field_alias=_("操作系统名称"))

# exception
EXCEPTION_TYPE = FieldSpec(field_name="exception.type", field_alias=_("异常类型"))
EXCEPTION_MESSAGE = FieldSpec(field_name="exception.message", field_alias=_("异常消息"))
EXCEPTION_STACKTRACE = FieldSpec(field_name="exception.stacktrace", field_alias=_("异常堆栈"))

# user
USER_ID = FieldSpec(field_name="user.id", field_alias=_("用户 ID"))
SPAN_TYPE = FieldSpec(field_name="span_type", field_alias=_("Span 类型"), option_values=RumSpanType)
OUTCOME_TYPE = FieldSpec(field_name="outcome.type", field_alias=_("执行结果"), option_values=OutcomeType)
