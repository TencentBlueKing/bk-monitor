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
import re

from typing import List
from django.utils.translation import ugettext_lazy as _


from apps.exceptions import ValidationError
from apps.log_desensitize.handlers.desensitize_operator import OPERATOR_MAPPING
from apps.log_desensitize.handlers.entity.desensitize_config_entity import DesensitizeConfigEntity
from apps.log_desensitize.models import DesensitizeRule


class DesensitizeHandler(object):
    """
    日志脱敏工厂
    接收配置规则的列表, 进行规则匹配, 并调用相关的脱敏算子进行处理, 规则列表以流水线的方式处理
    """

    def __init__(self, desensitize_config_list: List[DesensitizeConfigEntity]):
        self.desensitize_config_list = desensitize_config_list
        rule_ids = [_config.rule_id for _config in desensitize_config_list if _config.rule_id]

        # 初始化脱敏规则实例
        if rule_ids:
            desensitize_rule_obj = DesensitizeRule.objects.filter(id__in=rule_ids)
            desensitize_rule = {obj.id: obj for obj in desensitize_rule_obj}
        else:
            desensitize_rule = {}

        # 针对每一个配置，生成一个包含 "匹配模式", "匹配字段", "脱敏算子实例"
        for entity in self.desensitize_config_list:

            # 查询对应的脱敏规则 实例化算子
            if entity.rule_id:
                rule_obj = desensitize_rule.get(entity.rule_id, DesensitizeRule)
                entity.operator = rule_obj.operator
                entity.params = rule_obj.params
                entity.match_pattern = rule_obj.match_pattern or ""

            # 生成配置对应的算子实例
            if entity.operator not in OPERATOR_MAPPING.keys():
                raise ValidationError(_("{} 算子能力尚未实现").format(entity.operator))

            operator_cls = OPERATOR_MAPPING[entity.operator]

            # 实例化算子
            entity.operator_obj = operator_cls() if not entity.params else operator_cls(**entity.params)

    def transform_text(self, text: str = None):
        """
        纯文本格式处理 兼容快速调试
        """

        if not text:
            return ""

        # 文本处理
        for entity in self.desensitize_config_list:
            text = self._match_transform(entity, text)

        return text

    def transform_dict(self, log_content: dict = None):
        """
        params: log_content 需要处理的文本内容
        处理字典类型 单条log内容的格式 {"field_a": 12345, "field_b": "abc"}
        根据脱敏配置列表 desensitize_config_list 以流水线方式处理 log 字段的内容
        """

        for entity in self.desensitize_config_list:

            text = log_content.get(entity.field_name, None)

            if text is None:
                continue

            # 文本处理
            text = self._match_transform(entity, str(text))

            # 重新赋值 log_content
            log_content[entity.field_name] = text

        return log_content

    @staticmethod
    def _match_transform(entity: DesensitizeConfigEntity, text: str = ""):
        """
        公共方法 匹配文本并进行算子处理
        """
        pattern = entity.match_pattern or ""
        match = re.match(pattern, text)
        context = match.groupdict() if match else {}

        # 文本处理
        text = entity.operator_obj.transform(text, context)

        return text
