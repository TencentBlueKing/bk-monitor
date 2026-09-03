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

from semconv.constants import SessionType, SessionPhase
from semconv.rum.field import FieldSpec

SESSION_SAMPLE_RATE = FieldSpec(field_name="session.sample_rate", field_alias=_("Session 采样率"))
SESSION_ID = FieldSpec(field_name="session.id", field_alias=_("会话 ID"))
SESSION_HAS_REPLAY = FieldSpec(field_name="session.has_replay", field_alias=_("是否回放"))
SESSION_TYPE = FieldSpec(field_name="session.type", field_alias=_("会话类型"), option_values=SessionType)
SESSION_PHASE = FieldSpec(field_name="session.phase", field_alias=_("会话生命周期阶段"), option_values=SessionPhase)
