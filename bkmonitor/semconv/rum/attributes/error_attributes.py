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

# error
ERROR_MESSAGE = FieldSpec(field_name="error.message", field_alias=_("错误信息"))
ERROR_HANDLED = FieldSpec(field_name="error.handled", field_alias=_("错误是否被捕获"))
ERROR_SOURCE = FieldSpec(field_name="error.source", field_alias=_("错误来源"))

# code
ERROR_COLUMN = FieldSpec(field_name="code.column", field_alias=_("代码列号"))
ERROR_FILEPATH = FieldSpec(field_name="code.filepath", field_alias=_("代码文件路径"))
ERROR_LINENO = FieldSpec(field_name="code.lineno", field_alias=_("代码行号"))
