"""Isolated receipt tests: real ORM, no remote service bootstrap."""

import os
import sys
from pathlib import Path

from django.apps import AppConfig

SOURCE = Path(__file__).resolve().parents[2] / "bkmonitor"
sys.path.insert(0, str(SOURCE))


class ReceiptTestConfig(AppConfig):
    name = "bkmonitor"
    default_auto_field = "django.db.models.AutoField"

    def import_models(self):
        import importlib.util

        self.models = self.apps.all_models[self.label]
        spec = importlib.util.spec_from_file_location(
            "receipt_test_model", SOURCE / "bkmonitor/models/incident_delivery.py"
        )
        self.models_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.models_module)

    def ready(self):
        pass


SECRET_KEY = "isolated-receipt-tests"
INSTALLED_APPS = ["settings.ReceiptTestConfig"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
if os.environ.get("BKFARA_MYSQL_TEST_SOCKET"):
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.mysql",
        "NAME": "analysis_task_contracts",
        "USER": "root",
        "HOST": os.environ["BKFARA_MYSQL_TEST_SOCKET"],
        "OPTIONS": {"isolation_level": os.environ.get("BKFARA_MYSQL_TEST_ISOLATION", "read committed")},
        "TEST": {"NAME": f"test_delivery_receipts_{os.getpid()}"},
    }
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
