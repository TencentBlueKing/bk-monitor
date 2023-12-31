# Generated by Django 3.2.15 on 2023-11-06 07:37

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='DeepflowWorkload',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('bk_biz_id', models.IntegerField(verbose_name='业务id')),
                ('cluster_id', models.CharField(max_length=128, verbose_name='集群ID')),
                ('namespace', models.CharField(max_length=255, verbose_name='命名空间')),
                ('name', models.CharField(max_length=255, verbose_name='名称')),
                ('content', models.JSONField(verbose_name='特定配置内容')),
                (
                    'type',
                    models.CharField(
                        choices=[('deployment', 'deployment'), ('service', 'service')],
                        max_length=32,
                        verbose_name='workload类型',
                    ),
                ),
                ('is_normal', models.BooleanField(verbose_name='是否正常')),
                ('last_check_time', models.DateTimeField(verbose_name='最近检查日期')),
                ('create_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('update_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': 'deepflow集群管理表',
            },
        ),
    ]
