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
from collections import defaultdict

import arrow
from django.db import connections
from django.utils.functional import cached_property

from bkmonitor.data_source import UnifyQuery, load_data_source
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import api
from core.statistics.metric import Metric, register
from monitor_web.statistics.v2.base import BaseCollector


def nodeman_sql_to_result(sql):
    """
    向节点管理请求数据，并返回结果
    :param sql: sql语句
    :return: 数组结果
    """
    with connections["nodeman"].cursor() as cursor:
        cursor.execute(sql)
        desc = cursor.description
        result = [dict(list(zip([col[0] for col in desc], row))) for row in cursor.fetchall()]
    return result


class HostCollector(BaseCollector):
    """
    主机监控
    """

    @cached_property
    def cloud_id_to_name(self):
        try:
            clouds = api.cmdb.search_cloud_area()
            return {cloud["bk_cloud_id"]: cloud["bk_cloud_name"] for cloud in clouds}
        except Exception:
            return {}

    @cached_property
    def biz_collector_status_list(self):
        return nodeman_sql_to_result(
            """
            select bk_biz_id, count(*) as count, bk_cloud_id, status, name from
             (select a.bk_host_id, a.bk_biz_id, a.bk_cloud_id, b.status, b.name from node_man_host as a
             inner join (select name, status, bk_host_id, is_latest, source_type from node_man_processstatus) as b
             on a.bk_host_id = b.bk_host_id and b.name in ('basereport', 'bkmonitorbeat', 'bkunifylogbeat')
             and b.is_latest = 1 and b.source_type = 'default') as c
             group by bk_biz_id, bk_cloud_id, status, name;
        """
        )

    @cached_property
    def biz_monitor_collector_status_list(self):
        """监控采集器 去重+合并统计"""

        # 与 biz_collector_status_list 不同的是，剔除了 logbeat 同时，将新旧采集器去重合并统计
        # 如果开启 sql_mode='ONLY_FULL_GROUP_BY' 模式，sql将运行失败。
        # 解决方案，将mysql 的sql_mode 去掉
        # SET GLOBAL sql_mode=(SELECT REPLACE(@@sql_mode,'ONLY_FULL_GROUP_BY',''));
        return nodeman_sql_to_result(
            """
            select bk_biz_id, count(distinct(inner_ip)) as count, bk_cloud_id, status, name from
             (select a.bk_host_id, a.bk_biz_id, a.bk_cloud_id, a.inner_ip, b.status, b.name from node_man_host as a
             inner join (select name, status, bk_host_id, is_latest, source_type from node_man_processstatus) as b
             on a.bk_host_id = b.bk_host_id and b.name in ('basereport', 'bkmonitorbeat')
             and b.is_latest = 1 and b.source_type = 'default') as c
             group by bk_biz_id, bk_cloud_id, status;
        """
        )

    @register(
        labelnames=(
            "bk_biz_id",
            "bk_biz_name",
            "target_cloud_id",
            "target_cloud_name",
            "agent_status",
        ),
        run_every=30 * 60,
    )
    def host_agent_count(self, metric: Metric):
        """
        主机Agent数
        """
        # 获取节点管理Agent安装状态
        biz_host_status_list = nodeman_sql_to_result(
            """
            select count(a.bk_host_id) as host_count, a.bk_biz_id, a.bk_cloud_id, b.status from node_man_host as a
            inner join (select name, status, bk_host_id from node_man_processstatus) as b on
            a.bk_host_id = b.bk_host_id and b.name="gseagent" group by bk_biz_id, status, bk_cloud_id;
        """
        )
        for agent in biz_host_status_list:
            bk_biz_id = agent["bk_biz_id"]
            if not self.biz_exists(bk_biz_id):
                continue
            bk_cloud_id = agent["bk_cloud_id"]
            target_cloud_name = self.cloud_id_to_name.get(int(bk_cloud_id), bk_cloud_id)
            metric.labels(
                bk_biz_id=bk_biz_id,
                bk_biz_name=self.get_biz_name(bk_biz_id),
                target_cloud_id=bk_cloud_id,
                target_cloud_name=target_cloud_name,
                agent_status=agent["status"],
            ).set(agent["host_count"])

    @register(
        labelnames=(
            "bk_biz_id",
            "bk_biz_name",
            "target_cloud_id",
            "target_cloud_name",
            "data_status",
        ),
        run_every=30 * 60,
    )
    def host_report_count(self, metric: Metric):
        """
        主机上报数
        """
        now_ts = arrow.now()
        data_source = load_data_source(DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES)(
            table="system.cpu_summary",
            metrics=[{"field": "idle", "method": "COUNT", "alias": "a"}],
            interval=60,
            group_by=["bk_biz_id", "bk_cloud_id"],
        )
        query = UnifyQuery(bk_biz_id=None, data_sources=[data_source], expression="")
        records = query.query_data(
            start_time=now_ts.replace(minutes=-3).timestamp * 1000, end_time=now_ts.timestamp * 1000
        )

        biz_cnt_map = defaultdict(int)
        for item in records:
            bk_biz_id = item.get("bk_biz_id")
            if not bk_biz_id:
                continue
            bk_cloud_id = item["bk_cloud_id"]
            biz_cnt_map[(bk_biz_id, bk_cloud_id)] = max(biz_cnt_map[(bk_biz_id, bk_cloud_id)], item["_result_"])

        # 正常的指标
        for item in records:
            bk_biz_id = item.get("bk_biz_id")
            if not self.biz_exists(bk_biz_id):
                continue
            bk_cloud_id = item["bk_cloud_id"]
            target_cloud_name = self.cloud_id_to_name.get(int(bk_cloud_id), bk_cloud_id)
            metric.labels(
                bk_biz_id=bk_biz_id,
                bk_biz_name=self.get_biz_name(bk_biz_id),
                target_cloud_id=bk_cloud_id,
                target_cloud_name=target_cloud_name,
                data_status="NORMAL",
            ).set(biz_cnt_map[(bk_biz_id, bk_cloud_id)])

        # 无数据指标：agent正常的机器-主机上报总数
        for collector in self.biz_monitor_collector_status_list:
            if collector["status"] != "RUNNING":
                continue
            bk_biz_id = collector["bk_biz_id"]
            if not bk_biz_id or not self.biz_exists(bk_biz_id):
                continue
            bk_cloud_id = collector["bk_cloud_id"]
            target_cloud_name = self.cloud_id_to_name.get(int(bk_cloud_id), bk_cloud_id)

            metric.labels(
                bk_biz_id=bk_biz_id,
                bk_biz_name=self.get_biz_name(bk_biz_id),
                target_cloud_id=bk_cloud_id,
                target_cloud_name=target_cloud_name,
                data_status="NO_DATA_REPORT",
                # ts 数据中，bk_biz_id 和 bk_cloud_id 均是字符串，需要强制转换一次
            ).set(collector["count"] - biz_cnt_map[(str(bk_biz_id), str(bk_cloud_id))])

    @register(
        labelnames=(
            "bk_biz_id",
            "bk_biz_name",
            "target_cloud_id",
            "target_cloud_name",
            "collector_status",
            "collector_name",
        ),
        run_every=30 * 60,
    )
    def host_collector_count(self, metric: Metric):
        """
        主机采集器数
        """

        for collector in self.biz_collector_status_list:
            bk_biz_id = collector["bk_biz_id"]
            if not self.biz_exists(bk_biz_id):
                continue
            bk_cloud_id = collector["bk_cloud_id"]
            target_cloud_name = self.cloud_id_to_name.get(int(bk_cloud_id), bk_cloud_id)
            metric.labels(
                bk_biz_id=bk_biz_id,
                bk_biz_name=self.get_biz_name(bk_biz_id),
                target_cloud_id=bk_cloud_id,
                target_cloud_name=target_cloud_name,
                collector_status=collector["status"],
                collector_name=collector["name"],
            ).set(collector["count"])
