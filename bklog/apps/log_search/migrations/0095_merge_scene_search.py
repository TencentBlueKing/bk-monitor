"""Merge migration joining the master lineage (0094_migrate_index_set_to_group)
with the scene_search lineage (0094_scene_search, squashed from 0094~0102).
No schema operations; only reconciles the two migration graph leaves.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("log_search", "0094_migrate_index_set_to_group"),
        ("log_search", "0094_scene_search"),
    ]

    operations = []
