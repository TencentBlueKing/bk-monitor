# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import os
from enum import Enum

# influxdb 的配置
INFLUXDB_PROXY_HOST = os.environ.get("BK_INFLUXDB_PROXY_HOST", "")
INFLUXDB_PROXY_PORT = os.environ.get("BK_INFLUXDB_PROXY_PORT", "")
RP_1M_RESOLUTION = 60
RP_5M_RESOLUTION = 5 * 60
RP_1H_RESOLUTION = 60 * 60
RP_12H_RESOLUTION = 12 * 60 * 60
DURATION = "720h"
DEFAULT_RP_NAME = "autogen"

RP_RESOLUTION_MAP = {"1m": RP_1M_RESOLUTION, "5m": RP_5M_RESOLUTION, "1h": RP_1H_RESOLUTION, "12h": RP_12H_RESOLUTION}

# Log Report Default QPS
LOG_REPORT_MAX_QPS = 50000

# 针对计算平台指标类型默认为double
METRIC_VALUE_TYPE = "double"

# 接入计算平台时，需要的时间格式长度
DEFAULT_TIMESTAMP_LEN = 13
DEFAULT_TIME_FORMAT = "Unix Time Stamp(milliseconds)"
SECOND_TIMESTAMP_FORMAT = "Unix Time Stamp(seconds)"
SECOND_TIMESTAMP_LEN = 10
AGG_FUNC_LIST = ["max", "min", "mean", "sum", "last"]

# 单指标单表的指标模板
SINGLE_METRIC_TEMPLATE = [
    {"type": "double", "assign_to": "value", "key": "value"},
    {"type": "string", "assign_to": "metric", "key": "key"},
]
SINGLE_METRIC_FIELD_TEMPLATE = [
    {"field_name": "value", "field_type": "double", "field_alias": "value", "is_dimension": False, "field_index": 1},
    {"field_name": "metric", "field_type": "string", "field_alias": "metric", "is_dimension": False, "field_index": 2},
    {"field_name": "time", "field_type": "long", "field_alias": "time", "is_dimension": False, "field_index": 3},
    {
        "field_name": "dimensions",
        "field_type": "text",
        "field_alias": "dimensions",
        "is_dimension": False,
        "field_index": 4,
    },
]

# 降精度数据清洗模板
# NOTE: 因为接入计算平台需要根据结果表类型确定是否传递指标属性
DATA_HUB_CLEAN_TEMPLATE = """
{"json_config": {"extract": {"type": "fun", "method": "from_json", "result":
"json", "args": [], "next": {"type": "branch", "name": "", "next": [{"type":
"access", "subtype": "access_obj", "key": "metrics", "result": "metrics",
"default_type": "None", "default_value": "", "next": {"type": "fun", "result":
"item", "args": [], "method": "items", "next": {"type": "assign", "subtype":
"assign_obj", "assign": {{assigns}}, "next": null}}}, {"type": "assign",
"subtype": "assign_obj", "assign": [{"type": "long", "assign_to": "time", "key":
"time"}], "next": null}, {"type": "assign", "subtype": "assign_json",
"sorted_key": true, "assign": [{"type": "text", "assign_to": "dimensions",
"key": "dimensions"}], "next": null}]}}, "conf": {"time_format":
"{{time_format}}", "timezone": 8, "time_field_name": "time",
"output_field_name": "timestamp", "timestamp_len": {{timestamp_len}},
"encoding": "UTF-8"}}, "result_table_name": "{{result_table_name}}",
"result_table_name_alias": "{{result_table_name_alias}}", "description": "tsdb",
"fields": {{fields}}}
"""

