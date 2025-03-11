from collections import defaultdict
from typing import Dict, List

import arrow
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils.translation import gettext as _

from bkmonitor.models import ItemModel, QueryConfigModel, StrategyModel
from monitor_web.strategies.default_settings.common import (
    DEFAULT_NOTICE,
    NO_DATA_CONFIG,
    nodata_recover_detects_config,
    remind_algorithms_config,
    warning_algorithms_config,
)

# pod近30分钟重启次数过多，指标名
RESTARTS_TOTAL_METRIC_FIELD = 'kube_pod_container_status_restarts_total'
# 因OOM重启，指标名
TERMINATED_REASON_METRIC_FIELD = 'kube_pod_container_status_terminated_reason'

# pod近30分钟重启次数过多，promql
RESTARTS_TOTAL_PROMQL = (
    r'increase(sum by (pod_name, bcs_cluster_id, namespace, container_name)'
    r'(bkmonitor:kube_pod_container_status_restarts_total{bk_job="kube-state-metrics"})[30m:])'
)
# 因OOM重启，promql
TERMINATED_REASON_PROMQL = (
    r'increase ((max by (bcs_cluster_id, namespace, pod_name) (bkmonitor:'
    r'kube_pod_container_status_terminated_reason{container!="tke-monitor-agent",namespace!~"^'
    r'(|bkmonitor\\-operator)$",pod_name!="",reason="OOMKilled"}))[2m:])'
)

# pod近30分钟重启次数过多，默认策略
restarts_total_default_strategy = {
    "detects": nodata_recover_detects_config(5, 5, 4, 2),
    "items": [
        {
            "algorithms": warning_algorithms_config("gte", 5),
            "expression": "a",
            "functions": [],
            "name": _("SUM(重启次数)"),
            "no_data_config": NO_DATA_CONFIG,
            "query_configs": [
                {
                    "agg_condition": [
                        {"key": "job", "method": "eq", "value": ["kube-state-metrics"]},
                        {"condition": "and", "key": "namespace", "method": "neq", "value": ["bkmonitor-operator"]},
                        {"condition": "and", "key": "pod_name", "method": "neq", "value": [""]},
                        {"condition": "and", "key": "container", "method": "neq", "value": ["tke-monitor-agent"]},
                    ],
                    "agg_dimension": ["bcs_cluster_id", "namespace", "container_name", "pod_name"],
                    "agg_interval": 900,
                    "agg_method": "SUM",
                    "alias": "a",
                    "data_source_label": "bk_monitor",
                    "data_type_label": "time_series",
                    "functions": [{"id": "increase", "params": [{"id": "window", "value": "30m"}]}],
                    "metric_field": "kube_pod_container_status_restarts_total",
                    "metric_id": "bk_monitor..kube_pod_container_status_restarts_total",
                    # "name": _("重启次数"),
                    "result_table_id": "",
                    "unit": "",
                }
            ],
            "target": [[]],
        }
    ],
    "labels": [_("k8s_系统内置"), "kube-pod"],
    "name": _("[kube pod] pod近30分钟重启次数过多 KubePodCrashLooping"),
    "notice": DEFAULT_NOTICE,
}

