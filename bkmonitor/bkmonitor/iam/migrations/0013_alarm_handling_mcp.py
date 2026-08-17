from iam.contrib.iam_migration.migrator import IAMMigrator

from bkmonitor.migrate import BaseMigration


def add_alarm_handling_mcp_permission(*args, **kwargs):
    # 新增告警处置 MCP 权限
    IAMMigrator("0013_alarm_handling_mcp.json").migrate()


class Migration(BaseMigration):
    dependencies = ["0012_rum_application"]
    operations = [add_alarm_handling_mcp_permission]
