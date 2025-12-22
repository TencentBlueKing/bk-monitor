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

import arrow

from alarm_backends import constants
from alarm_backends.core.cache.cmdb import HostManager
from alarm_backends.core.control.item import Item
from alarm_backends.service.access import base
from alarm_backends.service.access.data.records import DataRecord
from bkmonitor.utils.common_utils import safe_int

logger = logging.getLogger("access.data")


class ExpireFilter(base.Filter):
    """
    过期数据过滤器
    """

    def filter(self, record):
        utctime = record.time
        # 丢弃超过max(半个小时 或者 10个周期延迟)的告警
        expire_seconds = max([record.items[0].query_configs[0]["agg_interval"] * 10, 30 * constants.CONST_MINUTES])
        if arrow.utcnow().timestamp - arrow.get(utctime).timestamp > expire_seconds:
            logger.info(f"Discard the data({record.raw_data}) because it takes more than 30 minutes")
            return True
        else:
            return False


class RangeFilter(base.Filter):
    """
    策略目标过滤器
    """

    def filter(self, record):
        """
        1. 在范围内，则不过滤掉，返回False
        2. 不在范围内，则过滤掉，返回True

        注意：每个item的范围是不一致的，只有当所有的item都被过滤掉后，才返回True

        :param record: DataRecord / EventRecord
        """

        dimensions = record.dimensions
        items: list[Item] = record.items
        for item in items:
            item_id = item.id
            if not record.is_retains[item_id]:
                # 如果被前面的filter过滤了，没有被保留下来，这里就直接跳过，节省时间
                continue

            is_match = item.is_range_match(dimensions)
            is_filtered = not is_match
            if is_filtered:
                logger.debug(
                    f"Discard the alarm ({record.raw_data}) because it not match strategy({item.strategy.id}) item({item_id}) agg_condition"
                )

            record.is_retains[item_id] = not is_filtered

        # 数据保留下来，因为数据可能多策略共用，不同策略有不同的过滤条件。同时都被过滤的情况下，也保留下来（给无数据告警使用）
        return False


class HostStatusFilter(base.Filter):
    """
    主机状态过滤器
    """

    def filter(self, record: DataRecord):
        """
        如果主机运营状态为不监控的几种类型，则直接过滤

        :param record: DataRecord / EventRecord
        """
        # 非主机数据不处理
        if "bk_host_id" not in record.dimensions and "bk_target_ip" not in record.dimensions:
            return False

        # 过滤非法的主机数据
        if not record.dimensions.get("bk_target_ip") and not record.dimensions.get("bk_host_id"):
            return True

        if record.dimensions.get("bk_host_id"):
            host = HostManager.get_by_id(
                bk_tenant_id=record.bk_tenant_id, bk_host_id=record.dimensions["bk_host_id"], using_mem=True
            )
        elif "bk_target_ip" in record.dimensions and "bk_target_cloud_id" in record.dimensions:
            host = HostManager.get(
                bk_tenant_id=record.bk_tenant_id,
                ip=record.dimensions["bk_target_ip"],
                bk_cloud_id=safe_int(record.dimensions["bk_target_cloud_id"]),
                using_mem=True,
            )
        else:
            return False

        if host is None:
            logger.debug(f"Discard the record ({record.raw_data}) because host is unknown")
            return True

        is_filtered = host.ignore_monitoring
        for item in record.items:
            record.is_retains[item.id] = not is_filtered and record.is_retains[item.id]
        if is_filtered:
            logger.debug(
                f"Discard the record ({record.raw_data}) because host({host.display_name}) status is {host.bk_state}"
            )
        return False
