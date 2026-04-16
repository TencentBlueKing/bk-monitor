"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any, Self

from django.db import models, transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from apm_web.constants import ServiceRelationLogTypeChoices, SyncScope
from bkmonitor.utils.request import get_request_username
from monitor_web.data_explorer.event.constants import EventCategory


class ServiceBase(models.Model):
    """服务基础信息"""

    bk_biz_id = models.BigIntegerField("业务ID")
    app_name = models.CharField("应用名称", max_length=50)
    service_name = models.CharField("服务名称", max_length=512)
    is_global = models.BooleanField("是否为全局配置", default=False)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)
    created_by = models.CharField("创建人", max_length=128, null=True)
    updated_by = models.CharField("更新人", max_length=128, null=True)

    # 子类可重写：用于 diff-sync 的唯一键字段（除 SCOPE_KEYS 外的业务唯一键）
    DIFF_KEYS: list[str] = []
    # 子类可重写：diff-sync 时可被更新的字段
    DEFAULT_KEYS: list[str] = []
    # 用于 diff-sync 的作用域字段
    SCOPE_KEYS: list[str] = ["bk_biz_id", "app_name", "service_name"]

    class Meta:
        abstract = True
        index_together = [["bk_biz_id", "app_name", "service_name"]]

    @classmethod
    def get_relation_qs(
        cls,
        bk_biz_id: int,
        app_name: str,
        service_names: list[str] | None = None,
        include_global: bool = False,
        **extra_filters,
    ) -> QuerySet[Self]:
        """统一查询入口，按场景构建查询条件并返回 QuerySet。

        场景说明：
        - 场景 1: service_names=["svc-a", ...] + include_global=True  → 指定服务级 + 全局规则
        - 场景 2: service_names=["svc-a", ...] + include_global=False → 仅指定服务级规则
        - 场景 3: service_names=[]             + include_global=True  → 仅全局规则
        - 场景 3b: service_names=[]            + include_global=False → 空结果（无服务可查且不含全局）
        - 场景 4: service_names=None(不传)      + include_global=True  → 应用下所有规则（全量）
        - 场景 5: service_names=None(不传)      + include_global=False → 应用下所有服务的规则（排除全局）

        向后兼容：include_global 默认 False，旧调用方不传参数时仅返回服务级记录，行为不变。
        """
        base_q = Q(bk_biz_id=bk_biz_id, app_name=app_name, **extra_filters)

        if service_names is None:
            scope_q = Q(is_global=False)
        else:
            scope_q = Q(service_name__in=service_names, is_global=False)

        if include_global:
            scope_q |= Q(is_global=True)

        return cls.objects.filter(base_q & scope_q)

    @classmethod
    def get_relations(
        cls,
        bk_biz_id: int,
        app_name: str,
        service_names: list[str] | None = None,
        include_global: bool = False,
        **extra_filters,
    ) -> list[dict[str, Any]]:
        """get_relation_qs 的便捷封装，直接返回 list[dict] 而非 QuerySet。参数语义同 get_relation_qs。"""
        return list(cls.get_relation_qs(bk_biz_id, app_name, service_names, include_global, **extra_filters).values())

    @classmethod
    def _make_sync_key(cls, obj_or_dict: "dict[str, Any] | ServiceBase") -> tuple:
        """从 dict 或 model 实例中提取 SCOPE_KEYS + DIFF_KEYS 组成的唯一键元组。"""
        all_keys = cls.SCOPE_KEYS + cls.DIFF_KEYS
        if isinstance(obj_or_dict, dict):
            return tuple(obj_or_dict.get(k) for k in all_keys)
        return tuple(getattr(obj_or_dict, k, None) for k in all_keys)

    @classmethod
    def _diff_and_apply(cls, obj: "ServiceBase", record: dict[str, Any]) -> bool:
        """将 record 中变化的 DEFAULT_KEYS 字段写入 obj，返回是否有变更。"""
        changed = False
        for field in cls.DEFAULT_KEYS:
            if field not in record:
                continue
            if (new_val := record[field]) != getattr(obj, field, None):
                setattr(obj, field, new_val)
                changed = True
        return changed

    @classmethod
    @transaction.atomic
    def sync_relations(
        cls,
        bk_biz_id: int,
        app_name: str,
        service_name: str = "",
        records: list[dict[str, Any]] | None = None,
        scope: SyncScope = SyncScope.SERVICE,
        is_delete: bool = True,
    ) -> dict[str, Any]:
        """统一更新入口，按 DIFF_KEYS 比对存量，执行增/改/删。

        records 字典结构（各子类按自身字段组合）：
          公共字段（SCOPE_KEYS，可省略，省略时自动填充）：
            - bk_biz_id (int): 业务 ID
            - app_name (str): 应用名称
            - service_name (str): 服务名称
            - is_global (bool): 是否为全局配置
          业务字段（DIFF_KEYS + DEFAULT_KEYS，因子类而异）
          注：DIFF_KEYS 与 SCOPE_KEYS 共同构成唯一键用于比对；
          其余业务字段属于 DEFAULT_KEYS，在记录已存在时按值差异进行更新。

        scope（SyncScope 枚举值）:
          - SyncScope.SERVICE：Q(is_global=False)，仅操作服务级记录。
          - SyncScope.GLOBAL：Q(is_global=True)，仅操作全局记录。
          - SyncScope.ALL：不区分，操作该应用下所有记录。

        is_delete (bool): 是否删除存量中多余的记录，默认为 True。
          为 True 时，不在 records 中的存量记录会被删除（完整同步语义）；
          为 False 时，仅执行新增和更新，不删除任何已有记录（增量同步语义）。
        """

        records: list[dict[str, Any]] = records or []

        # 1. 构建工作集查询条件
        base_q = Q(bk_biz_id=bk_biz_id, app_name=app_name)
        if scope == SyncScope.SERVICE:
            base_q &= Q(is_global=False, service_name=service_name)
        elif scope == SyncScope.GLOBAL:
            base_q &= Q(is_global=True)

        existing_map: dict[tuple, ServiceBase] = {cls._make_sync_key(obj): obj for obj in cls.objects.filter(base_q)}

        # 2. 遍历 records，新增 / 更新
        to_create: list[ServiceBase] = []
        to_update: list[ServiceBase] = []
        incoming_keys: set[tuple[Any]] = set()
        writable_fields: set[str] = {f.name for f in cls._meta.get_fields()} - {
            "id",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
        }
        for record in records:
            record.setdefault("bk_biz_id", bk_biz_id)
            record.setdefault("app_name", app_name)
            sync_key: tuple[Any] = cls._make_sync_key(record)
            incoming_keys.add(sync_key)
            if sync_key in existing_map:
                exist_obj: ServiceBase = existing_map[sync_key]
                if cls._diff_and_apply(exist_obj, record):
                    to_update.append(exist_obj)
            else:
                to_create.append(cls(**{k: v for k, v in record.items() if k in writable_fields}))

        to_delete_ids: list[int] = [obj.pk for key, obj in existing_map.items() if key not in incoming_keys]

        # 3. 仅在有实际写操作时才获取 username
        if to_create or to_update:
            username: str = get_request_username()
            for obj in to_create:
                obj.created_by = obj.updated_by = username
            for obj in to_update:
                obj.updated_by = username
                # bulk_update 不会触发 auto_now，需手动设置
                obj.updated_at = timezone.now()

        # 4. 执行批量操作
        if to_create:
            cls.objects.bulk_create(to_create, batch_size=100)
        if to_update:
            cls.objects.bulk_update(to_update, fields=cls.DEFAULT_KEYS + ["updated_by", "updated_at"], batch_size=100)
        if to_delete_ids and is_delete:
            cls.objects.filter(id__in=to_delete_ids).delete()
        else:
            to_delete_ids.clear()

        return {"created": len(to_create), "updated": len(to_update), "deleted": len(to_delete_ids)}


