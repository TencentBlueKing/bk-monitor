from iam.contrib.iam_migration.migrator import IAMMigrator
from bkmonitor.migrate import BaseMigration


def add_uptime_check_node_permission(*args, **kwargs):
    # 新增拨测节点权限
    IAMMigrator("0004_uptime_check_node.json").migrate()


class Migration(BaseMigration):
    dependencies = ["0003_initial"]
    operations = [add_uptime_check_node_permission]
