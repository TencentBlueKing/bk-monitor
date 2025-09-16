"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any

from django.db import models

from apm_web.constants import ServiceRelationLogTypeChoices
from monitor_web.data_explorer.event.constants import EventCategory


class ServiceBase(models.Model):
    """服务基础信息"""

    bk_biz_id = models.BigIntegerField("业务ID")
    app_name = models.CharField("应用名称", max_length=50)
    service_name = models.CharField("服务名称", max_length=512)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)
    created_by = models.CharField("创建人", max_length=128, null=True)
    updated_by = models.CharField("更新人", max_length=128, null=True)

    class Meta:
        abstract = True
        index_together = [["bk_biz_id", "app_name", "service_name"]]


class CMDBServiceRelation(ServiceBase):
    template_id = models.BigIntegerField("服务模板ID")


class EventServiceRelation(ServiceBase):
    table = models.CharField(verbose_name="关联事件结果表", max_length=255, db_index=True)
    relations = models.JSONField(verbose_name="匹配规则", default=list)
    options = models.JSONField(verbose_name="事件选项", default=dict)

    @classmethod
    def fetch_relations(cls, bk_biz_id: int, app_name: str, service_name: str | None = None) -> list[dict[str, Any]]:
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
        filter_kwargs: dict[str, Any] = {"bk_biz_id": bk_biz_id, "app_name": app_name}
        if service_name:
            filter_kwargs["service_name"] = service_name

        table_options_map: dict[str, dict[str, Any]] = {}
        table_relations_map: dict[str, list[dict[str, Any]]] = {EventCategory.SYSTEM_EVENT.value: []}
        for relation in EventServiceRelation.objects.filter(**filter_kwargs).values("table", "relations", "options"):
            table_options_map[relation["table"]] = relation["options"]
            table_relations_map.setdefault(relation["table"], []).extend(relation["relations"])

        # 去重
        for table in table_relations_map:
            duplicate_relation_tuples: set[frozenset] = {frozenset(r.items()) for r in table_relations_map[table]}
            table_relations_map[table] = [dict(relation_tuple) for relation_tuple in duplicate_relation_tuples]

        return [
            {"table": table, "relations": relations, "options": table_options_map.get(table) or {}}
            for table, relations in table_relations_map.items()
        ]


class LogServiceRelation(ServiceBase):
    log_type = models.CharField("日志类型", max_length=50, choices=ServiceRelationLogTypeChoices.choices())
    related_bk_biz_id = models.IntegerField("关联的业务id", null=True)
    # 已过时，不再使用
    value = models.CharField("日志值", max_length=512)
    # 需要保证value_list中的值是是 int 类型
    value_list = models.JSONField("日志值列表", default=list)

    @classmethod
    def filter_by_index_set_id(cls, index_set_id):
        """根据index_set_id过滤LogServiceRelation记录"""
        return cls.objects.filter(log_type=ServiceRelationLogTypeChoices.BK_LOG, value_list__contains=[index_set_id])


class AppServiceRelation(ServiceBase):
    relate_bk_biz_id = models.BigIntegerField("关联业务ID")
    relate_app_name = models.CharField("关联应用名称", max_length=50)


class UriServiceRelation(ServiceBase):
    uri = models.CharField("Uri", max_length=512)
    rank = models.IntegerField("排序")


class ApdexServiceRelation(ServiceBase):
    """服务的apdex只能设置此服务类型的apdex"""

    apdex_key = models.CharField(max_length=32, verbose_name="apdex类型")
    apdex_value = models.IntegerField("apdex值")


class CodeRedefinedConfigRelation(ServiceBase):
    ret_code_as_exception = models.BooleanField("非 0 返回码是否当成异常", default=False)  # 待新下发实现后旧逻辑移除！
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

    class Meta:
        index_together = [
            [
                "bk_biz_id",
                "app_name",
                "service_name",
                "kind",
            ]
        ]
