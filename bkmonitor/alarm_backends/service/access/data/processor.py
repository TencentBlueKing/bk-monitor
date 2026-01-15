"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import base64
import gzip
import json
import logging
import queue
import signal
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta

import arrow
import pytz
from django.conf import settings
from kafka import KafkaConsumer
from kafka.consumer.fetcher import ConsumerRecord
from kafka.errors import NoBrokersAvailable

from alarm_backends import constants
from alarm_backends.cluster import TargetType
from alarm_backends.core.cache import clear_mem_cache, key
from alarm_backends.core.cache.result_table import ResultTableCacheManager
from alarm_backends.core.cache.strategy import StrategyCacheManager
from alarm_backends.core.cluster import get_cluster
from alarm_backends.core.control.checkpoint import Checkpoint
from alarm_backends.core.control.item import Item
from alarm_backends.core.control.strategy import Strategy
from alarm_backends.core.storage.redis import Cache
from alarm_backends.core.storage.redis_cluster import get_node_by_strategy_id
from alarm_backends.management.hashring import HashRing
from alarm_backends.service.access import base
from alarm_backends.service.access.data.duplicate import Duplicate
from alarm_backends.service.access.data.filters import (
    ExpireFilter,
    HostStatusFilter,
    RangeFilter,
)
from alarm_backends.service.access.data.fullers import TopoNodeFuller
from alarm_backends.service.access.data.records import DataRecord
from alarm_backends.service.access.priority import PriorityChecker
from alarm_backends.core.circuit_breaking.manager import AccessDataCircuitBreakingManager
from bkmonitor.utils.common_utils import count_md5, get_local_ip
from bkmonitor.utils.consul import BKConsul
from bkmonitor.utils.local import local
from bkmonitor.utils.thread_backend import InheritParentThread
from constants.data_source import DataSourceLabel, DataTypeLabel
from constants.strategy import MULTI_METRIC_DATA_SOURCES
from core.drf_resource import api
from core.errors.api import BKAPIError
from core.prometheus import metrics

IP = get_local_ip()
logger = logging.getLogger("access.data")


