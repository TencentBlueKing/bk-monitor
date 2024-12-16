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


from django.utils.translation import gettext_lazy as _lazy

from monitor_web.models.plugin import CollectorPluginMeta


class Status(object):
    """
    采集配置状态
    """

    STARTING = "STARTING"
    STARTED = "STARTED"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    DEPLOYING = "DEPLOYING"
    AUTO_DEPLOYING = "AUTO_DEPLOYING"
    PREPARING = "PREPARING"


class CollectStatus(object):
    SUCCESS = "SUCCESS"
    RUNNING = "RUNNING"
    FAILED = "FAILED"
    PENDING = "PENDING"
    UNKNOWN = "UNKNOWN"
    NODATA = "NODATA"


class OperationType(object):
    ROLLBACK = "ROLLBACK"
    UPGRADE = "UPGRADE"
    CREATE = "CREATE"
    EDIT = "EDIT"
    START = "START"
    STOP = "STOP"
    ADD_DEL = "ADD_DEL"


class OperationResult(object):
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    FAILED = "FAILED"
    DEPLOYING = "DEPLOYING"
    PREPARING = "PREPARING"


class TaskStatus(object):
    PENDING = "PENDING"
    FAILED = "FAILED"
    WARNING = "WARNING"
    SUCCESS = "SUCCESS"
    STOPPED = "STOPPED"
    RUNNING = "RUNNING"
    DEPLOYING = "DEPLOYING"
    AUTO_DEPLOYING = "AUTO_DEPLOYING"
    STOPPING = "STOPPING"
    STARTING = "STARTING"
    PREPARING = "PREPARING"


COLLECT_TYPE_CHOICES = CollectorPluginMeta.PLUGIN_TYPE_CHOICES + (("log", _lazy("日志采集")),)

# 复合操作类型，在采集配置下发页和执行详情页显示标签
COMPLEX_OPETATION_TYPE = [OperationType.EDIT, OperationType.ADD_DEL, OperationType.ROLLBACK]

# 简单操作类型，在采集配置下发页和执行详情页不显示标签
SIMPLE_OPETATION_TYPE = [OperationType.CREATE, OperationType.UPGRADE, OperationType.START, OperationType.STOP]
