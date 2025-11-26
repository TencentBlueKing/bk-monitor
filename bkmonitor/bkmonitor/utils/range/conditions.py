"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import re
import sre_constants


class Condition:
    def is_match(self, data):
        raise NotImplementedError("You should implement this.")


class SimpleCondition(Condition):
    """eq / gt / lt / reg ..."""

    def __init__(self, cond_field, default_value_if_not_exists=False):
        self.cond_field = cond_field
        self.default_value_if_not_exists = default_value_if_not_exists

    def is_match(self, data):
        existed, data_field = self.get_field(data)
        if not existed:
            return self.default_value_if_not_exists

        return self._is_match(data_field)

    def _is_match(self, data_field):
        raise NotImplementedError("You should inherit me and implement this.")

    def get_field(self, data):
        is_exists, data_value = self.cond_field.get_value_from_data(data)
        if is_exists:
            return True, self.cond_field.__class__(self.cond_field.name, data_value)
        return False, None


class CompositeCondition(Condition):
    """AND / OR"""

    def __init__(self):
        self.conditions = []

    def is_match(self, data):
        raise NotImplementedError("You should inherit me and implement this.")

    def add(self, condition):
        self.conditions.append(condition)

    def remove(self, condition):
        self.conditions.remove(condition)


class OrCondition(CompositeCondition):
    def is_match(self, data):
        if not self.conditions:
            return True

        for cond in self.conditions:
            if cond.is_match(data):
                return True
        return False


class AndCondition(CompositeCondition):
    def is_match(self, data):
        if not self.conditions:
            return True

        for cond in self.conditions:
            if not cond.is_match(data):
                return False
        return True


class EqualCondition(SimpleCondition):
    def _is_match(self, data_field):
        data_value = data_field.to_str_list()
        cond_value = self.cond_field.to_str_list()
        return bool(set(data_value) & set(cond_value))


class NotEqualCondition(EqualCondition):
    def _is_match(self, data_field):
        return not super()._is_match(data_field)


class IncludeCondition(SimpleCondition):
    def _is_match(self, data_field):
        data_value_list = data_field.to_str_list()
        if not data_value_list:
            return False
        # 这里data_value 匹配一个即可
        for data_value in data_value_list:
            cond_value = self.cond_field.to_str_list()
            for v in cond_value:
                if v in data_value:
                    return True
        return False


class ExcludeCondition(IncludeCondition):
    def _is_match(self, data_field):
        return not super()._is_match(data_field)


class GreaterCondition(SimpleCondition):
    def _is_match(self, data_field):
        data_value = min(data_field.to_float_list())
        cond_value = max(self.cond_field.to_float_list())
        return data_value > cond_value


class LesserOrEqualCondition(GreaterCondition):
    def _is_match(self, data_field):
        return not super()._is_match(data_field)


class LesserCondition(SimpleCondition):
    def _is_match(self, data_field):
        data_value = max(data_field.to_float_list())
        cond_value = min(self.cond_field.to_float_list())
        return data_value < cond_value


class GreaterOrEqualCondition(LesserCondition):
    def _is_match(self, data_field):
        return not super()._is_match(data_field)


class RegularCondition(SimpleCondition):
    def _is_match(self, data_field):
        data_value = data_field.to_str_list()
        if not data_value:
            return False
        data_value = data_value[0]
        cond_value = self.cond_field.to_str_list()
        for v in cond_value:
            try:
                reg = re.compile(rf"{v}")
            except sre_constants.error:
                return False

            if reg.findall(data_value):
                return True
        return False


class NotRegularCondition(RegularCondition):
    def _is_match(self, data_field):
        return not super()._is_match(data_field)


class IsSuperSetCondition(SimpleCondition):
    def _is_match(self, data_field):
        data_value = data_field.to_str_list()
        cond_value = self.cond_field.to_str_list()
        return set(data_value).issuperset(set(cond_value))
