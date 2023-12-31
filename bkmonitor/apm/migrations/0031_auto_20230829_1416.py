# Generated by Django 3.2.15 on 2023-08-29 06:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("apm", "0030_auto_20230816_1651"),
    ]

    operations = [
        migrations.AlterField(
            model_name="normaltypevalueconfig",
            name="type",
            field=models.CharField(
                choices=[
                    ("metrics_batch_size", "每批Metric发送大小"),
                    ("traces_batch_size", "每批Trace发送大小"),
                    ("logs_batch_size", "每批Log发送大小"),
                    ("db_slow_command_config", "db slow command config"),
                    ("db_config", "db config"),
                ],
                max_length=32,
                verbose_name="配置类型",
            ),
        ),
        migrations.AlterField(
            model_name="normaltypevalueconfig",
            name="value",
            field=models.TextField(verbose_name="配置值"),
        ),
    ]
