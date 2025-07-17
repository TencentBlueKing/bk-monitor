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

import copy
import json
import math

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework import serializers
from rest_framework.response import Response
from io import BytesIO

from apps.constants import NotifyType, UserOperationActionEnum, UserOperationTypeEnum
from apps.decorators import user_operation_record
from apps.exceptions import ValidationError
from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.feature_toggle.plugins.constants import LOG_DESENSITIZE, UNIFY_QUERY_SEARCH
from apps.generic import APIViewSet
from apps.iam import ActionEnum, ResourceEnum
from apps.iam.handlers.drf import (
    BatchIAMPermission,
    InstanceActionForDataPermission,
    InstanceActionPermission,
    ViewBusinessPermission,
)
from apps.log_search.constants import (
    FEATURE_ASYNC_EXPORT_COMMON,
    FEATURE_ASYNC_EXPORT_NOTIFY_TYPE,
    MAX_RESULT_WINDOW,
    OPERATORS,
    RESULT_WINDOW_COST_TIME,
    ExportStatus,
    ExportType,
    IndexSetType,
    QueryMode,
    SearchScopeEnum,
)
from apps.log_search.decorators import search_history_record
from apps.log_search.exceptions import BaseSearchIndexSetException
from apps.log_search.handlers.es.querystring_builder import QueryStringBuilder
from apps.log_search.handlers.index_set import (
    IndexSetCustomConfigHandler,
    IndexSetFieldsConfigHandler,
    IndexSetHandler,
    UserIndexSetConfigHandler,
)
from apps.log_search.handlers.search.async_export_handlers import AsyncExportHandlers, UnionAsyncExportHandlers
from apps.log_search.handlers.search.chart_handlers import ChartHandler
from apps.log_search.handlers.search.search_handlers_esquery import (
    SearchHandler as SearchHandlerEsquery,
)
from apps.log_search.handlers.search.search_handlers_esquery import UnionSearchHandler
from apps.log_search.models import AsyncTask, LogIndexSet
from apps.log_search.permission import Permission
from apps.log_search.serializers import (
    BcsWebConsoleSerializer,
    ChartSerializer,
    CreateIndexSetFieldsConfigSerializer,
    GetExportHistorySerializer,
    IndexSetCustomConfigSerializer,
    IndexSetFieldsConfigListSerializer,
    LogGrepQuerySerializer,
    OriginalSearchAttrSerializer,
    QueryStringSerializer,
    SearchAttrSerializer,
    SearchExportSerializer,
    SearchIndexSetScopeSerializer,
    SearchUserIndexSetConfigSerializer,
    SearchUserIndexSetDeleteConfigSerializer,
    SearchUserIndexSetOptionHistoryDeleteSerializer,
    SearchUserIndexSetOptionHistorySerializer,
    UISearchSerializer,
    UnionSearchAttrSerializer,
    UnionSearchExportSerializer,
    UnionSearchFieldsSerializer,
    UnionSearchGetExportHistorySerializer,
    UnionSearchHistorySerializer,
    UnionSearchSearchExportSerializer,
    UpdateIndexSetFieldsConfigSerializer,
    UserIndexSetCustomConfigSerializer,
)
from apps.log_search.utils import create_download_response
from apps.log_unifyquery.builder.context import build_context_params
from apps.log_unifyquery.builder.tail import build_tail_params
from apps.log_unifyquery.handler.async_export_handlers import (
    UnifyQueryAsyncExportHandlers,
    UnifyQueryUnionAsyncExportHandlers,
)
from apps.log_unifyquery.handler.base import UnifyQueryHandler
from apps.log_unifyquery.handler.context import UnifyQueryContextHandler
from apps.log_unifyquery.handler.tail import UnifyQueryTailHandler
from apps.utils.drf import detail_route, list_route
from apps.utils.local import get_request_external_username, get_request_username
from bkm_space.utils import space_uid_to_bk_biz_id


