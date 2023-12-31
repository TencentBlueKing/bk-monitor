# Generated by Django 3.2.15 on 2023-11-23 07:48

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('apm', '0031_auto_20230829_1416'),
    ]

    operations = [
        migrations.AlterField(
            model_name='normaltypevalueconfig',
            name='type',
            field=models.CharField(
                choices=[
                    ('metrics_batch_size', '每批Metric发送大小'),
                    ('traces_batch_size', '每批Trace发送大小'),
                    ('logs_batch_size', '每批Log发送大小'),
                    ('db_slow_command_config', 'db慢命令配置'),
                    ('db_config', 'db配置'),
                ],
                max_length=32,
                verbose_name='配置类型',
            ),
        ),
    ]
