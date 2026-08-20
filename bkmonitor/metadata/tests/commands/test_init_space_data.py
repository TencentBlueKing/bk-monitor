"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from io import StringIO

import pytest
from django.core.management import call_command


@pytest.mark.parametrize("init_redis", ["True", "False"])
def test_init_redis_option_is_deprecated_noop(init_redis, mocker):
    mocker.patch("metadata.management.commands.init_space_data.Command.fix_dirty_datasource")
    mock_subcommand = mocker.patch("metadata.management.commands.init_space_data.call_command")
    stdout = StringIO()

    call_command(
        "init_space_data",
        init_type="False",
        sync_bkcc="False",
        sync_bcs="False",
        init_redis=init_redis,
        stdout=stdout,
    )

    mock_subcommand.assert_not_called()
    assert "参数 --init_redis 已废弃" in stdout.getvalue()
