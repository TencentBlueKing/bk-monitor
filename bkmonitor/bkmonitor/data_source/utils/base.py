"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


class DescendingStr:
    """
    定义降序字符串类，用于支持字符串降序排序
    """

    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value

    def __lt__(self, other):
        """
        降序，取反原来的比较顺序
        """
        return self.value > other.value


def sort_fields(records, fields, extractor=None):
    """
    对字典列表按照多个字段进行排序，支持字段名后加"desc"表示降序
    支持使用自定义提取器获取字段值

    :param records: 要排序的数据列表（字典列表）
    :param fields: 排序字段列表，如 ["time", "event.count desc"]
    :param extractor: 字段提取函数，用于从记录中提取基础数据字典
    :return: 排序后的字典列表
    """

    def get_sort_key(item):
        # 提取比较的字典数据
        base_data = extractor(item) if extractor else item
        keys = []
        for field in fields:
            # 解析字段和排序顺序
            if len(field.split()) == 1:
                field, order = field, "asc"
            else:
                field, order = field.split(maxsplit=1)

            value = base_data.get(field)
            # 用元组来控制 None 的排序顺序，None->(1,)，正常值：(0, value)，确保 None 在最后
            if value is None:
                keys.append((1,))
                continue

            # 升序处理
            if order != "desc":
                keys.append((0, value))
                continue

            # 降序处理
            if isinstance(value, int | float):
                keys.append((0, -value))
            else:
                keys.append((0, DescendingStr(value)))

        return tuple(keys)

    return sorted(records, key=get_sort_key)


def get_bar_interval_number(start_time, end_time, size=30) -> int:
    """计算出柱状图（特殊处理的）的 interval 固定柱子数量"""
    # 最低聚合为一分钟
    c = (end_time - start_time) / 60
    if c < size:
        return 60

    return int((end_time - start_time) // size)
