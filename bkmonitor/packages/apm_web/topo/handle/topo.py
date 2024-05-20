# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import itertools
import operator
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import List

from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

from apm_web.constants import (
    CalculationMethod,
    CategoryEnum,
    CustomServiceMatchType,
    TopoNodeKind,
)
from apm_web.handlers.component_handler import ComponentHandler
from apm_web.icon import get_icon
from apm_web.metrics import (
    TOPO_COMPONENT_METRIC,
    TOPO_LIST,
    TOPO_REMOTE_SERVICE_METRIC,
    TOPO_SERVICE_METRIC,
)
from apm_web.models import (
    Application,
    ApplicationCustomService,
    AppServiceRelation,
    LogServiceRelation,
)
from apm_web.utils import group_by
from bkmonitor.utils.thread_backend import ThreadPool
from constants.apm import OtlpKey, SpanKind
from core.drf_resource import api


@dataclass
class TopoNodeTip:
    id: str
    name: str
    value: str = ""
    original_value: any = 0


@dataclass
class TopoNode:
    id: str
    name: str
    icon: str
    kind: str
    category: str
    category_kind: str
    language: str
    menu: list = field(default_factory=list)
    size: int = 1
    converge: bool = False
    have_data: bool = False
    topo_level: str = ""
    stroke: str = ""
    language_icon: str = ""
    is_root_service: bool = False
    tips: List[TopoNodeTip] = field(default_factory=list)
    original_node: any = field(default_factory=list)
    from_service: str = ""


@dataclass
class TopoMenu:
    name: str
    url: str = ""
    target: str = "self"
    id: str = ""


class RelationKindEnum:
    SYNC = "sync"
    ASYNC = "async"

    @classmethod
    def get_label_by_key(cls, key: str):
        return {cls.ASYNC: _("异步"), cls.SYNC: _("同步")}


class TopoSizeCategory:
    REQUEST_COUNT = "request_count"
    DURATION = "avg_duration"

    @classmethod
    def get_label_by_key(cls, key: str):
        return {
            cls.REQUEST_COUNT: _("请求数"),
            cls.DURATION: _("耗时"),
        }.get(key, key)


class TopoSizeEnum:
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"

    DEFAULT_SIZE = 10

    _size_map = {
        "request_count": {
            SMALL: {
                "size": 20,
                "node_size": 1,
                "text": "0~200",
                "predicate": lambda x: x <= 200,
            },
            MEDIUM: {
                "size": 30,
                "node_size": 5,
                "text": "200~1k",
                "predicate": lambda x: x > 200 and x <= 1000,
            },
            LARGE: {
                "size": 40,
                "node_size": 10,
                "text": _("1k以上"),
                "predicate": lambda x: x > 1000,
            },
        },
        # ns
        "avg_duration": {
            SMALL: {
                "size": 20,
                "node_size": 1,
                "text": "0~200ms",
                "predicate": lambda x: x <= 1000 * 1000 * 200,
            },
            MEDIUM: {
                "size": 30,
                "node_size": 5,
                "text": "200ms~1s",
                "predicate": lambda x: x <= 1000 * 1000 * 1000,
            },
            LARGE: {
                "size": 40,
                "node_size": 10,
                "text": _("1s以上"),
                "predicate": lambda x: x > 1000 * 1000 * 1000,
            },
        },
    }

    @classmethod
    def get_size_by_value(cls, category: str, value: int):
        values = sorted(cls._size_map[category].values(), key=lambda x: x["size"])
        for size in values:
            if size["predicate"](value):
                return size["size"]
        return cls.DEFAULT_SIZE

    @classmethod
    def get_statistic_list(cls):
        return [
            {
                "id": key,
                "name": TopoSizeCategory.get_label_by_key(key),
                "data": [
                    {
                        "size": item["node_size"],
                        "name": item["text"],
                    }
                    for item in statistic.values()
                ],
            }
            for key, statistic in cls._size_map.items()
        ]


