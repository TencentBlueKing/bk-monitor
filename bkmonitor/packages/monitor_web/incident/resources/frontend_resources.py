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
import time
from collections import Counter, defaultdict
from typing import Any, Dict, List

import arrow
from django.conf import settings
from django.utils import timezone
from django.utils.translation import ugettext as _

from bkmonitor.aiops.alert.utils import AIOPSManager
from bkmonitor.aiops.incident.models import (
    IncidentGraphEdgeType,
    IncidentGraphEntity,
    IncidentSnapshot,
)
from bkmonitor.aiops.incident.operation import IncidentOperationManager
from bkmonitor.documents.alert import AlertDocument
from bkmonitor.documents.base import BulkActionType
from bkmonitor.documents.incident import (
    MAX_INCIDENT_ALERT_SIZE,
    IncidentDocument,
    IncidentOperationDocument,
    IncidentSnapshotDocument,
)
from bkmonitor.utils.request import get_request_username
from bkmonitor.views import serializers
from constants.alert import EVENT_STATUS_DICT, EventStatus
from constants.incident import (
    IncidentAlertAggregateDimension,
    IncidentOperationClass,
    IncidentOperationType,
    IncidentStatus,
)
from core.drf_resource import api, resource
from core.drf_resource.base import Resource
from fta_web.alert.handlers.incident import (
    IncidentAlertQueryHandler,
    IncidentQueryHandler,
)
from fta_web.alert.resources import BaseTopNResource
from fta_web.alert.serializers import AlertSearchSerializer
from fta_web.models.alert import SearchHistory, SearchType
from monitor_web.incident.serializers import IncidentSearchSerializer


class IncidentBaseResource(Resource):
    """
    故障相关资源基类
    """

    def get_snapshot_alerts(self, snapshot: IncidentSnapshot, **kwargs) -> List[Dict]:
        alert_ids = snapshot.get_related_alert_ids()
        if "conditions" in kwargs:
            kwargs["conditions"].append({'key': 'id', 'value': alert_ids, 'method': 'eq'})
        else:
            kwargs["conditions"] = [{'key': 'id', 'value': alert_ids, 'method': 'eq'}]
        if "bk_biz_ids" not in kwargs:
            kwargs["bk_biz_ids"] = list(
                map(lambda x: int(x), snapshot.incident_snapshot_content['rca_summary']['bk_biz_ids'])
            )
        alerts = IncidentAlertQueryHandler(**kwargs).search()["alerts"]
        return alerts

    def get_item_by_chain_key(self, data: Dict, chain_key: str) -> Any:
        keys = chain_key.split(".")
        for key in keys:
            if not data or not isinstance(data, dict):
                return None

            data = data.get(key)
        return data

    def expand_children_dict_as_list(self, aggregate_results: Dict) -> Dict:
        for agg_value in aggregate_results.values():
            if isinstance(agg_value["children"], dict):
                if agg_value["children"]:
                    agg_value["children"] = self.expand_children_dict_as_list(agg_value["children"])
                else:
                    agg_value["children"] = []

        return list(aggregate_results.values())

    def generate_nodes_by_entites(
        self, incident: IncidentDocument, snapshot: IncidentSnapshot, entities: List[IncidentGraphEntity]
    ) -> List[Dict]:
        """根据图谱实体生成拓扑图节点

        :param entites: 实体列表
        :return: 拓扑图节点列表
        """
        nodes = []

        for entity in entities:
            alert_ids = snapshot.entity_alerts(entity.entity_id)
            bk_biz_id = entity.bk_biz_id or snapshot.bk_biz_id
            bk_biz_name = resource.cc.get_app_by_id(bk_biz_id).name if bk_biz_id else bk_biz_id
            nodes.append(
                {
                    "id": entity.entity_id,
                    "comboId": str(entity.rank.rank_category.category_id),
                    "subComboId": entity.logic_key(),
                    "logic_content": entity.logic_content(),
                    "aggregated_nodes": self.generate_nodes_by_entites(incident, snapshot, entity.aggregated_entities),
                    "entity": {
                        key: value for key, value in entity.to_src_dict().items() if key != "aggregated_entities"
                    },
                    "total_count": len(entity.aggregated_entities) + 1,
                    "anomaly_count": self.get_anomaly_entity_count(entity),
                    "is_feedback_root": getattr(incident.feedback, "incident_root", None) == entity.entity_id,
                    "is_on_alert": entity.is_on_alert,
                    "alert_all_recorved": all(
                        map(
                            lambda alert_id: snapshot.alert_entity_mapping[alert_id].alert_status
                            in (EventStatus.RECOVERED, EventStatus.CLOSED),
                            alert_ids,
                        )
                    )
                    if alert_ids
                    else False,
                    "bk_biz_id": bk_biz_id,
                    "bk_biz_name": bk_biz_name,
                    "alert_ids": alert_ids,
                    "alert_display": (
                        {
                            "alert_id": alert_ids[0],
                            "alert_name": AlertDocument.get(alert_ids[0]).alert_name,
                        }
                        if len(alert_ids) > 0
                        else {}
                    ),
                }
            )

        return nodes

    def get_anomaly_entity_count(self, entity: IncidentGraphEntity) -> int:
        """获取实体（包含聚合在这个实体的其他实体）的异常数量

        :param entity: 图谱实体
        :return: 异常实体数量
        """
        anomaly_count = 1 if entity.is_anomaly else 0
        for aggregated_entity in entity.aggregated_entities:
            if aggregated_entity.is_anomaly:
                anomaly_count += 1

        return anomaly_count

    def update_incident_document(self, incident_info: Dict, update_time: arrow.Arrow) -> None:
        """更新故障记录，并记录故障流转

        :param incident_info: 需要更新的信息
        :param update_time: 更新时间
        """
        incident_document = IncidentDocument.get(incident_info["id"], fetch_remote=False)
        for incident_key, incident_value in incident_info.items():
            if (
                hasattr(incident_document, incident_key)
                and (getattr(incident_document, incident_key) or incident_key == "incident_reason")
                and (incident_value or incident_key == "incident_reason")
                and str(getattr(incident_document, incident_key)) != str(incident_value)
            ):
                if incident_key == "status":
                    if incident_value == IncidentStatus.CLOSED.value:
                        IncidentOperationManager.record_close_incident(
                            incident_info["incident_id"], update_time.timestamp
                        )
                    elif incident_value == IncidentStatus.RECOVERING.value:
                        incident_document.end_time = int(time.time())
                elif incident_key == "feedback":
                    IncidentOperationManager.record_feedback_incident(
                        incident_info["incident_id"],
                        update_time.timestamp,
                        incident_info["feedback"]["incident_root"],
                        incident_info["feedback"]["content"],
                    )
                else:
                    # 部分属性的修改不需要记录
                    if incident_key not in ["updated_at"]:
                        IncidentOperationManager.record_user_update_incident(
                            incident_info["incident_id"],
                            update_time.timestamp,
                            incident_key,
                            getattr(incident_document, incident_key),
                            incident_value,
                        )
                setattr(incident_document, incident_key, incident_value)

        incident_document.update_time = update_time.timestamp
        IncidentDocument.bulk_create([incident_document], action=BulkActionType.UPDATE)


