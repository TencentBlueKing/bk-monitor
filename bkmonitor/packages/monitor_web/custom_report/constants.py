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

# 自定义指标的配置
UNGROUP_SCOPE_NAME = "default"  # 未分组名称
DEFAULT_FIELD_SCOPE = "default"


class CustomTSMetricType:
    METRIC = "metric"
    DIMENSION = "dimension"

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(cls.METRIC, _("指标")), (cls.DIMENSION, _("维度"))]


class ScopeCreateFrom:
    """指标组创建来源."""

    DATA = "data"
    USER = "user"
    DEFAULT = "default"

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(cls.DATA, _("自动创建")), (cls.USER, _("手动创建")), (cls.DEFAULT, _("默认分组"))]
