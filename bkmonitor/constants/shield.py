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


class ScopeType(object):
    INSTANCE = "instance"
    IP = "ip"
    NODE = "node"
    BIZ = "biz"


class ShieldStatus(object):
    SHIELDED = 1
    EXPIRED = 2
    REMOVED = 3


class ShieldCategory(object):
    SCOPE = "scope"
    STRATEGY = "strategy"
    EVENT = "event"
    ALERT = "alert"
    DIMENSION = "dimension"

    CHOICES = [SCOPE, STRATEGY, EVENT, ALERT, DIMENSION]


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