# 因OOM重启，默认策略
terminated_reason_default_strategy = {
    "detects": nodata_recover_detects_config(5, 5, 1, 3),
    "items": [
        {
            "algorithms": remind_algorithms_config("gt", 0),
            "expression": "a",
            "functions": [],
            "name": "MAX(kube_pod_container_status_terminated_reason)",
            "no_data_config": NO_DATA_CONFIG,
            "query_configs": [
                {
                    "agg_condition": [
                        {"condition": "and", "key": "reason", "method": "eq", "value": ["OOMKilled"]},
                        {
                            "condition": "and",
                            "key": "namespace",
                            "method": "neq",
                            "value": ["", "bkmonitor-operator"],
                        },
                        {"condition": "and", "key": "pod_name", "method": "neq", "value": [""]},
                        {"condition": "and", "key": "container", "method": "neq", "value": ["tke-monitor-agent"]},
                    ],
                    "agg_dimension": ["bcs_cluster_id", "namespace", "pod_name"],
                    "agg_interval": 60,
                    "agg_method": "MAX",
                    "alias": "a",
                    "data_source_label": "bk_monitor",
                    "data_type_label": "time_series",
                    "functions": [{"id": "increase", "params": [{"id": "window", "value": "2m"}]}],
                    "metric_field": "kube_pod_container_status_terminated_reason",
                    "metric_id": "bk_monitor..kube_pod_container_status_terminated_reason",
                    # "name": "kube_pod_container_status_terminated_reason",
                    "result_table_id": "",
                    "unit": "",
                }
            ],
            "target": [[]],
        }
    ],
    "labels": [_("k8s_系统内置"), "kube-pod"],
    "name": _("[kube pod] pod 因OOM重启"),
    "notice": DEFAULT_NOTICE,
}


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--no_preview", action="store_true", help="是否开启预览")

    def handle(self, *args, **options):
        preview = not options["no_preview"]
        kube_state_metrics_analysis(preview)


class QueryConfigProcessor:
    def __init__(self, qc: QueryConfigModel):
        self.query_config = qc.__dict__

    def __getitem__(self, key):
        if key not in self.query_config:
            return self.query_config.get("config", {}).get(key)

        return self.query_config[key]

    @classmethod
    def sort_list(cls, li):
        if not li:
            return li

        def get_sort_key(item):
            if isinstance(item, dict):
                if "key" in item:
                    return item["key"]
                elif "id" in item:
                    return item["id"]
                else:
                    return len(str(dict))
            elif isinstance(item, str):
                return len(item)
            else:
                return item

        li = sorted(li, key=get_sort_key)
        return li

    @classmethod
    def handle_list(cls, d):
        """
        对列表进行处理
        """
        # 对列表进行排序，使得顺序一致
        d["agg_dimension"] = cls.sort_list(d["agg_dimension"])
        d["agg_condition"] = cls.sort_list(d["agg_condition"])
        d["functions"] = cls.sort_list(d["functions"])

        # 配置了聚合条件，页面如果有对策略修改，则会自动增加一个dimension_name的聚合条件，所以这里进行删除
        for condition in d["agg_condition"]:
            if condition.get("dimension_name"):
                condition.pop("dimension_name")

    def is_same_query_config(self, default_query_config):
        """
        判断是否与default_query_config默认策略相同
        """
        # 根据default_query_config的key从self中取值，组成新的query_config
        qc = {key: self[key] for key in default_query_config.keys()}
        # 对列表进行排序，使得顺序一致
        self.handle_list(qc)
        return qc == default_query_config


