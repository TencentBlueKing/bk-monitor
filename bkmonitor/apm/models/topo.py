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
import datetime

from django.db import models

from bkmonitor.utils.db import JsonField
from constants.apm import SpanKind


class TopoBase(models.Model):
    TOPO_NODE = "topo_node"
    TOPO_RELATION = "topo_relation"
    TOPO_INSTANCE = "topo_instance"

    bk_biz_id = models.IntegerField("业务id")
    app_name = models.CharField("应用名称", max_length=128)
    created_at = models.DateTimeField("创建时间", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("更新时间", blank=True, null=True, auto_now=True, db_index=True)
    extra_data = JsonField("额外数据")

    class Meta:
        abstract = True
        index_together = ["bk_biz_id", "app_name"]

    @classmethod
    def clear_expired(cls, bk_biz_id, app_name):
        from apm.models import ApmApplication

        application = ApmApplication.get_application(bk_biz_id, app_name)
        last = datetime.datetime.now() - datetime.timedelta(application.trace_datasource.retention)
        filter_params = {
            "bk_biz_id": bk_biz_id,
            "app_name": app_name,
            "updated_at__gte": last,
        }

        cls.objects.filter(**filter_params).delete()


class TopoNode(TopoBase):
    # extra_data会存储category类型
    # 如果这个Node是http类型，那么在extra_data数据：
    # {"category":"http","kind":"service","predicate_value":"POST","service_language":"python","instance":{}}
    topo_key = models.CharField("节点key", max_length=255, db_index=True)


class TopoRelation(TopoBase):
    # 这个数据表是表达TopoNode表的关系
    RELATION_KIND_SYNC = "sync"
    RELATION_KIND_ASYNC = "async"

    KIND_MAPPING = {
        SpanKind.SPAN_KIND_CLIENT: RELATION_KIND_SYNC,
        SpanKind.SPAN_KIND_SERVER: RELATION_KIND_SYNC,
        SpanKind.SPAN_KIND_PRODUCER: RELATION_KIND_ASYNC,
        SpanKind.SPAN_KIND_CONSUMER: RELATION_KIND_ASYNC,
    }

    from_topo_key = models.CharField("topo节点key", max_length=255)
    to_topo_key = models.CharField("topo_key", max_length=255)
    kind = models.CharField("关系类型", max_length=50)
    to_topo_key_kind = models.CharField("目标节点类型", max_length=255)
    to_topo_key_category = models.CharField("目标节点分类", max_length=255)


class TopoInstance(TopoBase):
    instance_id = models.CharField("实例id", max_length=255)
    instance_topo_kind = models.CharField("实例类型", max_length=255)
    component_instance_category = models.CharField("组件实例分类(service类型下为空)", max_length=255, null=True)
    component_instance_predicate_value = models.CharField("组件实例类型(service类型下为空)", max_length=255, null=True)
    topo_node_key = models.CharField("实例所属key", max_length=255)
    sdk_name = models.CharField("探针类型", max_length=255, null=True)
    sdk_version = models.CharField("探针版本", max_length=255, null=True)
    sdk_language = models.CharField("探针语言", max_length=255, null=True)


class HostInstance(TopoBase):
    bk_cloud_id = models.IntegerField(null=True, verbose_name="云区域id")
    ip = models.CharField(max_length=1024, verbose_name="ipv4地址")
    bk_host_id = models.IntegerField(null=True, verbose_name="主机ID")
    topo_node_key = models.CharField("实例所属key", max_length=255)


class RemoteServiceRelation(TopoBase):
    topo_node_key = models.CharField("实例所属key", max_length=255)
    from_endpoint_name = models.CharField("接口名称", max_length=2048)
    category = models.CharField("分类名称", max_length=128)
