"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import datetime
import functools
import itertools
import json
import re

from collections.abc import Callable
from typing import Any
from datetime import timedelta

import arrow
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from django.db.models import Q
from django.db.models.functions import Length

from api.cmdb.define import Business

from apm_web.constants import (
    CategoryEnum,
    CMDBCategoryIconMap,
    ServiceDetailReqTypeChoices,
    ServiceRelationLogTypeChoices,
)
from apm_web.handlers.service_handler import ServiceHandler
from apm_web.handlers.span_handler import SpanHandler
from apm_web.strategy.dispatch.entity import EntitySet
from apm_web.icon import get_icon
from apm_web.models import (
    ApdexServiceRelation,
    ApmMetaConfig,
    Application,
    AppServiceRelation,
    CMDBServiceRelation,
    EventServiceRelation,
    LogServiceRelation,
    CodeRedefinedConfigRelation,
    UriServiceRelation,
    ServiceBase,
)
from apm_web.profile.doris.querier import QueryTemplate
from apm_web.serializers import ApplicationListSerializer, ServiceApdexConfigSerializer
from apm_web.service.serializers import (
    AppServiceRelationSerializer,
    LogServiceRelationOutputSerializer,
    ServiceConfigSerializer,
    PipelineOverviewRequestSerializer,
    ListPipelineRequestSerializer,
    ListCodeRedefinedRuleRequestSerializer,
    SetCodeRedefinedRuleRequestSerializer,
    SetCodeRemarkRequestSerializer,
    BaseCodeRedefinedRequestSerializer,
    DeleteCodeRedefinedRuleRequestSerializer,
)
from apm_web.topo.handle.relation.relation_metric import RelationMetricHandler
from bkm_space.errors import NoRelatedResourceError
from bkm_space.validate import validate_bk_biz_id
from bkmonitor.commons.tools import batch_request
from bkmonitor.utils.cache import lru_cache_with_ttl
from bkmonitor.utils.request import get_request_username
from bkmonitor.utils.thread_backend import InheritParentThread, run_threads
from bkmonitor.utils.thread_backend import ThreadPool
from bkmonitor.utils.time_tools import get_datetime_range
from core.drf_resource import Resource, api


class ApplicationListResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")

    def perform_request(self, validated_request_data):
        apps = Application.objects.filter(bk_biz_id=validated_request_data["bk_biz_id"])
        serializer = ApplicationListSerializer(apps, many=True)
        return serializer.data


class ServiceListResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")
        service_names = serializers.ListField(
            label="服务名列表", child=serializers.CharField(), required=False, default=[]
        )

    def perform_request(self, validated_request_data):
        entity_set = EntitySet(
            bk_biz_id=validated_request_data["bk_biz_id"],
            app_name=validated_request_data["app_name"],
            service_names=validated_request_data["service_names"] or None,
        )
        return [self._build_service_info(entity_set, name) for name in entity_set.service_names]

    @staticmethod
    def _build_service_info(entity_set: EntitySet, service_name: str) -> dict[str, Any]:
        # 已按 `entity_set.service_names` 取值，不会出现 node 为 None 的情况。
        node: dict[str, Any] = entity_set.get_node_or_none(service_name)
        service_info: dict[str, Any] = {
            "service_name": service_name,
            "service_language": (node.get("extra_data") or {}).get("service_language", ""),
            "system": entity_set.get_system(service_name),
            "log_relations": entity_set.get_log_relations(service_name),
        }

        k8s_workloads: list[dict[str, Any]] = entity_set.get_workloads(service_name)
        if k8s_workloads:
            service_info["platform"] = {"name": "k8s", "relations": k8s_workloads}
        return service_info


class ServiceInfoResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label=_("业务 ID"))
        app_name = serializers.CharField(label=_("应用名称"))
        service_name = serializers.CharField(label=_("服务"))
        start_time = serializers.IntegerField(label=_("数据开始时间"), required=False)
        end_time = serializers.IntegerField(label=_("数据结束时间"), required=False)

        def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
            app: Application = Application.objects.filter(
                bk_biz_id=attrs["bk_biz_id"], app_name=attrs["app_name"]
            ).first()
            if not app:
                raise serializers.ValidationError(_("应用 %(app_name)s 不存在") % {"app_name": attrs["app_name"]})

            if "start_time" not in attrs and "end_time" not in attrs:
                start_time, end_time = get_datetime_range(
                    period="day",
                    distance=app.es_retention,
                    rounding=False,
                )
                attrs["start_time"] = int(start_time.timestamp())
                attrs["end_time"] = int(end_time.timestamp())

            return super().validate(attrs)

    @classmethod
    def fill_operate_record(cls, service_info: dict[str, Any], relation_infos: list[dict[str, Any]]) -> None:
        """获取操作记录"""
        default_username = "system"

        def bigger_than_update(lft_info: dict[str, Any], rgt_info: dict[str, Any]) -> None:
            lft_time: int = lft_info.get("updated_at") or 0
            rgt_time: int = rgt_info.get("updated_at") or 0
            if arrow.get(lft_time) > arrow.get(rgt_time):
                rgt_info["updated_at"] = lft_time
                rgt_info["updated_by"] = lft_info.get("updated_by") or default_username

        for relation_info in relation_infos:
            bigger_than_update(relation_info, service_info)

        # 如果没有，则设置默认值
        service_info.setdefault("created_at", None)
        service_info["created_by"] = service_info.get("created_by") or default_username
        service_info.setdefault("updated_at", None)
        service_info["updated_by"] = service_info.get("updated_by") or default_username

    @classmethod
    def get_cmdb_relation_info(cls, bk_biz_id: int, app_name: str, service_name: str) -> dict[str, Any]:
        relation_obj = CMDBServiceRelation.get_relation_qs(bk_biz_id, app_name, [service_name]).first()
        if not relation_obj:
            return {}

        template = {t["id"]: t for t in CMDBServiceTemplateResource.get_templates(bk_biz_id)}.get(
            relation_obj.template_id, {}
        )
        return {
            "template_id": template.get("id"),
            "template_name": template.get("name"),
            "first_category": template.get("first_category"),
            "second_category": template.get("second_category"),
            "updated_by": relation_obj.updated_by,
            "updated_at": relation_obj.updated_at,
        }

    @classmethod
    def get_log_relation_infos(cls, bk_biz_id: int, app_name: str, service_name: str) -> list[dict[str, Any]]:
        return LogServiceRelationOutputSerializer(
            instance=LogServiceRelation.get_relation_qs(bk_biz_id, app_name, [service_name]),
            many=True,
        ).data

    @classmethod
    def get_app_relation_info(cls, bk_biz_id: int, app_name: str, service_name: str) -> dict[str, Any]:
        relation_obj: AppServiceRelation = AppServiceRelation.get_relation_qs(
            bk_biz_id, app_name, [service_name]
        ).first()
        if not relation_obj:
            return {}

        res: dict[str, Any] = AppServiceRelationSerializer(instance=relation_obj).data
        biz = {i.bk_biz_id: i for i in api.cmdb.get_business(bk_biz_ids=[relation_obj.relate_bk_biz_id])}.get(
            relation_obj.relate_bk_biz_id
        )
        res["relate_bk_biz_name"] = biz.bk_biz_name if isinstance(biz, Business) else None
        res["application_id"] = relation_obj.relate_app_name
        return res

    @classmethod
    def get_uri_relation_infos(cls, bk_biz_id: int, app_name: str, service_name: str) -> list[dict[str, Any]]:
        return list(UriServiceRelation.get_relation_qs(bk_biz_id, app_name, [service_name]).order_by("rank").values())

    @classmethod
    def get_apdex_relation_info(
        cls, bk_biz_id: int, app_name: str, service_name: str, topo_node: list[dict[str, Any]]
    ) -> dict[str, Any]:
        instance = ServiceHandler.get_apdex_relation_info(bk_biz_id, app_name, service_name, topo_node)
        if not instance:
            return {}
        return ServiceApdexConfigSerializer(instance=instance).data

    @classmethod
    def get_profiling_info(
        cls, app: Application, bk_biz_id: int, app_name: str, service_name: str, start_time: int, end_time: int
    ) -> dict[str, Any]:
        """获取服务的 profiling 状态"""
        res = {"application_id": app.application_id, "is_enabled_profiling": app.is_enabled_profiling}
        if app.is_enabled_profiling:
            # 获取此服务是否有 Profiling 数据
            try:
                count = QueryTemplate(bk_biz_id, app_name).get_service_count(start_time, end_time, service_name)
                res["is_profiling_data_normal"] = bool(count)
            except Exception:  # pylint: disable=broad-except
                res["is_profiling_data_normal"] = False
        else:
            res["is_profiling_data_normal"] = False

        return res

    @classmethod
    def get_labels(cls, bk_biz_id: int, app_name: str, service_name: str) -> list[Any]:
        config_instance = ApmMetaConfig.get_service_config_value(bk_biz_id, app_name, service_name, "labels")
        if config_instance:
            return json.loads(config_instance.config_value)
        return []

    def perform_request(self, validate_data: dict[str, Any]) -> dict[str, Any]:
        # 获取请求数据
        bk_biz_id: int = validate_data["bk_biz_id"]
        app_name: str = validate_data["app_name"]
        service_name: str = validate_data["service_name"]
        app: Application = Application.objects.get(bk_biz_id=bk_biz_id, app_name=app_name)

        base_query_param: dict[str, Any] = {
            "bk_biz_id": bk_biz_id,
            "app_name": app_name,
            "service_name": service_name,
        }
        pool = ThreadPool()
        topo_node_res = pool.apply_async(ServiceHandler.list_nodes, kwds=base_query_param)
        instance_res = pool.apply_async(
            RelationMetricHandler.list_instances,
            kwds={
                **base_query_param,
                "start_time": validate_data["start_time"],
                "end_time": validate_data["end_time"],
            },
        )
        app_res = pool.apply_async(self.get_app_relation_info, kwds=base_query_param)
        log_res = pool.apply_async(self.get_log_relation_infos, kwds=base_query_param)
        cmdb_res = pool.apply_async(self.get_cmdb_relation_info, kwds=base_query_param)
        event_res = pool.apply_async(EventServiceRelation.get_relations, kwds=base_query_param)
        uri_res = pool.apply_async(self.get_uri_relation_infos, kwds=base_query_param)
        label_res = pool.apply_async(self.get_labels, kwds=base_query_param)
        profiling_res = pool.apply_async(
            self.get_profiling_info,
            kwds={
                "app": app,
                **base_query_param,
                "start_time": validate_data["start_time"],
                "end_time": validate_data["end_time"],
            },
        )
        pool.close()
        pool.join()

        # 获取服务信息
        service_info: dict[str, Any] = {"extra_data": {}, "topo_key": service_name}
        topo_nodes: list[dict[str, Any]] = topo_node_res.get()
        for service in topo_nodes:
            if service["topo_key"] == validate_data["service_name"]:
                service_info.update(service)

        app_relation_info: dict[str, Any] = app_res.get()
        log_relation_infos: list[dict[str, Any]] = log_res.get()
        cmdb_relation_info: dict[str, Any] = cmdb_res.get()
        event_relation_infos: list[dict[str, Any]] = event_res.get()
        uri_relation_infos: list[dict[str, Any]] = uri_res.get()
        apdex_info: dict[str, Any] = self.get_apdex_relation_info(bk_biz_id, app_name, service_name, topo_nodes)
        self.fill_operate_record(
            service_info,
            [
                apdex_info,
                app_relation_info,
                log_relation_infos[0] if log_relation_infos else {},
                cmdb_relation_info,
                *event_relation_infos,
                *uri_relation_infos,
            ],
        )
        profiling_info: dict[str, Any] = profiling_res.get()
        service_info.update(profiling_info)

        service_info["relation"] = {
            "app_relation": app_relation_info,
            "log_relation_list": log_relation_infos,
            "cmdb_relation": cmdb_relation_info,
            "event_relation": event_relation_infos,
            "uri_relation": uri_relation_infos,
            "apdex_relation": apdex_info,
        }

        # 一级分类
        first_category: str = service_info["extra_data"].get("category", "")
        # 一级分类为 HTTP 时，设置二级分类为空
        if first_category == "http":
            service_info["extra_data"]["predicate_value"] = ""
        # 二级分类，保留中间变量增加可读性
        second_category: str = service_info["extra_data"].get("predicate_value", "")
        service_info["extra_data"].update(
            category_name=CategoryEnum.get_label_by_key(first_category),
            category_icon=get_icon(first_category),
            predicate_value_icon=get_icon(second_category),
        )
        # 实例数
        service_info["instance_count"] = len(instance_res.get())
        # 自定义标签
        service_info["labels"] = label_res.get()
        return service_info


class CMDBServiceTemplateResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")

    @classmethod
    def get_cmdb_icon(cls, category_name: str):
        icon_id = CMDBCategoryIconMap.get_icon_id(category_name)
        icon = get_icon(icon_id)
        return icon

    @classmethod
    def get_templates(cls, bk_biz_id):
        # 获取目录信息
        categories = batch_request(api.cmdb.client.list_service_category, {"bk_biz_id": bk_biz_id})
        category_map = {category["id"]: category for category in categories}
        # 获取模板信息
        templates = batch_request(api.cmdb.client.list_service_template, {"bk_biz_id": bk_biz_id})
        for template in templates:
            # 获取二级目录信息
            second_category_id = template.get("service_category_id", 0)
            second_category = category_map.get(second_category_id, {})
            template["second_category"] = second_category
            template["second_category"]["icon"] = cls.get_cmdb_icon(second_category.get("name"))
            # 获取一级目录信息
            first_category_id = second_category.get("bk_parent_id", 0)
            first_category = category_map.get(first_category_id, {})
            template["first_category"] = first_category
            template["first_category"]["icon"] = cls.get_cmdb_icon(first_category.get("name"))
        return templates

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        if bk_biz_id < 0:
            # 非业务不能获取 CMDB 模板
            return []
        return self.get_templates(validated_request_data["bk_biz_id"])


