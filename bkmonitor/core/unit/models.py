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


import functools
from typing import Optional, Tuple, Union

from six.moves import range


class UnitCategory(object):
    """
    指标分类
    """

    def __init__(self, name):
        self.name = name


class UnitMeta(object):
    """
    单位元信息
    """

    def __init__(self, gid, name, category, fn):
        self.gid = gid
        self.name = name
        self.category = category
        self.fn = fn

    def __getattr__(self, item):
        return getattr(self.fn, item)

    def __repr__(self):
        return "{}||{}".format(self.category, self.gid)


class ScaledUnits(object):
    """
    动态单位
    """

    factor = 1
    suffix_list = []
    suffix_factor = {}

    def __init__(self, suffix_idx=0, suffix=None):
        self.suffix_idx = suffix_idx
        self._suffix = suffix or ""

    @property
    def unit(self):
        # 标准单位简写
        return self.suffix_list[self.suffix_idx] if self.suffix_list else ""

    @property
    def suffix(self):
        # 自定义单位名
        return self.unit + self._suffix

    @property
    def conversion(self):
        return self.factor**self.suffix_idx

    def __call__(self, *args, **kwargs):
        return self.suffix

    def get_unit_conversion(self, suffix_id):
        value = 1
        while suffix_id != self.suffix_idx:
            if suffix_id < self.suffix_idx:
                value /= self.suffix_factor.get(self.suffix_list[suffix_id], self.factor)
                suffix_id += 1
            elif suffix_id > self.suffix_idx:
                value *= self.suffix_factor.get(self.suffix_list[suffix_id], self.factor)
                suffix_id -= 1
            else:
                break
        return value

    def unit_series(self):
        if not self.suffix_list:
            return [{"unit_conversion": 1, "unit": self.suffix, "suffix": ""}]
        return [
            {
                "unit_conversion": self.get_unit_conversion(idx),
                "unit": self.suffix_list[idx] + self._suffix,
                "suffix": self.suffix_list[idx],
            }
            for idx in range(0, len(self.suffix_list))
        ]

    def auto_convert(
        self,
        value: Optional[Union[int, float]],
        suffix: Optional[str] = None,
        decimal: int = 6,
        target_range: Optional[Tuple[int, int]] = None,
    ) -> Tuple[Optional[Union[int, float]], str]:
        """
        动态单位转换
        :param value: 数值
        :param suffix: 数值单位
        :param decimal: 保留小数位数
        :param target_range: 数据应该转换到的目标数值范围
        """
        if value is None:
            return value, ""

        if suffix is None:
            suffix_id = self.suffix_idx
            suffix = self.suffix_list[self.suffix_idx] if 0 < self.suffix_idx < len(self.suffix_list) else ""
        else:
            try:
                suffix_id = self.suffix_list.index(suffix)
            except ValueError:
                suffix_id = -1

        if target_range is None:
            try:
                target_range = (1, self.suffix_factor.get(self.suffix_list[suffix_id], self.factor))
            except IndexError:
                target_range = (1, self.factor)

        # 如果不存在该单位，则返回原值
        if suffix_id < 0 or suffix_id >= len(self.suffix_list):
            return round(value, decimal), suffix + self._suffix

        if abs(value) < target_range[0]:
            while abs(value) < target_range[0] and suffix_id > 0:
                value *= self.suffix_factor.get(self.suffix_list[suffix_id - 1], self.factor)
                suffix_id -= 1
                if suffix_id <= 0:
                    break
                target_range = (1, self.suffix_factor.get(self.suffix_list[suffix_id - 1], self.factor))
        elif abs(value) >= target_range[1]:
            while abs(value) >= target_range[1] and suffix_id < len(self.suffix_list) - 1:
                value /= self.suffix_factor.get(self.suffix_list[suffix_id + 1], self.factor)
                suffix_id += 1
                if suffix_id >= len(self.suffix_list) - 1:
                    break
                target_range = (1, self.suffix_factor.get(self.suffix_list[suffix_id + 1], self.factor))

        return round(value, decimal), self.suffix_list[suffix_id] + self._suffix

    def convert(
        self,
        value: Optional[Union[int, float]],
        target_suffix: str,
        current_suffix: str = None,
        decimal: Optional[int] = None,
    ) -> Optional[Union[int, float]]:
        """
        转换为指定单位
        :param value: 数值
        :param current_suffix: 当前单位
        :param target_suffix: 目标单位
        :param decimal: 保留小数位数
        """
        if value is None:
            return value

        if current_suffix is None:
            current_suffix_id = self.suffix_idx
        else:
            try:
                current_suffix_id = self.suffix_list.index(current_suffix)
            except ValueError:
                current_suffix_id = -1

        try:
            target_suffix_id = self.suffix_list.index(target_suffix)
        except ValueError:
            target_suffix_id = -1

        if current_suffix_id >= 0 and target_suffix_id >= 0:
            if current_suffix_id < target_suffix_id:
                while current_suffix_id < target_suffix_id:
                    value /= self.suffix_factor.get(self.suffix_list[current_suffix_id + 1], self.factor)
                    current_suffix_id += 1
            if current_suffix_id > target_suffix_id:
                while current_suffix_id > target_suffix_id:
                    value *= self.suffix_factor.get(self.suffix_list[current_suffix_id], self.factor)
                    current_suffix_id -= 1

        if decimal is not None:
            value = round(value, decimal)

        return value

    def convert_to_max(self, value: Union[int, float], suffix: str = None, decimal: int = 6):
        """
        转换为最大值
        """
        if not len(self.suffix_list):
            return value, ""

        if suffix is None:
            suffix = self.suffix_list[self.suffix_idx] if 0 < self.suffix_idx < len(self.suffix_list) else ""

        return self.convert(value, target_suffix=self.suffix_list[0], current_suffix=suffix, decimal=decimal), suffix


