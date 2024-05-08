# -*- coding: utf-8 -*-

from collections import OrderedDict
from functools import reduce
from operator import or_

from django.db import migrations
from django.db.models import Q

REPLACE_RULES = {
    'bk_instance': 'instance',
    'bk_job': 'job',
}


def update_agg_dimension(apps, schema_editor):
    """更新 QueryConfigModel 的 agg_dimension，替换特定值。"""
    QueryConfigModel = apps.get_model('bkmonitor', 'QueryConfigModel')
    conditions = reduce(or_, (Q(config__agg_dimension__contains=d) for d in REPLACE_RULES.keys()))

    for query_config in QueryConfigModel.objects.filter(conditions):
        agg_dimension = query_config.config['agg_dimension']
        new_agg_dimensions = [REPLACE_RULES.get(d, d) for d in agg_dimension]
        new_agg_dimensions = list(OrderedDict.fromkeys(new_agg_dimensions))  # 去重并保证顺序
        for condition in query_config.config.get("agg_condition", []):
            if condition.get("key") in REPLACE_RULES:
                condition["key"] = REPLACE_RULES[condition["key"]]

        query_config.config['agg_dimension'] = new_agg_dimensions
        query_config.save(update_fields=['config'])


class Migration(migrations.Migration):
    dependencies = [
        ('bkmonitor', '0158_auto_20240117_1015'),
    ]

    operations = [
        migrations.RunPython(update_agg_dimension),
    ]
