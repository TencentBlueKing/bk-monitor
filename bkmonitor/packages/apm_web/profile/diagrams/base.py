"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from django.conf import settings

from bkmonitor.utils.common_utils import format_percent

logger = logging.getLogger("apm")

ROOT_DISPLAY_NAME = "total"

# 节点名称中不能包含以下特殊字符
DOT_INVALID_CHARS = ["[", "]", ":", ";", "{", "}", '"', "<", ">"]
GO_STRUCT_TYPE_REGEX = re.compile(r"\[go\.shape\..*\]")


@dataclass
class FunctionNode:
    """Function based flame node"""

    id: str
    name: str
    system_name: str
    filename: str

    is_root: bool = False
    has_parent: bool = False
    parent: Optional["FunctionNode"] = field(default=None)
    children: dict[str, "FunctionNode"] = field(default_factory=dict)
    value: int = 0
    values: list[int] = field(default=list)

    def __eq__(self, other):
        return self.id == other.id

    def __hash__(self):
        return hash(self.id)

    @property
    def self_time(self) -> int:
        """self time"""
        sub = self.value - sum(x.value for x in self.children.values())
        return sub if sub > 0 else 0

    def to_dict(self):
        return {
            "id": self.id,
            "value": self.value,
            "self": self.self_time,
            "name": self.name,
            "system_name": self.system_name,
            "filename": self.filename,
        }

    def add_child(self, child):
        child.has_parent = True
        self.children[child.id] = child

    def add_value(self, value):
        self.values.append(value)

    @classmethod
    def generate_id(cls, stacktrace_line):
        """根据 sample 的堆栈信息生成功能节点的 ID"""
        return "".join(
            [
                stacktrace_line["function"]["systemName"],
                stacktrace_line["function"]["fileName"],
                stacktrace_line["function"]["name"],
            ]
        )

    @classmethod
    def replace_invalid_char(cls, line):
        """
        1️⃣ 替换堆栈里面可能出现的特殊字符
        如果包含特殊字符 则为错误格式的数据 需要用户检查
        这里防止后续处理会出现异常进行替换
        2️⃣ 如果名称中有泛型的定义 替换具体类型变为 (...) [针对 GO SDK 上报]
        """

        check_fields = ["systemName", "fileName", "name"]
        for f in check_fields:
            f_value = line["function"][f]

            # Step1: 替换泛型
            matches_indices = [(m.start(), m.end()) for m in GO_STRUCT_TYPE_REGEX.finditer(f_value)]
            modified = []
            prev_end = 0
            for start, end in matches_indices:
                modified.append(f_value[prev_end:start] + "(...)")
                prev_end = end

            modified.append(f_value[prev_end:])
            tmp_value = "".join(modified)

            # Step2: 检查特殊字符
            for c in DOT_INVALID_CHARS:
                if c in tmp_value:
                    tmp_value = tmp_value.replace(c, "")
            line["function"][f] = tmp_value

        return line


@dataclass
class FunctionTree:
    root: FunctionNode

    map_root: FunctionNode
    function_node_map: dict[str, FunctionNode] = field(default_factory=dict)


class ValueCalculator:
    """节点值计算器（策略模式）"""

    @classmethod
    def agg_mapping(cls):
        return {
            "AVG": cls.AvgCount,
            "SUM": cls.SumCount,
            "LAST": cls.SumCount,  # agg_method的值是LAST时，只有一个样本，所以使用SumCount，保证这个样本保持自身的value
        }

    @classmethod
    def calculate_nodes(cls, tree, sample_type, samples_len, agg_method=None):
        """递归计算所有节点值"""
        # 根据聚合方法和采样类型获取计算策略，当agg_method没传值时，默认通过profiling数据类型的计算节点
        if agg_method:
            c = cls.agg_mapping().get(agg_method) or cls.agg_mapping().get(
                settings.APM_PROFILING_AGG_METHOD_MAPPING.get(sample_type["type"].upper()), cls.SumCount
            )
        else:
            c = cls.agg_mapping().get(
                settings.APM_PROFILING_AGG_METHOD_MAPPING.get(sample_type["type"].upper()), cls.SumCount
            )

        def calculate_node(tree_node):
            """递归计算节点值"""
            tree_node.value = c.calculate(tree_node.values, samples_len)
            for child in tree_node.children.values():
                calculate_node(child)

        calculate_node(tree.root)
        # 更新根节点值（子节点值总和）
        tree.root.value = format_percent(
            sum(child.value for child in tree.root.children.values()), precision=4, sig_fig_cnt=4
        )

        # 计算图结构节点
        for node in tree.function_node_map.values():
            node.value = c.calculate(node.values, samples_len)

        # 更新图结构根节点值
        tree.map_root.value = format_percent(
            sum(child.value for child in tree.map_root.children.values()), precision=4, sig_fig_cnt=4
        )

    class AvgCount:
        """Go协程数量计算策略（平均值）"""

        @classmethod
        def calculate(cls, values, samples_len):
            # 添加边界条件检查
            if not values or samples_len <= 0:
                return 0
            return format_percent(sum(values) / samples_len, precision=4, sig_fig_cnt=4)

    class SumCount:
        """默认计算策略（累加）"""

        @classmethod
        def calculate(cls, values, samples_len=None):
            if not values:
                return 0
            return sum(values)


def is_func(name: str) -> bool:
    """name包含斜杠或点说明是路径，返回True，不包含说明name是函数名，返回False"""
    return len(name.split("/")) <= 1 or len(name.split(".")) <= 1


language_handler_mapping = {
    "python": {
        "handler": lambda i: {**i, "name": replace_table_name(i["id"], i["name"]) if is_func(i["name"]) else i["name"]}
    },  # 根据 name 的类型修改 name
    "default": {"handler": lambda i: i},
}


def get_handler_by_mapping(options):
    language = options.get("service_language", "default")  # service_language为空时，language取默认key
    handler = language_handler_mapping.get(language, language_handler_mapping["default"]).get("handler")
    return handler


def replace_table_name(node_id: str, name: str) -> str:
    if node_id != name:
        node_id = node_id.replace(name, ":" + name)
    return node_id
