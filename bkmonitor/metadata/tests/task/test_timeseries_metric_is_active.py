"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import datetime

import pytest

from metadata import models

pytestmark = pytest.mark.django_db(databases="__all__")

DEFAULT_GROUP_ID = 100
DEFAULT_TABLE_ID = "test_is_active.__default__"


@pytest.fixture
def create_and_delete_records():
    """创建测试用的 TimeSeriesGroup 和 TimeSeriesMetric 记录"""
    models.TimeSeriesGroup.objects.create(
        bk_data_id=1000,
        bk_biz_id=1,
        table_id=DEFAULT_TABLE_ID,
        is_split_measurement=True,
        time_series_group_id=DEFAULT_GROUP_ID,
        time_series_group_name="test_is_active_group",
        label="test",
        creator="admin",
    )
    # 创建一些已存在的指标，其中部分设置为非活跃状态
    models.TimeSeriesMetric.objects.bulk_create(
        [
            models.TimeSeriesMetric(
                group_id=DEFAULT_GROUP_ID,
                table_id="test_is_active.metric1",
                field_name="metric1",
                tag_list=["tag1", "tag2"],
                is_active=True,  # 活跃状态
            ),
            models.TimeSeriesMetric(
                group_id=DEFAULT_GROUP_ID,
                table_id="test_is_active.metric2",
                field_name="metric2",
                tag_list=["tag1", "tag2"],
                is_active=True,  # 活跃状态
            ),
            models.TimeSeriesMetric(
                group_id=DEFAULT_GROUP_ID,
                table_id="test_is_active.metric3",
                field_name="metric3",
                tag_list=["tag1", "tag2"],
                is_active=False,  # 非活跃状态
            ),
        ]
    )
    yield
    # 清理测试数据
    models.TimeSeriesGroup.objects.filter(time_series_group_id=DEFAULT_GROUP_ID).delete()
    models.TimeSeriesMetric.objects.filter(group_id=DEFAULT_GROUP_ID).delete()


def test_create_metric_with_is_active_true(create_and_delete_records):
    """
    测试新创建的指标，is_active 字段应该设置为 True
    """
    curr_time = int(datetime.datetime.now().timestamp())
    metric_info_list = [
        {
            "field_name": "new_metric1",
            "tag_value_list": {
                "endpoint": {"last_update_time": curr_time, "values": []},
                "target": {"last_update_time": curr_time, "values": []},
            },
            "last_modify_time": curr_time,
        }
    ]

    models.TimeSeriesMetric.bulk_refresh_ts_metrics(
        group_id=DEFAULT_GROUP_ID,
        table_id=DEFAULT_TABLE_ID,
        metric_info_list=metric_info_list,
        is_auto_discovery=True,
    )

    # 验证新创建的指标存在且 is_active=True
    new_metric = models.TimeSeriesMetric.objects.get(group_id=DEFAULT_GROUP_ID, field_name="new_metric1")
    assert new_metric.is_active is True
    assert models.TimeSeriesMetric.objects.filter(group_id=DEFAULT_GROUP_ID).count() == 4


def test_update_existing_metric_to_active(create_and_delete_records):
    """
    测试更新已存在的指标，如果指标在返回列表中，is_active 应该更新为 True
    """
    curr_time = int(datetime.datetime.now().timestamp())
    # metric3 原本是 is_active=False，现在在返回列表中，应该更新为 True
    metric_info_list = [
        {
            "field_name": "metric3",
            "tag_value_list": {
                "endpoint": {"last_update_time": curr_time, "values": []},
                "target": {"last_update_time": curr_time, "values": []},
            },
            "last_modify_time": curr_time,
        }
    ]

    # 验证更新前 metric3 是 False
    metric3_before = models.TimeSeriesMetric.objects.get(group_id=DEFAULT_GROUP_ID, field_name="metric3")
    assert metric3_before.is_active is False

    models.TimeSeriesMetric.bulk_refresh_ts_metrics(
        group_id=DEFAULT_GROUP_ID,
        table_id=DEFAULT_TABLE_ID,
        metric_info_list=metric_info_list,
        is_auto_discovery=True,
    )

    # 验证更新后 metric3 是 True
    metric3_after = models.TimeSeriesMetric.objects.get(group_id=DEFAULT_GROUP_ID, field_name="metric3")
    assert metric3_after.is_active is True


def test_set_metric_to_inactive_when_not_in_list(create_and_delete_records):
    """
    测试不在返回列表中的已存在指标，is_active 应该设置为 False
    """
    curr_time = int(datetime.datetime.now().timestamp())
    # 只返回 metric1，metric2 和 metric3 不在列表中
    metric_info_list = [
        {
            "field_name": "metric1",
            "tag_value_list": {
                "endpoint": {"last_update_time": curr_time, "values": []},
                "target": {"last_update_time": curr_time, "values": []},
            },
            "last_modify_time": curr_time,
        }
    ]

    # 验证更新前 metric2 是 True
    metric2_before = models.TimeSeriesMetric.objects.get(group_id=DEFAULT_GROUP_ID, field_name="metric2")
    assert metric2_before.is_active is True

    models.TimeSeriesMetric.bulk_refresh_ts_metrics(
        group_id=DEFAULT_GROUP_ID,
        table_id=DEFAULT_TABLE_ID,
        metric_info_list=metric_info_list,
        is_auto_discovery=True,
    )

    # 验证 metric1 仍然是 True（在列表中）
    metric1 = models.TimeSeriesMetric.objects.get(group_id=DEFAULT_GROUP_ID, field_name="metric1")
    assert metric1.is_active is True

    # 验证 metric2 更新为 False（不在列表中）
    metric2_after = models.TimeSeriesMetric.objects.get(group_id=DEFAULT_GROUP_ID, field_name="metric2")
    assert metric2_after.is_active is False

    # 验证 metric3 仍然是 False（不在列表中，且原本就是 False）
    metric3 = models.TimeSeriesMetric.objects.get(group_id=DEFAULT_GROUP_ID, field_name="metric3")
    assert metric3.is_active is False


