from collections import namedtuple
from heapq import heapify, nlargest

from apm_web.profile.diagrams.tree_converter import TreeConverter


class NodeIdToMark(dict):
    def __init__(self):
        super().__init__()
        self.cnt = 0

    def __missing__(self, key):
        self[key] = self.cnt
        self.cnt += 1
        return self[key]


class DOTDiagrammer:
    def draw(self, c: TreeConverter, top_k_cost_node: int = 10, **options) -> dict:
        function_tree = c.tree
        Node = namedtuple("Node", ["self_time", "id"])
        nodes = [Node(self_time=n.self_time, id=n.id) for n in function_tree.function_node_map.values()]

        # 1. 获取self_time(开销)最大的前K个节点
        heapify(nodes)
        topk_nodes = nlargest(top_k_cost_node, nodes)

        node_id_to_mark = NodeIdToMark()
        DirectedEdge = namedtuple("DirectedEdge", ["source", "target"])
        directed_edges: list[DirectedEdge] = []

        # 2. 添加边, 遍历第一步获得的K个节点的调用栈
        for _node in topk_nodes:
            node_id = _node.id

            node = function_tree.function_node_map[node_id]

            # 收集调用栈信息
            while node.parent:
                parent_mark, node_mark = node_id_to_mark[node.parent.id], node_id_to_mark[node.id]
                directed_edges.append(DirectedEdge(parent_mark, node_mark))
                node = node.parent

        total_cost = function_tree.root.value

        edge_lines = [f"N{edge.source} -> N{edge.target}" for edge in directed_edges]
        node_marks = []
        for node_id, mark in node_id_to_mark.items():
            if node_id == "total":
                continue
            node = function_tree.function_node_map[node_id]
            node_marks.append(
                f'N{mark} [label="{node.system_name} \\n {node.self_time:.2f} ({node.self_time / total_cost:.2%})"]'
            )

        # 拼接 DOT 格式的字符串, chr(10) 为 '\n'(换行符)
        dot_graph = f"""digraph "type=[{c.sample_type.get("type")}/{c.sample_type.get("unit")}]" {{
{chr(10).join(node_marks)}
{chr(10).join(edge_lines)}
}}"""

        return {"dot_graph": dot_graph}

    def diff(self, base_tree_c: TreeConverter, comp_tree_c: TreeConverter, **options):
        pass
