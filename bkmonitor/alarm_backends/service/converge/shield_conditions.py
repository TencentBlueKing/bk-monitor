"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from bkmonitor.utils.metric_id import build_promql_metric_patterns
from bkmonitor.utils.range.conditions import EqualCondition

# 告警侧维度键，承载 PromQL 策略未截断的查询表达式。
#
# 单独占一个键而不是并入 metric_id：并入会让以 metric_id 为 key 的 dimension_conditions
# 多看到一个值，eq / include / issuperset 可能由不命中变命中，即屏蔽范围被动扩大。屏蔽范围
# 扩大等于漏告警，比屏蔽不生效更危险。该键不会出现在任何屏蔽配置里，因此不会被构造成条件，
# 只由本模块的 PromqlAwareMetricIdCondition 读取。
PROMQL_EXPRESSION_DIMENSION = "_promql_expressions"


class PromqlAwareMetricIdCondition(EqualCondition):
    """metric_id 维度的匹配条件，在等值匹配之外覆盖 PromQL 策略。

    PromQL 策略的 metric_id 是整段查询表达式（get_metric_id 对 prometheus 数据源直接返回
    promql），与屏蔽配置里的标准 metric_id 集合交恒为空，导致按指标屏蔽对引用同一底层指标
    的 PromQL 策略不生效。这里在等值匹配失败后，把配置的标准 metric_id 换算成 PromQL 指标
    名，再按 token 边界在表达式中搜索；多指标表达式命中任一即视为命中。

    换算或搜索不成立时返回 False，即维持“不屏蔽”，不让屏蔽范围被动扩大。
    """

    def is_match(self, data):
        if super().is_match(data):
            return True

        expressions = data.get(PROMQL_EXPRESSION_DIMENSION) or []
        if isinstance(expressions, str):
            expressions = [expressions]
        expressions = [expression for expression in expressions if expression]
        if not expressions:
            return False

        patterns = build_promql_metric_patterns(self.cond_field.to_str_list())
        if not patterns:
            return False

        return any(pattern.search(expression) for pattern in patterns for expression in expressions)


# 匹配语义与朴素等值不同的维度键在此登记专用条件类，其余维度键仍走 EqualCondition
DIMENSION_CONDITION_CLASSES: dict[str, type[EqualCondition]] = {"metric_id": PromqlAwareMetricIdCondition}
