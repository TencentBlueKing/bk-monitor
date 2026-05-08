"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from bkmonitor.models.metric_list_cache import MetricListCache
from monitor_web.strategies.resources.v2 import GetMetricListV2Resource


class TestGetMetricListV2Resource:
    def test_serializer_rejects_zero_page(self):
        serializer = GetMetricListV2Resource.RequestSerializer(
            data={
                "bk_biz_id": 2,
                "page": 0,
                "page_size": 100,
            }
        )

        assert not serializer.is_valid()
        assert "page" in serializer.errors

    def test_data_source_filter_orders_by_frequency_and_id(self):
        params = {
            "data_source_label": [],
            "data_source": [],
        }

        metrics = GetMetricListV2Resource.data_source_filter(MetricListCache.objects.all(), params)

        assert metrics.query.order_by == ("-use_frequency", "id")
