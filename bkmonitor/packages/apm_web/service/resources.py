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
import operator
import re
from multiprocessing.pool import ApplyResult
from typing import Any
from datetime import timedelta

import arrow
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy
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
)
from apm_web.profile.doris.querier import QueryTemplate
from apm_web.serializers import ApplicationListSerializer, ServiceApdexConfigSerializer
from apm_web.service.mock_data import (
    API_PIPELINE_OVERVIEW_RESPONSE,
    API_LIST_PIPELINE_RESPONSE,
    API_CODE_REDEFINED_RULE_LIST_RESPONSE,
)
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


class ServiceInfoResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")
        service_name = serializers.CharField(label="服务")
        start_time = serializers.IntegerField(required=False, default=None, label="数据开始时间")
        end_time = serializers.IntegerField(required=False, default=None, label="数据结束时间")

    @classmethod
    def fill_operate_record(cls, service_info: dict[str, Any], relation_infos: list[dict[str, Any]]):
        """获取操作记录"""
        default_username = "system"

        def bigger_than_update(lft_info, rgt_info):
            lft_time = lft_info.get("updated_at") or 0
            rgt_time = rgt_info.get("updated_at") or 0
            if arrow.get(lft_time) > arrow.get(rgt_time):
                rgt_info["updated_at"] = lft_info.get("updated_at")
                rgt_info["updated_by"] = lft_info.get("updated_by") or default_username

        for relation_info in relation_infos:
            bigger_than_update(relation_info, service_info)

        # 如果没有，则设置默认值
        service_info["created_at"] = service_info.get("created_at")
        service_info["created_by"] = service_info.get("created_by") or default_username
        service_info["updated_at"] = service_info.get("updated_at")
        service_info["updated_by"] = service_info.get("updated_by") or default_username

    @classmethod
    def get_cmdb_relation_info(cls, bk_biz_id, app_name, service_name):
        query = CMDBServiceRelation.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name, service_name=service_name)
        if not query.exists():
            return {}

        instance = query.first()
        bk_biz_id = instance.bk_biz_id
        template_id = instance.template_id
        template = {t["id"]: t for t in CMDBServiceTemplateResource.get_templates(bk_biz_id)}.get(template_id, {})

        return {
            "template_id": template.get("id"),
            "template_name": template.get("name"),
            "first_category": template.get("first_category"),
            "second_category": template.get("second_category"),
            "updated_by": instance.updated_by,
            "updated_at": instance.updated_at,
        }

    @classmethod
    def get_log_relation_info(cls, bk_biz_id, app_name, service_name):
        query = LogServiceRelation.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name, service_name=service_name)
        if query.exists():
            return LogServiceRelationOutputSerializer(instance=query.first()).data

        return {}

    @classmethod
    def get_log_relation_info_list(cls, bk_biz_id, app_name, service_name):
        relations = LogServiceRelation.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name, service_name=service_name)
        return LogServiceRelationOutputSerializer(instance=relations, many=True).data

    @classmethod
    def get_app_relation_info(cls, bk_biz_id, app_name, service_name):
        query = AppServiceRelation.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name, service_name=service_name)
        if query.exists():
            instance = query.first()
            res = AppServiceRelationSerializer(instance=instance).data
            relate_bk_biz_id = instance.relate_bk_biz_id
            biz = {i.bk_biz_id: i for i in api.cmdb.get_business(bk_biz_ids=[relate_bk_biz_id])}.get(relate_bk_biz_id)
            res["relate_bk_biz_name"] = biz.bk_biz_name if isinstance(biz, Business) else None
            res["application_id"] = instance.relate_app_name
            return res

        return {}

    @classmethod
    def get_uri_relation_info(cls, bk_biz_id, app_name, service_name):
        query = UriServiceRelation.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name, service_name=service_name)
        if not query.exists():
            return []

        return list(query.order_by("rank").values("id", "uri", "rank", "updated_at", "updated_by"))

    @classmethod
    def get_event_relation_info(cls, bk_biz_id: int, app_name: str, service_name: str) -> list[dict[str, Any]]:
        return list(
            EventServiceRelation.objects.filter(
                bk_biz_id=bk_biz_id, app_name=app_name, service_name=service_name
            ).values("id", "table", "relations", "options", "updated_at", "updated_by")
        )

    @classmethod
    def get_apdex_relation_info(cls, bk_biz_id, app_name, service_name, topo_node):
        instance = ServiceHandler.get_apdex_relation_info(bk_biz_id, app_name, service_name, topo_node)
        if not instance:
            return {}
        return ServiceApdexConfigSerializer(instance=instance).data

    @classmethod
    def get_profiling_info(cls, app, bk_biz_id, app_name, service_name, start_time, end_time):
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
    def get_labels(cls, bk_biz_id, app_name, service_name):
        config_instance = ApmMetaConfig.get_service_config_value(bk_biz_id, app_name, service_name, "labels")
        if config_instance:
            return json.loads(config_instance.config_value)
        return []

    def perform_request(self, validate_data):
        # 获取请求数据
        bk_biz_id = validate_data["bk_biz_id"]
        app_name = validate_data["app_name"]
        service_name = validate_data["service_name"]
        app = Application.objects.get(bk_biz_id=bk_biz_id, app_name=app_name)

        if not validate_data["start_time"] and not validate_data["end_time"]:
            start_time, end_time = get_datetime_range(
                period="day",
                distance=app.es_retention,
                rounding=False,
            )
            validate_data["start_time"] = int(start_time.timestamp())
            validate_data["end_time"] = int(end_time.timestamp())

        query_instance_param = {
            "bk_biz_id": bk_biz_id,
            "app_name": app_name,
            "service_name": service_name,
            "start_time": validate_data["start_time"],
            "end_time": validate_data["end_time"],
        }
        pool = ThreadPool()
        topo_node_res = pool.apply_async(
            ServiceHandler.list_nodes, kwds={"bk_biz_id": bk_biz_id, "app_name": app_name, "service_name": service_name}
        )
        instance_res = pool.apply_async(RelationMetricHandler.list_instances, kwds=query_instance_param)
        app_relation = pool.apply_async(self.get_app_relation_info, args=(bk_biz_id, app_name, service_name))
        log_relation_list = pool.apply_async(self.get_log_relation_info_list, args=(bk_biz_id, app_name, service_name))
        cmdb_relation = pool.apply_async(self.get_cmdb_relation_info, args=(bk_biz_id, app_name, service_name))
        event_relation = pool.apply_async(self.get_event_relation_info, args=(bk_biz_id, app_name, service_name))
        uri_relation = pool.apply_async(self.get_uri_relation_info, args=(bk_biz_id, app_name, service_name))
        labels = pool.apply_async(self.get_labels, args=(bk_biz_id, app_name, service_name))

        profiling_info = {}
        if validate_data.get("start_time") and validate_data.get("end_time"):
            profiling_info = pool.apply_async(
                self.get_profiling_info,
                args=(app, bk_biz_id, app_name, service_name, validate_data["start_time"], validate_data["end_time"]),
            )
        pool.close()
        pool.join()

        # 获取服务信息
        service_info = {"extra_data": {}, "topo_key": service_name}
        resp = topo_node_res.get()
        for service in resp:
            if service["topo_key"] == validate_data["service_name"]:
                service_info.update(service)

        app_relation_info = app_relation.get()
        log_relation_info_list = log_relation_list.get()
        cmdb_relation_info = cmdb_relation.get()
        event_relation_info = event_relation.get()
        uri_relation_info = uri_relation.get()
        apdex_info = self.get_apdex_relation_info(bk_biz_id, app_name, service_name, resp)
        self.fill_operate_record(
            service_info,
            [
                apdex_info,
                app_relation_info,
                log_relation_info_list[0] if log_relation_info_list else {},
                cmdb_relation_info,
                *event_relation_info,
                *uri_relation_info,
            ],
        )
        if isinstance(profiling_info, ApplyResult):
            execute_res = profiling_info.get()
            if isinstance(execute_res, dict):
                service_info.update(execute_res)

        service_info["relation"] = {
            "app_relation": app_relation_info,
            "log_relation_list": log_relation_info_list,
            "cmdb_relation": cmdb_relation_info,
            "event_relation": event_relation_info,
            "uri_relation": uri_relation_info,
            "apdex_relation": apdex_info,
        }

        # 一级目录名称
        category_key = service_info["extra_data"].get("category", "")
        service_info["extra_data"]["category_name"] = CategoryEnum.get_label_by_key(category_key)
        # HTTP 兼容
        if service_info["extra_data"].get("category") == "http":
            service_info["extra_data"]["predicate_value"] = ""
        # 增加 icon 信息
        service_info["extra_data"].update({"category_icon": "", "predicate_value_icon": ""})
        first_category = service_info["extra_data"].get("category")
        if first_category:
            service_info["extra_data"]["category_icon"] = get_icon(first_category)
        second_category = service_info["extra_data"].get("predicate_value")
        if second_category:
            service_info["extra_data"]["predicate_value_icon"] = get_icon(second_category)
        # 实例数
        instances = instance_res.get()
        service_info["instance_count"] = len(instances)
        # 自定义标签
        service_info["labels"] = labels.get()
        # 响应
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
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")
        service_name = serializers.CharField(label="服务")
        req_type = serializers.ChoiceField(label="请求类型", choices=ServiceDetailReqTypeChoices.choices())
        extras = serializers.JSONField(label="附加数据")

    def get_instance(self, bk_biz_id, app_name, service_name, instance_id):
        try:
            return self.queryset.get(id=instance_id, bk_biz_id=bk_biz_id, app_name=app_name, service_name=service_name)
        except self.queryset.model.DoesNotExist:
            raise ValueError(_lazy("资源不存在"))

    def build_instance_response_data(self, bk_biz_id: int, app_name: str, service_name: str, data: dict):
        return data

    def build_multi_response_data(self, bk_biz_id: int, app_name: str, service_name: str, data: list):
        return data

    def handle_delete(self, bk_biz_id: int, app_name: str, service_name: str, extras: dict):
        instance_id = extras.pop("id", None)
        instance = self.get_instance(bk_biz_id, app_name, service_name, instance_id)
        instance.delete()
        return

    def handle_update(self, bk_biz_id: int, app_name: str, service_name: str, extras: dict):
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

    def handle_list(self, bk_biz_id: int, app_name: str, service_name: str):
        queryset = self.queryset.filter(bk_biz_id=bk_biz_id, app_name=app_name, service_name=service_name)
        serializer = self.serializer_class(queryset, many=True)
        return self.build_multi_response_data(bk_biz_id, app_name, service_name, serializer.data)

    def perform_request(self, validated_request_data):
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

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        app_name = validated_request_data["app_name"]
        service_name = validated_request_data["service_name"]

        update_relation = functools.partial(self.update, bk_biz_id, app_name, service_name)

        update_relation(validated_request_data.get("cmdb_relation"), CMDBServiceRelation)
        self.update_log_relations(bk_biz_id, app_name, service_name, validated_request_data.get("log_relation_list"))
        update_relation(validated_request_data.get("app_relation"), AppServiceRelation)

        if validated_request_data.get("apdex_relation"):
            # 重新获取服务的类型 避免相同服务名类型更变导致统计出错
            apdex_key = ServiceHandler.get_service_apdex_key(bk_biz_id, app_name, service_name)
            validated_request_data["apdex_relation"]["apdex_key"] = apdex_key
        update_relation(validated_request_data.get("apdex_relation"), ApdexServiceRelation)

        self.update_event_relations(bk_biz_id, app_name, service_name, validated_request_data["event_relation"])
        self.update_uri(bk_biz_id, app_name, service_name, validated_request_data["uri_relation"])
        if validated_request_data.get("labels"):
            self.update_labels(bk_biz_id, app_name, service_name, validated_request_data["labels"])

        # 下发修改后的配置
        application = Application.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).get()
        from apm_web.tasks import update_application_config

        update_application_config.delay(
            application.bk_biz_id, application.app_name, {"service_configs": application.get_service_transfer_config()}
        )

    def update_uri(self, bk_biz_id, app_name, service_name, uri_relations):
        if len(set(uri_relations)) != len(uri_relations):
            raise ValueError(_lazy("uri含有重复配置项"))

        filter_params = {"bk_biz_id": bk_biz_id, "app_name": app_name, "service_name": service_name}
        relations = UriServiceRelation.objects.filter(**filter_params).order_by("rank")

        delete_uris = {
            k: [g.id for g in group] for k, group in itertools.groupby(relations, operator.attrgetter("uri"))
        }

        username = get_request_username()
        update_at = arrow.now().datetime
        for index, item in enumerate(uri_relations):
            qs = relations.filter(uri=item)
            if qs.exists():
                qs.update(rank=index, updated_by=username, updated_at=update_at)
                del delete_uris[item]
            else:
                UriServiceRelation.objects.create(uri=item, rank=index, **filter_params)

        UriServiceRelation.objects.filter(id__in=itertools.chain(*[ids for _, ids in delete_uris.items()])).delete()

    @classmethod
    def update_log_relations(cls, bk_biz_id: int, app_name: str, service_name: str, log_relation_list: list):
        if not log_relation_list:
            LogServiceRelation.objects.filter(
                bk_biz_id=bk_biz_id, app_name=app_name, service_name=service_name
            ).delete()
            return

        # 检查是否有重复的related_bk_biz_id，并合并value_list
        unique_relations = {}
        for request_relation in log_relation_list:
            related_bk_biz_id = request_relation.get("related_bk_biz_id")
            if related_bk_biz_id in unique_relations:
                # 合并value_list
                existing_value_list = unique_relations[related_bk_biz_id].get("value_list", [])
                new_value_list = request_relation.get("value_list", [])
                unique_relations[related_bk_biz_id]["value_list"] = existing_value_list + new_value_list
            else:
                unique_relations[related_bk_biz_id] = request_relation

        # 将合并后的结果转换为列表
        log_relation_list = list(unique_relations.values())

        # 获取现有记录的主键映射
        existing_relations = LogServiceRelation.objects.filter(
            bk_biz_id=bk_biz_id, app_name=app_name, service_name=service_name
        ).values_list("related_bk_biz_id", "id")

        existing_id_map = {related_bk_biz_id: id for related_bk_biz_id, id in existing_relations}

        to_update = []
        to_create = []
        to_delete = [id for _, id in existing_relations]
        username = get_request_username()
        update_time = arrow.now().datetime

        for request_relation in log_relation_list:
            related_bk_biz_id = request_relation.get("related_bk_biz_id")
            if related_bk_biz_id in existing_id_map:
                if request_relation.get("value_list"):
                    # 否则更新记录
                    instance = LogServiceRelation(
                        id=existing_id_map[related_bk_biz_id],
                        updated_by=username,
                        updated_at=update_time,
                        **request_relation,
                    )
                    to_update.append(instance)
                    # 如果记录不需要更新或者 value_list 为空，则需要删除记录
                    to_delete.remove(existing_id_map[related_bk_biz_id])
            else:
                # 创建记录
                instance = LogServiceRelation(
                    bk_biz_id=bk_biz_id,
                    app_name=app_name,
                    service_name=service_name,
                    updated_by=username,
                    created_by=username,
                    **request_relation,
                )
                to_create.append(instance)

        if to_update:
            LogServiceRelation.objects.bulk_update(
                to_update, fields=["updated_by", "updated_at", "value_list"], batch_size=100
            )
        if to_create:
            LogServiceRelation.objects.bulk_create(to_create, batch_size=100)
        if to_delete:
            LogServiceRelation.objects.filter(id__in=to_delete).delete()

    @classmethod
    def update_event_relations(
        cls, bk_biz_id: int, app_name: str, service_name: str, event_relations: list[dict[str, Any]]
    ):
        if not event_relations:
            return

        table_relation_map: dict[str, dict[str, Any]] = {
            relation["table"]: relation
            for relation in ServiceInfoResource.get_event_relation_info(bk_biz_id, app_name, service_name)
        }

        username: str = get_request_username()
        to_be_created_relations: list[EventServiceRelation] = []
        to_be_updated_relations: list[EventServiceRelation] = []
        for relation in event_relations:
            exists_relation: dict[str, Any] | None = table_relation_map.get(relation["table"])
            if exists_relation:
                to_be_updated_relations.append(
                    EventServiceRelation(
                        id=exists_relation["id"], updated_by=username, updated_at=arrow.now().datetime, **relation
                    )
                )
            else:
                to_be_created_relations.append(
                    EventServiceRelation(
                        bk_biz_id=bk_biz_id,
                        app_name=app_name,
                        service_name=service_name,
                        updated_by=username,
                        created_by=username,
                        **relation,
                    )
                )

        if to_be_created_relations:
            EventServiceRelation.objects.bulk_create(to_be_created_relations, batch_size=100)
        if to_be_updated_relations:
            EventServiceRelation.objects.bulk_update(
                to_be_updated_relations, batch_size=100, fields=["updated_at", "updated_by", "relations", "options"]
            )

    def update(self, bk_biz_id, app_name, service_name, relation, model):
        if not relation:
            # 删除原来的关联
            model.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name, service_name=service_name).delete()
        else:
            qs = model.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name, service_name=service_name)
            username = get_request_username()

            if qs.exists():
                qs.update(updated_by=username, updated_at=arrow.now().datetime, **relation)
            else:
                model.objects.create(
                    bk_biz_id=bk_biz_id,
                    app_name=app_name,
                    service_name=service_name,
                    updated_by=username,
                    created_by=username,
                    **relation,
                )

    def update_labels(self, bk_biz_id, app_name, service_name, labels):
        ApmMetaConfig.service_config_setup(
            bk_biz_id,
            app_name,
            service_name,
            "labels",
            json.dumps(labels),
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
        if validated_request_data["is_mock"]:
            return API_PIPELINE_OVERVIEW_RESPONSE

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
        if validated_request_data.get("is_mock", False):
            return API_LIST_PIPELINE_RESPONSE

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
        if validated_request_data.get("is_mock", False):
            return API_CODE_REDEFINED_RULE_LIST_RESPONSE
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

        # 处理每个规则
        for rule in rules:
            callee_server: str = rule["callee_server"]
            callee_service: str = rule["callee_service"]
            callee_method: str = rule["callee_method"]
            code_type_rules = rule["code_type_rules"]
            enabled: bool = rule.get("enabled", True)

            # 使用组合键进行 upsert
            filters = {
                "bk_biz_id": bk_biz_id,
                "app_name": app_name,
                "service_name": service_name,
                "kind": kind,
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
                    star_if_empty(item.callee_server),
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
