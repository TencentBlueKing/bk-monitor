from iam.contrib.iam_migration.migrator import IAMMigrator

from bkmonitor.migrate import BaseMigration


def correct_action_groups(*args, **kwargs):
    IAMMigrator("0016_correct_action_groups.json").migrate()


class Migration(BaseMigration):
    dependencies = ["0015_log_collection_extract_mcp"]
    operations = [correct_action_groups]
