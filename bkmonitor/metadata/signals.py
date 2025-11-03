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

from django.conf import settings
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from bkmonitor.utils import consul
from metadata.models import DataSource, InfluxDBHostInfo, InfluxDBStorage

logger = logging.getLogger("metadata")


@receiver(pre_delete, sender=DataSource)
def clean_datasource(sender, instance, using, **kwargs):
    """
    在真正删除信息前，清理数据源ID的Consul信息
    :param sender: The model class.
    :param instance: The actual instance being deleted.
    :param using: The database alias being used.
    :return:
    """
    if settings.ENVIRONMENT == "development":
        return

    instance.delete_consul_config()
    logger.info(f"datasource->[{instance.bk_data_id}] now is deleted its consul path.")

    return True


@receiver(pre_delete, sender=InfluxDBStorage)
def clean_influxdb_router(sender, instance, using, **kwargs):
    """
    在真正删除信息前，清理InfluxDB存储的Consul信息
    主要负责请求router下的信息，不涉及集群及机器信息
    :param sender: The model class.
    :param instance: The actual instance being deleted.
    :param using: The database alias being used.
    :return:
    """
    if settings.ENVIRONMENT == "development":
        return

    consul_client = consul.BKConsul()

    if not isinstance(instance, InfluxDBStorage):
        logger.error(
            f"clean_influxdb_router got info with instance is not InfluxDBStorage but->[{type(instance)}], nothing will do"
        )
        return False

    consul_client.kv.delete(instance.CONSUL_CONFIG_CLUSTER_PATH)
    logger.info(f"influxdb storage->[{instance.table_id}] now is deleted its consul path.")

    return True


@receiver(post_save, sender=InfluxDBHostInfo)
def refresh_influxdb_host(sender, instance, using, **kwargs):
    """刷新 influxdb host 的变动到 consul 和 redis"""
    logger.info("influxdb host -> [%s] refresh consul and redis start", instance.host_name)

    if settings.ENVIRONMENT == "development":
        return

    try:
        instance.refresh_consul_cluster_config()
    except Exception:
        logger.exception("refresh consul cluster config error")
        return

    logger.info("influxdb host -> [%s] refresh consul and redis end", instance.host_name)
