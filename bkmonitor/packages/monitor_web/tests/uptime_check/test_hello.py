"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from monitor_web.uptime_check.constants import UPTIME_CHECK_DB, UPTIME_DATA_SOURCE_LABEL


class TestUptimeCheckConstants:
    def test_uptime_check_db_constant(self):
        assert UPTIME_CHECK_DB == "uptimecheck"

    def test_uptime_data_source_label(self):
        assert UPTIME_DATA_SOURCE_LABEL == "bk_monitor"