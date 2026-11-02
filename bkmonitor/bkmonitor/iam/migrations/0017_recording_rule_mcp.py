from iam.contrib.iam_migration.migrator import IAMMigrator

from bkmonitor.migrate import BaseMigration


def register_recording_rule_mcp(*args, **kwargs):
    IAMMigrator("0017_recording_rule_mcp.json").migrate()


class Migration(BaseMigration):
    dependencies = ["0016_correct_action_groups"]
    operations = [register_recording_rule_mcp]
