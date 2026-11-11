import importlib
from unittest.mock import patch

import pytest

migration = importlib.import_module("bkmonitor.iam.migrations.0018_merge_system_clients")


@pytest.fixture
def iam_client(settings):
    settings.SAAS_APP_CODE = "bk_monitorv3"
    settings.BK_IAM_SKIP = False
    settings.BK_IAM_SYSTEM_ID = "bk_monitorv3"
    with patch.object(migration, "Client") as client_cls:
        yield client_cls.return_value


def test_appends_missing_clients_and_keeps_remote_ones(iam_client):
    iam_client.query.return_value = (True, "ok", {"base_info": {"clients": "bk_monitorv3,log-search-4"}})
    iam_client.update_system.return_value = (True, "ok")

    migration.merge_system_clients()

    iam_client.update_system.assert_called_once_with(
        "bk_monitorv3", {"clients": "bk_monitorv3,log-search-4,bkci,bk_ms,bk_paas3,paasv3cli"}
    )


def test_skips_update_when_nothing_missing(iam_client):
    clients = "bk_monitorv3,bkci,bk_ms,bk_paas3,paasv3cli,remote-extra"
    iam_client.query.return_value = (True, "ok", {"base_info": {"clients": clients}})

    migration.merge_system_clients()

    iam_client.update_system.assert_not_called()


def test_query_failure_aborts_without_write(iam_client):
    iam_client.query.return_value = (False, "denied", None)

    with pytest.raises(migration.MigrationFailError):
        migration.merge_system_clients()
    iam_client.update_system.assert_not_called()
