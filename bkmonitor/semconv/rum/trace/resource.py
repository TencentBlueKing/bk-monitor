"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from semconv.rum.attributes import common_attributes, device_attributes, session_attributes
from semconv.rum.field import FieldSpec


class Resource(FieldSpec):
    """resource.*（Span 顶层 resource 字段）"""

    # service
    SERVICE_NAME = common_attributes.SERVICE_NAME
    SERVICE_VERSION = common_attributes.SERVICE_VERSION

    # deployment
    DEPLOYMENT_ENVIRONMENT_NAME = common_attributes.DEPLOYMENT_ENVIRONMENT_NAME

    # session
    SESSION_SAMPLE_RATE = session_attributes.SESSION_SAMPLE_RATE

    # telemetry
    TELEMETRY_SDK_VERSION = common_attributes.TELEMETRY_SDK_VERSION
    TELEMETRY_SDK_LANGUAGE = common_attributes.TELEMETRY_SDK_LANGUAGE
    TELEMETRY_SDK_NAME = common_attributes.TELEMETRY_SDK_NAME

    # device
    DEVICE_TYPE = device_attributes.DEVICE_TYPE

    # user_agent
    USER_AGENT_NAME = common_attributes.USER_AGENT_NAME
    USER_AGENT_VERSION = common_attributes.USER_AGENT_VERSION
    USER_AGENT_OS_NAME = common_attributes.USER_AGENT_OS_NAME
