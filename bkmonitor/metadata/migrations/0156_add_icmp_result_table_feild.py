from django.db import migrations
from monitor_web.uptime_check.constants import NODE_ID_FIELD


def add_icmp_field_record(apps, schema_editor):
    field_model = apps.get_model('metadata', 'ResultTableField')
    field_model.objects.create(**NODE_ID_FIELD)


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0155_accessvmrecord"),
    ]

    operations = [migrations.RunPython(add_icmp_field_record)]
