from django.db import migrations


def migrate_doris_tag_to_inner(apps, schema_editor):
    IndexSetTag = apps.get_model("log_search", "IndexSetTag")
    IndexSetTag.objects.filter(
        name="Doris",
        value="",
        space_uid="",
        tag_type="user",
    ).update(tag_type="inner")


class Migration(migrations.Migration):
    dependencies = [
        ("log_search", "0097_indexsettag_space_uid"),
    ]

    operations = [
        migrations.RunPython(migrate_doris_tag_to_inner, migrations.RunPython.noop),
    ]
