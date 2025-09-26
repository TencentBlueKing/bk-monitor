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


class LabelMixin:
    """
    标签映射混入类，提供统一的标签获取逻辑

    子类需要定义 _LABEL_MAPPING 类变量或 _get_label_mapping 类方法
    """

    @cached_property
    def label(self):
        """
        获取枚举成员的标签值

        从子类的 _LABEL_MAPPING 或 _get_label_mapping 方法中获取标签
        """
        # 首先尝试获取 _LABEL_MAPPING 类变量
        label_mapping = getattr(self.__class__, "_LABEL_MAPPING", None)

        # 如果没有 _LABEL_MAPPING，尝试调用 _get_label_mapping 方法
        if label_mapping is None:
            get_mapping_method = getattr(self.__class__, "_get_label_mapping", None)
            if get_mapping_method is not None:
                label_mapping = get_mapping_method()

        if label_mapping is not None:
            return str(label_mapping.get(self, self.value))
        return str(self.value)


class EntityType(LabelMixin, CachedEnum):
    """
    事件类型
    """

    BcsPod = "BcsPod"
    APMService = "APMService"
    BkNodeHost = "BkNodeHost"
    UnKnown = "Unknown"

    @classmethod
    def _get_label_mapping(cls):
        return {
            cls.BcsPod: _("BCS Pod"),
            cls.APMService: _("APM服务"),
            cls.BkNodeHost: _("主机节点"),
            cls.UnKnown: _("未知"),
        }

    @classmethod
    def choices(cls):
        return [choice.value for choice in cls.__members__.values()]

    @classmethod
    def label_mapping(cls):
        return cls._get_label_mapping()

    @classmethod
    def get_default(cls, value):
        default = super().get_default(value)
        default.label = value
        return default


class IndexType(CachedEnum):
    """
    索引类型
    """

    ENTITY = "entity"
    EDGE = "edge"
