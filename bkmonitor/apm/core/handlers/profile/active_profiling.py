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
from dataclasses import asdict

from django.conf import settings

from apm.core.discover.precalculation.consul_handler import ConsulKafkaInfo
from apm.models import ProfileDataSource
from constants.apm import BUILTIN_EVENT_GROUP_NAME, BUILTIN_PROFILING_APP_NAME
from metadata.models import ClusterInfo, DataSource, EventGroup, KafkaTopicInfo
from metadata.utils import consul_tools

logger = logging.getLogger("apm")

# BMW 预计算按此前缀读取，路径与 value 结构变更需同步 BMW
CONSUL_PATH_PREFIX = f"{settings.APP_CODE}_{settings.PLATFORM}_{settings.ENVIRONMENT}/active_profiling/data_id/"


class ActiveProfilingConsulHandler:
    """把主动 Profiling 事件分组 DataID 的 Kafka 信息同步到 Consul，供 BMW 预计算消费"""

    @classmethod
    def refresh(cls, bk_biz_id):
        """刷新单个业务，不清理其他 key"""
        cls._put_values([bk_biz_id])

    @classmethod
    def check_update(cls):
        """全量对账：刷新全部开通业务，并删除已失效 DataID 的 key"""
        # event_group_name 没有索引，先从开通时创建的 Profiling 数据源取业务，再按 bk_biz_id 查事件分组
        bk_biz_ids = list(
            ProfileDataSource.objects.filter(app_name=BUILTIN_PROFILING_APP_NAME).values_list("bk_biz_id", flat=True)
        )
        valid_data_ids = cls._put_values(bk_biz_ids)
        cls._delete_stale_keys(valid_data_ids)
        logger.info("[ActiveProfilingConsul] check update finished, valid data_ids->[%s]", len(valid_data_ids))

    @classmethod
    def _put_values(cls, bk_biz_ids):
        """写入业务事件分组的 Consul 配置，返回仍有效的 DataID；单个 DataID 失败时跳过并保留 Consul 旧值"""
        event_groups = list(
            EventGroup.objects.filter(
                bk_biz_id__in=bk_biz_ids, event_group_name=BUILTIN_EVENT_GROUP_NAME, is_delete=False, is_enable=True
            ).values("bk_tenant_id", "bk_biz_id", "bk_data_id")
        )
        data_ids = [event_group["bk_data_id"] for event_group in event_groups]
        mq_cluster_ids = dict(
            DataSource.objects.filter(bk_data_id__in=data_ids, is_enable=True).values_list(
                "bk_data_id", "mq_cluster_id"
            )
        )
        topics = dict(
            KafkaTopicInfo.objects.filter(bk_data_id__in=list(mq_cluster_ids)).values_list("bk_data_id", "topic")
        )
        clusters = {
            cluster.cluster_id: cluster
            for cluster in ClusterInfo.objects.filter(cluster_id__in=set(mq_cluster_ids.values()))
        }

        hash_consul = consul_tools.HashConsul()
        valid_data_ids = set()
        for event_group in event_groups:
            bk_data_id = event_group["bk_data_id"]
            if bk_data_id not in mq_cluster_ids:
                continue
            valid_data_ids.add(bk_data_id)

            try:
                cluster = clusters[mq_cluster_ids[bk_data_id]]
                kafka_info = ConsulKafkaInfo(
                    host=f"{cluster.domain_name}:{cluster.port}",
                    username=cluster.username,
                    password=cluster.password,
                    topic=topics[bk_data_id],
                )
                hash_consul.put(
                    key=f"{CONSUL_PATH_PREFIX}{bk_data_id}",
                    value={**event_group, "kafka_info": asdict(kafka_info)},
                    bk_data_id=bk_data_id,
                )
            except Exception:  # pylint: disable=broad-except
                logger.exception("[ActiveProfilingConsul] put consul config failed, data_id->[%s]", bk_data_id)

        return valid_data_ids

    @classmethod
    def _delete_stale_keys(cls, valid_data_ids):
        hash_consul = consul_tools.HashConsul()
        valid_keys = {f"{CONSUL_PATH_PREFIX}{bk_data_id}" for bk_data_id in valid_data_ids}
        _, keys = hash_consul.list_keys(CONSUL_PATH_PREFIX)
        for key in keys or []:
            if key not in valid_keys:
                hash_consul.delete(key)