class SearchViewSet(APIViewSet):
    """
    检索
    """

    queryset = LogIndexSet.objects.all()
    serializer_class = serializers.Serializer
    lookup_field = "index_set_id"

    def get_permissions(self):
        if settings.BKAPP_IS_BKLOG_API:
            # 只在后台部署时做白名单校验
            auth_info = Permission.get_auth_info(self.request, raise_exception=False)
            # ESQUERY白名单不需要鉴权
            if auth_info and auth_info["bk_app_code"] in settings.ESQUERY_WHITE_LIST:
                return []

        if self.action in ["operators", "user_search_history"]:
            return []

        if self.action in [
            "bizs",
            "search",
            "context",
            "tailf",
            "export",
            "fields",
            "history",
            "chart",
            "generate_sql",
        ]:
            return [InstanceActionPermission([ActionEnum.SEARCH_LOG], ResourceEnum.INDICES)]

        if self.action in ["union_search", "config"]:
            if self.action == "config":
                if self.request.data.get("index_set_type", IndexSetType.SINGLE.value) == IndexSetType.SINGLE.value:
                    return [
                        InstanceActionForDataPermission("index_set_id", [ActionEnum.SEARCH_LOG], ResourceEnum.INDICES)
                    ]
                else:
                    return [BatchIAMPermission("index_set_ids", [ActionEnum.SEARCH_LOG], ResourceEnum.INDICES)]
            self.request.data["index_set_ids"] = [
                config["index_set_id"] for config in self.request.data.get("union_configs", [])
            ]
            return [BatchIAMPermission("index_set_ids", [ActionEnum.SEARCH_LOG], ResourceEnum.INDICES)]

        return [ViewBusinessPermission()]

    def list(self, request, *args, **kwargs):
        """
        @api {get} /search/index_set/?space_uid=$space_uid&is_group=false 01_搜索-索引集列表
        @apiDescription 用户有权限的索引集列表
        @apiName search_index_set
        @apiGroup 11_Search
        @apiParam {String} space_uid 空间唯一标识
        @apiSuccess {Int} index_set_id 索引集ID
        @apiSuccess {String} index_set_name 索引集名称
        @apiSuccess {Boolean} is_favorite 索引集为收藏索引集
        @apiSuccess {List} tags 索引集标签
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": [
                {
                    "index_set_id": 1,
                    "index_set_name": "索引集名称",
                    "scenario_id": "接入场景",
                    "scenario_name": "接入场景名称",
                    "storage_cluster_id": "存储集群ID",
                    "indices": [
                        {
                            "result_table_id": "结果表id",
                            "result_table_name": "结果表名称"
                        }
                    ],
                    "time_field": "dtEventTimeStamp",
                    "time_field_type": "date",
                    "time_field_unit": "microsecond",
                    "tags": [{"name": "test", "color": "xxx"}],
                    "is_favorite": true
                }
            ],
            "result": true
        }
        """
        data = self.params_valid(SearchIndexSetScopeSerializer)
        result_list = IndexSetHandler().get_user_index_set(data["space_uid"], data["is_group"])

        # 构建一个包含所有子项的列表，利用引用赋值特性
        all_items = []
        for item in result_list:
            all_items.append(item)
            if "children" in item and isinstance(item["children"], list):
                all_items.extend(item["children"])

        # 获取资源
        resources = []
        for item in all_items:
            attribute = {}
            if "bk_biz_id" in item:
                attribute["bk_biz_id"] = item["bk_biz_id"]
            if "space_uid" in item:
                attribute["space_uid"] = item["space_uid"]
            resources.append(
                [ResourceEnum.INDICES.create_simple_instance(instance_id=item["index_set_id"], attribute=attribute)]
            )

        if not resources:
            return Response(result_list)

        # 权限处理
        if settings.IGNORE_IAM_PERMISSION:
            for item in all_items:
                item.setdefault("permission", {})
                item["permission"].update({ActionEnum.SEARCH_LOG.id: True})
            return Response(result_list)

        from apps.iam.handlers.permission import Permission

        permission_result = Permission().batch_is_allowed([ActionEnum.SEARCH_LOG], resources)
        for item in all_items:
            origin_instance_id = item["index_set_id"]
            if not origin_instance_id:
                # 如果拿不到实例ID，则不处理
                continue
            instance_id = str(origin_instance_id)
            item.setdefault("permission", {})
            item["permission"].update(permission_result[instance_id])

        return Response(result_list)

    @detail_route(methods=["GET"], url_path="bizs")
    def bizs(self, request, *args, **kwargs):
        """
        @api {get} /search/index_set/$index_set_id/bizs/ 05_索引集-业务列表
        @apiName get_index_set_bizs
        @apiGroup 11_Search
        @apiParam {Int} index_set_id 索引集ID
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": [
                {
                    "bk_biz_id": 1,
                    "bk_biz_name": "业务名称"
                }
            ],
            "result": true
        }
        """
        return Response(IndexSetHandler(index_set_id=kwargs["index_set_id"]).bizs())

    @detail_route(methods=["POST"], url_path="search")
    @search_history_record
    def search(self, request, index_set_id=None):
        """
        @api {post} /search/index_set/$index_set_id/search/ 11_搜索-日志内容
        @apiName search_log
        @apiGroup 11_Search
        @apiParam {String} start_time 开始时间
        @apiParam {String} end_time 结束时间
        @apiParam {String} time_range 时间标识符符["15m", "30m", "1h", "4h", "12h", "1d", "customized"]
        @apiParam {String} keyword 搜索关键字
        @apiParam {Json} ip IP列表
        @apiParam {Json} addition 搜索条件
        @apiParam {Int} begin 起始位置
        @apiParam {Int} size 条数
        @apiParam {Dict} aggs ES的聚合参数 （非必填，默认为{}）
        @apiParamExample {Json} 请求参数
        {
            "start_time": "2019-06-11 00:00:00",
            "end_time": "2019-06-12 11:11:11",
            "time_range": "customized"
            "keyword": "error",
            "host_scopes": {
                "modules": [
                    {
                        "bk_obj_id": "module",
                        "bk_inst_id": 4
                    },
                    {
                        "bk_obj_id": "set",
                        "bk_inst_id": 4
                    }
                ],
                "ips": "127.0.0.1, 127.0.0.2"
            },
            "addition": [
                {
                    "key": "ip",
                    "method": "is",
                    "value": "127.0.0.1",
                    "condition": "and",  (默认不传是and，只支持and or)
                    "type": "field" (默认field 目前支持field，其他无效)
                }
            ],
            "begin": 0,
            "size": 15
        }

        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": {
                "total": 100,
                "took": 0.29,
                "list": [
                    {
                        "srcDataId": "2087",
                        "dtEventTimeStamp": 1534825132000,
                        "moduleName": "公共组件->consul",
                        "log": "is_cluster</em>-COMMON: ok",
                        "sequence": 1,
                        "dtEventTime": "2018-08-21 04:18:52",
                        "timestamp": 1534825132,
                        "serverIp": "127.0.0.1",
                        "errorCode": "0",
                        "gseIndex": 152358,
                        "dstDataId": "2087",
                        "worldId": "-1",
                        "logTime": "2018-08-21 12:18:52",
                        "path": "/tmp/health_check.log",
                        "platId": 0,
                        "localTime": "2018-08-21 04:18:00"
                    }
                ],
                "fields": {
                    "agent": {
                        "max_length": 101
                    },
                    "bytes": {
                        "max_length": 4
                    },
                }
            },
            "result": true
        }
        """
        data = self.params_valid(SearchAttrSerializer)
        search_handler = SearchHandlerEsquery(index_set_id, data)
        if data.get("is_scroll_search"):
            return Response(search_handler.scroll_search())

        if FeatureToggleObject.switch(UNIFY_QUERY_SEARCH, data.get("bk_biz_id")):
            data["index_set_ids"] = [index_set_id]
            query_handler = UnifyQueryHandler(data)
            return Response(query_handler.search())
        else:
            return Response(search_handler.search())

    @detail_route(methods=["POST"], url_path="search/original")
    def original_search(self, request, index_set_id=None):
        """
        @api {post} /search/index_set/$index_set_id/search/original/ 11_搜索-原始日志内容
        @apiName search_original_log
        @apiGroup 11_Search
        @apiParam {Int} begin 起始位置
        @apiParam {Int} size 条数
        @apiParamExample {Json} 请求参数
        {
            "begin": 0,
            "size": 3
        }

        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": {
                "total": 100,
                "took": 0.29,
                "list": [
                    {
                        "srcDataId": "2087",
                        "dtEventTimeStamp": 1534825132000,
                        "moduleName": "公共组件->consul",
                        "log": "is_cluster</em>-COMMON: ok",
                        "sequence": 1,
                        "dtEventTime": "2018-08-21 04:18:52",
                        "timestamp": 1534825132,
                        "serverIp": "127.0.0.1",
                        "errorCode": "0",
                        "gseIndex": 152358,
                        "dstDataId": "2087",
                        "worldId": "-1",
                        "logTime": "2018-08-21 12:18:52",
                        "path": "/tmp/health_check.log",
                        "platId": 0,
                        "localTime": "2018-08-21 04:18:00"
                    }
                ],
                "fields": {
                    "agent": {
                        "max_length": 101
                    },
                    "bytes": {
                        "max_length": 4
                    },
                }
            },
            "result": true
        }
        """
        data = self.params_valid(OriginalSearchAttrSerializer)
        data["original_search"] = True
        data["is_desensitize"] = False
        search_handler = SearchHandlerEsquery(index_set_id, data)
        return Response(search_handler.search())

    @detail_route(methods=["POST"], url_path="context")
    def context(self, request, index_set_id=None):
        """
        @api {post} /search/index_set/$index_set_id/context/ 13_搜索-上下文 [TODO]
        @apiName search_log_context
        @apiGroup 11_Search
        @apiParam {String} index_id 索引ID
        @apiParam {String} ip IP
        @apiParam {String} path 日志路径
        @apiParam {Int} gse_index 日志所在GSE位置
        @apiParam {Int} size 上下文条数
        @apiParam {Int} container_id docker used
        @apiParam {String} logfile docker used
        @apiParam {Int} begin 日志游标
        @apiParamExample {Json} 请求参数
        {
            "gseindex": 59810429,
            "ip": "127.0.0.1",
            "path": "/data/home/user00/log/accountsvrd/accountsvrd_127.0.0.1.error",
            "size": 500,
            "begin": 0
        }
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": {
                "total": 100,
                "took": 0.29,
                "list": [
                    {
                        "srcDataId": "2087",
                        "dtEventTimeStamp": 1534825132000,
                        "moduleName": "公共组件->consul",
                        "log": "is_cluster</em>-COMMON: ok",
                        "sequence": 1,
                        "dtEventTime": "2018-08-21 04:18:52",
                        "timestamp": 1534825132,
                        "serverIp": "127.0.0.1",
                        "errorCode": "0",
                        "gseIndex": 152358,
                        "dstDataId": "2087",
                        "worldId": "-1",
                        "logTime": "2018-08-21 12:18:52",
                        "path": "/tmp/health_check.log",
                        "platId": 0,
                        "localTime": "2018-08-21 04:18:00"
                    }
                ]
            },
            "result": true
        }
        """
        data = request.data
        data.update({"search_type_tag": "context"})
        # 获取所属业务id
        index_set_obj = LogIndexSet.objects.filter(index_set_id=index_set_id).first()
        if index_set_obj:
            data["bk_biz_id"] = space_uid_to_bk_biz_id(index_set_obj.space_uid)
        if FeatureToggleObject.switch(UNIFY_QUERY_SEARCH, data.get("bk_biz_id")):
            data.update({"index_set_id": index_set_id})
            params = build_context_params(data)
            query_handler = UnifyQueryContextHandler(params)
            return Response(query_handler.search())
        else:
            data.update({"search_type_tag": "context"})
            query_handler = SearchHandlerEsquery(index_set_id, data)
            return Response(query_handler.search_context())

    @detail_route(methods=["POST"], url_path="tail_f")
    def tailf(self, request, index_set_id=None):
        """
        @api {post} /search/index_set/$index_set_id/tail_f/ 12_搜索-实时日志 [TODO]
        @apiName search_log_tailf
        @apiGroup 11_Search
        @apiParam {String} index_id 索引ID
        @apiParam {String} ip IP
        @apiParam {String} path 日志路径
        @apiParam {Int} gse_index 日志所在GSE位置(not necessary, timestamp would be better)
        @apiParamExample {Json} 请求参数
        {
            "ip": "127.0.0.1",
            "path": "/data/home/user00/log/accountsvrd/accountsvrd_127.0.0.1.error",
            "size": 500,
            "gseindex": 59810429,
            "order": "-"
        }
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": {
                "total": 100,
                "took": 0.29,
                "list": [
                    {
                        "srcDataId": "2087",
                        "dtEventTimeStamp": 1534825132000,
                        "moduleName": "公共组件->consul",
                        "log": "is_cluster</em>-COMMON: ok",
                        "sequence": 1,
                        "dtEventTime": "2018-08-21 04:18:52",
                        "timestamp": 1534825132,
                        "serverIp": "127.0.0.1",
                        "errorCode": "0",
                        "gseIndex": 152358,
                        "dstDataId": "2087",
                        "worldId": "-1",
                        "logTime": "2018-08-21 12:18:52",
                        "path": "/tmp/health_check.log",
                        "platId": 0,
                        "localTime": "2018-08-21 04:18:00"
                    }
                ]
            },
            "result": true
        }
        """
        data = request.data
        # 获取所属业务id
        index_set_obj = LogIndexSet.objects.filter(index_set_id=index_set_id).first()
        if index_set_obj:
            data["bk_biz_id"] = space_uid_to_bk_biz_id(index_set_obj.space_uid)
        if FeatureToggleObject.switch(UNIFY_QUERY_SEARCH, data.get("bk_biz_id")):
            data.update({"index_set_id": index_set_id})
            params = build_tail_params(data)
            query_handler = UnifyQueryTailHandler(params)
            return Response(query_handler.search())
        else:
            data.update({"search_type_tag": "tail"})
            query_handler = SearchHandlerEsquery(index_set_id, data)
            return Response(query_handler.search_tail_f())

    @detail_route(methods=["POST"], url_path="export")
    def export(self, request, index_set_id=None):
        """
        @api {post} /search/index_set/$index_set_id/export/ 14_搜索-导出日志
        @apiName search_log_export
        @apiGroup 11_Search
        @apiParam bk_biz_id [Int] 业务id
        @apiParam keyword [String] 搜索关键字
        @apiParam time_range [String] 时间范围
        @apiParam start_time [String] 起始时间
        @apiParam end_time [String] 结束时间
        @apiParam host_scopes [Dict] 检索模块ip等信息
        @apiParam begin [Int] 检索开始 offset
        @apiParam size [Int]  检索结果大小
        @apiParam interval [String] 匹配规则
        @apiParamExample {Json} 请求参数
        {
            "bk_biz_id":"215",
            "keyword":"*",
            "time_range":"5m",
            "start_time":"2021-06-08 11:02:21",
            "end_time":"2021-06-08 11:07:21",
            "host_scopes":{
                "modules":[

                ],
                "ips":""
            },
            "addition":[

            ],
            "begin":0,
            "size":188,
            "interval":"auto",
            "isTrusted":true
        }

        @apiSuccessExample text/plain 成功返回:
        {"a": "good", "b": {"c": ["d", "e"]}}
        {"a": "good", "b": {"c": ["d", "e"]}}
        {"a": "good", "b": {"c": ["d", "e"]}}
        """
        request_user = get_request_external_username() or get_request_username()
        data = self.params_valid(SearchExportSerializer)
        if "is_desensitize" in data and not data["is_desensitize"] and request.user.is_superuser:
            data["is_desensitize"] = False
        else:
            data["is_desensitize"] = True
        index_set_id = int(index_set_id)
        request_data = copy.deepcopy(data)

        tmp_index_obj = LogIndexSet.objects.filter(index_set_id=index_set_id).first()
        if tmp_index_obj:
            index_set_data_obj_list = tmp_index_obj.get_indexes(has_applied=True)
            if len(index_set_data_obj_list) > 0:
                index_list = [x.get("result_table_id", "unknow") for x in index_set_data_obj_list]
                index = "_".join(index_list).replace(".", "_")
            else:
                raise BaseSearchIndexSetException(BaseSearchIndexSetException.MESSAGE.format(index_set_id=index_set_id))
        else:
            raise BaseSearchIndexSetException(BaseSearchIndexSetException.MESSAGE.format(index_set_id=index_set_id))

        output = BytesIO()
        if FeatureToggleObject.switch(UNIFY_QUERY_SEARCH, data.get("bk_biz_id")):
            data["index_set_ids"] = [index_set_id]
            query_handler = UnifyQueryHandler(data)
            result = query_handler.search(is_export=True)
        else:
            export_fields = data.get("export_fields", [])
            search_handler = SearchHandlerEsquery(
                index_set_id, search_dict=data, export_fields=export_fields, export_log=True
            )
            result = search_handler.search(is_export=True)
        result_list = result.get("origin_log_list")
        for item in result_list:
            json_data = json.dumps(item, ensure_ascii=False).encode("utf8")
            output.write(json_data + b"\n")
        file_name = f"bk_log_search_{index}.log"
        response = create_download_response(output, file_name)

        AsyncTask.objects.create(
            request_param=request_data,
            scenario_id=data["scenario_id"],
            index_set_id=index_set_id,
            result=True,
            completed_at=timezone.now(),
            export_status=ExportStatus.SUCCESS,
            start_time=data["start_time"],
            end_time=data["end_time"],
            export_type=ExportType.SYNC,
            bk_biz_id=data["bk_biz_id"],
            created_by=request_user,
        )

        # add user_operation_record
        operation_record = {
            "username": get_request_username(),
            "space_uid": tmp_index_obj.space_uid,
            "record_type": UserOperationTypeEnum.EXPORT,
            "record_object_id": index_set_id,
            "action": UserOperationActionEnum.START,
            "params": request_data,
        }
        user_operation_record.delay(operation_record)

        return response

    @detail_route(methods=["POST"], url_path="quick_export")
    def quick_export(self, request, index_set_id=None):
        """
        @api /search/index_set/$index_set_id/quick_export/ 15-搜索-快速导出日志
        @apiDescription 快速下载检索日志
        @apiName quick_export
        @apiGroup 11_Search
        @apiParam bk_biz_id [Int] 业务id
        @apiParam keyword [String] 搜索关键字
        @apiParam time_range [String] 时间范围
        @apiParam start_time [String] 起始时间
        @apiParam end_time [String] 结束时间
        @apiParam host_scopes [Dict] 检索模块ip等信息
        @apiParam begin [Int] 检索开始 offset
        @apiParam size [Int]  检索结果大小
        @apiParam interval [String] 匹配规则
        @apiParamExample {Json} 请求参数
        {
            "bk_biz_id":"215",
            "keyword":"*",
            "time_range":"5m",
            "start_time":"2021-06-08 11:02:21",
            "end_time":"2021-06-08 11:07:21",
            "host_scopes":{
                "modules":[

                ],
                "ips":""
            },
            "addition":[

            ],
            "begin":0,
            "size":188,
            "interval":"auto",
            "isTrusted":true
        }
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": {
                "task_id": 1,
                "prompt": "任务提交成功，系统处理后将通过邮件通知，请留意！"
            },
            "code": 0,
            "message": ""
        }
        """
        return self._export(request, index_set_id, is_quick_export=True)

    @detail_route(methods=["POST"], url_path="async_export")
    def async_export(self, request, index_set_id=None):
        """
        @api /search/index_set/$index_set_id/async_export/ 15-搜索-异步导出日志
        @apiDescription 异步下载检索日志
        @apiName async_export
        @apiGroup 11_Search
        @apiParam bk_biz_id [Int] 业务id
        @apiParam keyword [String] 搜索关键字
        @apiParam time_range [String] 时间范围
        @apiParam start_time [String] 起始时间
        @apiParam end_time [String] 结束时间
        @apiParam host_scopes [Dict] 检索模块ip等信息
        @apiParam begin [Int] 检索开始 offset
        @apiParam size [Int]  检索结果大小
        @apiParam interval [String] 匹配规则
        @apiParamExample {Json} 请求参数
        {
            "bk_biz_id":"215",
            "keyword":"*",
            "time_range":"5m",
            "start_time":"2021-06-08 11:02:21",
            "end_time":"2021-06-08 11:07:21",
            "host_scopes":{
                "modules":[

                ],
                "ips":""
            },
            "addition":[

            ],
            "begin":0,
            "size":188,
            "interval":"auto",
            "isTrusted":true
        }
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": {
                "task_id": 1,
                "prompt": "任务提交成功，系统处理后将通过邮件通知，请留意！"
            },
            "code": 0,
            "message": ""
        }
        """
        return self._export(request, index_set_id, is_quick_export=False)

    def _export(self, request, index_set_id, is_quick_export):
        data = self.params_valid(SearchExportSerializer)
        if "is_desensitize" in data and not data["is_desensitize"] and request.user.is_superuser:
            data["is_desensitize"] = False
        else:
            data["is_desensitize"] = True
        notify_type_name = NotifyType.get_choice_label(
            FeatureToggleObject.toggle(FEATURE_ASYNC_EXPORT_COMMON).feature_config.get(FEATURE_ASYNC_EXPORT_NOTIFY_TYPE)
        )

        if FeatureToggleObject.switch(UNIFY_QUERY_SEARCH, data.get("bk_biz_id")):
            task_id, size = UnifyQueryAsyncExportHandlers(
                index_set_id=int(index_set_id),
                bk_biz_id=data["bk_biz_id"],
                search_dict=data,
                export_fields=data["export_fields"],
                export_file_type=data["file_type"],
            ).async_export(is_quick_export=is_quick_export)
        else:
            task_id, size = AsyncExportHandlers(
                index_set_id=int(index_set_id),
                bk_biz_id=data["bk_biz_id"],
                search_dict=data,
                export_fields=data["export_fields"],
                export_file_type=data["file_type"],
            ).async_export(is_quick_export=is_quick_export)
        return Response(
            {
                "task_id": task_id,
                "prompt": _(
                    "任务提交成功，预估等待时间{time}分钟,系统处理后将通过{notify_type_name}通知，请留意！"
                ).format(
                    time=math.ceil(size / MAX_RESULT_WINDOW * RESULT_WINDOW_COST_TIME),
                    notify_type_name=notify_type_name,
                ),
            }
        )

    @list_route(methods=["POST"], url_path="union_async_export")
    def union_async_export(self, request, *args, **kwargs):
        """
        @api /search/index_set/$index_set_id/union_async_export/
        @apiDescription 联合查询异步下载检索日志
        @apiName union_async_export
        @apiGroup 11_Search
        @apiParam bk_biz_id [Int] 业务id
        @apiParam keyword [String] 搜索关键字
        @apiParam time_range [String] 时间范围
        @apiParam start_time [String] 起始时间
        @apiParam end_time [String] 结束时间
        @apiParam begin [Int] 检索开始 offset
        @apiParam size [Int]  检索结果大小
        @apiParam addition [List]  搜索条件
        @apiParam ip_chooser [Dict]  检索IP条件
        @apiParam is_quick_export [Bool] 是否快速导出 默认为False
        @apiParam {Array[Json]} union_configs 联合检索索引集配置
        @apiParam {Int} union_configs.index_set_id 索引集ID
        @apiParam {Int} union_configs.begin 索引对应的滚动条数
        @apiParam {Bool} union_configs.is_desensitize 是否脱敏 默认为True（只针对白名单SaaS开放此参数）
        @apiParamExample {Json} 请求参数
        {
        "bk_biz_id": "2",
        "size": 12699,
        "start_time": 1747234800000,
        "end_time": 1747238399999,
        "addition": [],
        "begin": 0,
        "ip_chooser": {},
        "keyword": "*",
        "union_configs": [
            {
                "begin": 0,
                "index_set_id": "66"
            },
            {
                "begin": 0,
                "index_set_id": "53"
            }
        ],
        "is_quick_export": true
        }
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": {
                "task_id": 1,
                "prompt": "任务提交成功，系统处理后将通过邮件通知，请留意！"
            },
            "code": 0,
            "message": ""
        }
        """
        data = self.params_valid(UnionSearchExportSerializer)
        auth_info = Permission.get_auth_info(self.request, raise_exception=False)
        is_verify = False if not auth_info or auth_info["bk_app_code"] not in settings.ESQUERY_WHITE_LIST else True
        for info in data.get("union_configs", []):
            if not info.get("is_desensitize") and not is_verify:
                info["is_desensitize"] = True
        notify_type_name = NotifyType.get_choice_label(
            FeatureToggleObject.toggle(FEATURE_ASYNC_EXPORT_COMMON).feature_config.get(FEATURE_ASYNC_EXPORT_NOTIFY_TYPE)
        )
        is_quick_export = data.pop("is_quick_export")
        if FeatureToggleObject.switch(UNIFY_QUERY_SEARCH, data.get("bk_biz_id")):
            task_id, size = UnifyQueryUnionAsyncExportHandlers(
                index_set_ids=data["index_set_ids"],
                bk_biz_id=data["bk_biz_id"],
                search_dict=data,
                export_fields=data["export_fields"],
                export_file_type=data["file_type"],
            ).async_export(is_quick_export=is_quick_export)
        else:
            task_id, size = UnionAsyncExportHandlers(
                bk_biz_id=data["bk_biz_id"],
                search_dict=data,
                index_set_ids=data["index_set_ids"],
                export_file_type=data["file_type"],
            ).async_export(is_quick_export=is_quick_export)
        return Response(
            {
                "task_id": task_id,
                "prompt": _(
                    "任务提交成功，预估等待时间{time}分钟,系统处理后将通过{notify_type_name}通知，请留意！"
                ).format(
                    time=math.ceil(size / MAX_RESULT_WINDOW * RESULT_WINDOW_COST_TIME),
                    notify_type_name=notify_type_name,
                ),
            }
        )

    @detail_route(methods=["GET"], url_path="export_history")
    def get_export_history(self, request, index_set_id=None):
        """
        @api {get} /search/index_set/$index_set_id/export_history/?page=1&pagesize=10 16_搜索-异步导出历史
        @apiDescription 16_搜索-异步导出历史
        @apiName export_history
        @apiGroup 11_Search
        @apiParam {Int} index_set_id 索引集id
        @apiParam {Int} page 当前页
        @apiParam {Int} pagesize 页面大小
        @apiParam {Bool} show_all 是否展示所有历史
        @apiParam {Int} bk_biz_id 业务id
        @apiSuccess {Int} total 返回大小
        @apiSuccess {list} list 返回结果列表
        @apiSuccess {Int} list.id 导出历史任务id
        @apiSuccess {Int} list.log_index_set_id 导出索引集id
        @apiSuccess {Str} list.search_dict 导出请求参数
        @apiSuccess {Str} list.start_time 导出请求所选择开始时间
        @apiSuccess {Str} list.end_time 导出请求所选择结束时间
        @apiSuccess {Str} list.export_type 导出请求类型
        @apiSuccess {Str} list.export_status 导出状态
        @apiSuccess {Str} list.error_msg 导出请求异常原因
        @apiSuccess {Str} list.download_url 异步导出下载地址
        @apiSuccess {Str} list.export_pkg_name 异步导出打包名
        @apiSuccess {int} list.export_pkg_size 异步导出包大小 单位M
        @apiSuccess {Str} list.export_created_at 异步导出创建时间
        @apiSuccess {Str} list.export_created_by 异步导出创建者
        @apiSuccess {Str} list.export_completed_at 异步导出成功时间
        @apiSuccess {Bool} list.download_able 是否可下载（不可下载禁用下载按钮且hover提示"下载链接过期"）
        @apiSuccess {Bool} list.retry_able 是否可重试（不可重试禁用对应按钮且hover提示"数据源过期"）
        @apiSuccessExample {json} 成功返回：
        {
            "result":true,
            "data":{
                "total":10,
                "list":[
                    {
                        "id": 1,
                        "log_index_set_id": 1,
                        "search_dict":"",
                        "start_time": "",
                        "end_time": "",
                        "export_type": "",
                        "export_status": "",
                        "error_msg":"",
                        "download_url":"",
                        "export_pkg_name": "",
                        "export_pkg_size": 1,
                        "export_created_at":"",
                        "export_created_by":"",
                        "export_completed_at":""，
                        "download_able": true,
                        "retry_able": true
                    }
                ]
            },
            "code":0,
            "message":""
        }
        """
        data = self.params_valid(GetExportHistorySerializer)
        return AsyncExportHandlers(index_set_id=int(index_set_id), bk_biz_id=data["bk_biz_id"]).get_export_history(
            request=request, view=self, show_all=data["show_all"]
        )

    @detail_route(methods=["GET"], url_path="fields")
    def fields(self, request, *args, **kwargs):
        """
        @api {get} /search/index_set/$index_set_id/fields/?scope=search_context 02_搜索-获取索引集配置
        @apiDescription 获取用户在某个索引集的配置 @TODO 前端需要调整
        @apiName list_search_index_set_user_config
        @apiGroup 11_Search
        @apiParam {String} [start_time] 开始时间(非必填)
        @apiParam {String} [end_time] 结束时间（非必填)
        @apiSuccess {String} display_fields 列表页显示的字段
        @apiSuccess {String} fields.field_name 字段名
        @apiSuccess {String} fields.field_alias 字段中文称 (为空时会直接取description)
        @apiSuccess {String} fields.description 字段说明
        @apiSuccess {String} fields.field_type 字段类型
        @apiSuccess {Bool} fields.is_display 是否显示给用户
        @apiSuccess {Bool} fields.is_editable 是否可以编辑（是否显示）
        @apiSuccess {Bool} fields.es_doc_values 是否聚合字段
        @apiSuccess {Bool} fields.is_analyzed 是否分词字段
        @apiSuccess {String} time_field 时间字段
        @apiSuccess {String} time_field_type 时间字段类型
        @apiSuccess {String} time_field_unit 时间字段单位
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": {
                "config": [
                    {
                        "name": "bcs_web_console"
                        "is_active": True,
                    },
                    {
                        name: "bkmonitor",
                        "is_active": True,
                    },
                    {
                        "name": "ip_topo_switch",
                        "is_active": True,
                    },
                    {
                        "name": "async_export",
                        "is_active": True, # async_export_usable
                        "extra": {
                            "fields": ["dtEventTimeStamp", "serverIp", "gseIndex", "iterationIndex"],
                            "usable_reason": ""
                        }
                    },
                    {
                        "name": "context_and_realtime", # context_search_usable realtime_search_usable
                        "is_active": True,
                        "extra": {
                            "reason": ""  #usable_reason
                        }
                    },
                    {
                        "name": "trace",
                        "is_active": True,
                        "extra": {
                            field: "trace_id"
                            index_set_name: "test_stag_oltp"
                        }
                    },
                ],
                "display_fields": ["dtEventTimeStamp", "log"],
                "fields": [
                    {
                        "field_name": "log",
                        "field_alias": "日志",
                        "field_type": "text",
                        "is_display": true,
                        "is_editable": true,
                        "description": "日志",
                        "es_doc_values": false
                    },
                    {
                        "field_name": "dtEventTimeStamp",
                        "field_alias": "时间",
                        "field_type": "date",
                        "is_display": true,
                        "is_editable": true,
                        "description": "描述",
                        "es_doc_values": true
                    }
                ],
                "sort_list": [
                    ["aaa", "desc"],
                    ["bbb", "asc"]
                ]
            },
            "result": true
        }
        """
        index_set_id = kwargs.get("index_set_id", "")
        scope = request.GET.get("scope", SearchScopeEnum.DEFAULT.value)
        is_realtime = bool(request.GET.get("is_realtime", False))
        if scope is not None and scope not in SearchScopeEnum.get_keys():
            raise ValidationError(_("scope取值范围：default、search_context"))

        # 将日期中的&nbsp;替换为标准空格
        start_time = request.GET.get("start_time", "").replace("&nbsp;", " ")
        end_time = request.GET.get("end_time", "").replace("&nbsp;", " ")
        custom_indices = request.GET.get("custom_indices", "")
        if scope == SearchScopeEnum.DEFAULT.value and not is_realtime and not start_time and not end_time:
            # 使用缓存
            fields = self.get_object().get_fields(use_snapshot=True)
        else:
            search_dict = {"start_time": start_time, "end_time": end_time}
            if custom_indices:
                search_dict.update({"custom_indices": custom_indices})
            search_handler_esquery = SearchHandlerEsquery(index_set_id, search_dict)
            fields = search_handler_esquery.fields(scope)

        # 添加用户索引集自定义配置
        index_set_config = UserIndexSetConfigHandler(index_set_id=int(index_set_id)).get_index_set_config()
        fields.update({"user_custom_config": index_set_config})

        # 添加索引集自定义配置
        custom_config = IndexSetCustomConfigHandler(index_set_id=int(index_set_id)).get_index_set_config()
        fields.update({"custom_config": custom_config})
        return Response(fields)

    @detail_route(methods=["GET"], url_path="bcs_web_console")
    def bcs_web_console(self, request, *args, **kwargs):
        """
        @api {get} /search/index_set/$index_set_id/bcs_web_console/ 获取bcs容器管理页面url
        @apiDescription 获取bcs容器管理页面url
        @apiName bcs_web_console
        @apiGroup 11_Search
        @apiParam {String} cluster_id 集群id
        @apiParam {String} container_id 容器id
        @apiSuccess {String} data bcs容器管理页面url
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": "http://...",
            "result": true
        }
        """
        data = self.params_valid(BcsWebConsoleSerializer)

        return Response(SearchHandlerEsquery.get_bcs_manage_url(data["cluster_id"], data["container_id"]))

    @list_route(methods=["POST"], url_path="config")
    def config(self, request, *args, **kwargs):
        """
        @api {post} /search/index_set/config/?scope=search_context 03_搜索-索引集配置
        @apiDescription 更新用户在某个索引集的配置
        @apiName update_user_index_set_config
        @apiGroup 11_Search
        @apiParamExample {Json} 请求参数
        {
            "config_id": 1
        }
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": null,
            "result": true
        }
        """
        data = self.params_valid(SearchUserIndexSetConfigSerializer)
        if data["index_set_type"] == IndexSetType.SINGLE.value:
            result = IndexSetHandler(index_set_id=data["index_set_id"]).config(config_id=data["config_id"])
        else:
            result = IndexSetHandler().config(
                config_id=data["config_id"],
                index_set_ids=data["index_set_ids"],
                index_set_type=data["index_set_type"],
            )
        return Response(result)

    @list_route(methods=["POST"], url_path="create_config")
    def create_config(self, request, *args, **kwargs):
        """
        @api {post} /search/index_set/create_config/ 03_搜索-创建索引集配置
        @apiDescription 创建索引集的字段配置
        @apiName create_index_set_config
        @apiGroup 11_Search
        @apiParamExample {Json} 请求参数
        {
            "name": xxx,
            "display_fields": ["aaa", "bbb"]
            "sort_list": [
                ["aaa", "desc"],
                ["bbb", "asc"]
            ]
        }
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": null,
            "result": true
        }
        """
        data = self.params_valid(CreateIndexSetFieldsConfigSerializer)
        if data.get("index_set_type") == IndexSetType.SINGLE.value:
            SearchHandlerEsquery(data["index_set_id"], {}).verify_sort_list_item(data["sort_list"])
            init_params = {
                "index_set_id": data["index_set_id"],
                "index_set_type": data["index_set_type"],
            }
        else:
            init_params = {
                "index_set_ids": data["index_set_ids"],
                "index_set_type": data["index_set_type"],
            }
        result = IndexSetFieldsConfigHandler(**init_params).create_or_update(
            name=data["name"], display_fields=data["display_fields"], sort_list=data["sort_list"]
        )
        return Response(result)

    @list_route(methods=["POST"], url_path="update_config")
    def update_config(self, request, *args, **kwargs):
        """
        @api {post} /search/index_set/update_config/ 03_搜索-修改索引集配置
        @apiDescription 更新某个索引集的字段配置
        @apiName update_index_set_config
        @apiGroup 11_Search
        @apiParamExample {Json} 请求参数
        {
            "name": xxx,
            "display_fields": ["aaa", "bbb"]
            "sort_list": [
                ["aaa", "desc"],
                ["bbb", "asc"]
            ]
        }
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": null,
            "result": true
        }
        """
        data = self.params_valid(UpdateIndexSetFieldsConfigSerializer)
        if data.get("index_set_type") == IndexSetType.SINGLE.value:
            SearchHandlerEsquery(data["index_set_id"], {}).verify_sort_list_item(data["sort_list"])
            init_params = {
                "index_set_id": data["index_set_id"],
                "index_set_type": data["index_set_type"],
                "config_id": data["config_id"],
            }
        else:
            init_params = {
                "index_set_ids": data["index_set_ids"],
                "index_set_type": data["index_set_type"],
                "config_id": data["config_id"],
            }
        result = IndexSetFieldsConfigHandler(**init_params).create_or_update(
            name=data["name"], display_fields=data["display_fields"], sort_list=data["sort_list"]
        )
        return Response(result)

    @detail_route(methods=["GET"], url_path="retrieve_config")
    def retrieve_config(self, request, *args, **kwargs):
        """
        @api {get} /search/index_set/$index_set_id/retrieve_config?config_id=1 03_搜索-获取指定索引集配置
        @apiDescription 获取某个索引集的字段配置
        @apiName retrieve_index_set_config
        @apiGroup 11_Search
        @apiParamExample {Json} 请求参数
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": [
                {
                    "id": 1,
                    "name": "1",
                    "index_set_id": 1,
                    "display_fields": [],
                    "sort_list": []
                }
            ],
            "result": true
        }
        """
        config_id = request.GET.get("config_id", 0)
        return Response(IndexSetFieldsConfigHandler(config_id=config_id).retrieve())

    @list_route(methods=["POST"], url_path="list_config")
    def list_config(self, request, *args, **kwargs):
        """
        @api {get} /search/index_set/list_config/ 03_搜索-获取索引集配置列表
        @apiDescription 获取某个索引集的字段配置列表
        @apiName list_index_set_config
        @apiGroup 11_Search
        @apiParamExample {Json} 请求参数
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": [
                {
                    "id": 1,
                    "name": "1",
                    "index_set_id": 1,
                    "display_fields": [],
                    "sort_list": []
                }
            ],
            "result": true
        }
        """
        data = self.params_valid(IndexSetFieldsConfigListSerializer)
        if data["index_set_type"] == IndexSetType.SINGLE.value:
            init_params = {"index_set_id": data["index_set_id"], "index_set_type": data["index_set_type"]}
        else:
            init_params = {"index_set_ids": data["index_set_ids"], "index_set_type": data["index_set_type"]}
        return Response(IndexSetFieldsConfigHandler(**init_params).list(scope=data["scope"]))

    @list_route(methods=["POST"], url_path="delete_config")
    def delete_config(self, request, *args, **kwargs):
        """
        @api {post} /search/index_set/delete_config/ 03_搜索-删除索引集配置
        @apiDescription 删除某个索引集的字段配置
        @apiName delete_index_set_config
        @apiGroup 11_Search
        @apiParamExample {Json} 请求参数
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": null,
            "result": true
        }
        """
        data = self.params_valid(SearchUserIndexSetDeleteConfigSerializer)
        result = IndexSetFieldsConfigHandler(config_id=data["config_id"]).delete()
        return Response(result)

    @list_route(methods=["get"], url_path="operators")
    def operators(self, request, *args, **kwargs):
        """
        @api {get} /search/index_set/operators/ 04_搜索-检索条件operator
        @apiName search_index_set_operators
        @apiGroup 11_Search
        @apiSuccess {Int} index_set_id 索引集ID
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": {
                "keyword": [
                    {
                        "operator": "is",
                        "label": "is",
                        "placeholder": _("请选择或直接输入")
                    },
                    {
                        "operator": "is one of",
                        "label": "is one of "，
                        "placeholder": _("请选择或直接输入，逗号分隔")
                    },
                ],
            }
            "result": true
        }
        """
        return Response(OPERATORS)

    @detail_route(methods=["GET"], url_path="history")
    def history(self, request, *args, **kwargs):
        """
        @api {get} /search/index_set/$index_set_id/history/ 06_搜索-检索历史
        @apiDescription 检索历史记录
        @apiName search_index_set_user_history
        @apiGroup 11_Search
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": [
                {
                    "id": 13,
                    "params": {
                        "keyword": "*",
                        "host_scopes": {
                            "modules": [
                                {
                                    "bk_inst_id": 25,
                                    "bk_obj_id": "module"
                                }
                            ],
                            "ips": "127.0.0.1,127.0.0.2"
                        },
                        "addition": [
                            {
                                "field": "cloudId",
                                "operator": "is",
                                "value": "0"
                            }
                        ]
                    },
                    "query_string": "keyword:* ADN modules:25 AND ips:127.0.0.1,127.0.0.2"
                }],
            "result": true
        }
        """
        index_set_id = kwargs.get("index_set_id")
        return Response(SearchHandlerEsquery.search_history(index_set_id))

    @list_route(methods=["POST"], url_path="option/history")
    def option_history(self, request, *args, **kwargs):
        """
        @api {get} /search/index_set/option/history/ 06_搜索-检索选项历史
        @apiDescription 检索选项历史记录
        @apiName search_index_set_user_option_history
        @apiGroup 11_Search
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": [
                {
                    "id": 13,
                    "params": {
                        "keyword": "*",
                        "host_scopes": {
                            "modules": [
                                {
                                    "bk_inst_id": 25,
                                    "bk_obj_id": "module"
                                }
                            ],
                            "ips": "127.0.0.1,127.0.0.2"
                        },
                        "addition": [
                            {
                                "field": "cloudId",
                                "operator": "is",
                                "value": "0"
                            }
                        ]
                    },
                    "query_string": "keyword:* ADN modules:25 AND ips:127.0.0.1,127.0.0.2"
                }],
            "result": true
        }
        """
        data = self.params_valid(SearchUserIndexSetOptionHistorySerializer)
        return Response(SearchHandlerEsquery.search_option_history(data["space_uid"], data["index_set_type"]))

    @list_route(methods=["POST"], url_path="option/history/delete")
    def option_history_delete(self, request, *args, **kwargs):
        """
        @api {get} /search/index_set/option/history/delete/ 06_搜索-检索选项历史删除
        @apiDescription 检索选项历史记录删除
        @apiName search_index_set_user_option_history
        @apiGroup 11_Search
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": null,
            "result": true
        }
        """
        data = self.params_valid(SearchUserIndexSetOptionHistoryDeleteSerializer)
        return Response(
            SearchHandlerEsquery.search_option_history_delete(
                space_uid=data["space_uid"],
                index_set_type=data["index_set_type"],
                history_id=data.get("history_id"),
                is_delete_all=data["is_delete_all"],
            )
        )

    @list_route(methods=["POST"], url_path="union_search")
    @search_history_record
    def union_search(self, request, *args, **kwargs):
        """
        @api {post} /search/index_set/union_search/ 11_联合检索-日志内容
        @apiName union_search_log
        @apiGroup 11_Search
        @apiParam {String} start_time 开始时间
        @apiParam {String} end_time 结束时间
        @apiParam {String} time_range 时间标识符符["15m", "30m", "1h", "4h", "12h", "1d", "customized"]
        @apiParam {String} keyword 搜索关键字
        @apiParam {Json} ip_chooser IP列表
        @apiParam {Array[Json]} addition 搜索条件
        @apiParam {Int} size 条数
        @apiParam {Array[Json]} union_configs 联合检索索引集配置
        @apiParam {Int} union_configs.index_set_id 索引集ID
        @apiParam {Int} union_configs.begin 索引对应的滚动条数
        @apiParam {Bool} union_configs.is_desensitize 是否脱敏 默认为True（只针对白名单SaaS开放此参数）
        @apiParamExample {Json} 请求参数
        {
            "start_time": "2019-06-11 00:00:00",
            "end_time": "2019-06-12 11:11:11",
            "time_range": "customized"
            "keyword": "error",
            "host_scopes": {
                "modules": [
                    {
                        "bk_obj_id": "module",
                        "bk_inst_id": 4
                    },
                    {
                        "bk_obj_id": "set",
                        "bk_inst_id": 4
                    }
                ],
                "ips": "127.0.0.1, 127.0.0.2"
            },
            "addition": [
                {
                    "key": "ip",
                    "method": "is",
                    "value": "127.0.0.1",
                    "condition": "and",  (默认不传是and，只支持and or)
                    "type": "field" (默认field 目前支持field，其他无效)
                }
            ],
            "size": 15,
            "union_configs": [
                {
                    "index_set_id": 146,
                    "begin": 0
                },
                {
                    "index_set_id": 147,
                    "begin": 0
                }
            ]
        }

        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": {
                "total": 100,
                "took": 0.29,
                "list": [
                    {
                        "srcDataId": "2087",
                        "dtEventTimeStamp": 1534825132000,
                        "moduleName": "公共组件->consul",
                        "log": "is_cluster</em>-COMMON: ok",
                        "sequence": 1,
                        "dtEventTime": "2018-08-21 04:18:52",
                        "timestamp": 1534825132,
                        "serverIp": "127.0.0.1",
                        "errorCode": "0",
                        "gseIndex": 152358,
                        "dstDataId": "2087",
                        "worldId": "-1",
                        "logTime": "2018-08-21 12:18:52",
                        "path": "/tmp/health_check.log",
                        "platId": 0,
                        "localTime": "2018-08-21 04:18:00"
                    }
                ],
                "origin_log_list": [
                    {
                        "srcDataId": "2087",
                        "dtEventTimeStamp": 1534825132000,
                        "moduleName": "公共组件->consul",
                        "log": "is_cluster</em>-COMMON: ok",
                        "sequence": 1,
                        "dtEventTime": "2018-08-21 04:18:52",
                        "timestamp": 1534825132,
                        "serverIp": "127.0.0.1",
                        "errorCode": "0",
                        "gseIndex": 152358,
                        "dstDataId": "2087",
                        "worldId": "-1",
                        "logTime": "2018-08-21 12:18:52",
                        "path": "/tmp/health_check.log",
                        "platId": 0,
                        "localTime": "2018-08-21 04:18:00"
                    }
                ],
                "union_configs": [
                    {
                        "index_set_id": 146,
                        "begin": 7
                    },
                    {
                        "index_set_id": 147,
                        "begin": 3
                    }
                ]

            },
            "result": true
        }
        """
        data = self.params_valid(UnionSearchAttrSerializer)
        auth_info = Permission.get_auth_info(self.request, raise_exception=False)
        is_verify = False if not auth_info or auth_info["bk_app_code"] not in settings.ESQUERY_WHITE_LIST else True
        for info in data.get("union_configs", []):
            if not info.get("is_desensitize") and not is_verify:
                info["is_desensitize"] = True
        if FeatureToggleObject.switch(UNIFY_QUERY_SEARCH, data.get("bk_biz_id")):
            return Response(UnionSearchHandler(data).unifyquery_union_search())
        return Response(UnionSearchHandler(data).union_search())

    @list_route(methods=["POST"], url_path="union_search/fields")
    def union_search_fields(self, request, *args, **kwargs):
        """
        @api {POST} /search/index_set/union_search/fields/?scope=search_context 联合检索-获取索引集配置
        @apiDescription 联合检索-获取字段Mapping字段信息
        @apiName union_search_fields
        @apiGroup 11_Search
        @apiParam {String} [start_time] 开始时间(非必填)
        @apiParam {String} [end_time] 结束时间（非必填)
        @apiParam {Array[Int]} [index_set_ids] 索引集ID
        @apiSuccess {String} display_fields 列表页显示的字段
        @apiSuccess {String} fields.field_name 字段名
        @apiSuccess {String} fields.field_alias 字段中文称 (为空时会直接取description)
        @apiSuccess {String} fields.description 字段说明
        @apiSuccess {String} fields.field_type 字段类型
        @apiSuccess {Bool} fields.is_display 是否显示给用户
        @apiSuccess {Bool} fields.is_editable 是否可以编辑（是否显示）
        @apiSuccess {Bool} fields.es_doc_values 是否聚合字段
        @apiSuccess {Bool} fields.is_analyzed 是否分词字段
        @apiSuccess {String} time_field 时间字段
        @apiSuccess {String} time_field_type 时间字段类型
        @apiSuccess {String} time_field_unit 时间字段单位
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": {
                "display_fields": ["dtEventTimeStamp", "log"],
                "fields": [
                    {
                        "field_name": "log",
                        "field_alias": "日志",
                        "field_type": "text",
                        "is_display": true,
                        "is_editable": true,
                        "description": "日志",
                        "es_doc_values": false
                    },
                    {
                        "field_name": "dtEventTimeStamp",
                        "field_alias": "时间",
                        "field_type": "date",
                        "is_display": true,
                        "is_editable": true,
                        "description": "描述",
                        "es_doc_values": true
                    }
                ],
            },
            "result": true
        }
        """
        data = self.params_valid(UnionSearchFieldsSerializer)
        fields = UnionSearchHandler().union_search_fields(data)

        # 添加用户索引集自定义配置
        index_set_config = UserIndexSetConfigHandler(
            index_set_ids=data["index_set_ids"],
            index_set_type=IndexSetType.UNION.value,
        ).get_index_set_config()
        fields.update({"user_custom_config": index_set_config})
        return Response(fields)

    @list_route(methods=["POST"], url_path="union_search/export")
    def union_search_export(self, request, *args, **kwargs):
        """
        @api {post} /search/index_set/union_search/export/ 14_联合检索-导出日志
        @apiName search_log_export
        @apiGroup 11_Search
        @apiParam bk_biz_id [Int] 业务id
        @apiParam keyword [String] 搜索关键字
        @apiParam time_range [String] 时间范围
        @apiParam start_time [String] 起始时间
        @apiParam end_time [String] 结束时间
        @apiParam host_scopes [Dict] 检索模块ip等信息
        @apiParam begin [Int] 检索开始 offset
        @apiParam size [Int]  检索结果大小
        @apiParam interval [String] 匹配规则
        @apiParam index_set_ids [List] 索引集ID列表
        @apiParamExample {Json} 请求参数
        {
            "bk_biz_id":"215",
            "keyword":"*",
            "time_range":"5m",
            "start_time":"2021-06-08 11:02:21",
            "end_time":"2021-06-08 11:07:21",
            "host_scopes":{
                "modules":[

                ],
                "ips":""
            },
            "addition":[

            ],
            "begin":0,
            "size":188,
            "interval":"auto",
            "isTrusted":true
        }

        @apiSuccessExample text/plain 成功返回:
        {"a": "good", "b": {"c": ["d", "e"]}}
        {"a": "good", "b": {"c": ["d", "e"]}}
        {"a": "good", "b": {"c": ["d", "e"]}}
        """

        data = self.params_valid(UnionSearchSearchExportSerializer)
        request_data = copy.deepcopy(data)
        index_set_ids = sorted(data.get("index_set_ids", []))

        output = BytesIO()
        search_handler = UnionSearchHandler(search_dict=data)
        result = search_handler.union_search(is_export=True)
        result_list = result.get("origin_log_list")
        for item in result_list:
            json_data = json.dumps(item, ensure_ascii=False).encode("utf8")
            output.write(json_data + b"\n")
        file_name = "bk_log_union_search_{}.log".format("_".join([str(i) for i in index_set_ids]))
        response = create_download_response(output, file_name)

        # 保存下载历史
        AsyncTask.objects.create(
            request_param=request_data,
            result=True,
            completed_at=timezone.now(),
            export_status=ExportStatus.SUCCESS,
            start_time=data["start_time"],
            end_time=data["end_time"],
            export_type=ExportType.SYNC,
            index_set_ids=index_set_ids,
            index_set_type=IndexSetType.UNION.value,
            bk_biz_id=data.get("bk_biz_id"),
        )

        return response

    @list_route(methods=["GET"], url_path="union_search/export_history")
    def union_search_get_export_history(self, request, *args, **kwargs):
        """
        @api {get} /search/index_set/union_search/export_history/?page=1&pagesize=10 联合检索-导出历史
        @apiDescription 联合检索-导出历史
        @apiName export_history
        @apiGroup 11_Search
        @apiParam {Int} index_set_id 索引集id
        @apiParam {Int} page 当前页
        @apiParam {Int} pagesize 页面大小
        @apiParam {Bool} show_all 是否展示所有历史
        @apiParam {String} index_set_ids 索引集ID  "146,147"
        @apiSuccess {Int} total 返回大小
        @apiSuccess {list} list 返回结果列表
        @apiSuccess {Int} list.id 导出历史任务id
        @apiSuccess {Int} list.log_index_set_id 导出索引集id
        @apiSuccess {Str} list.search_dict 导出请求参数
        @apiSuccess {Str} list.start_time 导出请求所选择开始时间
        @apiSuccess {Str} list.end_time 导出请求所选择结束时间
        @apiSuccess {Str} list.export_type 导出请求类型
        @apiSuccess {Str} list.export_status 导出状态
        @apiSuccess {Str} list.error_msg 导出请求异常原因
        @apiSuccess {Str} list.download_url 异步导出下载地址
        @apiSuccess {Str} list.export_pkg_name 异步导出打包名
        @apiSuccess {int} list.export_pkg_size 异步导出包大小 单位M
        @apiSuccess {Str} list.export_created_at 异步导出创建时间
        @apiSuccess {Str} list.export_created_by 异步导出创建者
        @apiSuccess {Str} list.export_completed_at 异步导出成功时间
        @apiSuccess {Bool} list.download_able 是否可下载（不可下载禁用下载按钮且hover提示"下载链接过期"）
        @apiSuccess {Bool} list.retry_able 是否可重试（不可重试禁用对应按钮且hover提示"数据源过期"）
        @apiSuccessExample {json} 成功返回：
        {
            "result": true,
            "data": {
                "total": 1,
                "list": [
                    {
                        "id": 25,
                        "search_dict": {
                            "size": 100,
                            "begin": 0,
                            "keyword": "*",
                            "addition": [],
                            "end_time": "2023-08-02 17:26:33",
                            "interval": "auto",
                            "ip_chooser": {},
                            "start_time": "2023-08-02 17:11:33",
                            "time_range": "customized",
                            "host_scopes": {
                                "ips": "",
                                "modules": [],
                                "target_nodes": [],
                                "target_node_type": ""
                            },
                            "export_fields": [],
                            "index_set_ids": [
                                146,
                                147
                            ]
                        },
                        "start_time": "2023-08-02 17:11:33",
                        "end_time": "2023-08-02 17:26:33",
                        "export_type": "sync",
                        "export_status": "success",
                        "error_msg": null,
                        "download_url": null,
                        "export_pkg_name": null,
                        "export_pkg_size": null,
                        "export_created_at": "2023-08-02T09:32:33.547018Z",
                        "export_created_by": "admin",
                        "export_completed_at": "2023-08-02T09:32:32.303892Z",
                        "download_able": true,
                        "retry_able": true,
                        "index_set_type": "union",
                        "index_set_ids": [
                            146,
                            147
                        ]
                    }
                ]
            },
            "code": 0,
            "message": ""
        }
        """
        data = self.params_valid(UnionSearchGetExportHistorySerializer)
        index_set_ids = sorted([int(index_set_id) for index_set_id in data["index_set_ids"].split(",")])
        return AsyncExportHandlers(index_set_ids=index_set_ids, bk_biz_id=data["bk_biz_id"]).get_export_history(
            request=request, view=self, show_all=data["show_all"], is_union_search=True
        )

    @list_route(methods=["GET"], url_path="union_search/history")
    def union_search_history(self, request, *args, **kwargs):
        """
        @api {get} /search/index_set/union_search/history/ 06_搜索-检索历史
        @apiDescription 检索历史记录
        @apiName union_search_index_set_user_history
        @apiGroup 11_Search
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": [
                {
                    "id": 13,
                    "params": {
                        "keyword": "*",
                        "host_scopes": {
                            "modules": [
                                {
                                    "bk_inst_id": 25,
                                    "bk_obj_id": "module"
                                }
                            ],
                            "ips": "127.0.0.1,127.0.0.2"
                        },
                        "addition": [
                            {
                                "field": "cloudId",
                                "operator": "is",
                                "value": "0"
                            }
                        ]
                    },
                    "query_string": "keyword:* ADN modules:25 AND ips:127.0.0.1,127.0.0.2"
                }],
            "result": true
        }
        """
        data = self.params_valid(UnionSearchHistorySerializer)
        index_set_ids = sorted([int(index_set_id) for index_set_id in data["index_set_ids"].split(",")])
        return Response(SearchHandlerEsquery.search_history(index_set_ids=index_set_ids, is_union_search=True))

    @list_route(methods=["POST"], url_path="user_custom_config")
    def update_or_create_config(self, request):
        """
        @api {post} /search/index_set/user_custom_config/ 更新或创建用户索引集自定义配置
        @apiDescription 更新或创建用户索引集自定义配置
        @apiName user_custom_config
        @apiGroup 11_Search
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": {
                "id": 7,
                "username": "admin",
                "index_set_id": 495,
                "index_set_ids": [],
                "index_set_hash": "35051070e572e47d2c26c241ab88307f",
                "index_set_config": {
                    "fields_width": {
                        "dtEventTimeStamp": 12,
                        "serverIp": 15,
                        "log": 80
                    }
                }
            },
            "code": 0,
            "message": ""
        }
        """
        data = self.params_valid(UserIndexSetCustomConfigSerializer)
        return Response(
            UserIndexSetConfigHandler(
                index_set_id=data.get("index_set_id"),
                index_set_ids=data.get("index_set_ids"),
                index_set_type=data["index_set_type"],
            ).update_or_create(index_set_config=data["index_set_config"])
        )

    @list_route(methods=["POST"], url_path="custom_config")
    def update_or_create_index_set_config(self, request):
        """
        @api {post} /search/index_set/custom_config/ 更新或创建索引集自定义配置
        @apiDescription 更新或创建索引集自定义配置
        @apiName custom_config
        @apiGroup 11_Search
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": {
                "id": 7,
                "index_set_id": 495,
                "index_set_ids": [],
                "index_set_hash": "35051070e572e47d2c26c241ab88307f",
                "index_set_config": {
                    "fields_width": {
                        "dtEventTimeStamp": 12,
                        "serverIp": 15,
                        "log": 80
                    }
                }
            },
            "code": 0,
            "message": ""
        }
        """
        data = self.params_valid(IndexSetCustomConfigSerializer)
        return Response(
            IndexSetCustomConfigHandler(
                index_set_id=data.get("index_set_id"),
                index_set_ids=data.get("index_set_ids"),
                index_set_type=data["index_set_type"],
            ).update_or_create(index_set_config=data["index_set_config"])
        )

    @detail_route(methods=["POST"], url_path="chart")
    def chart(self, request, index_set_id=None):
        """
        @api {get} /search/index_set/$index_set_id/chart/
        @apiDescription 获取图表信息
        @apiName chart
        @apiGroup 11_Search
        @apiSuccessExample {json} 成功返回:
        {
          "result": true,
          "data": {
            "total_records": 2,
            "time_taken": 0.092,
            "list": [
              {
                "aa": "aa",
                "number": 16.3
                "time": 1731260184
              },
              {
                "aa": "bb",
                "number": 20.56
                "time": 1731260184
              }
            ],
            "select_fields_order": [
              "aa",
              "number",
              "time"
            ],
            "result_schema": [
            {
                "field_type": "string",
                "field_name": "aa",
                "field_alias": "aa",
                "field_index": 0
            },
            {
                "field_type": "double",
                "field_name": "number",
                "field_alias": "number",
                "field_index": 1
            },
            {
                "field_type": "long",
                "field_name": "time",
                "field_alias": "time",
                "field_index": 2
            }
            ]
          },
          "code": 0,
          "message": ""
        }
        """
        params = self.params_valid(ChartSerializer)
        instance = ChartHandler.get_instance(index_set_id=index_set_id, mode=params["query_mode"])
        result = instance.get_chart_data(params)
        return Response(result)

    @detail_route(methods=["POST"], url_path="generate_sql")
    def generate_sql(self, request, index_set_id=None):
        """
        @api {get} /search/index_set/$index_set_id/generate_sql/
        @apiDescription 生成sql条件
        @apiName generate_sql
        @apiGroup 11_Search
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": {
                "sql": "dtEventTimeStamp>=1732220441000 and dtEventTimeStamp<=1732220443000"
            },
            "code": 0,
            "message": ""
        }
        """
        params = self.params_valid(UISearchSerializer)
        data = ChartHandler.generate_sql(
            addition=params["addition"],
            start_time=params["start_time"],
            end_time=params["end_time"],
            sql_param=params["sql"],
            keyword=params["keyword"],
            alias_mappings=params["alias_mappings"],
        )
        return Response(data)

    @list_route(methods=["POST"], url_path="generate_querystring")
    def generate_querystring(self, request):
        """
        @api {get} /search/index_set/generate_querystring/
        @apiDescription 生成querystring语法
        @apiName generate_querystring
        @apiGroup 11_Search
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": {
                "querystring": "color: * AND name: x"
            },
            "code": 0,
            "message": ""
        }
        """
        params = self.params_valid(QueryStringSerializer)
        querystring = QueryStringBuilder.to_querystring(params)
        return Response({"querystring": querystring})

    @detail_route(methods=["POST"], url_path="grep_query")
    def grep_query(self, request, index_set_id):
        """
        @api {post} /search/index_set/$index_set_id/grep_query/
        @apiDescription grep语法查询
        @apiName grep_query
        @apiGroup 11_Search
        @apiParam start_time [String] 起始时间
        @apiParam end_time [String] 结束时间
        @apiParam keyword [String] 搜索关键字
        @apiParam addition [List[dict]] 搜索条件
        @apiParam grep_query [String] grep查询条件
        @apiParam grep_field [String] 高亮字段
        @apiParam begin [Int] 检索开始 offset
        @apiParam size [Int]  检索结果大小
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": {
                "total": 2,
                "took" 0.88,
                "list": [
                    {
                        "thedate": 20250416,
                        "dteventtimestamp": 1744788480000,
                        "log": "[2025.04.16-15.27.59:459][290]RPC",
                    },
                    {
                        "thedate": 20250416,
                        "dteventtimestamp": 1744788480000,
                        "log": "[2025.04.16-15.27.59:124][280]RPC",
                    }
                ],
            },
            "code": 0,
            "message": ""
        }
        """
        params = self.params_valid(LogGrepQuerySerializer)
        instance = ChartHandler.get_instance(index_set_id=index_set_id, mode=QueryMode.SQL.value)
        data = instance.fetch_grep_query_data(params)
        return Response(data)