class CMDBServiceRelation(ServiceBase):
    template_id = models.BigIntegerField("服务模板ID")

    DIFF_KEYS: list[str] = []
    DEFAULT_KEYS: list[str] = ["template_id"]


class EventServiceRelation(ServiceBase):
    table = models.CharField(verbose_name="关联事件结果表", max_length=255, db_index=True)
    relations = models.JSONField(verbose_name="匹配规则", default=list)
    options = models.JSONField(verbose_name="事件选项", default=dict)

    DIFF_KEYS: list[str] = ["table"]
    DEFAULT_KEYS: list[str] = ["relations", "options"]

    @classmethod
    def fetch_relations(
        cls, bk_biz_id: int, app_name: str, service_names: list[str]
    ) -> dict[str, list[dict[str, Any]]]:
        """获取事件关联配置
        [
            {
                "table": "k8s_event",
                "relations": [
                    # 集群 / 命名空间 / Workload 类型 / Workload 名称
                    # case 1：勾选整个集群
                    {"bcs_cluster_id": "BCS-K8S-00000"},
                    # case 2：勾选整个 Namespace
                    {"bcs_cluster_id": "BCS-K8S-00000", "namespace": "blueking"},
                    # case 3：勾选整个 WorkloadType
                    {"bcs_cluster_id": "BCS-K8S-00000", "namespace": "blueking", "kind": "Deployment"},
                    # case 4：勾选 Workload
                    # Deployment 包括 Pod、HorizontalPodAutoscaler、ReplicaSet 事件
                    # DaemonSet / StatefulSet 包括 Pod
                    {
                        "bcs_cluster_id": "BCS-K8S-00000",
                        "namespace": "blueking",
                        "kind": "Deployment",
                        "name": "bk-monitor-api",
                    },
                ],
            },
            {
                "table": "system_event",
                "relations": [
                    {"bk_biz_id": self.bk_biz_id},
                ],
            },
        ]
        """
        service_table_options_map: dict[tuple[str, str], dict[str, Any]] = {}
        service_table_relations_map: dict[tuple[str, str], list[dict[str, Any]]] = {
            (service_name, EventCategory.SYSTEM_EVENT.value): [] for service_name in service_names
        }
        for relation in cls.get_relations(bk_biz_id, app_name, service_names):
            key: tuple[str, str] = (relation["service_name"], relation["table"])
            service_table_options_map[key] = relation["options"]
            service_table_relations_map.setdefault(key, []).extend(relation["relations"])

        # 去重
        for key in service_table_relations_map:
            duplicate_relation_tuples: set[frozenset] = {frozenset(r.items()) for r in service_table_relations_map[key]}
            service_table_relations_map[key] = [dict(relation_tuple) for relation_tuple in duplicate_relation_tuples]

        service_relations: dict[str, list[dict[str, Any]]] = {}
        for key, relations in service_table_relations_map.items():
            service_name, table = key
            service_relations.setdefault(service_name, []).append(
                {"table": table, "relations": relations, "options": service_table_options_map.get(key) or {}}
            )

        return service_relations


