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
import pytest
from monitor_web.models.scene_view import SceneViewModel

from core.drf_resource import resource

pytestmark = pytest.mark.django_db


class TestUpdateSceneViewResource:
    def test_perform_request_pod(self, add_bcs_pods, monkeypatch_strategies_get_metric_list_v2):
        order_id = "custom_123456789"
        params = {
            "scene_id": "kubernetes",
            "type": "detail",
            "config": {
                "order": [
                    {"id": order_id, "title": "GPU", "panels": []},
                ]
            },
            "id": "pod",
            "name": "Pod",
            "bk_biz_id": 2,
        }
        SceneViewModel.objects.create(
            bk_biz_id=2,
            scene_id="kubernetes",
            type="",
            id="pod",
            name="Pod",
            mode="auto",
            variables=[],
            panels=[],
            list=[],
            order=[],
            options={},
        )

        resource.scene_view.update_scene_view(params)
        view = SceneViewModel.objects.get(bk_biz_id=2, scene_id="kubernetes", type="", id="pod")
        assert view.order[0]["id"] == order_id
