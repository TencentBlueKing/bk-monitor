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


from django.db import migrations

init_sql = """
INSERT INTO `dict_base_alarm` VALUES 
(10,9,'oom-gse','OOM异常事件告警',1);
"""


class Migration(migrations.Migration):
    dependencies = [
        ("bkmonitor", "0021_merge_20200916_1514"),
    ]

    operations = [migrations.RunSQL(init_sql)]
