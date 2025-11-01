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
from itertools import chain

import arrow
from django.conf import settings
from django.utils.translation import gettext as _

from alarm_backends.core.cache.cmdb import HostManager
from alarm_backends.core.control.strategy import Strategy
from alarm_backends.service.access.event.records.base import EventRecord
from api.cmdb.define import Host
from constants.common import DEFAULT_TENANT_ID

logger = logging.getLogger("access.event")


class GseCustomStrEventRecord(EventRecord):
    """
    raw data format:
    {
       "_bizid_" : 0,
       "_cloudid_" : 0,
       "_server_" : "127.0.0.1",
       "_time_" : "2019-03-02 15:29:24",
       "_utctime_" : "2019-03-02 07:29:24",
       "_value_" : [ "This service is offline" ]
    }

    output_standard_data:
    {
        "data": {
            "record_id": "{dimensions_md5}.{timestamp}",
            "dimensions": {
                "bk_target_ip": "127.0.0.1",
                "bk_target_cloud_id": "0",
                "bk_topo_node": ["biz|2", "set|5", "module|6"]
            },
            "value": "This service is offline",
            "time": 1551482964,
            "raw_data": {
               "_bizid_" : 0,
               "_cloudid_" : 0,
               "_server_" : "127.0.0.1",
               "_time_" : "2019-03-02 15:29:24",
               "_utctime_" : "2019-03-02 07:29:24",
               "_value_" : [ "This service is offline" ]
            }
        },
        "anomaly": {
            "1": {
                "anomaly_message": "This service is offline",
                "anomaly_id": "{dimensions_md5}.{timestamp}.{strategy_id}.{item_id}.{level}",
                "anomaly_time": "2019-03-02 07:29:24"
            }
        },
        "strategy_snapshot_key": "xxx"
    }
    """

    TYPE = 100
    NAME = "gse_custom_event"
    METRIC_ID = "bk_monitor.gse_custom_event"
    TITLE = _("自定义字符型")

    def __init__(self, raw_data, strategies: dict[int, dict[int, "Strategy"]]):
        super().__init__(raw_data=raw_data)

        self.strategies = strategies

    def check(self):
        if len(self.raw_data["_value_"]) >= 1:
            logger.debug(f"custom event value: {self.raw_data}")
            return True
        else:
            logger.warning(f"custom event value check fail: {self.raw_data}")
            return False

    def get_host(self, alarm: dict) -> Host | None:
        # 多租户模式下，bk_tenant_id为None进行跨租户查询
        if settings.ENABLE_MULTI_TENANT_MODE:
            bk_tenant_id = None
        else:
            bk_tenant_id = DEFAULT_TENANT_ID

        agent_id = alarm.get("_agent_id_")

        if agent_id and ":" in agent_id:
            bk_cloud_id, ip = agent_id.split(":")
            agent_id = ""
            bk_cloud_id = int(bk_cloud_id)
        else:
            ip = alarm.get("_host_")
            bk_cloud_id = alarm.get("_cloudid_") or 0

        host = None
        if agent_id:
            host = HostManager.get_by_agent_id(bk_agent_id=agent_id, bk_tenant_id=bk_tenant_id)
        elif ip and bk_tenant_id:
            # 基于ip的查询仅在单租户模式下生效
            host = HostManager.get(bk_tenant_id=bk_tenant_id, ip=ip, bk_cloud_id=bk_cloud_id, using_mem=True)

        return host

    def full(self):
        alarm = self.raw_data

        host_obj = self.get_host(alarm)
        if not host_obj:
            return []

        biz_id = int(host_obj.bk_biz_id)
        alarm["_biz_id_"] = biz_id

        dimensions = alarm.setdefault("dimensions", {})

        # 判断agent版本，增加agent_version维度
        if "_agent_id_" in alarm:
            agent_id = alarm["_agent_id_"]
            if agent_id and ":" not in agent_id:
                dimensions["agent_version"] = "v2"
            else:
                dimensions["agent_version"] = "v1"

        try:
            dimensions["bk_target_ip"] = host_obj.bk_host_innerip
            dimensions["bk_target_cloud_id"] = host_obj.bk_cloud_id
            dimensions["bk_host_id"] = host_obj.bk_host_id
            if host_obj.topo_link:
                dimensions["bk_topo_node"] = sorted({node.id for node in chain(*list(host_obj.topo_link.values()))})
        except Exception as e:
            logger.exception(f"{self.__class__.__name__} full error {alarm}, {e}")
            return []

        new_record_list = []
        strategies = self.strategies.get(int(biz_id))
        if not strategies:
            logger.warning("abandon custom event(%s), because not strategy", self.raw_data)
            return []

        for strategy_id, strategy_obj in list(strategies.items()):
            # 针对每条策略， 只要是配置了该事件的策略，都克隆一个新的event record 对象。
            if not strategy_obj.items or self.METRIC_ID not in strategy_obj.items[0].metric_ids:
                continue
            new_alarm = {}
            new_alarm.update(alarm)
            new_alarm["strategy"] = strategy_obj

            new_record_list.append(self.__class__(new_alarm, self.strategies))
        return new_record_list

    def flat(self):
        alarm_time = self.raw_data["_utctime_"]
        values = self.raw_data.pop("_value_", [])
        event_records = []
        for v in values:
            new_alarm = {
                "_time_": alarm_time,
                "_type_": "-1",  # 自定义字符型没有类型，暂时填写-1
                "_bizid_": self.raw_data["_bizid_"],
                "_cloudid_": self.raw_data["_cloudid_"],
                "_server_": self.raw_data["_server_"],
                "_host_": self.raw_data["_server_"],
                "_title_": v,
                "_extra_": {"value": v},
            }
            event_records.append(self.__class__(new_alarm, self.strategies))
        return event_records

    ######################
    # CLEAN DATA METHODS #
    ######################

    def clean_time(self):
        return self.event_time

    def clean_record_id(self):
        return f"{self.md5_dimension}.{self.event_time}"

    def clean_dimensions(self):
        dimensions = self.raw_data["dimensions"].copy()
        # 将过滤维度添加到dimensions中，方便后续问题排查
        dimensions.update(self.filter_dimensions)
        return dimensions

    def clean_value(self):
        return self.raw_data["_title_"]

    def clean_values(self):
        return {"time": self.event_time, "value": self.raw_data["_title_"]}

    #########################
    # CLEAN ANOMALY METHODS #
    #########################

    def clean_anomaly_id(self):
        """
        {md5_dimension}.{timestamp}.{strategy_id}.{item_id}.{level}"
        """
        return f"{self.md5_dimension}.{self.event_time}.{self._strategy_id}.{self._item_id}.{self.level}"

    def clean_anomaly_message(self):
        return self.raw_data["_title_"]

    def clean_anomaly_time(self):
        return arrow.utcnow().format("YYYY-MM-DD HH:mm:ss")
