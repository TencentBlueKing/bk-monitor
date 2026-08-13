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

from django.conf import settings
from rest_framework import serializers
from rest_framework.response import Response

from apps.generic import ModelViewSet
from apps.iam import ActionEnum, Permission, ResourceEnum
from apps.iam.exceptions import PermissionDeniedError
from apps.iam.handlers.drf import ViewBusinessPermission, insert_permission_field
from apps.log_databus.handlers.clean import CleanHandler, CleanTemplateHandler
from apps.log_databus.handlers.etl import EtlHandler
from apps.log_databus.models import BKDataClean, CleanTemplate
from apps.log_databus.serializers import (
    CleanRefreshSerializer,
    CleanSerializer,
    CleanSyncSerializer,
    CleanTemplateListFilterSerializer,
    CleanTemplateListSerializer,
    CleanTemplateOperatorListSerializer,
    CleanTemplatePreviewSerializer,
    CleanTemplateSerializer,
    CleanTemplateUpdateSerializer,
    CollectorEtlSerializer,
)
from apps.log_databus.utils.clean import CleanFilterUtils
from apps.utils.drf import detail_route, list_route


class CleanViewSet(ModelViewSet):
    """
    清洗列表
    """

    lookup_field = "collector_config_id"
    model = BKDataClean

    def get_permissions(self):
        return [ViewBusinessPermission()]

    @insert_permission_field(
        id_field=lambda d: d["collector_config_id"],
        data_field=lambda d: d["list"],
        actions=[ActionEnum.VIEW_COLLECTION, ActionEnum.MANAGE_COLLECTION],
        resource_meta=ResourceEnum.COLLECTION,
    )
    @insert_permission_field(
        id_field=lambda d: d["index_set_id"],
        data_field=lambda d: d["list"],
        actions=[ActionEnum.SEARCH_LOG],
        resource_meta=ResourceEnum.INDICES,
    )
    def list(self, request, *args, **kwargs):
        """
        @api {get} /databus/clean/?page=$page&pagesize=$pagesize&bk_biz_id=$bk_biz_id 1_清洗-列表
        @apiName list_clean
        @apiGroup 22_clean
        @apiDescription 清洗列表，获取入库列表及基础清洗合集
        @apiParam {Int} bk_biz_id 业务ID
        @apiParam {Int} page 页数
        @apiParam {Int} pagesize 每页数量
        @apiSuccess {Int} count 总数
        @apiSuccess {Int} total_page 总页数
        @apiSuccessExample {json} 成功返回
        {
            "message": "",
            "code": 0,
            "data": {
                "count": 10,
                "total_page": 1,
                "results": [
                {
                    "collector_config_id":1,
                    "collector_config_name":"test",
                    "bk_data_id": 10,
                    "result_table_id":"test",
                    "updated_by":"test",
                    "updated_at":"2021-07-24 17:42:32+0800"
                }
            ]
            },
            "result": true
        }
        """
        data = self.params_valid(CleanSerializer)
        return Response(
            CleanFilterUtils(bk_biz_id=data["bk_biz_id"]).filter(
                keyword=data.get("keyword", ""),
                etl_config=data.get("etl_config", ""),
                page=data["page"],
                pagesize=data["pagesize"],
            )
        )

    @detail_route(methods=["DELETE"], url_path="destroy_clean")
    def destroy_clean(self, request, collector_config_id=None):
        """
        @api {destroy} /databus/clean/$collector_config_id/destroy_clean 1_清洗-删除清洗
        @apiName destroy_clean
        @apiGroup 22_clean
        @apiDescription 删除清洗配置
        @apiParam {Int} $collector_config_id 采集项ID
        @apiSuccess {Bool} 删除结果
        @apiSuccessExample {json} 成功返回
        {
            "message": "",
            "code": 0,
            "data": {
                true
            },
            "result": true
        }
        """
        return Response(CleanFilterUtils().delete(collector_config_id))

    @detail_route(methods=["GET"])
    def refresh(self, request, *args, collector_config_id=None, **kwargs):
        """
        @api {get} /databus/clean/$collector_config_id/refresh/?bk_biz_id=$bk_biz_id&bk_data_id=$bk_data_id 2_高级清洗-刷新
        @apiName refresh_clean
        @apiGroup 22_clean
        @apiDescription 刷新高级清洗
        @apiParam {Int} bk_biz_id 业务id
        @apiParam {Int} bk_data_id 数据源id
        @apiSuccessExample {json} 成功返回
        {
            "message": "",
            "code": 0,
            "data": [
                "test"
            ],
            "result": true
        }
        @apiSuccessExample {json} 成功返回(未找到对应记录)
        {
            "message": "",
            "code": 0,
            "data": {
                "result": False,
                "log_set_index_id": null,
            },
            "result": true
        }
        """
        data = self.params_valid(CleanRefreshSerializer)
        return Response(
            CleanHandler(collector_config_id=collector_config_id).refresh(
                raw_data_id=data["bk_data_id"], bk_biz_id=data["bk_biz_id"]
            )
        )

    @list_route(methods=["GET"])
    def sync(self, request, *args, **kwargs):
        """
        @api {get} /databus/clean/sync/?bk_biz_id=$bk_biz_id 3_高级清洗-同步
        @apiName sync_clean
        @apiGroup 22_clean
        @apiDescription 同步高级清洗
        @apiParam {Int} bk_biz_id 业务id
        @apiSuccessExample {json} 任务已完成
        {
            "message": "",
            "code": 0,
            "data": {
                "status": "DONE"
            },
            "result": true
        }
        @apiSuccessExample {json} 任务正在进行中
        {
            "message": "",
            "code": 0,
            "data": {
                "status": "RUNNING"
            },
            "result": true
        }
        """
        data = self.params_valid(CleanSyncSerializer)
        return Response({"status": CleanHandler.sync(bk_biz_id=data["bk_biz_id"], polling=data["polling"])})


