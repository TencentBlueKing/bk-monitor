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

from semconv.rum.attributes import common_attributes, longtask_attributes
from semconv.rum.field import FieldSpec


class EventAttributes(FieldSpec):
    """events.attributes.*"""

    EXCEPTION_TYPE = common_attributes.EXCEPTION_TYPE
    EXCEPTION_MESSAGE = common_attributes.EXCEPTION_MESSAGE
    EXCEPTION_STACKTRACE = common_attributes.EXCEPTION_STACKTRACE

    LONG_TASK_SCRIPT_DURATION = longtask_attributes.LONG_TASK_SCRIPT_DURATION
    LONG_TASK_SCRIPT_EXECUTION_START = longtask_attributes.LONG_TASK_SCRIPT_EXECUTION_START
    LONG_TASK_SCRIPT_FORCED_STYLE_AND_LAYOUT_DURATION = (
        longtask_attributes.LONG_TASK_SCRIPT_FORCED_STYLE_AND_LAYOUT_DURATION
    )
    LONG_TASK_SCRIPT_PAUSE_DURATION = longtask_attributes.LONG_TASK_SCRIPT_PAUSE_DURATION
    LONG_TASK_SCRIPT_SOURCE_CHAR_POSITION = longtask_attributes.LONG_TASK_SCRIPT_SOURCE_CHAR_POSITION
    LONG_TASK_SCRIPT_START_TIME = longtask_attributes.LONG_TASK_SCRIPT_START_TIME
    LONG_TASK_SCRIPT_INVOKER = longtask_attributes.LONG_TASK_SCRIPT_INVOKER
    LONG_TASK_SCRIPT_INVOKER_TYPE = longtask_attributes.LONG_TASK_SCRIPT_INVOKER_TYPE
    LONG_TASK_SCRIPT_SOURCE_FUNCTION_NAME = longtask_attributes.LONG_TASK_SCRIPT_SOURCE_FUNCTION_NAME
    LONG_TASK_SCRIPT_SOURCE_URL = longtask_attributes.LONG_TASK_SCRIPT_SOURCE_URL
    LONG_TASK_SCRIPT_WINDOW_ATTRIBUTION = longtask_attributes.LONG_TASK_SCRIPT_WINDOW_ATTRIBUTION


class Events(FieldSpec):
    """events（Span 事件字段，数组类型）"""

    NAME = FieldSpec(field_name="name", field_alias=_("事件名称"))
    TIMESTAMP = FieldSpec(field_name="timestamp", field_alias=_("事件发生时间"))
    ATTRIBUTES = EventAttributes(field_name="attributes")
