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

from apps.log_search.handlers.index_set import IndexSetHandler


def add_bcs_tag(apps, schema_editor):
    IndexSetTag = apps.get_model("log_search", "IndexSetTag")
    CollectorConfig = apps.get_model("log_databus", "CollectorConfig")
    collect_configs = list(CollectorConfig.objects.filter(bk_app_code="bk_bcs"))
    for config in collect_configs:
        bcs_cluster_id = config.bcs_cluster_id
        tag_id = IndexSetTag.get_tag_id(bcs_cluster_id)
        try:
            IndexSetHandler(config.index_set_id).add_tag(tag_id=tag_id)
            print(f"add tag[{bcs_cluster_id}] to index[{config.collector_config_name_en}] success.")
        except Exception as e:
            print(f"add tag[{bcs_cluster_id}] to index[{config.collector_config_name_en}] failed: {e}")


class Migration(migrations.Migration):
    dependencies = [
        ("log_search", "0075_logindexset_result_window"),
    ]

    operations = [migrations.RunPython(add_bcs_tag)]
