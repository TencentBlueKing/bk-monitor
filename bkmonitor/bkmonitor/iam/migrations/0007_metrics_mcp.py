from iam.contrib.iam_migration.migrator import IAMMigrator
from bkmonitor.migrate import BaseMigration


def add_metrics_mcp_permission(*args, **kwargs):
    # 新增指标MCP权限
    IAMMigrator("0007_metrics_mcp.json").migrate()


class Migration(BaseMigration):
    dependencies = ["0006_correct_groups"]
    operations = [add_metrics_mcp_permission]
