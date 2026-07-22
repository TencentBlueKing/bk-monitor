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

from bkmonitor.models import StrategyHistoryModel
from bkmonitor.strategy.history import repair_legacy_bulk_strategy_history_status


def _create_history(*, operate: str, status: bool = False, message: str = "") -> StrategyHistoryModel:
    return StrategyHistoryModel.objects.create(
        strategy_id=1001,
        create_user="admin",
        operate=operate,
        status=status,
        message=message,
    )


@pytest.mark.django_db(databases=("default", "monitor_api"))
def test_repair_legacy_bulk_history_status_uses_empty_message_as_success():
    legacy_bulk_update = _create_history(operate="update")
    legacy_bulk_delete = _create_history(operate="delete")
    failed_update = _create_history(operate="update", message="bulk update failed")
    successful_update = _create_history(operate="update", status=True)
    unrelated_create = _create_history(operate="create")
    current_bulk_update = _create_history(operate="bulk_update")

    repaired = repair_legacy_bulk_strategy_history_status(batch_size=1, dry_run=False)

    assert repaired == 2
    assert set(StrategyHistoryModel.objects.filter(status=True).values_list("id", flat=True)) == {
        legacy_bulk_update.id,
        legacy_bulk_delete.id,
        successful_update.id,
    }
    assert set(StrategyHistoryModel.objects.filter(status=False).values_list("id", flat=True)) == {
        failed_update.id,
        unrelated_create.id,
        current_bulk_update.id,
    }


@pytest.mark.django_db(databases=("default", "monitor_api"))
def test_repair_legacy_bulk_history_status_dry_run_does_not_update_records():
    legacy_bulk_update = _create_history(operate="update")
    legacy_bulk_delete = _create_history(operate="delete")

    matched = repair_legacy_bulk_strategy_history_status(batch_size=1, dry_run=True)

    assert matched == 2
    assert not StrategyHistoryModel.objects.filter(
        id__in=[legacy_bulk_update.id, legacy_bulk_delete.id], status=True
    ).exists()


def test_repair_command_defaults_to_dry_run():
    stdout = StringIO()

    with mock.patch(
        "bkmonitor.management.commands.repair_strategy_history_status.repair_legacy_bulk_strategy_history_status",
        return_value=42,
    ) as repair:
        call_command("repair_strategy_history_status", stdout=stdout)

    repair.assert_called_once_with(batch_size=1000, dry_run=True)
    assert "would repair 42 records" in stdout.getvalue()


def test_repair_command_executes_with_requested_batch_size():
    stdout = StringIO()

    with mock.patch(
        "bkmonitor.management.commands.repair_strategy_history_status.repair_legacy_bulk_strategy_history_status",
        return_value=42,
    ) as repair:
        call_command("repair_strategy_history_status", batch_size=200, execute=True, stdout=stdout)

    repair.assert_called_once_with(batch_size=200, dry_run=False)
    assert "repaired 42 records" in stdout.getvalue()


def test_repair_command_rejects_non_positive_batch_size():
    with pytest.raises(CommandError, match="batch_size must be a positive integer"):
        call_command("repair_strategy_history_status", batch_size=0, stdout=StringIO())
