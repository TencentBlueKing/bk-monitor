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
from django.db.models import Count, Min


def fix_duplicate_detects(apps, *args, **kwargs):
    """
    处理冗余重复detects模型数据
    """
    DetectModel = apps.get_model("bkmonitor", "DetectModel")
    # 冗余Detect记录
    detects_info = (
        DetectModel.objects.values("strategy_id", "level")
        .annotate(dcount=Count("id"), detect_id=Min("id"))
        .order_by("-dcount")
    )
    cnt = 0
    to_be_update_ids = []
    for row in detects_info:
        dcount = row["dcount"]
        if dcount == 1:
            print(f"fix_duplicate_detects total {cnt} done")
            break
        to_be_update_ids.append(row["detect_id"])
        strategy_id = row["strategy_id"]
        level = row["level"]
        # 删除冗余detects
        DetectModel.objects.filter(strategy_id=strategy_id, level=level).exclude(id=row["detect_id"]).delete()
        print(f"clean strategy({strategy_id}-{level})")
        cnt += 1
    # 批量更新唯一剩余的detect的connector属性未AND
    DetectModel.objects.filter(id__in=to_be_update_ids).update(connector="and")


class Migration(migrations.Migration):

    dependencies = [
        ("bkmonitor", "0034_auto_20210419_1732"),
    ]

    operations = [
        migrations.RunPython(fix_duplicate_detects),
    ]
