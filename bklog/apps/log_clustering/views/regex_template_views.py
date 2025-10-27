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

from apps.generic import ModelViewSet
from apps.iam import ActionEnum
from apps.iam.handlers.drf import BusinessActionPermission
from apps.log_clustering.exceptions import RegexTemplateNotExistException
from apps.log_clustering.handlers.regex_template import RegexTemplateHandler
from apps.log_clustering.models import RegexTemplate
from apps.log_clustering.serializers import (
    CreateRegexTemplateSerializer,
    UpdateRegexTemplateSerializer,
)


class RegexTemplateViewSet(ModelViewSet):
    lookup_field = "id"
    model = RegexTemplate

    def get_permissions(self):
        if self.action == "list":
            space_uid = self.request.query_params.get("space_uid")
            return [BusinessActionPermission([ActionEnum.VIEW_BUSINESS], space_uid)]
        elif self.action in ["create", "partial_update", "destroy"]:
            if self.action == "create":
                space_uid = self.request.data.get("space_uid")
            else:
                template_id = self.kwargs[self.lookup_field]
                template_obj = RegexTemplate.objects.filter(id=template_id).first()
                if not template_obj:
                    raise RegexTemplateNotExistException(
                        RegexTemplateNotExistException.MESSAGE.format(regex_template_id=template_id)
                    )
                space_uid = template_obj.space_uid
            return [BusinessActionPermission([ActionEnum.VIEW_BUSINESS], space_uid)]

        return []

    def list(self, request, *args, **kwargs):
        """
        @api {get} /regex_template/?space_uid=$space_uid 1_聚类正则模板-模板列表
        @apiDescription 指定空间下的聚类正则模板列表
        @apiName regex_template list
        @apiGroup log_clustering
        @apiSuccess {Int} id 模板ID
        @apiSuccess {String} template_name 模板名称
        @apiSuccess {String} predefined_varibles 正则表达式
        @apiSuccess {Array} related_index_set_list 模板关联的索引集
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
        return Response(RegexTemplateHandler().list_templates(space_uid=space_uid))

    def create(self, request, *args, **kwargs):
        """
        @api {post} /regex_template/ 2_聚类正则模板-创建
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
        data = self.params_valid(CreateRegexTemplateSerializer)
        return Response(
            RegexTemplateHandler().create_template(
                space_uid=data["space_uid"],
                template_name=data["template_name"],
                predefined_varibles=data.get("predefined_varibles"),
            )
        )

    def partial_update(self, request, *args, id=None, **kwargs):
        """
        @api {patch} /regex_template/$regex_template_id/ 2_聚类正则模板-修改
        @apiName update_regex_template
        @apiGroup log_clustering
        @apiParamExample {Json} 请求参数
        {
            "template_name": "aaa"
        }
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": {
                "id': 6,
                "space_uid": "bkcc__2",
                "template_name": "aaa",
                "pipeline_ids": ["xx"]
            },
            "result": true
        }
        """
        data = self.params_valid(UpdateRegexTemplateSerializer)
        return Response(
            RegexTemplateHandler().update_template(
                template_id=id,
                template_name=data.get("template_name"),
                predefined_varibles=data.get("predefined_varibles"),
            )
        )

    def destroy(self, request, *args, id=None, **kwargs):
        """
        @api {delete} /regex_template/$regex_template_id/ 2_聚类正则模板-删除
        @apiName delete_regex_template
        @apiGroup log_clustering
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": null,
            "result": true
        }
        """
        return Response(RegexTemplateHandler().delete_template(template_id=id))
