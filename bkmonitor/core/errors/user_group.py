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

from core.errors import Error


class UserGroupError(Error):
    status_code = 400
    code = 3312001
    name = _lazy("告警组模块错误")
    message_tpl = _lazy("告警组模块错误：{msg}")


class UserGroupNotExist(UserGroupError):
    code = 3312002
    name = _lazy("告警组ID不存在")
    message_tpl = _lazy("告警组ID错误: 不存在的告警组，{msg}")


class UserGroupNameExist(UserGroupError):
    code = 3312003
    name = _lazy("告警组名称已存在")
    message_tpl = _lazy("告警组名称重复错误: 告警组名称已存在")


class UserGroupHasStrategy(UserGroupError):
    code = 3312004
    name = _lazy("告警组无法删除")
    message_tpl = _lazy("告警组无法删除: 告警组存在关联策略")


class ContentMessageError(UserGroupError):
    code = 3312005
    name = _lazy("创建告警组失败")
    message_tpl = _lazy("创建告警组失败：填写内容不合规范")


class DutyRuleNameExist(UserGroupError):
    code = 3312006
    name = _lazy("轮值规则名称已存在")
    message_tpl = _lazy("轮值规则名称重复错误: 轮值规则名称已存在")
