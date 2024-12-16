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

from django.utils.translation import gettext_lazy as _

from core.errors import Error


class RelatedAlertNotFoundError(Error):
    status_code = 500
    code = 3326001
    name = _("获取告警错误")
    message_tpl = _("获取处理动作({action_id})的关联告警失败")


class ActionAlreadyFinishedError(Error):
    status_code = 500
    code = 3326002
    name = _("处理已执行")
    message_tpl = _("当前处理动作({action_id})已经完成")
