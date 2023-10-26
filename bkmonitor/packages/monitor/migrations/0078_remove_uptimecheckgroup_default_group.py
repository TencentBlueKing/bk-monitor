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


from django.db import migrations, models


def remove_default_group(apps, schema_editor):
    """
    删除默认"未分类"拨测任务组，因为拨测任务组解除业务ID限制后会导致多个在不同业务的"未分类"任务组同时显示
    """
    UptimeCheckGroup = apps.get_model("monitor", "UptimeCheckGroup")
    groups = UptimeCheckGroup.objects.filter(is_deleted=False, name="未分类")
    groups.update(is_deleted=True)


class Migration(migrations.Migration):
    dependencies = [
        ("monitor", "0077_remove_uptimecheckgroup_bk_biz_id"),
    ]

    operations = [migrations.RunPython(remove_default_group)]
