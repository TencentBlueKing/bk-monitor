import re

from bkmonitor.models import MetricListCache
from constants.data_source import DataSourceLabel, DataTypeLabel


def check_metric_field(metric_field: str, mapping_config: dict) -> dict:
    """
    确认指标名是否存在
    """
    check_result = {"is_exist": False, "table_id": "", "scenario": "kubernetes"}
    table_ids = mapping_config.get("mapping_range", [])
    if mapping_config.get("range_type") == "kubernetes":
        check_result["is_exist"] = True
        return check_result
    if mapping_config.get("range_type") == "customTs":
        for table_id in table_ids:
            qs = MetricListCache.objects.filter(
                data_source_label=DataSourceLabel.CUSTOM,
                data_type_label=DataTypeLabel.TIME_SERIES,
                result_table_id=table_id,
                metric_field=metric_field,
            )
            if qs.exists():
                check_result["is_exist"] = True
                check_result["table_id"] = table_id
                check_result["data_label"] = qs.first().data_label
                check_result["scenario"] = qs.first().result_table_label
                return check_result
    if mapping_config.get("range_type") == "bkPull":
        for table_id in table_ids:
            qs = MetricListCache.objects.filter(
                data_source_label=DataSourceLabel.BK_MONITOR_COLLECTOR,
                data_type_label=DataTypeLabel.TIME_SERIES,
                related_id=table_id,
                metric_field=metric_field,
            )
            if qs.exists():
                check_result["is_exist"] = True
                check_result["table_id"] = qs.first().result_table_id
                check_result["data_label"] = qs.first().data_label
                check_result["scenario"] = qs.first().result_table_label
                return check_result
    return check_result


re_time_parse = re.compile(r"^(\d+)([^\d]*)")
time_trans_mapping = {"w": 7 * 24 * 3600, "d": 24 * 3600, "h": 3600, "m": 60, "s": 1}
# PromQL match相关算符正则
re_ignoring_on_op = re.compile(r"(?![A-Za-z0-9_]) ?(ignoring|on) ?\(.*\) ?")
re_group_op = re.compile(r"(?![A-Za-z0-9_]) ?(group_left|group_right) ?(\([0-9a-zA-Z_ ]*\))?")
# 按表名判断数据源
re_custom_time_series = re.compile(r"\d+bkmonitor_time_series_\d+")
# 支持聚合方法
aggr_ops = {"sum", "avg", "mean", "max", "min", "count"}
# 条件算符转换
condition_op_mapping = {"req": "reg", "nreq": "nreg", "eq": "eq", "ne": "neq"}
# 指标ID正则
re_metric_id = re.compile(r"([A-Za-z0-9_]+(:[A-Za-z0-9_]+)+)")
# 内置k8s维度替换
k8s_dimension_map = {"cluster_id": "bcs_cluster_id"}
# 时间聚合函数映射
time_functon_map = {"count": "sum"}


def convert_metric_field(query, mapping_config):
    if not (query.get("field_name") or query.get("conditions") or query["conditions"].get("field_list")):
        return query
    global_mapping = mapping_config["mapping_detail"].get("global_mapping", {})
    if global_mapping:
        metric_map = global_mapping.get("metric_map", {})
        dimension_map = global_mapping.get("dimension_map", {})
        if metric_map.get(query["field_name"]):
            query["field_name"] = metric_map[query["field_name"]]
        for index, field in enumerate(query["conditions"]["field_list"]):
            if dimension_map.get(field["field_name"]):
                field["field_name"] = dimension_map[field["field_name"]]
        for function in query.get("function") or []:
            if function["method"] in aggr_ops and function["dimensions"]:
                function["dimensions"] = [
                    dimension_map.get(dimension, dimension) for dimension in function["dimensions"]
                ]
    default_mapping = mapping_config["mapping_detail"].get("default_mapping", [])
    for metric in default_mapping:
        if metric["metric_field"] == query["field_name"]:
            metric_map = metric["metric_map"][0]
            dimension_map = metric["dimension_map"]
            for index, field in enumerate(query["conditions"]["field_list"]):
                condition = {
                    "key": field["field_name"],
                    "method": condition_op_mapping[field["op"]],
                    "value": field["value"],
                }
                if condition in metric_map.get("where"):
                    query["field_name"] = metric_map["new_metric_field"]
                    query["conditions"]["field_list"].pop(index)
                    continue
                for item in dimension_map:
                    if condition["key"] == item.get("dimension_field", ""):
                        field["field_name"] = item.get("new_dimension_field", "")
            for function in query.get("function") or []:
                if function["method"] in aggr_ops and function["dimensions"]:
                    function["dimensions"] = [
                        dimension_map.get(dimension, dimension) for dimension in function["dimensions"]
                    ]
    return query
