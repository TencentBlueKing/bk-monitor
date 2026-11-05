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
import json
from unittest.mock import MagicMock, PropertyMock, patch

from metadata.models.storage import ESStorage


def _storage():
    storage = ESStorage(
        table_id="biz_bklog.demo",
        date_format="%Y%m%d",
        warm_phase_days=2,
        time_zone=0,
    )
    storage.index_settings = json.dumps(
        {
            "number_of_shards": 1,
            "index.routing.allocation.include.tag": "hot",
        }
    )
    storage.es_client = MagicMock()
    return storage


def test_backfill_only_untagged_indices_inside_hot_window():
    storage = _storage()
    today = "v2_biz_bklog_demo_20261105_0"
    yesterday = "v2_biz_bklog_demo_20261104_0"
    older = "v2_biz_bklog_demo_20261103_0"
    storage.es_client.indices.get_alias.return_value = {today: {}, yesterday: {}, older: {}}

    def get_settings(index, flat_settings=True):
        if index == today:
            return {index: {"settings": {"index.routing.allocation.include.tag": "hot"}}}
        return {index: {"settings": {"index.number_of_shards": "1"}}}

    storage.es_client.indices.get_settings.side_effect = get_settings
    with patch.object(ESStorage, "now", new_callable=PropertyMock, return_value=datetime.datetime(2026, 11, 5)):
        updated = storage.backfill_hot_allocation_settings()

    assert updated == [yesterday]
    storage.es_client.indices.put_settings.assert_called_once_with(
        index=yesterday,
        body={"index.routing.allocation.include.tag": "hot"},
    )


def test_backfill_skips_when_hot_window_is_closed():
    storage = _storage()
    storage.warm_phase_days = 0
    updated = storage.backfill_hot_allocation_settings()
    assert updated == []
    storage.es_client.indices.get_alias.assert_not_called()
