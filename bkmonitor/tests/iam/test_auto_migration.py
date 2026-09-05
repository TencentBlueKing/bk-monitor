"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from importlib import import_module
from unittest.mock import MagicMock

from django.apps import apps
from django.core.management.sql import emit_post_migrate_signal
from django.dispatch import Signal
from django.test import override_settings

from bkmonitor.iam.iam_engine.django.apps import IamEngineConfig


def test_semi_auto_migration_uses_model_bearing_sender_and_runs_once(monkeypatch):
    post_migrate = Signal()
    monkeypatch.setattr("django.db.models.signals.post_migrate", post_migrate)

    app_config = IamEngineConfig(
        "bkmonitor.iam.iam_engine.django",
        import_module("bkmonitor.iam.iam_engine.django"),
    )
    app_config._migration_done = False
    app_config._do_auto_migration = MagicMock()

    framework = object()
    migration_config = {
        "mode": "semi_auto",
        "database": "default",
    }

    with override_settings(IAM_FRAMEWORK={"MIGRATION": migration_config}):
        app_config._maybe_auto_migrate(framework)

    legacy_sender = apps.get_app_config("bkmonitor")
    assert legacy_sender.models_module is not None

    emit_post_migrate_signal(verbosity=0, interactive=False, db="monitor_api")
    app_config._do_auto_migration.assert_not_called()

    emit_post_migrate_signal(verbosity=0, interactive=False, db="default")
    emit_post_migrate_signal(verbosity=0, interactive=False, db="default")

    app_config._do_auto_migration.assert_called_once_with(framework, migration_config)
