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

from bkmonitor.strategy.history import MIN_CLEAN_STRATEGY_HISTORY_DAYS


def test_command_passes_cleanup_options_and_prints_deleted_count():
    """带 --execute 时应真正删除，并将参数传给业务层。"""
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
            execute=True,
            stdout=stdout,
        )

    params = clean.call_args.args[0]
    assert params.days == 30
    assert params.batch_size == 200
    assert params.keep_latest_snapshots == 3
    assert params.dry_run is False
    assert "deleted 42 records" in stdout.getvalue()


def test_command_defaults_to_dry_run_without_execute():
    """未传 --execute 时应默认 dry-run，不删除。"""
    stdout = StringIO()

    with mock.patch(
        "bkmonitor.management.commands.clean_strategy_history.clean_strategy_history",
        return_value=42,
    ) as clean:
        call_command("clean_strategy_history", days=30, stdout=stdout)

    params = clean.call_args.args[0]
    assert params.batch_size == 1000
    assert params.keep_latest_snapshots == 1
    assert params.dry_run is True
    assert "would delete 42 records" in stdout.getvalue()
    assert "deleted 42 records" not in stdout.getvalue()


def test_compat_command_uses_safe_legacy_status_cleanup():
    """临时兼容命令应调用兼容清理入口，并保持默认 dry-run。"""
    stdout = StringIO()

    with mock.patch(
        "bkmonitor.management.commands.clean_strategy_history_compat.clean_strategy_history_compat",
        return_value=7,
    ) as clean:
        call_command("clean_strategy_history_compat", days=30, stdout=stdout)

    params = clean.call_args.args[0]
    assert params.dry_run is True
    assert "deprecated compatibility command" in stdout.getvalue()
    assert "would delete 7 records" in stdout.getvalue()


def test_command_rejects_days_below_minimum_retention():
    """命令层拒绝低于最小保留天数的 --days。"""
    with pytest.raises(CommandError, match=rf"days must be >= {MIN_CLEAN_STRATEGY_HISTORY_DAYS}"):
        call_command(
            "clean_strategy_history",
            days=MIN_CLEAN_STRATEGY_HISTORY_DAYS - 1,
            stdout=StringIO(),
        )


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