class CleanTemplateViewSet(ModelViewSet):
    """
    清洗模板
    """

    lookup_field = "clean_template_id"
    lookup_value_regex = r"\d+"
    model = CleanTemplate
    filter_fields_exclude = ["etl_params", "etl_fields", "visible_type", "visible_bk_biz_id", "alias_settings"]
    search_fields = ("name",)
    permission_classes = (ViewBusinessPermission,)

    @staticmethod
    def _get_authorized_sync_collector_ids(request, clean_template):
        """返回本批次已通过采集管理权限校验的采集项 ID。"""
        collectors = list(
            CleanTemplateHandler.get_collectors_to_sync_queryset(
                clean_template.clean_template_id,
                clean_template.bk_biz_id,
                clean_template.config_version,
            )
            .values(
                "collector_config_id",
                "collector_config_name",
                "bk_biz_id",
            )
            .order_by("collector_config_id")
        )
        collector_ids = [collector["collector_config_id"] for collector in collectors]
        if settings.IGNORE_IAM_PERMISSION or not collectors:
            return collector_ids

        permission = Permission(request=request)
        resources = [
            [
                ResourceEnum.COLLECTION.create_simple_instance(
                    collector["collector_config_id"],
                    attribute={
                        "id": str(collector["collector_config_id"]),
                        "name": collector["collector_config_name"],
                        "bk_biz_id": str(collector["bk_biz_id"]),
                    },
                )
            ]
            for collector in collectors
        ]
        permission_result = permission.batch_is_allowed([ActionEnum.MANAGE_COLLECTION], resources)
        denied_resources = [
            resource[0]
            for resource in resources
            if not permission_result.get(resource[0].id, {}).get(ActionEnum.MANAGE_COLLECTION.id)
        ]
        if denied_resources:
            apply_data, apply_url = permission.get_apply_data(
                [ActionEnum.MANAGE_COLLECTION],
                denied_resources,
            )
            raise PermissionDeniedError(
                action_name=ActionEnum.MANAGE_COLLECTION.name,
                permission=apply_data,
                apply_url=apply_url,
            )
        return collector_ids

    def get_serializer_class(self, *args, **kwargs):
        action_serializer_map = {
            "list": CleanTemplateListSerializer,
            "retrieve": CleanTemplateListSerializer,
        }
        return action_serializer_map.get(self.action, serializers.Serializer)

    def get_queryset(self):
        return self.model.objects.all()

    def list(self, request, *args, **kwargs):
        """
        @api {get} /databus/clean_template/?page=$page&pagesize=$pagesize&bk_biz_id=$bk_biz_id 1_清洗模板-列表
        @apiName list_clean_template
        @apiGroup 23_clean_template
        @apiDescription 获取清洗模板列表
        @apiParam {Int} bk_biz_id 业务id
        @apiParam {String} [keyword] 模板名称关键字
        @apiParam {String} [clean_type] 清洗类型
        @apiParam {String} [created_by] 创建人
        @apiParam {String} [updated_by] 更新人
        @apiParam {String} [ordering] 排序字段，可选 field_count、-field_count、
            active_collector_count、-active_collector_count
        @apiSuccessExample {json} 成功返回
        {
            "message":"",
            "code":0,
            "data":{
                "total":10,
                "list":[
                    {
                        "clean_template_id":1,
                        "name": "test",
                        "description": "模板描述",
                        "clean_type":"bk_log_text",
                        "etl_params":{
                            "retain_original_text":true,
                            "separator":" "
                        },
                        "etl_fields":[
                            {
                                "field_name":"user",
                                "alias_name":"",
                                "field_type":"long",
                                "description":"字段描述",
                                "is_analyzed":true,
                                "is_dimension":false,
                                "is_time":false,
                                "is_delete":false
                            },
                            {
                                "field_name":"report_time",
                                "alias_name":"",
                                "field_type":"string",
                                "description":"字段描述",
                                "tag":"metric",
                                "is_analyzed":false,
                                "is_dimension":false,
                                "is_time":true,
                                "is_delete":false,
                                "option":{
                                    "time_zone":8,
                                    "time_format":"yyyy-MM-dd HH:mm:ss"
                                }
                            }
                        ],
                        "alias_settings": [],
                        "config_version": 1,
                        "field_count": 2,
                        "active_collector_count": 2,
                        "pending_sync_collector_count": 1,
                        "related_index_set_count": 1,
                        "created_at": "2026-07-30 10:00:00",
                        "created_by": "admin",
                        "updated_at": "2026-07-30 10:00:00",
                        "updated_by": "admin",
                        "bk_biz_id": 0,
                        "visible_bk_biz_id": "",
                        "visible_type": "current_biz"
                    }
                ]
            },
            "result":true
        }
        """
        data = self.params_valid(CleanTemplateListFilterSerializer)
        queryset = self.get_queryset().filter(bk_biz_id=data["bk_biz_id"])

        if name_filter := data.get("keyword"):
            queryset = queryset.filter(name__icontains=name_filter)
        if clean_type := data.get("clean_type"):
            queryset = queryset.filter(clean_type=clean_type)
        if created_by := data.get("created_by"):
            queryset = queryset.filter(created_by=created_by)
        if updated_by := data.get("updated_by"):
            queryset = queryset.filter(updated_by=updated_by)

        queryset = queryset.order_by("-updated_at", "-clean_template_id")
        ordering = data.get("ordering")

        # 默认排序可以先在数据库分页，只为当前页计算统计值；统计字段排序仍需全量计算后再分页。
        if not ordering:
            page = self.paginate_queryset(queryset)
            if page is None:
                clean_templates = CleanTemplateHandler.fill_template_stats(queryset)
            else:
                page = CleanTemplateHandler.fill_template_stats(page)
        else:
            clean_templates = CleanTemplateHandler.fill_template_stats(queryset)
            clean_templates.sort(key=lambda item: getattr(item, ordering.lstrip("-")), reverse=ordering.startswith("-"))
            page = self.paginate_queryset(clean_templates)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(clean_templates, many=True)
        return Response(serializer.data)

    @list_route(methods=["GET"], url_path="operators")
    def list_operators(self, request, *args, **kwargs):
        """返回当前业务清洗模板的创建人和更新人枚举。"""
        data = self.params_valid(CleanTemplateOperatorListSerializer)
        operators = self.get_queryset().filter(bk_biz_id=data["bk_biz_id"]).values_list("created_by", "updated_by")
        return Response(
            {
                "created_by": sorted({created_by for created_by, _ in operators if created_by}),
                "updated_by": sorted({updated_by for _, updated_by in operators if updated_by}),
            }
        )

    def retrieve(self, request, *args, clean_template_id=None, **kwargs):
        """
        @api {get} /databus/clean_template/$clean_template_id/ 2_清洗模板-详情
        @apiName retrieve_clean_template
        @apiGroup 23_clean_template
        @apiDescription 清洗模板详情
        @apiSuccessExample {json} 成功返回
        {
            "message":"",
            "code":0,
            "data":{
                "name": "xxx",
                "clean_template_id":1,
                "description": "模板描述",
                "clean_type":"bk_log_text",
                "etl_params":{
                    "retain_original_text":true,
                    "separator":" "
                },
                "etl_fields":[
                    {
                        "field_name":"user",
                        "alias_name":"",
                        "field_type":"long",
                        "description":"字段描述",
                        "is_analyzed":true,
                        "is_dimension":false,
                        "is_time":false,
                        "is_delete":false
                    },
                    {
                        "field_name":"report_time",
                        "alias_name":"",
                        "field_type":"string",
                        "description":"字段描述",
                        "tag":"metric",
                        "is_analyzed":false,
                        "is_dimension":false,
                        "is_time":true,
                        "is_delete":false,
                        "option":{
                            "time_zone":8,
                            "time_format":"yyyy-MM-dd HH:mm:ss"
                        }
                    }
                ],
                "bk_biz_id": 0,
                "visible_bk_biz_id": [],
                "visible_type": "current_biz",
                "alias_settings": [],
                "config_version": 1,
                "field_count": 2,
                "active_collector_count": 2,
                "pending_sync_collector_count": 1,
                "related_index_set_count": 1,
                "created_at": "2026-07-30 10:00:00",
                "created_by": "admin",
                "updated_at": "2026-07-30 10:00:00",
                "updated_by": "admin"
            },
            "result":true
        }
        """
        clean_template = CleanTemplateHandler.fill_template_stats([self.get_object()])[0]
        return Response(self.get_serializer(clean_template).data)

    def update(self, request, *args, clean_template_id=None, **kwargs):
        """
        @api {put} /databus/clean_template/$clean_template_id/ 4_清洗模板-更新
        @apiName update_clean_template
        @apiGroup 23_clean_template
        @apiDescription 更新清洗模板
        @apiParamExample {json} 成功请求
        {
            "name": "xxx",
            "clean_type":"bk_log_text",
            "etl_params":{
                "retain_original_text":true,
                "separator":" "
            },
            "etl_fields":[
                {
                    "field_name":"user",
                    "alias_name":"",
                    "field_type":"long",
                    "description":"字段描述",
                    "is_analyzed":true,
                    "is_dimension":false,
                    "is_time":false,
                    "is_delete":false
                },
                {
                    "field_name":"report_time",
                    "alias_name":"",
                    "field_type":"string",
                    "description":"字段描述",
                    "tag":"metric",
                    "is_analyzed":false,
                    "is_dimension":false,
                    "is_time":true,
                    "is_delete":false,
                    "option":{
                        "time_zone":8,
                        "time_format":"yyyy-MM-dd HH:mm:ss"
                    }
                }
            ]
        }
        @apiSuccessExample {json} 成功返回
        {
            "message": "",
            "code": 0,
            "data": {
                "clean_template_id": 1
            },
            "result": true
        }
        """
        clean_template = self.get_object()
        data = self.params_valid(CleanTemplateUpdateSerializer)
        return Response(
            CleanTemplateHandler(clean_template_id=clean_template.clean_template_id).create_or_update(params=data)
        )

    def create(self, request, *args, **kwargs):
        """
        @api {post} /databus/clean_template/ 3_清洗模板-新建
        @apiName create_clean_template
        @apiGroup 23_clean_template
        @apiDescription 新建清洗模板
        @apiParamExample {json} 成功请求
        {
            "name": "test",
            "clean_type":"bk_log_text",
            "etl_params":{
                "retain_original_text":true,
                "separator":" "
            },
            "etl_fields":[
                {
                    "field_name":"user",
                    "alias_name":"",
                    "field_type":"long",
                    "description":"字段描述",
                    "is_analyzed":true,
                    "is_dimension":false,
                    "is_time":false,
                    "is_delete":false
                },
                {
                    "field_name":"report_time",
                    "alias_name":"",
                    "field_type":"string",
                    "description":"字段描述",
                    "tag":"metric",
                    "is_analyzed":false,
                    "is_dimension":false,
                    "is_time":true,
                    "is_delete":false,
                    "option":{
                        "time_zone":8,
                        "time_format":"yyyy-MM-dd HH:mm:ss"
                    }
                }
            ],
            "bk_biz_id": 0
        }
        @apiSuccessExample {json} 成功返回
        {
            "message": "",
            "code": 0,
            "data": {
                "clean_template_id": 1
            },
            "result": true
        }
        """
        data = self.params_valid(CleanTemplateSerializer)
        return Response(CleanTemplateHandler().create_or_update(params=data))

    def destroy(self, request, *args, clean_template_id=None, **kwargs):
        """
        @api {delete} /databus/clean_template/$clean_template_id/ 5_清洗模板-删除
        @apiName destry_clean_template
        @apiGroup 23_clean_template
        @apiDescription 删除清洗模板
        @apiSuccessExample {json} 成功返回
        {
            "message": "",
            "code": 0,
            "data": 1,
            "result": true
        }
        """
        clean_template = self.get_object()
        return Response(CleanTemplateHandler(clean_template_id=clean_template.clean_template_id).destroy())

    @detail_route(methods=["GET"], url_path="collectors")
    def list_collectors(self, request, *args, clean_template_id=None, **kwargs):
        """
        @api {get} /databus/clean_template/$clean_template_id/collectors/ 6_清洗模板-关联采集项
        @apiName list_clean_template_collectors
        @apiGroup 23_clean_template
        @apiDescription 查询清洗模板关联的采集项
        @apiSuccess {Int} collector_config_id 采集项ID
        @apiSuccess {String} collector_config_name 采集项名称
        @apiSuccess {Int} bk_biz_id 业务ID
        @apiSuccess {Int/Null} index_set_id 索引集ID
        @apiSuccess {String/Null} index_set_name 索引集名称
        @apiSuccess {Array} related_index_set_list 关联索引集（索引组）列表
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": [
                {
                    "collector_config_id": 1,
                    "collector_config_name": "collector_name",
                    "bk_biz_id": 2,
                    "index_set_id": 3,
                    "index_set_name": "index_set_name",
                    "related_index_set_list": [
                        {
                            "index_set_id": 4,
                            "index_set_name": "parent_index_set_name"
                        }
                    ]
                }
            ],
            "result": true
        }
        """
        clean_template = self.get_object()
        collectors = CleanTemplateHandler(clean_template_id=clean_template.clean_template_id).list_collectors()
        return Response(collectors)

    @detail_route(methods=["POST"], url_path="sync")
    def sync_collectors(self, request, *args, clean_template_id=None, **kwargs):
        """
        @api {post} /databus/clean_template/$clean_template_id/sync/ 7_清洗模板-同步关联采集项
        @apiName sync_clean_template_collectors
        @apiGroup 23_clean_template
        @apiDescription 仅将模板配置同步到当前业务中失败、未同步或版本落后的关联采集项
        @apiSuccess {Int} id 采集项ID
        @apiSuccess {String} name 采集项名称
        @apiSuccess {String="SUCCESS","FAILED"} status 单项同步结果
        @apiSuccess {String} message 同步结果或错误信息
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": [
                {
                    "id": 1,
                    "name": "collector_name",
                    "status": "SUCCESS",
                    "message": "清洗模板同步成功"
                },
                {
                    "id": 2,
                    "name": "collector_name_2",
                    "status": "FAILED",
                    "message": "同步期间清洗模板关联关系发生变化，实际 RT 配置可能与当前配置不一致，请确认并重新保存采集项配置"
                }
            ],
            "result": true
        }
        """
        clean_template = self.get_object()
        collector_config_ids = self._get_authorized_sync_collector_ids(request, clean_template)
        return Response(
            CleanTemplateHandler(clean_template_id=clean_template.clean_template_id).sync_collectors(
                collector_config_ids=collector_config_ids
            )
        )

    @detail_route(methods=["POST"], url_path="etl_preview")
    def template_etl_preview(self, request, *args, clean_template_id=None, **kwargs):
        """
        @api {post} /databus/clean_template/$clean_template_id/etl_preview/ 8_清洗模板-使用模板预览
        @apiName clean_template_detail_etl_preview
        @apiGroup 23_clean_template
        @apiDescription 使用已保存的模板配置解析日志样例，并返回模板字段匹配情况
        @apiParam {String} data 日志样例
        @apiSuccess {Int} clean_template_id 清洗模板ID
        @apiSuccess {String} etl_config 模板清洗类型
        @apiSuccess {String} data 本次预览使用的日志样例
        @apiSuccess {Float} match_rate 字段匹配率
        @apiSuccess {Int} normal_count 正常字段数
        @apiSuccess {Int} abnormal_count 异常字段数
        @apiSuccess {List} fields 模板字段及其值、状态和异常原因
        @apiSuccess {String} fields.inferred_field_type 类型匹配时为模板类型，不匹配时为推断类型，空值时为null
        """
        clean_template = self.get_object()
        data = self.params_valid(CleanTemplatePreviewSerializer)
        return Response(
            CleanTemplateHandler(clean_template_id=clean_template.clean_template_id).preview(data=data["data"])
        )

    @list_route(methods=["POST"])
    def etl_preview(self, request, collector_config_id=None):
        """
        @api {post} /databus/clean_template/etl_preview/ 9_清洗模板-预览提取结果
        @apiName clean_template_etl_preview
        @apiDescription 清洗模板-预览提取结果
        @apiGroup 23_clean_template
        @apiParam {String} etl_config 清洗类型（格式化方式）
        @apiParam {Object} etl_params 清洗配置，不同的清洗类型的参数有所不同
        @apiParam {String} etl_params.separator 分隔符，当etl_config=="bk_log_delimiter"时需要传递
        @apiParam {String} etl_params.separator_regexp 正则表达式，当etl_config=="bk_log_regexp"时需要传递
        @apiParam {String} data 日志内容

        @apiSuccess {list} fields 字段列表
        @apiSuccess {Int} fields.field_index 字段顺序
        @apiSuccess {String} fields.field_name 字段名称 (分隔符默认为空)
        @apiSuccess {String} fields.value 值
        @apiParamExample {json} 请求样例:
        {
            "etl_config": "bk_log_text | bk_log_json | bk_log_regexp | bk_log_delimiter",
            "etl_params": {
                "separator": "|"
            },
            "data": "a|b|c"
        }
        @apiSuccessExample {json} 成功返回:
        {

            "message": "",
            "code": 0,
            "data": {
                "fields": [
                    {
                        "field_index": 1,
                        "field_name": "",
                        "value": "a"
                    },
                    {
                        "field_index": 2,
                        "field_name": "",
                        "value": "b"
                    },
                    {
                        "field_index": 3,
                        "field_name": "",
                        "value": "c"
                    }
                ]
            },
            "result": true
        }
        """
        data = self.params_valid(CollectorEtlSerializer)
        return Response(EtlHandler.etl_preview(**data))
