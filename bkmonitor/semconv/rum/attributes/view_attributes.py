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
from semconv.rum.constants import ViewLoadingTimeSource, ViewPhase, ViewLoadingType
from semconv.constants import FieldUnit, FieldDisplayType


VIEW_ID = FieldSpec(field_name="view.id", field_alias=_("页面 ID"))
VIEW_NAME = FieldSpec(field_name="view.name", field_alias=_("页面名称"))
VIEW_LOADING_TYPE = FieldSpec(
    field_name="view.loading_type", field_alias=_("页面加载类型"), option_values=ViewLoadingType
)
VIEW_URL = FieldSpec(field_name="view.url", field_alias=_("页面 URL"))
VIEW_PREVIOUS = FieldSpec(field_name="view.previous", field_alias=_("上一页面 URL"))
VIEW_PREVIOUS_URL_TEMPLATE = FieldSpec(field_name="view.previous_url_template", field_alias=_("上一个页面"))
VIEW_REFERRER = FieldSpec(field_name="view.referrer", field_alias=_("初始来源 URL"))
VIEW_URL_TEMPLATE = FieldSpec(field_name="view.url_template", field_alias=_("页面"))
VIEW_LOADING_TIME = FieldSpec(
    field_name="view.loading_time",
    field_alias=_("页面加载耗时"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
VIEW_LOADING_TIME_SOURCE = FieldSpec(
    field_name="view.loading_time_source", field_alias=_("页面加载计时方式"), option_values=ViewLoadingTimeSource
)
VIEW_FIRST_BYTE = FieldSpec(
    field_name="view.first_byte",
    field_alias=_("页面首字节耗时"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
VIEW_DOM_INTERACTIVE = FieldSpec(
    field_name="view.dom_interactive",
    field_alias=_("DOM 可交互时间"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
VIEW_DOM_CONTENT_LOADED = FieldSpec(
    field_name="view.dom_content_loaded",
    field_alias=_("DOMContentLoaded 时间"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
VIEW_DOM_COMPLETE = FieldSpec(
    field_name="view.dom_complete",
    field_alias=_("DOM 完成时间"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
VIEW_LOAD_EVENT = FieldSpec(
    field_name="view.load_event",
    field_alias=_("Load 事件时间"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
VIEW_PHASE = FieldSpec(field_name="view.phase", field_alias=_("页面阶段"), option_values=ViewPhase)
VIEW_STARTED_AT = FieldSpec(
    field_name="view.started_at",
    field_alias=_("页面开始时间"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DATETIME.value,
)
VIEW_VERSION = FieldSpec(field_name="view.version", field_alias=_("页面快照版本"))
VIEW_END_REASON = FieldSpec(field_name="view.end_reason", field_alias=_("页面结束原因"))
