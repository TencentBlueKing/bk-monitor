# Generated manually for RenderImageTask upload path

from django.db import migrations, models

import bkmonitor.models.report


class Migration(migrations.Migration):
    dependencies = [
        ("bkmonitor", "0194_add_strategy_issue_config"),
    ]

    operations = [
        migrations.AlterField(
            model_name="renderimagetask",
            name="image",
            field=models.ImageField(
                null=True,
                upload_to=bkmonitor.models.report.get_render_image_upload_path,
                verbose_name="图片",
            ),
        ),
    ]
