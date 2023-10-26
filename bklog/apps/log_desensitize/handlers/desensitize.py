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

from django.db.models import Q
from django.utils.translation import ugettext_lazy as _

from apps.exceptions import ValidationError
from apps.log_desensitize.exceptions import (
    DesensitizeRuleNotExistException,
    DesensitizeRuleNameExistException,
    DesensitizeRuleRegexCompileException
)
from apps.log_desensitize.handlers.desensitize_operator import OPERATOR_MAPPING
from apps.log_desensitize.models import DesensitizeRule
from apps.models import model_to_dict


class DesensitizeHandler(object):
    """
    日志脱敏工厂
    接收配置规则的列表, 进行规则匹配, 并调用相关的脱敏算子进行处理, 规则列表以流水线的方式处理
    """

    def __init__(self, desensitize_config_info):

        # 构建字段绑定的规则mapping {"field_a": [{"rule_id":1, "operator": "mask_shield"}]}
        self.field_rule_mapping = dict()

        self.rule_ids = [_info["rule_id"] for _info in desensitize_config_info if _info.get("rule_id")]

        # 过滤出当前脱敏配置的关联规则中生效的规则
        self.effective_rule_ids = [] if not self.rule_ids else list(DesensitizeRule.objects.filter(id__in=self.rule_ids, is_active=True).values_list("id", flat=True))

        # 脱敏配置的标志序号
        sign_num = 1

        for _config in desensitize_config_info:

            # 如果绑定了脱敏规则  判断绑定的规则当前是否删除或者未启用
            rule_id = _config.get("rule_id")

            if rule_id and rule_id not in self.effective_rule_ids:
                continue

            field_name = _config["field_name"]

            operator = _config["operator"]

            if not operator or not field_name:
                continue

            # 生成配置对应的算子实例
            if operator not in OPERATOR_MAPPING.keys():
                raise ValidationError(_("{} 算子能力尚未实现").format(operator))

            if field_name not in self.field_rule_mapping.keys():
                self.field_rule_mapping[field_name] = list()

            operator_cls = OPERATOR_MAPPING[operator]

            # 实例化算子
            _config["operator_obj"] = operator_cls() if not _config["params"] else operator_cls(**_config["params"])

            # 编译正则表达式
            try:
                _config["__regex__"] = None if not _config.get("match_pattern") else re.compile(_config["match_pattern"])
            except re.error:
                raise DesensitizeRuleRegexCompileException(
                    DesensitizeRuleRegexCompileException.MESSAGE.format(
                        rule_id=rule_id,
                        pattern=_config["match_pattern"]
                    )
                )

            # 添加配置序号 兼容没有绑定脱敏规则的纯配置脱敏模式
            _config["__id__"] = sign_num

            self.field_rule_mapping[field_name].append(_config)

            sign_num += 1

        if self.field_rule_mapping:
            # 对字段绑定的规则按照优先级排序 sort_index 越小的优先级越高
            for _field_name, _config in self.field_rule_mapping.items():
                self.field_rule_mapping[_field_name] = sorted(_config, key=lambda x: x["sort_index"])

    def transform_dict(self, log_content: dict = None):
        """
        params: log_content 需要处理的文本内容
        处理字典类型 单条log内容的格式 {"field_a": 12345, "field_b": "abc"}
        根据脱敏配置列表 desensitize_config_list 以流水线方式处理 log 字段的内容
        """
        if not self.field_rule_mapping or not log_content:
            return log_content

        for _field, _rules in self.field_rule_mapping.items():
            text = log_content.get(_field)
            if not text or not _rules:
                continue
            log_content[_field] = self.transform(log=str(text), rules=_rules)

        return log_content

    @staticmethod
    def _match_transform(rule: dict, text: str = "", context: dict = None):
        """
        公共方法 匹配文本并进行算子处理
        """

        # 文本处理
        text = rule["operator_obj"].transform(text, context)

        return text

    @staticmethod
    def find_substrings_by_rule(log: str, rule: dict):
        """
        找出所有匹配正则的起止位置
        """

        # 匹配表达式未指定的情况下 默认整个字段全部处理
        regex = rule.get("__regex__")
        if not regex:
            return [
                {
                    "src": log,
                    "start": 0,
                    "end": len(str(log)),
                    "group_dict": dict(),
                    "__id__": rule["__id__"],
                    "rule": rule
                }
            ]

        # 使用finditer()函数找到所有匹配的子串
        matches = regex.finditer(log)

        results = []
        # 输出匹配的子串及其起止位置
        for match in matches:
            results.append({
                "src": match.group(),
                "start": match.start(),
                "end": match.end(),
                "group_dict": match.groupdict(),
                "__id__": rule["__id__"],
                "rule": rule
            })
        return results

    @staticmethod
    def merge_substrings(first, second):
        """
        合并子串匹配结果，剔除出现重叠的子串
        """

        def is_overlap(item1, item2):
            return not (item1["start"] >= item2["end"] or item1["end"] < item2["start"])

        result = first.copy()

        for second_item in second:
            is_overlapping = False

            for first_item in first:
                if is_overlap(first_item, second_item):
                    is_overlapping = True
                    break

            if not is_overlapping:
                result.append(second_item)

        return result

    def transform(self, log: str, rules: list):
        substrings = []
        for rule in rules:
            rule_substrings = self.find_substrings_by_rule(log, rule)
            substrings = self.merge_substrings(substrings, rule_substrings)
        substrings.sort(key=lambda x: x["start"])

        last_end = 0
        outputs = []
        for substring in substrings:
            outputs.append(log[last_end:substring["start"]])
            # 文本处理
            _text = self._match_transform(substring["rule"], str(substring["src"]), substring["group_dict"])
            outputs.append(_text)
            last_end = substring["end"]

        # 末尾补充
        outputs.append(log[last_end:len(log)])
        return "".join(outputs)


