# Generated by Django 3.2.15 on 2023-09-01 05:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('log_desensitize', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='desensitizefieldconfig',
            name='match_pattern',
            field=models.TextField(blank=True, default='', null=True, verbose_name='匹配模式'),
        ),
    ]
