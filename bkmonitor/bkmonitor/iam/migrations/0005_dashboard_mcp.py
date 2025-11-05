from iam.contrib.iam_migration.migrator import IAMMigrator
from bkmonitor.migrate import BaseMigration


def add_dashboard_mcp_permission(*args, **kwargs):
    # 新增仪表盘MCP权限
    IAMMigrator("0005_dashboard_mcp.json").migrate()


class Migration(BaseMigration):
    dependencies = ["0004_uptime_check_node"]
    operations = [add_dashboard_mcp_permission]
