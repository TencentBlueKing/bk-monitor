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

HOUR = 60 * 60

ROBOT_AI_SETTING_KEY = "robot"
LATEST_FETCH_TIME_KEY = "latest_fetch_time"

MIN_FETCH_TIME_RANGE = HOUR  # 最小拉取间隔一小时
MAX_FETCH_TIME_RANGE = HOUR * 24  # 最大拉取间隔一天


class RobotLevel:
    RED = 1
    YELLOW = 2
    BLUE = 3


DISPLAY_TIME_LEVEL = [
    HOUR * 1,
    HOUR * 3,
    HOUR * 6,
    HOUR * 12,
    HOUR * 24,
]
