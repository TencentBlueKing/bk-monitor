"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import math
import os
import re
from collections import deque
from dataclasses import dataclass
from io import BytesIO
from typing import Any, List

from graphviz import Digraph

from apm_web.profile.constants import CallGraph, CallGraphResponseDataMode
from apm_web.profile.diagrams.base import FunctionNode, FunctionTree
from apm_web.profile.diagrams.tree_converter import TreeConverter

# 定义正则表达式 来过滤切割不同语言的 pkg 名称
cpp_anonymous_prefix_re = re.compile(r'^\(anonymous namespace\)::')
go_ver_re = re.compile(r'^(.*?)/v(?:[2-9]|[1-9][0-9]+)([./].*)$')
go_re = re.compile(r'^(?:[\w\-\.]+\/)+([^.]+\..+)')
java_re = re.compile(r'^(?:[a-z]\w*\.)*([A-Z][\w\$]*\.(?:<init>|[a-z][\w\$]*(?:\$\d+)?))(?:(?:\()|$)')
cpp_re = re.compile(r'^(?:[_a-zA-Z]\w*::)+(_*[A-Z]\w*::~?[_a-zA-Z]\w*(?:<.*>)?)')


def shorten_function_name(f):
    """
    缩短函数名 减少显示长度
    """
    f = cpp_anonymous_prefix_re.sub('', f)
    f = go_ver_re.sub(r'\1\2', f)
    for re_pattern in [go_re, java_re, cpp_re]:
        matches = re_pattern.findall(f)
        if matches:
            return ''.join(matches)
    return f


def escape_for_dot(string):
    """
    过滤 graphviz 不能识别的转义字符
    """
    return string.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\l')


def multiline_printable_name(name, file_path=''):
    """
    生成多行可读的函数名
    """
    name = escape_for_dot(shorten_function_name(name))
    name = name.replace('::', '\\n')
    name = name.replace('[...]', '[…]')
    name = name.replace('.', '\\n')
    if file_path:
        file_path = os.path.basename(file_path)
    return f"{name}\\n{file_path}\\n" if file_path else f"{name}\\n"


def build_edge_relation(node_list: List[FunctionNode]) -> list:
    edges = {}
    visited_nodes = set()

    queue = deque(node_list)
    while queue:
        node = queue.popleft()
        for child in node.children.values():
            edge_key = (node.id, child.id)
            if edge_key in edges:
                continue

            edge_value = min(node.value, child.value)
            edges[edge_key] = {"source_id": node.id, "target_id": child.id, "value": edge_value}
            if child.id not in visited_nodes:
                visited_nodes.add(child.id)
                queue.append(child)
    return list(edges.values())


def dot_color(score: float, is_back_ground: bool = False) -> str:
    """
    A float between 0.0 and 1.0, indicating the extent to which
    colors should be shifted away from grey (to make positive and
    negative values easier to distinguish, and to make more use of
    the color range.)

    :param score: 分数
    :param is_back_ground:
    :return:
    """

    shift = 0.7
    # Saturation and value (in hsv colorspace) for background colors.
    bg_saturation = 0.1
    bg_value = 0.93

    # Saturation and value (in hsv colorspace) for foreground colors.
    fg_saturation = 1.0
    fg_value = 0.7

    saturation: float
    value: float
    if is_back_ground:
        saturation = bg_saturation
        value = bg_value
    else:
        saturation = fg_saturation
        value = fg_value

    # Limit the score values to the range [-1.0, 1.0].
    score = max(-1.0, min(1.0, score))

    # Reduce saturation near score=0 (so it is colored grey, rather than yellow).
    if math.fabs(score) < 0.2:
        saturation *= math.fabs(score) / 0.2

    # // Apply 'shift' to move scores away from 0.0 (grey).
    if score > 0.0:
        score = math.pow(score, (1.0 - shift))

    if score < 0.0:
        score = -math.pow(-score, (1.0 - shift))

    # red, green, blue
    r: float
    g: float
    b: float
    if score < 0.0:
        g = value
        r = value * (1 + saturation * score)
    else:
        r = value
        g = value * (1 - saturation * score)

    b = value * (1 - saturation)
    return "#{:02x}{:02x}{:02x}".format(int(r * 255.0), int(g * 255.0), int(b * 255.0))


