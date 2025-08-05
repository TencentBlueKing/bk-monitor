"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from constants.apm import CachedEnum


class EntityType(CachedEnum):
    """
    事件类型
    """

    BcsPod = "BcsPod"
    APMService = "APMService"
    BkNodeHost = "BkNodeHost"
    UnKnown = "Unknown"
    
    @classmethod
    def choices(cls):
        return [choice.value for choice in cls.__members__.values()]

    @cached_property
    def label(self):
        return str(
            {
                EntityType.BcsPod: _("BCS Pod"),
                EntityType.APMService: _("APM服务"),
                EntityType.BkNodeHost: _("主机节点"),
                EntityType.UnKnown: _("未知"),
            }.get(self, self.value)
        )

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
