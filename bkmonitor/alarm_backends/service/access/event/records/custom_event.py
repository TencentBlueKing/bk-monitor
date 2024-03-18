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


import logging
from itertools import chain

import arrow
from django.utils.translation import ugettext as _

from alarm_backends.core.cache.cmdb import HostManager
from alarm_backends.service.access.event.records.base import EventRecord

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

    def __init__(self, raw_data, strategies):
        super(GseCustomStrEventRecord, self).__init__(raw_data=raw_data)

        self.strategies = strategies

    def check(self):
        if len(self.raw_data["_value_"]) >= 1:
            logger.debug("custom event value: %s" % self.raw_data)
            return True
        else:
            logger.warning("custom event value check fail: %s" % self.raw_data)
            return False

    def get_plat_info(self, alarm):
        """获取单机告警中的plat_id, company_id, ip等字段"""
        bk_cloud_id = alarm.get("_cloudid_") or 0
        company_id = alarm.get("_bizid_") or 0  # 这里bizid存储的是companyid，而不是真实的bizid
        ip = alarm["_server_"]
        return bk_cloud_id, company_id, ip

    def full(self):
        alarm = self.raw_data
        bk_cloud_id, company_id, ip = self.get_plat_info(alarm)
        try:
            host_obj = HostManager.get(ip, bk_cloud_id, using_mem=True)
        except Exception as e:
            logger.exception(
                "{}, get host error, bk_cloud_id({}), " "ip({}), except({})".format(self.NAME, bk_cloud_id, ip, e)
            )
            return []

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
            if host_obj.topo_link:
                dimensions["bk_topo_node"] = sorted({node.id for node in chain(*list(host_obj.topo_link.values()))})
        except Exception as e:
            logger.exception("{} full error {}, {}".format(self.__class__.__name__, alarm, e))
            return []

        new_record_list = []
        strategies = self.strategies.get(int(biz_id))
        if not strategies:
            logger.warning("abandon custom event(%s), because not strategy", self.raw_data)
            return []

        for strategy_id, strategy_obj in list(strategies.items()):
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
        return "{md5_dimension}.{timestamp}".format(md5_dimension=self.md5_dimension, timestamp=self.event_time)

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
        return "{md5_dimension}.{timestamp}.{strategy_id}.{item_id}.{level}".format(
            md5_dimension=self.md5_dimension,
            timestamp=self.event_time,
            strategy_id=self._strategy_id,
            item_id=self._item_id,
            level=self.level,
        )

    def clean_anomaly_message(self):
        return self.raw_data["_title_"]

    def clean_anomaly_time(self):
        return arrow.utcnow().format("YYYY-MM-DD HH:mm:ss")
