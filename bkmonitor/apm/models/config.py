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
import itertools
import logging
import operator

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import ugettext_lazy as _
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.semconv.trace import SpanAttributes

from apm.constants import (
    GLOBAL_CONFIG_BK_BIZ_ID,
    PLATFORM_METRIC_DIMENSION_FILED,
    ConfigTypes,
    SpanKind,
)
from bkmonitor.utils.db import JsonField
from constants.apm import OtlpKey, TrpcAttributes

logger = logging.getLogger("apm")


class ApmTopoDiscoverRule(models.Model):
    # topo发现类型 http rpc
    TOPO_SERVICE = "service"
    # db messaging
    TOPO_COMPONENT = "component"
    # remote_service
    TOPO_REMOTE_SERVICE = "remote_service"
    # instance_key
    DEFAULT_SERVICE_INSTANCE_KEY = OtlpKey.get_resource_key(ResourceAttributes.SERVICE_NAME)
    DEFAULT_COMPONENT_INSTANCE_KEY = (
        f"{OtlpKey.get_attributes_key(SpanAttributes.NET_PEER_NAME)},"
        f"{OtlpKey.get_attributes_key(SpanAttributes.NET_PEER_IP)},"
        f"{OtlpKey.get_attributes_key(SpanAttributes.NET_PEER_PORT)}"
    )

    DEFAULT_ENDPOINT_KEY = OtlpKey.SPAN_NAME

    APM_TOPO_CATEGORY_HTTP = "http"
    APM_TOPO_CATEGORY_RPC = "rpc"
    APM_TOPO_CATEGORY_DB = "db"
    APM_TOPO_CATEGORY_MESSAGING = "messaging"
    APM_TOPO_CATEGORY_ASYNC_BACKEND = "async_backend"
    APM_TOPO_CATEGORY_OTHER = "other"

    APM_TOPO_CATEGORY_CHOICES = (
        (APM_TOPO_CATEGORY_HTTP, "http"),
        (APM_TOPO_CATEGORY_RPC, _("远程过程调用")),
        (APM_TOPO_CATEGORY_DB, _("数据库")),
        (APM_TOPO_CATEGORY_MESSAGING, _("消息队列")),
        (APM_TOPO_CATEGORY_ASYNC_BACKEND, _("后台任务")),
        (APM_TOPO_CATEGORY_OTHER, _("其他")),
    )

    HTTP_PREDICATE_KEY = OtlpKey.get_attributes_key(SpanAttributes.HTTP_METHOD)
    RPC_PREDICATE_KEY = OtlpKey.get_attributes_key(SpanAttributes.RPC_SYSTEM)
    DB_PREDICATE_KEY = OtlpKey.get_attributes_key(SpanAttributes.DB_SYSTEM)
    MESSAGING_PREDICATE_KEY = OtlpKey.get_attributes_key(SpanAttributes.MESSAGING_SYSTEM)
    ASYNC_BACKEND_PREDICATE_KEY = OtlpKey.get_attributes_key(SpanAttributes.MESSAGING_DESTINATION)
    # for trpc
    TRPC_PREDICATE_KEY = OtlpKey.get_attributes_key(TrpcAttributes.TRPC_NAMESPACE)

    COMMON_RULE = [
        {
            "category_id": APM_TOPO_CATEGORY_HTTP,
            "endpoint_key": DEFAULT_ENDPOINT_KEY,
            "instance_key": DEFAULT_SERVICE_INSTANCE_KEY,
            "topo_kind": TOPO_SERVICE,
            "predicate_key": HTTP_PREDICATE_KEY,
        },
        {
            "category_id": APM_TOPO_CATEGORY_RPC,
            "endpoint_key": DEFAULT_ENDPOINT_KEY,
            "instance_key": DEFAULT_SERVICE_INSTANCE_KEY,
            "topo_kind": TOPO_SERVICE,
            "predicate_key": RPC_PREDICATE_KEY,
        },
        {
            "category_id": APM_TOPO_CATEGORY_ASYNC_BACKEND,
            "endpoint_key": DEFAULT_ENDPOINT_KEY,
            "instance_key": DEFAULT_SERVICE_INSTANCE_KEY,
            "topo_kind": TOPO_SERVICE,
            "predicate_key": ASYNC_BACKEND_PREDICATE_KEY,
        },
        {
            "category_id": APM_TOPO_CATEGORY_DB,
            "endpoint_key": DEFAULT_ENDPOINT_KEY,
            "instance_key": f"{DB_PREDICATE_KEY},{DEFAULT_COMPONENT_INSTANCE_KEY}",
            "topo_kind": TOPO_COMPONENT,
            "predicate_key": DB_PREDICATE_KEY,
        },
        {
            "category_id": APM_TOPO_CATEGORY_MESSAGING,
            "endpoint_key": DEFAULT_ENDPOINT_KEY,
            "instance_key": f"{MESSAGING_PREDICATE_KEY},{DEFAULT_COMPONENT_INSTANCE_KEY}",
            "topo_kind": TOPO_COMPONENT,
            "predicate_key": MESSAGING_PREDICATE_KEY,
        },
        {
            "category_id": APM_TOPO_CATEGORY_OTHER,
            "endpoint_key": DEFAULT_ENDPOINT_KEY,
            "instance_key": DEFAULT_SERVICE_INSTANCE_KEY,
            "topo_kind": TOPO_SERVICE,
            "predicate_key": "",
        },
    ]
    PREDICATE_OP_EXISTS = "exists"
    PREDICATE_OP_EQ = "="
    PREDICATE_OP_NOT_EQ = "!="
    DEFAULT_PREDICATE_OP_VALUE = ""

    # 0 全平台通用规则
    bk_biz_id = models.IntegerField("业务id")
    app_name = models.CharField("应用名称", max_length=128)
    # http,rpc,db.messaging
    category_id = models.CharField("分类名称", max_length=128)
    # 接口字段，如果没有特殊要求统一为span_name
    endpoint_key = models.CharField("接口字段", max_length=255)
    instance_key = models.CharField("实例字段", max_length=255)
    topo_kind = models.CharField("topo发现类型", max_length=50)
    predicate_key = models.CharField("判断字段", max_length=128)

    @classmethod
    def get_application_rule(cls, bk_biz_id, app_name, topo_kind=None):
        filter_args = {}
        if topo_kind:
            filter_args["topo_kind"] = topo_kind
        return cls.objects.filter(
            (Q(bk_biz_id=bk_biz_id) & Q(app_name=app_name)) | (Q(bk_biz_id=GLOBAL_CONFIG_BK_BIZ_ID)), **filter_args
        )

    @classmethod
    def init_builtin_config(cls):
        objs = []
        for common_rule in cls.COMMON_RULE:
            if cls.objects.filter(**common_rule, bk_biz_id=GLOBAL_CONFIG_BK_BIZ_ID).exists():
                continue
            objs.append(cls(bk_biz_id=GLOBAL_CONFIG_BK_BIZ_ID, app_name="", **common_rule))
        cls.objects.bulk_create(objs)


