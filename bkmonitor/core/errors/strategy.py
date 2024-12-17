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
"""
策略配置模块错误
"""


from django.utils.translation import gettext_lazy as _lazy

from core.errors import Error


class StrategyError(Error):
    status_code = 400
    code = 3313001
    name = _lazy("策略配置模块错误")
    message_tpl = _lazy("策略配置模块错误：{msg}")


class StrategyConfigInitError(StrategyError):
    code = 3313002
    name = _lazy("StrategyConfig实例初始化错误")
    message_tpl = _lazy("实例化StrategyConfig的参数须为策略配置id")


class StrategyNotExist(StrategyError):
    code = 3313003
    name = _lazy("策略配置不存在")
    message_tpl = _lazy("策略配置不存在")


class StrategyTargetStructureError(StrategyError):
    code = 3313004
    name = _lazy("监控对象数据结构错误")
    message_tpl = _lazy("监控对象数据结构错误: {target}")


class TargetParseError(StrategyError):
    code = 3313005
    name = _lazy("监控目标解析失败")
    message_tpl = _lazy("监控目标解析失败: {target}")


class EmptyTargetError(StrategyError):
    code = 3313006
    name = _lazy("监控目标为空")
    message_tpl = _lazy("监控目标为空")


class CreateStrategyError(StrategyError):
    code = 3313008
    name = _lazy("创建策略配置失败")
    message_tpl = _lazy("创建策略配置失败：{msg}")


class UpdateStrategyError(StrategyError):
    code = 3313009
    name = _lazy("修改策略配置失败")
    message_tpl = _lazy("修改策略配置失败：{msg}")


class IntelligentModelNotFound(StrategyError):
    code = 3313010
    name = _lazy("智能异常检测模型不存在")
    message_tpl = _lazy("智能异常检测模型不存在：{model_id}")


class StrategyNameExist(StrategyError):
    code = 3313011
    name = _lazy("策略名称已存在")
    message_tpl = _lazy("策略名称 [{name}] 已存在")
