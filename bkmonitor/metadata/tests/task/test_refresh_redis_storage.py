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

from metadata.task import config_refresh
from metadata.tools.constants import TASK_FINISHED_FAILURE, TASK_FINISHED_SUCCESS, TASK_STARTED


@pytest.mark.parametrize("failed", [False, True])
def test_refresh_redis_storage_reports_actual_status(mocker, failed):
    refresh = mocker.patch.object(config_refresh.models.ClusterInfo, "refresh_redis_storage_config")
    metrics = mocker.patch.object(config_refresh, "metrics")
    consul = mocker.patch.object(config_refresh.models.ClusterInfo, "refresh_consul_storage_config")
    if failed:
        refresh.side_effect = RuntimeError("redis unavailable")
        with pytest.raises(RuntimeError, match="redis unavailable"):
            config_refresh.refresh_redis_storage.__wrapped__()
    else:
        config_refresh.refresh_redis_storage.__wrapped__()

    refresh.assert_called_once_with()
    consul.assert_not_called()
    assert metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels.call_args_list == [
        mocker.call(task_name="refresh_redis_storage", status=TASK_STARTED, process_target=None),
        mocker.call(
            task_name="refresh_redis_storage",
            status=TASK_FINISHED_FAILURE if failed else TASK_FINISHED_SUCCESS,
            process_target=None,
        ),
    ]
    metrics.METADATA_CRON_TASK_COST_SECONDS.labels.return_value.observe.assert_called_once()
    metrics.report_all.assert_called_once_with()