class ApmInstanceDiscover(models.Model):
    COMMON_DISCOVERY_KEYS = [
        OtlpKey.get_resource_key(ResourceAttributes.TELEMETRY_SDK_LANGUAGE),
        OtlpKey.get_resource_key(ResourceAttributes.SERVICE_NAME),
        OtlpKey.get_resource_key(SpanAttributes.NET_HOST_NAME),
        OtlpKey.get_resource_key(SpanAttributes.NET_HOST_IP),
        OtlpKey.get_resource_key(SpanAttributes.NET_HOST_PORT),
    ]

    # 0 为全局
    bk_biz_id = models.IntegerField("业务id")
    app_name = models.CharField("应用名称", max_length=255)
    discover_key = models.CharField("应用名称", max_length=255)
    # 同rank按字典序
    rank = models.IntegerField("rank")

    class Meta:
        ordering = ["rank", "discover_key"]

    @classmethod
    def init_builtin_config(cls):
        objs = []
        for rank, discover_key in enumerate(cls.COMMON_DISCOVERY_KEYS):
            qs = cls.objects.filter(discover_key=discover_key, bk_biz_id=GLOBAL_CONFIG_BK_BIZ_ID)
            if qs.exists():
                cls.objects.update(rank=rank)
            objs.append(cls(bk_biz_id=GLOBAL_CONFIG_BK_BIZ_ID, discover_key=discover_key, rank=rank, app_name=""))
        cls.objects.bulk_create(objs)

    @classmethod
    def refresh_config(cls, bk_biz_id, app_name, instance_name_config):
        configs = cls.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).order_by("rank")
        delete_configs = {
            key: [i.id for i in item] for key, item in itertools.groupby(configs, operator.attrgetter("discover_key"))
        }
        instances = []
        for rank, discover_key in enumerate(instance_name_config):
            qs = cls.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name, discover_key=discover_key)
            if qs.exists():
                qs.update(rank=rank)
                del delete_configs[discover_key]
            else:
                instances.append(cls(bk_biz_id=bk_biz_id, app_name=app_name, discover_key=discover_key, rank=rank))

        cls.objects.bulk_create(instances)
        cls.objects.filter(id__in=itertools.chain(*[ids for _, ids in delete_configs.items()])).delete()

    @classmethod
    def delete_config(cls, bk_biz_id, app_name):
        cls.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).delete()

    @classmethod
    def get_biz_config(cls, bk_biz_id):
        if cls.objects.filter(bk_biz_id=bk_biz_id).exists():
            return cls.objects.filter(bk_biz_id=bk_biz_id)
        return cls.objects.filter(bk_biz_id=GLOBAL_CONFIG_BK_BIZ_ID)

    def to_json(self):
        return {"discover_key": self.discover_key, "rank": self.rank}


