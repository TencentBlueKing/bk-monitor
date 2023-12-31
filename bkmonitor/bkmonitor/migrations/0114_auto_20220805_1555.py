# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2022-08-05 07:55
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bkmonitor", "0113_migrate_event_plugin"),
    ]

    operations = [
        migrations.AddField(
            model_name="apiauthtoken",
            name="expire_time",
            field=models.DateTimeField(default=None, null=True, verbose_name="过期时间"),
        ),
        migrations.AddField(
            model_name="apiauthtoken",
            name="params",
            field=models.JSONField(default=dict, verbose_name="鉴权参数"),
        ),
        migrations.AlterField(
            model_name="apiauthtoken",
            name="type",
            field=models.CharField(
                choices=[
                    ("as_code", "AsCode"),
                    ("grafana", "Grafana"),
                    ("uptime_check", "UptimeCheck"),
                    ("host", "Host"),
                    ("collect", "Collect"),
                    ("custom_metric", "CustomMetric"),
                    ("custom_event", "CustomEvent"),
                    ("kubernetes", "Kubernetes"),
                    ("event", "Event"),
                    ("dashboard", "Dashboard"),
                    ("apm_application", "ApmApplication"),
                ],
                max_length=32,
                verbose_name="鉴权类型",
            ),
        ),
    ]
