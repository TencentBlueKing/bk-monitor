# Generated by Django 3.2.15 on 2023-08-09 12:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('log_clustering', '0019_auto_20230523_2122'),
    ]

    operations = [
        migrations.AddField(
            model_name='clusteringconfig',
            name='online_task_id',
            field=models.IntegerField(blank=True, null=True, verbose_name='在线任务id'),
        ),
        migrations.AddField(
            model_name='clusteringconfig',
            name='predict_flow',
            field=models.JSONField(blank=True, null=True, verbose_name='predict_flow配置'),
        ),
        migrations.AddField(
            model_name='clusteringconfig',
            name='predict_flow_id',
            field=models.IntegerField(blank=True, null=True, verbose_name='预测flow_id'),
        ),
    ]
