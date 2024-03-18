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
import datetime
import json
import time
from collections import defaultdict

import arrow
from django.conf import settings
from kafka import KafkaConsumer, TopicPartition

from alarm_backends.core.cache import key as cache_key
from alarm_backends.core.cache.cmdb.base import CMDBCacheManager
from alarm_backends.core.cache.key import ALERT_HOST_DATA_ID_KEY
from alarm_backends.core.cache.strategy import StrategyCacheManager
from alarm_backends.core.storage.kafka import KafkaOffsetManager, KafkaQueue
from alarm_backends.core.storage.redis import Cache
from alarm_backends.management.story.base import (
    BaseStory,
    CheckStep,
    ResolvedProblem,
    register_step,
    register_story,
)
from bkmonitor.data_source import UnifyQuery, load_data_source
from bkmonitor.models import StrategyModel
from bkmonitor.utils.common_utils import get_local_ip
from constants.action import ActionPluginType
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import api
from metadata.models import DataSource


@register_story()
class KernelStory(BaseStory):
    name = "Kernel Service Healthz Check"


@register_step(KernelStory)
class ServiceQueueCheck(CheckStep):
    name = "check service signal queue"

    def check(self):
        # 检测待检测信号队列是否拥堵
        client = cache_key.DATA_SIGNAL_KEY.client
        strategy_len = len(StrategyCacheManager.get_strategy_ids())
        self.story.info(f"strategy total: {strategy_len}")
        # detect signal queue check
        signal_len = client.llen(cache_key.DATA_SIGNAL_KEY.get_key())
        if signal_len > strategy_len * 10:
            p = DetectSignalPending(f"待检测信号队列已堵塞(当前堆积: {signal_len})", self.story)
            return p
        self.story.info(f"detect service signal queue length is {signal_len}")
        # trigger signal queue check
        client = cache_key.ANOMALY_SIGNAL_KEY.client
        signal_len = client.llen(cache_key.ANOMALY_SIGNAL_KEY.get_key())
        if signal_len > 100:
            p = TriggerSignalPending(f"trigger信号队列已堵塞(当前堆积: {signal_len})", self.story)
            return p
        self.story.info(f"trigger service signal queue length is {signal_len}")
        return None


@register_step(KernelStory)
class PollEventDelayCheck(CheckStep):
    name = "check AccessGseEventProcess delay"

    def check(self):
        topic_info = api.metadata.get_data_id(bk_data_id=settings.GSE_BASE_ALARM_DATAID, with_rt_info=False)
        topic = topic_info["mq_config"]["storage_config"]["topic"]
        kafka_queue = KafkaQueue.get_common_kafka_queue()
        data_id = topic_info["data_id"]
        # 获取本机GSE EVENT 对应topic消费组对应的最新的offset， 再和本地offset对比。
        kafka_queue.set_topic(topic, group_prefix=f"access.event.{data_id}")
        offset_manager = KafkaOffsetManager(kafka_queue.get_consumer())
        last_remote_offset = max(offset_manager.consumer.offsets.values())
        local_offset = offset_manager.get_offset()
        problem = None
        if local_offset + 10000 <= last_remote_offset:
            # 处理不过来了
            problem = Kafka1000Delay(
                f"GSE EVENT拉取存在处理瓶颈，topic[{topic}]已堵塞" f"{last_remote_offset - local_offset}条消息",
                self.story,
                topic=topic,
            )
        else:
            self.story.info(f"OK!: topic[{topic}] local offset({local_offset}) > remote({last_remote_offset})。")
        return problem


@register_step(KernelStory)
class MonitorEventDelayCheck(CheckStep):
    name = "check AlertPoller delay"

    def check(self):
        cache = Cache("service")
        ip_topics = cache.hgetall(ALERT_HOST_DATA_ID_KEY.get_key())
        topics = []
        for value in ip_topics.values():
            topics.extend(json.loads(value))

        # kafka集群及所属topic分组
        bootstrap_servers_topics = defaultdict(set)
        topics_data_id = defaultdict()

        for topic in topics:
            bootstrap_servers = topic["bootstrap_server"]
            topic_name = topic["topic"]
            bootstrap_servers_topics[bootstrap_servers].add(topic_name)
            topics_data_id[f"{bootstrap_servers}|{topic_name}"] = topic["data_id"]

        group_id = f"{settings.APP_CODE}.alert.builder"
        for bootstrap_servers, topics in bootstrap_servers_topics.items():
            c = KafkaConsumer(bootstrap_servers=bootstrap_servers, group_id=group_id)
            c.topics()

            congestion_topics = []
            topic_partitions = []
            for topic in topics:
                partitions = c.partitions_for_topic(topic) or {0}
                topic_partitions.extend([TopicPartition(topic=topic, partition=partition) for partition in partitions])
            end_offsets = c.end_offsets(topic_partitions)
            committed_offsets = {}
            for topic_partition in topic_partitions:
                committed_offsets[topic_partition] = c.committed(topic_partition) or 0
            c.close()

            for topic_partition in committed_offsets:
                if end_offsets[topic_partition] - committed_offsets[topic_partition] > 20000:
                    congestion_topics.append(topic_partition.topic)
                    data_id = topics_data_id.get(f"{bootstrap_servers}|{topic_partition.topic}")
                    alert_info = (
                        f"[alert poller] {bootstrap_servers} {topic_partition.topic} {data_id} pull event "
                        f"delay offset {end_offsets[topic_partition] - committed_offsets[topic_partition]}"
                    )
                    self.story.warning(alert_info)
                    return AlertPollerDelay(alert_info, self.story)


