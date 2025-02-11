from django.db import connections, migrations


def truncate_table(apps, schema_editor):
    target_tables = [
        # 以 "labels" 结尾的表名
        "bkmonitor_bcsclusterlabels",
        "bkmonitor_bcscontainerlabels",
        "bkmonitor_bcsnodelabels",
        "bkmonitor_bcspodlabels",
        "bkmonitor_bcspodmonitorlabels",
        "bkmonitor_bcsservicelabels",
        "bkmonitor_bcsservicemonitorlabels",
        "bkmonitor_bcsworkloadlabels",
        # 其他表名
        "bkmonitor_bcscluster",
        "bkmonitor_bcscontainer",
        "bkmonitor_bcslabel",
        "bkmonitor_bcsnode",
        "bkmonitor_bcspod",
        "bkmonitor_bcspodmonitor",
        "bkmonitor_bcsservice",
        "bkmonitor_bcsservicemonitor",
        "bkmonitor_bcsworkload",
    ]
    connection = connections["monitor_api"]
    with connection.cursor() as cursor:
        for table_name in target_tables:
            print(f"Truncating table: {table_name}")
            cursor.execute(f"TRUNCATE TABLE {table_name};")


class Migration(migrations.Migration):
    dependencies = [
        ('bkmonitor', '0172_add_default_usergroup'),
    ]

    operations = [
        migrations.RunPython(truncate_table),
    ]
