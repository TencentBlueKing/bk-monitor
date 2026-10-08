"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import logging
import signal
import time
from collections import defaultdict

from django.conf import settings
from kafka import KafkaConsumer, TopicPartition

from alarm_backends.core.cache.key import (
    ALERT_DATA_POLLER_LEADER_KEY,
    ALERT_HOST_DATA_ID_KEY,
)
from alarm_backends.core.cluster import get_cluster
from alarm_backends.core.handlers import base
from alarm_backends.management.hashring import HashRing
from alarm_backends.management.utils import get_host_addr
from alarm_backends.service.alert.builder.tasks import run_alert_builder
from bkmonitor.models import EventPluginInstance
from bkmonitor.utils.consul import BKConsul
from bkmonitor.utils.thread_backend import InheritParentThread
from core.drf_resource import api

logger = logging.getLogger("alert.poller")


def always_retry(wait):
    def decorator(func):
        def wrapper(*args, **kwargs):
            while True:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    logger.exception(f"alert handler error: {func.__name__}: {e}")
                    if args[0]._stop_signal:
                        return
                    time.sleep(wait)

        return wrapper

    return decorator


class AlertHandler(base.BaseHandler):
    # 内置 topic
    INTERNAL_TOPICS = (settings.MONITOR_EVENT_KAFKA_TOPIC,)  # 蓝鲸监控专用
    MAX_RETRIEVE_NUMBER = 5000
    MAX_EVENT_NUMBER = 500
    MAX_POLLER_THREAD = 20
    _kafka_queues = {}

    def __init__(self, service, *args, **kwargs):
        super().__init__()
        self.service = service
        self.run_once = True
        self._stop_signal = False
        self.topic_data_id = {}
        self.max_event_number = getattr(settings, "MAX_BUILD_EVENT_NUMBER", 0) or self.MAX_EVENT_NUMBER
        self.consumers: dict[str, KafkaConsumer] = {}
        self.ip = get_host_addr()
        self.redis_client = ALERT_DATA_POLLER_LEADER_KEY.client
        self.data_id_cache_key = ALERT_HOST_DATA_ID_KEY.get_key()
        self.leader_key = ALERT_DATA_POLLER_LEADER_KEY.get_key()

    def _stop(self, *args, **kwargs):
        self._stop_signal = True

    @staticmethod
    def get_all_hosts():
        """
        获取所有运行中机器
        """
        prefix = "{}_{}_{}_{}/{}".format(
            settings.APP_CODE,
            settings.PLATFORM,
            settings.ENVIRONMENT,
            get_cluster().name,
            "run_discovery_service-alert",
        )
        client = BKConsul()
        host_keys = client.kv.get(prefix, keys=True)[1]
        return [host_key.split("/")[-2] for host_key in host_keys]

    def handle(self):
        # 需要拉取的topic分两部分
        # 1. 内置topic，直接将事件写入到 kafka 中
        # 2. 自定义topic，通过常规事件源接入
        signal.signal(signal.SIGTERM, self._stop)
        signal.signal(signal.SIGINT, self._stop)
        leader = InheritParentThread(target=self.run_leader)
        poller = InheritParentThread(target=self.run_poller)
        leader.start()
        poller.start()

        try:
            while True:
                try:
                    self.service.register()
                except Exception as error:
                    logger.exception(
                        "[main poller thread] register service failed, retry later, error info %s", str(error)
                    )
                if self._stop_signal:
                    break

                time.sleep(15)
        except Exception as e:
            logger.exception("Do event poller task in host(%s) failed %s", self.ip, str(e))
        finally:
            self._stop()
            leader.join()
            poller.join()
            self.service.unregister()

    @always_retry(10)
    def run_leader(self):
        """
        分发data_id获取任务
        :return:
        """
        # 抢占redis leader锁
        while not self._stop_signal:
            result = self.redis_client.set(self.leader_key, self.ip, nx=True, ex=ALERT_DATA_POLLER_LEADER_KEY.ttl)
            leader_ip = self.redis_client.get(self.leader_key)
            if not result and leader_ip != self.ip:
                logger.info(
                    "[run_leader] %s is elected to be alert poller leader already, current host sleep 10 secs",
                    leader_ip,
                )
                time.sleep(10)
            else:
                # leader 分配data_id
                if get_cluster().is_default():
                    plugin_data_ids = list(
                        EventPluginInstance.objects.filter(is_enabled=True).values_list("data_id", flat=True)
                    )
                else:
                    plugin_data_ids = []
                logger.info(
                    "[run_leader] ip(%s) is elected to be leader, start to dispatch data_ids, %s",
                    self.ip,
                    plugin_data_ids,
                )

                plugin_kafka_configs = defaultdict(list)
                plugin_data_ids.append(0)
                existed_data_kfk_info = {}
                for topics in self.redis_client.hgetall(self.data_id_cache_key).values():
                    for topic_info in json.loads(topics):
                        existed_data_kfk_info[topic_info["data_id"]] = {
                            "topic": topic_info["topic"],
                            "bootstrap_server": topic_info["bootstrap_server"],
                        }

                consumers = {}
                for data_id in plugin_data_ids:
                    try:
                        # 告警默认采用
                        # TODO 是否需要判断data_id是否已经该存在
                        if data_id != 0:
                            if data_id in existed_data_kfk_info:
                                # 增加是否已经分配到了对应的kfk信息
                                bootstrap_server = existed_data_kfk_info[data_id]["bootstrap_server"]
                                topic = existed_data_kfk_info[data_id]["topic"]
                            else:
                                data_id_info = api.metadata.get_data_id(bk_data_id=data_id)
                                kafka_config = data_id_info["result_table_list"][0]["shipper_list"][0]
                                cluster_config = kafka_config["cluster_config"]
                                bootstrap_server = f"{cluster_config['domain_name']}:{cluster_config['port']}"
                                topic = kafka_config["storage_config"]["topic"]
                        else:
                            # 使用专用kafka集群: ALERT_KAFKA_HOST  ALERT_KAFKA_PORT
                            bootstrap_server = f"{settings.ALERT_KAFKA_HOST[0]}:{settings.ALERT_KAFKA_PORT}"
                            # 默认集群使用默认topic，其他集群使用集群名作为topic后缀
                            if get_cluster().is_default():
                                topic = settings.MONITOR_EVENT_KAFKA_TOPIC
                            else:
                                topic = f"{settings.MONITOR_EVENT_KAFKA_TOPIC}_{get_cluster().name}"

                        if bootstrap_server not in consumers:
                            consumers[bootstrap_server] = KafkaConsumer(bootstrap_servers=bootstrap_server)
                            consumers[bootstrap_server].topics()
                        consumer = consumers[bootstrap_server]

                        partition_configs = []
                        partitions = consumer.partitions_for_topic(topic) or {0}
                        for partition in partitions:
                            # 根据topic的partition进行分配
                            partition_configs.append(
                                {
                                    "partition": partition,
                                    "data_id": data_id,
                                    "topic": topic,
                                    "bootstrap_server": bootstrap_server,
                                }
                            )
                        plugin_kafka_configs[data_id] = partition_configs
                    except Exception as e:
                        logger.exception("get topic info of data id(%s) failed: %s", data_id, e)
                        continue
                try:
                    hosts = self.get_all_hosts()
                except Exception as error:
                    logger.exception("get all host from consul error %s", str(error))
                    hosts = []
                if not hosts:
                    # 一般没有获取到hosts， 可能是consul服务有问题, 暂时等待一下
                    time.sleep(15)
                else:
                    hash_ring = HashRing({host: 1 for host in hosts})
                    host_kfk_info = defaultdict(list)
                    for data_id, kfk_info in plugin_kafka_configs.items():
                        for partition_info in kfk_info:
                            host = hash_ring.get_node(f"{data_id}|{partition_info['partition']}")
                            host_kfk_info[host].append(partition_info)

                    # 将data_id分配信息写入redis
                    pipeline = self.redis_client.pipeline(transaction=True)
                    pipeline.delete(self.data_id_cache_key)
                    pipeline.hmset(
                        self.data_id_cache_key,
                        mapping={host: json.dumps(host_kfk_info[host]) for host in hosts},
                    )
                    pipeline.expire(self.data_id_cache_key, ALERT_HOST_DATA_ID_KEY.ttl)
                    pipeline.expire(self.leader_key, ALERT_DATA_POLLER_LEADER_KEY.ttl)
                    pipeline.execute()

                    # 每一次执行稍微停顿一下，节约资源
                    time.sleep(10)

            if self.run_once or self._stop_signal:
                logger.info(
                    "[run_leader] alert event run leader got stop signal %s, ready to delete leader ip(%s)",
                    self._stop_signal,
                    leader_ip,
                )
                if leader_ip == self.ip and self._stop_signal:
                    # 当前主机为leader并且终止程序之后，直接删除leader缓存
                    logger.info("[run_leader] delete leader cache(%s) by ip(%s)", leader_ip, self.ip)
                    self.redis_client.delete(self.leader_key)
                break

    def run_consumer_manager(self):
        """
        在消费线程内更新 Kafka 消费者，避免 assign/close 与 poll 并发。
        """
        kfk_confs = json.loads(self.redis_client.hget(self.data_id_cache_key, self.ip) or "[]")
        bootstrap_servers_topics = defaultdict(set)
        for kfk_conf in kfk_confs:
            bootstrap_server = kfk_conf.get("bootstrap_server")
            topic = kfk_conf.get("topic")
            if bootstrap_server and topic:
                self.topic_data_id[f"{bootstrap_server}|{topic}"] = kfk_conf.get("data_id")
                bootstrap_servers_topics[bootstrap_server].add(
                    TopicPartition(topic=topic, partition=kfk_conf.get("partition", 0))
                )

        for bootstrap_server in set(self.consumers) - bootstrap_servers_topics.keys():
            logger.info("[run_consumer_manager] delete %s", bootstrap_server)
            self.close_consumer(self.consumers.pop(bootstrap_server))

        for bootstrap_server, partitions in bootstrap_servers_topics.items():
            if bootstrap_server in self.consumers:
                consumer = self.consumers[bootstrap_server]
                if consumer.assignment() != partitions:
                    logger.info("[run_consumer_manager] update %s", bootstrap_server)
                    consumer.assign(partitions=list(partitions))
                continue

            logger.info("[run_consumer_manager] create %s", bootstrap_server)
            consumer = KafkaConsumer(
                bootstrap_servers=bootstrap_server,
                group_id=f"{settings.APP_CODE}.alert.builder",
                # 每个分区单次获取大小最大值为5M
                max_partition_fetch_bytes=1024 * 1024 * 5,
                request_timeout_ms=30000,
            )
            try:
                consumer.assign(partitions=list(partitions))
                for tp in partitions:
                    data_id = self.topic_data_id.get(f"{bootstrap_server}|{tp.topic}")
                    if not data_id or tp.partition != 0:
                        # 兼容历史的处理记录，以前默认的 partition 都为 0
                        continue
                    redis_offset = self.get_kafka_redis_offset(data_id=data_id, topic=tp.topic)
                    if redis_offset:
                        consumer.seek(tp, redis_offset)
            except Exception:
                consumer.close(autocommit=False)
                raise
            self.consumers[bootstrap_server] = consumer

    @staticmethod
    def close_consumer(consumer):
        try:
            consumer.commit()
        finally:
            consumer.close(autocommit=False)

    @always_retry(10)
    def run_poller(self):
        """
        通过批量拉取数据
        :return:
        """
        next_refresh = 0
        try:
            while not self._stop_signal:
                if time.monotonic() >= next_refresh:
                    next_refresh = time.monotonic() + 15
                    try:
                        self.run_consumer_manager()
                    except Exception:
                        # 刷新失败时继续消费已有实例，下个周期重试。
                        logger.exception("[run_consumer_manager] refresh failed")

                has_record = False
                for bootstrap_server, consumer in self.consumers.items():
                    try:
                        data = consumer.poll(500, max_records=self.MAX_RETRIEVE_NUMBER)
                    except Exception as e:
                        logger.warning("[run_poller] poll error for %s, skip: %s", bootstrap_server, e)
                        continue
                    if not data:
                        continue

                    has_record = True
                    events = []
                    for records in data.values():
                        events.extend(records)
                    self.push_handle_task(consumer.config["bootstrap_servers"], events)
                    logger.info(
                        "[run_poller]  alert event poller poll %s: count(%s)",
                        consumer.config["bootstrap_servers"],
                        len(events),
                    )

                if self.run_once or self._stop_signal:
                    logger.info("[run_poller] alert event poller got stop signal")
                    break

                if not has_record and self.consumers:
                    logger.info("[run_poller] alert event poller get no data from %s", ",".join(self.consumers))
                if not self.consumers:
                    time.sleep(5)
                    logger.info("[run_poller] sleep(5 seconds) because of no consumer")
        finally:
            if self._stop_signal:
                for consumer in self.consumers.values():
                    try:
                        # 沿用最近的自动提交位点，避免在分发异常退出时确认未分发批次。
                        consumer.close(autocommit=False)
                    except Exception:
                        logger.exception("[run_poller] close consumer failed")
                self.consumers = {}

    def get_kafka_redis_offset(self, data_id, topic):
        """
        获取redis记录的offset
        """
        prefix = f"{settings.APP_CODE}_kafka_offset"
        group = f"alert.builder.{data_id}"
        offset_key = "_".join(map(str, [prefix, group, topic]))
        offset = self.redis_client.get(offset_key)
        # 删除掉记录的key
        self.redis_client.delete(offset_key)
        return offset

    def push_handle_task(self, bootstrap_server, events):
        # 分批次推送至告警生成任务
        for event_index in range(0, len(events), self.max_event_number):
            # 分发处理任务
            self.send_handler_task(
                event_kwargs={
                    "topic_data_id": self.topic_data_id,
                    "bootstrap_server": bootstrap_server,
                    "events": events[event_index : event_index + self.max_event_number],
                }
            )

    def send_handler_task(self, event_kwargs):
        run_alert_builder(**event_kwargs)


class AlertCeleryHandler(AlertHandler):
    def __init__(self, service, *args, **kwargs):
        super().__init__(service, *args, **kwargs)
        self.run_once = False

    def send_handler_task(self, event_kwargs):
        run_alert_builder.delay(**event_kwargs)
