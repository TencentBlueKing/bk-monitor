# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from blueapps.account.decorators import login_exempt
from django.utils.decorators import method_decorator

from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class ShareViewSet(ResourceViewSet):

    resource_routes = [
        # 创建临时分享token
        ResourceRoute("POST", resource.share.create_share_token, endpoint="create_share_token"),
        # 更新临时分享token参数
        ResourceRoute("POST", resource.share.update_share_token, endpoint="update_share_token"),
        # 根据鉴权类型回收指定token
        ResourceRoute("POST", resource.share.delete_share_token, endpoint="delete_share_token"),
        # 获取临时分享token列表
        ResourceRoute("POST", resource.share.get_share_token_list, endpoint="get_share_token_list"),
    ]


@method_decorator(login_exempt, name='dispatch')
class GetTokenViewSet(ResourceViewSet):
    permission_classes = []

    resource_routes = [
        # 获取临时分享参数
        ResourceRoute("GET", resource.share.get_share_params, endpoint="get_share_params"),
    ]
