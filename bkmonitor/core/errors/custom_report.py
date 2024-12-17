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


class CustomEventValidationError(Error):
    status_code = 200
    code = 3335001
    name = _lazy("事件分组数据校验不通过")
    message_tpl = "{msg}"


class CustomTSValidationError(Error):
    status_code = 200
    code = 3335005
    name = _lazy("自定义时序数据校验不通过")
    message_tpl = "{msg}"


class CustomValidationNameError(Error):
    status_code = 200
    code = 3335006
    name = _lazy("自定义名称校验不通过")
    message_tpl = "{msg}"


class CustomValidationLabelError(Error):
    status_code = 200
    code = 3335007
    name = _lazy("自定义英文名校验不通过")
    message_tpl = "{msg}"
