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


class EventOperate(object):
    """事件操作类型"""

    ACK = "ACK"
    ANOMALY_NOTICE = "ANOMALY_NOTICE"
    CREATE = "CREATE"
    CONVERGE = "CONVERGE"
    RECOVER = "RECOVER"
    CLOSE = "CLOSE"
    CREATE_ORDER = "CREATE_ORDER"


class EventStatus(object):
    """
    事件状态
    """

    CLOSED = "CLOSED"  # 已失效，对应数据表 10
    RECOVERED = "RECOVERED"  # 已恢复，对应数据表 20
    ABNORMAL = "ABNORMAL"  # 异常事件，对应数据表 30
    ABNORMAL_ACK = "ABNORMAL_ACK"  # 未恢复已确认，对应(status=EventStatus.ABNORMAL, is_ack=True)


class AlertStatus(object):
    """
    通知状态
    """

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SHIELDED = "SHIELDED"


class ConfigChangedStatus(object):
    """
    策略配置变更状态
    """

    UNCHANGED = "UNCHANGED"
    UPDATED = "UPDATED"
    DELETED = "DELETED"


class EventActionStatus(object):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"
    SHIELDED = "SHIELDED"