class BaseAccessDataProcess(base.BaseAccessProcess):
    def __init__(self, *args, sub_task_id: str = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_filter(RangeFilter())
        self.add_filter(ExpireFilter())
        self.add_filter(HostStatusFilter())

        self.add_fuller(TopoNodeFuller())

        self.sub_task_id = sub_task_id
        self.batch_count = 1
        self.process_counts = {}

    def post_handle(self):
        # 释放主机信息本地内存
        clear_mem_cache("host_cache")

    def _check_circuit_breaking_before_pull(self) -> bool:
        """在数据查询前检查策略级别熔断并剔除触发熔断的策略。

        :return: True 表示所有策略都被熔断，需要跳过数据查询；False 表示仍有策略需要处理
        :raises: 不会抛出异常，内部已处理所有异常情况
        """
        if not hasattr(self, "items"):
            return False

        circuit_breaking_manager = AccessDataCircuitBreakingManager()
        circuit_breaking_strategies = []
        remaining_items = []

        # 检查策略组中的每个策略是否需要熔断（只检查策略ID维度）
        for item in self.items:
            strategy = item.strategy

            # 只检查策略级别的熔断（其他维度已在任务分发模块处理）
            if circuit_breaking_manager.is_strategy_only_circuit_breaking(
                strategy_id=strategy.id, labels=getattr(strategy, "labels", None)
            ):
                circuit_breaking_strategies.append(
                    {
                        "strategy_id": strategy.id,
                        "item_id": item.id,
                    }
                )
            else:
                # 未触发熔断的策略保留
                remaining_items.append(item)

        # 如果有策略触发熔断，记录日志并更新策略列表
        if circuit_breaking_strategies:
            strategy_group_key = getattr(self, "strategy_group_key", "unknown")

            for cb_strategy in circuit_breaking_strategies:
                logger.warning(
                    f"[circuit breaking] [access.data] strategy({cb_strategy['strategy_id']}),"
                    f"item({cb_strategy['item_id']}) "
                    f"circuit breaking triggered before data pull, "
                    f"strategy_group_key: {strategy_group_key}"
                )

            logger.info(
                f"[circuit breaking] [access.data] circuit breaking applied before data pull: "
                f"{len(circuit_breaking_strategies)}/{len(self.items)} strategies filtered, "
                f"remaining: {len(remaining_items)} strategies, "
                f"strategy_group_key: {strategy_group_key}"
            )

            # 更新策略列表，只保留未熔断的策略
            self.items = remaining_items

            # 如果所有策略都被熔断，返回True跳过数据查询
            if not remaining_items:
                logger.info(
                    f"[circuit breaking] [access.data] all strategies in group {strategy_group_key} are circuit broken, "
                    f"skipping data query"
                )
                return True

        return False

    def pull(self):
        pass

    def _push_noise_data(self, item, record_list):
        noise_reduce_config = item.strategy.notice.get("options", {}).get("noise_reduce_config")
        if not (noise_reduce_config and noise_reduce_config.get("is_enabled")):
            logger.debug(
                "skip to add noise data for strategy(%s) due to noise reduce is not enabled", item.strategy.strategy_id
            )
            return
        client = key.NOISE_REDUCE_TOTAL_KEY.client
        dimension_hash = count_md5(noise_reduce_config["dimensions"])
        record_key = key.NOISE_REDUCE_TOTAL_KEY.get_key(
            strategy_id=item.strategy.strategy_id, noise_dimension_hash=dimension_hash
        )
        noise_data = defaultdict()
        for record in record_list:
            dimensions = record.data["dimensions"]
            dimension_value = {
                dimension_key: dimensions.get(dimension_key) for dimension_key in noise_reduce_config["dimensions"]
            }
            logger.debug("strategy(%s) noise reduce dimension_value(%s)", item.strategy.strategy_id, dimension_value)
            dimension_value_hash = count_md5(dimension_value)
            noise_data[dimension_value_hash] = record.data["time"]
        client.zadd(record_key, noise_data)
        client.expire(record_key, key.NOISE_REDUCE_TOTAL_KEY.ttl)

        # 非批量任务，记录日志
        if not self.sub_task_id:
            logger.info(
                "record_key({record_key}) "
                "dimension_key({dimension_key})"
                "strategy({strategy_id}), item({item_id}), "
                "push dimension records({records_length}).".format(
                    record_key=record_key,
                    dimension_key="|".join(noise_reduce_config["dimensions"]),
                    strategy_id=item.strategy.strategy_id,
                    item_id=item.id,
                    records_length=len(noise_data.keys()),
                )
            )
        else:
            self.process_counts.setdefault("push_noise_data", {})
            self.process_counts["push_noise_data"][str(item.id)] = {
                "record_key": record_key,
                "dimension_key": "|".join(noise_reduce_config["dimensions"]),
                "count": len(noise_data.keys()),
            }

    def _push(self, item, record_list, output_client=None, data_list_key=None):
        """
        :summary: 推送单个item的数据到检测队列或无数据待检测队列
        :param item
        :param record_list
        :param output_client
        :param data_list_key：数据队列，默认为 key.DATA_LIST_KEY
        """
        data_list_key = data_list_key or key.DATA_LIST_KEY
        client = output_client or data_list_key.client
        output_key = data_list_key.get_key(strategy_id=item.strategy.strategy_id, item_id=item.id)
        queue_length = client.llen(output_key)
        # 超过最大检测长度10倍(50w)说明detect模块处理能力不足,数据将被丢弃。
        if queue_length > settings.SQL_MAX_LIMIT * 10:
            msg = (
                f"Critical: strategy({item.strategy.strategy_id}), item({item.id})"
                f"The number of ({output_key}) records to be detected has "
                f"exceeded {queue_length}/{settings.SQL_MAX_LIMIT * 10}. "
                f"Please check if the detect process is running normally."
            )
            raise Exception(msg)

        pipeline = client.pipeline(transaction=False)
        _offset = 0
        while _offset < len(record_list):
            chunk_records = record_list[_offset : _offset + 10000]
            pipeline.lpush(output_key, *[json.dumps(record.data) for record in chunk_records])
            _offset += 10000
        # 避免监控周期大于默认key过期时间，引起数据丢失
        agg_interval = min(query_config["agg_interval"] for query_config in item.query_configs)
        pipeline.expire(output_key, max([data_list_key.ttl, agg_interval * 5]))
        pipeline.execute()
        metrics.ACCESS_PROCESS_PUSH_DATA_COUNT.labels(strategy_id=metrics.TOTAL_TAG, type="data").inc(len(record_list))

        # 非批量任务，记录日志
        if not self.sub_task_id:
            logger.info(
                f"output_key({output_key}) "
                f"strategy({item.strategy.strategy_id}), item({item.id}), "
                f"push records({len(record_list)})."
            )
        else:
            self.process_counts.setdefault("push_data", {})
            self.process_counts["push_data"][str(item.id)] = {
                "output_key": output_key,
                "count": len(record_list),
            }

    def push(self, records: list | None = None, output_client=None):
        """
        推送格式化后的数据到 detect 和 nodata 中(按单个策略，单个item项，写入不同的队列)
        """
        if records is None:
            records = self.record_list

        # 去除重复数据
        records: list[DataRecord] = [record for record in records if not record.is_duplicate]

        # 优先级检查
        PriorityChecker.check_records(records)

        # 按item_id分组
        pending_to_push: dict[int, list[DataRecord]] = {}
        item_id_to_item: dict[int, Item] = {}
        for record in records:
            for item in record.items:
                item_id = item.id
                pending_to_push.setdefault(item_id, [])
                item_id_to_item[item_id] = item

                if record.is_retains[item_id] and not record.inhibitions[item_id]:
                    pending_to_push[item_id].append(record)

        strategy_ids = set()
        for item_id, record_list in list(pending_to_push.items()):
            item = item_id_to_item[item_id]
            if record_list:
                strategy_ids.add(item.strategy.id)

                # 推送到检测队列
                self._push(item, record_list, output_client)

                # 推送降噪基数至redis队列
                try:
                    self._push_noise_data(item, record_list)
                except BaseException as e:
                    logger.exception("push noise data of strategy(%s) error, %s", item.strategy.id, str(e))

            logger.info(
                "strategy_group_key(%s) strategy(%s) item(%s) push records to detect done",
                item.strategy.strategy_group_key,
                item.strategy.id,
                item.id,
            )
            # 推送无数据处理
            if item.no_data_config["is_enabled"]:
                self._push(item, records, output_client, key.NO_DATA_LIST_KEY)

        # 推送数据处理信号
        if records:
            client = output_client or key.DATA_SIGNAL_KEY.client
            if strategy_ids:
                client.lpush(key.DATA_SIGNAL_KEY.get_key(), *list(strategy_ids))
            client.expire(key.DATA_SIGNAL_KEY.get_key(), key.DATA_SIGNAL_KEY.ttl)


class AccessDataProcess(BaseAccessDataProcess):
    def __init__(self, strategy_group_key: str, *args, sub_task_id: str = None, **kwargs):
        super().__init__(sub_task_id=sub_task_id, *args, **kwargs)
        self.strategy_group_key = strategy_group_key
        self.from_timestamp = None
        self.until_timestamp = None

        if sub_task_id:
            self.batch_timestamp = int(sub_task_id.split(".")[0])
        else:
            self.batch_timestamp = None

    def __str__(self):
        return f"{self.__class__.__name__}:strategy_group_key({self.strategy_group_key})"

    def _load_items(self) -> list[Item]:
        """加载策略项列表"""
        data = []
        records = StrategyCacheManager.get_strategy_group_detail(self.strategy_group_key)
        for strategy_id, item_ids in list(records.items()):
            try:
                strategy_id = int(strategy_id)
            except ValueError:
                continue
            strategy = Strategy(strategy_id)
            for item in strategy.items:
                if item.id in item_ids:
                    data.append(item)
        data.sort(key=lambda _i: _i.strategy.id)
        return data

    @property
    def items(self) -> list[Item]:
        """获取策略项列表，支持动态修改"""
        if not hasattr(self, "_items") or self._items is None:
            self._items = self._load_items()
        return self._items

    @items.setter
    def items(self, value: list[Item]):
        """设置策略项列表"""
        self._items = value

    @staticmethod
    def get_max_local_time(records):
        """
        获取最大数据落地时间并剔除该字段
        """
        local_time_map = {}
        for record in records:
            local_time = record.pop("_localTime", None)
            point_time = record["_time_"]
            if not local_time:
                continue

            local_time = datetime.strptime(local_time, "%Y-%m-%d %H:%M:%S").replace(tzinfo=pytz.utc)
            if point_time not in local_time_map:
                local_time_map[point_time] = local_time

            if local_time > local_time_map[point_time]:
                local_time_map[point_time] = local_time

        # localTime不是UTC时间，而是计算平台的机器时间
        for k, v in local_time_map.items():
            local_time_map[k] += timedelta(hours=settings.BKDATA_LOCAL_TIMEZONE_OFFSET)

        return sorted(local_time_map.items(), key=lambda x: x[0])

    def pull(self):
        """
        1. 根据策略配置获取到需要拉取的数据
        2. 格式化数据，增加记录ID
        """
        if not self.items:
            return

        # 熔断检查：在数据查询前进行熔断判定
        if self._check_circuit_breaking_before_pull():
            # 如果需要熔断，直接返回，不进行数据查询
            return

        now_timestamp = arrow.utcnow().timestamp

        # 设置查询时间范围
        self.get_query_time_range(now_timestamp)

        # 如果策略更新导致查询时间错位，则跳过本次查询
        if self.from_timestamp > self.until_timestamp:
            return

        # 数据查询
        local.strategy_id = ",".join([str(item.strategy.id) for item in self.items])
        try:
            points = self.query_data(now_timestamp)
            if getattr(local, "strategy_id", None):
                delattr(local, "strategy_id")
        except Exception as e:
            if getattr(local, "strategy_id", None):
                delattr(local, "strategy_id")
            raise e

        # 当点数大于阈值时，将数据拆分为多个批量任务
        point_total = len(points)
        if point_total > (settings.ACCESS_DATA_BATCH_PROCESS_THRESHOLD or 500000):
            # 为分组中的每个策略分别记录指标（修复指标漏报问题）
            # Access 数据拉取基于分组，一个分组可能包含多个策略，且可能使用不同的 Redis 节点
            for item in self.items:
                strategy_id = item.strategy.id
                cache_node = get_node_by_strategy_id(strategy_id)
                redis_node = cache_node.node_alias or f"{cache_node.host}:{cache_node.port}"

                # 为每个策略记录指标（使用总数据点数作为参考）
                metrics.PROCESS_OVER_FLOW.labels(
                    module="access.data",
                    strategy_id=item.strategy.id,
                    bk_biz_id=item.strategy.bk_biz_id,
                    strategy_name=item.strategy.name,
                    redis_node=redis_node,
                ).inc(point_total)
            if settings.ACCESS_DATA_BATCH_PROCESS_THRESHOLD > 0:
                points = self.send_batch_data(points, settings.ACCESS_DATA_BATCH_PROCESS_SIZE)

        # 过滤重复数据并实例化
        self.filter_duplicates(points)

    def query_data(self, now_timestamp: int) -> list[dict]:
        """
        数据源查询
        """
        first_item = self.items[0]

        # 由于某些数据源需要进行策略分组，因此需要将条件置为空
        if not (first_item.data_source_types & MULTI_METRIC_DATA_SOURCES):
            first_item.data_sources[0]._advance_where = []

        bkdata_tmp_advance_where = []
        # 计算平台指标查询localTime
        if DataSourceLabel.BK_DATA in first_item.data_source_labels:
            if len(first_item.expression.strip()) <= 1:
                # 未配置多指标表达式， 则基于 bksql 查询，判断 localtime
                first_item.data_sources[0].metrics.append(
                    {"field": "localTime", "method": "MAX", "alias": "_localTime"}
                )
                for item in self.items:
                    item.data_sources[0].rollback_query()
                # 暂存高级过滤条件，清空高级过滤条件，后过滤
                bkdata_tmp_advance_where = first_item.data_sources[0]._advance_where.copy()
                first_item.data_sources[0]._advance_where = []

        try:
            points = first_item.query_record(self.from_timestamp, self.until_timestamp)
            # 判定is_partial
            if first_item.query.is_partial:
                logger.info(
                    f"strategy_group_key({self.strategy_group_key}) strategy({first_item.strategy.id}) "
                    f"query records is partial, one of points: {points[:1]}"
                )
                if first_item.strategy.id in settings.DOUBLE_CHECK_SUM_STRATEGY_IDS:
                    logger.warning(f"double_check strategy({first_item.strategy.id}) is partial: skip query results")
                    points = []
        except BKAPIError as e:
            logger.error(e)
            points = []
        except Exception as e:  # noqa
            logger.exception(f"strategy_group_key({self.strategy_group_key}) query records error, {e}")
            points = []

        # 如果最大的localTime离得太近，那就存下until_timestamp，下次再拉取数据
        if DataSourceLabel.BK_DATA in first_item.data_source_labels:
            local_time_list = self.get_max_local_time(points)
            first_item.data_sources[0].metrics = [
                m for m in first_item.data_sources[0].metrics if m["field"] != "localTime"
            ]
            # 如果之前暂存了过滤条件，则恢复
            if bkdata_tmp_advance_where and not first_item.data_sources[0]._advance_where:
                for item in self.items:
                    item.data_sources[0]._advance_where = bkdata_tmp_advance_where
            filter_point_time = None
            for point_time, max_local_time in local_time_list:
                if now_timestamp - max_local_time.timestamp() <= settings.BKDATA_LOCAL_TIME_THRESHOLD:
                    agg_interval = min(query_config["agg_interval"] for query_config in first_item.query_configs)
                    key.ACCESS_END_TIME_KEY.client.set(
                        key.ACCESS_END_TIME_KEY.get_key(group_key=self.strategy_group_key),
                        str(self.until_timestamp),
                        # key超时时间低于监控周期，会导致数据缓存丢失
                        ex=max([key.ACCESS_END_TIME_KEY.ttl, agg_interval * 5]),
                    )
                    logging.info(
                        f"skip access {self.strategy_group_key} data because data local time is too close."
                        f"now: {now_timestamp}, local time: {max_local_time.timestamp()}, point_time: {point_time}"
                    )
                    filter_point_time = point_time
                    break
            if filter_point_time:
                points = list(filter(lambda point: point["_time_"] < filter_point_time, points))
        return points

    def get_query_time_range(self, now_timestamp: int):
        """
        获取查询时间范围
        """
        first_item = self.items[0]
        agg_interval = min(query_config["agg_interval"] for query_config in first_item.query_configs)
        min_last_checkpoint = min([i.item_config["update_time"] for i in self.items])
        checkpoint = Checkpoint(self.strategy_group_key).get(min_last_checkpoint, interval=agg_interval)
        checkpoint = checkpoint // agg_interval * agg_interval

        # 由于存在入库延时问题，每次多往前拉取settings.NUM_OF_COUNT_FREQ_ACCESS个周期的数据
        self.from_timestamp = checkpoint - settings.NUM_OF_COUNT_FREQ_ACCESS * agg_interval

        # 计算平台类型尝试获取上次未处理完的时间
        until_timestamp = None
        if DataSourceLabel.BK_DATA in first_item.data_source_labels:
            end_time_key = key.ACCESS_END_TIME_KEY.get_key(group_key=self.strategy_group_key)
            client = key.ACCESS_END_TIME_KEY.client

            until_timestamp_str = client.get(end_time_key)
            if until_timestamp_str:
                client.delete(end_time_key)
                until_timestamp = int(until_timestamp_str)
            else:
                until_timestamp = 0

        time_delay = settings.ACCESS_DATA_TIME_DELAY
        if first_item.time_delay:
            time_delay += first_item.time_delay
        elif (DataSourceLabel.BK_LOG_SEARCH, DataTypeLabel.LOG) in first_item.data_source_types:
            time_delay += 60
        elif first_item.use_aiops_sdk:
            # bkbase智能检测flow默认有1分钟的计算等待延迟, SDK智能检测保持相同的逻辑
            time_delay += 60

        if not until_timestamp:
            # 非计算平台数据源：
            # 由于存在入库延时问题，SUM等聚合方式最后一个点的结果会不准确，所以后台检测往前推 ACCESS_DATA_TIME_DELAY 秒
            # 保证查询时间范围是< until_timestamp 而不是<=即可
            until_timestamp = (now_timestamp - time_delay) // agg_interval * agg_interval

        self.until_timestamp = until_timestamp

    def send_batch_data(self, points: list[dict], batch_threshold: int = 50000) -> list[dict]:
        """
        发送分批处理任务，并返回第一批数据
        """
        from alarm_backends.service.access.tasks import run_access_batch_data

        self.batch_timestamp = int(time.time())

        client = key.ACCESS_BATCH_DATA_KEY.client
        first_batch_points = []
        latest_record_timestamp = None
        last_batch_index, batch_count = 0, 0
        for index, record in enumerate(points):
            timestamp = record.get("_time_") or record["time"]
            # 当数据点数不足或数据同属一个时间点时，数据点记为同一批次
            if (index - last_batch_index < batch_threshold or latest_record_timestamp == timestamp) and index < len(
                points
            ) - 1:
                latest_record_timestamp = timestamp
                continue

            # 记录当前批次数
            batch_count += 1

            if index == len(points) - 1:
                batch_points = points[last_batch_index:]
            else:
                batch_points = points[last_batch_index:index]

            # 第一批数据原地处理
            if batch_count == 1:
                first_batch_points = batch_points
            else:
                # 将分批数据写入redis
                sub_task_id = f"{self.batch_timestamp}.{batch_count}"
                data_key = key.ACCESS_BATCH_DATA_KEY.get_key(
                    strategy_group_key=self.strategy_group_key, sub_task_id=sub_task_id
                )
                data_key.strategy_id = self.items[0].strategy.id
                compress_batch_points = base64.b64encode(gzip.compress(json.dumps(batch_points).encode("utf-8")))
                client.set(data_key, compress_batch_points, ex=key.ACCESS_BATCH_DATA_KEY.ttl)

                # 发起异步任务
                run_access_batch_data.delay(self.strategy_group_key, sub_task_id)

            # 记录下一轮的起始位置
            last_batch_index = index

        if batch_count > 1:
            self.sub_task_id = f"{self.batch_timestamp}.1"
            self.batch_count = batch_count
            logger.info(
                f"strategy_group_key({self.strategy_group_key}), split {len(points)} access data into {batch_count} batch tasks"
            )

        return first_batch_points

    def filter_duplicates(self, points: list[dict]):
        """
        过滤重复数据并实例化
        """
        first_item = self.items[0]
        max_agg_interval = max(query_config["agg_interval"] for query_config in first_item.query_configs)
        records = []
        dup_obj = Duplicate(self.strategy_group_key, strategy_id=first_item.strategy.id, ttl=max_agg_interval * 10)
        duplicate_counts = none_point_counts = 0

        # 是否有优先级
        have_priority = False
        for item in self.items:
            if item.strategy.priority is not None and item.strategy.priority_group_key:
                have_priority = True
                break

        max_data_time = 0
        for record in reversed(points):
            point = DataRecord(self.items, record)

            if point.value is not None:
                # 去除重复数据
                if dup_obj.is_duplicate(point):
                    duplicate_counts += 1
                    # 有优先级的策略，重复数据需要保留，后续再过滤
                    if have_priority:
                        point.is_duplicate = True
                        records.append(point)
                else:
                    dup_obj.add_record(point)
                    records.append(point)

                    # 只观察非重复数据
                    if point.time > max_data_time:
                        max_data_time = point.time
            else:
                none_point_counts += 1

        # 如果当前数据延迟超过一定值，则上报延迟埋点
        # 对于非batch的数据，有可能存在数据稀疏的情况，因此在filter duplicate后再进行延迟统计
        if max_data_time > 0 and not self.batch_timestamp and self.until_timestamp:
            self.observe_big_latency_datasource(first_item, max_data_time)

        dup_obj.refresh_cache()
        self.record_list = records
        point_count = len(records)
        if point_count:
            metrics.ACCESS_DATA_PROCESS_PULL_DATA_COUNT.labels(strategy_group_key=metrics.TOTAL_TAG).inc(point_count)

        # 日志记录按strategy + item 来记录，方便问题排查
        for item in self.items:
            if not self.sub_task_id:
                logger.info(
                    f"strategy({item.strategy.id}),item({item.id}),"
                    f"total_records({len(points)}),"
                    f"access records({point_count}),"
                    f"duplicate({duplicate_counts}),"
                    f"none_point_counts({none_point_counts}),"
                    f"strategy_group_key({self.strategy_group_key}),"
                    f"time range({arrow.get(self.from_timestamp).strftime(constants.STD_LOG_DT_FORMAT)} - {arrow.get(self.until_timestamp).strftime(constants.STD_LOG_DT_FORMAT)})"
                )
            else:
                self.process_counts.setdefault("pull_data", {})
                self.process_counts["pull_data"][str(item.id)] = {
                    "total_count": len(points),
                    "access_count": point_count,
                    "duplicate_count": duplicate_counts,
                    "none_point_count": none_point_counts,
                }

    def _limit_records_by_time_points(self, records: list) -> tuple[list, int | None]:
        """
        限制处理的时间点数量（方案 B）。

        限制的是唯一时间点数量，同一时间点的所有序列数据会被完整保留或完整丢弃。
        这样可以控制推送到下游 detect 模块的数据量，避免故障恢复后一次性处理过量数据。

        注意：
        - 仅对 TIME_SERIES 类型数据生效，日志关键字等其他类型不受影响
        - 查询逻辑保持不变，仅在处理阶段进行限制
        - checkpoint 更新为最后处理的时间点，确保逐步补齐历史数据

        Args:
            records: 原始数据记录列表

        Returns:
            tuple: (限制后的记录列表, 最后处理的时间点 或 None（未触发限制）)
        """
        if not records:
            return records, None

        # 检查是否为时序数据类型
        first_item = self.items[0]
        is_time_series = DataTypeLabel.TIME_SERIES in first_item.data_type_labels

        if not is_time_series:
            # 非时序数据，不做限制
            return records, None

        max_time_points = settings.ACCESS_DATA_MAX_TIME_POINTS

        # 提取所有唯一时间点并排序
        unique_times = sorted(set(r.time for r in records))

        if len(unique_times) <= max_time_points:
            # 时间点数量未超限，不做限制
            return records, None

        # 取前 N 个时间点
        allowed_times = set(unique_times[:max_time_points])
        last_time_point = max(allowed_times)

        # 过滤：只保留允许时间点内的所有序列数据
        limited_records = [r for r in records if r.time in allowed_times]

        logger.info(
            f"strategy_group_key({self.strategy_group_key}) time points limited: "
            f"total={len(unique_times)}, processed={max_time_points}, "
            f"last_time_point={last_time_point}, "
            f"records: {len(records)} -> {len(limited_records)}"
        )

        return limited_records, last_time_point

    def _is_all_static_threshold(self, item: Item) -> bool:
        """
        判断 Item 的所有检测算法是否均为静态阈值。

        静态阈值算法的特点：
        - 纯计算：只需要当前数据点的值，不依赖历史数据
        - 无外部依赖：不需要调用外部服务
        - 计算简单：只是简单的数值比较

        Args:
            item: 策略项

        Returns:
            bool: True 表示所有算法都是静态阈值
        """
        for algorithm in item.algorithms:
            # Threshold 算法类型
            if algorithm.get("type") != "Threshold":
                return False
        return True

    def _can_merge_access_detect(self) -> bool:
        """
        判断当前策略组是否可以进行 access-detect 合并处理。

        条件：
        1. 配置开关启用
        2. 策略的所有检测算法均为静态阈值
        3. 如果配置了灰度列表，策略必须在灰度列表中

        Returns:
            bool: True 表示可以合并处理
        """
        # 检查开关
        if not settings.ACCESS_DETECT_MERGE_ENABLED:
            return False

        # 检查是否有策略项
        if not self.items:
            return False

        # 检查灰度列表
        merge_strategy_ids = getattr(settings, "ACCESS_DETECT_MERGE_STRATEGY_IDS", [])
        if merge_strategy_ids:
            # 如果配置了灰度列表，检查策略是否在列表中
            for item in self.items:
                if item.strategy.id not in merge_strategy_ids:
                    return False

        # 检查所有 Item 的算法类型
        for item in self.items:
            if not self._is_all_static_threshold(item):
                return False

        return True

    def _detect_and_push_abnormal(self, output_client=None):
        """
        在 access 模块直接执行静态阈值检测，并推送异常数据。

        优化方案：复用 DetectProcess，避免重复实现检测逻辑。
        通过 pull_data(item, inputs=data_points) 直接传入数据，
        自动获得所有监控指标（延迟统计、大延迟告警、double_check 等）。

        流程：
        1. 去重和优先级检查（复用 access 原有逻辑）
        2. 创建 DetectProcess 实例
        3. gen_strategy_snapshot 生成策略快照
        4. pull_data(item, inputs=data_points) 直接传入数据
        5. handle_data 执行检测
        6. double_check 二次确认（自动获得）
        7. push_data 推送异常数据（自动获得所有监控指标）
        8. 推送无数据检测数据
        9. 推送降噪数据
        10. 上报 detect 模块指标（DETECT_PROCESS_TIME/COUNT）

        Args:
            output_client: Redis 客户端（可选）
        """
        from alarm_backends.service.detect import DataPoint
        from alarm_backends.service.detect.process import DetectProcess

        # 记录检测开始时间，用于上报 DETECT_PROCESS_TIME
        detect_start_time = time.time()
        exc = None

        # 去除重复数据（复用原有逻辑）
        records: list[DataRecord] = [record for record in self.record_list if not record.is_duplicate]

        # 优先级检查（复用原有逻辑）
        PriorityChecker.check_records(records)
        for item in self.items:
            strategy_id = item.strategy.id
            # 创建 DetectProcess 实例，复用成熟的检测逻辑
            detect_process = DetectProcess(strategy_id)

            # 生成策略快照（与 detect 模块保持一致）
            detect_process.strategy.gen_strategy_snapshot()
            # 转换数据格式：将 DataRecord 转换为 DataPoint
            # 过滤条件与原有 push 逻辑一致：is_retains 且非 inhibitions
            data_points = []
            valid_records = []
            for record in records:
                if record.is_retains.get(item.id) and not record.inhibitions.get(item.id):
                    try:
                        data_point = DataPoint(record.data, item)
                        data_points.append(data_point)
                        valid_records.append(record)
                    except ValueError as e:
                        logger.warning(
                            f"[access-detect-merge] strategy({strategy_id}) item({item.id}) "
                            f"failed to create DataPoint: {e}"
                        )

            # 使用 DetectProcess 复用检测逻辑
            # pull_data 支持直接传入数据，不需要从 Redis 拉取
            detect_process.pull_data(item, inputs=data_points)
            detect_process.handle_data(item)

            # 二次确认（自动获得）
            try:
                detect_process.double_check(item)
            except Exception:
                logger.exception("[access-detect-merge] strategy(%s) 二次确认时发生异常，不影响告警主流程", strategy_id)

            # 推送无数据检测数据（如果启用）
            # 无数据检测需要知道有哪些维度有数据上报，用于判断哪些维度无数据
            if item.no_data_config.get("is_enabled"):
                self._push(item, records, output_client, key.NO_DATA_LIST_KEY)

            # 推送降噪数据
            if valid_records:
                try:
                    self._push_noise_data(item, valid_records)
                except Exception as e:
                    logger.exception(f"[access-detect-merge] push noise data of strategy({strategy_id}) error: {e}")

            # 推送异常数据（自动获得所有监控指标：延迟统计、大延迟告警、PROCESS_OVER_FLOW 等）
            detect_process.push_data()
            # 上报 detect 模块指标，保持监控连续性
            # 即使合并处理跳过了 detect 异步任务，也需要上报这些指标
            detect_end_time = time.time()

            # DETECT_PROCESS_TIME: 检测处理耗时
            metrics.DETECT_PROCESS_TIME.labels(strategy_id=metrics.TOTAL_TAG).observe(
                detect_end_time - detect_start_time
            )

            # DETECT_PROCESS_COUNT: 检测处理次数（包含成功/失败状态）
            metrics.DETECT_PROCESS_COUNT.labels(
                strategy_id=metrics.TOTAL_TAG,
                status=metrics.StatusEnum.from_exc(exc),
                exception=exc,
            ).inc()

            # 日志记录
            logger.info(
                f"[access-detect-merge] strategy_group_key({self.strategy_group_key}) "
                f"strategy({strategy_id}) merged processing completed, "
                f"processed: {len(data_points)}, detect_time: {detect_end_time - detect_start_time:.3f}s"
            )

            # 指标上报：数据处理计数
            # 复用 ACCESS_PROCESS_PUSH_DATA_COUNT 指标，与原有 push 流程保持一致
            metrics.ACCESS_PROCESS_PUSH_DATA_COUNT.labels(
                strategy_id=metrics.TOTAL_TAG,
                type="data",
            ).inc(len(data_points))

    def push(self, records: list = None, output_client=None):
        # 方案 B：限制处理的时间点数量（在处理阶段限制，不影响查询）
        # 这样可以控制推送到下游 detect 模块的数据量
        limited_records, last_time_point = self._limit_records_by_time_points(self.record_list)
        self.record_list = limited_records

        # 判断是否可以合并处理（access-detect 合并）
        # 当策略的所有检测算法均为静态阈值时，直接在 access 模块执行检测
        if self._can_merge_access_detect():
            # 直接在 access 中执行检测并推送异常数据
            self._detect_and_push_abnormal()
        else:
            # 走原有流程：推送到 Redis 队列，由 detect 异步任务处理
            super().push(records=records, output_client=output_client)

        checkpoint = Checkpoint(self.strategy_group_key)
        checkpoint_timestamp = checkpoint.get()

        if self.record_list:
            if last_time_point:
                # 触发了时间点限制，使用最后处理的时间点作为 checkpoint
                # 这样下次会从这个时间点继续处理，逐步补齐历史数据
                last_checkpoint = last_time_point
            else:
                # 未触发限制，正常计算 checkpoint
                # 使用生成器表达式优化内存，避免创建临时列表
                last_checkpoint = max(checkpoint_timestamp, max(r.time for r in self.record_list))
        else:
            # 无数据：保持 checkpoint 不变
            # 注意：方案 B 不需要空数据检测逻辑，因为查询逻辑保持不变
            # 如果查询返回空数据，说明确实没有数据，无需特殊处理
            last_checkpoint = checkpoint_timestamp

        if last_checkpoint > 0:
            # 记录检测点 下次从检测点开始重新检查
            checkpoint.set(last_checkpoint)

        # 记录access最后一次数据拉取时间
        access_run_timestamp_key = key.ACCESS_RUN_TIMESTAMP_KEY.get_key(strategy_group_key=self.strategy_group_key)
        key.ACCESS_RUN_TIMESTAMP_KEY.client.set(access_run_timestamp_key, int(time.time()))

        # 非批量任务，记录日志
        if not self.sub_task_id:
            logger.info(
                f"strategy_group_key({self.strategy_group_key}), process records({len(self.record_list)}), last_checkpoint({arrow.get(last_checkpoint).strftime(constants.STD_LOG_DT_FORMAT)})"
            )
        else:
            self.process_counts["total_push_data"] = {
                "count": len(self.record_list),
                "last_checkpoint": last_checkpoint,
            }

    def process(self):
        start_time = time.time()

        exc = super().process()

        client = key.ACCESS_BATCH_DATA_RESULT_KEY.client
        result_key = key.ACCESS_BATCH_DATA_RESULT_KEY.get_key(
            strategy_group_key=self.strategy_group_key, timestamp=self.batch_timestamp
        )

        # 如果没有分批任务，直接返回
        if self.batch_count == 1:
            metrics.ACCESS_DATA_PROCESS_TIME.labels(strategy_group_key=metrics.TOTAL_TAG).observe(
                time.time() - start_time
            )
            metrics.ACCESS_DATA_PROCESS_COUNT.labels(
                strategy_group_key=metrics.TOTAL_TAG,
                status=metrics.StatusEnum.from_exc(exc),
                exception=exc,
            ).inc()
            return

        # 等待分批任务结果
        batch_results = [
            {
                "sub_task_id": self.sub_task_id,
                "result": not exc,
                "error": str(exc),
                "process_counts": self.process_counts,
            }
        ]
        wait_start_time = time.time()
        while len(batch_results) < self.batch_count and time.time() - wait_start_time < 5 * constants.CONST_MINUTES:
            batch_result = client.brpop(result_key, timeout=1)
            if batch_result:
                batch_results.append(json.loads(batch_result[1]))

        # 如果有任务未返回结果，记录日志
        if len(batch_results) < self.batch_count:
            logger.error(
                "strategy_group_key({strategy_group_key}) get batch task result timeout,"
                "expect {expect_count} but only get {actual_count}, result({batch_results})".format(
                    strategy_group_key=self.strategy_group_key,
                    expect_count=self.batch_count,
                    actual_count=len(batch_results),
                    batch_results=[result["sub_task_id"] for result in batch_results],
                )
            )

        # 记录日志
        self.batch_log(batch_results)

        metrics.ACCESS_DATA_PROCESS_TIME.labels(strategy_group_key=metrics.TOTAL_TAG).observe(time.time() - start_time)
        metrics.ACCESS_DATA_PROCESS_COUNT.labels(
            strategy_group_key=metrics.TOTAL_TAG,
            status=metrics.StatusEnum.from_exc(exc),
            exception=exc,
        ).inc()

    def batch_log(self, batch_results: list[dict]):
        """
        汇总分批任务结果并记录日志
        """

        last_checkpoint, total_push_count = 0, 0
        for result in batch_results:
            if not result["result"]:
                logger.error(
                    "strategy_group_key({strategy_group_key}) access batch task({sub_task_id}) error({error})".format(
                        strategy_group_key=self.strategy_group_key,
                        sub_task_id=result["sub_task_id"],
                        error=result["error"],
                    )
                )
                continue

            total_push_data = result["process_counts"].get("total_push_data", {})
            last_checkpoint = max(last_checkpoint, total_push_data.get("last_checkpoint", 0))
            total_push_count += total_push_data.get("count", 0)

        # 拉取数量记录日志
        for item in self.items:
            item_id = str(item.id)
            total_count, access_count, duplicate_count, none_point_count = 0, 0, 0, 0
            push_count, push_noise_count = 0, 0
            output_key, record_key, dimension_key = "", "", ""
            for result in batch_results:
                pull_data = result.get("process_counts", {}).get("pull_data", {}).get(item_id, {})
                total_count += pull_data.get("total_count", 0)
                access_count += pull_data.get("access_count", 0)
                duplicate_count += pull_data.get("duplicate_count", 0)
                none_point_count += pull_data.get("none_point_count", 0)

                push_data = result.get("process_counts", {}).get("push_data", {}).get(item_id, {})
                push_count += push_data.get("count", 0)
                output_key = push_data.get("output_key")

                push_noise_data = result.get("process_counts", {}).get("push_noise_data", {}).get(item_id, {})
                push_noise_count += push_noise_data.get("count", 0)
                record_key = push_noise_data.get("record_key")
                dimension_key = push_noise_data.get("dimension_key")

            # 拉取数量记录日志
            if total_count:
                logger.info(
                    f"strategy({item.strategy.id}),item({item.id}),"
                    f"total_records({total_count}),"
                    f"access records({access_count}),"
                    f"duplicate({duplicate_count}),"
                    f"none_point_counts({none_point_count}),"
                    f"strategy_group_key({self.strategy_group_key}),"
                    f"time range({arrow.get(self.from_timestamp).strftime(constants.STD_LOG_DT_FORMAT)} - {arrow.get(self.until_timestamp).strftime(constants.STD_LOG_DT_FORMAT)})"
                )

            # 推送数量记录日志
            if push_count:
                logger.info(
                    f"output_key({output_key}) "
                    f"strategy({item.strategy.strategy_id}), item({item.id}), "
                    f"push records({push_count})."
                )

            # 降噪推送数量记录日志
            if push_noise_count:
                logger.info(
                    f"record_key({record_key}) "
                    f"dimension_key({dimension_key})"
                    f"strategy({item.strategy.strategy_id}), item({item.id}), "
                    f"push dimension records({push_noise_count})."
                )

        # 总推送数量
        if total_push_count:
            logger.info(
                f"strategy_group_key({self.strategy_group_key}), push records({total_push_count}), last_checkpoint({arrow.get(last_checkpoint).strftime(constants.STD_LOG_DT_FORMAT)})"
            )

            # 记录最后检测点，避免子任务并发导致checkpoint数据不准确
            checkpoint = Checkpoint(self.strategy_group_key)
            # 使用生成器表达式优化内存，避免创建临时列表
            last_checkpoint = max(checkpoint.get(), max((r.time for r in self.record_list), default=0))
            if last_checkpoint > 0:
                # 记录检测点 下次从检测点开始重新检查
                checkpoint.set(last_checkpoint)

    def observe_big_latency_datasource(self, item: Item, max_data_time: int):
        """上报数据源延迟较大的指标，以此发现告警策略数据源的质量问题.

        :param item: 检测配置
        :param max_data_time: 当前批次数据最大的数据时间.
        """
        agg_interval = min(query_config["agg_interval"] for query_config in item.query_configs)
        max_latency = self.until_timestamp - max_data_time - agg_interval
        threshold = agg_interval * settings.ACCESS_LATENCY_INTERVAL_FACTOR + settings.ACCESS_LATENCY_THRESHOLD_CONSTANT
        if max_latency > threshold:
            logger.warning(
                "[data source delay]big latency %s,  strategy(%s)",
                max_latency,
                item.strategy.id,
            )
            metrics.PROCESS_BIG_LATENCY.labels(
                strategy_id=item.strategy.id,
                strategy_name=item.strategy.name,
                bk_biz_id=item.strategy.bk_biz_id,
                module="data_delay",
            ).observe(max_latency)


class AccessBatchDataProcess(AccessDataProcess):
    """
    分批任务处理器
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.sub_task_id is None:
            raise ValueError("sub_task_id is required")

    def pull(self):
        client = key.ACCESS_BATCH_DATA_KEY.client
        cache_key = key.ACCESS_BATCH_DATA_KEY.get_key(
            strategy_group_key=self.strategy_group_key, sub_task_id=self.sub_task_id
        )
        cache_key.strategy_id = self.items[0].strategy.id
        data = client.get(cache_key)
        if data:
            points = json.loads(gzip.decompress(base64.b64decode(data)).decode("utf-8"))
        else:
            points = []
        client.delete(cache_key)
        self.filter_duplicates(points)

    def process(self):
        exc = super().process()

        client = key.ACCESS_BATCH_DATA_RESULT_KEY.client
        result_key = key.ACCESS_BATCH_DATA_RESULT_KEY.get_key(
            strategy_group_key=self.strategy_group_key, timestamp=self.batch_timestamp
        )

        client.lpush(
            result_key,
            json.dumps(
                {
                    "sub_task_id": self.sub_task_id,
                    "result": not exc,
                    "error": str(exc),
                    "process_counts": self.process_counts,
                }
            ),
        )
        client.expire(result_key, key.ACCESS_BATCH_DATA_RESULT_KEY.ttl)


class AccessRealTimeDataProcess(BaseAccessDataProcess):
    """
    实时监控数据拉取
    """

    def __init__(self, service):
        """
        {
            "0bkmonitor_100010": {"strategy_ids": [1, 2], "dimensions": ["ip", "bk_cloud_id"]},
            "0bkmonitor_100010": {"strategy_ids": [3, 4], "dimensions": ["ip", "bk_cloud_id"]},
        }
        """
        super().__init__()

        # 服务注册
        self.service = service
        # redis存储
        self.cache = Cache("service")
        # 本机IP
        self.ip = get_local_ip()

        # topic信息缓存key
        self.topic_cache_key = key.REAL_TIME_HOST_TOPIC_KEY.get_key()

        # topics信息
        self.topics: dict[str, dict] = {}
        self.rt_id_to_storage_info = {}

        self.consumers: dict[str, KafkaConsumer] = {}
        self.consumers_lock = threading.Lock()
        self.queue = queue.Queue(maxsize=100)
        self._stop_signal = False
        self.strategy_cache = {}

    def __str__(self):
        return super().__str__()

    @staticmethod
    def get_all_hosts():
        """
        获取所有运行中机器
        """
        prefix = "{}_{}_{}_{}/{}".format(
            settings.APP_CODE, settings.PLATFORM, settings.ENVIRONMENT, get_cluster().name, "run_access-real_time_data"
        )
        client = BKConsul()
        host_keys = client.kv.get(prefix, keys=True)[1]
        return [host_key.split("/")[-2] for host_key in host_keys]

    def run_leader(self, once=False):
        """
        leader选举与任务分发
        1. 实时监控服务注册
        2. 抢占redis leader锁
        3. 成为leader的获取所有实时监控策略/拉取表信息/分配topic到各个机器
        """
        while True:
            # 抢占redis leader锁
            result = self.cache.set("real-time-handler-leader", self.ip, nx=True, ex=120)
            leader_ip = self.cache.get("real-time-handler-leader")

            # 没有获得锁就等待15秒
            if not result and leader_ip != self.ip:
                if once or self._stop_signal:
                    logger.info("real_time leader get stop signal")
                    break

                time.sleep(30)
                continue

            logger.info(f"{self.ip} is be elected at the real-time-access leader election")

            start_time = time.time()
            # 获取所有实时监控待拉取的topic及对应的策略信息
            rt_id_to_strategies = StrategyCacheManager.get_real_time_data_strategy_ids()

            # 过滤出当前集群下的策略
            for rt_id in rt_id_to_strategies:
                rt_id_to_strategies[rt_id] = {
                    biz_id: strategy_ids
                    for biz_id, strategy_ids in rt_id_to_strategies[rt_id].items()
                    if get_cluster().match(TargetType.biz, biz_id)
                }

            # 去除空的rt_id
            rt_id_to_strategies = {
                rt_id: strategy_ids for rt_id, strategy_ids in rt_id_to_strategies.items() if strategy_ids
            }

            rt_ids = list(rt_id_to_strategies.keys())
            partitions = []
            topic_strategy = defaultdict(set)
            topic_dimensions = {}
            consumers = {}
            for rt_id in rt_ids:
                try:
                    info = ResultTableCacheManager.get_result_table_by_id(DataSourceLabel.BK_MONITOR_COLLECTOR, rt_id)
                    if not info:
                        continue

                    if rt_id in self.rt_id_to_storage_info:
                        storage_info = self.rt_id_to_storage_info[rt_id]
                    else:
                        if not info.get("storage_info"):
                            storage_info = api.metadata.get_result_table_storage(
                                result_table_list=rt_id, storage_type="kafka"
                            )
                            storage_info = storage_info[rt_id] if storage_info else {}
                        else:
                            storage_info = info["storage_info"]

                        self.rt_id_to_storage_info[rt_id] = storage_info

                    if not storage_info:
                        continue

                    cluster_config = storage_info["cluster_config"]
                    bootstrap_server = f"{cluster_config['domain_name']}:{cluster_config['port']}"
                    consumer = consumers.get(bootstrap_server)
                    if not consumer:
                        try:
                            consumer = KafkaConsumer(bootstrap_servers=bootstrap_server)
                            consumer.topics()
                        except NoBrokersAvailable:
                            continue
                        consumers[bootstrap_server] = consumer

                    topic = storage_info["storage_config"]["topic"]
                    partitions.extend(
                        [f"{bootstrap_server}|{topic}|{index}" for index in consumer.partitions_for_topic(topic) or [0]]
                    )
                    topic = f"{bootstrap_server}|{topic}"
                    for strategy_ids in rt_id_to_strategies[rt_id].values():
                        topic_strategy[topic].update(strategy_ids)

                    dimensions = {field["field_name"] for field in info.get("fields", []) if field["is_dimension"]}
                    topic_dimensions[topic] = dimensions - {"bk_cmdb_level", "bk_supplier_id"}
                except Exception as e:
                    logger.exception(e)
                    logger.error(f"get real time result_table({rt_id}) info error")
            map(lambda c: c.close(), consumers)

            # 使用哈希算法分配topic到机器上
            hosts = self.get_all_hosts()
            hash_ring = HashRing({host: 1 for host in hosts})
            host_topics = defaultdict(set)
            for partition in partitions:
                host = hash_ring.get_node(partition)
                host_topics[host].add(partition.rsplit("|", maxsplit=1)[0])

            # 将topic分配信息写入redis
            pipeline = self.cache.pipeline()
            self.cache.delete(self.topic_cache_key)
            self.cache.hmset(
                self.topic_cache_key,
                mapping={
                    host: json.dumps(
                        {
                            topic: {
                                "dimensions": list(topic_dimensions[topic]),
                                "strategy_ids": list(topic_strategy[topic]),
                            }
                            for topic in host_topics[host]
                        }
                    )
                    for host in hosts
                },
            )
            self.cache.expire(self.topic_cache_key, key.REAL_TIME_HOST_TOPIC_KEY.ttl)
            pipeline.execute()

            # 只执行一次或存在停止信号
            if once or self._stop_signal:
                if self._stop_signal:
                    self.cache.delete("real-time-handler-leader")
                logger.info("real_time leader get stop signal")
                break

            # 最小执行间隔30秒
            end_time = time.time()
            if end_time - start_time < 60:
                time.sleep(60 - (end_time - start_time))

    def flat(self, bootstrap_servers: str, record: ConsumerRecord):
        """
        扁平化
        1. 数据结构转换
        2. 分策略拆分成多条DataRecord
        record:
        {
            "metrics":{
                "load1":2.77,
                "load5":2.56,
                "load15":2.57
            },
            "dimensions":{
                "bk_biz_id":2,
                "bk_cmdb_level":"",
                "ip":"127.0.0.1",
                "bk_cloud_id":0,
                "bk_target_ip":"127.0.0.1",
                "bk_target_cloud_id":"0",
                "bk_supplier_id":0
            },
            "time":1573701305
        }

        standard raw_data:
        {
            "bk_target_ip":"127.0.0.1",
            "load5":2.56,
            "bk_target_cloud_id":"0",
            "time":1573701305
        }
        """
        raw_data = record.value
        raw_data = json.loads(raw_data[:-1] if raw_data[-1] == "\x00" or raw_data[-1] == "\n" else raw_data)

        data_bk_biz_id = int(raw_data["dimensions"].get("bk_biz_id") or 0)
        if data_bk_biz_id == 0:
            return []

        strategy_ids = self.topics[f"{bootstrap_servers}|{record.topic}"]["strategy_ids"]
        dimensions = self.topics[f"{bootstrap_servers}|{record.topic}"]["dimensions"]
        strategies = [self.get_strategy(strategy_id) for strategy_id in strategy_ids]
        strategies = [s for s in strategies if int(s.bk_biz_id) == data_bk_biz_id]
        if not strategies:
            logger.debug("abandon data(%s), not belong targets", raw_data)
            return []

        new_record_list = []
        for strategy in strategies:
            standard_raw_data = {"time": raw_data["time"]}
            standard_raw_data.update(raw_data["metrics"])
            standard_raw_data.update(raw_data["dimensions"])

            item = strategy.items[0]
            item.data_sources[0].group_by = dimensions
            item.query_configs[0]["agg_dimension"] = dimensions
            new_record_list.append(DataRecord(item, standard_raw_data))
        return new_record_list

    def get_strategy(self, strategy_id: int) -> Strategy:
        """
        获取策略配置
        """
        if time.time() - self.strategy_cache.get(strategy_id, {}).get("time", 0) > 60:
            self.strategy_cache[strategy_id] = {"time": time.time(), "strategy": Strategy(strategy_id)}

        return self.strategy_cache[strategy_id]["strategy"]

    def run_poller(self, once=False):
        while True:
            self.consumers_lock.acquire()
            has_record = False
            for consumer in self.consumers.values():
                data = consumer.poll(500, max_records=5000)
                if not data:
                    continue

                has_record = True
                for records in data.values():
                    logger.info(f"real_time poller poll {consumer.config['bootstrap_servers']}: {len(records)}")
                    self.queue.put((consumer.config["bootstrap_servers"], records))
            self.consumers_lock.release()

            if once or self._stop_signal:
                logger.info("real_time poller get stop signal")
                break

            # 如果没有数据就等待一秒
            if not has_record:
                time.sleep(1)

    def run_consumer_manager(self, once=False):
        """
        kafka消费者管理
        """
        while True:
            # 获取最新的topic信息
            self.topics = json.loads(self.cache.hget(self.topic_cache_key, self.ip) or "{}")

            # kafka集群及所属topic分组
            bootstrap_servers_topics = defaultdict(set)
            for topic in self.topics:
                bootstrap_servers, topic = topic.split("|")
                bootstrap_servers_topics[bootstrap_servers].add(topic)

            update_bootstrap_servers = []
            create_bootstrap_servers = []
            delete_bootstrap_servers = []

            for bootstrap_servers, topics in bootstrap_servers_topics.items():
                if bootstrap_servers not in self.consumers:
                    create_bootstrap_servers.append(bootstrap_servers)
                    continue

                consumer = self.consumers[bootstrap_servers]
                if consumer.subscription() != topics:
                    update_bootstrap_servers.append(bootstrap_servers)

            for bootstrap_servers in self.consumers:
                if bootstrap_servers not in bootstrap_servers_topics:
                    delete_bootstrap_servers.append(bootstrap_servers)

            if update_bootstrap_servers:
                logger.info(f"real_time consumer_manager update {'|'.join(update_bootstrap_servers)}")
            if create_bootstrap_servers:
                logger.info(f"real_time consumer_manager create {'|'.join(create_bootstrap_servers)}")
            if delete_bootstrap_servers:
                logger.info(f"real_time consumer_manager delete {'|'.join(delete_bootstrap_servers)}")

            if any([update_bootstrap_servers, create_bootstrap_servers, delete_bootstrap_servers]):
                self.consumers_lock.acquire()
                new_consumers = {}

                for bootstrap_servers in create_bootstrap_servers:
                    new_consumers[bootstrap_servers] = KafkaConsumer(
                        bootstrap_servers=bootstrap_servers,
                        group_id=f"{settings.APP_CODE}.real_time_access",
                    )
                    new_consumers[bootstrap_servers].subscribe(topics=list(bootstrap_servers_topics[bootstrap_servers]))

                for bootstrap_servers, consumer in self.consumers.items():
                    if bootstrap_servers in delete_bootstrap_servers:
                        consumer.close()
                        continue

                    if bootstrap_servers in update_bootstrap_servers:
                        consumer.subscribe(topics=list(bootstrap_servers_topics[bootstrap_servers]))
                    new_consumers[bootstrap_servers] = consumer
                self.consumers = new_consumers
                self.consumers_lock.release()

            if once or self._stop_signal:
                if self._stop_signal:
                    logger.info("real_time consumer_manager get stop signal")
                    self.consumers_lock.acquire()
                    map(lambda c: c.close(), self.consumers.values())
                    self.consumers = []
                    self.consumers_lock.release()
                break

            time.sleep(15)

    def run_handler(self, once=False):
        while True:
            if self._stop_signal and self.queue.empty():
                logger.info("real_time handler get stop signal")
                break

            try:
                bootstrap_servers, data = self.queue.get(block=True, timeout=5)
            except queue.Empty:
                data = []
                bootstrap_servers = ""

            try:
                records = []
                for record in data:
                    try:
                        records.extend(self.flat(bootstrap_servers, record))
                    except Exception as e:
                        logger.warning("%s loads alarm(%s) failed: %s", record.topic, record.value, e)

                record_list = []
                for r in records:
                    # 补充维度：比如：业务、集群、模块等信息
                    self.full(r)

                    new_r_list = r.full()
                    if not new_r_list:
                        continue

                    record_list.extend(new_r_list)

                output = []
                for r in record_list:
                    # 过滤数据
                    if self.filter(r) or r.filter(r):
                        continue

                    # 格式化数据
                    r.clean()

                    output.append(r)

                self.push(output)
            except Exception as e:
                logger.exception(e)
                logger.error(f"real_time handler exception: {e}")

            if once:
                break

    def _stop(self, *args, **kwargs):
        self._stop_signal = True

    def process(self, once=False):
        if once:
            self.run_leader(once=True)
            self.run_consumer_manager(once=True)
            self.run_poller(once=True)
            self.run_handler(once=True)
        else:
            signal.signal(signal.SIGTERM, self._stop)
            signal.signal(signal.SIGINT, self._stop)
            leader = InheritParentThread(target=self.run_leader)
            consumer_manager = InheritParentThread(target=self.run_consumer_manager)
            poller = InheritParentThread(target=self.run_poller)
            handler = InheritParentThread(target=self.run_handler)
            leader.start()
            consumer_manager.start()
            poller.start()
            handler.start()

            while True:
                self.service.register()

                if self._stop_signal:
                    leader.join()
                    consumer_manager.join()
                    poller.join()
                    handler.join()
                    self.service.unregister()
                    return

                time.sleep(15)
