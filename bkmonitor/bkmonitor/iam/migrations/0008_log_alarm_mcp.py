from iam.contrib.iam_migration.migrator import IAMMigrator
from bkmonitor.migrate import BaseMigration


def add_log_alarm_mcp_permission(*args, **kwargs):
    # 新增日志MCP和告警MCP权限
    IAMMigrator("0008_log_alarm_mcp.json").migrate()


class Migration(BaseMigration):
    dependencies = ["0007_metrics_mcp"]
    operations = [add_log_alarm_mcp_permission]

