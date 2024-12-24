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


class IncidentError(Error):
    status_code = 500
    code = 3336001
    name = _("故障模块错误")
    message_tpl = _("故障模块错误")


class IncidentNotFoundError(Error):
    status_code = 404
    code = 3336002
    name = _("故障不存在")
    message_tpl = _("故障 ({id}) 对应的故障信息不存在")


class IncidentEntityNotFoundError(Error):
    status_code = 404
    code = 3336003
    name = _("实体ID不在当前图谱中")
    message_tpl = _("实体ID ({entity_id}) 不在当前图谱中")
