"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging

from django.db.models import Q, Model
from django.db import migrations

from constants.apm import DEFAULT_DATA_LABEL, APM_METRIC_TABLE_REGEX

logger = logging.getLogger("metadata")

models: dict[str, type[Model] | None] = {"ResultTable": None}


def add_data_label_to_apm_metric_rt(apps, schema_editor):
    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("metadata", model_name)

    rts = models["ResultTable"].objects.filter(
        Q(table_id__contains="bkapm_") & Q(table_id__contains="metric_") & Q(data_label="")
    )

    to_be_updated_rts = []
    for rt in rts:
        if APM_METRIC_TABLE_REGEX.match(rt.table_id) is not None:
            rt.data_label = DEFAULT_DATA_LABEL
            to_be_updated_rts.append(rt)

    models["ResultTable"].objects.bulk_update(to_be_updated_rts, fields=["data_label"], batch_size=1000)
    logger.info(
        "[add_data_label_to_apm_metric_rt] add data_label -> %s, rows -> %s.",
        DEFAULT_DATA_LABEL,
        len(to_be_updated_rts),
    )


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0236_auto_20250807_2145"),
    ]

    operations = [migrations.RunPython(code=add_data_label_to_apm_metric_rt)]
