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

from enum import Enum

# 默认的间隔, 默认为60秒
DEFAULT_EVALUATION_INTERVAL = "60s"
DEFAULT_RULE_TYPE = "prometheus"


class RecordRuleStatus(Enum):
    """预计算状态"""

    CREATED = "created"
    RUNNING = "running"
    DELETED = "deleted"


class BkDataFlowStatus(Enum):
    """流程状态"""

    NO_ACCESS = "no-access"
    NO_CREATE = "no-create"
    NO_START = "no-start"

    ACCESSING = "accessing"
    CREATING = "creating"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"

    ACCESS_FAILED = "access-failed"
    CREATE_FAILED = "create-failed"
    START_FAILED = "start-failed"
    STOP_FAILED = "stop-failed"
