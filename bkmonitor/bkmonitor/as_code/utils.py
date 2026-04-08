"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.utils.translation import gettext as _

from bkmonitor.as_code.ply.conditions import condition_lexer, conditions_parser
from bkmonitor.as_code.ply.function import function_lexer, function_parser
from bkmonitor.as_code.ply.threshold import threshold_lexer, threshold_parser
from bkmonitor.data_source import Functions, GrafanaFunctions
from constants.data_source import DataSourceLabel, DataTypeLabel


def parse_function(text: str) -> dict:
    """
    函数及参数解析
    """
    func_name, param_list = function_parser.parse(text, lexer=function_lexer)

    params = []
    if func_name in Functions or func_name in GrafanaFunctions:
        function = Functions.get(func_name, GrafanaFunctions.get(func_name))
        if len(param_list) != len(function.params):
            raise ValueError(_("{}参数数量不对").format(func_name))

        for param, param_info in zip(param_list, function.params):
            params.append({"id": param_info.id, "value": param})
    else:
        raise ValueError(_("{}函数不存在").format(func_name))

    return {"id": func_name, "params": params}


def parse_conditions(text: str) -> list:
    """
    条件表达式解析
    """
    if not text:
        return []
    return conditions_parser.parse(text, lexer=condition_lexer) or []


def parse_threshold(text: str) -> list[list[dict]]:
    return threshold_parser.parse(text, lexer=threshold_lexer)


def create_function_expression(config: dict):
    """
    生成函数表达式
    """
    params = []
    for p in config.get("params", []):
        params.append(str(p["value"]))
    return f"{config['id']}({', '.join([str(x) for x in params])})"


def create_threshold_expression(configs: list[list[dict]]):
    """
    生成静态阈值表达式
    """
    method_mapping = {
        "eq": "=",
        "neq": "!=",
        "gt": ">",
        "gte": ">=",
        "lt": "<",
        "lte": "<=",
        "is one of": "=",
        "is not one of": "!=",
    }

    expressions_list = []
    for config in configs:
        expressions = []
        for element in config:
            expressions.append(f"{method_mapping[element['method']]}{element['threshold']}")
        expressions_list.append(" and ".join(expressions))
    return " or ".join(expressions_list)


def create_conditions_expression(configs: list[dict]):
    """
    生成条件表达式
    """
    number_methods = ["gt", "gte", "lt", "lte", "eq", "neq"]

    method_mapping = {
        "eq": "=",
        "neq": "!=",
        "gt": ">",
        "gte": ">=",
        "lt": "<",
        "lte": "<=",
        "regex": "=~",
        "reg": "=~",
        "nreg": "!~",
        "nregex": "!~",
        "include": "=-",
        "exclude": "!-",
    }

    expressions = ""
    for config in configs:
        method = config["method"]
        key = config["key"]
        values = config["value"] if isinstance(config["value"], list) else [config["value"]]
        condition = config.get("condition", "and")

        if not values or method not in method_mapping:
            continue

        if isinstance(values[0], str) or method not in number_methods:
            expression = f'{key}{method_mapping[method]}"{",".join([str(v) for v in values])}"'
        else:
            expression = f"{key}{method_mapping[method]}{','.join([str(v) for v in values])}"

        if expressions:
            expressions += f" {condition} "
        expressions += expression

    return expressions


