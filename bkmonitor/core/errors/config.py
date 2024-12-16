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
"""系统配置模块错误"""


from django.utils.translation import gettext_lazy as _lazy

from core.errors import Error


class MetricMetaError(Error):
    status_code = 400
    code = 3322001
    name = _lazy("权限配置错误")
    message_tpl = _lazy("权限配置错误：{msg}")


class NoUpdatePermission(Error):
    code = 3322002
    name = _lazy("没有修改权限")
    message_tpl = _lazy("{permission}的权限不允许修改")
