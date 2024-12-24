"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List

logger = logging.getLogger("apm")

ROOT_DISPLAY_NAME = "total"

# 节点名称中不能包含以下特殊字符
DOT_INVALID_CHARS = ["[", "]", ":", ";", "{", "}", '"', "<", ">"]
GO_STRUCT_TYPE_REGEX = re.compile(r'\[go\.shape\..*\]')


@dataclass
class FunctionNode:
    """Function based flame node"""

    id: str
    name: str
    system_name: str
    filename: str

    is_root: bool = False
    has_parent: bool = False
    children: Dict[str, "FunctionNode"] = field(default_factory=dict)
    value: int = 0
    values: List[int] = field(default=list)

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
    function_node_map: Dict[str, FunctionNode] = field(default_factory=dict)


class ValueCalculator:
    @classmethod
    def mapping(cls):
        return {
            "goroutine": {
                "count": cls.GoroutineCount,
            }
        }

    @classmethod
    def calculate_nodes(cls, tree, sample_type):
        c = cls.mapping().get(sample_type["type"], {}).get(sample_type["unit"], cls.Default)

        # 1. 计算树节点的值
        def calculate_node(tree_node):
            tree_node.value = c.calculate(tree_node.values)
            for child in tree_node.children.values():
                calculate_node(child)

        calculate_node(tree.root)
        tree.root.value = sum([child.value for child in tree.root.children.values()])

        # 2. 计算图节点的值
        for node in tree.function_node_map.values():
            node.value = c.calculate(node.values)

        tree.map_root.value = sum([child.value for child in tree.map_root.children.values()])

    class GoroutineCount:
        type = "goroutine"
        unit = "count"

        @classmethod
        def calculate(cls, values):
            if not values:
                return 0

            return int(sum(values) / len(values))

    class Default:
        @classmethod
        def calculate(cls, values):
            return sum(values)