class ServiceRelationResource(Resource):
    queryset = None
    serializer_class = None

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label=_("业务 ID"))
        app_name = serializers.CharField(label=_("应用名称"))
        service_name = serializers.CharField(label=_("服务"))
        req_type = serializers.ChoiceField(label=_("请求类型"), choices=ServiceDetailReqTypeChoices.choices())
        extras = serializers.JSONField(label=_("附加数据"))

    def get_instance(self, bk_biz_id: int, app_name: str, service_name: str, instance_id: int) -> Any:
        try:
            return self.queryset.get(id=instance_id, bk_biz_id=bk_biz_id, app_name=app_name, service_name=service_name)
        except self.queryset.model.DoesNotExist:
            raise ValueError(_("资源不存在"))

    def build_instance_response_data(self, bk_biz_id: int, app_name: str, service_name: str, data: dict) -> dict:
        return data

    def build_multi_response_data(self, bk_biz_id: int, app_name: str, service_name: str, data: list) -> list:
        return data

    def handle_delete(self, bk_biz_id: int, app_name: str, service_name: str, extras: dict) -> None:
        instance_id = extras.pop("id", None)
        instance = self.get_instance(bk_biz_id, app_name, service_name, instance_id)
        instance.delete()
        return

    def handle_update(self, bk_biz_id: int, app_name: str, service_name: str, extras: dict) -> dict[str, Any]:
        instance_id = extras.pop("id", None)
        # 新增
        if instance_id is None:
            extras.update({"bk_biz_id": bk_biz_id, "app_name": app_name, "service_name": service_name})
            serializer = self.serializer_class(data=extras)
        # 更新
        else:
            instance = self.get_instance(bk_biz_id, app_name, service_name, instance_id)
            serializer = self.serializer_class(instance, data=extras, partial=True)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        serializer = self.serializer_class(instance)
        return self.build_instance_response_data(bk_biz_id, app_name, service_name, serializer.data)

    def handle_list(self, bk_biz_id: int, app_name: str, service_name: str) -> list[dict[str, Any]]:
        queryset = self.queryset.filter(bk_biz_id=bk_biz_id, app_name=app_name, service_name=service_name)
        serializer = self.serializer_class(queryset, many=True)
        return self.build_multi_response_data(bk_biz_id, app_name, service_name, serializer.data)

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict[str, Any] | None:
        # 处理数据
        bk_biz_id = validated_request_data["bk_biz_id"]
        app_name = validated_request_data["app_name"]
        service_name = validated_request_data["service_name"]
        req_type = validated_request_data["req_type"]
        extras = validated_request_data["extras"]
        # 删除方法
        if req_type == ServiceDetailReqTypeChoices.DEL:
            return self.handle_delete(bk_biz_id, app_name, service_name, extras)
        # 更新方法
        if req_type == ServiceDetailReqTypeChoices.SET:
            return self.handle_update(bk_biz_id, app_name, service_name, extras)
        # 查询方法
        if req_type == ServiceDetailReqTypeChoices.GET:
            return self.handle_list(bk_biz_id, app_name, service_name)


class LogServiceChoiceListResource(Resource):
    def perform_request(self, validated_request_data):
        return ServiceRelationLogTypeChoices.choice_list()


