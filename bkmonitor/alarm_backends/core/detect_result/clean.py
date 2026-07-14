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

from alarm_backends.constants import LATEST_NO_DATA_CHECK_POINT
from alarm_backends.core.cache import key
from alarm_backends.core.cache.key import (
    MD5_TO_DIMENSION_CACHE_KEY,
    OLD_MD5_TO_DIMENSION_CACHE_KEY,
)
from alarm_backends.core.control.item import detect_result_point_required
from alarm_backends.core.control.strategy import StrategyCacheManager
from bkmonitor.models import AlgorithmModel

DUMMY_DIMENSIONS_MD5 = "dummy_dimensions_md5"
CLEAN_EXPIRED_ARROW_REPLACE_TIME = {"hours": -5}

logger = logging.getLogger("core.detect_result")


class CleanResult:
    @staticmethod
    def clean_expired_detect_result(strategy_range=None):
        """
        清理检测结果及最近拉取结果的缓存
        """
        strategy_ids = StrategyCacheManager.get_strategy_ids()
        # 分片处理
        if strategy_range is not None:
            strategy_ids = [s_id for s_id in strategy_ids if s_id in range(*strategy_range)]

        strategies = StrategyCacheManager.get_strategy_by_ids(strategy_ids)

        client = key.LAST_CHECKPOINTS_CACHE_KEY.client
        pipeline = client.pipeline()
        for strategy in strategies:
            # 按照策略的检测与恢复周期配置，决定保留多少个周期的检测结果
            point_remain = detect_result_point_required(strategy)

            for item in strategy["items"]:
                # 获取监控项下所有的维度与级别组合
                last_checkpoints_cache_key = key.LAST_CHECKPOINTS_CACHE_KEY.get_key(
                    strategy_id=strategy["id"], item_id=item["id"]
                )
                all_hkeys = client.hkeys(last_checkpoints_cache_key)
                if not all_hkeys:
                    continue

                # 计算所有的检测结果缓存key
                check_result_cache_keys = []
                for index, hkey in enumerate(all_hkeys):
                    *_, dimension_md5, level = hkey.split(".")
                    check_result_cache_keys.append(
                        key.CHECK_RESULT_CACHE_KEY.get_key(
                            strategy_id=strategy["id"], item_id=item["id"], dimensions_md5=dimension_md5, level=level
                        )
                    )

                # 按保留点数清理检测结果缓存
                for index, check_result_cache_key in enumerate(check_result_cache_keys):
                    pipeline.zremrangebyrank(check_result_cache_key, 0, -point_remain)
                    # 一次最多清理5000个维度的检测结果
                    if index % 5000 == 4999:
                        pipeline.execute()
                pipeline.execute()

                # 批量获取检测结果缓存是否被清理
                check_result_lengths = []
                for index, check_result_cache_key in enumerate(check_result_cache_keys):
                    pipeline.zcard(check_result_cache_key)
                    if index % 5000 == 4999:
                        check_result_lengths.extend(pipeline.execute())
                check_result_lengths.extend(pipeline.execute())

                # 如果检测结果缓存被清理，同步清理last checkpoint
                index = 0
                for check_result_cache_key, check_result_length in zip(check_result_cache_keys, check_result_lengths):
                    if check_result_length > 0:
                        continue
                    *_, dimension_md5, level = check_result_cache_key.split(".")
                    if dimension_md5 == LATEST_NO_DATA_CHECK_POINT:
                        continue
                    last_checkpoints_cache_field = key.LAST_CHECKPOINTS_CACHE_KEY.get_field(
                        dimensions_md5=dimension_md5, level=level
                    )
                    pipeline.hdel(last_checkpoints_cache_key, last_checkpoints_cache_field)
                    if index % 5000 == 4999:
                        pipeline.execute()
                    index += 1
                pipeline.execute()

    @staticmethod
    def clean_new_series_seen_cache(strategy_range=None):
        """
        清理新维度值检测(NewSeries)的已见维度集合缓存：按阈值分组的 max_series 上限收口各 seen-zset。
        热路径只读写不淘汰(仅 2*max_series 安全阀)，故由本周期任务按 10w 上限做主清理。
        逐条 zremrangebyrank 分批删(每批 5000)，不下"一条删百万成员"的长命令。
        另：对无 TTL(ttl==-1)的 seen-zset 补设软 TTL，兜住"首写后 expire 前崩溃"导致的无 TTL 残留泄漏。
        """
        # 复用 detector 的签名口径，避免 clean 与 detector 双写漂移
        from alarm_backends.service.detect.strategy.new_series import NewSeries

        strategy_ids = StrategyCacheManager.get_strategy_ids()
        if strategy_range is not None:
            strategy_ids = [s_id for s_id in strategy_ids if s_id in range(*strategy_range)]
        strategies = StrategyCacheManager.get_strategy_by_ids(strategy_ids)

        client = key.NEW_SERIES_SEEN_KEY.client
        for strategy in strategies:
            for item in strategy["items"]:
                # 找出该 item 下的 NewSeries 算法(可能多 level，独占各自 level，共享同一 seen-zset)
                ns_algorithms = [
                    algorithm
                    for algorithm in item.get("algorithms") or []
                    if algorithm.get("type") == AlgorithmModel.AlgorithmChoices.NewSeries
                ]
                if not ns_algorithms:
                    continue

                ns_configs = [(algorithm.get("config") or {}) for algorithm in ns_algorithms]

                # seen key 含维度签名(配置层 agg_dimension 的稳定 md5)，与 detector 口径一致
                query_configs = item.get("query_configs") or []
                agg_dimension = query_configs[0].get("agg_dimension") if query_configs else None
                dimension_signature = NewSeries.signature_from_agg_dimension(agg_dimension)

                threshold_groups = {}
                for config in ns_configs:
                    threshold_groups.setdefault(int(config.get("threshold", 0)), []).append(config)

                for threshold, group_configs in threshold_groups.items():
                    # 每个阈值组独立使用组内最宽松配置，与 detector 写侧口径一致。
                    max_series = max(int(c.get("max_series", 100000)) for c in group_configs)
                    max_detect_range = max(int(c.get("detect_range", 0) or 0) for c in group_configs)
                    soft_ttl = max(max_detect_range * 2, 86400)
                    params = {
                        "strategy_id": strategy["id"],
                        "item_id": item["id"],
                        "dimension_signature": dimension_signature,
                    }
                    if threshold == 0:
                        seen_cache_key = key.NEW_SERIES_SEEN_KEY
                    else:
                        seen_cache_key = key.NEW_SERIES_THRESHOLD_SEEN_KEY
                        params["threshold"] = NewSeries.threshold_token(threshold)
                    seen_key = seen_cache_key.get_key(**params)

                    # 正常正 TTL 不续期；仅修复历史异常的无 TTL key。
                    if client.ttl(seen_key) == -1:
                        client.expire(seen_key, soft_ttl)

                    card = client.zcard(seen_key)
                    if card <= max_series:
                        continue

                    # 分批删最旧(score 升序=last_seen 最旧)，收口到组内 max_series。
                    excess = card - max_series
                    removed = 0
                    while removed < excess:
                        step = min(5000, excess - removed)
                        client.zremrangebyrank(seen_key, 0, step - 1)
                        removed += step
                    logger.info(
                        "clean_new_series_seen_cache strategy(%s) item(%s) threshold(%s) trimmed %s -> %s",
                        strategy["id"],
                        item["id"],
                        threshold,
                        card,
                        max_series,
                    )

    @staticmethod
    def clean_md5_to_dimension_cache():
        """
        清理无数据历史维度
        """
        # 清理旧的历史维度字段
        MD5_TO_DIMENSION_CACHE_KEY.client.delete(OLD_MD5_TO_DIMENSION_CACHE_KEY.get_key())

        strategy_ids = StrategyCacheManager.get_strategy_ids()
        strategies = StrategyCacheManager.get_strategy_by_ids(strategy_ids)

        pipeline = MD5_TO_DIMENSION_CACHE_KEY.client.pipeline()
        index = 0
        for strategy in strategies:
            for item in strategy["items"]:
                # 如果没有配置无数据告警，则不处理
                no_data_config = item.get("no_data_config", {})
                if not no_data_config.get("is_enabled", False):
                    continue

                md5_key = MD5_TO_DIMENSION_CACHE_KEY.get_key(
                    service_type="nodata", strategy_id=strategy["id"], item_id=item["id"]
                )
                pipeline.delete(md5_key)
                index += 1

                # 一次最多清理5000个维度的检测结果
                if index % 5000 == 4999:
                    pipeline.execute()
        pipeline.execute()