class ApmMetricDimension(models.Model):
    SPAN_KIND_SERVER = "SPAN_KIND_SERVER"
    SPAN_KIND_CLIENT = "SPAN_KIND_CLIENT"
    SPAN_KIND_PRODUCER = "SPAN_KIND_PRODUCER"
    SPAN_KIND_CONSUMER = "SPAN_KIND_CONSUMER"

    DEFAULT_PREDICATE_KEY = ""

    COMMON_DIMENSION_KEYS = [
        OtlpKey.get_resource_key(OtlpKey.BK_INSTANCE_ID),
        OtlpKey.SPAN_NAME,
        OtlpKey.KIND,
        OtlpKey.STATUS_CODE,
        OtlpKey.get_resource_key(ResourceAttributes.SERVICE_NAME),
        OtlpKey.get_resource_key(ResourceAttributes.SERVICE_VERSION),
        OtlpKey.get_resource_key(ResourceAttributes.TELEMETRY_SDK_NAME),
        OtlpKey.get_resource_key(ResourceAttributes.TELEMETRY_SDK_VERSION),
        OtlpKey.get_resource_key(ResourceAttributes.TELEMETRY_SDK_LANGUAGE),
        OtlpKey.get_attributes_key(SpanAttributes.PEER_SERVICE),
        OtlpKey.get_attributes_key(OtlpKey.APDEX_TYPE),
    ]

    if settings.APM_IS_ADD_PLATFORM_METRIC_DIMENSION_CONFIG:
        COMMON_DIMENSION_KEYS.extend(PLATFORM_METRIC_DIMENSION_FILED)

    SERVER_DIMENSION_KEYS = [
        {"predicate_key": DEFAULT_PREDICATE_KEY, "dimensions": []},
        {
            "predicate_key": ApmTopoDiscoverRule.HTTP_PREDICATE_KEY,
            "dimensions": [
                OtlpKey.get_attributes_key(SpanAttributes.HTTP_SERVER_NAME),
                OtlpKey.get_attributes_key(SpanAttributes.HTTP_METHOD),
                OtlpKey.get_attributes_key(SpanAttributes.HTTP_SCHEME),
                OtlpKey.get_attributes_key(SpanAttributes.HTTP_FLAVOR),
                OtlpKey.get_attributes_key(SpanAttributes.HTTP_STATUS_CODE),
            ],
        },
        {
            "predicate_key": ApmTopoDiscoverRule.RPC_PREDICATE_KEY,
            "dimensions": [
                OtlpKey.get_attributes_key(SpanAttributes.RPC_METHOD),
                OtlpKey.get_attributes_key(SpanAttributes.RPC_SERVICE),
                OtlpKey.get_attributes_key(SpanAttributes.RPC_SYSTEM),
                OtlpKey.get_attributes_key(SpanAttributes.RPC_GRPC_STATUS_CODE),
            ],
        },
    ]

    CLIENT_DIMENSION_KEYS = [
        {"predicate_key": DEFAULT_PREDICATE_KEY, "dimensions": []},
        {
            "predicate_key": ApmTopoDiscoverRule.HTTP_PREDICATE_KEY,
            "dimensions": [
                OtlpKey.get_attributes_key(SpanAttributes.HTTP_METHOD),
                OtlpKey.get_attributes_key(SpanAttributes.HTTP_STATUS_CODE),
            ],
        },
        {
            "predicate_key": ApmTopoDiscoverRule.RPC_PREDICATE_KEY,
            "dimensions": [
                OtlpKey.get_attributes_key(SpanAttributes.RPC_METHOD),
                OtlpKey.get_attributes_key(SpanAttributes.RPC_SERVICE),
                OtlpKey.get_attributes_key(SpanAttributes.RPC_SYSTEM),
                OtlpKey.get_attributes_key(SpanAttributes.RPC_GRPC_STATUS_CODE),
            ],
        },
        {
            "predicate_key": ApmTopoDiscoverRule.DB_PREDICATE_KEY,
            "dimensions": [
                OtlpKey.get_attributes_key(SpanAttributes.DB_NAME),
                OtlpKey.get_attributes_key(SpanAttributes.DB_OPERATION),
                OtlpKey.get_attributes_key(SpanAttributes.DB_SYSTEM),
                OtlpKey.get_attributes_key(SpanAttributes.NET_PEER_NAME),
                OtlpKey.get_attributes_key(SpanAttributes.NET_PEER_IP),
                OtlpKey.get_attributes_key(SpanAttributes.NET_PEER_PORT),
            ],
        },
    ]

    if settings.APM_TRPC_ENABLED:
        trpc_metric_dimensions = {
            "predicate_key": ApmTopoDiscoverRule.TRPC_PREDICATE_KEY,
            "dimensions": [
                OtlpKey.get_attributes_key(TrpcAttributes.TRPC_NAMESPACE),
                OtlpKey.get_attributes_key(TrpcAttributes.TRPC_CALLER_SERVICE),
                OtlpKey.get_attributes_key(TrpcAttributes.TRPC_CALLEE_SERVICE),
                OtlpKey.get_attributes_key(TrpcAttributes.TRPC_CALLEE_METHOD),
                OtlpKey.get_attributes_key(TrpcAttributes.TRPC_STATUS_TYPE),
                OtlpKey.get_attributes_key(TrpcAttributes.TRPC_STATUS_CODE),
            ],
        }
        CLIENT_DIMENSION_KEYS.append(trpc_metric_dimensions)
        SERVER_DIMENSION_KEYS.append(trpc_metric_dimensions)

    PRODUCER_DIMENSION_KEYS = [
        {"predicate_key": DEFAULT_PREDICATE_KEY, "dimensions": []},
        {
            "predicate_key": ApmTopoDiscoverRule.MESSAGING_PREDICATE_KEY,
            "dimensions": [
                OtlpKey.get_attributes_key(SpanAttributes.MESSAGING_SYSTEM),
                OtlpKey.get_attributes_key(SpanAttributes.MESSAGING_DESTINATION),
                OtlpKey.get_attributes_key(SpanAttributes.MESSAGING_DESTINATION_KIND),
                OtlpKey.get_attributes_key(SpanAttributes.NET_PEER_NAME),
                OtlpKey.get_attributes_key(SpanAttributes.NET_PEER_IP),
                OtlpKey.get_attributes_key(SpanAttributes.NET_PEER_PORT),
                OtlpKey.get_attributes_key("celery.action"),
                OtlpKey.get_attributes_key("celery.task_name"),
            ],
        },
    ]

    CONSUMER_DIMENSION_KEYS = [
        {"predicate_key": DEFAULT_PREDICATE_KEY, "dimensions": []},
        {
            "predicate_key": ApmTopoDiscoverRule.MESSAGING_PREDICATE_KEY,
            "dimensions": [
                OtlpKey.get_attributes_key(SpanAttributes.NET_PEER_NAME),
                OtlpKey.get_attributes_key(SpanAttributes.NET_PEER_IP),
                OtlpKey.get_attributes_key(SpanAttributes.NET_PEER_PORT),
                OtlpKey.get_attributes_key(SpanAttributes.MESSAGING_SYSTEM),
                OtlpKey.get_attributes_key("celery.state"),
                OtlpKey.get_attributes_key("celery.action"),
            ],
        },
    ]

    PREDICATE_OP_EXISTS = "exists"
    PREDICATE_OP_EQ = "="
    DEFAULT_PREDICATE_OP_VALUE = ""

    # 0 全平台通用规则
    bk_biz_id = models.IntegerField("业务id")
    app_name = models.CharField("应用名称", max_length=128)
    span_kind = models.CharField("提取kind", max_length=50)
    predicate_key = models.CharField("判断字段", max_length=128)
    dimension_key = models.CharField("维度字段名称", max_length=128)

    @classmethod
    def init_builtin_config(cls):
        cls.init_metric_dimensions(cls.SPAN_KIND_SERVER, cls.SERVER_DIMENSION_KEYS, cls.COMMON_DIMENSION_KEYS)
        cls.init_metric_dimensions(cls.SPAN_KIND_CLIENT, cls.CLIENT_DIMENSION_KEYS, cls.COMMON_DIMENSION_KEYS)
        cls.init_metric_dimensions(cls.SPAN_KIND_PRODUCER, cls.PRODUCER_DIMENSION_KEYS, cls.COMMON_DIMENSION_KEYS)
        cls.init_metric_dimensions(cls.SPAN_KIND_CONSUMER, cls.CONSUMER_DIMENSION_KEYS, cls.COMMON_DIMENSION_KEYS)

    @classmethod
    def init_metric_dimensions(cls, kind, kind_items, common_dimensions):
        logger.info(f"[init metric dimensions] span_kind: {kind} ")
        objs = []
        bk_biz_id = GLOBAL_CONFIG_BK_BIZ_ID
        app_name = ""

        mapping = cls.list_exists_mappings(bk_biz_id, app_name, kind)

        for item in kind_items:
            for dimension in common_dimensions:
                instance = cls.objects.filter(
                    span_kind=kind,
                    bk_biz_id=GLOBAL_CONFIG_BK_BIZ_ID,
                    predicate_key=item["predicate_key"],
                    dimension_key=dimension,
                    app_name="",
                ).first()

                if instance:
                    mapping.pop((instance.predicate_key, instance.dimension_key), None)
                    continue

                objs.append(
                    cls(
                        span_kind=kind,
                        bk_biz_id=GLOBAL_CONFIG_BK_BIZ_ID,
                        predicate_key=item["predicate_key"],
                        dimension_key=dimension,
                        app_name="",
                    )
                )

            for dimension in item["dimensions"]:
                instance = cls.objects.filter(
                    span_kind=kind,
                    bk_biz_id=GLOBAL_CONFIG_BK_BIZ_ID,
                    predicate_key=item["predicate_key"],
                    dimension_key=dimension,
                    app_name="",
                ).first()

                if instance:
                    mapping.pop((instance.predicate_key, instance.dimension_key), None)
                    continue
                objs.append(
                    cls(
                        span_kind=kind,
                        bk_biz_id=GLOBAL_CONFIG_BK_BIZ_ID,
                        predicate_key=item["predicate_key"],
                        dimension_key=dimension,
                        app_name="",
                    )
                )

        cls.objects.bulk_create(objs)
        cls.objects.filter(id__in=list(itertools.chain(*mapping.values()))).delete()

        logger.info(f"[init metric dimensions] create dimensions: {len(objs)} ")
        logger.info(f"[init metric dimensions] delete dimensions keys: {list(mapping.keys())} ")

    @classmethod
    def list_exists_mappings(cls, bk_biz_id, app_name, kind):
        res = {}
        datas = cls.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name, span_kind=kind)
        for item in datas:
            res.setdefault((item.predicate_key, item.dimension_key), []).append(item.id)

        return res

    @classmethod
    def refresh_config(cls, bk_biz_id, app_name, dimension_configs):
        instances = []
        if not dimension_configs:
            return

        for item in dimension_configs:
            for dimension in item["dimensions"]:
                qs = cls.objects.filter(
                    bk_biz_id=bk_biz_id,
                    app_name=app_name,
                    span_kind=item["span_kind"],
                    predicate_key=item["predicate_key"],
                    dimension_key=dimension,
                )
                if qs.exists():
                    continue
                instances.append(
                    cls(
                        bk_biz_id=bk_biz_id,
                        app_name=app_name,
                        span_kind=item["span_kind"],
                        predicate_key=item["predicate_key"],
                        dimension_key=dimension,
                    )
                )

        cls.objects.bulk_create(instances)

    @classmethod
    def delete_config(cls, bk_biz_id, app_name):
        cls.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).delete()

    @classmethod
    def get_biz_config(cls, bk_biz_id):
        return cls.objects.filter(bk_biz_id__in=[bk_biz_id, GLOBAL_CONFIG_BK_BIZ_ID])

    def to_json(self):
        return {
            "bk_biz_id": self.bk_biz_id,
            "app_name": self.app_name,
            "span_kind": self.span_kind,
            "predicate_key": self.predicate_key,
            "dimension_key": self.dimension_key,
        }