def generate_svg_data(tree: FunctionTree, data: dict, unit: str):
    """
    生成 svg 图片数据
    :param tree 功能树调用树
    :param data call_graph 数据
    :param unit 单位
    """

    dot = Digraph(comment="The Round Table", format="svg")
    call_graph_data = data.get("call_graph_data", {})
    for node in call_graph_data.get("call_graph_nodes", []):
        ratio = 0.00 if data["call_graph_all"] == 0 else node["value"] / data["call_graph_all"]
        ratio_str = f"{ratio:.2%}"
        node_name = multiline_printable_name(node["name"])
        title = f"""{node_name} {display(node["self"], unit)} of {display(node["value"], unit)} ({ratio_str})"""
        node_color = dot_color(score=ratio, is_back_ground=True)
        background_color = dot_color(score=ratio, is_back_ground=False)
        width, height = calculate_node_size(ratio)
        base_font_size, max_font_size = 10, 32
        font_size = int(base_font_size + (max_font_size - base_font_size) * ratio**2)

        dot.node(
            str(node["id"]),
            label=title,
            style="filled",
            fillcolor=node_color,
            color=background_color,
            fontsize=str(font_size),
            tooltip=node["name"],
            width=str(width),
            height=str(height),
            shape="box",
        )

    for edge in call_graph_data.get("call_graph_relation", []):
        tooltip = (
            tree.function_node_map.get(edge["source_id"]).name
            if edge["source_id"] in tree.function_node_map
            else "unknown" + "->" + tree.function_node_map.get(edge["target_id"]).name
            if edge["target_id"] in tree.function_node_map
            else "unknown"
        )
        penwidth = max(int(min((edge["value"] * 5 / data["call_graph_all"]), 5)), 1)
        # 线条宽度 避免为零 至少为一
        ratio = 0.00 if data["call_graph_all"] == 0 else edge["value"] / data["call_graph_all"]
        background_color = dot_color(score=ratio, is_back_ground=False)

        dot.edge(
            str(edge["source_id"]),
            str(edge["target_id"]),
            label=f'{display(edge["value"], unit)}',
            tooltip=tooltip,
            color=background_color,
            splines="curved",
            penwidth=str(penwidth),
        )

    svg_data = dot.pipe(format="svg")
    try:
        with BytesIO(svg_data) as svg_buffer:
            res = svg_buffer.read().decode()
    except Exception as e:
        raise ValueError(f"generate_svg_data, read call graph data failed , error: {e}")

    res = re.sub(r'<title>.*?</title>', '', res, flags=re.DOTALL)
    data["call_graph_data"] = res
    return data


def calculate_node_size(percentage, exponent=2):
    """根据百分比计算节点大小 指数级放大增强对比"""

    percentage = max(0, min(1, percentage))
    adjusted_percentage = percentage**exponent

    # 计算节点宽度和高度
    node_width = CallGraph.BASE_SIZE + adjusted_percentage * (CallGraph.MAX_SIZE - CallGraph.MIN_SIZE)
    node_height = CallGraph.BASE_SIZE + adjusted_percentage * (CallGraph.MAX_SIZE - CallGraph.MIN_SIZE)

    return node_width, node_height


def display(value, unit):
    """将不同数据类型单位转换可读格式"""

    if unit == "nanoseconds":
        return convert_seconds(value / 1000000000)
    elif unit == "seconds":
        return convert_seconds(value)
    elif unit == "bytes":
        units = ["Bytes", "KB", "MB", "GB", "TB"]
        step = 1024
        if value == 0:
            return "0Bytes"

        i = 0
        while value >= step and i < len(units) - 1:
            value /= step
            i += 1

        size = round(value, 2)
        return f"{size}{units[i]}"

    return str(value)


def convert_seconds(seconds):
    hours = seconds // 3600
    if hours >= 1:
        remaining_minutes = (seconds % 3600) // 60
        return f"{int(hours)}h{int(remaining_minutes)}m"

    minutes = seconds // 60
    if minutes >= 1:
        remaining_seconds = seconds % 60
        return f"{int(minutes)}m{remaining_seconds:.2f}s"

    milliseconds = seconds * 1000
    if milliseconds < 1000:
        return f"{milliseconds:.0f}ms"

    microseconds = milliseconds * 1000
    if microseconds < 1000:
        return f"{microseconds:.0f}μs"

    nanoseconds = microseconds * 1000
    if nanoseconds < 1000:
        return f"{nanoseconds}ns"

    return f"{seconds:.2f}s"


@dataclass
class CallGraphDiagrammer:
    def draw(self, c: TreeConverter, **options) -> Any:
        nodes = list(c.tree.function_node_map.values())
        edges = build_edge_relation(list(c.tree.map_root.children.values()))
        data = {
            "call_graph_data": {
                "call_graph_nodes": [
                    {"id": node.id, "name": node.name, "value": node.value, "self": node.self_time} for node in nodes
                ],
                "call_graph_relation": edges,
            },
            "call_graph_all": c.tree.map_root.value,
        }
        if options.get("data_mode") and options.get("data_mode") == CallGraphResponseDataMode.IMAGE_DATA_MODE:
            # 补充 sample_type 信息
            sample_type_info = c.get_sample_type()
            data.update(sample_type_info)
            return generate_svg_data(c.tree, data, unit=sample_type_info["unit"])
        return data

    def diff(self, base_tree_converter: TreeConverter, diff_tree_converter: TreeConverter, **options) -> dict:
        raise ValueError("CallGraph not support diff mode")
