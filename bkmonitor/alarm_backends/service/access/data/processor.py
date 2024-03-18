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

import json
import logging
import queue
import signal
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List

import arrow
import pytz
from django.conf import settings
from django.utils.functional import cached_property
from kafka import KafkaConsumer
from kafka.consumer.fetcher import ConsumerRecord
from kafka.errors import NoBrokersAvailable

from alarm_backends import constants
from alarm_backends.cluster import TargetType
from alarm_backends.core.cache import clear_mem_cache, key
from alarm_backends.core.cache.key import ACCESS_END_TIME_KEY, REAL_TIME_HOST_TOPIC_KEY
from alarm_backends.core.cache.result_table import ResultTableCacheManager
from alarm_backends.core.cache.strategy import StrategyCacheManager
from alarm_backends.core.cluster import get_cluster
from alarm_backends.core.control.checkpoint import Checkpoint
from alarm_backends.core.control.item import Item
from alarm_backends.core.control.strategy import Strategy
from alarm_backends.core.storage.redis import Cache
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
from bkmonitor.utils.common_utils import count_md5, get_local_ip
from bkmonitor.utils.consul import BKConsul
from bkmonitor.utils.thread_backend import InheritParentThread
from constants.data_source import DataSourceLabel, DataTypeLabel
from constants.strategy import MULTI_METRIC_DATA_SOURCES
from core.drf_resource import api
from core.errors.api import BKAPIError
from core.prometheus import metrics

IP = get_local_ip()
logger = logging.getLogger("access.data")