class IncidentListResource(IncidentBaseResource):
    """
    故障列表
    """

    def __init__(self):
        super(IncidentListResource, self).__init__()

    class RequestSerializer(IncidentSearchSerializer):
        level = serializers.ListField(required=False, label="故障级别", default=[])
        assignee = serializers.ListField(required=False, label="故障负责人", default=[])
        handler = serializers.ListField(required=False, label="故障处理人", default=[])
        record_history = serializers.BooleanField(label="是否保存收藏历史", default=False)
        page = serializers.IntegerField(required=False, label="页码")
        page_size = serializers.IntegerField(required=False, label="每页条数")

    def perform_request(self, validated_request_data: Dict) -> Dict:
        record_history = validated_request_data.pop("record_history")

        handler = IncidentQueryHandler(**validated_request_data)

        with SearchHistory.record(
            SearchType.INCIDENT,
            validated_request_data,
            enabled=record_history and validated_request_data.get("query_string"),
        ):
            result = handler.search(show_overview=False, show_aggs=True)

        return result


class ExportIncidentResource(Resource):
    """
    导出故障数据
    """

    class RequestSerializer(IncidentSearchSerializer):
        level = serializers.ListField(required=False, label="故障级别", default=[])
        assignee = serializers.ListField(required=False, label="故障负责人", default=[])
        handler = serializers.ListField(required=False, label="故障处理人", default=[])

    def perform_request(self, validated_request_data):
        handler = IncidentQueryHandler(**validated_request_data)
        incidents = handler.export()
        return resource.export_import.export_package(list_data=incidents)


class IncidentOverviewResource(IncidentBaseResource):
    """
    故障汇总统计
    """

    def __init__(self):
        super(IncidentOverviewResource, self).__init__()

    RequestSerializer = IncidentSearchSerializer

    def perform_request(self, validated_request_data: Dict) -> Dict:
        handler = IncidentQueryHandler(**validated_request_data)
        results = handler.search(show_overview=True, show_aggs=False)
        results["enable_aiops_incident"] = bool(
            set(settings.AIOPS_INCIDENT_BIZ_WHITE_LIST) & set(validated_request_data.get("bk_biz_ids", []))
        )
        return results


class IncidentTopNResource(BaseTopNResource):
    handler_cls = IncidentQueryHandler

    class RequestSerializer(IncidentSearchSerializer, BaseTopNResource.RequestSerializer):
        pass


class IncidentValidateQueryStringResource(Resource):
    """
    校验 query_string 是否合法
    """

    class RequestSerializer(serializers.Serializer):
        query_string = serializers.CharField(label="查询字符串", allow_blank=True)

    def perform_request(self, validated_request_data):
        if not validated_request_data["query_string"]:
            return ""

        return IncidentQueryHandler.query_transformer.transform_query_string(
            query_string=validated_request_data["query_string"]
        )


