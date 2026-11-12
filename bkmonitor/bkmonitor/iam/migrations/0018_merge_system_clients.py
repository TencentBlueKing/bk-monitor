from django.conf import settings
from iam.api.client import Client
from iam.contrib.iam_migration.exceptions import MigrationFailError
from iam.contrib.iam_migration.migrator import IAMMigrator

from bkmonitor.iam.backends.config import get_system_clients
from bkmonitor.migrate import BaseMigration


def merge_system_clients(*args, **kwargs):
    # upsert_system 会整体覆盖 clients，这里只追加缺失项，保留各环境在 IAM 侧已有的调用方
    if getattr(settings, "BK_IAM_SKIP", False):
        return
    system_id = settings.BK_IAM_SYSTEM_ID
    client = Client(settings.APP_CODE, settings.SECRET_KEY, settings.BK_IAM_APIGATEWAY_URL, IAMMigrator.get_tenant_id())
    ok, message, data = client.query(system_id)
    if not ok:
        raise MigrationFailError(f"query iam system {system_id} failed: {message}")
    actual = [item for item in data["base_info"]["clients"].split(",") if item]
    clients = list(dict.fromkeys([*actual, *get_system_clients()]))
    if clients == actual:
        return
    ok, message = client.update_system(system_id, {"clients": ",".join(clients)})
    if not ok:
        raise MigrationFailError(f"update iam system {system_id} clients failed: {message}")


class Migration(BaseMigration):
    dependencies = ["0017_recording_rule_mcp"]
    operations = [merge_system_clients]
