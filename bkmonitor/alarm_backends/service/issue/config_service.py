"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
from typing import Optional

logger = logging.getLogger("alarm_backends")


class StrategyIssueConfigService:
    """StrategyIssueConfig 的创建 / 更新入口，含跨模型校验

    校验顺序：
      1. 跨模型子集校验（aggregate_dimensions ⊆ Strategy.public_dimensions）
      2. conditions.key 有效性校验（⊆ 生效维度集合）
      3. bk_biz_id 由 strategy_id 对应策略快照回填，不接受外部指定
      4. Model.clean() 格式校验（构造临时实例，不落库）
      5. 全部通过后才 update_or_create 落库（信号在此时触发）

    第一阶段通过 Django shell 调用；第二阶段 API 层直接复用。
    """

    @staticmethod
    def _get_strategy_public_dimensions(strategy: dict) -> set:
        """从策略快照中提取公共维度集合

        维度语义与现有策略模型保持一致：
          - 单 Item 取 Item.public_dimensions（即 query_configs 中所有 agg_dimension 的交集）
          - 多 Item 取各 Item 公共维度的交集（Strategy.public_dimensions）
        """
        item_public_dimensions = []
        for item in strategy.get("items", []):
            query_dimensions = []
            for query in item.get("query_configs", []):
                dims = {dim for dim in query.get("agg_dimension", []) if dim}
                if dims:
                    query_dimensions.append(dims)
            if not query_dimensions:
                continue
            item_public_dimensions.append(set.intersection(*query_dimensions))

        if not item_public_dimensions:
            return set()
        return set.intersection(*item_public_dimensions)

    @classmethod
    def validate_aggregate_dimensions(cls, strategy_id: int, aggregate_dimensions: list) -> None:
        """校验 aggregate_dimensions 是 Strategy.public_dimensions 的子集

        aggregate_dimensions 为空列表时跳过（表示使用 Strategy.public_dimensions 全量）。
        """
        if not aggregate_dimensions:
            return

        from alarm_backends.core.cache.strategy import StrategyCacheManager

        strategy = StrategyCacheManager.get_strategy_by_id(strategy_id)
        if not strategy:
            raise ValueError(f"strategy_id={strategy_id} 不存在或未缓存")

        strategy_dimensions = cls._get_strategy_public_dimensions(strategy)
        invalid = set(aggregate_dimensions) - strategy_dimensions
        if invalid:
            raise ValueError(
                f"aggregate_dimensions 包含当前策略公共维度之外的字段: {invalid}，"
                f"当前策略 Strategy.public_dimensions 为: {strategy_dimensions}"
            )

    @classmethod
    def validate_conditions(cls, conditions: list, effective_dimensions: set) -> None:
        """校验 conditions 中每条记录的 method 和 key 合法性"""
        valid_methods = {"eq", "neq", "include", "exclude", "reg", "nreg"}
        for cond in conditions:
            if cond.get("method") not in valid_methods:
                raise ValueError(f"不支持的 method: {cond.get('method')}")
            if cond.get("key") not in effective_dimensions:
                raise ValueError(
                    f"conditions.key={cond.get('key')} 不在可用维度集合中，"
                    f"当前可用维度为: {effective_dimensions}"
                )

    @classmethod
    def save(cls, strategy_id: int, config_data: dict) -> "StrategyIssueConfig":  # noqa: F821
        """创建或更新 StrategyIssueConfig

        :param strategy_id: 策略 ID
        :param config_data: 配置字段字典，支持的 key：
            - aggregate_dimensions: list[str]
            - conditions: list[dict]
            - alert_levels: list[int]
            - is_enabled: bool（可选，默认 True）
        :return: 保存后的 StrategyIssueConfig 实例
        """
        from alarm_backends.core.cache.strategy import StrategyCacheManager
        from bkmonitor.models.issue import StrategyIssueConfig

        aggregate_dimensions = config_data.get("aggregate_dimensions", [])
        conditions = config_data.get("conditions", [])

        # Step 1: 读取策略快照，统一做跨模型校验并回填 bk_biz_id
        strategy = StrategyCacheManager.get_strategy_by_id(strategy_id)
        if not strategy:
            raise ValueError(f"strategy_id={strategy_id} 不存在或未缓存")

        cls.validate_aggregate_dimensions(strategy_id, aggregate_dimensions)
        strategy_dimensions = cls._get_strategy_public_dimensions(strategy)
        effective_dimensions = set(aggregate_dimensions) if aggregate_dimensions else strategy_dimensions
        cls.validate_conditions(conditions, effective_dimensions)

        # bk_biz_id 由策略快照回填，不接受外部指定
        config_data = dict(config_data)
        config_data["bk_biz_id"] = strategy["bk_biz_id"]

        # Step 2: 构造临时实例，仅做格式校验，不落库，不触发信号
        temp = StrategyIssueConfig(strategy_id=strategy_id, **config_data)
        temp.full_clean(exclude=["create_user", "update_user"])  # 触发 Model.clean()

        # Step 3: 全部校验通过，写库（post_save 信号在此时触发缓存失效）
        config, _ = StrategyIssueConfig.objects.update_or_create(
            strategy_id=strategy_id,
            defaults=config_data,
        )
        return config

    @classmethod
    def get_effective_dimensions(cls, strategy_id: int, aggregate_dimensions: Optional[list] = None) -> set:
        """返回指定策略的生效维度集合

        :param strategy_id: 策略 ID
        :param aggregate_dimensions: 配置中的 aggregate_dimensions；None 或空列表时取 Strategy.public_dimensions
        :return: 生效维度 set
        """
        from alarm_backends.core.cache.strategy import StrategyCacheManager

        if aggregate_dimensions:
            return set(aggregate_dimensions)

        strategy = StrategyCacheManager.get_strategy_by_id(strategy_id)
        if not strategy:
            return set()
        return cls._get_strategy_public_dimensions(strategy)
