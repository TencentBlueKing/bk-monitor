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
import signal
import threading
import time
from collections import defaultdict
from typing import Dict

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
        super(AlertHandler, self).__init__()
        self.service = service
        self.run_once = True
        self._stop_signal = False
        self.topic_data_id = {}
        self.max_event_number = getattr(settings, "MAX_BUILD_EVENT_NUMBER", 0) or self.MAX_EVENT_NUMBER
        self.consumers: Dict[str, KafkaConsumer] = {}
        self.ip = get_host_addr()
        self.redis_client = ALERT_DATA_POLLER_LEADER_KEY.client
        self.data_id_cache_key = ALERT_HOST_DATA_ID_KEY.get_key()
        self.leader_key = ALERT_DATA_POLLER_LEADER_KEY.get_key()
        self.consumers_lock = threading.Lock()

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
        consumer_manager = InheritParentThread(target=self.run_consumer_manager)
        poller = InheritParentThread(target=self.run_poller)
        leader.start()
        consumer_manager.start()
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
                    leader.join()
                    consumer_manager.join()
                    poller.join()
                    self.service.unregister()
                    break

                time.sleep(15)
        except Exception as e:
            logger.exception("Do event poller task in host(%s) failed %s", self.ip, str(e))
        finally:
            map(lambda c: self.close_consumer(c), self.consumers.values())

    @always_retry(10)
    def run_leader(self):
        """
        分发data_id获取任务
        :return:
        """
        # 抢占redis leader锁
        while True:
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
                                bootstrap_server = f'{cluster_config["domain_name"]}:{cluster_config["port"]}'
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
                    pipeline = self.redis_client.pipeline()
                    self.redis_client.delete(self.data_id_cache_key)
                    self.redis_client.hmset(
                        self.data_id_cache_key,
                        mapping={host: json.dumps(host_kfk_info[host]) for host in hosts},
                    )
                    self.redis_client.expire(self.data_id_cache_key, ALERT_HOST_DATA_ID_KEY.ttl)
                    self.redis_client.expire(self.leader_key, ALERT_DATA_POLLER_LEADER_KEY.ttl)
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

    @always_retry(10)
    def run_consumer_manager(self):
        """
        kafka消费者管理
        """
        while True:
            # 获取最新的topic信息
            kfk_confs = json.loads(self.redis_client.hget(self.data_id_cache_key, self.ip) or "{}")

            # kafka集群及所属topic分组
            bootstrap_servers_topics = defaultdict(set)
            for kfk_conf in kfk_confs:
                bootstrap_server = kfk_conf.get("bootstrap_server")
                topic = kfk_conf.get("topic")
                data_id = kfk_conf.get("data_id")
                partition = kfk_conf.get("partition", 0)
                if bootstrap_server and topic:
                    self.topic_data_id[f"{bootstrap_server}|{topic}"] = data_id
                    bootstrap_servers_topics[bootstrap_server].add(TopicPartition(topic=topic, partition=partition))

            update_bootstrap_servers = []
            create_bootstrap_servers = []
            delete_bootstrap_servers = []

            for bootstrap_server, tps in bootstrap_servers_topics.items():
                if bootstrap_server not in self.consumers:
                    create_bootstrap_servers.append(bootstrap_server)
                    continue

                consumer = self.consumers[bootstrap_server]
                if consumer.assignment() != tps:
                    # 当前分配的内容与新的不一致的情况
                    update_bootstrap_servers.append(bootstrap_server)

            for bootstrap_server in self.consumers:
                if bootstrap_server not in bootstrap_servers_topics:
                    delete_bootstrap_servers.append(bootstrap_server)

            if update_bootstrap_servers:
                logger.info(f"[run_consumer_manager] update {'|'.join(update_bootstrap_servers)}")
            if create_bootstrap_servers:
                logger.info(f"[run_consumer_manager]  create {'|'.join(create_bootstrap_servers)}")
            if delete_bootstrap_servers:
                logger.info(f"[run_consumer_manager] delete {'|'.join(delete_bootstrap_servers)}")

            if any([update_bootstrap_servers, create_bootstrap_servers, delete_bootstrap_servers]):
                self.consumers_lock.acquire()
                new_consumers = {}

                for bootstrap_server in create_bootstrap_servers:
                    new_consumers[bootstrap_server] = KafkaConsumer(
                        bootstrap_servers=bootstrap_server,
                        group_id=f"{settings.APP_CODE}.alert.builder",
                        # 每个分区单次获取大小最大值为5M
                        max_partition_fetch_bytes=1024 * 1024 * 5,
                    )
                    new_consumers[bootstrap_server].poll()
                    new_consumers[bootstrap_server].assign(partitions=list(bootstrap_servers_topics[bootstrap_server]))
                    for tp in bootstrap_servers_topics[bootstrap_server]:
                        # 新的需要重新设置一下offset
                        data_id = self.topic_data_id.get(f"{bootstrap_server}|{tp.topic}")
                        if not data_id or tp.partition != 0:
                            # 兼容历史的处理记录， 以前默认的partition都为0
                            continue
                        redis_offset = self.get_kafka_redis_offset(data_id=data_id, topic=tp.topic)
                        if redis_offset:
                            new_consumers[bootstrap_server].seek(tp, redis_offset)

                for bootstrap_server, consumer in self.consumers.items():
                    if bootstrap_server in delete_bootstrap_servers:
                        # 如果删除了，提交当前的记录
                        self.close_consumer(consumer)
                        continue

                    if bootstrap_server in update_bootstrap_servers:
                        consumer.assign(partitions=list(bootstrap_servers_topics[bootstrap_server]))
                    new_consumers[bootstrap_server] = consumer
                self.consumers = new_consumers
                self.consumers_lock.release()
            else:
                logger.info("[run_consumer_manager] comsumers have not changed, %s", len(list(self.consumers.values())))
            if self._stop_signal:
                self.consumers_lock.acquire()
                logger.info("[run_consumer_manager] got stop signal")
                map(lambda c: self.close_consumer(c), self.consumers.values())
                self.consumers = {}
                self.consumers_lock.release()
                break
            if self.run_once:
                break
            time.sleep(15)

    @staticmethod
    def close_consumer(consumer):
        consumer.commit()
        consumer.close()

    @always_retry(10)
    def run_poller(self):
        """
        通过批量拉取数据
        :return:
        """
        while True:
            self.consumers_lock.acquire()
            has_record = False
            for bootstrap_server, consumer in self.consumers.items():
                # 设置timeout时间500ms
                data = consumer.poll(500, max_records=self.MAX_RETRIEVE_NUMBER)
                if not data:
                    continue

                has_record = True
                events = []

                for records in list(data.values()):
                    events.extend(records)
                self.push_handle_task(consumer.config['bootstrap_servers'], events)
                logger.info(
                    "[run_poller]  alert event poller poll %s: count(%s)",
                    consumer.config['bootstrap_servers'],
                    len(events),
                )
            self.consumers_lock.release()

            if self.run_once or self._stop_signal:
                logger.info("[run_poller] alert event poller got stop signal")
                break

            # gpt说：如果消费者启用了自动提交消费位移，那么Kafka会在消费者poll消息时自动提交消费位移在这种情况下，
            # 如果消费者在第一次poll消息时没有消费完所有的消息，那么这些消息的消费位移就会被自动提交，导致第二次poll返回数据为空。
            # 所以没有数据不代表真实的没有数据
            if not has_record and self.consumers:
                logger.info(
                    "[run_poller]  alert event poller get no data from  %s", ",".join(list(self.consumers.keys()))
                )

            if not self.consumers:
                # 没有consumer的情况下，沉睡10秒钟，减少调度
                time.sleep(5)
                logger.info("[run_poller] sleep(5 seconds) because of no consumer")
                continue

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
        super(AlertCeleryHandler, self).__init__(service, *args, **kwargs)
        self.run_once = False

    def send_handler_task(self, event_kwargs):
        run_alert_builder.delay(**event_kwargs)
