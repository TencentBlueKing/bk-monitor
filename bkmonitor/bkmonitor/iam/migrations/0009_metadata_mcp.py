from iam.contrib.iam_migration.migrator import IAMMigrator
from bkmonitor.migrate import BaseMigration


def add_metadata_mcp_permission(*args, **kwargs):
    # 新增元数据MCP权限
    IAMMigrator("0009_metadata_mcp.json").migrate()


class Migration(BaseMigration):
    dependencies = ["0008_log_alarm_mcp"]
    operations = [add_metadata_mcp_permission]
