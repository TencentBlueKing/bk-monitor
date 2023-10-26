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


def change_label_and_field_name(apps, schema_editor):
    Label = apps.get_model("metadata", "Label")
    ResultTable = apps.get_model("metadata", "ResultTable")
    ResultTableField = apps.get_model("metadata", "ResultTableField")

    Label.objects.filter(
        label_id="applications",
        label_type="result_table_label",
    ).update(label_name="用户体验")

    tags = ["dimension", "group"]
    ResultTableField.objects.filter(
        field_name="bk_target_cloud_id",
        tag__in=tags,
    ).update(description="云区域ID")

    ResultTableField.objects.filter(
        field_name="bk_cloud_id",
        tag__in=tags,
    ).update(description="采集器云区域ID")

    ResultTableField.objects.filter(
        field_name="ip",
        tag__in=tags,
    ).update(description="采集器IP")

    ResultTableField.objects.filter(
        field_name="bk_target_service_instance_id",
        tag__in=tags,
    ).update(description="服务实例")

    ResultTableField.objects.filter(
        field_name="bk_target_service_category_id",
        tag__in=tags,
    ).update(description="服务类别ID")

    ResultTableField.objects.filter(
        field_name="bk_target_topo_level",
        tag__in=tags,
    ).update(description="拓扑层级")

    ResultTableField.objects.filter(
        field_name="bk_target_topo_id",
        tag__in=tags,
    ).update(description="拓扑ID")

    ResultTable.objects.filter(table_id="uptimecheck.http").update(table_name_zh="HTTP")
    ResultTable.objects.filter(table_id="uptimecheck.tcp").update(table_name_zh="TCP")
    ResultTable.objects.filter(table_id="uptimecheck.udp").update(table_name_zh="UDP")
    ResultTable.objects.filter(table_id="uptimecheck.heartbeat").update(table_name_zh="HeartBeat")


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0049_merge"),
    ]

    operations = [migrations.RunPython(change_label_and_field_name)]
