# Data migration: fix legacy FavoriteGroup.name that was written as English literal
# under non-zh locale (e.g. private/unknown). New entries are created with translated
# Chinese names via FavoriteGroup.get_or_create_private_group/_ungrouped_group, while
# the API layer falls back by group_type at read time. This migration only repairs
# legacy rows that still carry the English literal.

from django.db import migrations


def forwards(apps, schema_editor):
    FavoriteGroup = apps.get_model("log_search", "FavoriteGroup")
    FavoriteGroup.objects.filter(group_type="private", name="private").update(name="个人收藏")
    FavoriteGroup.objects.filter(group_type="unknown", name="unknown").update(name="未分组")


def backwards(apps, schema_editor):
    # No-op: the original literal cannot be reliably restored without per-row history.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("log_search", "0101_favoritegroup_source_type"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
