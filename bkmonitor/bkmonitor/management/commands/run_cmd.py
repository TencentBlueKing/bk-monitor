"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import re
from collections import defaultdict

import arrow
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Count

from bkm_space.errors import NoRelatedResourceError
from bkm_space.validate import validate_bk_biz_id
from bkmonitor.data_source import UnifyQuery, load_data_source
from bkmonitor.models.fta.action import StrategyActionConfigRelation
from bkmonitor.models.strategy import (
    AlgorithmModel,
    DetectModel,
    ItemModel,
    QueryConfigModel,
    StrategyModel,
    UserGroup,
)
from constants.common import DEFAULT_TENANT_ID
from constants.data_source import DataSourceLabel, DataTypeLabel
from constants.strategy import TargetFieldType
from core.drf_resource import api
from monitor_web.models import CollectorPluginMeta

target_biz_list = list(
    map(
        int,
        [
            i.strip()
            for i in """
# add biz list here
""".split("\n")
            if i
        ],
    )
)


class Command(BaseCommand):
    def add_arguments(self, parser):
        super().add_arguments(parser)

    def handle(self, *args, **options):
        print(parse_strategy.__doc__)
        parse_strategy()
        print(parse_uptime_check.__doc__)
        parse_uptime_check()
        print(parse_dataflow.__doc__)
        parse_dataflow()
        print(parse_histogram_quantile_strategy.__doc__)
        parse_histogram_quantile_strategy()
        print(parse_target_dimension_strategy.__doc__)
        parse_target_dimension_strategy()


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
    query = UnifyQuery(bk_biz_id=None, bk_tenant_id=DEFAULT_TENANT_ID, data_sources=[data_source], expression="")
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
    query = UnifyQuery(bk_biz_id=None, bk_tenant_id=DEFAULT_TENANT_ID, data_sources=[data_source], expression="")
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
    query = UnifyQuery(bk_biz_id=None, bk_tenant_id=DEFAULT_TENANT_ID, data_sources=[data_source], expression="")
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
    query = UnifyQuery(bk_biz_id=None, bk_tenant_id=DEFAULT_TENANT_ID, data_sources=[data_source], expression="")
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


def parse_dataflow():
    """
    按业务统计dataflow归属
    """
    project_id = settings.BK_DATA_PROJECT_ID
    flows = api.bkdata.get_data_flow_list(project_id=project_id)
    lines = ["{}\t{}".format(f["flow_id"], f["flow_name"]) for f in flows if f["status"] == "running"]

    strategy_info = {s["id"]: s["bk_biz_id"] for s in StrategyModel.objects.values("id", "bk_biz_id")}
    flow_info = {}
    child_flow = []

    for line in lines:
        flow_id, flow_name = line.strip().split("\t")
        flow_info[flow_id] = [flow_name]

    for flow_id, flow_name in flow_info.items():
        flow_name = flow_name[0]
        # 先统计完父flow
        if flow_name.startswith("#场景应用节点"):
            child_flow.append((flow_id, flow_name))
            continue
        bk_biz_id = clean_flow_name(flow_name, strategy_info)
        if not bk_biz_id:
            if "_bkplugin_" in flow_name:
                bk_biz_id = "100147"
        flow_info[flow_id].append(bk_biz_id)

    for flow_id, flow_name in child_flow:
        ret = re.search(r"^#场景应用节点<(\d+)_\d+>实例", flow_name, re.I | re.S)
        if ret:
            parent_flow_id = ret.group(1)
            flow_info[flow_id].append(flow_info.get(parent_flow_id, ["", ""])[1])

    bk_biz_info = defaultdict(int)

    for line in lines:
        flow_id, flow_name = line.strip().split("\t")
        bk_biz_id = flow_info[flow_id][1]
        if bk_biz_id:
            bk_biz_info[bk_biz_id] += 1

    for biz_id in target_biz_list:
        print(bk_biz_info[str(biz_id)])


