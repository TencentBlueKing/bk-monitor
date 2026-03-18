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


import metadata.models.space.space_table_id_redis as redis_module
from metadata.models.constants import DataIdCreatedFromSystem
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis

BK_TENANT_ID = "system"
V3_DATA_ID = 610001
V4_DATA_ID = 610002
V3_GROUP_ID = 710001
V4_GROUP_ID = 710002
V3_TABLE_ID = "1001_bkmonitor_time_series_610001.__default__"
V4_TABLE_ID = "1001_bkmonitor_time_series_610002.__default__"
FIXED_NOW = datetime.datetime(2026, 3, 10, 12, 0, tzinfo=datetime.timezone.utc)


def build_filter_model_stub(metric_queries: list[dict]) -> tuple[callable, datetime.datetime]:
    begin_time = FIXED_NOW - datetime.timedelta(hours=1)

    def fake_filter_model_by_in_page(
        model,
        field_op,
        filter_data,
        page_size=None,
        value_func=None,
        value_field_list=None,
        other_filter=None,
    ):
        if model is redis_module.models.TimeSeriesGroup:
            assert field_op == "table_id__in"
            assert set(filter_data) == {V3_TABLE_ID, V4_TABLE_ID}
            return [
                {"table_id": V3_TABLE_ID, "time_series_group_id": V3_GROUP_ID},
                {"table_id": V4_TABLE_ID, "time_series_group_id": V4_GROUP_ID},
            ]

        if model is redis_module.models.DataSourceResultTable:
            assert field_op == "table_id__in"
            assert set(filter_data) == {V3_TABLE_ID, V4_TABLE_ID}
            assert other_filter == {"bk_tenant_id": BK_TENANT_ID}
            return [
                {"table_id": V3_TABLE_ID, "bk_data_id": V3_DATA_ID},
                {"table_id": V4_TABLE_ID, "bk_data_id": V4_DATA_ID},
            ]

        if model is redis_module.models.DataSource:
            assert field_op == "bk_data_id__in"
            assert set(filter_data) == {V3_DATA_ID, V4_DATA_ID}
            assert value_func == "values_list"
            assert value_field_list == ["bk_data_id"]
            assert other_filter == {
                "bk_tenant_id": BK_TENANT_ID,
                "created_from": DataIdCreatedFromSystem.BKDATA.value,
            }
            return [V4_DATA_ID]

        if model is redis_module.models.TimeSeriesMetric:
            metric_queries.append({"group_ids": set(filter_data), "other_filter": other_filter})
            if other_filter == {"is_active": True}:
                return [
                    {"field_name": "v4_active_recent", "group_id": V4_GROUP_ID},
                    {"field_name": "v4_active_stale", "group_id": V4_GROUP_ID},
                ]
            if other_filter == {"last_modify_time__gte": begin_time}:
                result = []
                if V3_GROUP_ID in set(filter_data):
                    result.extend(
                        [
                            {"field_name": "v3_active_recent", "group_id": V3_GROUP_ID},
                            {"field_name": "v3_inactive_recent", "group_id": V3_GROUP_ID},
                        ]
                    )
                if V4_GROUP_ID in set(filter_data):
                    result.extend(
                        [
                            {"field_name": "v4_active_recent", "group_id": V4_GROUP_ID},
                            {"field_name": "v4_inactive_recent", "group_id": V4_GROUP_ID},
                        ]
                    )
                return result

            raise AssertionError(f"unexpected time series metric filter: {other_filter}")

        raise AssertionError(f"unexpected model: {model}")

    return fake_filter_model_by_in_page, begin_time


def test_filter_ts_info_use_is_active_only_for_v4(settings, monkeypatch):
    settings.ENABLE_TS_METRIC_FILTER_BY_IS_ACTIVE = True
    settings.TIME_SERIES_METRIC_EXPIRED_SECONDS = 3600
    metric_queries = []
    fake_filter_model_by_in_page, begin_time = build_filter_model_stub(metric_queries)
    monkeypatch.setattr(redis_module, "tz_now", lambda: FIXED_NOW)
    monkeypatch.setattr(redis_module, "filter_model_by_in_page", fake_filter_model_by_in_page)

    result = SpaceTableIDRedis()._filter_ts_info({V3_TABLE_ID, V4_TABLE_ID}, bk_tenant_id=BK_TENANT_ID)

    assert result["group_id_field_map"] == {
        V3_GROUP_ID: {"v3_active_recent", "v3_inactive_recent"},
        V4_GROUP_ID: {"v4_active_recent", "v4_active_stale", "v4_inactive_recent"},
    }
    assert metric_queries == [
        {"group_ids": {V4_GROUP_ID}, "other_filter": {"is_active": True}},
        {"group_ids": {V4_GROUP_ID}, "other_filter": {"last_modify_time__gte": begin_time}},
        {"group_ids": {V3_GROUP_ID}, "other_filter": {"last_modify_time__gte": begin_time}},
    ]


def test_filter_ts_info_keep_time_filter_when_switch_disabled(settings, monkeypatch):
    settings.ENABLE_TS_METRIC_FILTER_BY_IS_ACTIVE = False
    settings.TIME_SERIES_METRIC_EXPIRED_SECONDS = 3600
    metric_queries = []
    fake_filter_model_by_in_page, begin_time = build_filter_model_stub(metric_queries)
    monkeypatch.setattr(redis_module, "tz_now", lambda: FIXED_NOW)
    monkeypatch.setattr(redis_module, "filter_model_by_in_page", fake_filter_model_by_in_page)

    result = SpaceTableIDRedis()._filter_ts_info({V3_TABLE_ID, V4_TABLE_ID}, bk_tenant_id=BK_TENANT_ID)

    assert result["group_id_field_map"] == {
        V3_GROUP_ID: {"v3_active_recent", "v3_inactive_recent"},
        V4_GROUP_ID: {"v4_active_recent", "v4_inactive_recent"},
    }
    assert metric_queries == [
        {"group_ids": {V3_GROUP_ID, V4_GROUP_ID}, "other_filter": {"last_modify_time__gte": begin_time}}
    ]
