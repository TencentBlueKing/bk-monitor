# -*- coding: utf-8 -*-
"""
V4 清洗规则测试 — built_in_config 构造器
"""
import copy

STANDARD_BUILT_IN_CONFIG = {
    "option": {
        "es_unique_field_list": [
            "cloudId", "serverIp", "path", "gseIndex",
            "iterationIndex", "bk_host_id", "dtEventTimeStamp"
        ],
        "separator_node_source": "",
        "separator_node_action": "",
        "separator_node_name": "",
    },
    "fields": [
        {"field_name": "bk_host_id", "field_type": "float", "tag": "dimension",
         "alias_name": "bk_host_id", "description": "主机ID",
         "option": {"es_type": "integer"}},
        {"field_name": "__ext", "field_type": "object", "tag": "dimension",
         "alias_name": "ext", "description": "额外信息字段",
         "option": {"es_type": "object"}},
        {"field_name": "cloudId", "field_type": "float", "tag": "dimension",
         "alias_name": "cloudid", "description": "云区域ID",
         "option": {"es_type": "integer"}},
        {"field_name": "serverIp", "field_type": "string", "tag": "dimension",
         "alias_name": "ip", "description": "ip",
         "option": {"es_type": "keyword"}},
        {"field_name": "path", "field_type": "string", "tag": "dimension",
         "alias_name": "filename", "description": "日志路径",
         "option": {"es_type": "keyword"}},
        {"field_name": "gseIndex", "field_type": "float", "tag": "dimension",
         "alias_name": "gseindex", "description": "gse索引",
         "option": {"es_type": "long"}},
        {"field_name": "iterationIndex", "field_type": "float", "tag": "dimension",
         "alias_name": "iterationindex", "description": "迭代ID",
         "option": {"es_type": "integer"}, "flat_field": True},
    ],
    "time_field": {
        "field_name": "dtEventTimeStamp",
        "field_type": "timestamp",
        "alias_name": "utctime",
        "description": "数据时间",
        "tag": "timestamp",
        "option": {
            "time_zone": 8,
            "time_format": "yyyy-MM-dd HH:mm:ss",
            "es_type": "date",
            "es_format": "epoch_millis",
        },
    },
}


def get_fresh_config():
    """获取标准配置的独立副本"""
    return copy.deepcopy(STANDARD_BUILT_IN_CONFIG)


def make_nanos_config(v3_time_format="yyyy-MM-dd HH:mm:ss.SSSSSS"):
    """构造 nanos 时间格式的 built_in_config"""
    config = get_fresh_config()
    config["time_field"]["option"]["time_format"] = v3_time_format
    return config


def make_path_regex_config(regexp=r"/data/logs/(?P<app_name>[^/]+)/(?P<log_type>[^/]+)\.log"):
    """构造包含 path regex 的 built_in_config"""
    config = get_fresh_config()
    config["option"]["separator_configs"] = [{"separator_regexp": regexp}]
    return config


def make_no_iteration_index_config():
    """构造无 iterationIndex (flat_field=False) 的 built_in_config"""
    config = get_fresh_config()
    for field in config["fields"]:
        if field["field_name"] == "iterationIndex":
            field["flat_field"] = False
    return config


def make_no_time_field_config():
    """构造无 time_field 的 built_in_config"""
    config = get_fresh_config()
    del config["time_field"]
    return config


def make_empty_fields_config():
    """构造 fields 为空列表的 built_in_config"""
    config = get_fresh_config()
    config["fields"] = []
    return config