@register_step(KernelStory)
class CacheCronJobCheck(CheckStep):
    name = "check cron job cache"

    def check(self):
        cache = Cache("cache")
        p_list = []
        ttl = None
        # 1. cmdb
        for k in cache.keys(f"{cache_key.KEY_PREFIX}.cache.cmdb*"):
            ttl = cache.ttl(k)
            if ttl and ttl < CMDBCacheManager.CACHE_TIMEOUT - 60 * 30:
                # 30分钟未刷新
                p = CMDBCacheCronError(f"key: {k}在30分钟内未刷新", self.story)
                p_list.append(p)
                break
        if ttl is None:
            p = CMDBCacheCronError("cmdb缓存任务未正常运行", self.story)
            p_list.append(p)
        else:
            self.story.info("cmdb cron job executed {}s ago!".format(CMDBCacheManager.CACHE_TIMEOUT - ttl))

        # 2. strategy
        # 随机抽取一条策略缓存
        _, random_key = cache.scan(0, f"{cache_key.KEY_PREFIX}.cache.strategy_*")
        ttl = cache.ttl(random_key[0]) if random_key else None
        if ttl and ttl < StrategyCacheManager.CACHE_TIMEOUT - 60 * 30:
            # 30分钟未刷新
            p = StrategyCacheCronError(f"key: {random_key[0]}在30分钟内未刷新", self.story)
            p_list.append(p)
            return p_list
        # 针对策略缓存步骤逐一检查
        keys = [
            "IDS_CACHE_KEY",
            "BK_BIZ_IDS_CACHE_KEY",
            "REAL_TIME_CACHE_KEY",
            "GSE_ALARM_CACHE_KEY",
            "STRATEGY_GROUP_CACHE_KEY",
        ]
        for k in [getattr(StrategyCacheManager, key) for key in keys]:
            ttl = cache.ttl(k)

            if ttl and ttl < StrategyCacheManager.CACHE_TIMEOUT - 60 * 30:
                # 30分钟未刷新
                p = StrategyCacheCronError(f"key: {k}在30分钟内未刷新", self.story)
                p_list.append(p)
                break

        if ttl is None:
            # 拿当前有效策略数，如果新装，则不产生告警
            if StrategyModel.objects.filter(is_enabled=True).count() == 0:
                self.story.info("暂未发现有监控策略启用中...")
            else:
                p = StrategyCacheCronError("策略相关缓存任务未正常运行", self.story)
                p_list.append(p)
        else:
            self.story.info("strategy cron job executed {}s ago!".format(StrategyCacheManager.CACHE_TIMEOUT - ttl))

        return p_list


@register_step(KernelStory)
class DurationSpace(CheckStep):
    name = "check api duration"

    # 超过 10s 表示问题
    warning_duration = 10

    def check(self):
        start = time.time()
        bk_biz_id = api.cmdb.get_blueking_biz()
        data_source_class = load_data_source(DataSourceLabel.PROMETHEUS, DataTypeLabel.TIME_SERIES)
        promql = "sum(count_over_time(bkmonitor:system:cpu_summary:usage[10m]))"
        data_source = data_source_class(
            bk_biz_id=bk_biz_id,
            promql=promql,
            interval=60,
        )
        query = UnifyQuery(bk_biz_id=bk_biz_id, data_sources=[data_source], expression="")
        now_ts = arrow.now()
        try:
            records = query.query_data(
                start_time=now_ts.replace(minutes=-1).timestamp * 1000, end_time=now_ts.timestamp * 1000
            )
        except Exception as e:
            return APIERROR("UnifyQuery.query_data Error: %s" % e, self.story)

        duration = time.time() - start
        if duration > self.warning_duration:
            return APIPending("api worker duration cost %s" % duration, self.story)
        self.story.info("api worker duration cost %s" % duration)

        if records[0]["_result_"] == 0:
            # 尝试从kafka拉取最新的一条数据。
            p = self.check_from_kafka(1001)
            if not p:
                # kafka 数据正常
                return TransferPending("基础性能dataid: 1001的入库延迟10分钟以上，kafka正常有数据，请关注", self.story)
            return p

    def check_from_kafka(self, dataid):
        d = DataSource.objects.get(bk_data_id=dataid)
        culster_info = d.mq_cluster
        topic = d.mq_config.topic
        kfk_conf = {
            "domain": culster_info.domain_name,
            "port": culster_info.port,
        }
        kafka_queue = KafkaQueue(kfk_conf=kfk_conf)
        try:
            kafka_queue.set_topic(topic, group_prefix="%s.healthz.0" % get_local_ip())
            kafka_queue.reset_offset()
            result = kafka_queue.take(count=1, timeout=5)
            if not result:
                # 无数据
                return KafkaNoData(
                    "Kafka[{}] topic[{}] 中未找到基础性能数据上报 ".format("{domain}:{port}".format(**kfk_conf), topic), self.story
                )
        except Exception as e:
            return KafkaConnectionError(
                "Kafka[{}] 拉取topic[{}]失败: {}".format("{domain}:{port}".format(**kfk_conf), topic, e), self.story
            )

        message = result[0]
        raw_data = json.loads(message[:-1] if message[-1] == "\x00" or message[-1] == "\n" else message)
        report_time = raw_data["data"]["utctime"]
        d = datetime.datetime.strptime("%s+0000" % report_time, "%Y-%m-%d %H:%M:%S%z")
        offset = time.time() - d.timestamp()
        if offset > 10 * 60:
            return KafkaDataDelay(
                "Kafka[{}] topic[{}] 中最新数据与当前时间相差 {}秒".format("{domain}:{port}".format(**kfk_conf), topic, offset),
                self.story,
            )