def clean_flow_name(flow_name, strategy_info):
    deleted_plugin = {}
    # 全小写
    if flow_name.startswith("过滤无效时间"):
        name_list = flow_name.split("_")
        if name_list[1] == "ieod":
            table_name = "_".join(name_list[3:-1])
        else:
            index = 3
            if name_list[1].strip("ieod"):
                index = 2
            while index > 0:
                table_name = "_".join(name_list[index:-1])
                if not table_name:
                    index -= 1
                    continue
                else:
                    break
        if not table_name:
            print(f"flow_name: {flow_name} -> no table name fetch")
            return ""
        search_table_name = table_name.lower() if "jk_" not in table_name else "jk_"
        ret = (
            CollectorPluginMeta.objects.filter(plugin_id__icontains=search_table_name)
            .values("plugin_id", "bk_biz_id")
            .first()
        )
        if not ret:
            while search_table_name.count("_") >= 1:
                search_table_name = "_".join(search_table_name.split("_")[:-1])
                query = CollectorPluginMeta.objects.filter(plugin_id__icontains=search_table_name).values(
                    "plugin_id", "bk_biz_id"
                )
                count = query.count()
                ret = query.first()
                if ret:
                    print(f"{search_table_name} -> {ret['bk_biz_id']}[{count}]")
                    if count > 5:
                        ret = None
                    break
        if ret:
            bk_biz_id = ret["bk_biz_id"]
            if bk_biz_id == 0:
                bk_biz_id = 100147
            # print(f"{table_name}->{bk_biz_id}")
            return str(bk_biz_id)
        else:
            if search_table_name not in deleted_plugin:
                deleted_plugin[search_table_name] = flow_name
            print(f"{search_table_name} -> no plugin found")

    if flow_name.startswith("CMDB预聚合"):
        name_list = flow_name.split("_")
        if name_list[1] == "ieod":
            table_name = "_".join(name_list[3:-2])
        else:
            index = 3
            if name_list[1].strip("ieod"):
                index = 2
            while index > 0:
                table_name = "_".join(name_list[index:-2])
                if not table_name:
                    index -= 1
                    continue
                else:
                    break
        if not table_name:
            print(f"flow_name: {flow_name} -> no table name fetch")
            return ""
        search_table_name = table_name.lower() if "jk_" not in table_name else "jk_"
        ret = (
            CollectorPluginMeta.objects.filter(plugin_id__icontains=search_table_name)
            .values("plugin_id", "bk_biz_id")
            .first()
        )
        if not ret:
            while search_table_name.count("_") >= 1:
                search_table_name = "_".join(search_table_name.split("_")[:-1])
                query = CollectorPluginMeta.objects.filter(plugin_id__icontains=search_table_name).values(
                    "plugin_id", "bk_biz_id"
                )
                count = query.count()
                ret = query.first()
                if ret:
                    print(f"{search_table_name} -> {ret['bk_biz_id']}[{count}]")
                    if count > 5:
                        ret = None
                    break
        if ret:
            bk_biz_id = ret["bk_biz_id"]
            if bk_biz_id == 0:
                bk_biz_id = 100147
            # print(f"{table_name}->{bk_biz_id}")
            return str(bk_biz_id)
        else:
            if search_table_name not in deleted_plugin:
                deleted_plugin[search_table_name] = flow_name
            print(f"{search_table_name} -> no plugin found")

    ret = re.search(r"^(\d+)\s多指标异常检测 主机场景", flow_name, re.I | re.S)
    if ret:
        return ret.group(1)
    ret = re.search(r"^(\d+)\s(场景服务|模型应用) .*", flow_name, re.I | re.S)
    if ret:
        strategy_id = ret.group(1)
        return str(strategy_info.get(int(strategy_id), ""))

    ret = re.search(r"^(\d+)\s指标推荐", flow_name, re.I | re.S)
    if ret:
        return ret.group(1)


def parse_histogram_quantile_strategy():
    """
    统计promql中使用了百分位函数histogram_quantile的策略信息

    查询条件：
        1. 策略只配置了静态阈值算法
        2. 配置了promql 并且使用了百分位分析函数：histogram_quantile
        3. 策略的触发条件是x个周期1次。
    """

    # step1 查询关联了静态阈值算法的策略和监控项
    item_ids = AlgorithmModel.objects.filter(type="Threshold").values_list("item_id", flat=True)

    # step2 查询promql中使用了百分位函数histogram_quantile的监控项，及其关联的策略
    related_strategy_ids = ItemModel.objects.filter(
        origin_sql__contains="histogram_quantile", id__in=item_ids
    ).values_list("strategy_id", flat=True)

    # 获取关联的检测配置模型
    detects = DetectModel.objects.filter(strategy_id__in=related_strategy_ids).only("strategy_id", "trigger_config")
    # step3: 过滤出使用了count=1的检测配置
    strategy_ids = [detect.strategy_id for detect in detects if detect.trigger_config.get("count") in ["1", 1]]

    # step4: 获取策略模型
    strategies = StrategyModel.objects.filter(id__in=strategy_ids).only("id", "bk_biz_id", "name")

    #  获取业务信息
    biz_info = {biz.bk_biz_id: biz for biz in api.cmdb.get_business()}

    print("业务id、业务名、策略id、策略名:")
    for strategy in strategies:
        print(f"{strategy.bk_biz_id}、{biz_info.get(strategy.bk_biz_id)}、{strategy.id}、{strategy.name}")