class IncidentDetailResource(IncidentBaseResource):
    """
    故障详情
    """

    def __init__(self):
        super(IncidentDetailResource, self).__init__()

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(required=True, label="故障ID")
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def perform_request(self, validated_request_data: Dict) -> Dict:
        id = validated_request_data["id"]

        incident = IncidentDocument.get(id).to_dict()
        incident = IncidentQueryHandler.handle_hit(incident)
        incident["snapshots"] = [item.to_dict() for item in self.get_incident_snapshots(incident)]
        incident["bk_biz_name"] = resource.cc.get_app_by_id(incident["bk_biz_id"]).name
        if len(incident["snapshots"]) > 0:
            incident["current_snapshot"] = incident["snapshots"][-1]
            incident["alert_count"] = len(incident["snapshot"]["alerts"])

        return incident

    def get_incident_snapshots(self, incident: IncidentDocument) -> Dict:
        """根据故障详情获取故障快照

        :param incident: 故障详情
        :return: 故障快照信息
        """
        snapshots = IncidentSnapshotDocument.list_by_incident_id(incident["incident_id"])
        for snapshot in snapshots:
            snapshot["bk_biz_ids"] = [
                {
                    "bk_biz_id": bk_biz_id,
                    "bk_biz_name": resource.cc.get_app_by_id(bk_biz_id).name,
                }
                for bk_biz_id in snapshot["bk_biz_ids"]
            ]
        return snapshots


class IncidentTopologyResource(IncidentBaseResource):
    """
    故障拓扑图
    """

    def __init__(self):
        super(IncidentTopologyResource, self).__init__()

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(required=True, label="故障ID")
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        auto_aggregate = serializers.BooleanField(required=False, default=False, label="是否自动聚合")
        aggregate_config = serializers.JSONField(required=False, default=dict, label="聚合配置")
        limit = serializers.IntegerField(required=False, label="拓扑图数量", default=None)
        start_time = serializers.IntegerField(required=False, label="开始时间", default=None)
        end_time = serializers.IntegerField(required=False, label="结束时间", default=None)
        only_diff = serializers.BooleanField(required=False, default=False, label="是否只展示diff数据")

    def perform_request(self, validated_request_data: Dict) -> Dict:
        incident = IncidentDocument.get(validated_request_data.pop("id"))
        limit = validated_request_data.get("limit")
        start_time = validated_request_data.get("start_time")
        end_time = validated_request_data.get("end_time")

        if not limit and not start_time:
            incident_snapshots = [incident.snapshot]
        else:
            incident_snapshots = IncidentSnapshotDocument.list_by_incident_id(
                incident.incident_id,
                start_time,
                end_time,
                limit,
            )
            incident_snapshots = sorted(incident_snapshots, key=lambda x: x["create_time"])

        # 根据实体加入的时间生成实体ID到时间的映射
        entities_orders = self.generate_entities_orders(incident_snapshots)

        snapshots = {}
        for incident_snapshot in incident_snapshots:
            snapshot = IncidentSnapshot(incident_snapshot.content.to_dict())
            if validated_request_data["auto_aggregate"]:
                snapshot.aggregate_graph(incident, entities_orders=entities_orders)
            elif validated_request_data["aggregate_config"]:
                snapshot.aggregate_graph(
                    incident, validated_request_data["aggregate_config"], entities_orders=entities_orders
                )
            snapshots[incident_snapshot.id] = snapshot

        latest_snapshot_content = self.generate_topology_data_from_snapshot(
            incident, snapshots[incident_snapshots[-1].id]
        )
        last_snapshot_content = None
        topologies_data = []
        complete_topologies = {"nodes": {}, "edges": {}}
        for incident_snapshot in incident_snapshots:
            snapshot = snapshots[incident_snapshot.id]
            if validated_request_data["only_diff"]:
                last_snapshot_content, topo_data = self.generate_topology_diff_from_snapshot(
                    incident,
                    snapshot,
                    last_snapshot_content,
                    complete_topologies,
                )
            else:
                topo_data = self.generate_topology_data_from_snapshot(incident, snapshot)
            topologies_data.append(
                {
                    "incident_id": incident_snapshot.incident_id,
                    "fpp_snapshot_id": incident_snapshot.fpp_snapshot_id,
                    "create_time": incident_snapshot.create_time,
                    "content": topo_data,
                }
            )

        return {
            "latest": latest_snapshot_content,
            "diff" if validated_request_data["only_diff"] else "full": topologies_data,
            "complete": {
                "nodes": list(complete_topologies["nodes"].values()),
                "edges": list(complete_topologies["edges"].values()),
            },
        }

    def generate_entities_orders(self, incident_snapshots: List[IncidentSnapshotDocument]) -> Dict:
        entities_orders = {}
        for incident_snapshot in incident_snapshots:
            for entity in incident_snapshot.content["incident_propagation_graph"]["entities"]:
                if entity["entity_id"] not in entities_orders:
                    entities_orders[entity["entity_id"]] = incident_snapshot.create_time
        return entities_orders

    def generate_topology_diff_from_snapshot(
        self,
        incident: IncidentDocument,
        snapshot: IncidentSnapshot,
        last_snapshot_content: Dict,
        complete_topologies: Dict,
    ) -> Dict:
        new_nodes = []
        new_edges = []
        current = self.generate_topology_data_from_snapshot(incident, snapshot)
        last_nodes = {node["id"]: node for node in last_snapshot_content["nodes"]} if last_snapshot_content else {}
        last_edges = (
            {(edge["source"], edge["target"], edge["edge_type"]): edge for edge in last_snapshot_content["edges"]}
            if last_snapshot_content
            else {}
        )
        for node in current["nodes"]:
            if node["id"] not in last_nodes:
                new_nodes.append(node)
                complete_topologies["nodes"][node["id"]] = node
            elif self.check_node_diff(node, last_nodes[node["id"]]):
                new_nodes.append(node)
                complete_topologies["nodes"][node["id"]] = node
            elif node["id"] not in complete_topologies["nodes"]:
                complete_topologies["nodes"][node["id"]] = node

        for edge in current["edges"]:
            edge_id = (edge["source"], edge["target"], edge["edge_type"])
            if edge_id not in last_edges:
                new_edges.append(edge)
                complete_topologies["edges"][edge_id] = edge
            elif self.check_edge_diff(edge, last_edges[edge_id]):
                new_edges.append(edge)
                complete_topologies["edges"][edge_id] = edge
            elif edge_id not in complete_topologies["edges"]:
                complete_topologies["edges"][edge_id] = edge

        return current, {
            "nodes": new_nodes,
            "edges": new_edges,
        }

    def check_node_diff(self, current_node: dict, last_node: dict):
        """判断节点是否发生变化."""
        for node_key in ["is_on_alert", "is_feedback_root", "anomaly_count", "alert_ids", "aggregated_nodes"]:
            if current_node[node_key] != last_node[node_key]:
                return True

        return False

    def check_edge_diff(self, current_edge: dict, last_edge: dict):
        """判断节点是否发生变化."""
        for edge_key in [
            "count",
            "aggregated_edges",
            "anomaly_score",
            "is_anomaly",
            "source_is_anomaly",
            "target_is_anomaly",
            "source_is_on_alert",
            "target_is_on_alert",
        ]:
            if current_edge[edge_key] != last_edge[edge_key]:
                return True

        return False

    def generate_topology_data_from_snapshot(self, incident: IncidentDocument, snapshot: IncidentSnapshot) -> Dict:
        """根据快照内容生成拓扑图数据

        :param snapshot: 快照内容
        :return: 拓扑图数据
        """
        nodes = self.generate_nodes_by_entites(
            incident,
            snapshot,
            snapshot.incident_graph_entities.values(),
        )

        node_categories = [node["entity"]["rank"]["rank_category"]["category_id"] for node in nodes]
        sub_combos = [
            {
                "id": node["subComboId"],
                "label": node["subComboId"],
                "dataType": node["subComboId"],
                "comboId": str(node["entity"]["rank"]["rank_category"]["category_id"]),
                "dimensions": node["logic_content"],
            }
            for node in nodes
            if node["subComboId"]
        ]
        topology_data = {
            "nodes": nodes,
            "edges": [edge.to_src_dict() for edge in snapshot.incident_graph_edges.values()],
            "sub_combos": list({item["id"]: item for item in sub_combos}.values()),
            "combos": [
                {
                    "id": str(category.category_id),
                    "label": category.category_alias,
                    "dataType": category.category_name,
                }
                for category in snapshot.incident_graph_categories.values()
                if category.category_id in node_categories
            ],
        }
        return topology_data

    def get_incident_snapshots(self, incident: IncidentDocument) -> Dict:
        """根据故障详情获取故障快照

        :param incident: 故障详情
        :return: 故障快照信息
        """
        snapshots = IncidentSnapshotDocument.list_by_incident_id(incident["incident_id"])
        return snapshots


