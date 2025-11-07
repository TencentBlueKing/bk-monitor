from iam.contrib.iam_migration.migrator import IAMMigrator
from bkmonitor.migrate import BaseMigration


def correct_permission_groups(*args, **kwargs):
    # 新增仪表盘MCP权限
    IAMMigrator("0006_correct_groups.json").migrate()


class Migration(BaseMigration):
    dependencies = ["0005_dashboard_mcp"]
    operations = [correct_permission_groups]