class RemoteServiceDiscover(models.Model):
    # 0 全平台通用规则
    bk_biz_id = models.IntegerField("业务id")
    app_name = models.CharField("应用名称", max_length=128)
    span_kind = models.CharField("提取kind", max_length=50)
    predicate_key = models.CharField("判断字段", max_length=128)
    match_key = models.CharField("匹配key", max_length=128)
    match_op = models.CharField("匹配操作", max_length=20)
    match_value = models.CharField("匹配值", max_length=255)
    peer_service_name = models.CharField("远程服务名称", max_length=128)


class AppConfigBase(models.Model):
    APP_LEVEL = "app_level"
    SERVICE_LEVEL = "service_level"
    INSTANCE_LEVEL = "instance_level"

    REFRESH_CONFIG_KEYS = None
    UNIQUE_KEYS = None

    bk_biz_id = models.IntegerField("业务id")
    app_name = models.CharField("应用名称", max_length=128)
    config_level = models.CharField("配置级别", max_length=50)
    config_key = models.CharField("配置key", max_length=255)

    class Meta:
        abstract = True

    @classmethod
    def refresh_config(cls, bk_biz_id, app_name, config_level, config_key, refresh_configs, need_delete_config=True):
        create_objs = []
        exist_ids = []
        if need_delete_config:
            exist_ids = list(
                cls.objects.filter(
                    bk_biz_id=bk_biz_id, app_name=app_name, config_key=config_key, config_level=config_level
                ).values_list("id", flat=True)
            )
        for refresh_config in refresh_configs:
            unique_params = {
                "bk_biz_id": bk_biz_id,
                "app_name": app_name,
                "config_level": config_level,
                "config_key": config_key,
            }
            if cls.UNIQUE_KEYS:
                for unique_key in cls.UNIQUE_KEYS:
                    unique_params[unique_key] = refresh_config[unique_key]

            obj = cls.objects.filter(**unique_params)
            obj_ids = obj.values_list("id", flat=True)
            exist_ids = [i for i in exist_ids if i not in obj_ids]

            if obj.exists():
                obj = obj.first()
                for key in cls.REFRESH_CONFIG_KEYS:
                    setattr(obj, key, refresh_config[key])
                obj.save()
                repeat_ids = [i for i in obj_ids if i != obj.id]
                if repeat_ids:
                    cls.objects.filter(id__in=repeat_ids).delete()
                    logger.info(f"[AppConfigBase] delete repeat ids in {unique_params}")
                continue
            create_params = {
                "bk_biz_id": bk_biz_id,
                "app_name": app_name,
                "config_level": config_level,
                "config_key": config_key,
                **refresh_config,
            }
            create_objs.append(cls(**create_params))
        cls.objects.bulk_create(create_objs)
        cls.objects.filter(id__in=exist_ids).delete()
        logger.info(f"[AppConfigBase] {bk_biz_id} {app_name} create {len(create_objs)} delete: {len(exist_ids)}")

    @classmethod
    def delete_config(cls, bk_biz_id, app_name, delete_configs):
        delete_ids = []
        for delete_config in delete_configs:
            unique_params = {
                "bk_biz_id": bk_biz_id,
                "app_name": app_name,
                "config_level": delete_config["config_level"],
                "config_key": delete_config["config_key"],
            }
            if cls.UNIQUE_KEYS:
                for unique_key in cls.UNIQUE_KEYS:
                    unique_params[unique_key] = delete_config[unique_key]
            delete_ids.extend([obj.id for obj in cls.objects.filter(**unique_params)])
        cls.objects.filter(id__in=delete_ids).delete()

    @classmethod
    def configs(cls, bk_biz_id, app_name, config_level):
        return cls.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name, config_level=config_level)

    @classmethod
    def service_configs(cls, bk_biz_id, app_name):
        return cls.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name, config_level=cls.SERVICE_LEVEL)

    @classmethod
    def application_configs(cls, bk_biz_id, app_name):
        return cls.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name, config_level=cls.APP_LEVEL)

    @classmethod
    def instance_configs(cls, bk_biz_id, app_name):
        return cls.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name, config_level=cls.INSTANCE_LEVEL)

    def to_json(self):
        return {"config_level": self.config_level, "config_key": self.config_key, **self.to_config_json()}

    def to_config_json(self):
        return {}


