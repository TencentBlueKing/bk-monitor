from iam.contrib.iam_migration.migrator import IAMMigrator
from bkmonitor.migrate import BaseMigration


def add_apm_mcp_permission(*args, **kwargs):
    # 新增APM MCP权限
    IAMMigrator("0010_apm_mcp.json").migrate()


class Migration(BaseMigration):
    dependencies = ["0009_metadata_mcp"]
    operations = [add_apm_mcp_permission]
