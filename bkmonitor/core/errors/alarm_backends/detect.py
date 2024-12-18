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

from core.errors.alarm_backends import DetectError


class InvalidDataPoint(DetectError):
    code = 3352001
    name = _lazy("无效的检测数据")
    message_tpl = _lazy("无效的检测数据：{data_point}")


class InvalidAlgorithmsConfig(DetectError):
    code = 3352002
    name = _lazy("无效的检测算法配置")
    message_tpl = _lazy("无效的检测算法配置：{config}")


class InvalidThresholdConfig(InvalidAlgorithmsConfig):
    code = 3352003
    name = _lazy("无效的静态阈值算法配置")
    message_tpl = _lazy("无效的静态阈值算法配置：{config}")


class InvalidSimpleRingRatioConfig(InvalidAlgorithmsConfig):
    code = 3352004
    name = _lazy("无效的简易环比算法配置")
    message_tpl = _lazy("无效的简易环比算法配置：{config}")


class InvalidSimpleYearRoundConfig(InvalidAlgorithmsConfig):
    code = 3352005
    name = _lazy("无效的简易同比算法配置")
    message_tpl = _lazy("无效的简易同比算法配置：{config}")


class InvalidAdvancedRingRatioConfig(InvalidAlgorithmsConfig):
    code = 3352006
    name = _lazy("无效的高级环比算法配置")
    message_tpl = _lazy("无效的高级环比算法配置：{config}")


class InvalidAdvancedYearRoundConfig(InvalidAlgorithmsConfig):
    code = 3352007
    name = _lazy("无效的高级同比算法配置")
    message_tpl = _lazy("无效的高级同比算法配置：{config}")


class HistoryDataNotExists(DetectError):
    code = 3352008
    name = _lazy("历史数据不存在")
    message_tpl = _lazy("历史数据不存在：item:{item_id}, timestamp:{timestamp}")