class Percent(ScaledUnits):
    factor = 100
    suffix_list = ["%", "x100%"]

    def auto_convert(
        self,
        value: Union[int, float],
        suffix: Optional[str] = None,
        decimal: int = 6,
        target_range: Optional[Tuple[int, int]] = None,
    ) -> Tuple[Union[int, float], str]:
        if target_range is None:
            target_range = (float("inf"), float("inf"))
        return super(Percent, self).auto_convert(value, suffix, decimal, target_range)


class BinarySIPrefix(ScaledUnits):
    factor = 1024
    suffix_list = ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi", "Yi"]

    def __init__(self, suffix=None, suffix_idx=0):
        super(BinarySIPrefix, self).__init__(suffix_idx=suffix_idx, suffix=suffix)


class DecimalSIPrefix(ScaledUnits):
    factor = 1000
    suffix_list = ["", "k", "M", "G", "T", "P", "E", "Z", "Y"]

    def __init__(self, suffix=None, suffix_idx=0):
        super(DecimalSIPrefix, self).__init__(suffix_idx=suffix_idx, suffix=suffix)


class DecimalSIPrefixPlus(ScaledUnits):
    factor = 1000
    suffix_list = ["f", "p", "n", "µ", "m", "", "k", "M", "G", "T", "P", "E", "Z", "Y"]

    def __init__(self, suffix=None, suffix_idx=0):
        super(DecimalSIPrefixPlus, self).__init__(suffix_idx=suffix_idx, suffix=suffix)
        self.suffix_idx = self.suffix_idx + 5


class SimpleCountUnit(ScaledUnits):
    factor = 1000
    suffix_list = ["", "K", "M", "B", "T"]

    def __init__(self, suffix=None, suffix_idx=0):
        super(SimpleCountUnit, self).__init__(suffix_idx=suffix_idx, suffix=suffix)


class TimeUnit(ScaledUnits):
    factor = 1000
    suffix_list = ["ns", "µs", "ms", "s", "m", "h", "d"]
    suffix_factor = {"m": 60, "h": 60, "d": 24}


to_fixed_unit = functools.partial(ScaledUnits, 0)

to_percent = Percent(0)
to_percent_unit = Percent(1)


binary_si_prefix = BinarySIPrefix


def create_default_unit(suffix=""):
    return UnitMeta("none", "none", "Misc", to_fixed_unit(suffix))