def parse_metric_id(data_source_label: str, data_type_label: str, metric_id: str) -> dict:
    data_source = (data_source_label, data_type_label)
    if data_source in (
        (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES),
        (DataSourceLabel.CUSTOM, DataTypeLabel.TIME_SERIES),
        (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.EVENT),
        (DataSourceLabel.BK_DATA, DataTypeLabel.TIME_SERIES),
        (DataSourceLabel.BK_APM, DataTypeLabel.TRACE),
    ):
        data_label = ""
        if "." in metric_id:
            result_table_id, metric_field = metric_id.rsplit(".", 1)
            if "." not in result_table_id:
                data_label = result_table_id
        else:
            result_table_id = ""
            metric_field = metric_id
            data_label = ""
        return {"result_table_id": result_table_id, "metric_field": metric_field, "data_label": data_label}
    elif data_source == (DataSourceLabel.BK_APM, DataTypeLabel.TIME_SERIES):
        *result_table_id, metric_field = metric_id.split(".", 2)
        result_table_id = ".".join(result_table_id)
        return {"result_table_id": result_table_id, "metric_field": metric_field}
    elif data_source == (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.LOG):
        return {"result_table_id": metric_id}
    elif data_source == (DataSourceLabel.BK_LOG_SEARCH, DataTypeLabel.TIME_SERIES):
        index_set_id, metric_field = metric_id.split(".", 1)
        return {"index_set_id": index_set_id, "metric_field": metric_field, "result_table_id": index_set_id}
    elif data_source == (DataSourceLabel.BK_LOG_SEARCH, DataTypeLabel.LOG):
        return {"index_set_id": metric_id, "result_table_id": metric_id}
    elif data_source == (DataSourceLabel.CUSTOM, DataTypeLabel.EVENT):
        result_table_id, custom_event_name = metric_id.rsplit(".", 1)
        if custom_event_name == "__INDEX__":
            custom_event_name = ""
        return {"result_table_id": result_table_id, "custom_event_name": custom_event_name}
    elif data_source in (
        (DataSourceLabel.BK_FTA, DataTypeLabel.EVENT),
        (DataSourceLabel.BK_FTA, DataTypeLabel.ALERT),
    ):
        return {"alert_name": metric_id}
    elif data_source == (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.ALERT):
        return {"bkmonitor_strategy_id": metric_id}
    elif data_source == (DataSourceLabel.PROMETHEUS, DataTypeLabel.TIME_SERIES):
        return {"promql": metric_id}

    raise ValueError(f"data_source({data_source_label}, {data_type_label}) not exists")


def get_metric_id(data_source_label: str, data_type_label: str, query_config: dict):
    data_source = (data_source_label, data_type_label)
    if data_source in (
        (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES),
        (DataSourceLabel.CUSTOM, DataTypeLabel.TIME_SERIES),
        (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.EVENT),
        (DataSourceLabel.BK_DATA, DataTypeLabel.TIME_SERIES),
        (DataSourceLabel.BK_APM, DataTypeLabel.TRACE),
    ):
        if query_config.get("data_label"):
            metric_id = f"{query_config['data_label']}.{query_config['metric_field']}"
        elif query_config.get("result_table_id"):
            metric_id = f"{query_config['result_table_id']}.{query_config['metric_field']}"
        else:
            metric_id = query_config["metric_field"]
    elif data_source == (DataSourceLabel.BK_APM, DataTypeLabel.TIME_SERIES):
        metric_id = f"{query_config['result_table_id']}.{query_config['metric_field']}"
    elif data_source == (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.LOG):
        metric_id = query_config["result_table_id"]
    elif data_source == (DataSourceLabel.BK_LOG_SEARCH, DataTypeLabel.TIME_SERIES):
        metric_id = f"{query_config['index_set_id']}.{query_config['metric_field']}"
    elif data_source == (DataSourceLabel.BK_LOG_SEARCH, DataTypeLabel.LOG):
        metric_id = str(query_config["index_set_id"])
    elif data_source == (DataSourceLabel.CUSTOM, DataTypeLabel.EVENT):
        metric_id = f"{query_config['result_table_id']}.{query_config['custom_event_name'] or '__INDEX__'}"
    elif data_source in (
        (DataSourceLabel.BK_FTA, DataTypeLabel.EVENT),
        (DataSourceLabel.BK_FTA, DataTypeLabel.ALERT),
    ):
        metric_id = query_config["alert_name"]
    elif data_source == (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.ALERT):
        metric_id = str(query_config["bkmonitor_strategy_id"])
    elif data_source == (DataSourceLabel.PROMETHEUS, DataTypeLabel.TIME_SERIES):
        metric_id = query_config["promql"]
    else:
        raise ValueError(f"data_source({data_source_label}, {data_type_label}) not exists")
    return metric_id


def parse_user(user: str) -> dict | None:
    """
    用户字段解析
    """
    splits = user.split("#")
    if len(splits) == 1:
        return {"id": splits[0], "type": "user"}
    elif len(splits) == 2:
        return {"id": splits[1], "type": splits[0]}
    return None
