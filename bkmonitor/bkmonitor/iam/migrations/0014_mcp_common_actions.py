from iam.contrib.iam_migration.migrator import IAMMigrator

from bkmonitor.migrate import BaseMigration


def add_mcp_common_actions(*args, **kwargs):
    # 将 MCP 权限（不含运营数据 MCP）加入「业务运维」推荐权限组
    IAMMigrator("0014_mcp_common_actions.json").migrate()


class Migration(BaseMigration):
    dependencies = ["0013_alarm_handling_mcp"]
    operations = [add_mcp_common_actions]
