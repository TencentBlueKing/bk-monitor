"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import itertools
import logging
import os
import signal
import socket
import time
import uuid
from collections import defaultdict

from django.conf import settings
import kafka

from alarm_backends.core.cache import key
from alarm_backends.service.access.tasks import run_access_event_handler_v2
from bkmonitor.utils.common_utils import safe_int
from bkmonitor.utils.thread_backend import InheritParentThread
from constants.common import DEFAULT_TENANT_ID
from constants.strategy import MAX_RETRIEVE_NUMBER
from core.drf_resource import api


logger = logging.getLogger("access.event")


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


class EventPoller:
    def __init__(self):
        self.topics_map = {}
        self.pod_id = socket.gethostname().rsplit("-", 1)[-1] or str(uuid.uuid4())[:8]
        self.refresh()
        self.should_exit = False
        self.consumer = None
        self.polled_info = defaultdict(int)

    def get_consumer(self):
        if self.consumer is None:
            self.consumer = self.create_consumer()
        return self.consumer

    def create_consumer(self):
        group_name = f"{settings.APP_CODE}.access.event"
        consumer = kafka.KafkaConsumer(
            bootstrap_servers=[f"{host}:{settings.KAFKA_PORT}" for host in settings.KAFKA_HOST],
            group_id=group_name,
            client_id=f"{group_name}-{self.pod_id}",
            enable_auto_commit=settings.KAFKA_AUTO_COMMIT,
            session_timeout_ms=30000,
            max_partition_fetch_bytes=1024 * 1024 * 5,  # 增大分区拉取量
            partition_assignment_strategy=[kafka.coordinator.assignors.roundrobin.RoundRobinPartitionAssignor],
            auto_offset_reset="latest",
        )
        consumer.subscribe(list(self.topics_map.keys()))
        return consumer

    def poll_once(self):
        consumer = self.get_consumer()
        logger.debug(f"[start event poller] topics: {consumer.subscription()}, pod_id: {self.pod_id}")
        records = consumer.poll(500, max_records=MAX_RETRIEVE_NUMBER)
        messages = list(itertools.chain.from_iterable(records.values()))
        logger.debug(f"[event poller] pulled {len(messages)}, pod_id: {self.pod_id}")
        return messages

    def close(self):
        if self.consumer is not None:
            try:
                # 先尝试正常唤醒消费者线程
                self.consumer.wakeup()
                # 确保关闭前完成所有pending操作
                self.consumer.commit()
            except Exception as e:
                logger.warning(f"[event poller] consumer wakeup/commit failed: {e}")
            finally:
                try:
                    self.consumer.close()
                except Exception as e:
                    logger.exception(f"[event poller] consumer close failed: {e}")
                self.consumer = None

    def _stop(self, signum, frame):
        logger.info(f"[event poller] received signal {signum}, shutting down...")
        self.should_exit = True
        self.close()  # 确保信号处理也调用增强版的close

    def __del__(self):
        self.should_exit = True

    @always_retry(10)
    def kick_task(self):
        check_time = time.time()
        while True:
            if time.time() - check_time < 5.0:
                time.sleep(1)
            client = key.EVENT_SIGNAL_KEY.client
            signal_channel = key.EVENT_SIGNAL_KEY.get_key()
            signals = client.smembers(signal_channel)
            # send task
            for data_id in signals:
                run_access_event_handler_v2.delay(data_id)
                logger.info(
                    "[access event poller] data_id(%s) pod_id(%s) push alarm list(%s) to redis %s",
                    data_id,
                    self.pod_id,
                    self.polled_info[data_id],
                    key.EVENT_LIST_KEY.get_key(data_id=data_id),
                )
            check_time = time.time()
            self.polled_info.clear()

    def start(self):
        # 添加退出信号处理，支持优雅退出
        signal.signal(signal.SIGTERM, self._stop)
        signal.signal(signal.SIGINT, self._stop)
        kick_task = InheritParentThread(target=self.kick_task)
        kick_task.start()
        while not self.should_exit:
            try:
                topic_data = {}
                messages = self.poll_once()
                # 先收集所有消息按topic分类
                for message in messages:
                    topic = message.topic
                    data = message.value
                    if topic not in topic_data:
                        topic_data[topic] = []
                    topic_data[topic].append(data)
                # 统一推送所有topic的数据到redis
                for topic, data_list in topic_data.items():
                    if data_list:
                        try:
                            self.push_to_redis(topic, data_list)
                        except KeyboardInterrupt:
                            self.should_exit = True
                        except Exception:
                            continue
            except KeyboardInterrupt:
                self.should_exit = True
            except Exception as e:
                logger.exception(f"[event poller] start poll error: {e}")

        self.close()

    def send_signal(self, data_id):
        client = key.EVENT_SIGNAL_KEY.client
        signal_channel = key.EVENT_SIGNAL_KEY.get_key()
        client.sadd(signal_channel, data_id)
        client.expire(signal_channel, key.EVENT_SIGNAL_KEY.ttl)

    def push_to_redis(self, topic, messages):
        if not messages:
            return
        messages = [m[:-1] if m[-1] == "\x00" or m[-1] == "\n" else m for m in messages]
        data_id = self.topics_map[topic]
        redis_client = key.EVENT_LIST_KEY.client
        data_channel = key.EVENT_LIST_KEY.get_key(data_id=data_id)
        redis_client.lpush(data_channel, *messages)
        redis_client.expire(data_channel, key.EVENT_LIST_KEY.ttl)
        self.send_signal(data_id)
        self.polled_info[data_id] += len(messages)
        logger.debug(
            "data_id(%s) topic(%s) pod_id(%s) push alarm list(%s) to redis %s",
            data_id,
            topic,
            self.pod_id,
            len(messages),
            data_channel,
        )

    def refresh(self):
        self.topics_map = {}
        DISABLE_EVENT_DATAID = os.getenv("DISABLE_EVENT_DATAID", "0")
        disabled_data_ids = {safe_int(i) for i in DISABLE_EVENT_DATAID.split(",")}
        data_ids = {
            settings.GSE_BASE_ALARM_DATAID,
            settings.GSE_CUSTOM_EVENT_DATAID,
            settings.GSE_PROCESS_REPORT_DATAID,
        } - disabled_data_ids
        for data_id in data_ids:
            topic_info = api.metadata.get_data_id(
                bk_tenant_id=DEFAULT_TENANT_ID, bk_data_id=data_id, with_rt_info=False
            )
            self.topics_map[topic_info["mq_config"]["storage_config"]["topic"]] = data_id