class IncidentTopologyMenuResource(IncidentBaseResource):
    """
    故障拓扑图目录
    """

    def __init__(self):
        super(IncidentTopologyMenuResource, self).__init__()

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(required=True, label="故障ID")
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def perform_request(self, validated_request_data: Dict) -> Dict:
        incident = IncidentDocument.get(validated_request_data.pop("id"))
        snapshot = IncidentSnapshot(incident.snapshot.content.to_dict())

        topology_menu = self.generate_topology_menu(snapshot)

        default_aggregated_config = {}
        for menu in topology_menu:
            default_aggregated_config[menu["entity_type"]] = [
                item["aggregate_key"] for item in menu["aggregate_bys"] if not item["is_anomaly"]
            ]

        return {
            "menu": topology_menu,
            "default_aggregated_config": default_aggregated_config,
        }

    def generate_topology_menu(self, snapshot: IncidentSnapshot) -> Dict:
        """根据快照内容生成拓扑图目录选项

        :param snapshot: 快照内容
        :return: 拓扑图目录选项
        """
        entity_types = defaultdict(list)
        for entity in snapshot.incident_graph_entities.values():
            entity_types[entity.entity_type].append(entity)

        menu_data = {}

        for entity_type, entities in entity_types.items():
            has_anomaly = False
            neighbors = set()
            for i_entity in entities:
                for j_entity in entities:
                    if i_entity.entity_id == j_entity.entity_id or i_entity.is_root or j_entity.is_root:
                        continue

                    i_entity_targets = set(
                        snapshot.entity_targets[i_entity.entity_id][IncidentGraphEdgeType.DEPENDENCY]
                    )
                    j_entity_targets = set(
                        snapshot.entity_targets[j_entity.entity_id][IncidentGraphEdgeType.DEPENDENCY]
                    )
                    # 如果任意两个实体，他们的有同一个从属实体，则两个实体可以按照这个从属实体进行聚会，就把从属实体的实体类型加入到可聚合的实体类型中
                    for target_entity_id in list(i_entity_targets & j_entity_targets):
                        neighbors.add(snapshot.incident_graph_entities[target_entity_id].entity_type)
                        if (
                            (i_entity.is_anomaly or j_entity.is_anomaly)
                            and not i_entity.is_root
                            and not j_entity.is_root
                        ):
                            has_anomaly = True

                    i_entity_sources = set(
                        snapshot.entity_sources[i_entity.entity_id][IncidentGraphEdgeType.DEPENDENCY]
                    )
                    j_entity_sources = set(
                        snapshot.entity_sources[j_entity.entity_id][IncidentGraphEdgeType.DEPENDENCY]
                    )
                    # 如果任意两个实体，他们的有同一个从属实体，则两个实体可以按照这个从属实体进行聚会，就把从属实体的实体类型加入到可聚合的实体类型中
                    for source_entity_id in list(i_entity_sources & j_entity_sources):
                        neighbors.add(snapshot.incident_graph_entities[source_entity_id].entity_type)
                        if (
                            (i_entity.is_anomaly or j_entity.is_anomaly)
                            and not i_entity.is_root
                            and not j_entity.is_root
                        ):
                            has_anomaly = True

            aggregate_keys = [{"count": 0, "aggregate_key": key, "is_anomaly": False} for key in list(neighbors)]
            if has_anomaly:
                aggregate_keys.append({"count": 0, "aggregate_key": None, "is_anomaly": True})

            if len(aggregate_keys) > 0:
                menu_data[entity_type] = {
                    "entity_type": entity_type,
                    "aggregate_bys": aggregate_keys,
                }
        return list(menu_data.values())