class TopoLevelEnum:
    MIDDLE = "middle"
    UPSTREAM = "upstream"
    DOWNSTREAM = "downstream"


class TopoLegendEnum:
    """
    拓扑图的图例
    """

    NORMAL = "normal"
    WARNING = "warning"
    ERROR = "error"
    NO_DATA = "no_data"

    _color_map = {
        NORMAL: "#2DCB56",
        WARNING: "#FF9C01",
        ERROR: "#EA3636",
        NO_DATA: "#DCDEE5",
    }

    _status_map = {
        NORMAL: {
            "name": _("正常"),
            "color": _color_map[NORMAL],
            "predicate": lambda x, y: x == 0 and y,
        },
        WARNING: {
            "name": _("错误率 < 10%"),
            "color": _color_map[WARNING],
            "predicate": lambda x, y: x <= 10 and y,
        },
        ERROR: {
            "name": _("错误率 >= 10%"),
            "color": _color_map[ERROR],
            "predicate": lambda x, y: x > 10 and y,
        },
        NO_DATA: {
            "name": _("无数据"),
            "color": _color_map[NO_DATA],
            "predicate": lambda x, y: not y,
        },
    }

    @classmethod
    def get_status_map_list(cls):
        return [
            {
                "name": status["name"],
                "color": status["color"],
            }
            for status in cls._status_map.values()
        ]

    @classmethod
    def get_color(cls, status):
        return cls._color_map.get(status, cls.NO_DATA)

    @classmethod
    def get_color_by_value(cls, error_rate_value, count_value):
        for status_info in cls._status_map.values():
            if status_info["predicate"](error_rate_value, count_value):
                return status_info["color"]
        return cls.get_color(cls.NO_DATA)


