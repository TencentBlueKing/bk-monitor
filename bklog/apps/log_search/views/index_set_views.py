"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

import json

from django.conf import settings
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.response import Response

from apps.exceptions import ValidationError
from apps.generic import ModelViewSet
from apps.iam import ActionEnum, ResourceEnum
from apps.iam.handlers.drf import (
    BusinessActionPermission,
    InstanceActionPermission,
    ViewBusinessPermission,
    insert_permission_field,
)
from apps.log_clustering.models import ClusteringConfig
from apps.log_search.constants import TimeFieldTypeEnum, TimeFieldUnitEnum
from apps.log_search.exceptions import BkJwtVerifyException, IndexSetNotEmptyException
from apps.log_search.handlers.index_set import BaseIndexSetHandler, IndexSetHandler
from apps.log_search.models import LogIndexSet, LogIndexSetData, Scenario
from apps.log_search.permission import Permission
from apps.log_search.serializers import (
    CreateIndexSetTagSerializer,
    CreateOrUpdateDesensitizeConfigSerializer,
    DesensitizeConfigStateSerializer,
    ESRouterListSerializer,
    IndexSetAddTagSerializer,
    IndexSetDeleteTagSerializer,
    StorageUsageSerializer,
    UserFavoriteSerializer,
    UserSearchSerializer,
    QueryByDataIdSerializer,
)
from apps.log_search.tasks.bkdata import sync_auth_status
from apps.utils.drf import detail_route, list_route
from bkm_space.serializers import SpaceUIDField


