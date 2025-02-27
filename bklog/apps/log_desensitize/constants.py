# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""
from django.utils.translation import gettext_lazy as _

from apps.utils import ChoicesEnum


class DesensitizeOperator(ChoicesEnum):
    """
    脱敏算子
    """

    MASK_SHIELD = "mask_shield"
    TEXT_REPLACE = "text_replace"

    _choices_labels = (
        (MASK_SHIELD, _("掩码屏蔽")),
        (TEXT_REPLACE, _("文本替换")),
    )


MODEL_TO_DICT_EXCLUDE_FIELD = ["id", "created_at", "created_by", "updated_at", "updated_by"]


class ScenarioEnum(ChoicesEnum):
    LOG_CUSTOM = "log_custom"
    LOG = "log"
    ES = "es"
    BKDATA = "bkdata"
    INDEX_SET = "index_set"

    _choices_labels = (
        (LOG_CUSTOM, _("自定义上报")),
        (LOG, _("采集接入")),
        (ES, _("第三方ES")),
        (BKDATA, _("数据平台")),
        (INDEX_SET, _("索引集")),
    )


class DesensitizeRuleStateEnum(ChoicesEnum):
    ADD = "add"
    UPDATE = "update"
    DELETE = "delete"
    NORMAL = "normal"

    _choices_labels = (
        (ADD, _("新增")),
        (UPDATE, _("更新")),
        (DELETE, _("删除")),
        (NORMAL, _("正常")),
    )


class DesensitizeRuleTypeEnum(ChoicesEnum):
    PUBLIC = "public"
    SPACE = "space"
    ALL = "all"

    _choices_labels = (
        (PUBLIC, _("全局下规则")),
        (SPACE, _("业务下规则")),
        (ALL, _("全部")),
    )
