"""Django deployment/CLI integration; no product imports or migration state tables."""

import hashlib
import sys
from collections.abc import Callable
from contextlib import contextmanager
from threading import RLock

from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from iam_engine.model.sync import ModelSyncError
from iam_engine.model.sync import ModelSyncService
from iam_engine.error_summary import sanitize_error_summary

_local_lock = RLock()


@contextmanager
def model_sync_lock(identity, *, using="default"):
    """Serialize model writers. MySQL advisory locks release on process disconnect.

    SQLite is only used by the offline harness and uses an in-process lock.
    No historical IAM records or DB schema are changed by this lock.
    """
    connection = connections[using]
    name = "iam-model-" + hashlib.sha256(identity.encode()).hexdigest()[:48]
    with _local_lock:
        if connection.vendor == "sqlite":
            yield
            return
        if connection.vendor != "mysql":
            raise ModelSyncError(f"model sync locking is unsupported for database vendor {connection.vendor!r}")
        with connection.cursor() as cursor:
            cursor.execute("SELECT GET_LOCK(%s, %s)", [name, 30])
            if cursor.fetchone()[0] != 1:
                raise ModelSyncError("another IAM model synchronization holds the deployment lock")
        try:
            yield
        finally:
            with connection.cursor() as cursor:
                cursor.execute("SELECT RELEASE_LOCK(%s)", [name])


@contextmanager
def legacy_migration_command():
    """The original IAM SDK writes only in a migrate process; preserve that guard."""
    appended = "migrate" not in sys.argv
    if appended:
        sys.argv.append("migrate")
    try:
        yield
    finally:
        if appended:
            sys.argv.remove("migrate")


class ModelSyncCommand(BaseCommand):
    get_service: Callable[[], ModelSyncService]
    help = "按当前 IAM 模式预览模型；--apply 实际同步，与部署 post_migrate 共用同一服务"

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="实际写入 IAM；默认仅预览")

    def handle(self, *args, **options):
        try:
            mode, plans = self.get_service().run(apply=options["apply"])
        except Exception as error:
            raise CommandError(sanitize_error_summary(error)) from error
        self.stdout.write(f"mode: {mode.value}")
        for target, plan in plans.items():
            self.stdout.write(f"[{target}]\n{plan.describe()}")
            for reason in getattr(plan, "drift", ()):
                self.stdout.write(f"drift: {reason}")
            if getattr(plan, "blocking", ()):
                raise CommandError("model plan is blocked: " + "; ".join(plan.blocking))
        self.stdout.write(
            "model synchronization completed" if options["apply"] else "preview only: nothing was written"
        )