@register_step(KernelStory)
class FtaActionServiceQueueCheck(CheckStep):
    name = "check fta action service signal queue"

    def check(self):
        # 检测待检测信号队列是否拥堵
        client = cache_key.FTA_ACTION_LIST_KEY.client
        for action_type in ActionPluginType.PLUGIN_TYPE_DICT.keys():
            key = cache_key.FTA_ACTION_LIST_KEY.get_key(action_type=action_type)
            signal_len = client.llen(key)
            if signal_len > 100:
                p = FtaActionSignalPending(f"[{action_type}] 动作执行等待队列已堵塞(当前堆积: {signal_len})", self.story)
                return p
            self.story.info(f"[{action_type}] fta action signal queue length is {signal_len}")
        return None


class APIERROR(ResolvedProblem):
    solution = "请确认kernel_api进程状态"


class KafkaConnectionError(ResolvedProblem):
    solution = "请确认kafka组件状态"


class KafkaNoData(ResolvedProblem):
    solution = "请确认gse_data服务状态, 同时确认zk中的配置信息[/gse/config/etc/dataserver/data/1001]是否正确"


class KafkaDataDelay(ResolvedProblem):
    solution = "请确认gse_data服务状态，或确认被管控机器是否启动了basereport进程"


class Kafka1000Delay(ResolvedProblem):
    solution = (
        "执行：grep 'poll alarm list' kernel.log 观察拉取事件条数，若达到10000表示当前已满负荷处理GSE基础事件。"
        "确认大量基础事件来源是否符合预期(少量机器大量corefile等异常事件需要手动定位解决)，"
        "如大量事件现象是符合预期的，则需要尽快扩容监控后台以提升集群针对基础事件的处理能力。"
    )


class AlertPollerDelay(ResolvedProblem):
    solution = (
        "执行：grep 'alert.poller' kernel.log 观察是否存在error日志。" "如果存在 'consul error' 日志，需要重启 alert-service 或 alarm-alert模块"
    )


class AlertBuilderDelay(ResolvedProblem):
    solution = (
        "执行：grep 'alert.builder' kernel.log 观察拉取事件条数，若达到10000表示当前已满负荷处理。"
        "确认大量事件来源是否符合预期，如大量事件现象是符合预期的，则需要尽快扩容 celery_worker_alert 进程。"
    )


class APIPending(ResolvedProblem):
    solution = "建议扩容kernel_api: 在'conf/api/production/gunicorn_config.py' 中调大worker的值"


class DetectSignalPending(ResolvedProblem):
    solution = "建议扩容监控后台节点！"


class TriggerSignalPending(ResolvedProblem):
    solution = "建议立刻重启监控后台"


class TransferPending(ResolvedProblem):
    solution = "transfer集群处理能力低于数据上报量，需要立刻对dataid:1001进行扩容"


class CMDBCacheCronError(ResolvedProblem):
    solution = (
        "kernel 后台cmdb周期缓存任务存在连续失败的情况，需要"
        '在kernel.log中搜索关键字：cat kernel.log|grep "alarm_backends.core.cache.cmdb"|grep "error"'
        "以定位具体失败原因"
    )


class StrategyCacheCronError(ResolvedProblem):
    solution = (
        "kernel 后台策略相关周期缓存任务存在连续失败的情况，需要"
        '在kernel.log中搜索关键字：cat kernel.log|grep "refresh strategy error when"'
        "以定位具体失败原因"
    )


class AlertActionSignalPending(ResolvedProblem):
    solution = "建议扩容 composite 进程"


class ConvergeSignalPending(ResolvedProblem):
    solution = "请确认 run_service -s converge 进程是否正常启动，如果已经正常启动，则建议扩容 converge 进程"


class FtaActionSignalPending(ResolvedProblem):
    solution = "请确认 run_service -s fta_action 进程是否正常启动，如果已经正常启动，则建议扩容 fta_action 进程"