class LogServiceRelationBkLogIndexSet(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        # 是否仅过滤开启数据指纹的索引集
        clustering_only = serializers.BooleanField(required=False, default=False)

    def perform_request(self, validated_request_data):
        index_set = api.log_search.search_index_set(bk_biz_id=validated_request_data["bk_biz_id"])
        if validated_request_data.get("clustering_only"):
            # 过滤开启数据指纹的索引集，根据是否携带关联tag判定
            new_index_set = []
            for index in index_set:
                for tag in index.get("tags", []):
                    if tag["name"] == "数据指纹" and tag["color"] == "green":
                        new_index_set.append(index)
                        continue
            index_set = new_index_set
        return [{"id": i["index_set_id"], "name": i["index_set_name"]} for i in index_set]


class ServiceConfigResource(Resource):
    RequestSerializer = ServiceConfigSerializer

    RELATION_MODEL_MAP = {
        "app_relation": AppServiceRelation,
        "cmdb_relation": CMDBServiceRelation,
        "log_relation_list": LogServiceRelation,
        "apdex_relation": ApdexServiceRelation,
        "uri_relation": UriServiceRelation,
        "event_relation": EventServiceRelation,
    }

    @classmethod
    def _prepare_default(cls, data: dict[str, Any] | list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        if data is None:
            return []
        return [data] if isinstance(data, dict) else data

    @classmethod
    def _prepare_uri_relation(cls, data: list[str]) -> list[dict[str, Any]]:
        return [{"uri": uri, "rank": i} for i, uri in enumerate(data)]

    @classmethod
    def _prepare_log_relation_list(cls, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        unique_relations: dict[int, dict[str, Any]] = {}
        for relation_dict in data:
            related_bk_biz_id = relation_dict.get("related_bk_biz_id")
            if related_bk_biz_id in unique_relations:
                # 合并 value_list
                existing_value_list: list[int] = unique_relations[related_bk_biz_id].get("value_list", [])
                new_value_list: list[int] = relation_dict.get("value_list", [])
                unique_relations[related_bk_biz_id]["value_list"] = existing_value_list + new_value_list
            else:
                if not relation_dict.get("value_list"):
                    continue
                unique_relations[related_bk_biz_id] = relation_dict

        return list(unique_relations.values())

    @classmethod
    def update_relation(cls, bk_biz_id: int, app_name: str, service_name: str, relation_type: str, relation_data: Any):
        if relation_type not in cls.RELATION_MODEL_MAP:
            return

        # 预处理数据
        model_cls: type[ServiceBase] = cls.RELATION_MODEL_MAP[relation_type]
        prepare_handler: Callable[[Any], list[dict[str, Any]]] = getattr(
            cls, f"_prepare_{relation_type}", cls._prepare_default
        )
        prepare_datas: list[dict[str, Any]] = prepare_handler(relation_data)
        # 构建模型记录数据
        records: list[dict[str, Any]] = [
            {"bk_biz_id": bk_biz_id, "app_name": app_name, "service_name": service_name, "is_global": False, **data}
            for data in prepare_datas
        ]
        # 执行同步
        if relation_type == "event_relation":
            model_cls.sync_relations(bk_biz_id, app_name, service_name, records, is_delete=False)
        else:
            model_cls.sync_relations(bk_biz_id, app_name, service_name, records)

    @classmethod
    def update_labels(cls, bk_biz_id: int, app_name: str, service_name: str, labels: list[str] | None) -> None:
        ApmMetaConfig.service_config_setup(
            bk_biz_id,
            app_name,
            service_name,
            "labels",
            json.dumps(labels),
        )

    def perform_request(self, validated_request_data: dict[str, Any]) -> None:
        bk_biz_id: int = validated_request_data["bk_biz_id"]
        app_name: str = validated_request_data["app_name"]
        service_name: str = validated_request_data["service_name"]

        # 对 labels 单独作处理
        if "labels" in validated_request_data:
            self.update_labels(bk_biz_id, app_name, service_name, validated_request_data["labels"])

        update_relation: Callable[[str, Any], None] = functools.partial(
            self.update_relation, bk_biz_id, app_name, service_name
        )
        for relation_type, relation_data in validated_request_data.items():
            if relation_type in self.RELATION_MODEL_MAP:
                update_relation(relation_type, relation_data)

        # 下发修改后的配置
        application = Application.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).get()
        from apm_web.tasks import update_application_config

        update_application_config.delay(
            application.bk_biz_id, application.app_name, {"service_configs": application.get_service_transfer_config()}
        )


class UriregularVerifyResource(Resource):
    TIME_DELTA = 1

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        app_name = serializers.CharField()
        service_name = serializers.CharField()
        uris_source = serializers.ListSerializer(child=serializers.CharField())
        uris = serializers.ListSerializer(child=serializers.CharField())

    def perform_request(self, data):
        """
        调试url
        """
        pool = ThreadPool()
        params = [(index, i, data["uris_source"]) for index, i in enumerate(data["uris"])]
        match_results = pool.map_ignore_exception(self.uri_regular, params)
        return list(itertools.chain(*[i for i in match_results if i]))

    def uri_regular(self, index, url_regex, sources):
        res = []
        for source in sources:
            if re.match(url_regex, source):
                res.append(f"第 {index + 1} 项配置({url_regex})匹配到 url: {source}")

        return res


class ServiceUrlListResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        app_name = serializers.CharField()
        service_name = serializers.CharField()

    def perform_request(self, data):
        app = Application.objects.get(bk_biz_id=data["bk_biz_id"], app_name=data["app_name"])
        if not app:
            raise ValueError(_("应用不存在"))

        end_time = datetime.datetime.now()
        # 页面有刷新按钮，这里限制一个比较可控的时间范围，避免查询超时。
        start_time = end_time - datetime.timedelta(hours=2)

        return SpanHandler.get_span_uris(app, start_time, end_time, service_name=data["service_name"])


class AppQueryByIndexSetResource(Resource):
    class RequestSerializer(serializers.Serializer):
        index_set_id = serializers.IntegerField()

    def perform_request(self, data):
        relations = LogServiceRelation.filter_by_index_set_id(data["index_set_id"])
        res = []
        for relation in relations:
            res.append({"bk_biz_id": relation.bk_biz_id, "app_name": relation.app_name})

        return res


class PipelineOverviewResource(Resource):
    RequestSerializer = PipelineOverviewRequestSerializer

    def perform_request(self, validated_request_data: dict[str, Any]) -> list[dict[str, Any]]:

        bk_biz_id = self._validate_bk_biz_id(validated_request_data["bk_biz_id"])
        business = api.cmdb.get_business(bk_biz_ids=[bk_biz_id])
        if not business:
            return []

        # 使用 devops_product_id 作为备选字段
        for field in ["bk_product_id", "devops_product_id"]:
            product_id = getattr(business[0], field, None)
            if product_id is not None:
                break
        # 没有产品 ID，返回空列表
        if product_id is None:
            return []

        # 获取业务关联的蓝盾项目
        devops_projects = api.devops.list_app_project({"productIds": product_id})
        pipeline_overview = []
        thread_list = []
        for devops_project in devops_projects:
            params = {
                "app_name": validated_request_data["app_name"],
                "bk_biz_id": bk_biz_id,
                "project_id": devops_project["projectCode"],
                "project_name": devops_project["projectName"],
                "page": validated_request_data["page"],
                "page_size": validated_request_data["page_size"],
                "keyword": validated_request_data.get("keyword"),
            }
            thread_list.append(
                InheritParentThread(target=self.list_pipeline, args=(params, pipeline_overview)),
            )
        run_threads(thread_list)

        return sorted(pipeline_overview, key=lambda project: project["project_id"])

    @classmethod
    @lru_cache_with_ttl(ttl=int(timedelta(minutes=10).total_seconds()))
    def _validate_bk_biz_id(cls, bk_biz_id: int) -> int:
        """将负数项目空间 ID，转为关联业务 ID"""
        try:
            return validate_bk_biz_id(bk_biz_id)
        except NoRelatedResourceError:
            return bk_biz_id

    @classmethod
    def list_pipeline(cls, params: dict[str, Any], pipeline_overview: list[dict[str, Any]]):
        pipeline_overview.append(cls.query_pipelines(**params))

    @classmethod
    def query_pipelines(cls, bk_biz_id, app_name, project_id, project_name, keyword, page, page_size) -> dict[str, Any]:
        """
        查询项目下的流水线
        """
        return {
            "project_id": project_id,
            "project_name": project_name,
            **ListPipelineResource().perform_request(
                {
                    "app_name": app_name,
                    "bk_biz_id": bk_biz_id,
                    "project_id": project_id,
                    "page": page,
                    "page_size": page_size,
                    "keyword": keyword,
                }
            ),
        }


class ListPipelineResource(Resource):
    RequestSerializer = ListPipelineRequestSerializer

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict[str, Any]:

        params = {
            "project_id": validated_request_data["project_id"],
            "page": validated_request_data["page"],
            "pageSize": validated_request_data["page_size"],
            "viewId": "allPipeline",
            "showDelete": False,
            "sortType": "LAST_EXEC_TIME",
        }

        if validated_request_data.get("keyword"):
            params["filterByPipelineName"] = validated_request_data["keyword"]

        # 查询流水线
        pipelines = api.devops.list_pipeline(params)
        processed_pipelines = [
            {
                "project_id": pipeline["projectId"],
                "pipeline_id": pipeline["pipelineId"],
                "pipeline_name": pipeline["pipelineName"],
            }
            for pipeline in pipelines["records"]
        ]
        return {"count": pipelines["count"], "items": processed_pipelines}


class ListCodeRedefinedRuleResource(Resource):
    RequestSerializer = ListCodeRedefinedRuleRequestSerializer

    def perform_request(self, validated_request_data):
        bk_biz_id: int = validated_request_data["bk_biz_id"]
        app_name: str = validated_request_data["app_name"]
        service_name: str = validated_request_data["service_name"]
        kind: str = validated_request_data["kind"]

        requested_callee_server: str | None = validated_request_data.get("callee_server")
        requested_callee_service: str | None = validated_request_data.get("callee_service")
        requested_callee_method: str | None = validated_request_data.get("callee_method")

        # 基础精确过滤
        q = Q(bk_biz_id=bk_biz_id, app_name=app_name, service_name=service_name, kind=kind)

        # 对传入的维度，匹配该值或空串；未传的不加过滤
        if requested_callee_server is not None:
            if requested_callee_server == "":
                q &= Q(callee_server="")
            else:
                q &= Q(callee_server__in=[requested_callee_server, ""])  # type: ignore
        if requested_callee_service is not None:
            if requested_callee_service == "":
                q &= Q(callee_service="")
            else:
                q &= Q(callee_service__in=[requested_callee_service, ""])  # type: ignore
        if requested_callee_method is not None:
            if requested_callee_method == "":
                q &= Q(callee_method="")
            else:
                q &= Q(callee_method__in=[requested_callee_method, ""])  # type: ignore

        queryset = (
            CodeRedefinedConfigRelation.objects.filter(q)
            .annotate(
                method_len=Length("callee_method"),
                service_len=Length("callee_service"),
                server_len=Length("callee_server"),
            )
            .order_by("-method_len", "-service_len", "-server_len")
        )
        return list(
            queryset.values(
                "id",
                "kind",
                "service_name",
                "callee_server",
                "callee_service",
                "callee_method",
                "code_type_rules",
                "enabled",
                "updated_at",
                "updated_by",
            )
        )


class SetCodeRedefinedRuleResource(Resource):
    RequestSerializer = SetCodeRedefinedRuleRequestSerializer

    def perform_request(self, validated_request_data):
        bk_biz_id: int = validated_request_data["bk_biz_id"]
        app_name: str = validated_request_data["app_name"]
        service_name: str = validated_request_data["service_name"]
        kind: str = validated_request_data["kind"]
        rules: list = validated_request_data["rules"]

        username = get_request_username()

        # 获取当前数据库中的所有规则
        base_filters = {
            "bk_biz_id": bk_biz_id,
            "app_name": app_name,
            "service_name": service_name,
            "kind": kind,
        }
        existing_rules = CodeRedefinedConfigRelation.objects.filter(**base_filters)

        # 构建前端传入规则的唯一标识集合
        incoming_rule_keys = set()
        for rule in rules:
            rule_key = (rule["callee_server"], rule["callee_service"], rule["callee_method"])
            incoming_rule_keys.add(rule_key)

        # 处理每个传入的规则（新增/修改）
        for rule in rules:
            callee_server: str = rule["callee_server"]
            callee_service: str = rule["callee_service"]
            callee_method: str = rule["callee_method"]
            code_type_rules = rule["code_type_rules"]
            enabled: bool = rule.get("enabled", True)

            # 使用组合键进行 upsert
            filters = {
                **base_filters,
                "callee_server": callee_server,
                "callee_service": callee_service,
                "callee_method": callee_method,
            }

            # 只更新必要字段，不更新组合键字段
            defaults = {
                "code_type_rules": code_type_rules,
                "enabled": enabled,
                "updated_by": username,
            }

            obj, created = CodeRedefinedConfigRelation.objects.update_or_create(defaults=defaults, **filters)
            if created:
                CodeRedefinedConfigRelation.objects.filter(id=obj.id).update(created_by=username)

        # 删除前端没有传递的规则
        rules_to_delete = []
        for existing_rule in existing_rules:
            existing_key = (existing_rule.callee_server, existing_rule.callee_service, existing_rule.callee_method)
            if existing_key not in incoming_rule_keys:
                rules_to_delete.append(existing_rule.id)

        if rules_to_delete:
            CodeRedefinedConfigRelation.objects.filter(id__in=rules_to_delete).delete()

        # 同步下发：汇总整个应用的 code_relabel 列表并下发到 APM
        self.publish_code_relabel_to_apm(bk_biz_id, app_name)

        return {}

    @classmethod
    def publish_code_relabel_to_apm(cls, bk_biz_id: int, app_name: str) -> None:
        code_relabel_config = cls.build_code_relabel_config(bk_biz_id, app_name)

        # 下发到 APM 模块
        api.apm_api.release_app_config(
            {
                "bk_biz_id": bk_biz_id,
                "app_name": app_name,
                "code_relabel_config": code_relabel_config,
            }
        )

    @classmethod
    def build_code_relabel_config(cls, bk_biz_id: int, app_name: str) -> list[dict[str, Any]]:
        """将 DB 规则聚合为 collector 的 code_relabel 列表结构。

        规则：
        - kind=caller → metrics: [定义指标名]
        - kind=callee → metrics: [定义指标名]
        - source = service_name（本服务）
        - services[].name = "callee_server;callee_service;callee_method"；空串/空行统一转 "*"
        - codes[].rule 透传；codes[].target 固定 {action:"upsert", label:"code_type", value in [success,exception,timeout]}
        """
        metrics_map = {
            "caller": [
                "rpc_client_handled_total",
                "rpc_client_handled_seconds_bucket",
                "rpc_client_handled_seconds_count",
                "rpc_client_handled_seconds_sum",
            ],
            "callee": [
                "rpc_server_handled_total",
                "rpc_server_handled_seconds_bucket",
                "rpc_server_handled_seconds_count",
                "rpc_server_handled_seconds_sum",
            ],
        }

        def star_if_empty(value: str | None) -> str:
            if value is None:
                return "*"
            text = str(value).strip()
            return text if text else "*"

        queryset = CodeRedefinedConfigRelation.objects.filter(
            bk_biz_id=bk_biz_id, app_name=app_name, enabled=True
        ).order_by("service_name", "kind", "callee_server", "callee_service", "callee_method")

        grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for item in queryset:
            name = ";".join(
                [
                    # 被调类型已通过 source 限制服务名，callee_server 设置为 "*"，
                    # 避免部分上报缺失 callee_server 字段导致无法匹配的问题。
                    star_if_empty("" if item.is_callee() else item.callee_server),
                    star_if_empty(item.callee_service),
                    star_if_empty(item.callee_method),
                ]
            )

            codes: list[dict[str, Any]] = []
            for code_type_key in ("success", "exception", "timeout"):
                rule_val = (item.code_type_rules or {}).get(code_type_key)
                if rule_val is None:
                    continue
                rule_text = str(rule_val).strip()
                if not rule_text:
                    continue
                codes.append(
                    {
                        "rule": rule_text,
                        "target": {"action": "upsert", "label": "code_type", "value": code_type_key},
                    }
                )

            if not codes:
                continue

            entry = {"name": name, "codes": codes}
            group_key = (item.service_name, item.kind)
            grouped.setdefault(group_key, []).append(entry)

        # 组装最终列表
        code_relabel: list[dict[str, Any]] = []
        for (service_name, kind), services in grouped.items():
            metrics = metrics_map.get(kind)
            if not metrics:
                continue
            code_relabel.append({"metrics": metrics, "source": service_name, "services": services})

        return code_relabel


class DeleteCodeRedefinedRuleResource(Resource):
    RequestSerializer = DeleteCodeRedefinedRuleRequestSerializer

    def perform_request(self, validated_request_data):
        bk_biz_id: int = validated_request_data["bk_biz_id"]
        app_name: str = validated_request_data["app_name"]
        service_name: str = validated_request_data["service_name"]
        kind: str = validated_request_data["kind"]

        # 构建精确匹配条件
        filters = {
            "bk_biz_id": bk_biz_id,
            "app_name": app_name,
            "service_name": service_name,
            "kind": kind,
        }

        # 添加可选的被调字段进行精确匹配
        if "callee_server" in validated_request_data:
            filters["callee_server"] = validated_request_data["callee_server"]
        if "callee_service" in validated_request_data:
            filters["callee_service"] = validated_request_data["callee_service"]
        if "callee_method" in validated_request_data:
            filters["callee_method"] = validated_request_data["callee_method"]

        try:
            instance = CodeRedefinedConfigRelation.objects.get(**filters)
        except CodeRedefinedConfigRelation.DoesNotExist:
            # 按需求可以视为已删除
            return

        instance.delete()

        # 同步下发删除后的配置
        SetCodeRedefinedRuleResource.publish_code_relabel_to_apm(bk_biz_id, app_name)
        return


class GetCodeRemarksResource(Resource):
    """
    获取返回码备注

    维度：业务 + 应用 + 服务 + 调用类型(kind)
    存储：ApmMetaConfig ，config_key 随 kind 变化
    """

    RequestSerializer = BaseCodeRedefinedRequestSerializer

    CONFIG_KEY_MAP = {"caller": "code_remarks_caller", "callee": "code_remarks_callee"}

    def perform_request(self, validated_request_data):
        bk_biz_id: int = validated_request_data["bk_biz_id"]
        app_name: str = validated_request_data["app_name"]
        service_name: str = validated_request_data["service_name"]
        kind: str = validated_request_data["kind"]

        config_key = self.CONFIG_KEY_MAP.get(kind)
        if not config_key:
            return {}

        instance = ApmMetaConfig.get_service_config_value(bk_biz_id, app_name, service_name, config_key)
        return instance.config_value if instance else {}


class SetCodeRemarkResource(Resource):
    RequestSerializer = SetCodeRemarkRequestSerializer

    CONFIG_KEY_MAP = {"caller": "code_remarks_caller", "callee": "code_remarks_callee"}

    def perform_request(self, validated_request_data):
        bk_biz_id: int = validated_request_data["bk_biz_id"]
        app_name: str = validated_request_data["app_name"]
        service_name: str = validated_request_data["service_name"]
        kind: str = validated_request_data["kind"]
        code: str = str(validated_request_data["code"]).strip()
        remark: str = str(validated_request_data.get("remark", "")).strip()

        config_key = self.CONFIG_KEY_MAP.get(kind)
        if not config_key:
            return {}

        exists = ApmMetaConfig.get_service_config_value(bk_biz_id, app_name, service_name, config_key)
        data = (exists.config_value if exists else {}) or {}

        # 设置/覆盖/删除（空串即删除该码的备注）
        if remark:
            data[code] = remark
        else:
            if code in data:
                del data[code]

        ApmMetaConfig.service_config_setup(bk_biz_id, app_name, service_name, config_key, data)
        return {}
