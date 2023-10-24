"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import random
import re
from dataclasses import dataclass, field
from typing import ClassVar, Dict, List, Optional
from uuid import UUID


def generate_id():
    return UUID(int=random.getrandbits(128), version=4).hex


@dataclass
class Location:
    file_name: str
    func: str
    start_line: int

    @property
    def full_name(self) -> str:
        return f"{self.func} {self.file_name}:{self.start_line}"

    def __hash__(self):
        return hash(tuple([self.file_name, self.func, self.start_line]))

    def __eq__(self, other):
        return self.file_name == other.file_name and self.func == other.func and self.start_line == other.start_line


@dataclass
class SampleNode:

    location: Location
    elapsed_time: float
    level: int = 0
    parent: Optional["SampleNode"] = None
    children: List["SampleNode"] = field(default_factory=list)

    # fake fields for aligning with trace
    FakeIconType: ClassVar[str] = "sample"
    FakeKind: ClassVar[int] = -1
    FakeStatus: ClassVar[str] = "success"

    def __post_init__(self):
        self.id = generate_id()

    def should_merge(self, other: "SampleNode") -> bool:
        return self.location == other.location

    def merge(self, other: "SampleNode"):
        self.elapsed_time += other.elapsed_time

    def to_element(self) -> dict:
        element = {
            "name": self.location.full_name,
            "value": self.elapsed_time,
            "children": [x.to_element() for x in self.children],
            "id": self.id,
            "parallel_id": None,
            "last_sibling_id": None,
            "icon_type": self.FakeIconType,
            "start_time": None,
            "end_time": None,
            # field for trace, left it empty
            "kind": self.FakeKind,
            "level": self.level,
            "status": self.FakeStatus,
        }
        return element


@dataclass
class SampleTree:
    roots: List["SampleNode"] = field(default_factory=list)

    nodes_map: Dict[Location, SampleNode] = field(default_factory=dict)

    PATTERN: ClassVar[str] = r"(?P<elapsed_time>\d+)\s(?P<func>.*?)\s(?P<file_name>.*?):(?P<start_line>\d+);"

    @classmethod
    def parse(cls, raw: dict) -> "SampleTree":
        """turn raw data to profiling linked list"""

        stacktraces = [r["stacktrace"] for r in raw["list"]]
        # multiple samples will be merged into one tree
        tree = cls()

        # "4429050 runtime.main /usr/local/go/src/runtime/proc.go:267;7021886 main.main /some/path/to/main.go:12;"
        for stacktrace in stacktraces:
            matches = re.finditer(cls.PATTERN, stacktrace)

            last_node = None
            for match in matches:
                elapsed_time, func, file_name, start_line = match.groupdict().values()
                elapsed_time = float(elapsed_time)
                start_line = int(start_line)
                location = Location(func=func, file_name=file_name, start_line=start_line)

                # merge same location
                if location not in tree.nodes_map:
                    node = SampleNode(location=location, elapsed_time=elapsed_time, parent=last_node)
                    if last_node is not None:
                        last_node.children.append(node)

                    tree.nodes_map[location] = node
                    last_node = node
                else:
                    node = tree.nodes_map[location]
                    node.parent = last_node
                    node.elapsed_time += elapsed_time
                    last_node = node

        # get real roots
        roots = [x for x in tree.nodes_map.values() if x.parent is None]
        tree.roots = roots

        return tree


class ProfileParser:
    @classmethod
    def raw_to_flamegraph(cls, raw: dict) -> dict:
        """
        将原始数据转换为火焰图数据
        :param raw: 原始数据
        :return: 火焰图数据
        """
        tree = SampleTree.parse(raw)

        flamegraph_data = []
        # turn linked list to flamegraph data
        for root in tree.roots:
            flamegraph_data.append(root.to_element())

        # return to custom flamegraph component
        return {"flame_data": flamegraph_data}
