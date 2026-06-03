"""
Add 'tag_type' field to IndexSetTag, migrate existing data to correct type,
and change unique constraint to (name, value, tag_type).
"""

from django.db import migrations, models

INNER_TAG_NAMES = ["trace", "restoring", "restored", "no_data", "have_delay", "bkdata", "bcs", "clustering"]


def migrate_tag_types(apps, schema_editor):
    """Set tag_type for existing rows: inner tags by name, scene tags by non-empty value."""
    IndexSetTag = apps.get_model("log_search", "IndexSetTag")
    IndexSetTag.objects.filter(name__in=INNER_TAG_NAMES, value="").update(tag_type="inner")
    IndexSetTag.objects.exclude(value="").update(tag_type="scene")


class Migration(migrations.Migration):

    dependencies = [
        ("log_search", "0094_indexsettag_value_and_unique_together"),
    ]

    operations = [
        migrations.AddField(
            model_name="indexsettag",
            name="tag_type",
            field=models.CharField(
                choices=[("user", "用户自定义"), ("inner", "系统内置"), ("scene", "场景维度")],
                db_index=True,
                default="user",
                max_length=16,
                verbose_name="标签类型",
            ),
        ),
        migrations.RunPython(migrate_tag_types, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name="indexsettag",
            unique_together={("name", "value", "tag_type")},
        ),
    ]
