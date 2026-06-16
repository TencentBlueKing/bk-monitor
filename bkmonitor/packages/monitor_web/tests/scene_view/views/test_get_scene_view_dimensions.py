"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest import mock

from monitor_web.scene_view.resources.view import GetSceneViewDimensionsResource

# 模拟 metadata query_time_series_group 返回：进程性能分组真实上报的维度（含 process / 维度提取自定义维度 / 需过滤的 time）
MOCK_PROCESS_TS_GROUPS = [
    {
        "time_series_group_name": "process_perf",
        "metric_info_list": [
            {
                "field_name": "cpu_total_pct",
                "tag_list": [
                    {"field_name": "process", "description": "进程"},
                    {"field_name": "process_name", "description": "进程名"},
                    {"field_name": "game_zone", "description": ""},  # extract_pattern 提取的自定义维度
                    {"field_name": "time", "description": "time"},  # 内部维度，应被过滤
                ],
            }
        ],
    }
]


def _patch(groups):
    """同时 mock metadata API 与 CollectConfigMeta，使用例不依赖 DB。"""
    api_patch = mock.patch(
        "monitor_web.scene_view.resources.view.api.metadata.query_time_series_group",
        return_value=groups,
    )
    objects_patch = mock.patch("monitor_web.models.collecting.CollectConfigMeta.objects")
    return api_patch, objects_patch


def test_augment_surfaces_process_and_extract_dimensions():
    """进程表应按真实上报维度补全 process 与维度提取的自定义维度，并过滤内部维度。"""
    api_patch, objects_patch = _patch(MOCK_PROCESS_TS_GROUPS)
    with api_patch, objects_patch as mock_objects:
        mock_objects.filter.return_value.exists.return_value = True
        extra = GetSceneViewDimensionsResource._augment_process_dimensions(
            "system", 2, {"process.perf", "other.custom.table"}
        )

    dim_ids = {dim["id"] for dim in extra["process.perf"]}
    assert "process" in dim_ids  # 进程别名维度（核心修复）
    assert "game_zone" in dim_ids  # 维度提取自定义维度
    assert "process_name" in dim_ids
    assert "time" not in dim_ids  # 内部维度被过滤
    assert "other.custom.table" not in extra  # 非进程表不处理


def test_augment_gated_by_collect_config():
    """业务没有进程采集时直接跳过，不查询 metadata。"""
    api_patch, objects_patch = _patch(MOCK_PROCESS_TS_GROUPS)
    with api_patch as mock_api, objects_patch as mock_objects:
        mock_objects.filter.return_value.exists.return_value = False
        extra = GetSceneViewDimensionsResource._augment_process_dimensions("system", 2, {"process.perf"})

    assert extra == {}
    mock_api.assert_not_called()


def test_augment_skips_when_no_process_table():
    """请求不涉及进程表时零开销返回，不查 CollectConfigMeta、不查 metadata。"""
    with mock.patch("monitor_web.scene_view.resources.view.api.metadata.query_time_series_group") as mock_api:
        extra = GetSceneViewDimensionsResource._augment_process_dimensions("system", 2, {"system.cpu_detail"})

    assert extra == {}
    mock_api.assert_not_called()