def kube_state_metrics_analysis(preview=True):
    """
    重启kube state metrics引起误告策略梳理
    预览模式下只打印将要处理的策略的相关信息。
    非预览模式下打印未处理的策略的相关信息。

    usage:
        python manage.py kube_state_analysis.py   # 预览模式
        python manage.py kube_state_analysis.py --no_preview # 非预览模式

    """
    print()
    if preview:
        print("预览模式，只打印将要处理的策略的相关信息")
    else:
        print("以下打印的是未处理的策略的相关信息")
    print("策略id、策略名称、业务ID、关联的查询配置ID列表:")

    restarts_total_default_query_config = restarts_total_default_strategy["items"][0]["query_configs"][0]
    terminated_reason_default_query_config = terminated_reason_default_strategy["items"][0]["query_configs"][0]
    promql_mapping = {
        RESTARTS_TOTAL_METRIC_FIELD: {
            "promql": RESTARTS_TOTAL_PROMQL,
            "default_query_configs": restarts_total_default_query_config,
        },
        TERMINATED_REASON_METRIC_FIELD: {
            "promql": TERMINATED_REASON_PROMQL,
            "default_query_configs": terminated_reason_default_query_config,
        },
    }

    # 对默认query_config中的列表进行预处理
    QueryConfigProcessor.handle_list(restarts_total_default_query_config)
    QueryConfigProcessor.handle_list(terminated_reason_default_query_config)

    query_configs = QueryConfigModel.objects.filter(
        Q(config__metric_field=RESTARTS_TOTAL_METRIC_FIELD) | Q(config__metric_field=TERMINATED_REASON_METRIC_FIELD)
    )

    strategy_ids = query_configs.values_list('strategy_id', flat=True).distinct()
    strategies = StrategyModel.objects.filter(id__in=strategy_ids)
    items = ItemModel.objects.filter(strategy_id__in=strategy_ids)

    # 构建映射关系
    query_configs_mapping: Dict[int, List[QueryConfigModel]] = defaultdict(list)
    items_mapping: Dict[int, List[ItemModel]] = defaultdict(list)
    for qc in query_configs:
        query_configs_mapping[qc.strategy_id].append(qc)
    for item in items:
        items_mapping[item.strategy_id].append(item)

    # 需要被更新的策略
    previewed_strategies_info = defaultdict(list)
    query_configs_to_update = []
    items_to_update = []

    # 获取到日期时间的时间戳
    now = arrow.now('Asia/Shanghai').timestamp
    time_delta = 1 * 60  # 1分钟

    for strategy in strategies:
        try:
            create_time = arrow.get(strategy.create_time).timestamp
            update_time = arrow.get(strategy.update_time).timestamp

            # 是否被更新过，创建时间和更新时间差值大于2秒，则认为被更新过
            is_updated = abs(create_time - update_time) > 2
            # 是否在最近被创建或者更新过
            is_recently_modified = now - create_time < time_delta or now - update_time < time_delta
            if is_recently_modified or is_updated:
                promql = None
                related_item_ids = set()  # 关联的监控项ID
                query_config_ids = []
                for qc in query_configs_mapping[strategy.id]:
                    default_qc = promql_mapping[qc.config.get("metric_field")]["default_query_configs"]

                    # 被更新过，且更新后与默认query_config配置不一致，则不处理
                    if (
                        not is_recently_modified
                        and is_updated
                        and not QueryConfigProcessor(qc).is_same_query_config(default_qc)
                    ):
                        query_config_ids.append(qc.id)
                        continue

                    # 开启预览模式，则不处理
                    if preview:
                        previewed_strategies_info[f"{strategy.id}、{strategy.name}、{strategy.bk_biz_id}"].append(qc.id)
                        continue

                    related_item_ids.add(qc.item_id)
                    promql = promql_mapping[qc.config.get("metric_field")]["promql"]
                    # 将bk_monitor..kube_pod_container_status_restarts_total替换为
                    # bk_monitor:kube_pod_container_status_restarts_total
                    metric_id = qc.metric_id.replace("..", ":")

                    # 更新QueryConfigModel
                    qc.data_source_label = "prometheus"
                    qc.metric_id = metric_id  # promql内容超过字段长度
                    qc.config = {
                        "promql": promql,
                        "agg_interval": qc.config.get("agg_interval", ""),
                        "functions": qc.config.get("functions", []),
                    }
                    query_configs_to_update.append(qc)

                # 不开启预览模式，则打印未处理的策略相关信息
                if not preview and not promql:
                    print(f"{strategy.id}、{strategy.name}、{strategy.bk_biz_id}、{query_config_ids}")
                    continue

                # 修改关联监控项的origin_sql字段
                for item in items_mapping[strategy.id]:
                    if item.id in related_item_ids:
                        item.origin_sql = promql
                        items_to_update.append(item)

            else:
                query_config_ids = [qc.id for qc in query_configs_mapping[strategy.id]]
                # 不开启预览模式，则打印未处理的策略相关信息
                if not preview:
                    print(f"{strategy.id}、{strategy.name}、{strategy.bk_biz_id}、{query_config_ids}")
        except Exception as e:
            print(f"ERROR: 处理[{strategy.id}][{strategy.name}]策略时发生错误， error: {e}")
            continue

    if preview:
        for key, value in previewed_strategies_info.items():
            print(f"{key}、{value}")
    else:
        # 批量更新QueryConfigModel和ItemModel
        QueryConfigModel.objects.bulk_update(
            query_configs_to_update, fields=["data_source_label", "metric_id", "config"]
        )
        ItemModel.objects.bulk_update(items_to_update, fields=["origin_sql"])

    print("\n执行结束\n")