# 降精度数据计算模板
MULTI_METRIC_CALC_TEMPLATE = """
[{"result_table_id":"{{data_source}}","bk_biz_id":{{bk_biz_id}},"name":"{{data_source}}","id":7113,"
from_nodes":[],"node_type":"stream_source","frontend_info":{"x":277,"y":293}},{"bk_biz_id":{{bk_biz_
id}},"sql":"select {{result_table_fields}}, time, udf_pop_key_from_dimensions(dimensions,
'bk_cmdb_level') as dimensions from {{data_source}}","table_name":"one_{{step_suffix_name}}","name":
"one_{{step_suffix_name}}","count_freq":null,"waiting_time":null,"window_time":null,"window_type":"n
one","counter":null,"output_name":"one_{{step_suffix_name}}","session_gap":null,"expired_time":null,
"window_lateness":{"allowed_lateness":false,"lateness_time":1,"lateness_count_freq":60},"correct_con
fig_id":null,"is_open_correct":false,"id":7114,"from_nodes":[{"id":7113,"from_result_table_ids":["{{
data_source}}"]}],"node_type":"realtime","frontend_info":{"x":478,"y":293}},{"result_table_id":"{{bk
_biz_id}}_one_{{step_suffix_name}}","name":"{{step_suffix_name}}(hdfs_storage)","bk_biz_id":{{bk_biz
_id}},"cluster":"{{hdfs_cluster}}","expires":{{expires}},"dimension_table":false,"storage_keys":[],"
id":7120,"from_nodes":[{"id":7114,"from_result_table_ids":["{{bk_biz_id}}_one_{{step_suffix_name}}"]
}],"node_type":"hdfs_storage","frontend_info":{"x":476,"y":549}},{"bk_biz_id":{{bk_biz_id}},"sql":"s
elect '{{measurement_name}}' AS metric, dimensions, {{fields_with_calc_func}} from
{{bk_biz_id}}_one_{{step_suffix_name}} group by dimensions","table_name":"one_m_{{step_suffix_name}}
","name":"one_m_{{step_suffix_name}}","count_freq":60,"waiting_time":0,"window_time":null,"window_ty
pe":"scroll","counter":null,"output_name":"one_m_{{step_suffix_name}}","session_gap":null,"expired_t
ime":null,"window_lateness":{"allowed_lateness":false,"lateness_time":1,"lateness_count_freq":60},"c
orrect_config_id":null,"is_open_correct":false,"id":7279,"from_nodes":[{"id":7114,"from_result_table
_ids":["{{bk_biz_id}}_one_{{step_suffix_name}}"]}],"node_type":"realtime","frontend_info":{"x":810,"
y":197}},{"bk_biz_id":{{bk_biz_id}},"sql":"select '{{measurement_name}}' AS metric, dimensions,
{{fields_with_calc_func}} from {{bk_biz_id}}_one_{{step_suffix_name}} group by dimensions","table_na
me":"five_m_{{step_suffix_name}}","name":"five_m_{{step_suffix_name}}","count_freq":300,"waiting_tim
e":0,"window_time":null,"window_type":"scroll","counter":null,"output_name":"five_m_{{step_suffix_na
me}}","session_gap":null,"expired_time":null,"window_lateness":{"allowed_lateness":false,"lateness_t
ime":1,"lateness_count_freq":60},"correct_config_id":null,"is_open_correct":false,"id":7281,"from_no
des":[{"id":7114,"from_result_table_ids":["{{bk_biz_id}}_one_{{step_suffix_name}}"]}],"node_type":"r
ealtime","frontend_info":{"x":799,"y":377}},{"result_table_id":"{{bk_biz_id}}_one_m_{{step_suffix_na
me}}","name":"one_m_{{step_suffix_name}}(influxdb_storage)","bk_biz_id":{{bk_biz_id}},"cluster":"def
ault","dim_fields":null,"expires":3,"server_url":"{{influxdb_url}}","db":"{{influxdb_db}}","rp":"{{i
nfluxdb_rp_1m}}","id":7282,"from_nodes":[{"id":7279,"from_result_table_ids":["{{bk_biz_id}}_one_m_{{
step_suffix_name}}"]}],"node_type":"influxdb_storage","frontend_info":{"x":1058,"y":197}},{"result_t
able_id":"{{bk_biz_id}}_five_m_{{step_suffix_name}}","name":"five_m_{{step_suffix_name}}(influxdb_st
orage)","bk_biz_id":{{bk_biz_id}},"cluster":"default","dim_fields":null,"expires":3,"server_url":"{{
influxdb_url}}","db":"{{influxdb_db}}","rp":"{{influxdb_rp_5m}}","id":7283,"from_nodes":[{"id":7281,
"from_result_table_ids":["{{bk_biz_id}}_five_m_{{step_suffix_name}}"]}],"node_type":"influxdb_storag
e","frontend_info":{"x":1048,"y":377}},{"bk_biz_id":{{bk_biz_id}},"sql":"select
'{{measurement_name}}' AS metric, dimensions, {{fields_with_calc_func}} from
{{bk_biz_id}}_one_{{step_suffix_name}} group by dimensions","table_name":"one_h_{{step_suffix_name}}
","name":"one_h_{{step_suffix_name}}","window_type":"fixed","accumulate":false,"parent_tables":null,
"schedule_period":"hour","count_freq":1,"fallback_window":1,"fixed_delay":1,"delay_period":"hour","d
ata_start":null,"data_end":null,"delay":null,"output_name":"one_h_{{step_suffix_name}}","dependency_
config_type":"unified","unified_config":{"window_size":1,"window_size_period":"hour","dependency_rul
e":"all_finished"},"custom_config":{},"advanced":{"start_time":"","force_execute":false,"self_depend
ency":false,"recovery_enable":false,"recovery_times":1,"recovery_interval":"5m","self_dependency_con
fig":{"dependency_rule":"self_finished","fields":[]}},"correct_config_id":null,"is_open_correct":fal
se,"id":7284,"from_nodes":[{"id":7120,"from_result_table_ids":["{{bk_biz_id}}_one_{{step_suffix_name
}}"]}],"node_type":"offline","frontend_info":{"x":798,"y":488}},{"bk_biz_id":{{bk_biz_id}},"sql":"se
lect '{{measurement_name}}' AS metric, dimensions, {{fields_with_calc_func}} from
{{bk_biz_id}}_one_{{step_suffix_name}} group by dimensions","table_name":"twelve_h_{{step_suffix_nam
e}}","name":"twelve_h_{{step_suffix_name}}","window_type":"fixed","accumulate":false,"parent_tables"
:null,"schedule_period":"hour","count_freq":12,"fallback_window":1,"fixed_delay":1,"delay_period":"h
our","data_start":null,"data_end":null,"delay":null,"output_name":"twelve_h_{{step_suffix_name}}","d
ependency_config_type":"unified","unified_config":{"window_size":12,"window_size_period":"hour","dep
endency_rule":"all_finished"},"custom_config":{},"advanced":{"start_time":"","force_execute":false,"
self_dependency":false,"recovery_enable":false,"recovery_times":1,"recovery_interval":"5m","self_dep
endency_config":{"dependency_rule":"self_finished","fields":[]}},"correct_config_id":null,"is_open_c
orrect":false,"id":7285,"from_nodes":[{"id":7120,"from_result_table_ids":["{{bk_biz_id}}_one_{{step_
suffix_name}}"]}],"node_type":"offline","frontend_info":{"x":800,"y":661}},{"result_table_id":"{{bk_
biz_id}}_one_h_{{step_suffix_name}}","name":"one_h_{{step_suffix_name}}(influxdb_storage)","bk_biz_i
d":{{bk_biz_id}},"cluster":"default","dim_fields":null,"expires":3,"server_url":"{{influxdb_url}}","
db":"{{influxdb_db}}","rp":"{{influxdb_rp_1h}}","id":7286,"from_nodes":[{"id":7284,"from_result_tabl
e_ids":["{{bk_biz_id}}_one_h_{{step_suffix_name}}"]}],"node_type":"influxdb_storage","frontend_info"
:{"x":1050,"y":488}},{"result_table_id":"{{bk_biz_id}}_twelve_h_{{step_suffix_name}}","name":"twelve
_h_{{step_suffix_name}}(influxdb_storage)","bk_biz_id":{{bk_biz_id}},"cluster":"default","dim_fields
":null,"expires":3,"server_url":"{{influxdb_url}}","db":"{{influxdb_db}}","rp":"{{influxdb_rp_12h}}"
,"id":7287,"from_nodes":[{"id":7285,"from_result_table_ids":["{{bk_biz_id}}_twelve_h_{{step_suffix_n
ame}}"]}],"node_type":"influxdb_storage","frontend_info":{"x":1062,"y":661}}]
"""
SINGLE_METRIC_CALC_TEMPLATE = """
[{"result_table_id":"{{data_source}}","bk_biz_id":{{bk_biz_id}},"name":"{{data_source}}","id":7288,"
from_nodes":[],"node_type":"stream_source","frontend_info":{"x":30,"y":204}},{"bk_biz_id":{{bk_biz_i
d}},"sql":"select value, metric, time, udf_pop_key_from_dimensions(dimensions, 'bk_cmdb_level') as
dimensions from {{data_source}}","table_name":"one_{{step_suffix_name}}","name":"one_{{step_suffix_n
ame}}","count_freq":null,"waiting_time":null,"window_time":null,"window_type":"none","counter":null,
"output_name":"one_{{step_suffix_name}}","session_gap":null,"expired_time":null,"window_lateness":{"
allowed_lateness":false,"lateness_time":1,"lateness_count_freq":60},"correct_config_id":null,"is_ope
n_correct":false,"id":7289,"from_nodes":[{"id":7288,"from_result_table_ids":["{{data_source}}"]}],"n
ode_type":"realtime","frontend_info":{"x":355,"y":222}},{"result_table_id":"{{bk_biz_id}}_one_{{step
_suffix_name}}","name":"one_{{step_suffix_name}}(hdfs_storage)","bk_biz_id":{{bk_biz_id}},"cluster":
"{{hdfs_cluster}}","expires":{{bk_biz_id}}1,"dimension_table":false,"storage_keys":[],"id":7290,"fro
m_nodes":[{"id":7289,"from_result_table_ids":["{{bk_biz_id}}_one_{{step_suffix_name}}"]}],"node_type
":"hdfs_storage","frontend_info":{"x":680,"y":120}},{"bk_biz_id":{{bk_biz_id}},"sql":"select metric,
dimensions, count(1)  AS count_value, max(`value`) AS max_value, min(`value`) AS min_value,
sum(`value`) AS sum_value, avg(`value`) AS mean_value, last(`value`) AS last_value from
{{bk_biz_id}}_one_{{step_suffix_name}} group by metric, dimensions","table_name":"one_m_{{step_suffi
x_name}}","name":"one_m_{{step_suffix_name}}","count_freq":60,"waiting_time":0,"window_time":null,"w
indow_type":"scroll","counter":null,"output_name":"one_m_{{step_suffix_name}}","session_gap":null,"e
xpired_time":null,"window_lateness":{"allowed_lateness":false,"lateness_time":1,"lateness_count_freq
":60},"correct_config_id":null,"is_open_correct":false,"id":7292,"from_nodes":[{"id":7289,"from_resu
lt_table_ids":["{{bk_biz_id}}_one_{{step_suffix_name}}"]}],"node_type":"realtime","frontend_info":{"
x":680,"y":255}},{"bk_biz_id":{{bk_biz_id}},"sql":"select metric, dimensions, count(1) AS
count_value, max(`value`) AS max_value, min(`value`) AS min_value, sum(`value`) AS sum_value,
avg(`value`) AS mean_value, last(`value`) AS last_value from {{bk_biz_id}}_one_{{step_suffix_name}}
group by metric, dimensions","table_name":"five_m_{{step_suffix_name}}","name":"five_m_{{step_suffix
_name}}","count_freq":300,"waiting_time":0,"window_time":null,"window_type":"scroll","counter":null,
"output_name":"five_m_{{step_suffix_name}}","session_gap":null,"expired_time":null,"window_lateness"
:{"allowed_lateness":false,"lateness_time":1,"lateness_count_freq":60},"correct_config_id":null,"is_
open_correct":false,"id":7293,"from_nodes":[{"id":7289,"from_result_table_ids":["{{bk_biz_id}}_one_{
{step_suffix_name}}"]}],"node_type":"realtime","frontend_info":{"x":680,"y":357}},{"bk_biz_id":{{bk_
biz_id}},"sql":"select metric, dimensions, count(1) AS count_value, max(`value`) AS max_value,
min(`value`) AS min_value, sum(`value`) AS sum_value, avg(`value`) AS mean_value, last(`value`) AS
last_value from {{bk_biz_id}}_one_{{step_suffix_name}} group by metric, dimensions","table_name":"on
e_h_{{step_suffix_name}}","name":"one_h_{{step_suffix_name}}","window_type":"fixed","accumulate":fal
se,"parent_tables":null,"schedule_period":"hour","count_freq":1,"fallback_window":1,"fixed_delay":1,
"delay_period":"hour","data_start":null,"data_end":null,"delay":null,"output_name":"one_h_{{step_suf
fix_name}}","dependency_config_type":"unified","unified_config":{"window_size":1,"window_size_period
":"hour","dependency_rule":"all_finished"},"custom_config":{},"advanced":{"start_time":"","force_exe
cute":false,"self_dependency":false,"recovery_enable":false,"recovery_times":1,"recovery_interval":"
5m","self_dependency_config":{"dependency_rule":"self_finished","fields":[]}},"correct_config_id":nu
ll,"is_open_correct":false,"id":7294,"from_nodes":[{"id":7290,"from_result_table_ids":["{{bk_biz_id}
}_one_{{step_suffix_name}}"]}],"node_type":"offline","frontend_info":{"x":1005,"y":51}},{"bk_biz_id"
:{{bk_biz_id}},"sql":"select metric, dimensions, count(1) AS count_value, max(`value`) AS max_value,
min(`value`) AS min_value, sum(`value`) AS sum_value, avg(`value`) AS mean_value, last(`value`) AS
last_value from {{bk_biz_id}}_one_{{step_suffix_name}} group by metric, dimensions","table_name":"tw
elve_h_{{step_suffix_name}}","name":"twelve_h_{{step_suffix_name}}","window_type":"fixed","accumulat
e":false,"parent_tables":null,"schedule_period":"hour","count_freq":12,"fallback_window":1,"fixed_de
lay":1,"delay_period":"hour","data_start":null,"data_end":null,"delay":null,"output_name":"twelve_h_
{{step_suffix_name}}","dependency_config_type":"unified","unified_config":{"window_size":12,"window_
size_period":"hour","dependency_rule":"all_finished"},"custom_config":{},"advanced":{"start_time":""
,"force_execute":false,"self_dependency":false,"recovery_enable":false,"recovery_times":1,"recovery_
interval":"5m","self_dependency_config":{"dependency_rule":"self_finished","fields":[]}},"correct_co
nfig_id":null,"is_open_correct":false,"id":7295,"from_nodes":[{"id":7290,"from_result_table_ids":["{
{bk_biz_id}}_one_{{step_suffix_name}}"]}],"node_type":"offline","frontend_info":{"x":1023,"y":128}},
{"result_table_id":"{{bk_biz_id}}_one_m_{{step_suffix_name}}","name":"one_m_{{step_suffix_name}}(inf
luxdb_storage)","bk_biz_id":{{bk_biz_id}},"cluster":"default","dim_fields":null,"expires":3,"server_
url":"{{influxdb_url}}","db":"{{influxdb_db}}","rp":"{{influxdb_rp_1m}}","id":7296,"from_nodes":[{"i
d":7292,"from_result_table_ids":["{{bk_biz_id}}_one_m_{{step_suffix_name}}"]}],"node_type":"influxdb
_storage","frontend_info":{"x":1005,"y":255}},{"result_table_id":"{{bk_biz_id}}_five_m_{{step_suffix
_name}}","name":"five_m_{{step_suffix_name}}(influxdb_storage)","bk_biz_id":{{bk_biz_id}},"cluster":
"default","dim_fields":null,"expires":3,"server_url":"{{influxdb_url}}","db":"{{influxdb_db}}","rp":
"{{influxdb_rp_5m}}","id":7297,"from_nodes":[{"id":7293,"from_result_table_ids":["{{bk_biz_id}}_five
_m_{{step_suffix_name}}"]}],"node_type":"influxdb_storage","frontend_info":{"x":1005,"y":357}},{"res
ult_table_id":"{{bk_biz_id}}_one_h_{{step_suffix_name}}","name":"one_h_{{step_suffix_name}}(influxdb
_storage)","bk_biz_id":{{bk_biz_id}},"cluster":"default","dim_fields":null,"expires":3,"server_url":
"{{influxdb_url}}","db":"{{influxdb_db}}","rp":"{{influxdb_rp_1h}}","id":7298,"from_nodes":[{"id":72
94,"from_result_table_ids":["{{bk_biz_id}}_one_h_{{step_suffix_name}}"]}],"node_type":"influxdb_stor
age","frontend_info":{"x":1330,"y":51}},{"result_table_id":"{{bk_biz_id}}_twelve_h_{{step_suffix_nam
e}}","name":"twelve_h_{{step_suffix_name}}(influxdb_storage)","bk_biz_id":{{bk_biz_id}},"cluster":"d
efault","dim_fields":null,"expires":3,"server_url":"{{influxdb_url}}","db":"{{influxdb_db}}","rp":"{
{influxdb_rp_12h}}","id":7299,"from_nodes":[{"id":7295,"from_result_table_ids":["{{bk_biz_id}}_twelv
e_h_{{step_suffix_name}}"]}],"node_type":"influxdb_storage","frontend_info":{"x":1330,"y":153}}]
"""
FIXED_METRIC_CALC_TEMPLATE = """
[{"result_table_id":"{{bk_biz_id}}_{{data_source}}","bk_biz_id":{{bk_biz_id}},"name":"{{data_source}
}","id":7303,"from_nodes":[],"node_type":"stream_source","frontend_info":{"x":30,"y":204}},{"bk_biz_
id":{{bk_biz_id}},"sql":"select {{result_table_fields}}, time,
udf_pop_key_from_dimensions(dimensions, 'bk_cmdb_level') as dimensions from {{bk_biz_id}}_{{data_sou
rce}}","table_name":"one_{{step_suffix_name}}","name":"one_{{step_suffix_name}}","count_freq":null,"
waiting_time":null,"window_time":null,"window_type":"none","counter":null,"output_name":"one_{{step_
suffix_name}}","session_gap":null,"expired_time":null,"window_lateness":{"allowed_lateness":false,"l
ateness_time":1,"lateness_count_freq":60},"correct_config_id":null,"is_open_correct":false,"id":7304
,"from_nodes":[{"id":7303,"from_result_table_ids":["{{bk_biz_id}}_{{data_source}}"]}],"node_type":"r
ealtime","frontend_info":{"x":355,"y":222}},{"bk_biz_id":{{bk_biz_id}},"sql":"select
'{{measurement_name}}' as metric, dimensions, {{fields_with_calc_func}} from
{{bk_biz_id}}_one_{{step_suffix_name}} group by dimensions","table_name":"one_m_one_{{step_suffix_na
me}}","name":"one_m_one_{{step_suffix_name}}","count_freq":60,"waiting_time":0,"window_time":null,"w
indow_type":"scroll","counter":null,"output_name":"one_m_one_{{step_suffix_name}}","session_gap":nul
l,"expired_time":null,"window_lateness":{"allowed_lateness":false,"lateness_time":1,"lateness_count_
freq":60},"correct_config_id":null,"is_open_correct":false,"id":7305,"from_nodes":[{"id":7304,"from_
result_table_ids":["{{bk_biz_id}}_one_{{step_suffix_name}}"]}],"node_type":"realtime","frontend_info
":{"x":680,"y":51}},{"bk_biz_id":{{bk_biz_id}},"sql":"select dimensions, {{calc_fields_with_concat}}
from {{bk_biz_id}}_one_m_one_{{step_suffix_name}}","table_name":"one_m_two_{{step_suffix_name}}","na
me":"one_m_two_{{step_suffix_name}}","count_freq":null,"waiting_time":null,"window_time":null,"windo
w_type":"none","counter":null,"output_name":"one_m_two_{{step_suffix_name}}","session_gap":null,"exp
ired_time":null,"window_lateness":{"allowed_lateness":false,"lateness_time":1,"lateness_count_freq":
60},"correct_config_id":null,"is_open_correct":false,"id":7306,"from_nodes":[{"id":7305,"from_result
_table_ids":["{{bk_biz_id}}_one_m_one_{{step_suffix_name}}"]}],"node_type":"realtime","frontend_info
":{"x":1005,"y":51}},{"bk_biz_id":{{bk_biz_id}},"sql":"SELECT '{{measurement_name}}' as metric,
dimensions, metric_name, metric_value from {{bk_biz_id}}_one_m_two_{{step_suffix_name}}, LATERAL
TABLE(udf_str_to_row_field({{concat_metric_info}}, '\\^', '\\#')) AS T(metric_name, metric_value);",
"table_name":"one_m_three_{{step_suffix_name}}","name":"one_m_three_{{step_suffix_name}}","count_fre
q":null,"waiting_time":null,"window_time":null,"window_type":"none","counter":null,"output_name":"on
e_m_three_{{step_suffix_name}}","session_gap":null,"expired_time":null,"window_lateness":{"allowed_l
ateness":false,"lateness_time":1,"lateness_count_freq":60},"correct_config_id":null,"is_open_correct
":false,"id":7307,"from_nodes":[{"id":7306,"from_result_table_ids":["{{bk_biz_id}}_one_m_two_{{step_
suffix_name}}"]}],"node_type":"realtime","frontend_info":{"x":1330,"y":51}},{"bk_biz_id":{{bk_biz_id
}},"sql":"select '{{measurement_name}}' as metric, dimensions, {{fields_with_calc_func}} from
{{bk_biz_id}}_one_{{step_suffix_name}} group by dimensions","table_name":"five_m_one_{{step_suffix_n
ame}}","name":"five_m_one_{{step_suffix_name}}","count_freq":300,"waiting_time":0,"window_time":null
,"window_type":"scroll","counter":null,"output_name":"five_m_one_{{step_suffix_name}}","session_gap"
:null,"expired_time":null,"window_lateness":{"allowed_lateness":false,"lateness_time":1,"lateness_co
unt_freq":60},"correct_config_id":null,"is_open_correct":false,"id":7309,"from_nodes":[{"id":7304,"f
rom_result_table_ids":["{{bk_biz_id}}_one_{{step_suffix_name}}"]}],"node_type":"realtime","frontend_
info":{"x":680,"y":153}},{"bk_biz_id":{{bk_biz_id}},"sql":"select dimensions,
{{calc_func_with_concat}} from {{bk_biz_id}}_five_m_one_{{step_suffix_name}}","table_name":"five_m_t
wo_{{step_suffix_name}}","name":"five_m_two_{{step_suffix_name}}","count_freq":null,"waiting_time":n
ull,"window_time":null,"window_type":"none","counter":null,"output_name":"five_m_two_{{step_suffix_n
ame}}","session_gap":null,"expired_time":null,"window_lateness":{"allowed_lateness":false,"lateness_
time":1,"lateness_count_freq":60},"correct_config_id":null,"is_open_correct":false,"id":7310,"from_n
odes":[{"id":7309,"from_result_table_ids":["{{bk_biz_id}}_five_m_one_{{step_suffix_name}}"]}],"node_
type":"realtime","frontend_info":{"x":1005,"y":153}},{"bk_biz_id":{{bk_biz_id}},"sql":"SELECT
'{{measurement_name}}' as metric, dimensions, metric_name, metric_value from
{{bk_biz_id}}_five_m_two_{{step_suffix_name}}, LATERAL
TABLE(udf_str_to_row_field({{concat_metric_info}},'\\^','\\#')) AS T(metric_name, metric_value);","t
able_name":"five_m_three_{{step_suffix_name}}","name":"five_m_three_{{step_suffix_name}}","count_fre
q":null,"waiting_time":null,"window_time":null,"window_type":"none","counter":null,"output_name":"fi
ve_m_three_{{step_suffix_name}}","session_gap":null,"expired_time":null,"window_lateness":{"allowed_
lateness":false,"lateness_time":1,"lateness_count_freq":60},"correct_config_id":null,"is_open_correc
t":false,"id":7311,"from_nodes":[{"id":7310,"from_result_table_ids":["{{bk_biz_id}}_five_m_two_{{ste
p_suffix_name}}"]}],"node_type":"realtime","frontend_info":{"x":1330,"y":153}},{"result_table_id":"{
{bk_biz_id}}_one_{{step_suffix_name}}","name":"one_{{step_suffix_name}}(hdfs_storage)","bk_biz_id":{
{bk_biz_id}},"cluster":"{{hdfs_cluster}}","expires":{{expires}},"dimension_table":false,"storage_key
s":[],"id":7348,"from_nodes":[{"id":7304,"from_result_table_ids":["{{bk_biz_id}}_one_{{step_suffix_n
ame}}"]}],"node_type":"hdfs_storage","frontend_info":{"x":680,"y":324}},{"bk_biz_id":{{bk_biz_id}},"
sql":"select '{{measurement_name}}' as metric, dimensions, {{fields_with_calc_func}} from
{{bk_biz_id}}_one_{{step_suffix_name}} group by dimensions","table_name":"one_h_one_{{step_suffix_na
me}}","name":"one_h_one_{{step_suffix_name}}","window_type":"fixed","accumulate":false,"parent_table
s":null,"schedule_period":"hour","count_freq":1,"fallback_window":1,"fixed_delay":1,"delay_period":"
hour","data_start":null,"data_end":null,"delay":null,"output_name":"one_h_one_{{step_suffix_name}}",
"dependency_config_type":"unified","unified_config":{"window_size":1,"window_size_period":"hour","de
pendency_rule":"all_finished"},"custom_config":{},"advanced":{"start_time":"","force_execute":false,
"self_dependency":false,"recovery_enable":false,"recovery_times":1,"recovery_interval":"5m","self_de
pendency_config":{"dependency_rule":"self_finished","fields":[]}},"correct_config_id":null,"is_open_
correct":false,"id":7349,"from_nodes":[{"id":7348,"from_result_table_ids":["{{bk_biz_id}}_one_{{step
_suffix_name}}"]}],"node_type":"offline","frontend_info":{"x":1005,"y":255}},{"bk_biz_id":{{bk_biz_i
d}},"sql":"select dimensions, {{calc_func_with_concat}} from {{bk_biz_id}}_one_h_one_{{step_suffix_n
ame}}","table_name":"one_h_two_{{step_suffix_name}}","name":"one_h_two_{{step_suffix_name}}","window
_type":"fixed","accumulate":false,"parent_tables":null,"schedule_period":"hour","count_freq":1,"fall
back_window":1,"fixed_delay":1,"delay_period":"hour","data_start":null,"data_end":null,"delay":null,
"output_name":"one_h_two_{{step_suffix_name}}","dependency_config_type":"unified","unified_config":{
"window_size":1,"window_size_period":"hour","dependency_rule":"all_finished"},"custom_config":{},"ad
vanced":{"start_time":"","force_execute":false,"self_dependency":false,"recovery_enable":false,"reco
very_times":1,"recovery_interval":"5m","self_dependency_config":{"fields":[],"dependency_rule":"self
_finished"}},"correct_config_id":null,"is_open_correct":false,"id":7354,"from_nodes":[{"id":7349,"fr
om_result_table_ids":["{{bk_biz_id}}_one_h_one_{{step_suffix_name}}"]}],"node_type":"offline","front
end_info":{"x":1330,"y":255}},{"bk_biz_id":{{bk_biz_id}},"sql":"select '{{measurement_name}}' as
metric, dimensions, {{fields_with_calc_func}} from {{bk_biz_id}}_one_{{step_suffix_name}} group by d
imensions","table_name":"twelve_h_one_{{step_suffix_name}}","name":"twelve_h_one_{{step_suffix_name}
}","window_type":"fixed","accumulate":false,"parent_tables":null,"schedule_period":"hour","count_fre
q":12,"fallback_window":1,"fixed_delay":1,"delay_period":"hour","data_start":null,"data_end":null,"d
elay":null,"output_name":"twelve_h_one_{{step_suffix_name}}","dependency_config_type":"unified","uni
fied_config":{"window_size":12,"window_size_period":"hour","dependency_rule":"all_finished"},"custom
_config":{},"advanced":{"start_time":"","force_execute":false,"self_dependency":false,"recovery_enab
le":false,"recovery_times":1,"recovery_interval":"5m","self_dependency_config":{"dependency_rule":"s
elf_finished","fields":[]}},"correct_config_id":null,"is_open_correct":false,"id":7369,"from_nodes":
[{"id":7348,"from_result_table_ids":["{{bk_biz_id}}_one_{{step_suffix_name}}"]}],"node_type":"offlin
e","frontend_info":{"x":1005,"y":357}},{"bk_biz_id":{{bk_biz_id}},"sql":"select dimensions,
{{calc_func_with_concat}} from {{bk_biz_id}}_twelve_h_one_{{step_suffix_name}}","table_name":"twelve
_h_two_{{step_suffix_name}}","name":"twelve_h_two_{{step_suffix_name}}","window_type":"fixed","accum
ulate":false,"parent_tables":null,"schedule_period":"hour","count_freq":12,"fallback_window":1,"fixe
d_delay":1,"delay_period":"hour","data_start":null,"data_end":null,"delay":null,"output_name":"twelv
e_h_two_{{step_suffix_name}}","dependency_config_type":"unified","unified_config":{"window_size":12,
"window_size_period":"hour","dependency_rule":"all_finished"},"custom_config":{},"advanced":{"start_
time":"","force_execute":false,"self_dependency":false,"recovery_enable":false,"recovery_times":1,"r
ecovery_interval":"5m","self_dependency_config":{"dependency_rule":"self_finished","fields":[]}},"co
rrect_config_id":null,"is_open_correct":false,"id":7370,"from_nodes":[{"id":7369,"from_result_table_
ids":["{{bk_biz_id}}_twelve_h_one_{{step_suffix_name}}"]}],"node_type":"offline","frontend_info":{"x
":1330,"y":357}},{"bk_biz_id":{{bk_biz_id}},"sql":"SELECT '{{measurement_name}}' as metric,
dimensions, metric_name, metric_value from {{bk_biz_id}}_one_h_two_{{step_suffix_name}}, LATERAL
TABLE(udf_str_to_row_field({{concat_metric_info}},'\\^','\\#')) AS T(metric_name, metric_value);","t
able_name":"one_h_three_{{step_suffix_name}}","name":"one_h_three_{{step_suffix_name}}","window_type
":"fixed","accumulate":false,"parent_tables":null,"schedule_period":"hour","count_freq":1,"fallback_
window":1,"fixed_delay":1,"delay_period":"hour","data_start":null,"data_end":null,"delay":null,"outp
ut_name":"one_h_three_{{step_suffix_name}}","dependency_config_type":"unified","unified_config":{"wi
ndow_size":1,"window_size_period":"hour","dependency_rule":"all_finished"},"custom_config":{},"advan
ced":{"start_time":"","force_execute":false,"self_dependency":false,"recovery_enable":false,"recover
y_times":1,"recovery_interval":"5m","self_dependency_config":{"dependency_rule":"self_finished","fie
lds":[]}},"correct_config_id":null,"is_open_correct":false,"id":7394,"from_nodes":[{"id":7354,"from_
result_table_ids":["{{bk_biz_id}}_one_h_two_{{step_suffix_name}}"]}],"node_type":"offline","frontend
_info":{"x":1661,"y":258}},{"bk_biz_id":{{bk_biz_id}},"sql":"SELECT '{{measurement_name}}' as
metric, dimensions, metric_name, metric_value from
{{bk_biz_id}}_twelve_h_two_{{step_suffix_name}},LATERAL
TABLE(udf_str_to_row_field({{concat_metric_info}},'\\^','\\#')) AS T(metric_name, metric_value);","t
able_name":"twelve_h_three_{{step_suffix_name}}","name":"twelve_h_three_{{step_suffix_name}}","windo
w_type":"fixed","accumulate":false,"parent_tables":null,"schedule_period":"hour","count_freq":12,"fa
llback_window":1,"fixed_delay":1,"delay_period":"hour","data_start":null,"data_end":null,"delay":nul
l,"output_name":"twelve_h_three_{{step_suffix_name}}","dependency_config_type":"unified","unified_co
nfig":{"window_size":12,"window_size_period":"hour","dependency_rule":"all_finished"},"custom_config
":{},"advanced":{"start_time":"","force_execute":false,"self_dependency":false,"recovery_enable":fal
se,"recovery_times":1,"recovery_interval":"5m","self_dependency_config":{"dependency_rule":"self_fin
ished","fields":[]}},"correct_config_id":null,"is_open_correct":false,"id":7395,"from_nodes":[{"id":
7370,"from_result_table_ids":["{{bk_biz_id}}_twelve_h_two_{{step_suffix_name}}"]}],"node_type":"offl
ine","frontend_info":{"x":1647,"y":354}},{"result_table_id":"{{bk_biz_id}}_one_m_three_{{step_suffix
_name}}","name":"one_m_three_{{step_suffix_name}}(influxdb_storage)","bk_biz_id":{{bk_biz_id}},"clus
ter":"default","dim_fields":null,"expires":3,"server_url":"{{influxdb_url}}","db":"{{influxdb_db}}",
"rp":"{{influxdb_rp_1m}}","id":7396,"from_nodes":[{"id":7307,"from_result_table_ids":["{{bk_biz_id}}
_one_m_three_{{step_suffix_name}}"]}],"node_type":"influxdb_storage","frontend_info":{"x":1883,"y":1
6}},{"result_table_id":"{{bk_biz_id}}_five_m_three_{{step_suffix_name}}","name":"five_m_three_{{step
_suffix_name}}(influxdb_storage)","bk_biz_id":{{bk_biz_id}},"cluster":"default","dim_fields":null,"e
xpires":3,"server_url":"{{influxdb_url}}","db":"{{influxdb_db}}","rp":"{{influxdb_rp_5m}}","id":7397
,"from_nodes":[{"id":7311,"from_result_table_ids":["{{bk_biz_id}}_five_m_three_{{step_suffix_name}}"
]}],"node_type":"influxdb_storage","frontend_info":{"x":1914,"y":154}},{"result_table_id":"{{bk_biz_
id}}_one_h_three_{{step_suffix_name}}","name":"one_h_three_{{step_suffix_name}}(influxdb_storage)","
bk_biz_id":{{bk_biz_id}},"cluster":"default","dim_fields":null,"expires":3,"server_url":"{{influxdb_
url}}","db":"{{influxdb_db}}","rp":"{{influxdb_rp_1h}}","id":7398,"from_nodes":[{"id":7394,"from_res
ult_table_ids":["{{bk_biz_id}}_one_h_three_{{step_suffix_name}}"]}],"node_type":"influxdb_storage","
frontend_info":{"x":1909,"y":307}},{"result_table_id":"{{bk_biz_id}}_twelve_h_three_{{step_suffix_na
me}}","name":"twelve_h_three_{{step_suffix_name}}(influxdb_storage)","bk_biz_id":{{bk_biz_id}},"clus
ter":"default","dim_fields":null,"expires":3,"server_url":"{{influxdb_url}}","db":"{{influxdb_db}}",
"rp":"{{influxdb_rp_12h}}","id":7399,"from_nodes":[{"id":7395,"from_result_table_ids":["{{bk_biz_id}
}_twelve_h_three_{{step_suffix_name}}"]}],"node_type":"influxdb_storage","frontend_info":{"x":1854,"
y":433}}]
"""