class IndexSetViewSet(ModelViewSet):
    """
    索引集管理
    """

    lookup_field = "index_set_id"
    model = LogIndexSet
    search_fields = ("index_set_name",)
    lookup_value_regex = "[^/]+"
    filter_fields_exclude = ["target_fields", "sort_fields"]

    def get_permissions(self):
        try:
            auth_info = Permission.get_auth_info(self.request)
            # ESQUERY白名单不需要鉴权
            if auth_info["bk_app_code"] in settings.ESQUERY_WHITE_LIST:
                return []
        except Exception:  # pylint: disable=broad-except
            pass
        if self.action in [
            "mark_favorite",
            "cancel_favorite",
            "user_search",
            "user_favorite",
            "space",
            "query_by_dataid",
        ]:
            return []
        if self.action in ["create", "replace"]:
            return [BusinessActionPermission([ActionEnum.CREATE_INDICES])]
        if self.action in ["update", "destroy"]:
            return [InstanceActionPermission([ActionEnum.MANAGE_INDICES], ResourceEnum.INDICES)]
        return [ViewBusinessPermission()]

    def get_queryset(self):
        qs = LogIndexSet.objects.filter(collector_config_id__isnull=True)
        if self.request.query_params.get("index_set_id_list", None):
            index_set_id_list = self.request.query_params.get("index_set_id_list").split(",")
            return qs.filter(index_set_id__in=index_set_id_list)
        return qs

    def get_serializer_class(self, *args, **kwargs):
        serializer_class = super().get_serializer_class()

        class CustomSerializer(serializer_class):
            view_roles = serializers.ListField(default=[])
            bkdata_project_id = serializers.IntegerField(read_only=True)
            indexes = serializers.ListField(allow_empty=True)
            is_trace_log = serializers.BooleanField(required=False, default=False)
            time_field = serializers.CharField(required=False, default=None)
            time_field_type = serializers.ChoiceField(
                required=False, default=None, choices=TimeFieldTypeEnum.get_choices()
            )
            time_field_unit = serializers.ChoiceField(
                required=False, default=None, choices=TimeFieldUnitEnum.get_choices()
            )
            tag_ids = serializers.ListField(required=False, default=[], child=serializers.IntegerField())

            target_fields = serializers.ListField(required=False, default=[])
            sort_fields = serializers.ListField(required=False, default=[])

            class Meta:
                model = LogIndexSet
                fields = "__all__"

            def validate_indexes(self, value):
                if value:
                    return value
                raise IndexSetNotEmptyException

        class CreateSerializer(CustomSerializer):
            index_set_name = serializers.CharField(required=True)
            result_table_id = serializers.CharField(required=False)
            storage_cluster_id = serializers.IntegerField(required=False)
            category_id = serializers.CharField(required=True)
            scenario_id = serializers.CharField(required=True)
            space_uid = SpaceUIDField(label=_("空间唯一标识"), required=True)
            bkdata_auth_url = serializers.ReadOnlyField()
            is_editable = serializers.BooleanField(required=False, default=True)

            def validate(self, attrs):
                attrs = super().validate(attrs)

                scenario_id = attrs["scenario_id"]
                if scenario_id == Scenario.ES and not attrs.get("storage_cluster_id"):
                    raise ValidationError(_("集群ID不能为空"))
                return attrs

        class UpdateSerializer(CustomSerializer):
            index_set_name = serializers.CharField(required=True)
            storage_cluster_id = serializers.IntegerField(required=False, default=None)
            scenario_id = serializers.CharField(required=True)
            category_id = serializers.CharField(required=True)
            space_uid = SpaceUIDField(label=_("空间唯一标识"), required=True)
            bkdata_auth_url = serializers.ReadOnlyField()

        class ShowMoreSerializer(CustomSerializer):
            source_name = serializers.CharField(read_only=True)

        class ReplaceSerializer(CreateSerializer):
            category_id = serializers.CharField(required=False)

        if self.request.query_params.get("show_more", False):
            # 显示更多，把索引集内的索引一并查出，一般列表中无需使用到
            return ShowMoreSerializer

        action_serializer_map = {
            "update": UpdateSerializer,
            "create": CreateSerializer,
            "retrieve": ShowMoreSerializer,
            "replace": ReplaceSerializer,
            "desensitize_config_create": CreateOrUpdateDesensitizeConfigSerializer,
            "desensitize_config_update": CreateOrUpdateDesensitizeConfigSerializer,
            "add_tag": IndexSetAddTagSerializer,
            "delete_tag": IndexSetDeleteTagSerializer,
            "create_tag": CreateIndexSetTagSerializer,
        }
        return action_serializer_map.get(self.action, CustomSerializer)

    @insert_permission_field(
        actions=[ActionEnum.MANAGE_INDICES],
        resource_meta=ResourceEnum.INDICES,
        id_field=lambda d: d["index_set_id"],
        data_field=lambda d: d["list"],
    )
    def list(self, request, *args, **kwargs):
        """
        @api {get} /index_set/ 索引集-列表
        @apiName list_index_set
        @apiGroup 05_AccessIndexSet
        @apiDescription 未做分页处理; view_roles需同时返回角色名称； 需同时返回索引数据
        @apiParam {String} space_uid 空间唯一标识
        @apiParam {Int} [storage_cluster_id] 数据源ID
        @apiParam {String} [keyword] 搜索关键字
        @apiParam {String} [index_set_id_list] 索引集列表过滤 【index_set_id_list=1,2,3,4】
        @apiParam {Int} page 当前页数
        @apiParam {Int} pagesize 分页大小
        @apiSuccess {Int} index_set_id 索引集ID
        @apiSuccess {String} index_set_name 索引集名称
        @apiSuccess {String} space_uid 空间唯一标识
        @apiSuccess {Int} storage_cluster_id 数据源ID
        @apiSuccess {Int} source_name 数据源名称
        @apiSuccess {String} scenario_id 接入场景
        @apiSuccess {String} scenario_name 接入场景名称
        @apiSuccess {String} category_id 数据分类
        @apiSuccess {String} cluster_name 数据分类名称
        @apiSuccess {Int} storage_cluster_id 存储集群ID
        @apiSuccess {Int} storage_cluster_name 存储集群名称
        @apiSuccess {List} view_roles 可查看角色ID列表
        @apiSuccess {List} view_roles_list 可查看角色列表
        @apiSuccess {Int} view_roles_list.role_id 角色ID
        @apiSuccess {String} view_roles_list.role_name 角色名称
        @apiSuccess {Object} indexes 索引集名称
        @apiSuccess {Int} indexes.bk_biz_id 业务ID
        @apiSuccess {String} indexes.index_id 索引ID
        @apiSuccess {String} indexes.result_table_id 数据源-索引ID
        @apiSuccess {String} indexes.time_field 时间字段
        @apiSuccess {String} indexes.apply_status 审核状态
        @apiSuccess {String} indexes.apply_status_name 审核状态名称
        @apiSuccess {List} target_fields 实时日志上下文目标字段
        @apiSuccess {List} sort_fields 实时日志上下文排序字段
        @apiSuccess {String} indexes.created_at 创建时间
        @apiSuccess {String} indexes.created_by 创建者
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": {
                "total": 100,
                "list": [
                    {
                        "index_set_id": 1,
                        "index_set_name": "登陆日志",
                        "space_uid": "bkcc__2",
                        "storage_cluster_id": 1,
                        "source_name": "ES集群",
                        "scenario_id": "es",
                        "scenario_name": "用户ES",
                        "category_id": "hosts",
                        "category_name": "主机",
                        "storage_cluster_id": 15,
                        "storage_cluster_name": "es_demo",
                        "orders": 1,
                        "view_roles": [1, 2, 3],
                        "view_roles_list": [
                            {
                                "role_id": 1,
                                "role_name": "运维"
                            },
                            {
                                "role_id": 2,
                                "role_name": "产品"
                            }
                        ],
                        "indexes": [
                            {
                                "index_id": 1,
                                "index_set_id": 1,
                                "bk_biz_id": 1,
                                "bk_biz_name": "业务名称",
                                "storage_cluster_id": 1,
                                "source_name": "数据源名称",
                                "result_table_id": "结果表",
                                "result_table_name_alias": "结果表显示名",
                                "time_field": "时间字段",
                                "apply_status": "pending",
                                "apply_status_name": "审核状态名称",
                                "created_at": "2019-10-10 11:11:11",
                                "created_by": "user",
                                "updated_at": "2019-10-10 11:11:11",
                                "updated_by": "user",
                            }
                        ],
                        "target_fields": ['path', 'bk_host_id'],
                        "sort_fields": ['gseIndex'],
                        "created_at": "2019-10-10 11:11:11",
                        "created_by": "user",
                        "updated_at": "2019-10-10 11:11:11",
                        "updated_by": "user",
                        "time_field": "dtEventTimeStamp",
                        "time_field_type": "date",
                        "time_field_unit": "microsecond"
                    }
                ]
            },
            "result": true
        }
        """
        # 强制前端必须传分页参数
        if not request.GET.get("page") or not request.GET.get("pagesize"):
            raise ValueError(_("分页参数不能为空"))
        response = super().list(request, *args, **kwargs)
        response.data["list"] = IndexSetHandler.post_list(response.data["list"])
        return response

    @list_route(methods=["GET"], url_path="list_es_router")
    def list_es_router(self, request):
        params = self.params_valid(ESRouterListSerializer)
        router_list = []
        qs = LogIndexSet.objects.all()
        clustered_qs = ClusteringConfig.objects.exclude(clustered_rt="")
        if params.get("scenario_id", ""):
            qs = qs.filter(scenario_id=params["scenario_id"])
            if params["scenario_id"] != Scenario.BKDATA:
                clustered_qs = clustered_qs.none()

        if params.get("space_uid", ""):
            qs = qs.filter(space_uid=params["space_uid"])

        clustering_config_list = list(clustered_qs.values("index_set_id", "clustered_rt"))
        total = qs.count() + len(clustering_config_list)
        qs = qs[(params["page"] - 1) * params["pagesize"] : params["page"] * params["pagesize"]]

        index_set_ids = list(qs.values_list("index_set_id", flat=True))
        clustering_index_set_ids = [clustering_config["index_set_id"] for clustering_config in clustering_config_list]

        index_set_list = list(qs.values())
        clustering_index_set_list = list(LogIndexSet.objects.filter(index_set_id__in=clustering_index_set_ids).values())

        index_set_dict = {
            index_set["index_set_id"]: index_set for index_set in index_set_list if index_set.get("index_set_id")
        }
        clustering_index_set_dict = {
            index_set["index_set_id"]: index_set
            for index_set in clustering_index_set_list
            if index_set.get("index_set_id")
        }
        index_list = list(
            LogIndexSetData.objects.filter(index_set_id__in=index_set_ids).values("index_set_id", "result_table_id")
        )
        for index in index_list:
            index_set = index_set_dict.get(index["index_set_id"], {})
            if index_set:
                if index_set.get("indexes", []):
                    index_set["indexes"].append(index)
                else:
                    index_set["indexes"] = [index]

        # 普通索引路由创建
        for index_set_id, index_set in index_set_dict.items():
            if not index_set.get("indexes", []):
                continue
            origin_index_set = ",".join([index["result_table_id"] for index in index_set["indexes"]])
            if index_set["scenario_id"] == Scenario.LOG:
                origin_index_set = origin_index_set.replace(".", "_")
            router_list.append(
                {
                    "cluster_id": index_set["storage_cluster_id"],
                    "index_set": origin_index_set,
                    "source_type": index_set["scenario_id"],
                    "data_label": BaseIndexSetHandler.get_data_label(index_set["scenario_id"], index_set_id),
                    "table_id": BaseIndexSetHandler.get_rt_id(
                        index_set_id, index_set["collector_config_id"], index_set["indexes"]
                    ),
                    "space_uid": index_set["space_uid"],
                    "need_create_index": True if index_set["collector_config_id"] else False,
                    "options": [
                        {
                            "name": "time_field",
                            "value_type": "dict",
                            "value": json.dumps(
                                {
                                    "name": index_set["time_field"],
                                    "type": index_set["time_field_type"],
                                    "unit": index_set["time_field_unit"]
                                    if index_set["time_field_type"] != TimeFieldTypeEnum.DATE.value
                                    else TimeFieldUnitEnum.MILLISECOND.value,
                                }
                            ),
                        },
                        {
                            "name": "need_add_time",
                            "value_type": "bool",
                            "value": json.dumps(index_set["scenario_id"] != Scenario.ES),
                        },
                    ],
                }
            )

        # 聚类索引路由创建，追加至列表末尾，不支持space过滤
        if qs.count() < params["pagesize"]:
            for clustering_config in clustering_config_list:
                clustered_rt = clustering_config["clustered_rt"]
                index_set_id = clustering_config["index_set_id"]
                index_set = clustering_index_set_dict.get(index_set_id, None)
                if not clustered_rt or not index_set:
                    continue
                router_list.append(
                    {
                        "cluster_id": index_set["storage_cluster_id"],
                        "index_set": clustered_rt,
                        "source_type": Scenario.BKDATA,
                        "data_label": BaseIndexSetHandler.get_data_label(
                            index_set["scenario_id"], index_set_id, clustered_rt
                        ),
                        "table_id": BaseIndexSetHandler.get_rt_id(
                            index_set_id, index_set["collector_config_id"], [], clustered_rt
                        ),
                        "space_uid": index_set["space_uid"],
                        "need_create_index": False,
                        "options": [
                            {
                                "name": "time_field",
                                "value_type": "dict",
                                "value": json.dumps(
                                    {
                                        "name": index_set["time_field"],
                                        "type": index_set["time_field_type"],
                                        "unit": index_set["time_field_unit"]
                                        if index_set["time_field_type"] != TimeFieldTypeEnum.DATE.value
                                        else TimeFieldUnitEnum.MILLISECOND.value,
                                    }
                                ),
                            },
                            {
                                "name": "need_add_time",
                                "value_type": "bool",
                                "value": "true",
                            },
                        ],
                    }
                )
        return Response({"total": total, "list": router_list})

    def retrieve(self, request, *args, **kwargs):
        """
        @api {get} /index_set/$index_set_id/ 索引集-详情
        @apiName retrieve_index_set
        @apiGroup 05_AccessIndexSet
        @apiParam {Int} index_set_id 索引集ID
        @apiSuccess {Int} index_set_id 索引集ID
        @apiSuccess {String} index_set_name 索引集名称
        @apiSuccess {String} space_uid 空间唯一标识
        @apiSuccess {Int} storage_cluster_id 数据源ID
        @apiSuccess {Int} source_name 数据源名称
        @apiSuccess {String} scenario_id 接入场景
        @apiSuccess {String} scenario_name 接入场景名称
        @apiSuccess {List} view_roles 可查看角色ID列表
        @apiSuccess {List} view_roles_list 可查看角色列表
        @apiSuccess {Int} view_roles_list.role_id 角色ID
        @apiSuccess {String} view_roles_list.role_name 角色名称
        @apiSuccess {Object} indexes 索引集名称
        @apiSuccess {Int} [indexes.bk_biz_id] 业务ID
        @apiSuccess {String} indexes.index_id 索引ID
        @apiSuccess {String} indexes.result_table_id 数据源-索引ID
        @apiSuccess {String} indexes.time_field 时间字段
        @apiSuccess {String} indexes.apply_status 审核状态
        @apiSuccess {String} indexes.apply_status_name 审核状态名称
        @apiSuccess {List} target_fields 实时日志上下文目标字段
        @apiSuccess {List} sort_fields 实时日志上下文排序字段
        @apiSuccess {String} indexes.created_at 创建时间
        @apiSuccess {String} indexes.created_by 创建者
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": {
                "index_set_id": 1,
                "index_set_name": "登陆日志",
                "space_uid": "bkcc__2",
                "storage_cluster_id": 1,
                "source_name": "ES集群",
                "scenario_id": "es",
                "scenario_name": "用户ES",
                "orders": 1,
                "view_roles": [1, 2, 3],
                "view_roles_list": [
                    {
                        "role_id": 1,
                        "role_name": "运维"
                    },
                    {
                        "role_id": 2,
                        "role_name": "产品"
                    }
                ],
                "indexes": [
                    {
                        "index_id": 1,
                        "index_set_id": 1,
                        "bk_biz_id": 1,
                        "bk_biz_name": "业务名称",
                        "storage_cluster_id": 1,
                        "source_name": "数据源名称",
                        "result_table_id": "结果表",
                        "result_table_name_alias": "结果表显示名",
                        "time_field": "时间字段",
                        "apply_status": "pending",
                        "apply_status_name": "审核状态名称",
                        "created_at": "2019-10-10 11:11:11",
                        "created_by": "user",
                        "updated_at": "2019-10-10 11:11:11",
                        "updated_by": "user",
                    }
                ],
                "target_fields": ['path', 'bk_host_id'],
                "sort_fields": ['gseIndex'],
                "created_at": "2019-10-10 11:11:11",
                "created_by": "user",
                "updated_at": "2019-10-10 11:11:11",
                "updated_by": "user",
            },
            "result": true
        }
        """
        response = super().retrieve(request, *args, **kwargs)
        response.data = IndexSetHandler.post_list([response.data])[0]
        return response

    def create(self, request, *args, **kwargs):
        """
        @api {post} /index_set/ 索引集-创建
        @apiName create_index_set
        @apiDescription storage_cluster_id&view_roles校验、索引列表处理
        @apiGroup 05_AccessIndexSet
        @apiParam {String} index_set_name 索引集名称
        @apiParam {String} space_uid 空间唯一标识
        @apiParam {String} [is_editable] 此索引集是否可以编辑
        @apiParam {Int} storage_cluster_id 数据源ID
        @apiParam {String} result_table_id 数据源ID
        @apiParam {String} category_id 数据分类
        @apiParam {String} scenario_id 接入场景ID
        @apiParam {List} view_roles 可查看角色ID列表，可填角色ID，如 "1", "2", 也可以填角色名称，
                                    如 "bk_biz_maintainer", "bk_biz_developer", "bk_biz_productor"
        @apiParam {Object} indexes 索引集列表
        @apiParam {String} indexes.result_table_id 索引ID
        @apiParam {String} indexes.time_field 时间字段(逻辑暂时保留)
        @apiParam {String} is_trace_log 是否是trace类日志
        @apiParam {String} time_field 时间字段
        @apiParam {String} time_field_type 时间字段类型（当选择第三方es时候需要传入，默认值是date,可传入如long）
        @apiParam {String} time_field_unit 时间字段类型单位（当选择非date的时候传入，秒/毫秒/微秒）
        @apiParam {List} target_fields 上下文、实时日志目标字段 默认为 []
        @apiParam {List} sort_fields 上下文、实时日志排序字段 默认为 []
        @apiParamExample {Json} 请求参数
        {
            "index_set_name": "登陆日志",
            "space_uid": "bkcc__2",
            "storage_cluster_id": 1,
            "scenario_id": "es",
            "view_roles": [1, 2, 3],
            "indexes": [
                {
                    "bk_biz_id": 1,
                    "result_table_id": "591_xx",
                    "time_field": "timestamp"
                },
                {
                    "bk_biz_id": null,
                    "result_table_id": "log_xxx",
                    "time_field": "timestamp"
                }
            ],
            "time_field": "abc",
            "time_field_type": "date"/"long",
            "time_field_unit": "second"/"millisecond"/"microsecond",
            "target_fields": ['path', 'bk_host_id'],
            "sort_fields": ['gseIndex']
        }
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": "",
            "result": true
        }
        """
        data = self.validated_data

        if data["scenario_id"] == Scenario.BKDATA or settings.RUN_VER == "tencent":
            storage_cluster_id = None
        elif data["scenario_id"] == Scenario.ES:
            storage_cluster_id = data["storage_cluster_id"]
        else:
            storage_cluster_id = IndexSetHandler.get_storage_by_table_list(data["indexes"])
        # 获取调用方APP CODE
        auth_info = Permission.get_auth_info(request, raise_exception=False)
        if auth_info:
            data["bk_app_code"] = auth_info["bk_app_code"]

        index_set = IndexSetHandler.create(
            index_set_name=data["index_set_name"],
            space_uid=data["space_uid"],
            scenario_id=data["scenario_id"],
            view_roles=data["view_roles"],
            indexes=data["indexes"],
            storage_cluster_id=storage_cluster_id,
            category_id=data["category_id"],
            is_trace_log=data["is_trace_log"],
            time_field=data["time_field"],
            time_field_type=data["time_field_type"],
            time_field_unit=data["time_field_unit"],
            bk_app_code=data.get("bk_app_code"),
            is_editable=data.get("is_editable"),
            target_fields=data.get("target_fields", []),
            sort_fields=data.get("sort_fields", []),
        )

        return Response(self.get_serializer_class()(instance=index_set).data)

    def update(self, request, *args, **kwargs):
        """
        @api {post} /index_set/$index_set_id/ 索引集-更新
        @apiName update_index_set
        @apiGroup 05_AccessIndexSet
        @apiParam {String} is_trace_log 是否是trace类日志
        @apiParam {Int} storage_cluster_id 数据源ID
        @apiParam {String} time_field 时间字段
        @apiParam {String} time_field_type 时间字段类型（当选择第三方es时候需要传入，默认值是date,可传入如long）
        @apiParam {String} time_field_unit 时间字段类型单位（当选择非date的时候传入，秒/毫秒/微秒）
        @apiParam {List} target_fields 上下文、实时日志目标字段 默认为 []
        @apiParam {List} sort_fields 上下文、实时日志排序字段 默认为 []
        @apiParamExample {Json} 请求参数
        {
            "index_set_name": "登陆日志",
            "view_roles": [1, 2, 3],
            "category_id": host,
            "indexes":[
                {
                    "bk_biz_id": 1,
                    "result_table_id": "591_xx"
                    "time_field": "timestamp"
                },
                {
                    "bk_biz_id": null,
                    "result_table_id": "log_xxx",
                    "time_field": "timestamp"
                }
            ],
            "time_field": "abc",
            "time_field_type": "date"/"long",
            "time_field_unit": "second"/"millisecond"/"microsecond",
            "target_fields": ['path', 'bk_host_id'],
            "sort_fields": ['gseIndex']
        }
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": "",
            "result": true
        }
        """
        handler = IndexSetHandler(index_set_id=kwargs["index_set_id"])

        data = self.validated_data
        if data["scenario_id"] == Scenario.BKDATA or settings.RUN_VER == "tencent":
            storage_cluster_id = None
        elif data["scenario_id"] == Scenario.ES:
            storage_cluster_id = data["storage_cluster_id"]
        else:
            storage_cluster_id = IndexSetHandler.get_storage_by_table_list(data["indexes"])

        index_set = handler.update(
            data["index_set_name"],
            data["view_roles"],
            data["indexes"],
            data["category_id"],
            storage_cluster_id=storage_cluster_id,
            is_trace_log=data["is_trace_log"],
            time_field=data["time_field"],
            time_field_type=data["time_field_type"],
            time_field_unit=data["time_field_unit"],
            target_fields=data.get("target_fields", []),
            sort_fields=data.get("sort_fields", []),
        )

        return Response(self.get_serializer_class()(instance=index_set).data)

    @list_route(methods=["POST"], url_path="replace")
    def replace(self, request, *args, **kwargs):
        """
        @api {post} /index_set/ 索引集-替换
        @apiName replace_index_set
        @apiDescription 索引集替换，仅用于第三方APP使用
        @apiGroup 05_AccessIndexSet
        @apiParam {String} index_set_name 索引集名称
        @apiParam {String} space_uid 空间唯一标识
        @apiParam {Int} storage_cluster_id 数据源ID
        @apiParam {String} result_table_id 数据源ID
        @apiParam {String} category_id 数据分类
        @apiParam {String} scenario_id 接入场景ID
        @apiParam {List} view_roles 可查看角色ID列表，可填角色ID，如 "1", "2", 也可以填角色名称，
                                    如 "bk_biz_maintainer", "bk_biz_developer", "bk_biz_productor"
        @apiParam {Object} indexes 索引集列表
        @apiParam {String} indexes.result_table_id 索引ID
        @apiParam {String} indexes.time_field 时间字段(逻辑暂时保留)
        @apiParam {String} is_trace_log 是否是trace类日志
        @apiParam {String} time_field 时间字段
        @apiParam {String} time_field_type 时间字段类型（当选择第三方es时候需要传入，默认值是date,可传入如long）
        @apiParam {String} time_field_unit 时间字段类型单位（当选择非date的时候传入，秒/毫秒/微秒）
        @apiParam {List} target_fields 上下文、实时日志目标字段 默认为 []
        @apiParam {List} sort_fields 上下文、实时日志排序字段 默认为 []
        @apiParamExample {Json} 请求参数
        {
            "index_set_name": "登陆日志",
            "space_uid": "bkcc__2",
            "storage_cluster_id": 1,
            "scenario_id": "es",
            "view_roles": [1, 2, 3],
            "indexes": [
                {
                    "bk_biz_id": 1,
                    "result_table_id": "591_xx",
                    "time_field": "timestamp"
                },
                {
                    "bk_biz_id": null,
                    "result_table_id": "log_xxx",
                    "time_field": "timestamp"
                }
            ],
            "time_field": "abc",
            "time_field_type": "date"/"long",
            "time_field_unit": "second"/"millisecond"/"microsecond",
            "target_fields": [],
            "sort_fields": []
        }
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": "",
            "result": true
        }
        """
        data = self.validated_data
        auth_info = Permission.get_auth_info(request, raise_exception=False)
        if not auth_info:
            raise BkJwtVerifyException()

        index_set = IndexSetHandler.replace(
            data["index_set_name"],
            data["scenario_id"],
            data["view_roles"],
            data["indexes"],
            auth_info["bk_app_code"],
            space_uid=data.get("space_uid"),
            storage_cluster_id=data.get("storage_cluster_id"),
            category_id=data.get("category_id"),
            collector_config_id=data.get("collector_config_id"),
            target_fields=data.get("target_fields", []),
            sort_fields=data.get("sort_fields", []),
        )
        return Response(self.get_serializer_class()(instance=index_set).data)

    def destroy(self, request, *args, **kwargs):
        """
        @api {delete} /index_set/$index_set_id/ 索引集-删除
        @apiName delete_index_set
        @apiGroup 05_AccessIndexSet
        @apiDescription 已删除索引未做判断
        @apiParam {Int} index_set_id 索引集ID
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": "",
            "result": true
        }
        """
        IndexSetHandler(index_set_id=kwargs["index_set_id"]).delete()
        return Response()

    @detail_route(methods=["GET", "POST"])
    def sync_auth_status(self, request, *args, **kwargs):
        """
        @api {post} /index_set/$index_set_id/sync_auth_status/ 更新授权状态
        @apiName sync_auth_status
        @apiGroup 05_AccessIndexSet
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": [
                {
                    "index_id": 1,
                    "index_set_id": 1,
                    "bk_biz_id": 1,
                    "bk_biz_name": "业务名称",
                    "source_name": "数据源名称",
                    "result_table_id": "结果表",
                    "result_table_name_alias": "结果表显示名",
                    "time_field": "时间字段",
                    "apply_status": "pending",
                    "apply_status_name": "审核状态名称",
                }
            ],
            "code": 0,
            "message": ""
        }
        """
        sync_auth_status()
        return Response(self.get_object().indexes)

    @detail_route(methods=["GET"], url_path="indices")
    def indices(self, request, index_set_id, *args, **kwargs):
        """
        @api {post} /index_set/$index_set_id/indices/ 索引集物理索引信息
        @apiName indices
        @apiGroup 05_AccessIndexSet
        @apiSuccess {Int} total 索引集数量
        @apiSuccess {String} result_table_id rt_id
        @apiSuccess {Dict} item key为索引集名称
        @apiSuccess {String} health 索引健康状态 red green yellow
        @apiSuccess {String} status 索引状态
        @apiSuccess {String} pri 主分片数量
        @apiSuccess {String} rep 副本数量
        @apiSuccess {String} index 索引名称
        @apiSuccess {String} docs.count 文档数量
        @apiSuccess {String} docs.deleted 删除文档数量
        @apiSuccess {String} store.size 储存大小 Byte
        @apiSuccess {String} pri.store.size 主分片储存大小 Byte
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": {
                "total": 2,
                "list": [{
                    "result_table_id": "215_bklog.test_samuel_111111",
                    "stat": {
                        "health": "green",
                        "status": "open",
                        "pri": "3",
                        "rep": "1",
                        "docs.count": "0",
                        "docs.deleted": "0",
                        "store.size": "1698",
                        "pri.store.size": "849"
                    },
                    "details": [{
                        "health": "green",
                        "status": "open",
                        "index": "v2_215_bklog_test_samuel_111111_20210315_0",
                        "uuid": "V6ZuLKXAR06kQriSWyXXmA",
                        "pri": "3",
                        "rep": "1",
                        "docs.count": "0",
                        "docs.deleted": "0",
                        "store.size": "1698",
                        "pri.store.size": "849"
                    }]
                }]
            }
        }
        }
        """
        return Response(IndexSetHandler(index_set_id).indices())

    @detail_route(methods=["POST"])
    def mark_favorite(self, request, index_set_id, *arg, **kwargs):
        """
        @api {POST} /index_set/$index_set_id/mark_favorite/ 标记索引集为收藏索引集
        @apiName mark_favorite
        @apiGroup 05_AccessIndexSet
        """
        return Response(IndexSetHandler(index_set_id).mark_favorite())

    @detail_route(methods=["POST"])
    def cancel_favorite(self, request, index_set_id, *arg, **kwargs):
        """
        @api {POST} /index_set/$index_set_id/cancel_favorite/ 取消标记为收藏索引集
        @apiName cancel_favorite
        @apiGroup 05_AccessIndexSet
        """
        return Response(IndexSetHandler(index_set_id).cancel_favorite())

    @detail_route(methods=["POST"], url_path="desensitize/config/create")
    def desensitize_config_create(self, request, index_set_id, *args, **kwargs):
        """
        @api {POST} /index_set/$index_set_id/desensitize/config/create/ 创建索引集脱敏配置
        @apiName desensitize_config create
        @apiGroup 05_AccessIndexSet
        @apiParam {Array[Json]} field_configs 字段脱敏配置信息
        @apiParam {String} field_configs.field_name 字段名
        @apiParam {Array[Json]} field_configs.rules 规则配置列表
        @apiParam {Int} field_configs.rule_id 脱敏规则ID （传递脱敏规则的情况下不需要在传递脱敏配置）
        @apiParam {String} field_configs.state 状态 update、delete、normal
        @apiParam {String} field_configs.rules.operator 脱敏算子 可选字段 ‘mask_shield, text_replace’
        @apiParam {Json} field_configs.rules.params 脱敏算子参数
        @apiParam {Int} field_configs.rules.params.preserve_head 掩码屏蔽算子参数 保留前几位  默认 0
        @apiParam {Int} field_configs.rules.params.preserve_tail 掩码屏蔽算子参数 保留后几位  默认 0
        @apiParam {String} field_configs.rules.params.replace_mark 掩码屏蔽算子参数 替换符号 默认 *
        @apiParam {String} field_configs.rules.params.template_string 文本替换算子参数 替换模板
        @apiParam {Array[String]} text_fields 日志原文字段
        @apiParamExample {Json} 请求示例:
        {
            "space_uid": "bkcc__2",
             "field_configs": [
                {
                 "field_name": "path",
                 "rules": [
                     {
                         "rule_id": 5,
                         "match_pattern": ".*",
                         "operator": "mask_shield",
                         "params": {
                                "replace_mark": "*",
                                "preserve_head": 1,
                                "preserve_tail": 2
                            }
                       },
                       {
                           "rule_id": 4,
                           "match_pattern": ".*",
                           "operator": "mask_shield",
                           "params": {
                                "replace_mark": "*",
                                "preserve_head": 1,
                                "preserve_tail": 2
                            }
                       }
                    ]
                }
             ]
            "text_fields": ["log"]
        }
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": {
                "field_configs": [
                    {
                        "field_name": "path",
                        "rules": [
                            {
                                "rule_id": 5,
                                "match_pattern": ".*",
                                "operator": "mask_shield",
                                "params": {
                                    "preserve_head": 1,
                                    "preserve_tail": 2,
                                    "replace_mark": "*"
                                },
                                "state": "add"
                            },
                            {
                                "rule_id": 4,
                                "match_pattern": ".*",
                                "operator": "mask_shield",
                                "params": {
                                    "preserve_head": 1,
                                    "preserve_tail": 2,
                                    "replace_mark": "*"
                                },
                                "state": "add"
                            }
                        ]
                    }
                ],
                "text_fields": [
                    "log"
                ]
            },
            "code": 0,
            "message": ""
        }
        """
        data = self.validated_data
        return Response(IndexSetHandler(int(index_set_id)).update_or_create_desensitize_config(params=data))

    @detail_route(methods=["PUT"], url_path="desensitize/config/update")
    def desensitize_config_update(self, request, index_set_id, *args, **kwargs):
        """
        @api {POST} /index_set/$index_set_id/desensitize/config/update/ 更新索引集脱敏配置
        @apiName desensitize_config update
        @apiGroup 05_AccessIndexSet
        @apiParam {Array[Json]} field_configs 字段脱敏配置信息
        @apiParam {String} field_configs.field_name 字段名
        @apiParam {Int} field_configs.rule_id 绑定的规则ID
        @apiParam {String} field_configs.state 状态 update、delete、normal
        @apiParam {String} field_configs.operator 脱敏算子 可选字段 ‘mask_shield, text_replace’
        @apiParam {Json} field_configs.params 脱敏算子参数
        @apiParam {Int} field_configs.params.preserve_head 掩码屏蔽算子参数 保留前几位  默认 0
        @apiParam {Int} field_configs.params.preserve_tail 掩码屏蔽算子参数 保留后几位  默认 0
        @apiParam {String} field_configs.params.replace_mark 掩码屏蔽算子参数 替换符号 默认 *
        @apiParam {String} field_configs.params.template_string 文本替换算子参数 替换模板
        @apiParam {Array[String]} text_fields 日志原文字段
        @apiParamExample {Json} 请求示例:
        {
            "space_uid": "bkcc__2",
             "field_configs": [
                {
                 "field_name": "path",
                 "rules": [
                     {
                         "rule_id": 5,
                         "match_pattern": ".*",
                         "operator": "mask_shield",
                         "params": {
                                "replace_mark": "*",
                                "preserve_head": 1,
                                "preserve_tail": 2
                            },
                         "state": "normal",
                       },
                       {
                           "rule_id": 4,
                           "match_pattern": ".*",
                           "operator": "mask_shield",
                           "params": {
                                "replace_mark": "*",
                                "preserve_head": 1,
                                "preserve_tail": 2
                            },
                           "state": "update",
                       }
                    ]
                }
             ]
            "text_fields": ["log"]
        }
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": {
                "field_configs": [
                    {
                        "field_name": "path",
                        "rules": [
                            {
                                "rule_id": 5,
                                "match_pattern": ".*",
                                "operator": "mask_shield",
                                "params": {
                                    "preserve_head": 1,
                                    "preserve_tail": 2,
                                    "replace_mark": "*"
                                },
                                "state": "add"
                            },
                            {
                                "rule_id": 4,
                                "match_pattern": ".*",
                                "operator": "mask_shield",
                                "params": {
                                    "preserve_head": 1,
                                    "preserve_tail": 2,
                                    "replace_mark": "*"
                                },
                                "state": "add"
                            }
                        ]
                    }
                ],
                "text_fields": [
                    "log"
                ]
            },
            "code": 0,
            "message": ""
        }
        """
        data = self.validated_data
        return Response(IndexSetHandler(int(index_set_id)).update_or_create_desensitize_config(params=data))

    @detail_route(methods=["GET"], url_path="desensitize/config/retrieve")
    def desensitize_config_retrieve(self, request, index_set_id, *args, **kwargs):
        """
        @api {GET} /index_set/$index_set_id/desensitize/config/retrieve/ 索引集脱敏配置详情
        @apiName desensitize_config retrieve
        @apiGroup 05_AccessIndexSet
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": {
                "id": 18,
                "created_at": "2023-09-07T01:56:25.035238Z",
                "created_by": "admin",
                "updated_at": "2023-09-07T01:56:25.035238Z",
                "updated_by": "admin",
                "index_set_id": 150,
                "text_fields": [],
                "field_configs": [
                    {
                        "field_name": "path",
                        "rules": [
                            {
                                "index_set_id": 150,
                                "field_name": "path",
                                "rule_id": 5,
                                "match_pattern": ".*",
                                "operator": "mask_shield",
                                "params": {
                                    "replace_mark": "*",
                                    "preserve_head": 1,
                                    "preserve_tail": 2
                                },
                                "sort_index": 1,
                                "state": "normal",
                                "new_rule": {}
                            },
                            {
                                "index_set_id": 150,
                                "field_name": "path",
                                "rule_id": 4,
                                "match_pattern": ".*",
                                "operator": "mask_shield",
                                "params": {
                                    "replace_mark": "*",
                                    "preserve_head": 1,
                                    "preserve_tail": 2
                                },
                                "sort_index": 0,
                                "state": "update",
                                "new_rule": {
                                    "operator": "mask_shield",
                                    "params": {
                                        "replace_mark": "*",
                                        "preserve_head": 1,
                                        "preserve_tail": 4
                                    },
                                    "match_pattern": ".*"
                                }
                            }
                        ]
                    }
                ]
            },
            "code": 0,
            "message": ""
        }
        """
        return Response(IndexSetHandler(int(index_set_id)).desensitize_config_retrieve())

    @detail_route(methods=["DELETE"], url_path="desensitize/config/delete")
    def desensitize_config_delete(self, request, index_set_id, *args, **kwargs):
        """
        @api {GET} /index_set/$index_set_id/desensitize/config/delete/ 索引集脱敏配置删除
        @apiName desensitize_config delete
        @apiGroup 05_AccessIndexSet
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": null,
            "code": 0,
            "message": ""
        }
        """
        return Response(IndexSetHandler(int(index_set_id)).desensitize_config_delete())

    @list_route(methods=["POST"], url_path="desensitize/config/state")
    def desensitize_config_state(self, request, *args, **kwargs):
        """
        @api {POST} /index_set/desensitize/config/state/ 索引集脱敏状态
        @apiName desensitize config state
        @apiGroup 05_AccessIndexSet
        @apiParam {Array[Int]} index_set_ids 索引集列表
        @apiParamExample {Json} 请求示例:
        {
            "index_set_ids": [1,2,3,4,5]
        }
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": {
                "1": {
                    "is_desensitize": false
                },
                "2": {
                    "is_desensitize": false
                },
                "3": {
                    "is_desensitize": false
                },
                "4": {
                    "is_desensitize": false
                },
                "5": {
                    "is_desensitize": false
                }
            },
            "code": 0,
            "message": ""
        }
        """
        data = self.params_valid(DesensitizeConfigStateSerializer)
        return Response(IndexSetHandler().get_desensitize_config_state(data["index_set_ids"]))

    @detail_route(methods=["POST"], url_path="tag/add")
    def add_tag(self, request, index_set_id, *args, **kwargs):
        """
        @api {POST} /index_set/$index_set_id/tag/add/ 索引集添加标签
        @apiName add_tag
        @apiGroup 05_AccessIndexSet
        """
        data = self.validated_data
        return Response(IndexSetHandler(int(index_set_id)).add_tag(tag_id=int(data["tag_id"])))

    @detail_route(methods=["POST"], url_path="tag/delete")
    def delete_tag(self, request, index_set_id, *args, **kwargs):
        """
        @api {POST} /index_set/$index_set_id/tag/delete/ 索引集取消标签
        @apiName cancel_tag
        @apiGroup 05_AccessIndexSet
        """
        data = self.validated_data
        return Response(IndexSetHandler(int(index_set_id)).delete_tag(tag_id=int(data["tag_id"])))

    @list_route(methods=["POST"], url_path="tag")
    def create_tag(self, request, *args, **kwargs):
        """
        @api {POST} /index_set/tag/ 创建标签
        @apiName create_tag
        @apiGroup 05_AccessIndexSet
        """
        data = self.validated_data
        return Response(IndexSetHandler().create_tag(params=data))

    @list_route(methods=["GET"], url_path="tag/list")
    def tag_list(self, request, *args, **kwargs):
        """
        @api {POST} /index_set/tag/list/ 标签列表
        @apiName list_tag
        @apiGroup 05_AccessIndexSet
        """
        return Response(IndexSetHandler().tag_list())

    @list_route(methods=["POST"], url_path="user_search")
    def user_search(self, request):
        """
        @api {post} /index_set/user_search/
        @apiDescription 获取用户最近查询的索引集
        @apiName user_search
        @apiGroup 05_AccessIndexSet
        @apiParam {String} username 用户名(必填)
        @apiParam {String} [space_uid] 空间唯一标识(非必填)
        @apiParam {Int} [start_time] 开始时间(非必填)
        @apiParam {Int} [end_time] 结束时间(非必填)
        @apiParam {Int} limit 限制条数(必填)
        @apiParamExample {Json} 请求参数
        {
            "username": "admin",
            "space_uid": "bkcc__2",
            "start_time": 1732694693,
            "end_time": 1735286693,
            "limit": 1
        }
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": [
                {
                    "index_set_id": 305,
                    "created_at": "2024-12-23T09:10:59.968318Z",
                    "params": {
                        "keyword": "mylevel: *",
                        "ip_chooser": {},
                        "addition": [],
                        "start_time": "2024-12-23 16:55:59",
                        "end_time": "2024-12-23 17:10:59",
                        "time_range": null
                    },
                    "duration": 680.0,
                    "index_set_name": "[采集项]ES存储集群无损切换-测试验证",
                    "space_uid": "bkcc__2"
                }
            ],
            "code": 0,
            "message": ""
        }
        """
        data = self.params_valid(UserSearchSerializer)
        return Response(IndexSetHandler.fetch_user_search_index_set(params=data))

    @list_route(methods=["POST"], url_path="user_favorite")
    def user_favorite(self, request):
        """
        @api {post} /index_set/user_favorite/
        @apiDescription 获取用户收藏的索引集
        @apiName user_favorite
        @apiGroup 05_AccessIndexSet
        @apiParam {String} username 用户名(必填)
        @apiParam {String} [space_uid] 空间唯一标识(非必填)
        @apiParam {Int} [limit] 限制条数(非必填)
        @apiParamExample {Json} 请求参数
        {
            "username": "admin",
            "space_uid": "bkcc__2",
            "limit": 1
        }
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": [
                {
                    "index_set_id": 305,
                    "created_at": "2024-12-23T09:10:59.968318Z",
                    "index_set_name": "[采集项]ES存储集群无损切换-测试验证",
                    "space_uid": "bkcc__2"
                }
            ],
            "code": 0,
            "message": ""
        }
        """
        data = self.params_valid(UserFavoriteSerializer)
        return Response(IndexSetHandler.fetch_user_favorite_index_set(params=data))

    @list_route(methods=["POST"], url_path="storage_usage")
    def storage_usage(self, request):
        """
        @api {post} /index_set/storage_usage/ 查询索引集的存储使用量
        @apiDescription 查询索引集的存储使用量
        @apiName storage_usage
        @apiParam {Int} bk_biz_id 业务ID
        @apiParam {Int} index_set_ids 索引集列表
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": [
                {
                    "index_set_id": 71,
                    "daily_count": 8888,
                    "total_count": 191067379,
                    "daily_usage": 2341664,
                    "total_usage": 50339300366
                },
                {
                    "index_set_id": 81,
                    "daily_count": 8888,
                    "total_count": 23202673,
                    "daily_usage": 10116334,
                    "total_usage": 26409316486
                }
            ],
            "code": 0,
            "message": ""
        }
        """
        data = self.params_valid(StorageUsageSerializer)
        return Response(IndexSetHandler.get_storage_usage_info(data["bk_biz_id"], data["index_set_ids"]))

    @detail_route(methods=["GET"], url_path="space")
    def space(self, request, index_set_id, *args, **kwargs):
        """
        @api {GET} /index_set/$index_set_id/space/ 根据索引集ID获取空间信息
        @apiDescription 根据索引集ID获取空间信息
        @apiName space
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": {
                "id": 2,
                "space_type_id": "bkcc",
                "space_id": "2",
                "space_name": "蓝鲸",
                "space_uid": "bkcc__2",
                "space_code": "2",
                "bk_biz_id": 2,
                "time_zone": "Asia/Shanghai",
                "bk_tenant_id": "system"
            },
            "code": 0,
            "message": ""
        }
        """
        return Response(IndexSetHandler.get_space_info(int(index_set_id)))

    @list_route(methods=["GET"], url_path="query_by_dataid")
    def query_by_dataid(self, request):
        """
        @api {GET} /index_set/query_by_dataid/?bk_data_id=xxx 根据 bk_data_id 获取采集项和索引集信息的接口
        @apiDescription 根据 bk_data_id 获取采集项和索引集信息的接口
        @apiName query_by_dataid
        @apiSuccessExample {json} 成功返回:
        {
            'result': True,
            'data': {
                'index_set_id': 39,
                'index_set_name': 'xxxx',
                'space_uid': 'bkcc__2',
                'collector_config_id': 131,
                'collector_config_name': 'xxxxxx'
            },
            'code': 0,
            'message': ''
        }
        """
        params = self.params_valid(QueryByDataIdSerializer)
        return Response(IndexSetHandler.query_by_bk_data_id(bk_data_id=params["bk_data_id"]))
