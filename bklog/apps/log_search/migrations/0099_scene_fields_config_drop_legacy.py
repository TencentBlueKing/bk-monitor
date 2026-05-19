# Generated for scene_search fields config legacy field cleanup

import apps.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("log_search", "0098_scene_fields_config_template"),
    ]

    operations = [
        migrations.AlterField(
            model_name="userscenefieldsconfig",
            name="config_id",
            field=models.IntegerField(db_index=True, verbose_name="场景字段配置ID"),
        ),
        migrations.RemoveField(
            model_name="userscenefieldsconfig",
            name="display_fields",
        ),
        migrations.RemoveField(
            model_name="userscenefieldsconfig",
            name="sort_list",
        ),
    ]
