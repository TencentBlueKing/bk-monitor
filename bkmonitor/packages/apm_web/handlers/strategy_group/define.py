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


class StrategyLabelType(Enum):
    # 用于标识一个策略的归属，便于后续完善 APM 告警治理
    # 场景层
    SCENE: str = "APM-APP"
    # 服务层
    SERVICE: str = "APM-SERVICE"
    # 系统层
    SYSTEM: str = "APM-SYSTEM"
    # 告警类别
    ALERT_TYPE: str = "APM-ALERT"

    @classmethod
    def scene_label(cls, app_name: str) -> str:
        return f"{cls.SCENE.value}({app_name})"

    @classmethod
    def service_label(cls, service_name: str) -> str:
        return f"{cls.SERVICE.value}({service_name})"

    @classmethod
    def system_label(cls, system: str) -> str:
        return f"{cls.SYSTEM.value}({system})"

    @classmethod
    def alert_type(cls, alert_type: str) -> str:
        return f"{cls.ALERT_TYPE.value}({alert_type})"


class GroupType(Enum):
    RPC: str = "rpc"

    @classmethod
    def choices(cls):
        return [(cls.RPC.value, cls.RPC.value)]


class AlgorithmType(Enum):
    THRESHOLD = "Threshold"
    ADVANCE_YEAR_ROUND = "AdvancedYearRound"
