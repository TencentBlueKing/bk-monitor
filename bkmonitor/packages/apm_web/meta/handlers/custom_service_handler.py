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
    def manual_match_host(cls, host_rule, value):
        if not host_rule or not value:
            return False

        operator = host_rule["operator"]
        rule_value = host_rule["value"]

        return cls.operator_match(rule_value, value, operator)

    @classmethod
    def operator_match(cls, value, except_value, operator):
        if operator == "eq":
            return value == except_value
        if operator == "nq":
            return value != except_value
        if operator == "reg":
            return bool(re.match(value, except_value))
        return False

    @classmethod
    def manual_match_uri(cls, rules, value):
        if not rules or not value:
            return False

        operator = rules["operator"]
        rule_value = rules["value"]

        return cls.operator_match(rule_value, value, operator)