class BaseAccessDataProcess(base.BaseAccessProcess):
    def __init__(self, *args, **kwargs):
        super(BaseAccessDataProcess, self).__init__(*args, **kwargs)

        self.add_filter(RangeFilter())
        self.add_filter(ExpireFilter())
        self.add_filter(HostStatusFilter())

        self.add_fuller(TopoNodeFuller())

    def post_handle(self):
        # 释放主机信息本地内存
        clear_mem_cache("host_cache")

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

        logger.info(
            "record_key({record_key}) "
            "dimension_key({dimension_key})"
            "strategy({strategy_id}) "
            "push dimension records({records_length}).".format(
                record_key=record_key,
                dimension_key="|".join(noise_reduce_config["dimensions"]),
                strategy_id=item.strategy.strategy_id,
                records_length=len(noise_data.keys()),
            )
        )

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

        logger.info(
            "output_key({output_key}) "
            "strategy({strategy_id}), item({item_id}), "
            "push records({records_length}).".format(
                output_key=output_key,
                strategy_id=item.strategy.strategy_id,
                item_id=item.id,
                records_length=len(record_list),
            )
        )

    def push(self, records: List = None, output_client=None):
        """
        推送格式化后的数据到 detect 和 nodata 中(按单个策略，单个item项，写入不同的队列)
        """
        if records is None:
            records = self.record_list

        # 去除重复数据
        records: List[DataRecord] = [record for record in records if not record.is_duplicate]

        # 优先级检查
        PriorityChecker.check_records(records)

        # 按item_id分组
        pending_to_push = {}
        item_id_to_item = {}
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
                strategy_ids.add(item.strategy.strategy_id)

                # 推送到检测队列
                self._push(item, record_list, output_client)

                # 推送降噪基数至redis队列
                try:
                    self._push_noise_data(item, record_list)
                except BaseException as e:
                    logger.exception("push noise data of strategy(%s) error, %s", item.strategy.strategy_id, str(e))

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
    def __init__(self, strategy_group_key, *args, **kwargs):
        super(AccessDataProcess, self).__init__(strategy_group_key, *args, **kwargs)
        self.strategy_group_key = strategy_group_key

    def __str__(self):
        return "{}:strategy_group_key({})".format(self.__class__.__name__, self.strategy_group_key)

    @cached_property
    def items(self):
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

    @staticmethod
    def get_max_local_time(records):
        """
        获取最大数据落地时间并剔除该字段
        """
        max_local_time = arrow.get(0).datetime
        for record in records:
            local_time = record.pop("_localTime", None)
            if not local_time:
                continue

            local_time = datetime.strptime(local_time, "%Y-%m-%d %H:%M:%S").replace(tzinfo=pytz.utc)
            if local_time > max_local_time:
                max_local_time = local_time

        # localTime不是UTC时间，而是计算平台的机器时间
        max_local_time += timedelta(hours=settings.BKDATA_LOCAL_TIMEZONE_OFFSET)
        return max_local_time

    def pull(self):
        """
        1. 根据策略配置获取到需要拉取的数据
        2. 格式化数据，增加记录ID
        """
        if not self.items:
            return

        # 拉取一次数据，默认相同查询方法的数据拉取状态保持一致
        first_item: Item = self.items[0]
        agg_interval = min(query_config["agg_interval"] for query_config in first_item.query_configs)

        min_last_checkpoint = min([i.item_config["update_time"] for i in self.items])
        checkpoint = Checkpoint(self.strategy_group_key).get(min_last_checkpoint, interval=agg_interval)
        checkpoint = checkpoint // agg_interval * agg_interval

        now_timestamp = arrow.utcnow().timestamp

        # 由于存在入库延时问题，每次多往前拉取settings.NUM_OF_COUNT_FREQ_ACCESS个周期的数据
        from_timestamp = checkpoint - settings.NUM_OF_COUNT_FREQ_ACCESS * agg_interval

        until_timestamp = None
        # 计算平台类型尝试获取上次未处理完的时间
        if DataSourceLabel.BK_DATA in first_item.data_source_labels:
            end_time_key = ACCESS_END_TIME_KEY.get_key(group_key=self.strategy_group_key)
            client = ACCESS_END_TIME_KEY.client

            until_timestamp = client.get(end_time_key)
            if until_timestamp:
                client.delete(end_time_key)
                until_timestamp = int(until_timestamp)
            else:
                until_timestamp = 0

        time_delay = settings.ACCESS_DATA_TIME_DELAY
        if (DataSourceLabel.BK_LOG_SEARCH, DataTypeLabel.LOG) in first_item.data_source_types:
            time_delay += 60

        if not until_timestamp:
            # 非计算平台数据源：
            # 由于存在入库延时问题，SUM等聚合方式最后一个点的结果会不准确，所以后台检测往前推 ACCESS_DATA_TIME_DELAY 秒
            # 保证查询时间范围是< until_timestamp 而不是<=即可
            until_timestamp = (now_timestamp - time_delay) // agg_interval * agg_interval

        if from_timestamp > until_timestamp:
            return

        # 由于某些数据源需要进行策略分组，因此需要将条件置为空
        if not (first_item.data_source_types & MULTI_METRIC_DATA_SOURCES):
            first_item.data_sources[0]._advance_where = []

        # 计算平台指标查询localTime
        if DataSourceLabel.BK_DATA in first_item.data_source_labels:
            first_item.data_sources[0].metrics.append({"field": "localTime", "method": "MAX", "alias": "_localTime"})

        try:
            item_records = first_item.query_record(from_timestamp, until_timestamp)
        except BKAPIError as e:
            logger.error(e)
            item_records = []
        except Exception as e:  # noqa
            logger.exception(
                "strategy_group_key({strategy_group_key}) query records error, {err}".format(
                    strategy_group_key=self.strategy_group_key, err=e
                )
            )
            item_records = []

        # 如果最大的localTime离得太近，那就存下until_timestamp，下次再拉取数据
        if DataSourceLabel.BK_DATA in first_item.data_source_labels:
            max_local_time = self.get_max_local_time(item_records)
            first_item.data_sources[0].metrics = [
                m for m in first_item.data_sources[0].metrics if m["field"] != "localTime"
            ]
            if now_timestamp - max_local_time.timestamp() <= settings.BKDATA_LOCAL_TIME_THRESHOLD:
                ACCESS_END_TIME_KEY.client.set(
                    ACCESS_END_TIME_KEY.get_key(group_key=self.strategy_group_key),
                    str(until_timestamp),
                    # key超时时间低于监控周期，会导致数据缓存丢失
                    ex=max([ACCESS_END_TIME_KEY.ttl, agg_interval * 5]),
                )
                logging.info(
                    f"skip access {self.strategy_group_key} data because data local time is too close."
                    f"now: {now_timestamp}, local time: {max_local_time.timestamp()}"
                )
                return

        records = []
        dup_obj = Duplicate(self.strategy_group_key, strategy_id=first_item.strategy.id)
        duplicate_counts = none_point_counts = 0

        # 是否有优先级
        have_priority = False
        for item in self.items:
            if item.strategy.priority is not None and item.strategy.priority_group_key:
                have_priority = True
                break

        for record in reversed(item_records):
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
            else:
                none_point_counts += 1

        dup_obj.refresh_cache()
        self.record_list = records
        point_count = len(records)
        if point_count:
            metrics.ACCESS_DATA_PROCESS_PULL_DATA_COUNT.labels(strategy_group_key=metrics.TOTAL_TAG).inc(point_count)

        # 日志记录按strategy + item 来记录，方便问题排查
        for item in self.items:
            logger.info(
                "strategy({strategy_id}),item({item_id}),"
                "total_records({total}),"
                "access records({records_length}),"
                "duplicate({duplicate_counts}),"
                "none_point_counts({none_point_counts}),"
                "strategy_group_key({strategy_group_key}),"
                "time range({from_datetime} - {until_datetime})".format(
                    strategy_id=item.strategy.id,
                    item_id=item.id,
                    total=len(item_records),
                    records_length=point_count,
                    duplicate_counts=duplicate_counts,
                    none_point_counts=none_point_counts,
                    strategy_group_key=self.strategy_group_key,
                    from_datetime=arrow.get(from_timestamp).strftime(constants.STD_LOG_DT_FORMAT),
                    until_datetime=arrow.get(until_timestamp).strftime(constants.STD_LOG_DT_FORMAT),
                )
            )

    def push(self, records: List = None, output_client=None):
        super(AccessDataProcess, self).push(records=records, output_client=output_client)

        checkpoint = Checkpoint(self.strategy_group_key)
        last_checkpoint = max([checkpoint.get()] + [r.time for r in self.record_list])
        if last_checkpoint > 0:
            # 记录检测点 下次从检测点开始重新检查
            checkpoint.set(last_checkpoint)

        # 记录access最后一次数据拉取时间
        access_run_timestamp_key = key.ACCESS_RUN_TIMESTAMP_KEY.get_key(strategy_group_key=self.strategy_group_key)
        key.ACCESS_RUN_TIMESTAMP_KEY.client.set(access_run_timestamp_key, int(time.time()))

        logger.info(
            "strategy_group_key({}), push records({}), last_checkpoint({})".format(
                self.strategy_group_key,
                len(self.record_list),
                arrow.get(last_checkpoint).strftime(constants.STD_LOG_DT_FORMAT),
            )
        )

    def process(self):
        start_time = time.time()

        exc = super(AccessDataProcess, self).process()

        metrics.ACCESS_DATA_PROCESS_TIME.labels(strategy_group_key=metrics.TOTAL_TAG).observe(time.time() - start_time)
        metrics.ACCESS_DATA_PROCESS_COUNT.labels(
            strategy_group_key=metrics.TOTAL_TAG,
            status=metrics.StatusEnum.from_exc(exc),
            exception=exc,
        ).inc()


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
        super(AccessRealTimeDataProcess, self).__init__()

        # 服务注册
        self.service = service
        # redis存储
        self.cache = Cache("service")
        # 本机IP
        self.ip = get_local_ip()

        # topic信息缓存key
        self.topic_cache_key = REAL_TIME_HOST_TOPIC_KEY.get_key()

        # topics信息
        self.topics: Dict[str, Dict] = {}
        self.rt_id_to_storage_info = {}

        self.consumers: Dict[str, KafkaConsumer] = {}
        self.consumers_lock = threading.Lock()
        self.queue = queue.Queue(maxsize=100)
        self._stop_signal = False
        self.strategy_cache = {}

    def __str__(self):
        return super(AccessRealTimeDataProcess, self).__str__()

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
                    bootstrap_server = f'{cluster_config["domain_name"]}:{cluster_config["port"]}'
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
            self.cache.expire(self.topic_cache_key, REAL_TIME_HOST_TOPIC_KEY.ttl)
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
                        logger.warning("%s loads alarm(%s) failed", record.topic, record.value, e)

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
