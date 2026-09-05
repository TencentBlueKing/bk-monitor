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

from semconv.rum.field import FieldSpec
from semconv.rum.constants import LongTaskEntryType
from semconv.constants import FieldUnit, FieldDisplayType


LONG_TASK_SCRIPT_DURATION = FieldSpec(
    field_name="long_task.script.duration",
    field_alias=_("脚本耗时"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
LONG_TASK_SCRIPT_EXECUTION_START = FieldSpec(
    field_name="long_task.script.execution_start",
    field_alias=_("脚本执行开始时间"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
LONG_TASK_SCRIPT_FORCED_STYLE_AND_LAYOUT_DURATION = FieldSpec(
    field_name="long_task.script.forced_style_and_layout_duration",
    field_alias=_("强制样式与布局耗时"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
LONG_TASK_SCRIPT_PAUSE_DURATION = FieldSpec(
    field_name="long_task.script.pause_duration",
    field_alias=_("暂停耗时"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
LONG_TASK_SCRIPT_SOURCE_CHAR_POSITION = FieldSpec(
    field_name="long_task.script.source_char_position", field_alias=_("源码字符位置")
)
LONG_TASK_SCRIPT_START_TIME = FieldSpec(
    field_name="long_task.script.start_time",
    field_alias=_("脚本开始时间"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
LONG_TASK_SCRIPT_INVOKER = FieldSpec(field_name="long_task.script.invoker", field_alias=_("调用方"))
LONG_TASK_SCRIPT_INVOKER_TYPE = FieldSpec(field_name="long_task.script.invoker_type", field_alias=_("调用方类型"))
LONG_TASK_SCRIPT_SOURCE_FUNCTION_NAME = FieldSpec(
    field_name="long_task.script.source_function_name", field_alias=_("源函数名")
)
LONG_TASK_SCRIPT_SOURCE_URL = FieldSpec(field_name="long_task.script.source_url", field_alias=_("脚本 URL"))
LONG_TASK_SCRIPT_WINDOW_ATTRIBUTION = FieldSpec(
    field_name="long_task.script.window_attribution", field_alias=_("Window 归因")
)

LONG_TASK_ID = FieldSpec(field_name="long_task.id", field_alias=_("长任务 ID"))
LONG_TASK_NAME = FieldSpec(field_name="long_task.name", field_alias=_("Performance Entry 名称"))
LONG_TASK_ENTRY_TYPE = FieldSpec(
    field_name="long_task.entry_type", field_alias=_("采集条目类型"), option_values=LongTaskEntryType
)
LONG_TASK_BLOCKING_DURATION = FieldSpec(
    field_name="long_task.blocking_duration",
    field_alias=_("主线程阻塞耗时"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
LONG_TASK_FIRST_UI_EVENT_TIMESTAMP = FieldSpec(
    field_name="long_task.first_ui_event_timestamp",
    field_alias=_("首个 UI 事件时间"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
LONG_TASK_RENDER_START = FieldSpec(
    field_name="long_task.render_start",
    field_alias=_("渲染开始时间"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
LONG_TASK_STYLE_AND_LAYOUT_START = FieldSpec(
    field_name="long_task.style_and_layout_start",
    field_alias=_("样式与布局开始时间"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
