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
from rest_framework.response import Response

from apps.api import UnifyQueryApi
from apps.generic import APIViewSet
from apps.log_search.permission import Permission
from apps.log_unifyquery.handler.base import UnifyQueryHandler
from apps.log_unifyquery.utils import verify_unify_query_token
from apps.utils.drf import list_route


class UnifyQueryViewSet(APIViewSet):
    def check_permissions(self, request):
        """检查权限：白名单判断和token验证"""
        super().check_permissions(request)

        # 白名单校验
        auth_info = Permission.get_auth_info(request, raise_exception=False)
        if auth_info and auth_info["bk_app_code"] in settings.ESQUERY_WHITE_LIST:
            return

        # 非白名单应用需要进行token验证
        verify_unify_query_token(request, auth_info)

    @list_route(methods=["post"], url_path="ts")
    def query_ts(self, request):
        """
        @api {post} /query/ts/ 时序型检索
        @apiName unify_query_query_ts
        @apiGroup unify_query
        @apiParam {Integer} bk_biz_id 业务ID
        @apiParam {Object} ... 其他UQ参数
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": {
                "series": [
                    {
                        "name": "_result0",
                        "metric_name": "",
                        "columns": [
                            "_time",
                            "_value"
                        ],
                        "types": [
                            "float",
                            "float"
                        ],
                        "group_keys": [
                        "gseIndex"
                        ],
                        "group_values": [
                            "36069"
                        ],
                        "values": [
                            [
                                1754893191000,
                                36069
                            ]
                        ]
                    }
                ],
                "trace_id": "xxxxxxx"
            },
            "code": 0,
            "message": ""
        }
        """
        return Response(UnifyQueryApi.query_ts(request.data))

    @list_route(methods=["post"], url_path="ts/reference")
    def query_ts_reference(self, request):
        """
        @api {post} /query/ts/reference/ 非时序型检索
        @apiName unify_query_query_ts_reference
        @apiGroup unify_query
        @apiParam {Integer} bk_biz_id 业务ID
        @apiParam {Object} ... 其他UQ参数
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": {
                "series": [
                    {
                        "name": "_result0",
                        "metric_name": "",
                        "columns": [
                            "_time",
                            "_value"
                        ],
                        "types": [
                            "float",
                            "float"
                        ],
                        "group_keys": [
                            "__ipv6__"
                        ],
                        "group_values": [
                            ""
                        ],
                        "values": [
                            [
                                1754029191000,
                                39648
                            ]
                        ]
                    }
                ],
                "trace_id": "xxxx"
            },
            "code": 0,
            "message": ""
        }
        """
        return Response(UnifyQueryHandler.query_ts_reference(request.data))

    @list_route(methods=["post"], url_path="ts/raw")
    def query_ts_raw(self, request):
        """
        @api {post} /query/ts/raw/ 时序型检索日志
        @apiName unify_query_query_ts_raw
        @apiGroup unify_query
        @apiParam {Integer} bk_biz_id 业务ID
        @apiParam {Object} ... 其他UQ参数
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": {
                "total": 10000,
                "list": [
                    {
                        "__data_label": "bklog_index_set_xxx",
                        "__doc_id": "xxx",
                        "__index": "v2_2_bklog_codecc_20250810_0",
                        "__result_table": "bklog_index_set_xxx_2_bklog_codecc.__default__",
                        "_time": "1754784002000",
                        "bk_host_id": xxx,
                        "cloudId": 0,
                        "dtEventTimeStamp": "1754784002000",
                        "gseIndex": xxxx,
                        "iterationIndex": 0,
                        "log": "Aug 10 07:59:58 VM-6-115-centos kubelet: I0810 07:59:58.226108   11315 passthrough.go:48] ccResolverWrapper: sending update to cc: {[{/var/lib/kubelet/plugins/com.tencent.cloud.csi.cbs/csi.sock  <nil> 0 <nil>}] <nil> <nil>}",
                        "path": "/var/log/messages",
                        "serverIp": "x.x.x.x",
                        "time": "1754784002000"
                    }
                ],
                "trace_id": "xxx",
                "result_table_options": {
                    "bklog_index_set_xxx_2_bklog_codecc.__default__|http://x.x.x.x:9200": {
                        "from": 0,
                        "search_after": [
                            1754784002000
                        ]
                    }
                }
            },
            "code": 0,
            "message": ""
        }
        """
        return Response(UnifyQueryApi.query_ts_raw(request.data))
