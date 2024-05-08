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
import arrow
from django.core.management.base import BaseCommand
from django.db.models import Count

from bkm_space.errors import NoRelatedResourceError
from bkm_space.validate import validate_bk_biz_id
from bkmonitor.data_source import UnifyQuery, load_data_source
from bkmonitor.models import AlgorithmModel, StrategyModel
from constants.data_source import DataSourceLabel, DataTypeLabel

target_biz_list = []


class Command(BaseCommand):
    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

    def handle(self, *args, **options):
        print(parse_strategy.__doc__)
        parse_strategy()
        print(parse_uptime_check.__doc__)
        parse_uptime_check()


def parse_strategy():
    """按业务获取基础策略数量，并按一定顺序排列"""
    # 1. 按业务聚合统计基础策略
    # 1.1 基础策略匹配
    s_id = list(
        AlgorithmModel.objects.exclude(type__in=AlgorithmModel.AIOPS_ALGORITHMS).values_list("strategy_id", flat=1)
    )
    ret = StrategyModel.objects.filter(pk__in=s_id, is_enabled=1).values("bk_biz_id").annotate(count=Count("bk_biz_id"))
    strategy_info = {s["bk_biz_id"]: s["count"] for s in ret}
    # 2. 业务不在目标中的，且为负数的，将数据累积到归属业务上
    to_be_migrated = list()
    for biz_id in strategy_info:
        if biz_id < 0:
            try:
                real_biz_id = validate_bk_biz_id(biz_id)
                to_be_migrated.append((biz_id, real_biz_id))
                print(f"{biz_id} -> {real_biz_id}")
            except NoRelatedResourceError:
                pass
    # 2.1 累积归属业务
    for biz_id, target_biz_id in to_be_migrated:
        strategy_info.setdefault(target_biz_id, 0)
        strategy_info[target_biz_id] += strategy_info.pop(biz_id)
    # 3. 按顺序输出结果
    for target_biz in target_biz_list:
        print(strategy_info.get(target_biz, 0))


def parse_uptime_check():
    """按业务获取http， udp， tcp， icmp的拨测节点数据数量"""
    now_ts = arrow.now()
    data_source = load_data_source(DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES)(
        table="uptimecheck.http",
        metrics=[{"field": "available", "method": "count_without_time", "alias": "a"}],
        interval=300,
        group_by=["bk_biz_id"],
    )
    query = UnifyQuery(bk_biz_id=None, data_sources=[data_source], expression="")
    http_records = query.query_data(
        start_time=now_ts.replace(minutes=-3).timestamp * 1000, end_time=now_ts.timestamp * 1000
    )
    # udp
    data_source = load_data_source(DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES)(
        table="uptimecheck.udp",
        metrics=[{"field": "available", "method": "count_without_time", "alias": "a"}],
        interval=300,
        group_by=["bk_biz_id"],
    )
    query = UnifyQuery(bk_biz_id=None, data_sources=[data_source], expression="")
    udp_records = query.query_data(
        start_time=now_ts.replace(minutes=-3).timestamp * 1000, end_time=now_ts.timestamp * 1000
    )
    # tcp
    data_source = load_data_source(DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES)(
        table="uptimecheck.tcp",
        metrics=[{"field": "available", "method": "count_without_time", "alias": "a"}],
        interval=300,
        group_by=["bk_biz_id"],
    )
    query = UnifyQuery(bk_biz_id=None, data_sources=[data_source], expression="")
    tcp_records = query.query_data(
        start_time=now_ts.replace(minutes=-3).timestamp * 1000, end_time=now_ts.timestamp * 1000
    )
    # icmp
    data_source = load_data_source(DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES)(
        table="uptimecheck.icmp",
        metrics=[{"field": "available", "method": "count_without_time", "alias": "a"}],
        interval=300,
        group_by=["bk_biz_id"],
    )
    query = UnifyQuery(bk_biz_id=None, data_sources=[data_source], expression="")
    icmp_records = query.query_data(
        start_time=now_ts.replace(minutes=-3).timestamp * 1000, end_time=now_ts.timestamp * 1000
    )

    records = http_records + tcp_records + icmp_records + udp_records

    node_info = {}
    for record in records:
        bk_biz_id = int(record["bk_biz_id"])
        node_info.setdefault(bk_biz_id, 0)
        node_info[bk_biz_id] += record["_result_"]

    for target_biz in target_biz_list:
        print(node_info.get(target_biz, 0))
