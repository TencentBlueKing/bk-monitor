# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


from django.db import migrations


update_sql = """
UPDATE `app_snapshot_host_index` set description='读次数', conversion_unit='iops' where id=86;
UPDATE `app_snapshot_host_index` set description='写次数', conversion_unit='iops' where id=87;
UPDATE `app_snapshot_host_index` set conversion_unit='pps' where id=16 or id=20;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("bkmonitor", "0016_auto_20200825_1206"),
    ]

    operations = [migrations.RunSQL(update_sql)]