class ApdexConfig(AppConfigBase):
    REFRESH_CONFIG_KEYS = ["span_kind", "predicate_key", "apdex_t"]
    UNIQUE_KEYS = ["span_kind", "predicate_key"]

    span_kind = models.CharField("提取kind", max_length=50)
    predicate_key = models.CharField("判断字段", max_length=128)
    apdex_t = models.IntegerField("apdex_t", default=100)

    def to_config_json(self):
        return {
            "kind": self.span_kind,
            "metric_name": "bk_apm_duration",
            "destination": "apdex_type",
            "predicate_key": self.predicate_key,
            "apdex_t": self.apdex_t,
        }


class SamplerConfig(AppConfigBase):
    REFRESH_CONFIG_KEYS = ["sampler_type", "sampling_percentage"]

    sampler_type = models.CharField("采样类型", default="random", max_length=64)
    sampling_percentage = models.IntegerField("采样百分比", default=100)

    def to_config_json(self):
        return {
            "name": f"sampler/{self.sampler_type}",
            "type": self.sampler_type,
            "sampling_percentage": self.sampling_percentage,
        }


class CustomServiceConfig(AppConfigBase):
    REFRESH_CONFIG_KEYS = ["name", "type", "rule", "match_type"]

    DISCOVER_KEYS = {
        "http": {
            # http类型的远程服务发现规则
            "predicate_key": OtlpKey.get_attributes_key(SpanAttributes.HTTP_METHOD),
            "span_kind": SpanKind.SPAN_KIND_CLIENT,
            "match_key": OtlpKey.get_attributes_key(SpanAttributes.HTTP_URL),
        }
    }

    MATCH_GROUPS = {
        # 远程服务发现match_groups配置
        "auto": {"http": {"peer_service": {"destination": "peer.service"}, "span_name": {"destination": "span_name"}}},
        "manual": {"http": {"service": {"destination": "peer.service"}, "path": {"destination": "span_name"}}},
    }

    type = models.CharField(max_length=32, verbose_name="类型")
    name = models.CharField(max_length=258, verbose_name="名称", null=True)
    rule = JsonField(verbose_name="匹配规则")
    match_type = models.CharField(max_length=32, verbose_name="匹配类型")


