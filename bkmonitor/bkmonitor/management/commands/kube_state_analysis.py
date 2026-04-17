from collections import defaultdict

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

doc = """
    对“[kube pod] pod 因OOM重启”和“[kube pod] pod近30分钟重启次数过多”这两条策略进行修复

    脚本功能：
       1. 预览策略：打印需要进行修复的策略信息"策略id、策略名称、业务ID、关联的查询配置ID列表"
       2. 修改策略：执行修复策略操作，并打印没有进行修复的策略信息"策略id、策略名称、业务ID、关联的查询配置ID列表",以供人工处理。

    usage:
        python manage.py kube_state_analysis.py   # 预览模式
        python manage.py kube_state_analysis.py --no_preview # 非预览模式(修复策略)

    —————————————————————————————————————————————————————————————————————————————————
    需求背景：
        监控中内置了针对以下两个指标的告警策略：
            - kube_pod_container_status_restarts_total   策略名：[kube pod] pod 因OOM重启
            - kube_pod_container_status_terminated_reason  策略名：[kube pod] pod近30分钟重启次数过多
        但是这两个策略，配置的query_config(针对指标的查询配置)不够准确，存在误告的情况，需要进行修复处理。

    处理方案：
        - 修改数据库，将这两个内置策略的query_config内容替换为正确的promql查询语句。
        - 判断条件：
            - 未修改query_config，则对query_config进行替换。
        - 最后输出被修改过query_config的策略的相关信息，待人工处理。

    处理步骤：
        1. 在数据库中查询出这两个内置策略、及其对应的query_config(查询配置)、item_model(监控项配置)
        2. 判断这两个策略是否符合上述判断条件。
        3. 符合条件，则进行以下内容更新：
            - query_config.data_source_label = "prometheus"        # 数据源替换为prometheus
            - query_config.metric_id= query_config.metric_id.replace("..", ":")
            - query_config.config = {
                "promql": promql,                                  # 配置正确的promql查询语句
                "agg_interval": qc.config.get("agg_interval", ""), # 保留原有的聚合间隔
                "functions": qc.config.get("functions", []),       # 保留原有的处理函数
              }
            - item_model.origin_sql = promql # 监控项配置中的origin_sql替换为promql
        4. 如果不符合上述判断条件，则输出策略信息，待后续人工处理。

    """

# pod近30分钟重启次数过多，指标名
RESTARTS_TOTAL_METRIC_FIELD = "kube_pod_container_status_restarts_total"
# 因OOM重启，指标名
TERMINATED_REASON_METRIC_FIELD = "kube_pod_container_status_terminated_reason"

# pod近30分钟重启次数过多，promql
RESTARTS_TOTAL_PROMQL = (
    r"increase(sum by (pod_name, bcs_cluster_id, namespace, container_name)"
    r'(bkmonitor:kube_pod_container_status_restarts_total{job="kube-state-metrics",'
    r'pod_name!="",namespace!="bkmonitor-operator",container!="tke-monitor-agent"})[30m:])'
)
# 因OOM重启，promql
TERMINATED_REASON_PROMQL = (
    r"increase ((max by (bcs_cluster_id, namespace, pod_name) (bkmonitor:"
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
        print(kube_state_metrics_analysis.__doc__)
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
        print(self["strategy_id"], qc, "\n", default_query_config)
        print(qc == default_query_config)
        return qc == default_query_config


def kube_state_metrics_analysis(preview=True):
    """
    重启kube state metrics引起误告策略梳理
    预览模式下只打印将要处理的策略的相关信息。
    非预览模式下打印未处理的策略的相关信息。

    usage:
        python manage.py kube_state_analysis    # 预览模式
        python manage.py kube_state_analysis --no_preview # 非预览模式

    """
    print()
    if preview:
        print("预览模式，只打印将要处理的策略的相关信息")
    else:
        print("以下打印的是未处理的策略的相关信息")
    print("策略id、策略名称、业务ID、关联的查询配置ID列表:")

    # 处理模式
    handle_mode = not preview

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

    strategy_ids = query_configs.values_list("strategy_id", flat=True).distinct()
    strategies = StrategyModel.objects.filter(id__in=strategy_ids)
    items = ItemModel.objects.filter(strategy_id__in=strategy_ids)

    # 构建映射关系
    query_configs_mapping: dict[int, list[QueryConfigModel]] = defaultdict(list)
    items_mapping: dict[int, list[ItemModel]] = defaultdict(list)
    for qc in query_configs:
        query_configs_mapping[qc.strategy_id].append(qc)
    for item in items:
        items_mapping[item.strategy_id].append(item)

    # 预览需要被更新的策略
    previewed_strategies_info = defaultdict(list)
    query_configs_to_update = []
    items_to_update = []

    for strategy in strategies:
        try:
            promql = None
            related_item_ids = set()  # 关联的监控项ID
            not_handle_qc_ids = []  # 未处理的query_config ID
            for qc in query_configs_mapping[strategy.id]:
                default_qc = promql_mapping[qc.config.get("metric_field")]["default_query_configs"]

                # 有更改query_config，则不处理
                if not QueryConfigProcessor(qc).is_same_query_config(default_qc):
                    print(f"不处理{strategy.id}")
                    not_handle_qc_ids.append(qc.id)
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

            # 处理模式下，需要打印未处理的query_config的策略信息
            if handle_mode and not_handle_qc_ids:
                print(f"{strategy.id}、{strategy.name}、{strategy.bk_biz_id}、{not_handle_qc_ids}")

            # promql为空，无需修改origin_sql
            if not promql:
                continue

            # 修改关联监控项的origin_sql字段
            for item in items_mapping[strategy.id]:
                if item.id in related_item_ids:
                    item.origin_sql = promql
                    items_to_update.append(item)

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
