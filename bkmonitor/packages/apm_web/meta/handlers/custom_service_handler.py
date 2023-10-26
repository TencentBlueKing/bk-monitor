# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import re


class Matcher:
    @classmethod
    def match_auto(cls, rule, value):
        if not value:
            return False

        regex = rule["regex"]
        return bool(re.match(regex, value))

    @classmethod
    def opeartor_match(cls, value, operator, rule_value):
        if operator == "eq":
            return rule_value in value

        elif operator == "nq":
            return rule_value not in value

        elif operator == "reg":
            return bool(re.match(rule_value, value))

        return False

    @classmethod
    def manual_match_host(cls, host_rule, value):
        if not host_rule or not value:
            return False

        operator = host_rule["operator"]
        rule_value = host_rule["value"]

        return cls.opeartor_match(value, operator, rule_value)

    @classmethod
    def manual_match_uri(cls, rules, value):
        if not rules or not value:
            return False

        operator = rules["operator"]
        rule_value = rules["value"]

        return cls.opeartor_match(value, operator, rule_value)

    @classmethod
    def manual_match_params(cls, params_rule, value):
        if not params_rule or not value:
            return False

        def find_param_rule(_param):
            for p in params_rule:
                if p["name"] == _param:
                    return p
            return None

        predicates = set()
        params = value.split("&")
        for param in params:
            param_name, param_value = param.split("=")
            item = find_param_rule(param_name)
            if not item:
                continue

            predicates.add(cls.opeartor_match(param_value, item["operator"], item["value"]))

        return all(predicates)
