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


class NoticeGroupError(Error):
    status_code = 400
    code = 3312001
    name = _lazy("通知组模块错误")
    message_tpl = _lazy("通知组模块错误：{msg}")


class NoticeGroupNotExist(NoticeGroupError):
    code = 3312002
    name = _lazy("通知组ID不存在")
    message_tpl = _lazy("通知组ID错误: 不存在的通知组，{msg}")


class NoticeGroupNameExist(NoticeGroupError):
    code = 3312003
    name = _lazy("通知组名称已存在")
    message_tpl = _lazy("通知组名称重复错误: 通知组名称已存在")


class NoticeGroupHasStrategy(NoticeGroupError):
    code = 3312004
    name = _lazy("通知组无法删除")
    message_tpl = _lazy("通知组无法删除: 通知组存在关联策略")


class ContentMessageError(NoticeGroupError):
    code = 3312005
    name = _lazy("创建通知组失败")
    message_tpl = _lazy("创建通知组失败：填写内容不合规范")
