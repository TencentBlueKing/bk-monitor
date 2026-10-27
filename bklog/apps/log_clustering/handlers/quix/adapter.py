"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

from apps.log_clustering.exceptions import QuixClusteringParamsInvalidException
from apps.log_clustering.models import LogClusteringRuntime

# 日志平台过滤操作符 -> BKBase LogClusteringSink 过滤方法
FILTER_OP_TO_METHOD = {
    "=": "eq",
    "!=": "neq",
    "contains": "include",
    "not contains": "exclude",
}
FILTER_CONDITIONS = ("and", "or")
DEFAULT_FILTER_CONDITION = "and"

# 首版每个索引只启用一个距离档位
DISTANCE_THRESHOLD = "0.5"

# 清洗后统一的毫秒时间字段，模型入参 timestamp 要求毫秒整数
INPUT_TIMESTAMP_FIELD = "dtEventTimeStamp"


def _invalid(detail: str) -> QuixClusteringParamsInvalidException:
    return QuixClusteringParamsInvalidException(QuixClusteringParamsInvalidException.MESSAGE.format(detail=detail))


def convert_filter_rules(filter_rules: list[dict]) -> list[dict]:
    """
    {fields_name, op, value, logic_operator} -> {key, method, value, condition}
    BKBase 按 and 组内组合、or 开新组求值，首条 condition 必须为空；空规则表示全部日志参与聚类
    过滤规则只筛选聚类候选，不能转换为原文清洗的 filter_rules
    """
    log_filter = []
    for index, rule in enumerate(filter_rules or []):
        position = index + 1
        key = rule.get("fields_name")
        if not key:
            raise _invalid(f"filter rule #{position} fields_name is empty")

        method = FILTER_OP_TO_METHOD.get(rule.get("op"))
        if not method:
            raise _invalid(f"filter rule #{position} op({rule.get('op')}) is not supported")

        value = rule.get("value")
        values = value if isinstance(value, list) else [value]
        if not values or any(item is None for item in values):
            raise _invalid(f"filter rule #{position} value is empty")

        condition = ""
        if index > 0:
            condition = (rule.get("logic_operator") or DEFAULT_FILTER_CONDITION).lower()
            if condition not in FILTER_CONDITIONS:
                raise _invalid(f"filter rule #{position} logic_operator({rule.get('logic_operator')}) is not supported")

        log_filter.append(
            {"key": key, "method": method, "value": [str(item) for item in values], "condition": condition}
        )
    return log_filter


def build_clustering_config(clustering_fields: str, filter_rules: list[dict]) -> dict:
    """运行绑定中保存的生效/待生效配置"""
    if not clustering_fields:
        raise _invalid("clustering_fields is empty")
    return {
        "log_filter": convert_filter_rules(filter_rules),
        "input_mapping": {"log": clustering_fields, "timestamp": INPUT_TIMESTAMP_FIELD},
        "distance_threshold": DISTANCE_THRESHOLD,
    }


def build_index_names(index_set_id: int) -> tuple[str, str]:
    """Pattern 与恢复状态索引名，首次开启时生成并保存在运行绑定中，重试和重开沿用"""
    return f"log-clustering-{index_set_id}-pattern", f"log-clustering-{index_set_id}-state"


def build_binding(runtime: LogClusteringRuntime, clustering_config: dict, max_message_bytes: int = None) -> dict:
    """
    组装 LogClusteringSink.spec.clustering.binding
    config_revision 取 BKFara input_revision，修改过滤规则不自行递增
    """
    binding = {
        "task_id": runtime.bkfara_task_id,
        "index_id": str(runtime.index_set_id),
        "generation": runtime.generation,
        "config_revision": runtime.input_revision,
        "kafka": runtime.kafka_binding,
        "log_filter": clustering_config["log_filter"],
        "input_mapping": clustering_config["input_mapping"],
        "distance_threshold": clustering_config["distance_threshold"],
        "pattern_index": runtime.pattern_index,
        "state_index": runtime.state_index,
    }
    if max_message_bytes:
        binding["max_message_bytes"] = max_message_bytes
    return binding
