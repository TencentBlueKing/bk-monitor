"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
from types import SimpleNamespace

from bkmonitor.iam.iam_engine.django.apps import _log_system_migration
from bkmonitor.iam.iam_engine.django.management.commands.iam_engine_migrate import Command
from bkmonitor.iam.iam_engine.django.migration_logging import summarize_system_migration
from bkmonitor.iam.iam_engine.schema.diff import Change, ChangeType, EntityKind, MigrationPlan, MigrationReport


def _system_change(change_type, *, before=None, after=None, reason=""):
    return Change(
        kind=EntityKind.SYSTEM,
        change_type=change_type,
        entity_id="bk_monitor_v4",
        before=before,
        after=after,
        reason=reason,
    )


class TestSystemMigrationLogging:
    def test_uses_reconciled_dry_run_change_instead_of_local_plan(self):
        plan = MigrationPlan(
            provider_name="v4",
            changes=[_system_change(ChangeType.CREATE, after={"id": "bk_monitor_v4"})],
        )
        reconciled = _system_change(
            ChangeType.UPDATE,
            before={"id": "bk_monitor_v4", "callback_url": ""},
            after={"id": "bk_monitor_v4", "callback_url": "https://example.test/callback"},
            reason="System config differs",
        )
        report = MigrationReport(provider_name="v4", would_apply=[reconciled])

        result = summarize_system_migration(plan, report, dry_run=True)

        assert result.outcome == "would_apply"
        assert result.summary == "[v4] system: would apply 1 change(s)."
        assert result.details == (
            "  - UPDATE bk_monitor_v4 (changed_fields=callback_url; reason=System config differs)",
        )

    def test_create_summary_redacts_callback_url_and_summarizes_collections(self):
        change = _system_change(
            ChangeType.CREATE,
            after={
                "id": "bk_monitor_v4",
                "name": "监控平台",
                "description": "监控权限系统",
                "callback_url": "https://example.test/callback?token=secret",
                "managers": ["alice", "bob"],
                "clients": ["monitor", "paas"],
            },
            reason="System registration (local plan)",
        )
        plan = MigrationPlan(provider_name="v4", changes=[change])
        report = MigrationReport(provider_name="v4", applied=[change])

        result = summarize_system_migration(plan, report, dry_run=False)

        assert result.outcome == "applied"
        assert result.summary == "[v4] system: applied 1 change(s)."
        assert "name=监控平台" in result.details[0]
        assert "description=configured" in result.details[0]
        assert "callback_url=configured" in result.details[0]
        assert "managers=2" in result.details[0]
        assert "clients=2" in result.details[0]
        assert "https://example.test" not in result.details[0]
        assert "token=secret" not in result.details[0]

    def test_noop_uses_planned_system_id(self):
        plan = MigrationPlan(
            provider_name="v4",
            changes=[_system_change(ChangeType.CREATE, after={"id": "bk_monitor_v4"})],
        )
        report = MigrationReport(provider_name="v4")

        result = summarize_system_migration(plan, report, dry_run=False)

        assert result.outcome == "noop"
        assert result.summary == "[v4] system: no changes (id=bk_monitor_v4, reconciled=noop)."
        assert result.details == ()

    def test_failure_keeps_change_context_and_error(self):
        change = _system_change(
            ChangeType.UPDATE,
            before={"id": "bk_monitor_v4", "clients": ["monitor"]},
            after={"id": "bk_monitor_v4", "clients": ["monitor", "paas"]},
            reason="System config differs",
        )
        plan = MigrationPlan(provider_name="v4", changes=[change])
        report = MigrationReport(provider_name="v4", failed=[(change, "ProviderUnavailable: upstream timeout")])

        result = summarize_system_migration(plan, report, dry_run=False)

        assert result.outcome == "failed"
        assert result.is_error
        assert result.summary == "[v4] system: failed 1 change(s)."
        assert result.details == (
            "  - UPDATE bk_monitor_v4 (changed_fields=clients; reason=System config differs); "
            "error=ProviderUnavailable: upstream timeout",
        )

    def test_skipped_reason_is_reported_without_change_details(self):
        plan = MigrationPlan(
            provider_name="v4",
            changes=[_system_change(ChangeType.CREATE, after={"id": "bk_monitor_v4"})],
        )
        report = MigrationReport(provider_name="v4", skipped_reason="Destructive changes blocked")

        result = summarize_system_migration(plan, report, dry_run=False)

        assert result.outcome == "skipped"
        assert result.summary == "[v4] system: skipped (Destructive changes blocked)."
        assert result.details == ()

    def test_failure_redacts_common_secret_values(self):
        change = _system_change(ChangeType.CREATE, after={"id": "bk_monitor_v4"})
        plan = MigrationPlan(provider_name="v4", changes=[change])
        report = MigrationReport(
            provider_name="v4",
            failed=[
                (
                    change,
                    "ProviderError: token=plain-token, app_secret=plain-secret, authorization=Bearer plain-auth",
                )
            ],
        )

        result = summarize_system_migration(plan, report, dry_run=False)

        assert "plain-token" not in result.details[0]
        assert "plain-secret" not in result.details[0]
        assert "plain-auth" not in result.details[0]
        assert "token=***" in result.details[0]
        assert "app_secret=***" in result.details[0]
        assert "authorization=***" in result.details[0]

    def test_manual_command_writes_summary_and_change_details(self, capsys):
        plan = MigrationPlan(
            provider_name="v4",
            changes=[_system_change(ChangeType.CREATE, after={"id": "bk_monitor_v4"})],
        )
        reconciled = _system_change(
            ChangeType.UPDATE,
            before={"id": "bk_monitor_v4", "callback_url": ""},
            after={"id": "bk_monitor_v4", "callback_url": "https://example.test/callback"},
            reason="System config differs",
        )
        report = MigrationReport(provider_name="v4", would_apply=[reconciled])

        provider = SimpleNamespace(
            name="v4",
            plan_migration=lambda schema, scope: plan,
            apply_migration=lambda migration_plan, dry_run, allow_destructive: report,
        )

        Command()._migrate_system(provider, SimpleNamespace(schema=object()), dry_run=True)

        captured = capsys.readouterr()
        assert "[v4] system: would apply 1 change(s)." in captured.out
        assert "UPDATE bk_monitor_v4 (changed_fields=callback_url; reason=System config differs)" in captured.out
        assert not captured.err

    def test_semi_auto_logger_writes_summary_and_change_details(self, caplog):
        plan = MigrationPlan(
            provider_name="v4",
            changes=[_system_change(ChangeType.CREATE, after={"id": "bk_monitor_v4"})],
        )
        reconciled = _system_change(
            ChangeType.UPDATE,
            before={"id": "bk_monitor_v4", "clients": ["monitor"]},
            after={"id": "bk_monitor_v4", "clients": ["monitor", "paas"]},
            reason="System config differs",
        )
        report = MigrationReport(provider_name="v4", applied=[reconciled])

        with caplog.at_level(logging.INFO, logger="iam_engine.django"):
            _log_system_migration(plan, report)

        assert "iam_engine migration: [v4] system: applied 1 change(s)." in caplog.messages
        assert (
            "iam_engine migration:   - UPDATE bk_monitor_v4 (changed_fields=clients; reason=System config differs)"
        ) in caplog.messages
