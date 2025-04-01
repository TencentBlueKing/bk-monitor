# -*- coding: utf-8 -*-
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
from apps.log_search.handlers.user_custom_config import UserCustomConfigHandler
from apps.log_search.models import UserCustomConfig
from apps.log_search.serializers import UserCustomConfigSerializer


class UserCustomConfigViewSet(ModelViewSet):
    lookup_field = "id"
    model = UserCustomConfig

    def create(self, request, *args, **kwargs):
        """
        @api {post} /user_custom/ 创建用户自定义配置
        @apiName create_config
        @apiGroup user_custom_config
        @apiParamExample {Json} 请求参数
        {
            "custom_config": {
                "is_keep_filter_conditions": false
            }
        }
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": {
                "id": 1,
                "custom_config": {
                    "is_keep_filter_conditions": false
                }
            },
            "result": true
        }
        """
        data = self.params_valid(UserCustomConfigSerializer)
        return Response(UserCustomConfigHandler().create_config(data["custom_config"]))

    def partial_update(self, request, *args, id=None, **kwargs):
        """
        @api {patch} /user_custom/$user_custom_config_id/ 修改用户自定义配置
        @apiName modify_config
        @apiGroup user_custom_config
        @apiParamExample {Json} 请求参数
        {
            "custom_config": {
                "is_keep_filter_conditions": false
            }
        }
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": {
                "id": 1,
                "custom_config": {
                    "is_keep_filter_conditions": false
                }
            },
            "result": true
        }
        """
        data = self.params_valid(UserCustomConfigSerializer)
        return Response(UserCustomConfigHandler(user_custom_config_id=id).update_config(data["custom_config"]))

    def destroy(self, request, *args, id=None, **kwargs):
        """
        @api {delete} /user_custom/$user_custom_config_id/ 删除用户自定义配置
        @apiName delete_config
        @apiGroup user_custom_config
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": null,
            "result": true
        }
        """
        return Response(UserCustomConfigHandler(user_custom_config_id=id).delete_config())

    def retrieve(self, request, *args, id=None, **kwargs):
        """
        @api {get} /user_custom/$user_custom_config_id/ 获取用户自定义配置
        @apiName get_config
        @apiGroup user_custom_config
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": {
                "id": 1,
                "custom_config": {
                    "is_keep_filter_conditions": false
                }
            },
            "result": true
        }
        """
        return Response(UserCustomConfigHandler(user_custom_config_id=id).get_config())
