"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from constants.apm import CachedEnum


class Namespace(CachedEnum):
    """命名空间"""

    APM = "apm"
    K8S = "k8s"
    DEFAULT = "default"

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(cls.APM.value, cls.APM.label), (cls.K8S.value, cls.K8S.label), (cls.DEFAULT.value, cls.DEFAULT.label)]

    @cached_property
    def label(self) -> str:
        return str(
            {self.APM: _("APM 内置"), self.K8S: _("容器监控内置"), self.DEFAULT: _("默认")}.get(self, self.value)
        )

    @classmethod
    def get_default(cls, value) -> "Namespace":
        default = super().get_default(value)
        default.label = value
        return default


class VariableType(CachedEnum):
    """变量类型"""

    METHOD = "METHOD"
    GROUP_BY = "GROUP_BY"
    TAG_VALUES = "TAG_VALUES"
    CONDITIONS = "CONDITIONS"
    FUNCTIONS = "FUNCTIONS"  # query_configs 中的指标函数
    CONSTANTS = "CONSTANTS"
    EXPRESSION_FUNCTIONS = "EXPRESSION_FUNCTIONS"

    @cached_property
    def require_related_tag(self) -> list[str]:
        """返回需要「关联维度」的变量类型列表"""
        return [self.TAG_VALUES.value]

    @cached_property
    def require_related_metrics(self) -> list[str]:
        """返回需要「关联指标」的变量类型列表"""
        return [self.GROUP_BY.value, self.TAG_VALUES.value, self.CONDITIONS.value]

    def is_required_related_tag(self) -> bool:
        """判断当前变量类型是否需要「关联维度」"""
        return self.value in self.require_related_tag

    def is_required_related_metrics(self) -> bool:
        """判断当前变量类型是否需要「关联指标」"""
        return self.value in self.require_related_metrics

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [
            (cls.METHOD.value, cls.METHOD.label),
            (cls.GROUP_BY.value, cls.GROUP_BY.label),
            (cls.TAG_VALUES.value, cls.TAG_VALUES.label),
            (cls.CONDITIONS.value, cls.CONDITIONS.label),
            (cls.FUNCTIONS.value, cls.FUNCTIONS.label),
            (cls.CONSTANTS.value, cls.CONSTANTS.label),
            (cls.EXPRESSION_FUNCTIONS.value, cls.EXPRESSION_FUNCTIONS.label),
        ]

    @cached_property
    def label(self) -> str:
        return str(
            {
                self.METHOD: _("汇聚方法"),
                self.GROUP_BY: _("维度"),
                self.TAG_VALUES: _("维度值"),
                self.CONDITIONS: _("条件"),
                self.FUNCTIONS: _("函数"),
                self.CONSTANTS: _("常量"),
                self.EXPRESSION_FUNCTIONS: _("表达式函数"),
            }.get(self, self.value)
        )

    @classmethod
    def get_default(cls, value) -> "VariableType":
        default = super().get_default(value)
        default.label = value
        return default