def test_mixed_scenario_active_and_inactive(create_and_delete_records):
    """
    测试混合场景：部分指标在返回列表中，部分不在
    """
    curr_time = int(datetime.datetime.now().timestamp())
    # 返回 metric1 和 metric2，不返回 metric3
    metric_info_list = [
        {
            "field_name": "metric1",
            "tag_value_list": {
                "endpoint": {"last_update_time": curr_time, "values": []},
                "target": {"last_update_time": curr_time, "values": []},
            },
            "last_modify_time": curr_time,
        },
        {
            "field_name": "metric2",
            "tag_value_list": {
                "endpoint": {"last_update_time": curr_time, "values": []},
                "target": {"last_update_time": curr_time, "values": []},
            },
            "last_modify_time": curr_time,
        },
    ]

    models.TimeSeriesMetric.bulk_refresh_ts_metrics(
        group_id=DEFAULT_GROUP_ID,
        table_id=DEFAULT_TABLE_ID,
        metric_info_list=metric_info_list,
        is_auto_discovery=True,
    )

    # 验证在列表中的指标是 True
    metric1 = models.TimeSeriesMetric.objects.get(group_id=DEFAULT_GROUP_ID, field_name="metric1")
    assert metric1.is_active is True

    metric2 = models.TimeSeriesMetric.objects.get(group_id=DEFAULT_GROUP_ID, field_name="metric2")
    assert metric2.is_active is True

    # 验证不在列表中的指标是 False
    metric3 = models.TimeSeriesMetric.objects.get(group_id=DEFAULT_GROUP_ID, field_name="metric3")
    assert metric3.is_active is False


def test_create_and_update_metrics_together(create_and_delete_records):
    """
    测试同时创建新指标和更新已存在指标的场景
    """
    curr_time = int(datetime.datetime.now().timestamp())
    # 包含新指标和已存在的指标
    metric_info_list = [
        {
            "field_name": "metric1",  # 已存在，在列表中
            "tag_value_list": {
                "endpoint": {"last_update_time": curr_time, "values": []},
                "target": {"last_update_time": curr_time, "values": []},
            },
            "last_modify_time": curr_time,
        },
        {
            "field_name": "new_metric2",  # 新指标
            "tag_value_list": {
                "endpoint": {"last_update_time": curr_time, "values": []},
                "target": {"last_update_time": curr_time, "values": []},
            },
            "last_modify_time": curr_time,
        },
    ]

    initial_count = models.TimeSeriesMetric.objects.filter(group_id=DEFAULT_GROUP_ID).count()
    assert initial_count == 3

    models.TimeSeriesMetric.bulk_refresh_ts_metrics(
        group_id=DEFAULT_GROUP_ID,
        table_id=DEFAULT_TABLE_ID,
        metric_info_list=metric_info_list,
        is_auto_discovery=True,
    )

    # 验证新指标创建成功且 is_active=True
    new_metric = models.TimeSeriesMetric.objects.get(group_id=DEFAULT_GROUP_ID, field_name="new_metric2")
    assert new_metric.is_active is True

    # 验证已存在的指标仍然是 True
    metric1 = models.TimeSeriesMetric.objects.get(group_id=DEFAULT_GROUP_ID, field_name="metric1")
    assert metric1.is_active is True

    # 验证不在列表中的指标更新为 False
    metric2 = models.TimeSeriesMetric.objects.get(group_id=DEFAULT_GROUP_ID, field_name="metric2")
    assert metric2.is_active is False

    metric3 = models.TimeSeriesMetric.objects.get(group_id=DEFAULT_GROUP_ID, field_name="metric3")
    assert metric3.is_active is False

    # 验证总数增加了
    final_count = models.TimeSeriesMetric.objects.filter(group_id=DEFAULT_GROUP_ID).count()
    assert final_count == 4


def test_empty_metric_list_sets_all_to_inactive(create_and_delete_records):
    """
    测试当返回的指标列表为空时，所有已存在的指标应该设置为非活跃
    """
    # 返回空列表
    metric_info_list = []

    # 验证更新前所有指标都是活跃的（除了 metric3）
    metric1_before = models.TimeSeriesMetric.objects.get(group_id=DEFAULT_GROUP_ID, field_name="metric1")
    assert metric1_before.is_active is True

    metric2_before = models.TimeSeriesMetric.objects.get(group_id=DEFAULT_GROUP_ID, field_name="metric2")
    assert metric2_before.is_active is True

    models.TimeSeriesMetric.bulk_refresh_ts_metrics(
        group_id=DEFAULT_GROUP_ID,
        table_id=DEFAULT_TABLE_ID,
        metric_info_list=metric_info_list,
        is_auto_discovery=True,
    )

    # 验证所有指标都更新为 False
    metric1_after = models.TimeSeriesMetric.objects.get(group_id=DEFAULT_GROUP_ID, field_name="metric1")
    assert metric1_after.is_active is False

    metric2_after = models.TimeSeriesMetric.objects.get(group_id=DEFAULT_GROUP_ID, field_name="metric2")
    assert metric2_after.is_active is False

    metric3 = models.TimeSeriesMetric.objects.get(group_id=DEFAULT_GROUP_ID, field_name="metric3")
    assert metric3.is_active is False
