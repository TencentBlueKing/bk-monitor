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
采集配置模块错误
"""

from django.utils.translation import gettext_lazy as _

from core.errors import Error


class CollectingError(Error):
    status_code = 400
    code = 3311001
    name = _("采集配置模块错误")
    message_tpl = _("采集配置模块错误：{msg}")


class CollectConfigNotExist(CollectingError):
    code = 3311003
    name = _("采集配置ID不存在")
    message_tpl = _("采集配置ID不存在：{msg}")


class CollectConfigNeedUpgrade(CollectingError):
    code = 3311004
    name = _("采集配置需要升级")
    message_tpl = _("采集配置需要升级：{msg}")


class CollectConfigNotNeedUpgrade(CollectingError):
    code = 3311005
    name = _("采集配置不需要升级")
    message_tpl = _("采集配置不需要升级：{msg}")


class MetricNotExist(CollectingError):
    code = 3311006
    name = _("指标不存在")
    message_tpl = _("指标不存在：{metric}")


class DeleteCollectConfigError(CollectingError):
    code = 3311007
    name = _("删除采集配置失败")
    message_tpl = _("删除采集配置失败: {msg}")


class LockTimeout(CollectingError):
    code = 3311008
    name = _("获取采集配置锁超时")
    message_tpl = "{msg}"


class RequestNodeManError(CollectingError):
    code = 3311009
    name = _("请求节点管理出现错误")
    message_tpl = _("请求节点管理出现错误: {msg}")


class ToggleConfigStatusError(CollectingError):
    code = 3311010
    name = _("采集配置状态切换错误")
    message_tpl = _("采集配置状态切换错误: {msg}")


class CollectConfigRollbackError(CollectingError):
    code = 3311011
    name = _("采集配置无法回滚")
    message_tpl = _("采集配置无法回滚：{msg}")


class SubscriptionStatusError(CollectingError):
    code = 3311012
    name = _("采集配置状态查询错误")
    message_tpl = _("采集配置状态查询错误：{msg}")


class CollectConfigParamsError(CollectingError):
    code = 3311013
    name = _("采集配置参数错误")
    message_tpl = _("采集配置参数错误：{msg}")
