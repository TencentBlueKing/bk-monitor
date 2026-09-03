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

from semconv.constants import FrustrationType
from semconv.rum.field import FieldSpec


ACTION_ID = FieldSpec(field_name="action.id", field_alias=_("动作 ID"))
ACTION_TYPE = FieldSpec(field_name="action.type", field_alias=_("动作类型"))
ACTION_TARGET_NAME = FieldSpec(field_name="action.target.name", field_alias=_("目标元素名称"))
ACTION_TARGET_TAG = FieldSpec(field_name="action.target.tag", field_alias=_("目标元素标签"))
ACTION_FRUSTRATION_TYPE = FieldSpec(
    field_name="action.frustration.type", field_alias=_("挫败类型"), option_values=FrustrationType
)
