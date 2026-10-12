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

from bkmonitor.data_source.utils.apm import APMAppTarget, LevelTarget, TraceDatasourceTarget


class TestTraceDatasourceTarget:
    """test_datasource_target.py 验收断言"""

    # [a] levels 默认空列表
    def test_levels_default_empty(self):
        target = TraceDatasourceTarget(
            table_id="bk_apm.default.span",
            app=APMAppTarget(bk_biz_id=2, app_name="my_app"),
        )
        assert target.levels == []

    # [b] 现有 TraceDatasourceTarget.build() 行为不变
    def test_build_without_levels(self):
        target = TraceDatasourceTarget.build(
            bk_biz_id=2,
            app_name="my_app",
            table_id="bk_apm.default.span",
        )
        assert target.table_id == "bk_apm.default.span"
        assert target.app.bk_biz_id == 2
        assert target.app.app_name == "my_app"
        assert target.retention is None
        assert target.levels == []

    def test_build_with_retention(self):
        target = TraceDatasourceTarget.build(
            bk_biz_id=2,
            app_name="my_app",
            table_id="bk_apm.default.span",
            retention=7,
        )
        assert target.retention == 7

    # [c] 可携带多个层级结果表
    def test_build_with_multiple_levels(self):
        levels = [
            LevelTarget(name="view", table_ids=["bk_rum.default.view_1", "bk_rum.default.view_2"]),
            LevelTarget(name="session", table_ids=["bk_rum.default.session_1"]),
            LevelTarget(name="trace", table_ids=["bk_apm.default.trace_1"]),
        ]
        target = TraceDatasourceTarget.build(
            bk_biz_id=2,
            app_name="my_app",
            table_id="bk_apm.default.span",
            levels=levels,
        )
        assert len(target.levels) == 3
        assert target.levels[0].name == "view"
        assert target.levels[0].table_ids == ["bk_rum.default.view_1", "bk_rum.default.view_2"]
        assert target.levels[1].name == "session"
        assert target.levels[2].name == "trace"

    def test_get_level_table_ids_existing(self):
        levels = [
            LevelTarget(name="view", table_ids=["bk_rum.default.view_1", "bk_rum.default.view_2"]),
            LevelTarget(name="session", table_ids=["bk_rum.default.session_1"]),
        ]
        target = TraceDatasourceTarget.build(
            bk_biz_id=2,
            app_name="my_app",
            table_id="bk_apm.default.span",
            levels=levels,
        )
        assert target.get_level_table_ids("view") == ["bk_rum.default.view_1", "bk_rum.default.view_2"]
        assert target.get_level_table_ids("session") == ["bk_rum.default.session_1"]

    def test_get_level_table_ids_missing(self):
        target = TraceDatasourceTarget.build(
            bk_biz_id=2,
            app_name="my_app",
            table_id="bk_apm.default.span",
        )
        assert target.get_level_table_ids("view") == []

    def test_target_is_frozen(self):
        """TraceDatasourceTarget 是 frozen dataclass，不可修改"""
        target = TraceDatasourceTarget.build(
            bk_biz_id=2,
            app_name="my_app",
            table_id="bk_apm.default.span",
        )
        with pytest.raises((AttributeError, TypeError)):
            target.table_id = "other"
