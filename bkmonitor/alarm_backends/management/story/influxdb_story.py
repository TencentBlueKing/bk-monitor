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
import sys

from alarm_backends.management.story.base import (
    BaseStory,
    CheckStep,
    Problem,
    register_step,
    register_story, StepController,
)
from metadata.models import InfluxDBClusterInfo, InfluxDBHostInfo
from query_api.drivers.influxdb.client import InfluxDBClient, pool


@register_story()
class InfluxdbStory(BaseStory):
    name = "Influxdb Healthz Check"

    def __init__(self):
        # get all influxdb connection info
        host_list = InfluxDBClusterInfo.objects.values_list("host_name", flat=1).distinct()
        self.influxdb_list = InfluxDBHostInfo.objects.filter(host_name__in=host_list)


class InfluxdbEntry(StepController):
    def _check(self):
        return "-influxdb" in sys.argv


influxdb_controller = InfluxdbEntry()


@register_step(InfluxdbStory)
class InfluxdbSeriesNumCheck(CheckStep):
    name = "check influxdb series num"
    controller = influxdb_controller

    def check(self):
        p_list = []
        for influxdb in self.story.influxdb_list:
            series_num_info = show_series_num(influxdb)
            for db, num_info in series_num_info.items():
                if db == "_internal":
                    continue
                num, rate = num_info
                if (rate or 0) > 100 and (num or 0) > 500 * 10000:
                    warn_message = f"{influxdb.host_name}({influxdb.domain_name}): {db}: {num}({rate}/min)"
                    self.story.warning(warn_message)
                    continue
                    # 暂不做自监控通知,仅打印需要关注的db信息
                    # p = TSIncreaseProblem(warn_message, self.story,
                    #                       host=f"{influxdb.host_name}({influxdb.domain_name})", db=db)
                    # p_list.append(p)
        return p_list


class TSIncreaseProblem(Problem):
    solution = "【重要】: influxdb主机{host}下的DB:{db} ts量级增长过快，需要观察是否一直持续，如果一直持续增长，需要尽快优化采集。"

    def position(self):
        self.story.warning(self.solution.format(**self.context))


def show_series_num(influxdb: InfluxDBHostInfo) -> dict:
    """
    {'uptimecheck': [302, 0], 'system': [8807355, -220.66666666604578]}
    """
    # 查询最近5分钟 各个 数据库的series 每分钟增长情况
    num_sql = (
        """select last(numSeries) as "last" from "database" where time > now() - 5m """
        """group by "database", time(1m) limit 1"""
    )
    rate_sql = (
        """select difference(mean(numSeries)) as "last" from "database" where time > now() - 5m """
        """group by "database", time(1m) limit 1"""
    )
    client = get_client_by_influxdb(influxdb)
    num = client.query(num_sql, database="_internal", epoch="ms")
    rate = client.query(rate_sql, database="_internal", epoch="ms")
    db_series_num_map = {}
    for series_dict in num.keys():
        s_name, series = series_dict
        db_name = series[s_name]
        if db_name not in db_series_num_map:
            db_series_num_map[db_name] = []
    for db_name in db_series_num_map:
        for ret in [num, rate]:
            points = list(ret.get_points(tags={"database": db_name}))
            if points:
                db_series_num_map[db_name].append(points[-1]["last"])
    return db_series_num_map


def qps(influxdb: InfluxDBHostInfo):
    pass


def show_databases(influxdb: InfluxDBHostInfo) -> [dict]:
    """
    [{'name': '_internal'}, {'name': 'xxx'}]
    :param influxdb:
    :return:
    """
    return get_client_by_influxdb(influxdb).get_list_database()


def get_client_by_influxdb(influxdb: InfluxDBHostInfo) -> InfluxDBClient:
    connection_args = influxdb.consul_config
    connection_args["host"] = connection_args.pop("domain_name")
    return pool.get_client(**connection_args)
