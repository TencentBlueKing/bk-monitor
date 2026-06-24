from iam.contrib.iam_migration.migrator import IAMMigrator

from bkmonitor.migrate import BaseMigration


def add_operation_mcp_permission(*args, **kwargs):
    # 新增运营数据 MCP 权限
    IAMMigrator("0011_operation_mcp.json").migrate()


class Migration(BaseMigration):
    dependencies = ["0010_apm_mcp"]
    operations = [add_operation_mcp_permission]
