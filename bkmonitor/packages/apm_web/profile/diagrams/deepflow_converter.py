from dataclasses import dataclass, field
from apm_web.profile.diagrams.base import (
    FunctionNode,
    FunctionTree,
)
from apm_web.profile.diagrams.tree_converter import TreeConverter
import logging
logger = logging.getLogger("root")

@dataclass
class DeepFlowConverter(TreeConverter):
    """
    DeepFlow 数据格式转换
    """
    sample_type: dict = field(default_factory=lambda: {"unit": "microseconds"})
    
    # deepflow 时间单位是微秒
    def empty(self) -> bool:
        return not bool(self.tree)


    def get_sample_type(self) -> dict:
        return self.sample_type
    

    def convert(self, raw: list, data_type: str):
        """
        deepflow 的数据格式是平铺的列表 每个元素为字典 其格式为
            {   
                'profile_location_str': '', 
                'node_id': '',
                'parent_node_id': '', 
                'self_value': 0,
                'total_value': 10101
            }
        """
        if len(raw) == 0:
            return 
        if raw[0]["parent_node_id"] != "-1":
            raise ValueError("Invalid data format: the first result of deepflow must be the root node with parent_node_id '-1'.")
        # 创建 FunctionNode 对象并存储在 function_node_map 中

        # 构建 FunctionTree
        tree = FunctionTree(
            root=FunctionNode(
                id="-1",
                name=raw[0]["profile_location_str"],
                system_name="",
                filename="",
                values=[],
                value=raw[0]["total_value"],
            )
        )
        self.sample_type.update({"type": data_type})
        for result in raw:
            node = FunctionNode(
                id=result["node_id"],
                name=result["profile_location_str"],
                system_name="",  # 字段留空
                filename="",  # 字段留空
                value=result["total_value"],
                values=[result["self_value"]]
            )
            tree.function_node_map[node.id] = node
        
        # 构建树结构
        for result in raw:
            node_id = result["node_id"]
            parent_id = result["parent_node_id"]
            node = tree.function_node_map[node_id]

            if parent_id != "-1":
                # 根节点 parent_id 为 -1
                parent_node = tree.function_node_map[parent_id]
                parent_node.add_child(node)
            else:
                # 如果没有父节点，则设置为根节点
                node.is_root = True
                tree.root = node
        self.tree = tree
    