class NormalTypeValueConfig(AppConfigBase):
    """
    TYPE-VALUE配置
    """

    REFRESH_CONFIG_KEYS = ["value"]
    UNIQUE_KEYS = ["type"]

    type = models.CharField("配置类型", choices=ConfigTypes.choices(), max_length=32)
    value = models.TextField("配置值")

    @classmethod
    def get_app_value(cls, bk_biz_id, app_name, config_type):
        """获取应用维度下的配置值"""

        config = cls.objects.filter(
            bk_biz_id=bk_biz_id, app_name=app_name, config_level=cls.APP_LEVEL, config_key=app_name, type=config_type
        ).first()
        if not config:
            return None

        return config.value


class QpsConfig(AppConfigBase):
    REFRESH_CONFIG_KEYS = ["qps"]
    qps = models.IntegerField("QPS", default=settings.APM_APP_QPS)

    @classmethod
    def get_application_qps(cls, bk_biz_id, app_name):
        qps_config = cls.objects.filter(
            bk_biz_id=bk_biz_id, app_name=app_name, config_level=cls.APP_LEVEL, config_key=app_name
        ).first()

        if not qps_config:
            return None

        return qps_config.qps


class LicenseConfig(AppConfigBase):
    REFRESH_CONFIG_KEYS = ["enabled", "expire_time", "tolerable_expire", "number_nodes", "tolerable_num_ratio"]

    enabled = models.BooleanField("是否开启license检查", default=True)
    expire_time = models.BigIntegerField("license 过期时间")
    tolerable_expire = models.CharField("容忍过期时间", max_length=12)
    number_nodes = models.IntegerField("可接受探针实例数量")
    tolerable_num_ratio = models.FloatField("可接受探针实例数量倍率", default=1.0)

    @classmethod
    def get_application_license_config(cls, bk_biz_id, app_name):
        license_config = cls.objects.filter(
            bk_biz_id=bk_biz_id, app_name=app_name, config_level=cls.APP_LEVEL, config_key=app_name
        ).first()

        if not license_config:
            return None

        return license_config.to_config_json()

    def to_config_json(self):
        return {
            "name": "license_checker/common",
            "enabled": self.enabled,
            "expire_time": self.expire_time,
            "number_nodes": self.number_nodes,
            "tolerable_expire": self.tolerable_expire,
            "tolerable_num_ratio": self.tolerable_num_ratio,
        }


class DbConfig(AppConfigBase):
    UNIQUE_KEYS = ["db_system"]
    REFRESH_CONFIG_KEYS = ["trace_mode", "length", "predicate_key", "match", "cut_keys", "drop_keys", "threshold"]

    db_system = models.CharField("DB类型", max_length=32)
    trace_mode = models.CharField("追踪模式", max_length=32)
    length = models.IntegerField("保留长度")
    predicate_key = models.CharField("发现字段", max_length=32)
    match = JsonField(verbose_name="匹配字段")
    cut_keys = JsonField(verbose_name="剪辑字段")
    drop_keys = JsonField(verbose_name="丢弃字段")
    threshold = models.IntegerField("阈值", default=500)


class ProbeConfig(AppConfigBase):
    REFRESH_CONFIG_KEYS = ["sn", "rules"]

    sn = models.CharField("配置变更标识", max_length=255)
    rules = models.JSONField(verbose_name="配置")

    @classmethod
    def get_config(cls, bk_biz_id, app_name):
        config = cls.objects.filter(
            bk_biz_id=bk_biz_id, app_name=app_name, config_level=cls.APP_LEVEL, config_key=app_name
        ).first()

        if not config:
            return None

        return config
