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


from django.test import TestCase
from mock import patch

from monitor_web.grafana.auth import GrafanaAuthSync


class TestAuthSync(TestCase):
    """
    测试Grafana权限同步
    """

    @patch("core.drf_resource.api.grafana.get_user_by_login_or_email")
    @patch("core.drf_resource.api.grafana.create_user")
    def test_get_or_create_user(self, create_user, get_user):
        # 测试获取用户
        get_user.return_value = {
            "result": True,
            "data": {"id": 1},
            "code": 200,
        }
        assert GrafanaAuthSync.get_or_create_user_id("user1") == 1
        assert get_user.call_count == 1
        assert create_user.call_count == 0

        # 测试用户缓存
        assert GrafanaAuthSync.get_or_create_user_id("user1") == 1
        assert get_user.call_count == 1
        assert create_user.call_count == 0

        # 测试创建用户
        get_user.return_value = {
            "result": False,
            "data": None,
            "code": 404,
        }
        create_user.return_value = {"result": True, "data": {"id": 2}}
        assert GrafanaAuthSync.get_or_create_user_id("user2") == 2
        assert get_user.call_count == 2
        assert create_user.call_count == 1
