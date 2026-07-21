# -*- coding: utf-8 -*-  # noqa: UP009
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
from unittest import mock

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError


def test_command_passes_cleanup_options_and_prints_deleted_count():
    """命令应将参数传给业务层，并输出实际删除数量。"""
    stdout = StringIO()

    with mock.patch(
        "bkmonitor.management.commands.clean_strategy_history.clean_strategy_history",
        return_value=42,
    ) as clean:
        call_command(
            "clean_strategy_history",
            days=30,
            batch_size=200,
            keep_latest_snapshots=3,
            stdout=stdout,
        )

    params = clean.call_args.args[0]
    assert params.days == 30
    assert params.batch_size == 200
    assert params.keep_latest_snapshots == 3
    assert "deleted 42 records" in stdout.getvalue()


def test_command_uses_business_defaults():
    """未指定可选参数时应使用业务层默认值。"""
    with mock.patch(
        "bkmonitor.management.commands.clean_strategy_history.clean_strategy_history",
        return_value=0,
    ) as clean:
        call_command("clean_strategy_history", days=30, stdout=StringIO())

    params = clean.call_args.args[0]
    assert params.batch_size == 1000
    assert params.keep_latest_snapshots == 1


@pytest.mark.parametrize(
    ("option", "value"),
    [
        ("days", 0),
        ("batch_size", 0),
        ("keep_latest_snapshots", 0),
    ],
)
def test_command_reports_invalid_cleanup_options_as_command_error(option, value):
    """业务参数校验错误应转换为 Django 命令错误。"""
    options = {
        "days": 30,
        "batch_size": 1000,
        "keep_latest_snapshots": 1,
        option: value,
    }

    with pytest.raises(CommandError, match="must be a positive integer"):
        call_command("clean_strategy_history", stdout=StringIO(), **options)