class IncidentTopologyUpstreamResource(IncidentBaseResource):
    """
    故障拓扑图资源子图
    """

    def __init__(self):
        super(IncidentTopologyUpstreamResource, self).__init__()

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(required=True, label="故障ID")
        entity_id = serializers.CharField(required=True, label="故障实体")
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def perform_request(self, validated_request_data: Dict) -> Dict:
        incident = IncidentDocument.get(validated_request_data.pop("id"))
        snapshot = IncidentSnapshot(incident.snapshot.content.to_dict())

        sub_snapshot = snapshot.generate_entity_sub_graph_from_api(
            incident.incident_id,
            validated_request_data["entity_id"],
            incident.snapshot.fpp_snapshot_id,
        )
        sub_snapshot.aggregate_graph(incident)
        ranks = sub_snapshot.group_by_rank()

        for rank_info in ranks:
            rank_info["nodes"] = self.generate_nodes_by_entites(incident, sub_snapshot, rank_info["entities"])
            for index, entity_info in enumerate(rank_info["entities"]):
                rank_info["nodes"][index]["aggregated_nodes"] = self.generate_nodes_by_entites(
                    incident, sub_snapshot, entity_info.aggregated_entities
                )
            rank_info.pop("entities")

        return {
            "ranks": sorted(
                [rank_info for rank_info in ranks if len(rank_info["nodes"]) > 0], key=lambda x: x["rank_id"]
            ),
            "edges": [edge.to_src_dict() for edge in sub_snapshot.incident_graph_edges.values()],
        }


class IncidentTimeLineResource(IncidentBaseResource):
    """
    故障时序图
    """

    def __init__(self):
        super(IncidentTimeLineResource, self).__init__()

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(required=False, label="故障ID")
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        start_time = serializers.IntegerField(required=False, label="开始时间")
        end_time = serializers.IntegerField(required=False, label="结束时间")

    def perform_request(self, validated_request_data: Dict) -> Dict:
        return {}


