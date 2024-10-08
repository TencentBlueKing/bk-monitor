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
import datetime
import functools
import itertools
import json
import operator
import re
from multiprocessing.pool import ApplyResult

from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy as _lazy
from rest_framework import serializers

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
    LogServiceRelation,
    UriServiceRelation,
)
from apm_web.profile.doris.querier import QueryTemplate
from apm_web.serializers import ApplicationListSerializer, ServiceApdexConfigSerializer
from apm_web.service.serializers import (
    AppServiceRelationSerializer,
    LogServiceRelationOutputSerializer,
    ServiceConfigSerializer,
)
from apm_web.topo.handle.relation.relation_metric import RelationMetricHandler
from bkmonitor.commons.tools import batch_request
from bkmonitor.utils.request import get_request_username
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

    def get_operate_record(self, bk_biz_id, app_name, service_name):
        """获取操作记录"""
        relation = AppServiceRelation.objects.filter(
            bk_biz_id=bk_biz_id, app_name=app_name, service_name=service_name
        ).first()
        return {
            "created_at": relation.created_at if relation else None,
            "updated_at": relation.updated_at if relation else None,
            "created_by": relation.created_by if relation else None,
            "updated_by": relation.updated_by if relation else None,
        }

    def get_cmdb_relation_info(self, bk_biz_id, app_name, service_name):
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
        }

    def get_log_relation_info(self, bk_biz_id, app_name, service_name):
        query = LogServiceRelation.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name, service_name=service_name)
        if query.exists():
            return LogServiceRelationOutputSerializer(instance=query.first()).data

        return {}

    def get_app_relation_info(self, bk_biz_id, app_name, service_name):
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

    def get_uri_relation_info(self, bk_biz_id, app_name, service_name):
        query = UriServiceRelation.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name, service_name=service_name)
        if not query.exists():
            return []

        return list(query.order_by("rank").values("id", "uri", "rank"))

    def get_apdex_relation_info(self, bk_biz_id, app_name, service_name, topo_node):
        instance = ServiceHandler.get_apdex_relation_info(bk_biz_id, app_name, service_name, topo_node)
        if not instance:
            return {}
        return ServiceApdexConfigSerializer(instance=instance).data

    def get_profiling_info(self, app, bk_biz_id, app_name, service_name, start_time, end_time):
        """获取服务的 profiling 状态"""

        res = {}
        res["application_id"] = app.application_id

        res["is_enabled_profiling"] = app.is_enabled_profiling
        if app.is_enabled_profiling:
            # 获取此服务是否有 Profiling 数据
            count = QueryTemplate(bk_biz_id, app_name).get_service_count(start_time, end_time, service_name)
            res["is_profiling_data_normal"] = bool(count)
        else:
            res["is_profiling_data_normal"] = False

        return res

    def get_labels(self, bk_biz_id, app_name, service_name):
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
        topo_node_res = pool.apply_async(ServiceHandler.list_nodes, kwds={"bk_biz_id": bk_biz_id, "app_name": app_name})
        instance_res = pool.apply_async(RelationMetricHandler.list_instances, kwds=query_instance_param)
        app_relation = pool.apply_async(self.get_app_relation_info, args=(bk_biz_id, app_name, service_name))
        log_relation = pool.apply_async(self.get_log_relation_info, args=(bk_biz_id, app_name, service_name))
        cmdb_relation = pool.apply_async(self.get_cmdb_relation_info, args=(bk_biz_id, app_name, service_name))
        uri_relation = pool.apply_async(self.get_uri_relation_info, args=(bk_biz_id, app_name, service_name))
        operate_record = pool.apply_async(self.get_operate_record, args=(bk_biz_id, app_name, service_name))
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
        service_info.update(operate_record.get())
        if isinstance(profiling_info, ApplyResult):
            execute_res = profiling_info.get()
            if isinstance(execute_res, dict):
                service_info.update(execute_res)
        resp = topo_node_res.get()

        service_info["relation"] = {
            "app_relation": app_relation.get(),
            "log_relation": log_relation.get(),
            "cmdb_relation": cmdb_relation.get(),
            "uri_relation": uri_relation.get(),
            "apdex_relation": self.get_apdex_relation_info(bk_biz_id, app_name, service_name, resp),
        }

        for service in resp:
            if service["topo_key"] == validate_data["service_name"]:
                service_info.update(service)
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
        service_info["labels"] = labels
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
        update_relation(validated_request_data.get("log_relation"), LogServiceRelation)
        update_relation(validated_request_data.get("app_relation"), AppServiceRelation)

        if validated_request_data.get("apdex_relation"):
            # 重新获取服务的类型 避免相同服务名类型更变导致统计出错
            apdex_key = ServiceHandler.get_service_apdex_key(bk_biz_id, app_name, service_name)
            validated_request_data["apdex_relation"]["apdex_key"] = apdex_key
        update_relation(validated_request_data.get("apdex_relation"), ApdexServiceRelation)

        self.update_uri(bk_biz_id, app_name, service_name, validated_request_data["uri_relation"])
        if validated_request_data.get("labels"):
            self.update_labels(bk_biz_id, app_name, service_name, validated_request_data["labels"])

        # 下发修改后的配置
        application_id = Application.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).get().application_id
        from apm_web.tasks import update_application_config

        update_application_config.delay(application_id)

    def update_uri(self, bk_biz_id, app_name, service_name, uri_relations):
        if len(set(uri_relations)) != len(uri_relations):
            raise ValueError(_lazy("uri含有重复配置项"))

        filter_params = {"bk_biz_id": bk_biz_id, "app_name": app_name, "service_name": service_name}
        relations = UriServiceRelation.objects.filter(**filter_params).order_by("rank")

        delete_uris = {
            k: [g.id for g in group] for k, group in itertools.groupby(relations, operator.attrgetter("uri"))
        }

        for index, item in enumerate(uri_relations):
            qs = relations.filter(uri=item)
            if qs.exists():
                qs.update(rank=index)
                del delete_uris[item]
            else:
                UriServiceRelation.objects.create(uri=item, rank=index, **filter_params)

        UriServiceRelation.objects.filter(id__in=itertools.chain(*[ids for _, ids in delete_uris.items()])).delete()

    def update(self, bk_biz_id, app_name, service_name, relation, model):
        if not relation:
            # 删除原来的关联
            model.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name, service_name=service_name).delete()
        else:
            qs = model.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name, service_name=service_name)
            username = get_request_username()

            if qs.exists():
                qs.update(updated_by=username, **relation)
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
    TIME_DELTA = 1

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        app_name = serializers.CharField()
        service_name = serializers.CharField()

    def perform_request(self, data):
        app = Application.objects.get(bk_biz_id=data["bk_biz_id"], app_name=data["app_name"])
        if not app:
            raise ValueError(_("应用不存在"))

        end_time = datetime.datetime.now()
        start_time = end_time - datetime.timedelta(days=self.TIME_DELTA)

        return SpanHandler.get_span_uris(app, start_time, end_time, service_name=data["service_name"])


class AppQueryByIndexSetResource(Resource):
    class RequestSerializer(serializers.Serializer):
        index_set_id = serializers.IntegerField()

    def perform_request(self, data):
        relations = LogServiceRelation.objects.filter(
            log_type=ServiceRelationLogTypeChoices.BK_LOG, value=data["index_set_id"]
        )
        res = []
        for relation in relations:
            res.append({"bk_biz_id": relation.bk_biz_id, "app_name": relation.app_name})

        return res
