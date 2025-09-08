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

from api.bcs_cc.default import BatchGetProjects
from core.drf_resource import api


@pytest.fixture
def mock_request_projects(monkeypatch):
    mock_return_value = [
        {
            "project_id": "test_pid_1",
            "name": "test_name_1",
            "project_code": "test_code_1",
            "bk_biz_id": "1",
        },
    ]
    monkeypatch.setattr(BatchGetProjects, "perform_request", lambda *args, **kwargs: mock_return_value)


def test_batch_get_projects(mock_request_projects):
    projects = api.bcs_cc.batch_get_projects()
    assert isinstance(projects, list)
    assert len(projects) == 1

    for p in projects:
        assert p["bk_biz_id"].isdigit()
        # 下面key必须存在
        for key in ["project_id", "name", "project_code", "bk_biz_id"]:
            assert key in p
