# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from django.utils.translation import gettext as _


class ScopeType(object):
    INSTANCE = "instance"
    IP = "ip"
    NODE = "node"
    BIZ = "biz"
    DYNAMIC_GROUP = "dynamic_group"


SCOPE_TYPE_NAME_MAPPING = {
    ScopeType.INSTANCE: _("服务实例"),
    ScopeType.IP: _("主机"),
    ScopeType.NODE: _("节点"),
    ScopeType.BIZ: _("业务"),
    ScopeType.DYNAMIC_GROUP: _("动态分组"),
}


class ShieldStatus(object):
    SHIELDED = 1
    EXPIRED = 2
    REMOVED = 3


SHIELD_STATUS_NAME_MAPPING = {
    ShieldStatus.SHIELDED: _("屏蔽中"),
    ShieldStatus.EXPIRED: _("已过期"),
    ShieldStatus.REMOVED: _("被解除"),
}


class ShieldCategory(object):
    SCOPE = "scope"
    STRATEGY = "strategy"
    EVENT = "event"
    ALERT = "alert"
    DIMENSION = "dimension"

    CHOICES = [SCOPE, STRATEGY, EVENT, ALERT, DIMENSION]


SHIELD_CATEGORY_NAME_MAPPING = {
    ShieldCategory.SCOPE: _("范围屏蔽"),
    ShieldCategory.DIMENSION: _("维度屏蔽"),
    ShieldCategory.STRATEGY: _("策略屏蔽"),
    ShieldCategory.ALERT: _("告警事件屏蔽"),
}


class ShieldCycleType(object):
    ONCE = 1  # 一次
    EVERYDAY = 2  # 每天
    EVERY_WEEK = 3  # 每周
    EVERY_MONTH = 4  # 每月


class ShieldType(object):
    SAAS_CONFIG = "saas_config"
    HOST_STATUS = "host_status"
    HOST_TARGET = "host_target"
    ALARM_TIME = "alarm_time"
