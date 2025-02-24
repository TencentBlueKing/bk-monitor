# -*- coding: utf-8 -*-
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


class EventDomain(CachedEnum):
    """事件领域
    一个领域的事件具有多个源。
    例如 CICD 可能来源于 BKCI、ARGO、GITHUB_ACTIONS
    """

    K8S: str = "K8S"
    CICD: str = "CICD"
    SYSTEM: str = "SYSTEM"

    @cached_property
    def label(self):
        return str({self.K8S: _("Kubernetes"), self.CICD: _("CICD"), self.SYSTEM: _("系统")}.get(self, self.value))

    @classmethod
    def get_default(cls, value):
        default = super().get_default(value)
        default.label = value
        return default


class EventSource(CachedEnum):
    """事件来源，需要保持唯一"""

    # CICD
    BKCI: str = "BKCI"
    # K8S
    BCS: str = "BCS"
    # HOST
    HOST: str = "HOST"

    @classmethod
    def choices(cls):
        return [(cls.BCS.value, cls.BCS.value), (cls.BKCI.value, cls.BKCI.value), (cls.HOST.value, cls.HOST.value)]

    @cached_property
    def label(self):
        return str({self.BKCI: _("蓝盾"), self.BCS: _("BCS"), self.HOST: _("主机")}.get(self, self.value))

    @classmethod
    def get_default(cls, value):
        default = super().get_default(value)
        default.label = value
        return default