class LogServiceRelation(ServiceBase):
    log_type = models.CharField("日志类型", max_length=50, choices=ServiceRelationLogTypeChoices.choices())
    related_bk_biz_id = models.IntegerField("关联的业务id", null=True)
    # 已过时，不再使用
    value = models.CharField("日志值", max_length=512)
    # 需要保证value_list中的值是是 int 类型
    value_list = models.JSONField("日志值列表", default=list)

    DIFF_KEYS: list[str] = ["related_bk_biz_id"]
    DEFAULT_KEYS: list[str] = ["log_type", "value", "value_list"]

    @classmethod
    def filter_by_index_set_id(cls, index_set_id):
        """根据index_set_id过滤LogServiceRelation记录"""
        return cls.objects.filter(log_type=ServiceRelationLogTypeChoices.BK_LOG, value_list__contains=[index_set_id])


class AppServiceRelation(ServiceBase):
    relate_bk_biz_id = models.BigIntegerField("关联业务ID")
    relate_app_name = models.CharField("关联应用名称", max_length=50)

    DIFF_KEYS: list[str] = []
    DEFAULT_KEYS: list[str] = ["relate_bk_biz_id", "relate_app_name"]


class UriServiceRelation(ServiceBase):
    uri = models.CharField("Uri", max_length=512)
    rank = models.IntegerField("排序")

    DIFF_KEYS: list[str] = ["uri"]
    DEFAULT_KEYS: list[str] = ["rank"]


class ApdexServiceRelation(ServiceBase):
    """服务的apdex只能设置此服务类型的apdex"""

    apdex_key = models.CharField(max_length=32, verbose_name="apdex类型")
    apdex_value = models.IntegerField("apdex值")

    DIFF_KEYS: list[str] = ["apdex_key"]
    DEFAULT_KEYS: list[str] = ["apdex_value"]


class CodeRedefinedConfigRelation(ServiceBase):
    # 类型：caller / callee
    kind = models.CharField("类型", max_length=16, choices=[("caller", "主调"), ("callee", "被调")])
    # 被调服务（caller 时必填；callee 时必须与 service_name 一致）
    callee_server = models.CharField("被调服务", max_length=512, blank=True, default="")
    # 被调 Service
    callee_service = models.CharField("被调Service", max_length=512, blank=True, default="")
    # 被调接口（完整名称/路径，精确匹配）
    callee_method = models.CharField("被调接口", max_length=512, blank=True, default="")
    # 返回码重定义：原始字段直接落库，三组 code 列表，示例：{"success": "0", "exception": "3001,err_1", "timeout": "408"}
    code_type_rules = models.JSONField("重定义返回码分组信息", default=dict)
    # 是否启用
    enabled = models.BooleanField("是否启用", default=True)

    DIFF_KEYS: list[str] = ["kind", "callee_server", "callee_service", "callee_method"]
    DEFAULT_KEYS: list[str] = ["code_type_rules", "enabled"]

    class Meta:
        index_together = [
            [
                "bk_biz_id",
                "app_name",
                "service_name",
                "kind",
            ]
        ]

    def is_callee(self) -> bool:
        """判断是否为被调类型"""
        return self.kind == "callee"