class IncidentAlertAggregateResource(IncidentBaseResource):
    """
    故障告警按维度聚合接口
    """

    def __init__(self):
        super(IncidentAlertAggregateResource, self).__init__()

    class RequestSerializer(AlertSearchSerializer):
        id = serializers.IntegerField(required=True, label="故障ID")
        aggregate_bys = serializers.ListField(required=True, label="聚合维度")
        ordering = serializers.ListField(label="排序", child=serializers.CharField(), default=[])
        page = serializers.IntegerField(label="页数", min_value=1, default=1)
        page_size = serializers.IntegerField(label="每页大小", min_value=0, max_value=5000, default=300)
        start_time = serializers.IntegerField(label="开始时间", required=False)
        end_time = serializers.IntegerField(label="结束时间", required=False)
        record_history = serializers.BooleanField(label="是否保存收藏历史", default=False)
        must_exists_fields = serializers.ListField(label="必要字段", child=serializers.CharField(), default=[])

    def perform_request(self, validated_request_data: Dict) -> Dict:
        incident = IncidentDocument.get(validated_request_data.pop("id"))
        snapshot = IncidentSnapshot(incident.snapshot.content.to_dict())

        record_history = validated_request_data.pop("record_history")

        with SearchHistory.record(
            SearchType.ALERT,
            validated_request_data,
            enabled=record_history and validated_request_data.get("query_string"),
        ):
            alerts = self.get_snapshot_alerts(snapshot, **validated_request_data)

        aggregate_results = self.aggregate_alerts(
            alerts, ["status", *validated_request_data["aggregate_bys"]], snapshot, incident
        )

        return aggregate_results

    def aggregate_alerts(
        self, alerts: List[Dict], aggregate_bys: List[str], snapshot: IncidentSnapshot, incident: IncidentDocument
    ) -> Dict:
        """对故障的告警进行聚合.

        :param alerts: 告警列表
        :return: 告警聚合结果
        """
        aggregate_results = {}

        for status in [EventStatus.ABNORMAL, EventStatus.RECOVERED, EventStatus.CLOSED]:
            aggregate_results[status] = {
                "id": status,
                "name": str(EVENT_STATUS_DICT[status]),
                "level_name": "status",
                "count": 0,
                "related_entities": [],
                "children": {},
                "alert_ids": [],
                "is_root": False,
                "is_feedback_root": False,
                "begin_time": None,
                "end_time": None,
                "status": None,
                "alert_example": None,
            }

        for alert in alerts:
            alert["entity"] = snapshot.alert_entity_mapping[alert["id"]].entity.to_src_dict()
            is_root = alert["entity"]["is_root"]
            is_feedback_root = getattr(incident.feedback, "incident_root", None) == alert["entity"]["entity_id"]

            aggregate_layer_results = aggregate_results
            for aggregate_by in aggregate_bys:
                agg_dim = IncidentAlertAggregateDimension(aggregate_by)
                chain_key = agg_dim.chain_key
                aggregate_by_value = self.get_item_by_chain_key(alert, chain_key)
                if not aggregate_by_value:
                    continue
                if agg_dim == IncidentAlertAggregateDimension.METRIC_NAME:
                    aggregate_by_value = "|".join([item["id"] for item in aggregate_by_value])
                if aggregate_by_value not in aggregate_layer_results:
                    aggregate_layer_results[aggregate_by_value] = {
                        "id": aggregate_by_value,
                        "name": aggregate_by_value,
                        "level_name": agg_dim.value,
                        "count": 1,
                        "children": {},
                        "related_entities": [alert["entity"]["entity_id"]],
                        "alert_ids": [str(alert["id"])],
                        "is_root": is_root,
                        "is_feedback_root": is_feedback_root,
                        "begin_time": alert["begin_time"],
                        "end_time": alert["end_time"],
                        "status": alert["status"],
                        "alert_example": alert,
                    }
                else:
                    # 更新被聚合告警聚合后的覆盖时间范围
                    if (
                        not aggregate_layer_results[aggregate_by_value]["begin_time"]
                        or alert["begin_time"] < aggregate_layer_results[aggregate_by_value]["begin_time"]
                    ):
                        aggregate_layer_results[aggregate_by_value]["begin_time"] = alert["begin_time"]
                    if not aggregate_layer_results[aggregate_by_value]["end_time"] or (
                        alert["end_time"]
                        and alert["end_time"] > aggregate_layer_results[aggregate_by_value]["end_time"]
                    ):
                        aggregate_layer_results[aggregate_by_value]["end_time"] = alert["end_time"]
                    if not aggregate_layer_results[aggregate_by_value]["status"]:
                        aggregate_layer_results[aggregate_by_value]["status"] = alert["status"]
                    elif alert["status"] == EventStatus.ABNORMAL:
                        aggregate_layer_results[aggregate_by_value]["status"] = EventStatus.ABNORMAL
                    if not aggregate_layer_results[aggregate_by_value]["alert_example"]:
                        aggregate_layer_results[aggregate_by_value]["alert_example"] = alert

                    # 其他依赖配置
                    aggregate_layer_results[aggregate_by_value]["count"] += 1
                    aggregate_layer_results[aggregate_by_value]["related_entities"].append(alert["entity"]["entity_id"])
                    aggregate_layer_results[aggregate_by_value]["alert_ids"].append(str(alert["id"]))
                    aggregate_layer_results[aggregate_by_value]["is_root"] = (
                        aggregate_layer_results[aggregate_by_value]["is_root"] or is_root
                    )
                    aggregate_layer_results[aggregate_by_value]["is_feedback_root"] = (
                        aggregate_layer_results[aggregate_by_value]["is_feedback_root"] or is_feedback_root
                    )
                aggregate_layer_results = aggregate_layer_results[aggregate_by_value]["children"]

        return self.expand_children_dict_as_list(aggregate_results)


