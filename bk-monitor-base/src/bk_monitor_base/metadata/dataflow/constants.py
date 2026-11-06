from typing import final


@final
class ConsumingMode:
    Head = "from_head"  # 从最早(from_head)位置消费
    Tail = "from_tail"  # 从最新(from_tail)位置消费
    Current = "continue"  # 从当前位置继续(continue), 不填默认continue


# 表后缀(字母或数字([A-Za-z0-9]), 不能有下划线"_", 且最好不超过10个字符)
BK_DATA_RAW_TABLE_SUFFIX = "raw"  # 数据接入
BK_DATA_CMDB_FULL_TABLE_SUFFIX = "full"  # 补充cmdb节点信息后的表后缀
BK_DATA_CMDB_SPLIT_TABLE_SUFFIX = "cmdb"  # 补充表拆分后的表后缀