def parse_target_dimension_strategy():
    """
    获取当前配置了监控目标，但未配置对应目标类型维度的监控策略
    """
    # 监控目标类型映射
    target_type_map = {
        TargetFieldType.host_target_ip: "host",
        TargetFieldType.host_ip: "host",
        TargetFieldType.host_topo: "host",
        TargetFieldType.service_topo: "topo",
        TargetFieldType.service_service_template: "service_instance",
        TargetFieldType.service_set_template: "service_instance",
        TargetFieldType.host_service_template: "host",
        TargetFieldType.host_set_template: "host",
        TargetFieldType.dynamic_group: "host",
    }

    # step1: 获取没有配置聚合维度的监控项ID
    query_configs = QueryConfigModel.objects.all().only("config", "item_id")

    unexpected_item_ids = set()
    item_ids = set()

    # ItemModel和QueryConfigModel是一对多关系，这里是过滤出所有query_config都没有配置聚合维度的item_id
    for query_config in query_configs:
        if not query_config.config["agg_dimension"]:
            item_ids.add(query_config.item_id)
        else:
            unexpected_item_ids.add(query_config.item_id)

    item_ids = item_ids - unexpected_item_ids

    # step2: 获取配置了监控目标的监控项
    items = ItemModel.objects.filter(id__in=item_ids).only("strategy_id", "target")
    # 策略与监控目标类型映射
    stra_target_type_map = {
        item.strategy_id: target_type_map.get(item.target[0][0]["field"])
        for item in items
        if item.target and item.target != [[]]
    }

    # step3: 获取目标策略
    strategies = StrategyModel.objects.filter(id__in=stra_target_type_map.keys()).only("id", "bk_biz_id", "name")
    print("业务id， 策略id， 策略名称，目标类型， 配置的维度列表")
    for strategy in strategies:
        print(strategy.bk_biz_id, strategy.id, strategy.name, stra_target_type_map[strategy.id], [])


def parse_usergroup_not_under_business(preview: bool = True):
    """
    排查关联的但是不在当前业务下的策略及告警组信息
    巡检用户组对应业务和策略业务不一致并同步修改，同时兜底使用运维用户组
    :param preview: 是否开启预览模式，开启预览模式，不替换数据，只打印信息
    :return:
    """

    if preview:
        print("策略id，策略名称，业务id，关联的非本业务的告警组信息，本业务下相同名称的告警组ID")
    else:
        print("策略id，策略名称，业务id，替换后关联的告警组信息")

    # 获取到所有的策略
    strategies_map = {
        strategy_id: (strategy_name, bk_biz_id)
        for strategy_id, strategy_name, bk_biz_id in StrategyModel.objects.all().values_list("id", "name", "bk_biz_id")
    }

    strategy_relations_map = {}

    # 获取到关联的告警组id
    for item in StrategyActionConfigRelation.objects.filter(strategy_id__in=strategies_map.keys()).only(
        "strategy_id", "user_groups"
    ):
        strategy_relations_map[item.strategy_id] = item

    # 所有的告警组key为id
    user_groups_base_id = {}
    # 所有的告警组key为name+bk_biz_id,value为告警组ID列表
    user_groups_base_name = defaultdict(list)

    for group in UserGroup.objects.filter().only("id", "name", "bk_biz_id"):
        user_groups_base_id[group.id] = (group.name, group.bk_biz_id)
        user_groups_base_name[(group.name, group.bk_biz_id)].append(group.id)

    strategy_relation_instances = []

    for strategy_id, (strategy_name, bk_biz_id) in strategies_map.items():
        strategy_relation = strategy_relations_map.get(strategy_id)
        if not strategy_relation:
            continue

        user_group_ids = strategy_relation.user_groups
        # 当前策略关联的告警组
        user_groups = {group_id: user_groups_base_id.get(group_id, (None, None)) for group_id in user_group_ids}
        same_group_ids = []  # 当前业务下想通名称的告警组
        raw_group_ids = []  # 原有的当前业务下的的告警组

        for gp_id, (gp_name, gp_bk_biz_id) in user_groups.items():
            if not gp_name:
                continue

            if gp_bk_biz_id == bk_biz_id:
                # 保留原有的当前业务下的的告警组
                raw_group_ids.append(gp_id)
                continue

            same_name_groups = user_groups_base_name.get((gp_name, bk_biz_id), [])
            if not same_name_groups:
                print("get default group: 【运维】")
                same_name_groups = user_groups_base_name.get(("运维", bk_biz_id), [])
            if preview:
                related_group_info = {
                    "id": gp_id,
                    "name": gp_name,
                    "bk_biz_id": gp_bk_biz_id,
                }
                print(f"{strategy_id},{strategy_name},{bk_biz_id},{related_group_info},{same_name_groups}")
            else:
                same_group_ids.extend(same_name_groups)

        if not preview and same_group_ids:
            strategy_relation = strategy_relations_map.get(strategy_id)
            strategy_relation.user_groups = raw_group_ids + same_group_ids
            strategy_relation_instances.append(strategy_relation)
            for group_id in raw_group_ids + same_group_ids:
                group_name, group_bk_biz_id = user_groups_base_id.get(group_id)
                related_group_info = {
                    "id": group_id,
                    "name": group_name,
                    "bk_biz_id": group_bk_biz_id,
                }
                print(f"{strategy_id},{strategy_name},{bk_biz_id},{related_group_info}")

    if not preview:
        StrategyActionConfigRelation.objects.bulk_update(strategy_relation_instances, ["user_groups"])
