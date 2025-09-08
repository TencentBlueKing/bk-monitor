# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("monitor_web", "0016_metriclistcache_description"),
    ]

    operations = [
        migrations.AddField(
            model_name="metriclistcache",
            name="category_display",
            field=models.CharField(default="", max_length=128, verbose_name="\u5206\u7c7b\u663e\u793a\u540d"),
        ),
        migrations.AddField(
            model_name="metriclistcache",
            name="collect_interval",
            field=models.IntegerField(default=1, verbose_name="\u6307\u6807\u91c7\u96c6\u5468\u671f"),
        ),
    ]