class DesensitizeRuleHandler(object):
    """
    脱敏规则
    """

    def __init__(self, rule_id=None):
        self.rule_id = rule_id
        self.data = None
        if rule_id:
            try:
                self.data = DesensitizeRule.objects.get(id=self.rule_id)
            except DesensitizeRule.DoesNotExist:
                raise DesensitizeRuleNotExistException(
                    DesensitizeRuleNotExistException.MESSAGE.format(id=self.rule_id)
                )

    def create_or_update(self, params: dict):
        """
        创建更新脱敏规则
        """
        # 重名校验
        query_params = {"rule_name": params["rule_name"]}

        if not self.data:
            # 创建
            if params["is_public"]:
                query_params.update({"is_public": True})
            else:
                query_params.update({"space_uid": params["space_uid"]})
            _qs = DesensitizeRule.objects.filter(**query_params)
        else:
            # 更新
            if self.data.is_public:
                query_params.update({"is_public": True})
            else:
                query_params.update({"space_uid": self.data.space_uid})
            _qs = DesensitizeRule.objects.filter(**query_params).exclude(id=self.rule_id)

        if _qs.exists():
            raise DesensitizeRuleNameExistException(
                DesensitizeRuleNameExistException.MESSAGE.format(name=params["rule_name"])
            )

        model_field = {
            "rule_name": params["rule_name"],
            "operator": params["operator"],
            "params": params["operator_params"],
            "match_pattern": params["match_pattern"],
            "match_fields": params["match_fields"],
        }

        if not self.data:
            # 创建脱敏规则
            model_field.update(
                {
                    "is_public": params["is_public"],
                    "space_uid": params.get("space_uid") or "",
                }
            )
            obj = DesensitizeRule.objects.create(**model_field)
            return model_to_dict(obj)
        else:
            # 更新脱敏规则
            DesensitizeRule.objects.filter(id=self.rule_id).update(**model_field)
            return {"id": self.rule_id}

    def list(self, is_public: bool, space_uid: str):
        """
        脱敏规则列表
        """
        objs = DesensitizeRule.objects.filter().all()

        if space_uid:
            # 返回全局规则&当前业务下的规则
            objs.filter(Q(is_public=is_public) | Q(space_uid=space_uid))
        else:
            # 只返回全局规则
            objs.filter(is_public=is_public)

        return [model_to_dict(obj) for obj in objs]

    def retrieve(self):
        """脱敏规则详情"""
        return model_to_dict(self.data)

    def destroy(self):
        """脱敏规则删除"""
        self.data.delete()
