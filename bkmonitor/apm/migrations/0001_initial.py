# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
# Generated by Django 1.11.23 on 2022-03-21 07:22
from __future__ import unicode_literals

from django.db import migrations, models

import bkmonitor.utils.db.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ApmApplication",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="是否删除")),
                ("create_user", models.CharField(blank=True, default="", max_length=32, verbose_name="创建人")),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("update_user", models.CharField(blank=True, default="", max_length=32, verbose_name="最后修改人")),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="最后修改时间")),
                ("bk_biz_id", models.IntegerField(verbose_name="业务id")),
                ("app_name", models.CharField(max_length=50, verbose_name="应用名称")),
                ("app_alias", models.CharField(max_length=128, verbose_name="应用别名")),
                ("description", models.CharField(max_length=255, verbose_name="应用描述")),
                ("is_enabled", models.BooleanField(default=True, verbose_name="是否启用")),
            ],
        ),
        migrations.CreateModel(
            name="ApmInstanceDiscover",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bk_biz_id", models.IntegerField(verbose_name="业务id")),
                ("app_name", models.CharField(max_length=255, verbose_name="应用名称")),
                ("discover_key", models.CharField(max_length=255, unique=True, verbose_name="应用名称")),
                ("rank", models.IntegerField(verbose_name="rank")),
            ],
            options={
                "ordering": ["rank", "discover_key"],
            },
        ),
        migrations.CreateModel(
            name="ApmMetricDimension",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bk_biz_id", models.IntegerField(verbose_name="业务id")),
                ("app_name", models.CharField(max_length=128, verbose_name="应用名称")),
                ("span_kind", models.CharField(max_length=50, verbose_name="提取kind")),
                ("predicate_key", models.CharField(max_length=128, verbose_name="判断字段")),
                ("dimension_key", models.CharField(max_length=128, verbose_name="维度字段名称")),
            ],
        ),
        migrations.CreateModel(
            name="ApmTopoDiscoverRule",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bk_biz_id", models.IntegerField(verbose_name="业务id")),
                ("app_name", models.CharField(max_length=128, verbose_name="应用名称")),
                ("category_id", models.CharField(max_length=128, verbose_name="分类名称")),
                ("endpoint_key", models.CharField(max_length=255, verbose_name="接口字段")),
                ("instance_key", models.CharField(max_length=255, verbose_name="实例字段")),
                ("topo_kind", models.CharField(max_length=50, verbose_name="topo发现类型")),
                ("predicate_key", models.CharField(max_length=128, verbose_name="判断字段")),
            ],
        ),
        migrations.CreateModel(
            name="DataLink",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bk_biz_id", models.IntegerField(verbose_name="业务id")),
                (
                    "trace_transfer_cluster_id",
                    models.CharField(default="", max_length=128, verbose_name="Trace Es Transfer集群id"),
                ),
                (
                    "metric_transfer_cluster_id",
                    models.CharField(default="", max_length=128, verbose_name="Metric Transfer集群id"),
                ),
                ("kafka_cluster_id", models.IntegerField(verbose_name="kafka集群id")),
            ],
        ),
        migrations.CreateModel(
            name="Endpoint",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("bk_biz_id", models.IntegerField(verbose_name="业务id")),
                ("app_name", models.CharField(max_length=50, verbose_name="应用名称")),
                ("endpoint_name", models.CharField(max_length=2048, verbose_name="接口")),
                ("service_name", models.CharField(max_length=2048, verbose_name="服务名称")),
                ("category_id", models.CharField(max_length=128, verbose_name="分类名称")),
                ("category_kind_key", models.CharField(max_length=255, verbose_name="分类类型key")),
                ("category_kind_value", models.CharField(max_length=255, verbose_name="分类类型值")),
                ("span_kind", models.IntegerField(default=0, verbose_name="跟踪类型")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, db_index=True, null=True, verbose_name="更新时间")),
            ],
        ),
        migrations.CreateModel(
            name="MetricDataSource",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bk_biz_id", models.IntegerField(verbose_name="业务id")),
                ("app_name", models.CharField(max_length=255, verbose_name="所属应用")),
                ("bk_data_id", models.IntegerField(default=-1, verbose_name="数据id")),
                ("result_table_id", models.CharField(default="", max_length=128, verbose_name="结果表id")),
                ("time_series_group_id", models.IntegerField(default=0, verbose_name="时序分组ID")),
                ("data_label", models.CharField(default="", max_length=128, verbose_name="数据标签")),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="RemoteServiceDiscover",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bk_biz_id", models.IntegerField(verbose_name="业务id")),
                ("app_name", models.CharField(max_length=128, verbose_name="应用名称")),
                ("span_kind", models.CharField(max_length=50, verbose_name="提取kind")),
                ("predicate_key", models.CharField(max_length=128, verbose_name="判断字段")),
                ("match_key", models.CharField(max_length=128, verbose_name="匹配key")),
                ("match_op", models.CharField(max_length=20, verbose_name="匹配操作")),
                ("match_value", models.CharField(max_length=255, verbose_name="匹配值")),
                ("peer_service_name", models.CharField(max_length=128, verbose_name="远程服务名称")),
            ],
        ),
        migrations.CreateModel(
            name="RootEndpoint",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("bk_biz_id", models.IntegerField(verbose_name="业务id")),
                ("app_name", models.CharField(max_length=50, verbose_name="应用名称")),
                ("endpoint_name", models.CharField(max_length=2048, verbose_name="接口")),
                ("service_name", models.CharField(max_length=2048, verbose_name="服务名称")),
                ("category_id", models.CharField(max_length=128, verbose_name="分类名称")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, db_index=True, null=True, verbose_name="更新时间")),
            ],
        ),
        migrations.CreateModel(
            name="TopoInstance",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bk_biz_id", models.IntegerField(verbose_name="业务id")),
                ("app_name", models.CharField(max_length=128, verbose_name="应用名称")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, db_index=True, null=True, verbose_name="更新时间")),
                ("extra_data", bkmonitor.utils.db.fields.JsonField(verbose_name="额外数据")),
                ("instance_id", models.CharField(max_length=255, verbose_name="实例id")),
                ("topo_node_key", models.CharField(max_length=255, verbose_name="实例所属key")),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="TopoNode",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bk_biz_id", models.IntegerField(verbose_name="业务id")),
                ("app_name", models.CharField(max_length=128, verbose_name="应用名称")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, db_index=True, null=True, verbose_name="更新时间")),
                ("extra_data", bkmonitor.utils.db.fields.JsonField(verbose_name="额外数据")),
                ("topo_key", models.CharField(max_length=255, verbose_name="节点key")),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="TopoRelation",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bk_biz_id", models.IntegerField(verbose_name="业务id")),
                ("app_name", models.CharField(max_length=128, verbose_name="应用名称")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, db_index=True, null=True, verbose_name="更新时间")),
                ("extra_data", bkmonitor.utils.db.fields.JsonField(verbose_name="额外数据")),
                ("from_topo_key", models.CharField(max_length=255, verbose_name="topo节点key")),
                ("to_topo_key", models.CharField(max_length=255, verbose_name="topo_key")),
                ("kind", models.CharField(max_length=50, verbose_name="关系类型")),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="TraceDataSource",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("bk_biz_id", models.IntegerField(verbose_name="业务id")),
                ("app_name", models.CharField(max_length=255, verbose_name="所属应用")),
                ("bk_data_id", models.IntegerField(default=-1, verbose_name="数据id")),
                ("result_table_id", models.CharField(default="", max_length=128, verbose_name="结果表id")),
            ],
            options={
                "abstract": False,
            },
        ),
        migrations.AlterIndexTogether(
            name="toporelation",
            index_together={("bk_biz_id", "app_name")},
        ),
        migrations.AlterIndexTogether(
            name="toponode",
            index_together={("bk_biz_id", "app_name")},
        ),
        migrations.AlterIndexTogether(
            name="topoinstance",
            index_together={("bk_biz_id", "app_name")},
        ),
        migrations.AlterUniqueTogether(
            name="apmapplication",
            unique_together={("app_name", "bk_biz_id")},
        ),
    ]
