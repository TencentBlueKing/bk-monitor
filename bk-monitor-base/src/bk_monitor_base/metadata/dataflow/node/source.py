from abc import ABC

from bk_monitor_base.metadata.dataflow.node.base import Node


class SourceNode(Node, ABC):
    pass


class StreamSourceNode(SourceNode):
    """
    数据源节点
    """

    NODE_TYPE: str = "stream_source"

    def __init__(self, source_rt_id):
        self.source_rt_id = source_rt_id
        super().__init__()

    def __eq__(self, other):
        if isinstance(other, dict):
            config = self.config
            if config.get("from_result_table_ids") == other.get("from_result_table_ids") and config.get(
                "table_name"
            ) == other.get("table_name"):
                return True
        elif isinstance(other, self.__class__):
            return self == other.config
        return False

    @property
    def name(self):
        return f"{self.get_node_type()}({self.source_rt_id})"

    @property
    def output_table_name(self):
        return self.source_rt_id

    @property
    def config(self):
        return {"from_result_table_ids": [self.source_rt_id], "result_table_id": self.source_rt_id, "name": self.name}


class RelationSourceNode(StreamSourceNode):
    """
    关联数据源
    """

    NODE_TYPE = "redis_kv_source"
