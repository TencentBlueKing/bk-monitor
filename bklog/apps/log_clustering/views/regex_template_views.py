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
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF  OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

from rest_framework.response import Response

from apps.generic import APIViewSet
from apps.log_clustering.handlers.regex_template import RegexTemplateHandler
from apps.log_clustering.serializers import RegexTemplateSerializer
from apps.utils.drf import detail_route, list_route


class RegexTemplateViewSet(APIViewSet):
    lookup_field = "regex_template_id"

    def get_permissions(self):
        return []

    # TODO:待完善
    @list_route(methods=["GET"], url_path="list")
    def get_template(self, request, *args, **kwargs):
        """
        @api {get} /regex_template/list?space_uid=$space_uid 1_聚类正则模板-模板列表
        @apiDescription 指定空间下的聚类正则模板列表
        @apiName get_regex_template
        @apiGroup log_clustering
        @apiSuccess {Int} id 模板ID
        @apiSuccess {String} template_name 模板名称
        @apiSuccess {String} predefined_varibles 正则表达式
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": [
                {
                    "id": 1,
                    "space_uid": "bkcc__2",
                    "template_name": "系统默认",
                    "predefined_varibles": "xxxxx",
                    "related_index_set_list": [
                        {
                            "index_set_id": 1,
                            "index_set_name": "xxxxx"
                        }
                    ]
                },
                {
                    "id": 3,
                    "space_uid": "bkcc__2",
                    "template_name": "个人1",
                    "predefined_varibles": "xxxxx",
                    "related_index_set_list": []
                },
                {
                    "id": 4,
                    "space_uid": "bkcc__2",
                    "template_name": "个人2",
                    "predefined_varibles": "xxxxx",
                    "related_index_set_list": []
                }
            ],
            "result": true
        }
        """
        space_uid = request.query_params.get("space_uid")
        return Response(RegexTemplateHandler(space_uid).get_template())

    @list_route(methods=["POST"], url_path="create")
    def create_template(self, request, *args, **kwargs):
        """
        @api {post} /regex_template/create/ 2_聚类正则模板-创建
        @apiName create_regex_template
        @apiGroup log_clustering
        @apiParamExample {Json} 请求参数
        {
            "space_uid": "bkcc__2",
            "template_name": "aaa"
        }
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": {
                "id": 6,
                "space_uid": "bkcc__2",
                "template_name": "aaa",
                "predefined_varibles": "xxxxx",
                "related_index_set_list": []
            },
            "result": true
        }
        """
        data = self.params_valid(RegexTemplateSerializer)
        return Response(RegexTemplateHandler(data["space_uid"]).create_template(template_name=data["template_name"]))

    @detail_route(methods=["POST"], url_path="update")
    def update_template(self, request, regex_template_id, *args, **kwargs):
        """
        @api {post} /regex_template/$regex_template_id/update/ 2_聚类正则模板-修改
        @apiName update_regex_template
        @apiGroup log_clustering
        @apiParamExample {Json} 请求参数
        {
            "space_uid": "bkcc__2",
            "template_name": "aaa"
        }
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": {
                "id': 6,
                "space_uid": "bkcc__2",
                "template_name": "aaa"
            },
            "result": true
        }
        """
        space_uid = request.data.get("space_uid")
        template_name = request.data.get("template_name")
        return Response(
            RegexTemplateHandler(space_uid).update_template(template_id=regex_template_id, template_name=template_name)
        )

    @list_route(methods=["POST"], url_path="delete")
    def delete_template(self, request, regex_template_id, *args, **kwargs):
        """
        @api {post} /regex_template/$regex_template_id/delete/ 2_聚类正则模板-创建
        @apiName delete_regex_template
        @apiGroup log_clustering
        @apiParamExample {Json} 请求参数
        {
            "space_uid": "bkcc__2"
        }
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": null,
            "result": true
        }
        """
        space_uid = request.data.get("space_uid")
        return Response(RegexTemplateHandler(space_uid).delete_template(template_id=regex_template_id))
