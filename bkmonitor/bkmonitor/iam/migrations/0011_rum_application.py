from iam.contrib.iam_migration.migrator import IAMMigrator
from bkmonitor.migrate import BaseMigration


def add_rum_permission(*args, **kwargs):
    # 新增 RUM 应用权限
    IAMMigrator("0011_rum_application.json").migrate()


class Migration(BaseMigration):
    dependencies = ["0010_apm_mcp"]
    operations = [add_rum_permission]
