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
from django.contrib import admin

from apm import models


def register(model, search_fields=None, list_filter=None):
    if not search_fields:
        search_fields = ("bk_biz_id", "app_name")
    if not list_filter:
        list_filter = ("bk_biz_id", "app_name")

    clz = type(
        f"{model.__name__}Admin",
        (admin.ModelAdmin,),
        {"list_display": all_fields(model), "search_fields": search_fields, "list_filter": list_filter},
    )

    admin.site.register(model, clz)


def all_fields(model):
    return [field.name for field in model._meta.get_fields()]


register(models.ApmApplication, ("bk_biz_id", "app_name", "app_alias"), ("bk_biz_id", "app_name"))
register(
    models.RootEndpoint,
    ("bk_biz_id", "app_name", "endpoint_name", "service_name", "category_id"),
    ("bk_biz_id", "app_name"),
)
register(
    models.Endpoint,
    ("bk_biz_id", "app_name", "endpoint_name", "service_name", "category_id", "span_kind"),
    ("bk_biz_id", "app_name"),
)
register(models.TopoNode, ("bk_biz_id", "app_name", "topo_key"), ("bk_biz_id", "app_name"))
register(models.TopoInstance, ("bk_biz_id", "app_name", "instance_id", "topo_node_key"), ("bk_biz_id", "app_name"))
register(
    models.TopoRelation, ("bk_biz_id", "app_name", "from_topo_key", "to_topo_key", "kind"), ("bk_biz_id", "app_name")
)
register(
    models.HostInstance, ("bk_biz_id", "app_name", "bk_cloud_id", "ip", "topo_node_key"), ("bk_biz_id", "app_name")
)
register(
    models.RemoteServiceRelation,
    ("bk_biz_id", "app_name", "from_endpoint_name", "category", "topo_node_key"),
    ("bk_biz_id", "app_name"),
)
register(models.TraceDataSource)
register(models.MetricDataSource)
register(models.ProfileDataSource)
register(models.ApmTopoDiscoverRule)
register(models.DataLink, ("bk_biz_id",), ("bk_biz_id",))
register(models.ApmInstanceDiscover)
register(models.ApmMetricDimension)
register(models.ApdexConfig)
register(models.SamplerConfig)
register(models.CustomServiceConfig)
register(models.QpsConfig)
register(models.NormalTypeValueConfig)
register(models.ProbeConfig)
register(models.DbConfig)
register(models.SubscriptionConfig)
register(models.ProfileService)
register(models.BkdataFlowConfig)
