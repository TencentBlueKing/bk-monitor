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
import copy
import re
from typing import List

from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.exceptions import ValidationError
from apps.log_databus.models import CollectorConfig
from apps.log_desensitize.constants import DesensitizeRuleTypeEnum, ScenarioEnum
from apps.log_desensitize.exceptions import (
    DesensitizeRegexDebugNoMatchException,
    DesensitizeRuleNameExistException,
    DesensitizeRuleNotExistException,
    DesensitizeRuleRegexCompileException,
)
from apps.log_desensitize.handlers.desensitize_operator import OPERATOR_MAPPING
from apps.log_desensitize.models import DesensitizeFieldConfig, DesensitizeRule
from apps.log_desensitize.utils import expand_nested_data
from apps.log_search.constants import CollectorScenarioEnum
from apps.log_search.models import LogIndexSet, Scenario
from apps.models import model_to_dict


class DesensitizeHandler(object):
    """
    日志脱敏工厂
    接收配置规则的列表, 进行规则匹配, 并调用相关的脱敏算子进行处理, 规则列表以流水线的方式处理
    """

    def __init__(self, desensitize_config_info):
        # 构建字段绑定的规则mapping
        self.field_rule_mapping = dict()
        self.rules = list()

        rule_ids = [_info["rule_id"] for _info in desensitize_config_info if _info.get("rule_id")]

        # 过滤出当前脱敏配置的关联规则中启用的规则 包含已删除的规则
        effective_rule_objs = DesensitizeRule.origin_objects.filter(id__in=rule_ids, is_active=True)
        effective_rule_mapping = {_obj.id: model_to_dict(_obj) for _obj in effective_rule_objs}

        for _config in desensitize_config_info:
            # 如果绑定了脱敏规则  判断绑定的规则当前是否启用
            rule_id = _config.get("rule_id")

            if rule_id and rule_id not in effective_rule_mapping:
                continue

            field_name = _config.get("field_name")

            if rule_id and field_name:
                match_fields = effective_rule_mapping[rule_id]["match_fields"]
                if match_fields and field_name not in match_fields:
                    continue

            operator = _config["operator"]

            if not operator:
                continue

            # 生成配置对应的算子实例
            if operator not in OPERATOR_MAPPING:
                raise ValidationError(_("{} 算子能力尚未实现").format(operator))

            operator_cls = OPERATOR_MAPPING[operator]

            # 实例化算子
            _config["operator_obj"] = operator_cls() if not _config["params"] else operator_cls(**_config["params"])

            # 编译正则表达式
            try:
                _config["__regex__"] = (
                    None if not _config.get("match_pattern") else re.compile(_config["match_pattern"])
                )
            except re.error:
                raise DesensitizeRuleRegexCompileException(
                    DesensitizeRuleRegexCompileException.MESSAGE.format(
                        rule_id=rule_id, pattern=_config["match_pattern"]
                    )
                )

            if field_name and field_name not in self.field_rule_mapping:
                self.field_rule_mapping[field_name] = list()
            if field_name:
                self.field_rule_mapping[field_name].append(_config)
            else:
                self.rules.append(_config)

        if self.field_rule_mapping:
            # 对字段绑定的规则按照优先级排序 sort_index 越小的优先级越高
            for _field_name, _config in self.field_rule_mapping.items():
                self.field_rule_mapping[_field_name] = sorted(_config, key=lambda x: x["sort_index"])

        if self.rules:
            self.rules = sorted(self.rules, key=lambda x: x["sort_index"])

    def transform_text(self, text: str, is_highlight: bool = False):
        """
        处理文本类型
        text 文本 -> ‘test log 123456789’
        is_highlight 结果是否高亮处理
        """
        if not self.rules or not text:
            return text

        text = self.transform(log=str(text), rules=self.rules, is_highlight=is_highlight)

        return text

    def transform_dict(self, log_content: dict = None):
        """
        params: log_content 需要处理的文本内容
        处理字典类型 单条log内容的格式 {"field_a": 12345, "field_b": "abc"}
        根据脱敏配置列表 desensitize_config_list 以流水线方式处理 log 字段的内容
        """
        if not self.field_rule_mapping or not log_content:
            return log_content

        for _field, _rules in self.field_rule_mapping.items():
            if _field not in log_content or not _rules:
                continue
            text = log_content[_field]
            log_content[_field] = self.transform(log=str(text), rules=_rules)

        return log_content

    @staticmethod
    def _match_transform(rule: dict, text: str = "", context: dict = None, is_highlight: bool = False):
        """
        公共方法 匹配文本并进行算子处理
        """

        if not is_highlight:
            # 文本处理
            text = rule["operator_obj"].transform(text, context)
        else:
            text_tmp = text
            text = rule["operator_obj"].transform(text, context)
            if text != text_tmp:
                text = f"<mark>{text}</mark>"

        return text

    @staticmethod
    def find_substrings_by_rule(log: str, rule: dict):
        """
        找出所有匹配正则的起止位置
        """

        # 匹配表达式未指定的情况下 默认整个字段全部处理
        regex = rule.get("__regex__")
        if not regex:
            return [{"src": log, "start": 0, "end": len(str(log)), "group_dict": dict(), "rule": rule}]

        # 使用finditer()函数找到所有匹配的子串
        matches = regex.finditer(log)

        results = []
        # 输出匹配的子串及其起止位置
        for match in matches:
            results.append(
                {
                    "src": match.group(),
                    "start": match.start(),
                    "end": match.end(),
                    "group_dict": match.groupdict(),
                    "rule": rule,
                }
            )
        return results

    @staticmethod
    def merge_substrings(first, second):
        """
        合并子串匹配结果，剔除出现重叠的子串
        """

        def is_overlap(item1, item2):
            return not (item1["start"] >= item2["end"] or item1["end"] <= item2["start"])

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

    def transform(self, log: str, rules: list, is_highlight: bool = False):
        substrings = []
        for rule in rules:
            rule_substrings = self.find_substrings_by_rule(log, rule)
            substrings = self.merge_substrings(substrings, rule_substrings)
        substrings.sort(key=lambda x: x["start"])

        last_end = 0
        outputs = []
        for substring in substrings:
            outputs.append(log[last_end : substring["start"]])
            # 文本处理
            _text = self._match_transform(
                rule=substring["rule"],
                text=str(substring["src"]),
                context=substring["group_dict"],
                is_highlight=is_highlight,
            )
            outputs.append(_text)
            last_end = substring["end"]

        # 末尾补充
        outputs.append(log[last_end : len(log)])
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
                raise DesensitizeRuleNotExistException(DesensitizeRuleNotExistException.MESSAGE.format(id=self.rule_id))

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
            model_field.update({"is_public": params["is_public"]})

            if not params["is_public"]:
                model_field.update({"space_uid": params.get("space_uid") or ""})

            obj = DesensitizeRule.objects.create(**model_field)
            return model_to_dict(obj)
        else:
            # 更新脱敏规则
            DesensitizeRule.objects.filter(id=self.rule_id).update(**model_field)
            return {"id": self.rule_id}

    def list(self, space_uid: str, rule_type: str):
        """
        脱敏规则列表
        """
        objs = DesensitizeRule.objects.filter().all()

        if rule_type == DesensitizeRuleTypeEnum.PUBLIC.value:
            # 过滤全局规则
            objs = objs.filter(is_public=True)
        elif rule_type == DesensitizeRuleTypeEnum.SPACE.value:
            # 过滤当前空间业务下规则
            objs = objs.filter(is_public=False, space_uid=space_uid)
        else:
            # 过滤全局+当前空间业务下规则
            objs = objs.filter(Q(is_public=True) | Q(space_uid=space_uid))

        if not objs:
            return []

        result = list()
        # 找出规则ID列表
        rule_ids = list(objs.values_list("id", flat=True))

        desensitize_field_config_objs = DesensitizeFieldConfig.objects.filter(rule_id__in=rule_ids)

        if not desensitize_field_config_objs:
            for _obj in objs:
                _info = model_to_dict(_obj)
                _info["access_num"] = 0
                _info["access_info"] = []
                result.append(_info)
            return result

        # 找出关联的索引集ID集合
        index_set_ids = set(desensitize_field_config_objs.values_list("index_set_id", flat=True))
        index_set_objs = LogIndexSet.objects.filter(index_set_id__in=index_set_ids)

        # 找出接入场景是log的索引集 找出对应的采集项对象
        index_set_obj_log_ids = set(
            index_set_objs.filter(scenario_id=Scenario.LOG).values_list("index_set_id", flat=True)
        )
        collector_config_objs = CollectorConfig.objects.filter(index_set_id__in=index_set_obj_log_ids)

        collector_config_mapping = {_obj.index_set_id: model_to_dict(_obj) for _obj in collector_config_objs}

        scenario_mapping = dict()

        for index_set_obj in index_set_objs:
            _index_set_id = index_set_obj.index_set_id
            index_set_info = model_to_dict(index_set_obj)
            scenario_id = index_set_info["scenario_id"]
            scenario_mapping[_index_set_id] = dict()
            if scenario_id == ScenarioEnum.LOG.value and _index_set_id in collector_config_mapping:
                # 采集接入&自定义上报
                _collector_config_id = collector_config_mapping[_index_set_id]["collector_config_id"]
                _custom_value = CollectorScenarioEnum.CUSTOM.value
                if collector_config_mapping[_index_set_id]["collector_scenario_id"] != _custom_value:
                    # 采集接入
                    scenario_mapping[_index_set_id]["scenario_id"] = ScenarioEnum.LOG.value
                    scenario_mapping[_index_set_id]["show_id"] = _collector_config_id
                else:
                    # 自定义上报
                    scenario_mapping[_index_set_id]["scenario_id"] = ScenarioEnum.LOG_CUSTOM.value
                    scenario_mapping[_index_set_id]["show_id"] = _collector_config_id
            elif scenario_id == ScenarioEnum.LOG.value:
                # 索引集
                scenario_mapping[_index_set_id]["scenario_id"] = ScenarioEnum.INDEX_SET.value
                scenario_mapping[_index_set_id]["show_id"] = _index_set_id
            else:
                # 第三方ES&计算平台
                scenario_mapping[_index_set_id]["scenario_id"] = scenario_id
                scenario_mapping[_index_set_id]["show_id"] = _index_set_id

        relation_mapping = dict()

        for relation_obj in desensitize_field_config_objs:
            _rule_id = relation_obj.rule_id
            _index_set_id = relation_obj.index_set_id
            if _rule_id not in relation_mapping:
                relation_mapping[_rule_id] = {"index_set_ids": set(), "access_info_mapping": dict()}

            if _index_set_id not in scenario_mapping:
                # 过滤排除已删除索引集的信息
                continue

            relation_mapping[_rule_id]["index_set_ids"].add(_index_set_id)

            scenario_info = scenario_mapping[_index_set_id]
            scenario_id = scenario_info["scenario_id"]

            if scenario_id not in relation_mapping[_rule_id]["access_info_mapping"]:
                relation_mapping[_rule_id]["access_info_mapping"][scenario_id] = {"ids": set()}
            relation_mapping[_rule_id]["access_info_mapping"][scenario_id]["ids"].add(scenario_info["show_id"])

        for _obj in objs:
            _info = model_to_dict(_obj)
            rule_id = _info["id"]
            if not relation_mapping or rule_id not in relation_mapping:
                _info["access_num"] = 0
                _info["access_info"] = []
            else:
                # 获取绑定当前规则ID的 索引集列表
                _index_set_ids = relation_mapping[rule_id]["index_set_ids"]
                _access_info = relation_mapping[rule_id]["access_info_mapping"]
                _info["access_num"] = len(_index_set_ids)
                _info["access_info"] = [
                    {"scenario_id": _k, "scenario_name": ScenarioEnum.get_choice_label(_k), "ids": list(_v["ids"])}
                    for _k, _v in _access_info.items()
                ]
            result.append(_info)

        return result

    def retrieve(self):
        """脱敏规则详情"""
        return model_to_dict(self.data)

    def destroy(self):
        """脱敏规则删除"""
        self.data.delete()

    @staticmethod
    def _get_match_info(log_sample: str, match_pattern: str):
        match_info = list()

        if not log_sample or not match_pattern:
            return match_info

        # 使用正则表达式查找所有匹配项
        regex = re.compile(match_pattern)

        matches = regex.finditer(log_sample)

        match_info = [
            {
                "src": match.group(),
                "start": match.start(),
                "end": match.end(),
            }
            for match in matches
        ]

        return match_info

    def rule_debug(self, params: dict):
        """
        规则调试
        """
        match_pattern = params["match_pattern"]
        log_sample = params["log_sample"]
        match_info = self._get_match_info(log_sample, match_pattern)

        if not match_info:
            raise DesensitizeRegexDebugNoMatchException

        # 构建脱敏配置列表
        desensitize_config = [
            {
                "operator": params["operator"],
                "params": params["params"],
                "match_pattern": match_pattern,
                "sort_index": 1,
            }
        ]

        # 文本脱敏 并将结果高亮处理
        result = DesensitizeHandler(desensitize_config).transform_text(text=log_sample, is_highlight=True)

        return result

    def regex_debug(self, log_sample: str, match_pattern: str):
        """
        正则调试
        """
        # 使用正则表达式查找所有匹配项
        match_info = self._get_match_info(log_sample, match_pattern)

        if not match_info:
            raise DesensitizeRegexDebugNoMatchException

        last_end = 0
        outputs = []
        # 遍历所有匹配项，并将它们用<mark>标签高亮显示
        for _m in match_info:
            outputs.append(log_sample[last_end : _m["start"]])
            outputs.append(f"<mark>{_m['src']}</mark>")
            last_end = _m["end"]

        outputs.append(log_sample[last_end : len(log_sample)])

        return {"log": "".join(outputs)}

    def start(self):
        """
        规则启用
        """
        self.data.is_active = True
        self.data.save()

    def stop(self):
        """
        规则停用
        """
        self.data.is_active = False
        self.data.save()

    @staticmethod
    def match_rule(space_uid: str, logs: List[dict], fields: List[str]):
        """
        匹配规则
        """
        # 找出当前业务下和公共的规则
        desensitize_rule_objs = DesensitizeRule.objects.filter(
            Q(Q(space_uid=space_uid) | Q(is_public=True)), is_active=True
        ).order_by("-is_public")

        desensitize_rule_info = [model_to_dict(_obj) for _obj in desensitize_rule_objs]

        res = dict()

        for _field in fields:
            if _field not in res:
                res[_field] = list()
            _hit_rule_ids = set()
            if not desensitize_rule_info:
                continue
            for _log in logs:
                _log = expand_nested_data(_log)
                if _field not in _log:
                    continue
                _text = str(_log[_field])
                for _rule in desensitize_rule_info:
                    match_fields = _rule["match_fields"]
                    match_pattern = _rule["match_pattern"]
                    if match_fields and match_pattern:
                        # 规则同时指定匹配字段名和正则  两者都匹配上 -> 命中
                        if _field not in match_fields:
                            continue
                        try:
                            if not _text or not re.search(match_pattern, _text):
                                continue
                        except re.error:
                            continue
                    elif match_fields and not match_pattern:
                        # 字段匹配上 -> 命中
                        if _field not in match_fields:
                            continue
                    elif not match_fields and match_pattern:
                        # 正则匹配上 -> 命中
                        try:
                            if not re.search(match_pattern, _text):
                                continue
                        except re.error:
                            continue
                    else:
                        continue

                    # 命中
                    if _rule["id"] not in _hit_rule_ids:
                        res[_field].append(
                            {
                                "rule_id": _rule["id"],
                                "rule_name": _rule["rule_name"],
                                "operator": _rule["operator"],
                                "params": _rule["params"],
                                "match_pattern": _rule["match_pattern"],
                                "match_fields": _rule["match_fields"],
                            }
                        )
                    _hit_rule_ids.add(_rule["id"])

        return res

    @staticmethod
    def preview(logs: List[dict], field_configs: List[dict], text_fields: List[str]):
        """
        脱敏预览
        """
        rule_ids = set()
        field_names = set()
        for _config in field_configs:
            field_names.add(_config["field_name"])
            for _rule in _config["rules"]:
                if _rule.get("rule_id"):
                    rule_ids.add(_rule["rule_id"])

        desensitize_rule_objs = DesensitizeRule.origin_objects.filter(id__in=rule_ids)
        desensitize_rule_info = {_obj.id: model_to_dict(_obj) for _obj in desensitize_rule_objs}

        # 构建脱敏配置列表
        desensitize_configs = list()
        text_fields_desensitize_configs = list()
        sort_index = 1
        text_sort_index = 1
        for _config in field_configs:
            field_name = _config["field_name"]
            for _rule in _config["rules"]:
                rule_id = _rule.get("rule_id")
                if rule_id and rule_id not in desensitize_rule_info:
                    continue
                if rule_id:
                    _operator = desensitize_rule_info[rule_id]["operator"]
                    _params = desensitize_rule_info[rule_id]["params"]
                    _match_pattern = desensitize_rule_info[rule_id]["match_pattern"]
                else:
                    _operator = _rule["operator"]
                    _params = _rule["params"]
                    _match_pattern = _rule["match_pattern"]
                # 原文字段的配置单独进行处理
                if field_name in text_fields:
                    text_fields_desensitize_configs.append(
                        {
                            "field_name": field_name,
                            "rule_id": rule_id or 0,
                            "operator": _operator,
                            "params": _params,
                            "match_pattern": _match_pattern,
                            "sort_index": text_sort_index,
                        }
                    )
                    text_sort_index += 1
                else:
                    desensitize_configs.append(
                        {
                            "field_name": field_name,
                            "rule_id": rule_id or 0,
                            "operator": _operator,
                            "params": _params,
                            "match_pattern": _match_pattern,
                            "sort_index": sort_index,
                        }
                    )
                    sort_index += 1

        desensitize_handler = DesensitizeHandler(desensitize_configs)

        text_fields_desensitize_handler = DesensitizeHandler(text_fields_desensitize_configs)

        res = dict()

        all_field_names = field_names.union(set(text_fields))

        # 日志原文脱敏处理
        for _log in logs:
            _log = expand_nested_data(_log)
            log_content_tmp = copy.deepcopy(_log)

            result = desensitize_handler.transform_dict(_log)

            # 日志原文字段同步应用其他字段的脱敏结果
            for text_field in text_fields:  # ["log"]
                # 判断原文字段是否存在log中
                if text_field not in result:
                    continue

                for field_name in field_names:
                    if field_name not in result or field_name == text_field:
                        continue
                    result[text_field] = result[text_field].replace(
                        str(log_content_tmp[field_name]), str(result[field_name])
                    )

            # 处理日志原文字段自身的脱敏逻辑
            result = text_fields_desensitize_handler.transform_dict(_log)

            for _field_name in all_field_names:
                if _field_name not in res:
                    res[_field_name] = list()
                res[_field_name].append(result.get(_field_name))

        return res