class IncidentHandlersResource(IncidentBaseResource):
    """
    故障处理人列表
    """

    def __init__(self):
        super(IncidentHandlersResource, self).__init__()

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(required=True, label="故障ID")
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def perform_request(self, validated_request_data: Dict) -> Dict:
        incident = IncidentDocument.get(validated_request_data["id"])
        snapshot = IncidentSnapshot(incident.snapshot.content.to_dict())
        alerts = self.get_snapshot_alerts(snapshot, page_size=MAX_INCIDENT_ALERT_SIZE)
        current_username = get_request_username()

        alert_abornomal_agg_results = Counter()
        alert_total_agg_results = Counter()
        for alert in alerts:
            if not alert["assignee"]:
                if alert["status"] == EventStatus.ABNORMAL:
                    alert_abornomal_agg_results["__not_dispatch__"] += 1
                alert_total_agg_results["__not_dispatch__"] += 1
                continue

            if alert["status"] == EventStatus.ABNORMAL:
                alert_abornomal_agg_results["__total__"] += 1
            alert_total_agg_results["__total__"] += 1

            for username in alert["assignee"]:
                if alert["status"] == EventStatus.ABNORMAL:
                    alert_abornomal_agg_results[username] += 1
                alert_total_agg_results[username] += 1

        handlers = {
            "all": {
                "id": "all",
                "name": _("全部"),
                "index": 1,
                "alert_count": alert_abornomal_agg_results["__total__"],
                "total_count": len(alerts),
            },
            "not_dispatch": {
                "id": "not_dispatch",
                "name": _("未分派"),
                "index": 2,
                "alert_count": alert_abornomal_agg_results["__not_dispatch__"],
                "total_count": alert_total_agg_results["__not_dispatch__"],
            },
            "mine": {
                "id": current_username,
                "name": _("我处理"),
                "index": 3,
                "alert_count": alert_abornomal_agg_results.get(current_username, 0),
                "total_count": alert_total_agg_results.get(current_username, 0),
            },
            "other": {
                "id": "other",
                "name": _("其他"),
                "index": 4,
                "children": [
                    {
                        "id": username,
                        "name": username,
                        "alert_count": alert_abornomal_agg_results.get(username, 0),
                        "total_count": alert_count,
                    }
                    for username, alert_count in alert_total_agg_results.items()
                    if username not in (current_username, "__not_dispatch__", "__total__")
                ],
            },
        }

        return handlers


class IncidentOperationsResource(IncidentBaseResource):
    """
    故障流转列表
    """

    def __init__(self):
        super(IncidentOperationsResource, self).__init__()

    class RequestSerializer(serializers.Serializer):
        incident_id = serializers.IntegerField(required=True, label="故障ID")
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        start_time = serializers.IntegerField(required=False, label="开始时间")
        end_time = serializers.IntegerField(required=False, label="结束时间")

    def perform_request(self, validated_request_data: Dict) -> Dict:
        operations = IncidentOperationDocument.list_by_incident_id(
            validated_request_data["incident_id"],
            start_time=validated_request_data.get("start_time"),
            end_time=validated_request_data.get("end_time"),
            order_by="-create_time",
        )
        operations = [operation.to_dict() for operation in operations]
        for operation in operations:
            operation["operation_class"] = IncidentOperationType(operation["operation_type"]).operation_class.value
        return operations


class IncidentRecordOperationResource(IncidentBaseResource):
    """
    故障流转列表
    """

    def __init__(self):
        super(IncidentRecordOperationResource, self).__init__()

    class RequestSerializer(serializers.Serializer):
        incident_id = serializers.IntegerField(required=True, label="故障ID")
        operation_type = serializers.ChoiceField(
            required=True, choices=IncidentOperationType.get_enum_value_list(), label="故障流转类型"
        )
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        extra_info = serializers.JSONField(required=True, label="额外信息")

    def perform_request(self, validated_request_data: Dict) -> Dict:
        IncidentOperationManager.record_operation(
            incident_id=validated_request_data["incident_id"],
            operation_type=IncidentOperationType(validated_request_data["operation_type"]),
            operate_time=int(time.time()),
            **validated_request_data["extra_info"],
        )
        return "ok"


class IncidentOperationTypesResource(IncidentBaseResource):
    """
    故障流转列表
    """

    class RequestSerializer(serializers.Serializer):
        incident_id = serializers.IntegerField(required=True, label="故障ID")
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def __init__(self):
        super(IncidentOperationTypesResource, self).__init__()

    def perform_request(self, validated_request_data: Dict) -> Dict:
        operations = IncidentOperationDocument.list_by_incident_id(
            validated_request_data["incident_id"],
            order_by="-create_time",
        )
        incident_operation_types = {operation.operation_type for operation in operations}

        operation_types = {
            operation_class: {
                "operation_class": operation_class.value,
                "operation_class_alias": operation_class.alias,
                "operation_types": [],
            }
            for operation_class in IncidentOperationClass.__members__.values()
        }

        for operation_type in IncidentOperationType.__members__.values():
            if operation_type.value in incident_operation_types:
                operation_types[operation_type.operation_class]["operation_types"].append(
                    {
                        "operation_type": operation_type.value,
                        "operation_type_alias": operation_type.alias,
                    }
                )
        return list(filter(lambda item: len(item["operation_types"]) > 0, operation_types.values()))


class EditIncidentResource(IncidentBaseResource):
    """
    故障修改接口
    """

    def __init__(self):
        super(EditIncidentResource, self).__init__()

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(required=True, label="故障ID")
        incident_id = serializers.IntegerField(required=True, label="故障ID")
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        incident_name = serializers.CharField(required=False, label="故障名称")
        incident_reason = serializers.CharField(required=False, label="故障原因", allow_blank=True, allow_null=True)
        level = serializers.CharField(required=False, label="故障级别")
        assignees = serializers.ListField(required=False, label="故障负责人")
        handlers = serializers.ListField(required=False, label="故障处理人")
        labels = serializers.ListField(required=False, label="故障标签")
        status = serializers.CharField(required=False, label="故障状态")

    def perform_request(self, validated_request_data: Dict) -> Dict:
        incident_id = validated_request_data["incident_id"]

        incident_info = api.bkdata.get_incident_detail(incident_id=incident_id)
        incident_info.update(validated_request_data)
        updated_incident = api.bkdata.update_incident_detail(**incident_info)

        self.update_incident_document(
            incident_info,
            arrow.get(updated_incident["updated_at"]).replace(tzinfo=timezone.get_current_timezone().zone),
        )
        return incident_info


