# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


def fix_metric_id(apps, *args, **kwargs):
    """
    修复日志平台相关指标
    """
    QueryConfigModel = apps.get_model("bkmonitor", "QueryConfigModel")
    # 修复关键字
    records = QueryConfigModel.objects.filter(data_source_label="bk_log_search", data_type_label="log")
    for record in records:
        metric_id = f"bk_log_search.index_set.{record.config['index_set_id']}"
        if record.metric_id != metric_id:
            print(f"fix strategy({record.strategy_id}) metric_id: {record.metric_id} -> {metric_id}")
            record.metric_id = metric_id
            record.save()
    # 修复时序指标
    records = QueryConfigModel.objects.filter(data_source_label="bk_log_search", data_type_label="time_series")
    for record in records:
        metric_id = f"bk_log_search.index_set.{record.config['index_set_id']}.{record.config['metric_field']}"
        if record.metric_id != metric_id:
            print(f"fix strategy({record.strategy_id}) metric_id: {record.metric_id} -> {metric_id}")
            record.metric_id = metric_id
            record.save()


class Migration(migrations.Migration):

    dependencies = [
        ("bkmonitor", "0050_merge_20211207_1140"),
    ]

    operations = [migrations.RunPython(fix_metric_id)]
