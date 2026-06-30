"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

运营数据指标注册表。

每个运营指标用一个 ``OperationMetric`` 描述，绑定一个取数 handler。
handler 统一签名为 ``handler(bk_biz_id: int, end_time: int | None = None) -> Any``。

注册表只负责"声明"与"存放"，具体取数逻辑在 ``handlers.py`` 中实现并调用 ``register_metric``。
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# 环境标识：用于在某个环境隐藏不存在的指标（如未部署 eBPF / doris 的环境）
ENV_ALL = "all"


class HandlerType(str, Enum):
    """取数方式类型（仅用于目录展示与说明，不影响调度）。"""

    PROMQL = "promql"  # 通过 unify-query 执行 PromQL
    COLLECTOR = "collector"  # 复用 monitor_web.statistics.v2 collector
    ORM = "orm"  # Django ORM 查询
    API = "api"  # bkdata / metadata / aiops 等 API 调用
    MANUAL = "manual"  # 暂无法程序化（仪表盘 / 人工口径），handler 为空


class MetricCategory(str, Enum):
    """运营指标分类（对齐 Excel 分区）。"""

    BASE = "base"  # 基础监控
    STORAGE = "storage"  # 指标存储
    APM = "apm"  # 观测能力 - APM
    LOG = "log"  # 观测能力 - 日志
    AIOPS = "aiops"  # AIOps 能力


@dataclass
class OperationMetric:
    key: str  # 全局唯一标识，如 "strategy_enabled_count"
    category: MetricCategory
    name: str  # 中文展示名
    unit: str  # 单位，如 "个" / "核" / "TB/天"；无单位用 ""
    description: str  # 双语描述，供 LLM 理解口径
    handler_type: HandlerType
    handler: Callable[..., Any] | None = None  # MANUAL 类为空
    supported_envs: list[str] = field(default_factory=lambda: [ENV_ALL])
    biz_scoped: bool = False  # True=按 bk_biz_id 过滤；False=平台总量
    slow: bool = False  # 慢查询（bkdata 多日循环 / aiops DB），overview 默认跳过
    cache_ttl: int = 0  # >0 时对取值结果做缓存（秒）
    note: str = ""  # 额外口径说明 / 人工取数指引

    def is_supported(self, env: str | None) -> bool:
        # env 未配置（None）时一律放行：环境门控仅在部署方显式设置 OPERATION_MCP_ENV 后生效
        if ENV_ALL in self.supported_envs or env is None:
            return True
        return env in self.supported_envs


# 全局注册表：key -> OperationMetric
OPERATION_METRIC_REGISTRY: dict[str, OperationMetric] = {}


def register_metric(metric: OperationMetric) -> OperationMetric:
    """注册一个运营指标，key 重复会直接抛错（避免静默覆盖）。"""
    if metric.key in OPERATION_METRIC_REGISTRY:
        raise ValueError(f"duplicate operation metric key: {metric.key}")
    OPERATION_METRIC_REGISTRY[metric.key] = metric
    return metric


def get_metric(key: str) -> OperationMetric | None:
    return OPERATION_METRIC_REGISTRY.get(key)


def iter_metrics(category: str | None = None, env: str | None = None) -> Iterator[OperationMetric]:
    """按分类 / 环境遍历注册表。"""
    for metric in OPERATION_METRIC_REGISTRY.values():
        if category and metric.category.value != category:
            continue
        if env and not metric.is_supported(env):
            continue
        yield metric
