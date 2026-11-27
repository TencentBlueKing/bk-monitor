from unittest.mock import patch

from functools import partial

import pytest
from django.db import connections, router
from django.db.utils import ConnectionHandler
from django.utils import timezone

from apps.exceptions import ValidationError
from apps.log_admin_resource.registry import AdminResourceRegistry
from apps.log_admin_resource.handlers import archive
from apps.log_databus.models import ArchiveConfig, RestoreConfig
from apps.log_search.models import Space


def test_archive_resource_calls(monkeypatch, django_db_blocker):
    connection = ConnectionHandler({"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}})["default"]
    models = (Space, ArchiveConfig, RestoreConfig)
    for alias in {"default", *(router.db_for_read(m) for m in models), *(router.db_for_write(m) for m in models)}:
        monkeypatch.setattr(connections._connections, alias, connection, raising=False)
    with django_db_blocker.unblock(), connection.schema_editor() as editor:
        for model in models:
            editor.create_model(model)
        for biz, tenant in [(7, "system"), (9, "another")]:
            Space.objects.bulk_create([Space(bk_biz_id=biz, bk_tenant_id=tenant, space_uid=f"bkcc__{biz}")])
            ArchiveConfig.objects.bulk_create([ArchiveConfig(archive_config_id=biz, instance_id=biz, bk_biz_id=biz)])
            RestoreConfig.objects.bulk_create(
                [
                    RestoreConfig(
                        bk_biz_id=biz,
                        archive_config_id=biz,
                        start_time=timezone.now(),
                        end_time=timezone.now(),
                        expired_time=timezone.now(),
                        meta_restore_id=66,
                    )
                ]
            )
        with patch.object(archive, "get_request_tenant_id", return_value="system"):
            for name in archive.HANDLERS:
                handler = partial(AdminResourceRegistry.call, name, app_code="unit-test")

                result = handler({})
                assert result["total"] == 1 and result["items"][0]["bk_biz_id"] == 7
                assert handler({"archive_config_id": 9})["items"] == []
                assert handler({"page": 2, "page_size": 1})["items"] == []
                with pytest.raises(ValidationError):
                    handler({"page_size": 101})
    connection.close()
