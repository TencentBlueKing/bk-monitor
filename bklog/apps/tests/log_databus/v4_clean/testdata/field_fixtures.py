# -*- coding: utf-8 -*-
"""
V4 清洗规则测试 — 字段构造器和预定义组合
"""


def make_field(name, field_type="string", alias="", is_time=False,
               is_delete=False, field_index=None, option=None):
    """构造单个字段配置"""
    field = {
        "field_name": name,
        "alias_name": alias,
        "field_type": field_type,
        "description": name,
        "is_analyzed": False,
        "is_dimension": True,
        "is_time": is_time,
        "is_delete": is_delete,
        "option": option or {},
    }
    if field_index is not None:
        field["field_index"] = field_index
    return field


# 预定义组合
SINGLE_STRING_FIELD = [make_field("level")]

MULTI_TYPE_FIELDS = [
    make_field("name"),
    make_field("count", "int"),
    make_field("ratio", "float"),
    make_field("active", "bool"),
    make_field("meta", "object"),
]

FIELD_WITH_ALIAS = [make_field("src_ip", alias="client_ip")]

FIELD_ALL_DELETED = [make_field("debug", is_delete=True)]

TIME_FIELD = [
    make_field("log_time", is_time=True,
               option={"time_zone": 8, "time_format": "yyyy-MM-dd HH:mm:ss"}),
]

DELIMITER_FIELDS = [
    make_field("ip", field_index=1),
    make_field("method", field_index=2),
    make_field("cost", "double", field_index=3),
]