class FeedbackIncidentRootResource(IncidentBaseResource):
    """
    反馈故障根因
    """

    def __init__(self):
        super(FeedbackIncidentRootResource, self).__init__()

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(required=True, label="故障ID")
        incident_id = serializers.IntegerField(required=True, label="故障ID")
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        feedback = serializers.JSONField(required=True, label="反馈的内容")
        is_cancel = serializers.BooleanField(required=False, default=False)

    def perform_request(self, validated_request_data: Dict) -> Dict:
        incident_id = validated_request_data["incident_id"]
        is_cancel = validated_request_data["is_cancel"]

        incident_info = api.bkdata.get_incident_detail(incident_id=incident_id)
        incident_info["id"] = validated_request_data["id"]

        if not is_cancel:
            incident_info["feedback"].update(validated_request_data["feedback"])
        else:
            incident_info["feedback"] = {}
        updated_incident = api.bkdata.update_incident_detail(**incident_info)
        update_time = arrow.get(updated_incident["updated_at"]).replace(tzinfo=timezone.get_current_timezone().zone)
        self.update_incident_document(incident_info, update_time)
        if is_cancel:
            IncidentOperationManager.record_feedback_incident(
                incident_info["incident_id"],
                update_time.timestamp,
                None,
                None,
                is_cancel,
            )
        return incident_info["feedback"]


class IncidentAlertListResource(IncidentBaseResource):
    """
    故障告警列表
    """

    def __init__(self):
        super(IncidentAlertListResource, self).__init__()

    class RequestSerializer(AlertSearchSerializer):
        id = serializers.IntegerField(required=True, label="故障ID")
        start_time = serializers.IntegerField(required=False, label="开始时间")
        end_time = serializers.IntegerField(required=False, label="结束时间")
        page = serializers.IntegerField(required=False, label="页码", default=1)
        page_size = serializers.IntegerField(required=False, label="每页条数", default=MAX_INCIDENT_ALERT_SIZE)

    def perform_request(self, validated_request_data: Dict) -> Dict:
        incident = IncidentDocument.get(validated_request_data.pop("id"))
        snapshot = IncidentSnapshot(incident.snapshot.content.to_dict())
        alerts = self.get_snapshot_alerts(snapshot, **validated_request_data)

        incident_alerts = resource.commons.get_label()
        for category in incident_alerts:
            category["alerts"] = []
            category["sub_categories"] = [item["id"] for item in category["children"]]

        for alert in alerts:
            alert_entity = snapshot.alert_entity_mapping.get(alert["id"])
            alert["entity"] = alert_entity.entity.to_src_dict() if alert_entity else None
            alert["is_feedback_root"] = (
                getattr(incident.feedback, "incident_root", None) == alert_entity.entity.entity_id
            )
            for category in incident_alerts:
                if alert["category"] in category["sub_categories"]:
                    category["alerts"].append(alert)

        if len(alerts) > 0:
            alerts[0]["is_incident_root"] = True

        return incident_alerts


class IncidentAlertViewResource(IncidentBaseResource):
    """
    故障告警视图接口
    """

    def __init__(self):
        super(IncidentAlertViewResource, self).__init__()

    class RequestSerializer(AlertSearchSerializer):
        id = serializers.IntegerField(required=True, label="故障ID")
        start_time = serializers.IntegerField(required=False, label="开始时间")
        end_time = serializers.IntegerField(required=False, label="结束时间")
        page = serializers.IntegerField(required=False, label="页码", default=1)
        page_size = serializers.IntegerField(required=False, label="每页条数", default=MAX_INCIDENT_ALERT_SIZE)

    def perform_request(self, validated_request_data: Dict) -> Dict:
        incident = IncidentDocument.get(validated_request_data.pop("id"))
        snapshot = IncidentSnapshot(incident.snapshot.content.to_dict())
        alerts = self.get_snapshot_alerts(snapshot, **validated_request_data)

        incident_alerts = resource.commons.get_label()
        for category in incident_alerts:
            category["alerts"] = []
            category["sub_categories"] = [item["id"] for item in category["children"]]

        for alert in alerts:
            alert_entity = snapshot.alert_entity_mapping.get(alert["id"])
            alert["entity"] = alert_entity.entity.to_src_dict() if alert_entity else None
            alert["is_feedback_root"] = (
                getattr(incident.feedback, "incident_root", None) == alert_entity.entity.entity_id
            )
            alert_doc = AlertDocument(**alert)
            for category in incident_alerts:
                if alert["category"] in category["sub_categories"]:
                    alert["graph_panel"] = AIOPSManager.get_graph_panel(alert_doc)
                    category["alerts"].append(alert)

        return incident_alerts
