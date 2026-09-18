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
import logging
from typing import Any

from django.db import OperationalError, models, router, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apm.constants import DiscoverRuleType
from bkmonitor.utils.cache import CacheType, using_cache
from bkmonitor.utils.db import JsonField
from constants.apm import SpanKind, TelemetryDataType
from core.drf_resource.exceptions import CustomException


logger = logging.getLogger("apm")


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
    # 节点过期时间（天）
    # 背景：之前节点过期时间设置为 Trace 数据的保留时间，但对于零星上报、活动类服务可能存在较长时间未上报 Trace 的情况，
    # 导致节点过早过期被删除，影响监控和展示。故调整为 180 天，兼顾数据时效性和完整性。
    EXPIRED_DAYS = 180

    # extra_data会存储category类型
    # 如果这个Node是http类型，那么在extra_data数据：
    # {"category":"http","kind":"service","predicate_value":"POST","service_language":"python","instance":{}}
    topo_key = models.CharField("节点key", max_length=255, db_index=True)
    system = models.JSONField("系统类型", null=True)
    platform = models.JSONField("部署平台", null=True)
    sdk = models.JSONField("上报sdk", null=True)
    # source: 说明这个服务是由哪个数据源发现的，值为 TelemetryData，存储格式: ["trace", "metric"]
    source = models.JSONField("服务发现来源", default=list)
    heartbeat = models.JSONField("服务数据心跳", default=dict)
    is_permanent = models.BooleanField("是否永久保存", default=False)

    @classmethod
    def new_source_filter(cls) -> Q:
        """仅由日志或性能分析发现的节点，尚无 Trace／Metric 分类。"""
        # JSON 精确匹配会在 MySQL 侧转换参数类型；JSON 列的 IN 查找没有这一步。
        log: str = TelemetryDataType.LOG.value
        profiling: str = TelemetryDataType.PROFILING.value
        return Q(source=[log]) | Q(source=[profiling]) | Q(source=[log, profiling]) | Q(source=[profiling, log])

    @classmethod
    def legacy_source_filter(cls) -> Q:
        """第一阶段的服务可见范围；第二阶段切换时移除查询入口的此限制。"""
        return ~cls.new_source_filter()

    @classmethod
    def get_service_queryset(cls, **filters: Any) -> models.QuerySet:
        """服务列表、计数与搜索共用过渡期过滤，原始拓扑诊断仍可读取 objects。"""
        return cls.objects.filter(cls.legacy_source_filter(), **filters)

    @staticmethod
    def has_trace_or_metric_source(sources: list[str] | None) -> bool:
        """空来源属于历史节点，其余节点须已被 Trace 或 Metric 发现。"""
        return not sources or bool(
            {TelemetryDataType.TRACE.value, TelemetryDataType.METRIC.value}.intersection(sources)
        )

    @classmethod
    def touch_heartbeat(
        cls,
        bk_biz_id: int,
        app_name: str,
        data_type: str,
        last_data_at_mapping: dict[str, int | None],
        checked_at: int,
        *,
        check_all_services: bool = False,
    ) -> bool:
        """合并单类心跳，不改变节点存活时间。

        :param check_all_services: 仅在完整应用查询成功时使用；未命中节点保持数据时间，仅推进检查时间。
        :return: 是否成功提交；锁超时或死锁时保留旧心跳，交由下一轮发现恢复。
        """
        if data_type not in {item.value for item in TelemetryDataType}:
            raise ValueError(f"unsupported telemetry data type: {data_type}")
        if not last_data_at_mapping and not check_all_services:
            return True

        database: str = router.db_for_write(cls)
        try:
            with transaction.atomic(using=database):
                queryset = (
                    cls.objects.using(database).select_for_update().filter(bk_biz_id=bk_biz_id, app_name=app_name)
                )
                if not check_all_services:
                    queryset = queryset.filter(topo_key__in=last_data_at_mapping)
                nodes: list[TopoNode] = list(queryset.only("id", "topo_key", "heartbeat").order_by("id"))
                for node in nodes:
                    heartbeat: dict[str, Any] = dict(node.heartbeat)
                    previous: dict[str, int | None] = heartbeat.get(data_type, {})
                    times: list[int] = [
                        value
                        for value in (previous.get("last_data_at"), last_data_at_mapping.get(node.topo_key))
                        if value is not None
                    ]
                    heartbeat[data_type] = {
                        "last_data_at": max(times) if times else None,
                        "checked_at": max(previous.get("checked_at") or 0, checked_at),
                    }
                    node.heartbeat = heartbeat
                cls.objects.using(database).bulk_update(nodes, fields=["heartbeat"], batch_size=200)
        except OperationalError as error:
            # 在事务退出并回滚后处理可恢复的行锁失败，其他数据库异常继续上抛。
            if not error.args or error.args[0] not in (1205, 1213):
                raise
            logger.warning(
                "[ServiceHeartbeat] lock failed, keeping previous heartbeat: bk_biz_id=%s app_name=%s data_type=%s errno=%s",
                bk_biz_id,
                app_name,
                data_type,
                error.args[0],
            )
            return False
        return True

    @classmethod
    def upsert_telemetry_nodes(
        cls, bk_biz_id: int, app_name: str, data_type: str, service_names: set[str], extra_data: dict[str, Any]
    ) -> None:
        """日志和性能分析只补充节点与来源，不覆盖已有拓扑分类。

        节点表没有服务键唯一约束，首建并发仍可能产生同名行；心跳入口覆盖全部同名行。
        """
        if not service_names:
            return
        database: str = router.db_for_write(cls)
        with transaction.atomic(using=database):
            nodes: list[TopoNode] = list(
                cls.objects.using(database)
                .select_for_update()
                .filter(bk_biz_id=bk_biz_id, app_name=app_name, topo_key__in=service_names)
                .order_by("id")
            )
            existing_names: set[str] = {node.topo_key for node in nodes}
            for node in nodes:
                # 空来源是历史节点，不能改成新增来源独有节点，否则第一阶段会隐藏它。
                if node.source and data_type not in node.source:
                    node.source = [*node.source, data_type]
                node.updated_at = timezone.now()
            cls.objects.using(database).bulk_update(nodes, fields=["source", "updated_at"], batch_size=200)
            cls.objects.using(database).bulk_create(
                [
                    cls(
                        bk_biz_id=bk_biz_id, app_name=app_name, topo_key=name, source=[data_type], extra_data=extra_data
                    )
                    for name in sorted(service_names - existing_names)
                ],
                batch_size=200,
            )

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
