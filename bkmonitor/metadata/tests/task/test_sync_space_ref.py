"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
from unittest import mock

import pytest

from metadata.models.space import Space
from metadata.task.sync_space import sync_bcs_space

logger = logging.getLogger("metadata")


@pytest.mark.django_db(databases="__all__")(databases=["monitor_api"])
def test_sync_bcs_space_no_projects_need_update_or_create():
    # 场景1: 没有需要更新或新增的项目
    with (
        mock.patch("metadata.task.sync_space.get_valid_bcs_projects") as mock_get_projects,
        mock.patch("metadata.task.sync_space.create_bcs_spaces") as mock_create_spaces,
    ):
        # 准备测试数据
        mock_get_projects.return_value = [
            {"project_code": "p1", "project_id": "pid1", "name": "项目1"},
            {"project_code": "p2", "project_id": "pid2", "name": "项目2"},
        ]

        # 创建已存在的空间记录
        Space.objects.create(
            space_type_id="bkci", space_id="p1", space_code="pid1", space_name="项目1", is_bcs_valid=True
        )
        Space.objects.create(
            space_type_id="bkci", space_id="p2", space_code="pid2", space_name="项目2", is_bcs_valid=True
        )

        sync_bcs_space()

        # 验证没有调用创建方法
        mock_create_spaces.assert_not_called()


@pytest.mark.django_db(databases="__all__")(databases=["monitor_api"])
def test_sync_bcs_space_has_projects_need_update():
    # 场景2: 有需要更新的项目
    with (
        mock.patch("metadata.task.sync_space.get_valid_bcs_projects") as mock_get_projects,
        mock.patch("metadata.task.sync_space.create_bcs_spaces"),
    ):
        # 准备测试数据
        mock_get_projects.return_value = [
            {"project_code": "p1_update", "project_id": "pid1", "name": "新项目名"},
            {"project_code": "p2", "project_id": "pid2", "name": "项目2"},
        ]

        # 创建需要更新的空间记录(使用不同的ID避免冲突)
        Space.objects.create(
            space_type_id="bkci", space_id="p1_update", space_code="old_pid", space_name="旧名称", is_bcs_valid=False
        )

        sync_bcs_space()

        # 验证空间更新
        updated_space = Space.objects.get(space_id="p1_update")
        assert updated_space.space_code == "pid1"
        assert updated_space.space_name == "新项目名"
        assert updated_space.is_bcs_valid is True


@pytest.mark.django_db(databases="__all__")(databases=["monitor_api"])
def test_sync_bcs_space_has_projects_need_create():
    # 场景3: 有需要新增的项目
    with (
        mock.patch("metadata.task.sync_space.get_valid_bcs_projects") as mock_get_projects,
        mock.patch("metadata.task.sync_space.create_bcs_spaces") as mock_create_spaces,
    ):
        # 准备测试数据
        new_project = {"project_code": "p3", "project_id": "pid3", "name": "项目3"}
        mock_get_projects.return_value = [new_project]

        sync_bcs_space()

        # 验证创建方法被调用
        mock_create_spaces.assert_called_once_with([new_project])


@pytest.mark.django_db(databases="__all__")(databases=["monitor_api"])
def test_sync_bcs_space_create_projects_with_exception():
    # 场景4: 创建项目时抛出异常
    with (
        mock.patch("metadata.task.sync_space.get_valid_bcs_projects") as mock_get_projects,
        mock.patch("metadata.task.sync_space.create_bcs_spaces") as mock_create_spaces,
        mock.patch.object(logger, "error") as mock_logger,
    ):
        # 准备测试数据
        mock_get_projects.return_value = [{"project_code": "p4", "project_id": "pid4", "name": "项目4"}]
        mock_create_spaces.side_effect = Exception("test error")

        sync_bcs_space()

        # 验证异常日志
        assert "create bcs project space error" in mock_logger.call_args[0][0]
        mock_create_spaces.assert_called_once()