class BkDataTaskStatus(Enum):
    """任务状态"""

    NO_ACCESS = "no-access"
    NO_CREATE = "no-create"
    NO_START = "no-start"

    ACCESSING = "accessing"
    CREATING = "creating"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"

    ACCESS_FAILED = "access-failed"
    CREATE_FAILED = "create-failed"
    START_FAILED = "start-failed"
    STOP_FAILED = "stop-failed"


class MeasurementType(Enum):
    """结果表类型

    TODO: 注意后续和空间功能逻辑合并
    """

    BK_TRADITIONAL = "bk_traditional_measurement"
    BK_SPLIT = "bk_split_measurement"
    BK_EXPORTER = "bk_exporter"
    BK_STANDARD_V2_TIME_SERIES = "bk_standard_v2_time_series"


# Influxdb Redis Keys
# 前缀
INFLUXDB_KEY_PREFIX = "bkmonitorv3:influxdb"
# 存储的集群信息
INFLUXDB_CLUSTER_INFO_KEY = "cluster_info"
# 集群关联的主机信息
INFLUXDB_HOST_INFO_KEY = "host_info"
# 标签信息，主要是用于数据分片
INFLUXDB_TAG_INFO_KEY = "tag_info"
# 结果表使用的 proxy 集群和实际存储集群的关联关系
INFLUXDB_PROXY_STORAGE_ROUTER_KEY = "influxdb_proxy"
# proxy 和 backend 的映射关系
INFLUXDB_PROXY_STORAGE_INFO_KEY = "influxdb_proxy_storage"
# unify query 需要的的更多字段
INFLUXDB_ADDITIONAL_INFO_FOR_UNIFY_QUERY = "query_router_info"
# 查询 vm 存储的路由信息
QUERY_VM_STORAGE_ROUTER_KEY = "query_vm_router"

# 批量写入数量限制
BULK_CREATE_BATCH_SIZE = 2000

# 批量更新数据限制, 防止数量上千，降低效率
BULK_UPDATE_BATCH_SIZE = 500

# 忽略的结果表类型
IGNORED_STORAGE_CLUSTER_TYPES = ["victoria_metrics"]

# 忽略同步consul的data_id
IGNORED_CONSUL_SYNC_DATA_IDS = [1002, 1003, 1004, 1005, 1006]

# db 重复标识
DB_DUPLICATE_ID = 1062

# ES别名延迟过期时间
ES_ALIAS_EXPIRED_DELAY_DAYS = 1


class ESScopeTypes(Enum):
    """可见范围类型"""

    ONLY_CURRENT_SPACE = "only_current_space"
    MANY_SPACE = "many_space"
    PLATFORM_SPACE = "platform_space"
    SPACE_FIELDS = "space_fields"
