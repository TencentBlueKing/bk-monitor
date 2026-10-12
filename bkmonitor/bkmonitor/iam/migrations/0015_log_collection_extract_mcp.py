from iam.contrib.iam_migration.migrator import IAMMigrator

from bkmonitor.migrate import BaseMigration


def add_log_collection_extract_mcp_permissions(*args, **kwargs):
    # 日志采集和日志提取使用独立的 MCP 权限；日志查询仍使用 using_log_mcp。
    IAMMigrator("0015_log_collection_extract_mcp.json").migrate()


class Migration(BaseMigration):
    dependencies = ["0014_mcp_common_actions"]
    operations = [add_log_collection_extract_mcp_permissions]
