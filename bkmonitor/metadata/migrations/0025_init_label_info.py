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


import logging

from django.db import migrations

logger = logging.getLogger("metadata")

models = {
    "ClusterInfo": None,
    "DataSource": None,
    "ResultTableField": None,
    "ResultTable": None,
    "DataSourceResultTable": None,
    "KafkaTopicInfo": None,
    "InfluxDBStorage": None,
    "Label": None,
}


def init_label_info(apps, schema_editor):
    """增加默认的label信息"""

    # 获取APP models
    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("metadata", model_name)

    Lable = models["Label"]

    # 创建数据源类型标签
    Lable.objects.create(
        label_id="event",
        label_name="内置事件类型",
        label_type="type_label",
        is_admin_only=False,
        parent_label=None,
        level=None,
        index=None,
    )

    Lable.objects.create(
        label_id="log",
        label_name="日志类型",
        label_type="type_label",
        is_admin_only=False,
        parent_label=None,
        level=None,
        index=None,
    )

    Lable.objects.create(
        label_id="time_series",
        label_name="时序数据",
        label_type="type_label",
        is_admin_only=False,
        parent_label=None,
        level=None,
        index=None,
    )

    # 创建数据源来源标签
    Lable.objects.create(
        label_id="bk_data",
        label_name="蓝鲸计算平台",
        label_type="source_label",
        is_admin_only=False,
        parent_label=None,
        level=None,
        index=None,
    )

    Lable.objects.create(
        label_id="bk_monitor",
        label_name="蓝鲸监控",
        label_type="source_label",
        is_admin_only=False,
        parent_label=None,
        level=None,
        index=None,
    )

    Lable.objects.create(
        label_id="custom",
        label_name="用户自定义",
        label_type="source_label",
        is_admin_only=False,
        parent_label=None,
        level=None,
        index=None,
    )

    # 创建结果表标签
    # 一级标签
    Lable.objects.create(
        label_id="applications",
        label_name="应用",
        label_type="result_table_label",
        is_admin_only=False,
        parent_label=None,
        level=1,
        index=1,
    )

    Lable.objects.create(
        label_id="services",
        label_name="服务",
        label_type="result_table_label",
        is_admin_only=False,
        parent_label=None,
        level=1,
        index=2,
    )

    Lable.objects.create(
        label_id="hosts",
        label_name="主机",
        label_type="result_table_label",
        is_admin_only=False,
        parent_label=None,
        level=1,
        index=3,
    )

    Lable.objects.create(
        label_id="others",
        label_name="其他",
        label_type="result_table_label",
        is_admin_only=False,
        parent_label=None,
        level=1,
        index=4,
    )

    # 二级标签
    # 应用
    Lable.objects.create(
        label_id="uptimecheck",
        label_name="服务拨测",
        label_type="result_table_label",
        is_admin_only=True,
        parent_label="applications",
        level=2,
        index=1,
    )

    Lable.objects.create(
        label_id="application_check",
        label_name="业务应用",
        label_type="result_table_label",
        is_admin_only=True,
        parent_label="applications",
        level=2,
        index=2,
    )

    # 服务
    Lable.objects.create(
        label_id="service_module",
        label_name="服务模块",
        label_type="result_table_label",
        is_admin_only=True,
        parent_label="services",
        level=2,
        index=1,
    )

    Lable.objects.create(
        label_id="component",
        label_name="组件",
        label_type="result_table_label",
        is_admin_only=True,
        parent_label="services",
        level=2,
        index=2,
    )

    Lable.objects.create(
        label_id="service_process",
        label_name="进程",
        label_type="result_table_label",
        is_admin_only=True,
        parent_label="services",
        level=2,
        index=3,
    )

    # 主机
    Lable.objects.create(
        label_id="host_process",
        label_name="进程",
        label_type="result_table_label",
        is_admin_only=True,
        parent_label="hosts",
        level=2,
        index=1,
    )

    Lable.objects.create(
        label_id="os",
        label_name="操作系统",
        label_type="result_table_label",
        is_admin_only=True,
        parent_label="hosts",
        level=2,
        index=2,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("metadata", "0024_auto_20190828_1744"),
    ]

    operations = [
        migrations.RunPython(init_label_info),
    ]