class TopoHandler:
    def __init__(self, application: Application, start_time, end_time):
        self.application = application
        self.start_time = start_time
        self.end_time = end_time

        query_instance_param = {
            "bk_biz_id": application.bk_biz_id,
            "app_name": application.app_name,
            "filters": {
                "instance_topo_kind": TopoNodeKind.SERVICE,
            },
            "fields": ["topo_node_key"],
        }

        service_components_metric_param = {
            "app": self.application,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "metric_clz": TOPO_COMPONENT_METRIC,
        }

        topo_remote_service_metric_param = topo_service_metric_param = {
            "application": self.application,
            "start_time": self.start_time,
            "end_time": self.end_time,
        }

        custom_services_param = {
            "app_name": self.application.app_name,
            "bk_biz_id": self.application.bk_biz_id,
            "match_type": CustomServiceMatchType.MANUAL,
        }

        pool = ThreadPool()
        original_nodes_res = pool.apply_async(
            api.apm_api.query_topo_node, kwds={"bk_biz_id": application.bk_biz_id, "app_name": application.app_name}
        )
        original_relations_res = pool.apply_async(
            api.apm_api.query_topo_relation, kwds={"bk_biz_id": application.bk_biz_id, "app_name": application.app_name}
        )
        original_instances_res = pool.apply_async(api.apm_api.query_instance, kwds=query_instance_param)
        service_components_metric_res = pool.apply_async(
            ComponentHandler.get_service_component_metrics, kwds=service_components_metric_param
        )
        topo_service_metric_res = pool.apply_async(TOPO_SERVICE_METRIC, kwds=topo_service_metric_param)
        topo_remote_service_metric_res = pool.apply_async(
            TOPO_REMOTE_SERVICE_METRIC, kwds=topo_remote_service_metric_param
        )
        custom_services_res = pool.apply_async(ApplicationCustomService.objects.filter, kwds=custom_services_param)
        pool.close()
        pool.join()

        # 获取数据
        self.original_nodes = original_nodes_res.get()
        self.original_relations = original_relations_res.get()
        self.original_instances = original_instances_res.get()
        if isinstance(self.original_instances, dict):
            self.original_instances = self.original_instances.get("data", [])
        else:
            self.original_instances = []

        # 获取服务指标
        self.service_metric = {
            **topo_service_metric_res.get(),
            **topo_remote_service_metric_res.get(),
        }
        # 获取服务下组件指标
        self.service_components_metric = service_components_metric_res.get()
        self.original_nodes_mapping = group_by(self.original_nodes, operator.itemgetter("topo_key"))

        self.custom_services = custom_services_res.get()

    def get_topo_view(
        self,
        category=None,
        service_name=None,
        keyword="",
        size_category=TopoSizeCategory.REQUEST_COUNT,
    ):
        """
        获取拓扑视图
        """

        origin_nodes = self.list_origin_nodes(category, service_name, keyword)
        nodes = [self.build_node_base_info(i) for i in origin_nodes]
        edges = self.process_edges(service_name)

        self.converge_fission(nodes, edges)
        self.process_node_size(nodes, size_category)
        self.process_node_color(nodes)
        self.process_tips(nodes)
        self.process_top_level(nodes, service_name)
        self.process_menu(nodes, service_name)
        self.process_root_service(nodes)

        # 服务过滤
        if service_name:
            tmp_edges = []
            nodes_in_edge = []
            for i in edges:
                if i["source"] == service_name:
                    tmp_edges.append(i)
                    nodes_in_edge.append(i["target"])
                elif i["target"] == service_name:
                    tmp_edges.append(i)
                    nodes_in_edge.append(i["source"])

            nodes = [i for i in nodes if i.id == service_name or i.id in nodes_in_edge]
            edges = tmp_edges

        # 关键字过滤
        if keyword:
            tmp_nodes = []
            match_keyword_nodes = []
            for i in nodes:
                if keyword in i.id:
                    tmp_nodes.append(i)
                    match_keyword_nodes.append(i.id)

            edges = [i for i in edges if i["source"] in match_keyword_nodes or i["target"] in match_keyword_nodes]
            nodes = tmp_nodes

        return {
            "nodes": [asdict(i) for i in nodes],
            "edges": edges,
            "legend_data": {
                "statusList": TopoLegendEnum.get_status_map_list(),
                "statistics": TopoSizeEnum.get_statistic_list(),
            },
            "filter_list": CategoryEnum.get_filter_fields(),
        }

    def converge_fission(self, nodes: List[TopoNode], edges):
        """
        1. 对于存储类节点 根据service进行归类
        """

        # 处理存储类节点
        component_nodes = [i for i in nodes if i.kind == TopoNodeKind.COMPONENT]
        db_name_mapping = group_by(component_nodes, operator.attrgetter("name"))

        not_db_nodes = [i for i in nodes if i.kind != TopoNodeKind.COMPONENT]

        node_db_mapping = {}

        for node in not_db_nodes:
            category_mapping = defaultdict(list)

            for r in edges:
                if r["target"] in db_name_mapping and r["source"] == node.id:
                    db_node = db_name_mapping[r["target"]][0]
                    new_node_name = f"{node.id}-{db_node.category_kind}"
                    key = (new_node_name, db_node.category, db_node.category_kind, node.id)
                    category_mapping[key].append(db_node)
                    r["target"] = key[0]

            node_db_mapping[node.id] = category_mapping

        for node_name, node_dbs in node_db_mapping.items():
            for converge, c_nodes in node_dbs.items():
                for c_node in c_nodes:
                    if c_node in nodes:
                        nodes.remove(c_node)

                fission_name = converge[0]
                category = converge[1]
                category_kind = converge[2]
                from_service = converge[3]

                nodes.append(
                    TopoNode(
                        # 消息队列类组件 也变成数据库了
                        id=fission_name,
                        name=fission_name,
                        kind=TopoNodeKind.COMPONENT,
                        category=category,
                        category_kind=category_kind,
                        language=category_kind,
                        icon=get_icon(category),
                        language_icon=get_icon(category_kind),
                        converge=True,
                        original_node=list(itertools.chain(*[i.original_node for i in c_nodes])),
                        from_service=from_service,
                    )
                )

    def list_origin_nodes(self, category=None, service_name=None, keyword=None):
        found_custom_service_names = [
            i["topo_key"] for i in self.original_nodes if i.get("extra_data").get("kind") == TopoNodeKind.REMOTE_SERVICE
        ]

        not_found_custom_service_nodes = []
        for custom_service in self.custom_services:
            if custom_service.name in found_custom_service_names:
                continue
            # 未被发现的自定义服务 -> 构造一个虚拟节点
            not_found_custom_service_nodes.append(
                {
                    # 命名需要符合api侧的发现规则
                    "topo_key": f"{custom_service.type}:{custom_service.name}",
                    "extra_data": {
                        "category": custom_service.type,
                        "kind": TopoNodeKind.REMOTE_SERVICE,
                        "predicate_value": None,
                        "service_language": None,
                        "instance": {},
                    },
                }
            )

        res = self.original_nodes + not_found_custom_service_nodes

        # 分类过滤
        if category:
            res = [i for i in res if i.get("extra_data", {}).get("category") == category]

        # # service_name过滤
        # if service_name:
        #     tmp_res = []
        #     for i in res:
        #         topo_key = i.get("topo_key")
        #         if topo_key == service_name:
        #             tmp_res.append(i)
        #             continue
        #
        #         has_relation = next(
        #             (
        #                 r
        #                 for r in self.original_relations
        #                 if (r["from_topo_key"], r["to_topo_key"])
        #                 in [(topo_key, service_name), (service_name, topo_key)]
        #             ),
        #             None,
        #         )
        #
        #         if has_relation:
        #             tmp_res.append(i)
        #
        #     res = tmp_res
        #
        # # keyword 过滤
        # if keyword:
        #     res = [i for i in res if keyword.lower() in i.id.lower()]
        return res

    def process_tips(self, nodes):
        instance_count_mapping = defaultdict(int)
        for instance in self.original_instances:
            instance_count_mapping[instance["topo_node_key"]] += 1

        for node in nodes:
            node_metric_map = self.get_node_metric(node)
            # 保证指标顺序request_count、avg_duration、error_count、error_rate、instance_count
            node_metric = [
                node_metric_map[metric]
                for metric in [
                    CalculationMethod.REQUEST_COUNT,
                    CalculationMethod.AVG_DURATION,
                    CalculationMethod.ERROR_COUNT,
                    CalculationMethod.ERROR_RATE,
                ]
                if metric in node_metric_map
            ]
            if not node_metric:
                node_metric = [
                    asdict(TopoNodeTip(id=CalculationMethod.REQUEST_COUNT, name=_("请求数量"), value="--")),
                    asdict(TopoNodeTip(id=CalculationMethod.AVG_DURATION, name=_("平均耗时"), value="--")),
                    asdict(TopoNodeTip(id=CalculationMethod.ERROR_RATE, name=_("错误率"), value="--")),
                ]

            # 对于service类型 instance会通过api侧发现
            # 对于component类型 则通过调用关系间接发现
            if node.kind == TopoNodeKind.SERVICE:
                # 对于service类型
                node_metric.append(
                    asdict(
                        TopoNodeTip(
                            id=CalculationMethod.INSTANCE_COUNT,
                            name=_("实例数量"),
                            value=instance_count_mapping.get(node.name, 0),
                            original_value=instance_count_mapping.get(node.name, 0),
                        )
                    )
                )
            elif node.kind == TopoNodeKind.COMPONENT:
                node_metric.append(
                    asdict(
                        TopoNodeTip(
                            id=CalculationMethod.INSTANCE_COUNT,
                            name=_("实例数量"),
                            value=str(len(node.original_node)),
                            original_value=len(node.original_node),
                        )
                    )
                )

            node.tips = node_metric

    def get_simple_node_metric(self, node: TopoNode):
        kind = node.kind

        if kind == TopoNodeKind.SERVICE:
            # 服务类型不区分主被调

            origin_node = node.original_node[0]
            if origin_node.get("topo_key") in self.service_metric:
                return self.service_metric[origin_node["topo_key"]]

            return {}
        elif kind == TopoNodeKind.REMOTE_SERVICE:
            # 自定义服务被调方不上报span 显示为主调方调用指标值
            origin_node = node.original_node[0]
            topo_key = origin_node.get("topo_key", "").split(":")[-1]
            return self.service_metric.get("|".join([topo_key, str(SpanKind.SPAN_KIND_CLIENT)]), {})

        else:
            # 组件类指标根据组件类型进行获取
            return self.service_components_metric.get(node.from_service, {}).get(node.category_kind, {})

    def get_converge_node_metric(self, node: TopoNode, fission_mapping):
        """多节点指标获取"""
        where = []

        source = fission_mapping[node.id]

        for index, origin_node in enumerate(node.original_node):
            tmp_where = []

            for key_index, key in enumerate(origin_node.get("extra_data", {}).get("instance", {}).keys()):
                tmp_where.append(
                    {
                        "condition": "or" if index != 0 and key_index == 0 else "and",
                        "key": OtlpKey.get_metric_dimension_key(key),
                        "method": "eq",
                        "value": [origin_node.get("extra_data", {}).get("instance", {}).get(key) or ""],
                    }
                )

            if source.category == CategoryEnum.HTTP:
                tmp_where.append({"condition": "and", "key": "service_name", "method": "eq", "value": [source.id]})

            where += tmp_where

        component_metric = TOPO_COMPONENT_METRIC(
            self.application, start_time=self.start_time, end_time=self.end_time, where=where, group_key=[]
        )

        if component_metric:
            return component_metric[list(component_metric.keys())[0]]

        return {}

    def get_node_metric(self, node: TopoNode):
        return self.get_simple_node_metric(node)

    def topo_level(self, node, service_name):
        if not service_name:
            return TopoLevelEnum.MIDDLE
        if node.id == service_name:
            return TopoLevelEnum.MIDDLE
        for relation in self.original_relations:
            if (relation["from_topo_key"], relation["to_topo_key"]) == (node.id, service_name):
                return TopoLevelEnum.UPSTREAM
            if (relation["from_topo_key"], relation["to_topo_key"]) == (service_name, node.id):
                return TopoLevelEnum.DOWNSTREAM
        return TopoLevelEnum.MIDDLE

    def service_match(self, topo_key: str, match_service_name):
        if not match_service_name:
            return True
        if topo_key == match_service_name:
            return True
        for relation in self.original_relations:
            if (relation["from_topo_key"], relation["to_topo_key"]) in [
                (topo_key, match_service_name),
                (match_service_name, topo_key),
            ]:
                return True
        return False

    def build_node_base_info(self, node):
        """构建节点基础信息"""

        extra_data = node.get("extra_data", {})
        category = extra_data.get("category")
        icon = get_icon(category)

        kind = extra_data.get("kind")

        if kind == TopoNodeKind.COMPONENT:
            language = extra_data.get("predicate_value")
            language_icon = get_icon(language)

        else:
            language = extra_data.get("service_language")
            language_icon = get_icon(language)

        return TopoNode(
            id=node["topo_key"],
            name=node["topo_key"],
            kind=kind,
            category=category,
            category_kind=extra_data.get("predicate_value"),
            language=language,
            icon=icon,
            language_icon=language_icon,
            converge=False,
            original_node=[node],
            from_service=node["topo_key"],
        )

    def get_metric_origin_value(self, node, metric_id):
        metric = self.get_node_metric(node)
        return metric.get(metric_id, {}).get("original_value", 0)

    def process_node_size(self, nodes, size_category):
        """根据节点指标值计算节点显示大小"""

        for node in nodes:
            node_metric_value = self.get_metric_origin_value(node, size_category)
            node.size = TopoSizeEnum.get_size_by_value(size_category, node_metric_value)

    def process_node_color(self, nodes):
        """根据节点指标值获取节点颜色"""
        for node in nodes:
            request_count = self.get_metric_origin_value(node, CalculationMethod.REQUEST_COUNT)
            node.stroke = TopoLegendEnum.get_color_by_value(
                self.get_metric_origin_value(node, CalculationMethod.ERROR_RATE),
                request_count,
            )
            node.have_data = bool(request_count)

    def process_node_category(self, nodes, category=None):
        if not category:
            return nodes
        return [node for node in nodes if node["category"] == category]

    def process_top_level(self, nodes, service_name=None):
        for node in nodes:
            node.topo_level = self.topo_level(node, service_name)

    def get_service_url(self, node, dashboard=None):
        base = (
            f"/service/?filter-app_name={self.application.app_name}"
            f"&filter-service_name={node.id}"
            f"&filter-category={node.category}"
            f"&filter-kind={node.kind}"
            f"&filter-predicate_value={node.category_kind}"
        )

        if not dashboard:
            return base
        return f"{base}&dashboardId={dashboard}"

    def get_app_url(self, bk_biz_id, app_name):
        return f"/?bizId={bk_biz_id}#/apm/application/?filter-app_name={app_name}"

    def process_menu(self, nodes: List[TopoNode], service_name=None):
        log_service_names = LogServiceRelation.objects.filter(
            service_name__in=[i.name for i in nodes],
            bk_biz_id=self.application.bk_biz_id,
            app_name=self.application.app_name,
        ).values_list("service_name", flat=True)

        app_service_mapping = group_by(
            AppServiceRelation.objects.filter(
                service_name__in=[i.name for i in nodes],
                bk_biz_id=self.application.bk_biz_id,
                app_name=self.application.app_name,
            ),
            operator.attrgetter("service_name"),
        )

        for node in nodes:
            node.menu = [
                TopoMenu(name=_("查看告警事件"), url=f"/?bizId={self.application.bk_biz_id}#/event-center", target="blank"),
                TopoMenu(name=_("查看相关指标"), url=f"/?bizId={self.application.bk_biz_id}#/data-retrieval", target="blank"),
            ]

            if not service_name:
                node.menu += [
                    TopoMenu(name=_("展开服务"), id="down"),
                    TopoMenu(name=_("查看服务"), url=self.get_service_url(node)),
                ]

            if node.id in log_service_names:
                node.menu.append(
                    TopoMenu(
                        name=_("查看日志"),
                        url=self.get_service_url(node, "service-default-log"),
                    )
                )

            if app_service_mapping.get(node.id):
                node.menu.append(
                    TopoMenu(
                        name=_("查看关联应用"),
                        target="blank",
                        url=self.get_app_url(
                            app_service_mapping[node.id][0].relate_bk_biz_id,
                            app_service_mapping[node.id][0].relate_app_name,
                        ),
                    )
                )

    def process_keyword(self, nodes, keyword):
        if not keyword:
            return nodes
        return [node for node in nodes if node["name"].lower().find(keyword.lower()) != -1]

    def process_root_service(self, nodes):
        root_endpoints = api.apm_api.query_root_endpoint(
            {"bk_biz_id": self.application.bk_biz_id, "app_name": self.application.app_name}
        )
        root_services = {root_endpoint["service_name"] for root_endpoint in root_endpoints}
        for node in nodes:
            node.is_root_service = node.id in root_services

    def process_edge_service_name(self, edges, service_name):
        if not service_name:
            return edges
        return [edge for edge in edges if edge["source"] == service_name or edge["target"] == service_name]

    def process_edges(self, service_name=None):
        """生成拓扑节点边"""
        res = []
        keys = set()
        for item in self.original_relations:
            source = item["from_topo_key"]
            target = item["to_topo_key"]
            if (source, target) in keys or (target, source) in keys:
                continue

            double = next(
                (
                    i
                    for i in self.original_relations
                    if item != i and i["to_topo_key"] == source and i["from_topo_key"] == target
                ),
                None,
            )
            if double:
                res.append(
                    {
                        "source": source,
                        "target": target,
                        "source_to_target_kind": item["kind"],
                        "target_to_source_kind": double["kind"],
                        "type": "complex",
                    }
                )
            else:
                res.append(
                    {
                        "source": source,
                        "target": target,
                        "source_to_target_kind": item["kind"],
                        "target_to_source_kind": "",
                        "type": "singular",
                    }
                )

            keys.add((source, target))
            keys.add((target, source))

        # # service_name 过滤
        # if service_name:
        #     res = [i for i in res if i["source"] == service_name or i["target"] == service_name]

        return res

    @cached_property
    def node_map(self):
        return {node["topo_key"]: node for node in self.original_nodes}

    def build_relation_list(self, relation):
        node_map = self.node_map
        from_node = node_map.get(relation["from_topo_key"])
        to_node = node_map.get(relation["to_topo_key"])
        if not from_node or not to_node:
            return []
        if to_node["extra_data"]["kind"] == "component":
            kind = (
                SpanKind.SPAN_KIND_CLIENT if relation["kind"] == RelationKindEnum.SYNC else SpanKind.SPAN_KIND_PRODUCER
            )
            return [
                {
                    "relation": [
                        {
                            "label": from_node["extra_data"]["service_language"],
                            "name": relation["from_topo_key"],
                        },
                        {
                            "label": to_node["extra_data"]["predicate_value"],
                            "name": relation["to_topo_key"],
                        },
                    ],
                    "service_name": relation["from_topo_key"],
                    "kind_id": kind,
                    "kind": SpanKind.get_label_by_key(kind),
                    "category": to_node["extra_data"]["category"],
                }
            ]

        if from_node["extra_data"]["kind"] == "component":
            kind = SpanKind.SPAN_KIND_CONSUMER
            return [
                {
                    "relation": [
                        {
                            "label": from_node["extra_data"]["service_language"],
                            "name": relation["from_topo_key"],
                        },
                        {
                            "label": to_node["extra_data"]["predicate_value"],
                            "name": relation["to_topo_key"],
                        },
                    ],
                    "service_name": relation["to_topo_key"],
                    "kind": SpanKind.get_label_by_key(kind),
                    "kind_id": kind,
                    "category": to_node["extra_data"]["category"],
                }
            ]
        kind_from = (
            SpanKind.SPAN_KIND_CLIENT if relation["kind"] == RelationKindEnum.SYNC else SpanKind.SPAN_KIND_PRODUCER
        )
        kind_to = (
            SpanKind.SPAN_KIND_SERVER if relation["kind"] == RelationKindEnum.SYNC else SpanKind.SPAN_KIND_CONSUMER
        )
        return [
            {
                "relation": [
                    {
                        "label": from_node["extra_data"]["service_language"],
                        "name": relation["from_topo_key"],
                    },
                    {
                        "label": to_node["extra_data"]["service_language"],
                        "name": relation["to_topo_key"],
                    },
                ],
                "service_name": relation["from_topo_key"],
                "kind": SpanKind.get_label_by_key(kind_from),
                "kind_id": kind_from,
                "category": from_node["extra_data"]["category"],
            },
            {
                "relation": [
                    {
                        "label": from_node["extra_data"]["service_language"],
                        "name": relation["from_topo_key"],
                    },
                    {
                        "label": to_node["extra_data"]["service_language"],
                        "name": relation["to_topo_key"],
                    },
                ],
                "service_name": relation["to_topo_key"],
                "kind": SpanKind.get_label_by_key(kind_to),
                "kind_id": kind_to,
                "category": to_node["extra_data"]["category"],
            },
        ]

    def get_topo_list(self, category=None):
        metric_data = TOPO_LIST(self.application, start_time=self.start_time, end_time=self.end_time)
        res = []

        for relation in self.original_relations:
            for row_data in self.build_relation_list(relation):
                if category:
                    if row_data["category"] != category:
                        continue

                row_data.update(
                    {
                        "app_name": self.application.app_name,
                        **metric_data.get(f"{row_data['service_name']}|{row_data['kind_id']}", {}),
                    }
                )
                res.append(row_data)

        return res
