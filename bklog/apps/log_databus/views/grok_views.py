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

from rest_framework.response import Response

from apps.generic import ModelViewSet
from apps.iam.handlers.drf import ViewBusinessPermission
from apps.log_databus.handlers.grok.handler import GrokHandler
from apps.log_databus.models import GrokInfo
from apps.log_databus.serializers import (
    GrokCreateSerializer,
    GrokDebugSerializer,
    GrokListSerializer,
    GrokUpdateSerializer,
    GrokUpdatedByListSerializer,
    SearchGrokSerializer,
)
from apps.utils.drf import list_route


class GrokViewSet(ModelViewSet):
    """
    Grok模式管理
    """

    model = GrokInfo
    queryset = GrokInfo.objects.all()
    lookup_field = "id"
    lookup_url_kwarg = "grok_info_id"
    filter_fields_exclude = ["sample_result"]

    def get_permissions(self):
        return [ViewBusinessPermission()]

    def list(self, request, *args, **kwargs):
        """
        @api {get} /log_databus/grok/ Grok模式-列表
        @apiName list_grok
        @apiGroup Grok
        @apiDescription 获取 Grok 模式列表
        @apiParam {Int} bk_biz_id 业务ID
        @apiParam {String} [keyword] 搜索关键字，可匹配规则名称、表达式、描述、更新人
        @apiParam {Boolean} [is_builtin] 是否仅筛选内置模式
        @apiParam {String} [updated_by] 更新人
        @apiParam {String} [ordering] 排序字段，默认按 is_builtin、-updated_at 排序
        @apiParam {Int} [page] 页码
        @apiParam {Int} [pagesize] 每页数量
        @apiSuccess {Int} total 总数
        @apiSuccess {Object[]} list 列表数据
        @apiSuccess {Int} list.id Grok模式ID
        @apiSuccess {Int} list.bk_biz_id 业务ID
        @apiSuccess {String} list.name 规则名称
        @apiSuccess {String} list.pattern 表达式
        @apiSuccess {Boolean} list.is_builtin 是否内置
        @apiSuccess {String} list.sample 样例
        @apiSuccess {String} list.description 描述
        @apiSuccess {String} list.created_at 创建时间
        @apiSuccess {String} list.created_by 创建人
        @apiSuccess {String} list.updated_at 更新时间
        @apiSuccess {String} list.updated_by 更新人
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": {
                "total": 1,
                "list": [
                    {
                        "id": 1,
                        "bk_biz_id": 2,
                        "name": "CUSTOM_LOG",
                        "pattern": "%{WORD:level}",
                        "is_builtin": false,
                        "sample": "INFO",
                        "description": "自定义日志级别",
                        "created_at": "2026-04-20T15:00:00+08:00",
                        "created_by": "admin",
                        "updated_at": "2026-04-20T15:00:00+08:00",
                        "updated_by": "admin"
                    }
                ]
            },
            "code": 0,
            "message": ""
        }
        """
        params = self.params_valid(GrokListSerializer)
        return Response(GrokHandler.list_grok_info(params))

    def create(self, request, *args, **kwargs):
        """
        @api {post} /log_databus/grok/ Grok模式-创建
        @apiName create_grok
        @apiGroup Grok
        @apiDescription 创建自定义 Grok 模式
        @apiParam {Int} bk_biz_id 业务ID
        @apiParam {String} name 规则名称
        @apiParam {String} pattern 表达式
        @apiParam {String} [sample] 样例
        @apiParam {String} [description] 描述
        @apiParamExample {json} 请求样例:
        {
            "bk_biz_id": 2,
            "name": "CUSTOM_LOG",
            "pattern": "%{WORD:level}",
            "sample": "INFO",
            "description": "自定义日志级别"
        }
        @apiSuccess {Int} id Grok模式ID
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": {
                "id": 1
            },
            "code": 0,
            "message": ""
        }
        """
        params = self.params_valid(GrokCreateSerializer)
        return Response(GrokHandler(params.pop("bk_biz_id")).create_grok_info(params))

    def update(self, request, *args, **kwargs):
        """
        @api {put} /log_databus/grok/$grok_info_id/ Grok模式-更新
        @apiName update_grok
        @apiGroup Grok
        @apiDescription 更新自定义 Grok 模式
        @apiParam {Int} grok_info_id Grok模式ID
        @apiParam {Int} bk_biz_id 业务ID
        @apiParam {String} pattern 表达式
        @apiParam {String} [sample] 样例
        @apiParam {String} [description] 描述
        @apiParamExample {json} 请求样例:
        {
            "bk_biz_id": 2,
            "pattern": "%{WORD:level}",
            "sample": "INFO",
            "description": "更新后的描述"
        }
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": null,
            "code": 0,
            "message": ""
        }
        """
        instance = self.get_object()
        params = self.params_valid(GrokUpdateSerializer)
        params["id"] = instance.id
        return Response(GrokHandler(params.pop("bk_biz_id")).update_grok_info(params))

    def destroy(self, request, *args, **kwargs):
        """
        @api {delete} /log_databus/grok/$grok_info_id/ Grok模式-删除
        @apiName delete_grok
        @apiGroup Grok
        @apiDescription 删除自定义 Grok 模式
        @apiParam {Int} grok_info_id Grok模式ID
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": null,
            "code": 0,
            "message": ""
        }
        """
        instance = self.get_object()
        return Response(GrokHandler.delete_grok_info(instance.id))

    @list_route(methods=["GET"], url_path="updated_by_list")
    def get_updated_by_list(self, request, *args, **kwargs):
        """
        @api {get} /log_databus/grok/updated_by_list/ Grok模式-更新人列表
        @apiName list_grok_updated_by
        @apiGroup Grok
        @apiDescription 获取 Grok 模式更新人列表
        @apiParam {Int} bk_biz_id 业务ID
        @apiSuccess {String[]} data 更新人列表
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": [
                "admin",
                "user1"
            ],
            "code": 0,
            "message": ""
        }
        """
        params = self.params_valid(GrokUpdatedByListSerializer)
        return Response(GrokHandler.get_updated_by_list(params["bk_biz_id"]))

    @list_route(methods=["GET"], url_path="search")
    def search_grok(self, request, *args, **kwargs):
        """
        @api {get} /log_databus/grok/search/ Grok模式-名称联想
        @apiName search_grok
        @apiGroup Grok
        @apiDescription 用户输入 Grok 名称时返回联想候选，仅匹配名称，按匹配类型、匹配位置和候选长度加权打分排序。
        @apiParam {Int} bk_biz_id 业务ID
        @apiParam {String} keyword 搜索关键字（允许为空，为空时返回全部）
        @apiParam {Int} [page=1] 页码
        @apiParam {Int} [pagesize=10] 每页数量，范围 1~100
        @apiSuccess {Int} total 匹配总数
        @apiSuccess {Object[]} list 联想列表
        @apiSuccess {Int} list.id Grok模式ID
        @apiSuccess {String} list.name 规则名称
        @apiSuccess {String} list.pattern Grok表达式
        @apiSuccess {String} list.description 描述
        @apiSuccess {String} list.sample 样例
        @apiSuccess {Object} list.sample_result 样例匹配结果
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": {
                "total": 1,
                "list": [
                    {
                        "id": 1,
                        "name": "CUSTOM_LOG",
                        "pattern": "%{WORD:level}",
                        "description": "自定义日志级别",
                        "sample": "INFO",
                        "sample_result": {"level": "INFO"}
                    }
                ]
            },
            "code": 0,
            "message": ""
        }
        """
        params = self.params_valid(SearchGrokSerializer)
        return Response(GrokHandler.search_grok(params))

    @list_route(methods=["POST"], url_path="debug")
    def debug(self, request, *args, **kwargs):
        """
        @api {post} /log_databus/grok/debug/ Grok模式-调试
        @apiName debug_grok
        @apiGroup Grok
        @apiDescription 调试 Grok 表达式并返回匹配结果
        @apiParam {Int} bk_biz_id 业务ID
        @apiParam {String} pattern Grok表达式
        @apiParam {String} sample 日志样例
        @apiParamExample {json} 请求样例:
        {
            "bk_biz_id": 2,
            "pattern": "%{WORD:level}",
            "sample": "INFO"
        }
        @apiSuccess {Object} data 匹配结果，key 为提取字段名，value 为字段值
        @apiSuccessExample {json} 成功返回:
        {
            "result": true,
            "data": {
                "_matched": "INFO",
                "level": "INFO"
            },
            "code": 0,
            "message": ""
        }
        """
        params = self.params_valid(GrokDebugSerializer)
        return Response(GrokHandler(params.pop("bk_biz_id")).debug(params))
