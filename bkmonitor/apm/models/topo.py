"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import datetime

from django.db import models
from django.utils.translation import gettext_lazy as _

from apm.constants import DiscoverRuleType
from bkmonitor.utils.cache import CacheType, using_cache
from bkmonitor.utils.db import JsonField
from constants.apm import SpanKind
from core.drf_resource.exceptions import CustomException


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

        application = ApmApplication.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
        if not application:
            raise CustomException(_("业务下的应用: {} 不存在").format(app_name))
        last = datetime.datetime.now() - datetime.timedelta(application.trace_datasource.retention)
        filter_params = {
            "bk_biz_id": bk_biz_id,
            "app_name": app_name,
            "updated_at__lte": last,
        }

        cls.objects.filter(**filter_params).delete()


class TopoNode(TopoBase):
    # extra_data会存储category类型
    # 如果这个Node是http类型，那么在extra_data数据：
    # {"category":"http","kind":"service","predicate_value":"POST","service_language":"python","instance":{}}
    topo_key = models.CharField("节点key", max_length=255, db_index=True)
    system = models.JSONField("系统类型", null=True)
    platform = models.JSONField("部署平台", null=True)
    sdk = models.JSONField("上报sdk", null=True)
    # source: 说明这个服务是由哪个数据源发现的，值为 TelemetryData，存储格式: ["trace", "metric"]
    source = models.JSONField("服务发现来源", default=list)
    is_permanent = models.BooleanField("是否永久保存", default=False)

    @classmethod
    @using_cache(CacheType.APM(60 * 10))
    def get_empty_extra_data(cls):
        """
        获取空的 extra_data 字段
        因为此字段为非空 为了兼容之前 trace 发现的数据一致性所以不将 extra_data 设置为 null=True
        如果其他数据源没有 extra_data 相关数据 则使用此默认值存储
        """
        # 默认服务匹配了 类型为 category 的 other 规则
        from apm.models import ApmTopoDiscoverRule

        other_rule = ApmTopoDiscoverRule.objects.filter(
            type=DiscoverRuleType.CATEGORY.value, category_id=ApmTopoDiscoverRule.APM_TOPO_CATEGORY_OTHER
        ).first()
        if not other_rule:
            return {
                "category": "",
                "kind": "",
                "predicate_value": "",
                "service_language": "",
            }
        return {
            "category": other_rule.category_id,
            "kind": other_rule.topo_kind,
            "predicate_value": "",
            "service_language": "",
        }


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
