# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import json

from bkmonitor.utils.request import get_request
from core.drf_resource import Resource
from monitor.models import GlobalConfig


class ApplyForBetaResource(Resource):
    """
    获取事件插件token
    """

    def perform_request(self, validated_data):
        request = get_request(peaceful=True)
        username = request.user.username
        config, is_new = GlobalConfig.objects.get_or_create(key="AI_USER_LIST")
        if is_new:
            config.value = json.dumps([username])
        else:
            ul = json.loads(config.value)
            if username in ul:
                return {"result": "already joined!"}
            ul.append(username)
            config.value = json.dumps(ul)
        config.save()
        return {"result": "joined!"}
