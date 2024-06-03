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
# -*- coding: utf-8 -*-
from django.db import migrations

from apps.log_search.constants import InnerTag


def add_bcs_tag(apps, schema_editor):
    IndexSetTag = apps.get_model("log_search", "IndexSetTag")
    LogIndexSet = apps.get_model("log_search", "LogIndexSet")
    CollectorConfig = apps.get_model("log_databus", "CollectorConfig")
    collect_configs = list(CollectorConfig.objects.filter(bk_app_code__in=["bk_bcs", "bk_bcs_app"]))
    for config in collect_configs:
        bcs_cluster_id = config.bcs_cluster_id
        try:
            # 校验标签是否已存在，创建或获取标签ID
            tag, _ = IndexSetTag.objects.get_or_create(name=bcs_cluster_id)
            tag_id = tag.tag_id

            index_set_obj = LogIndexSet.objects.get(index_set_id=config.index_set_id)
            tag_ids = list(index_set_obj.tag_ids)

            # 若标签已存在，则不重复添加
            if str(tag_id) not in tag_ids:
                tag_ids.append(str(tag_id))
                index_set_obj.tag_ids = tag_ids
                index_set_obj.save()
                print(f"add tag[{bcs_cluster_id}] to index[{config.collector_config_name_en}] success.")
            else:
                print(f"index[{config.collector_config_name_en}] - tag[{bcs_cluster_id}] already exist.")
        except Exception as e:
            print(f"add tag[{bcs_cluster_id}] to index[{config.collector_config_name_en}] failed: {e}")


class Migration(migrations.Migration):
    dependencies = [
        ("log_search", "0075_logindexset_result_window"),
    ]

    operations = [migrations.RunPython(add_bcs_tag)]
