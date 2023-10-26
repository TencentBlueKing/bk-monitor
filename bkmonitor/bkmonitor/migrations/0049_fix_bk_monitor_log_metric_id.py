# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


def fix_metric_id(apps, *args, **kwargs):
    """
    修复监控采集日志关键字指标
    """
    QueryConfigModel = apps.get_model("bkmonitor", "QueryConfigModel")
    records = QueryConfigModel.objects.filter(data_source_label="bk_monitor", data_type_label="log")
    for record in records:
        metric_id = f"bk_monitor.log.{record.config['result_table_id']}"
        if record.metric_id != metric_id:
            record.metric_id = metric_id
            record.save()


class Migration(migrations.Migration):

    dependencies = [
        ("bkmonitor", "0048_auto_20211021_1500"),
    ]

    operations = [migrations.RunPython(fix_metric_id)]
