"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import logging
from typing import TYPE_CHECKING, Any, ClassVar, Literal, cast

from django.conf import settings
from django.db import models
from typing_extensions import deprecated

from bkmonitor.utils.db.fields import SymmetricJsonField
from bkmonitor.utils.tenant import get_tenant_datalink_biz_id
from core.drf_resource import api
from metadata.models.data_link import constants, utils
from metadata.models.data_link.constants import BKBASE_NAMESPACE_BK_LOG, BKBASE_NAMESPACE_BK_MONITOR, DataLinkKind
from metadata.models.space.constants import LOG_EVENT_ETL_CONFIGS

logger = logging.getLogger("metadata")

if TYPE_CHECKING:
    from metadata.models.data_source import DataSource
    from metadata.models.storage import ClusterInfo


class DataLinkResourceConfigBase(models.Model):
    """
    数据链路资源配置基类
    """

    CONFIG_KIND_CHOICES = (
        (DataLinkKind.DATAID.value, "数据源"),
        (DataLinkKind.RESULTTABLE.value, "结果表"),
        (DataLinkKind.VMSTORAGEBINDING.value, "存储配置"),
        (DataLinkKind.DATABUS.value, "清洗任务"),
        (DataLinkKind.SINK.value, "清洗配置"),
        (DataLinkKind.CONDITIONALSINK.value, "过滤条件"),
        (DataLinkKind.BASEREPORTSINK.value, "基础采集清洗配置"),
    )

    kind = models.CharField(verbose_name="配置类型", max_length=64, choices=CONFIG_KIND_CHOICES)
    name = models.CharField(verbose_name="实例名称", max_length=64)
    namespace = models.CharField(
        verbose_name="命名空间", max_length=64, default=settings.DEFAULT_VM_DATA_LINK_NAMESPACE
    )
    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    last_modify_time = models.DateTimeField("最后更新时间", auto_now=True)
    status = models.CharField(verbose_name="状态", max_length=64)
    data_link_name = models.CharField(verbose_name="数据链路名称", max_length=64, blank=True)
    bk_biz_id = models.BigIntegerField(verbose_name="业务ID")
    bk_tenant_id: str = models.CharField("租户ID", max_length=256, null=True, default="system")  # pyright: ignore[reportAssignmentType]

    class Meta:
        abstract: ClassVar[bool] = True

    @property
    def component_status(self):
        """
        组件实时状态
        """
        from metadata.models.data_link.service import get_data_link_component_status

        return get_data_link_component_status(self.bk_tenant_id, self.kind, self.name, self.namespace)

    @property
    def component_config(self):
        """
        组件完整配置（bkbase侧）
        """
        from metadata.models.data_link.service import get_data_link_component_config

        return get_data_link_component_config(
            bk_tenant_id=self.bk_tenant_id,
            kind=self.kind,
            namespace=self.namespace,
            component_name=self.name,
        )

    @property
    def datalink_biz_ids(self):
        """
        数据链路业务ID
        """
        return get_tenant_datalink_biz_id(bk_tenant_id=self.bk_tenant_id, bk_biz_id=self.bk_biz_id)

    @classmethod
    def compose_config(cls, *args, **kwargs):
        raise NotImplementedError

    def delete_config(self):
        """删除数据链路配置"""
        api.bkdata.delete_data_link(
            bk_tenant_id=self.bk_tenant_id,
            kind=DataLinkKind.get_choice_value(self.kind),
            namespace=self.namespace,
            name=self.name,
        )
        self.delete()


class DataIdConfig(DataLinkResourceConfigBase):
    """
    链路数据源配置
    """

    kind = DataLinkKind.DATAID.value
    name = models.CharField(verbose_name="数据源名称", max_length=64, db_index=True)
    bk_data_id = models.IntegerField(verbose_name="数据源ID", default=0)

    class Meta:
        verbose_name = "数据源配置"
        verbose_name_plural = verbose_name
        unique_together = (("bk_tenant_id", "namespace", "name"),)

    def compose_predefined_config(self, data_source: "DataSource") -> dict[str, Any]:
        """
        组装预定义数据源配置
        """
        tpl = """
        {
            "kind": "DataId",
            "metadata": {
                "name": "{{name}}",
                {% if tenant %}
                "tenant": "{{ tenant }}",
                {% endif %}
                "namespace": "{{namespace}}",
                "labels": {"bk_biz_id": "{{bk_biz_id}}"}
            },
            "spec": {
                "alias": "{{name}}",
                "bizId": {{monitor_biz_id}},
                "description": "{{name}}",
                "maintainers": {{maintainers}},
                "predefined": {
                    "dataId": {{bk_data_id}},
                    "channel": {
                        "kind": "KafkaChannel",
                        {% if tenant %}
                        "tenant": "{{ tenant }}",
                        {% endif %}
                        "namespace": "{{namespace}}",
                        "name": "{{kafka_name}}"
                    },
                    "topic": "{{topic_name}}"
                },
                "eventType": "{{event_type}}"
            }
        }
        """
        maintainer = settings.BK_DATA_PROJECT_MAINTAINER.split(",")

        render_params = {
            "name": self.name,
            "namespace": self.namespace,
            "bk_biz_id": self.datalink_biz_ids.label_biz_id,  # 数据实际归属的业务ID
            "monitor_biz_id": self.datalink_biz_ids.data_biz_id,  # 接入者的业务ID
            "bk_data_id": data_source.bk_data_id,
            "topic_name": data_source.mq_config.topic,
            "kafka_name": data_source.mq_cluster.cluster_name,
            "maintainers": json.dumps(maintainer),
            "event_type": "log" if data_source.etl_config in LOG_EVENT_ETL_CONFIGS else "metric",
        }

        if settings.ENABLE_MULTI_TENANT_MODE:
            render_params["tenant"] = self.bk_tenant_id

        return utils.compose_config(
            tpl=tpl,
            render_params=render_params,
            err_msg_prefix="compose predefined data_id config",
        )

    def compose_config(self, event_type: str = "metric", prefer_kafka_cluster_name: str | None = None) -> dict:
        """
        数据源下发计算平台的资源配置
        """
        tpl = """
            {
                "kind": "DataId",
                "metadata": {
                    "name": "{{name}}",
                    "namespace": "{{namespace}}",
                    {% if tenant %}
                    "tenant": "{{ tenant }}",
                    {% endif %}
                    "labels": {"bk_biz_id": "{{bk_biz_id}}"}
                },
                "spec": {
                    "alias": "{{name}}",
                    "bizId": {{monitor_biz_id}},
                    "description": "{{name}}",
                    "maintainers": {{maintainers}},
                    {% if prefer_kafka_cluster_name %}
                    "preferCluster": {
                        "kind": "KafkaChannel",
                        {% if tenant %}
                        "tenant": "{{ tenant }}",
                        {% endif %}
                        "namespace": "{{namespace}}",
                        "name": "{{prefer_kafka_cluster_name}}"
                    },
                    {% endif %}
                    "eventType": "{{event_type}}"
                }
            }
            """
        maintainer = settings.BK_DATA_PROJECT_MAINTAINER.split(",")
        render_params = {
            "name": self.name,
            "namespace": self.namespace,
            "bk_biz_id": self.datalink_biz_ids.label_biz_id,  # 数据实际归属的业务ID
            "monitor_biz_id": self.datalink_biz_ids.data_biz_id,  # 接入者的业务ID
            "maintainers": json.dumps(maintainer),
            "event_type": event_type,
            "prefer_kafka_cluster_name": prefer_kafka_cluster_name,
        }

        # 现阶段仅在多租户模式下添加tenant字段
        if settings.ENABLE_MULTI_TENANT_MODE:
            render_params["tenant"] = self.bk_tenant_id

        return utils.compose_config(
            tpl=tpl,
            render_params=render_params,
            err_msg_prefix="compose data_id config",
        )


class ResultTableConfig(DataLinkResourceConfigBase):
    """
    链路VM结果表配置
    """

    kind = DataLinkKind.RESULTTABLE.value
    name = models.CharField(verbose_name="结果表名称", max_length=64, db_index=True)
    data_type = models.CharField(verbose_name="结果表类型", max_length=64, default="metric")
    table_id = models.CharField(verbose_name="结果表ID", max_length=255, default="", blank=True)
    bkbase_table_id = models.CharField(verbose_name="BKBase结果表ID", max_length=255, default="", blank=True)

    class Meta:
        verbose_name = "结果表配置"
        verbose_name_plural = verbose_name
        db_table = "metadata_vmresulttableconfig"
        unique_together = (("bk_tenant_id", "namespace", "name"),)

    def compose_config(self, fields: list[dict[str, Any]] | None = None) -> dict:
        """
        组装数据源结果表配置
        """
        tpl = """
            {
                "kind": "ResultTable",
                "metadata": {
                    "name": "{{name}}",
                    "namespace": "{{namespace}}",
                    {% if tenant %}
                    "tenant": "{{ tenant }}",
                    {% endif %}
                    "labels": {"bk_biz_id": "{{bk_biz_id}}"}
                },
                "spec": {
                    {% if fields %}
                    "fields": {{fields}},
                    {% endif %}
                    "alias": "{{name}}",
                    "bizId": {{monitor_biz_id}},
                    "dataType": "{{data_type}}",
                    "description": "{{name}}",
                    "maintainers": {{maintainers}}
                }
            }
            """
        maintainer = settings.BK_DATA_PROJECT_MAINTAINER.split(",")
        render_params = {
            "name": self.name,
            "namespace": self.namespace,
            "bk_biz_id": self.datalink_biz_ids.label_biz_id,  # 数据实际归属的业务ID
            "monitor_biz_id": self.datalink_biz_ids.data_biz_id,  # 接入者的业务ID
            "data_type": self.data_type,
            "maintainers": json.dumps(maintainer),
            "fields": json.dumps(fields, ensure_ascii=False) if fields else None,
        }

        # 现阶段仅在多租户模式下添加tenant字段
        if settings.ENABLE_MULTI_TENANT_MODE:
            render_params["tenant"] = self.bk_tenant_id

        return utils.compose_config(
            tpl=tpl,
            render_params=render_params,
            err_msg_prefix="compose bkdata es table_id config",
        )


class ESStorageBindingConfig(DataLinkResourceConfigBase):
    """
    链路ES结果表存储配置
    """

    kind = DataLinkKind.ESSTORAGEBINDING.value
    name = models.CharField(verbose_name="存储配置名称", max_length=64, db_index=True)
    es_cluster_name = models.CharField(verbose_name="ES集群名称", max_length=64)
    table_id = models.CharField(verbose_name="结果表ID", max_length=255, default="", blank=True)
    bkbase_result_table_name = models.CharField(verbose_name="BKBase结果表名称", max_length=255, default="")
    timezone = models.IntegerField("时区设置", default=0)

    class Meta:
        verbose_name = "ES存储配置"
        verbose_name_plural = verbose_name

    def compose_config(
        self,
        storage_cluster_name,
        write_alias_format,
        unique_field_list,
        json_field_list: list[str] | None = None,
    ):
        """
        结果表- ES存储关联关系
        在日志链路中,整套链路各个资源的name相同
        """
        tpl = """
            {
                "kind": "ElasticSearchBinding",
                "metadata": {
                    "name": "{{name}}",
                    {% if tenant %}
                    "tenant": "{{ tenant }}",
                    {% endif %}
                    "namespace": "{{namespace}}",
                    "labels": {"bk_biz_id": "{{bk_biz_id}}"}
                },
                "spec": {
                    "data": {
                        "kind": "ResultTable",
                        "name": "{{name}}",
                        {% if tenant %}
                        "tenant": "{{ tenant }}",
                        {% endif %}
                        "namespace": "{{namespace}}"
                    },
                    "storage": {
                        "kind": "ElasticSearch",
                        "namespace": "{{namespace}}",
                        {% if tenant %}
                        "tenant": "{{ tenant }}",
                        {% endif %}
                        "name": "{{storage_cluster_name}}"
                    },
                    "write_alias": {
                        "TimeBased": {
                            "format": "{{write_alias_format}}",
                            "timezone": {{timezone}}
                        }
                    },
                    "unique_field_list": {{unique_field_list}},
                    {% if json_field_list %}
                    "json_field_list": {{json_field_list}},
                    {% endif %}
                    "maintainers": {{maintainers}}
                }
            }
            """
        maintainer = settings.BK_DATA_PROJECT_MAINTAINER.split(",")
        render_params = {
            "name": self.name,
            "namespace": self.namespace,
            "bk_biz_id": self.datalink_biz_ids.label_biz_id,  # 数据实际归属的业务ID
            "storage_cluster_name": storage_cluster_name,
            "unique_field_list": json.dumps(unique_field_list),
            "write_alias_format": write_alias_format,
            "timezone": self.timezone,
            "maintainers": json.dumps(maintainer),
            "json_field_list": json.dumps(json_field_list) if json_field_list else None,
        }

        # 现阶段仅在多租户模式下添加tenant字段
        if settings.ENABLE_MULTI_TENANT_MODE:
            render_params["tenant"] = self.bk_tenant_id

        return utils.compose_config(
            tpl=tpl,
            render_params=render_params,
            err_msg_prefix="compose es storage binding config",
        )


class VMStorageBindingConfig(DataLinkResourceConfigBase):
    """
    链路VM结果表存储配置
    """

    kind = DataLinkKind.VMSTORAGEBINDING.value
    name = models.CharField(verbose_name="存储配置名称", max_length=64, db_index=True)
    vm_cluster_name = models.CharField(verbose_name="VM集群名称", max_length=64)
    bkbase_result_table_name = models.CharField(verbose_name="BKBase结果表名称", max_length=255, default="")
    table_id = models.CharField(verbose_name="结果表ID", max_length=255, default="", blank=True)

    class Meta:
        verbose_name = "VM存储配置"
        verbose_name_plural = verbose_name
        unique_together = (("bk_tenant_id", "namespace", "name"),)

    def compose_config(
        self,
        whitelist: dict[Literal["metrics", "tags"], list[str]] | None = None,
        bk_data_id: int | str | None = None,
        rt_name: str | None = None,
    ) -> dict[str, Any]:
        """
        组装VM存储配置，与结果表相关联

        :param rt_name: 关联的 ResultTable 名称。默认沿用 ``self.name`` 以保持
            "binding 与 RT 同名"的历史约定；当上层开启了组件复用、binding 与 RT
            的 name 已被各自独立 claim/复用时，必须由调用方显式传入
            ``vm_table_id_ins.name``，否则 payload 里 ``spec.data.name`` 会指向
            一个并不存在的 ResultTable，造成 BKBase 侧引用失效。
        """
        tpl = """
            {
                "kind": "VmStorageBinding",
                "metadata": {
                    "name": "{{name}}",
                    {% if tenant %}
                    "tenant": "{{ tenant }}",
                    {% endif %}
                    "namespace": "{{namespace}}",
                    "labels": {"bk_biz_id": "{{bk_biz_id}}"}
                },
                "spec": {
                    "data": {
                        "kind": "ResultTable",
                        "name": "{{rt_name}}",
                        {% if tenant %}
                        "tenant": "{{ tenant }}",
                        {% endif %}
                        "namespace": "{{namespace}}"
                    },
                    "maintainers": {{maintainers}},
                    {% if whitelist_config %}
                    "filter": {{whitelist_config}},
                    {% endif %}
                    "storage": {
                        "kind": "VmStorage",
                        "name": "{{vm_name}}",
                        {% if tenant %}
                        "tenant": "{{ tenant }}",
                        {% endif %}
                        "namespace": "{{namespace}}"
                    }
                    {% if metric_group_dimensions %},
                    "metricGroupDimensions": {{metric_group_dimensions}}
                    {% endif %}
                    {% if dd_version %},
                    "ddVersion": "{{dd_version}}"
                    {% endif %}
                }
            }
            """
        maintainer = settings.BK_DATA_PROJECT_MAINTAINER.split(",")

        # 白名单配置
        whitelist_config: str | None = None
        if whitelist and whitelist.get("metrics"):
            metrics = whitelist["metrics"]
            tags = whitelist.get("tags") or []
            whitelist_config = json.dumps(
                {
                    "kind": "Whitelist",
                    "metrics": metrics,
                    "tags": tags,
                }
            )

        render_params = {
            "name": self.name,
            "namespace": self.namespace,
            "bk_biz_id": self.datalink_biz_ids.label_biz_id,  # 数据实际归属的业务ID
            "rt_name": rt_name if rt_name is not None else self.name,
            "vm_name": self.vm_cluster_name,
            "maintainers": json.dumps(maintainer),
            "whitelist_config": whitelist_config,
        }

        if bk_data_id:
            # TimeSeriesGroup 中存在metric_group_dimensions才使用 v2 的 vmstoragebinding 配置
            from metadata.models.custom_report.time_series import TimeSeriesGroup

            ts_group = TimeSeriesGroup.objects.filter(bk_data_id=bk_data_id, is_delete=False).first()
            if ts_group and ts_group.metric_group_dimensions:
                metric_group_dimensions = []
                for dim in ts_group.metric_group_dimensions:
                    key = dim.get("key")
                    if not key:
                        continue
                    if "default_value" in dim and dim["default_value"] is not None:
                        metric_group_dimensions.append(f"{key}|{dim['default_value']}")
                    else:
                        metric_group_dimensions.append(key)
                render_params["metric_group_dimensions"] = json.dumps(metric_group_dimensions)
                render_params["dd_version"] = "v2"

        # 现阶段仅在多租户模式下添加tenant字段
        if settings.ENABLE_MULTI_TENANT_MODE:
            render_params["tenant"] = self.bk_tenant_id

        return utils.compose_config(
            tpl=tpl,
            render_params=render_params,
            err_msg_prefix="compose vm storage binding config",
        )


class DataBusConfig(DataLinkResourceConfigBase):
    """
    链路清洗任务配置
    """

    kind = DataLinkKind.DATABUS.value
    name = models.CharField(verbose_name="清洗任务名称", max_length=64, db_index=True)
    data_id_name = models.CharField(verbose_name="关联消费数据源名称", max_length=64)
    bk_data_id = models.IntegerField(verbose_name="数据源ID", default=0)
    sink_names = models.JSONField(verbose_name="处理配置列表", default=list, help_text="格式为kind:name，便于检索")

    class Meta:
        verbose_name = "清洗任务配置"
        verbose_name_plural = verbose_name
        unique_together = (("bk_tenant_id", "namespace", "name"),)

    def compose_config(
        self,
        sinks: list,
        transform_kind: str | None = constants.DEFAULT_METRIC_TRANSFORMER_KIND,
        transform_name: str | None = constants.DEFAULT_METRIC_TRANSFORMER,
        transform_format: str | None = constants.DEFAULT_METRIC_TRANSFORMER_FORMAT,
        transform_options: dict[str, Any] | None = None,
    ) -> dict:
        """
        组装清洗任务配置，需要声明 where -> how -> where
        需要注意：DataBusConfig和Sink的name需要相同
        @param data_id_name: 数据源名称 即从哪里读取数据
        @param sinks: 处理配置列表
        @param transform_kind: 转换类型
        @param transform_name: 转换名称
        @param transform_format: 转换格式
        @param transform_options: 转换额外配置
        """
        tpl = """
        {
            "kind": "Databus",
            "metadata": {
                "name": "{{name}}",
                {% if tenant %}
                "tenant": "{{ tenant }}",
                {% endif %}
                "namespace": "{{namespace}}",
                "labels": {"bk_biz_id": "{{bk_biz_id}}"}
            },
            "spec": {
                "maintainers": {{maintainers}},
                "sinks": {{sinks}},
                "sources": [
                    {
                        "kind": "DataId",
                        "name": "{{data_id_name}}",
                        {% if tenant %}
                        "tenant": "{{ tenant }}",
                        {% endif %}
                        "namespace": "{{namespace}}"
                    }
                ],
                "transforms": [
                    {{transform}}
                ]
            }
        }
        """
        maintainer = settings.BK_DATA_PROJECT_MAINTAINER.split(",")
        transform = {
            "kind": transform_kind,
            "name": transform_name,
            "format": transform_format,
        }
        if transform_options:
            transform.update(transform_options)
        render_params = {
            "name": self.name,
            "namespace": self.namespace,
            "bk_biz_id": self.datalink_biz_ids.label_biz_id,
            "sinks": json.dumps(sinks),
            "sink_name": self.name,
            "data_id_name": self.data_id_name,
            "transform": json.dumps(transform),
            "maintainers": json.dumps(maintainer),
        }

        # 现阶段仅在多租户模式下添加tenant字段
        if settings.ENABLE_MULTI_TENANT_MODE:
            render_params["tenant"] = self.bk_tenant_id

        return utils.compose_config(
            tpl=tpl,
            render_params=render_params,
            err_msg_prefix="compose vm databus config",
        )

    def compose_log_config(self, sinks: list[dict[str, Any]], rules: list[dict[str, Any]]) -> dict[str, Any]:
        """
        常规日志清洗总线配置
        """
        tpl = """
        {
            "kind": "Databus",
            "metadata": {
                "name": "{{name}}",
                {% if tenant %}
                "tenant": "{{ tenant }}",
                {% endif %}
                "namespace": "{{namespace}}",
                "labels": {"bk_biz_id": "{{bk_biz_id}}"}
            },
            "spec": {
                "maintainers": {{maintainers}},
                "sinks": {{sinks}},
                "sources": [
                    {
                        "kind": "DataId",
                        "name": "{{data_id_name}}",
                        {% if tenant %}
                        "tenant": "{{ tenant }}",
                        {% endif %}
                        "namespace": "{{namespace}}"
                    }
                ],
                "transforms": [
                    {
                        "kind": "Clean",
                        "rules": {{rules}},
                        "filter_rules": "True",
                        "context_map": {
                            "use_default_value": "__parse_failure"
                        }
                    }
                ]
            }
        }
        """
        maintainer = settings.BK_DATA_PROJECT_MAINTAINER.split(",")
        render_params = {
            "name": self.name,
            "namespace": self.namespace,
            "bk_biz_id": self.datalink_biz_ids.label_biz_id,  # 数据实际归属的业务ID
            "maintainers": json.dumps(maintainer),
            "sinks": json.dumps(sinks),
            "rules": json.dumps(rules),
            "data_id_name": self.data_id_name,
        }

        # 现阶段仅在多租户模式下添加tenant字段
        if settings.ENABLE_MULTI_TENANT_MODE:
            render_params["tenant"] = self.bk_tenant_id

        return utils.compose_config(
            tpl=tpl,
            render_params=render_params,
            err_msg_prefix="compose data_id config",
        )

    def compose_base_event_config(self):
        """
        基础事件清洗总线配置（固定逻辑）
        原先的1000 基础事件
        链路的各个环节的组件name一致
        """
        tpl = """
            {
                "kind": "Databus",
                "metadata": {
                    "name": "{{name}}",
                    {% if tenant %}
                    "tenant": "{{ tenant }}",
                    {% endif %}
                    "namespace": "{{namespace}}",
                    "labels": {"bk_biz_id": "{{bk_biz_id}}"}
                },
                "spec": {
                    "maintainers": {{maintainers}},
                    "sinks": [{
                        "kind": "ElasticSearchBinding",
                        "name": "{{name}}",
                        {% if tenant %}
                        "tenant": "{{ tenant }}",
                        {% endif %}
                        "namespace": "{{namespace}}"
                    }],
                    "sources": [{
                        "kind": "DataId",
                        "name": "{{name}}",
                        {% if tenant %}
                        "tenant": "{{ tenant }}",
                        {% endif %}
                        "namespace": "{{namespace}}"
                    }],
                    "transforms": [{
                        "kind": "PreDefinedLogic",
                        "name":"gse_system_event"
                    }]
                }
            }
            """
        maintainer = settings.BK_DATA_PROJECT_MAINTAINER.split(",")
        render_params = {
            "name": self.name,
            "namespace": self.namespace,
            "bk_biz_id": self.datalink_biz_ids.label_biz_id,  # 数据实际归属的业务ID
            "maintainers": json.dumps(maintainer),
        }

        # 现阶段仅在多租户模式下添加tenant字段
        if settings.ENABLE_MULTI_TENANT_MODE:
            render_params["tenant"] = self.bk_tenant_id

        return utils.compose_config(
            tpl=tpl,
            render_params=render_params,
            err_msg_prefix="compose data_id config",
        )


class ConditionalSinkConfig(DataLinkResourceConfigBase):
    """
    条件处理配置
    """

    kind = DataLinkKind.CONDITIONALSINK.value
    name = models.CharField(verbose_name="条件处理配置名称", max_length=64, db_index=True)

    class Meta:
        verbose_name = "条件处理配置"
        verbose_name_plural = verbose_name
        unique_together = (("bk_tenant_id", "namespace", "name"),)

    def compose_conditional_sink_config(self, conditions: list) -> dict:
        """
        组装条件处理配置
        @param conditions: 条件列表
        """
        tpl = """
        {
            "kind": "ConditionalSink",
            "metadata": {
                "namespace": "{{namespace}}",
                "name": "{{name}}",
                {% if tenant %}
                "tenant": "{{ tenant }}",
                {% endif %}
                "labels": {"bk_biz_id": "{{bk_biz_id}}"}
            },
            "spec": {
                "conditions": {{conditions}}
            }
        }
        """

        render_params = {
            "name": self.name,
            "namespace": settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
            "bk_biz_id": self.datalink_biz_ids.label_biz_id,  # 数据实际归属的业务ID
            "conditions": json.dumps(conditions),
        }

        # 现阶段仅在多租户模式下添加tenant字段
        if settings.ENABLE_MULTI_TENANT_MODE:
            render_params["tenant"] = self.bk_tenant_id

        return utils.compose_config(
            tpl=tpl,
            render_params=render_params,
            err_msg_prefix="compose vm conditional sink config",
        )


class BasereportSinkConfig(DataLinkResourceConfigBase):
    """
    基础采集处理配置
    """

    kind = DataLinkKind.BASEREPORTSINK.value
    name = models.CharField(verbose_name="基础采集处理配置名称", max_length=64, db_index=True)
    vm_storage_binding_names = models.JSONField(verbose_name="VM 存储绑定名称列表", default=list)
    result_table_ids = models.JSONField(verbose_name="结果表 ID 列表", default=list)

    class Meta:
        verbose_name = "基础采集处理配置"
        verbose_name_plural = verbose_name
        unique_together = (("bk_tenant_id", "namespace", "name"),)

    def compose_config(self, vmrt_prefix: str, include_cmdb: bool = False) -> dict[str, Any]:
        """组装基础采集处理配置。"""
        mappings: list[dict[str, Any]] = []
        for usage in constants.BASEREPORT_USAGES:
            vmrt_name = f"{vmrt_prefix}_{usage}" if vmrt_prefix else usage
            sink_config = {
                "kind": DataLinkKind.VMSTORAGEBINDING.value,
                "name": vmrt_name,
                "namespace": settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
            }
            if settings.ENABLE_MULTI_TENANT_MODE:
                sink_config["tenant"] = self.bk_tenant_id
            mappings.append(
                {
                    "metric_type": usage,
                    "sinks": [sink_config],
                }
            )
            if include_cmdb:
                cmdb_sink_config = {
                    "kind": DataLinkKind.VMSTORAGEBINDING.value,
                    "name": f"{vmrt_name}_cmdb",
                    "namespace": settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
                }
                if settings.ENABLE_MULTI_TENANT_MODE:
                    cmdb_sink_config["tenant"] = self.bk_tenant_id
                mappings.append({"metric_type": f"{usage}_cmdb", "sinks": [cmdb_sink_config]})

        metadata = {
            "name": self.name,
            "namespace": settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
            "labels": {"bk_biz_id": str(self.datalink_biz_ids.label_biz_id)},
        }
        if settings.ENABLE_MULTI_TENANT_MODE:
            metadata["tenant"] = self.bk_tenant_id

        return {
            "kind": self.kind,
            "metadata": metadata,
            "spec": {"mappings": mappings},
        }


class DorisStorageBindingConfig(DataLinkResourceConfigBase):
    """
    Doris存储绑定配置

    storage_config: [
        "table_type", // primary_table, duplicate_table
        "db", // 集群？
        "table",
        "storage_keys", // 唯一键？
        "json_fields", // JSON字段
        "original_json_fields",
        "field_config_group", // 字段配置，search_en: ["log"]
        "expires", // 保留时间, 7d, 30d
        "is_profiling", // 是否为profiling, true/false
        "unique_partition_table", // 是否为unique partition table, true/false
        "sample_table_name", // 采样表名
        "label_table_name", // 标签表名
        "flush_timeout", // 刷新时间
    ]
    """

    kind = DataLinkKind.DORISBINDING.value
    name = models.CharField(verbose_name="Doris存储绑定配置名称", max_length=64, db_index=True)
    table_id = models.CharField(verbose_name="结果表ID", max_length=255, default="", blank=True)
    bkbase_result_table_name = models.CharField(verbose_name="BKBase结果表名称", max_length=255, default="")
    doris_cluster_name = models.CharField(verbose_name="Doris集群名称", max_length=255, default="")

    class Meta:
        verbose_name: ClassVar[str] = "Doris存储绑定配置"
        verbose_name_plural = verbose_name
        unique_together = (("bk_tenant_id", "namespace", "name"),)

    def compose_config(
        self,
        storage_cluster_name: str,
        storage_keys: list[str],
        json_fields: list[str],
        field_config_group: dict[str, Any],
        original_json_fields: list[str],
        expires: str,
        flush_timeout: int | None,
    ) -> dict[str, Any]:
        """
        组装Doris存储绑定配置
        """
        tpl = """
        {
            "kind": "DorisBinding",
            "metadata": {
                {% if tenant %}
                "tenant": "{{ tenant }}",
                {% endif %}
                "labels": {"bk_biz_id": "{{monitor_biz_id}}"},
                "name": "{{name}}",
                "namespace": "{{namespace}}"
            },
            "spec": {
                "data": {
                    "name": "{{name}}",
                    {% if tenant %}
                    "tenant": "{{ tenant }}",
                    {% endif %}
                    "namespace": "{{namespace}}",
                    "kind": "ResultTable"
                },
                "storage": {
                    "name": "{{storage_cluster_name}}",
                    {% if tenant %}
                    "tenant": "{{ tenant }}",
                    {% endif %}
                    "namespace": "{{namespace}}",
                    "kind": "Doris"
                },
                "storage_config": {
                    "table_type": "primary_table",
                    "is_profiling": false,
                    "unique_partition_table": true,
                    "db": "mapleleaf_{{bk_biz_id}}",
                    "table": "{{name}}_{{bk_biz_id}}",
                    "storage_keys": {{storage_keys}},
                    "json_fields": {{json_fields}},
                    "original_json_fields": {{original_json_fields}},
                    "field_config_group": {{field_config_group}},
                    "expires": "{{expires}}",
                    "flush_timeout": {{flush_timeout}}
                }
            }
        }
        """

        render_params = {
            "name": self.name,
            "namespace": self.namespace,
            "bk_biz_id": self.datalink_biz_ids.data_biz_id,
            "monitor_biz_id": self.datalink_biz_ids.label_biz_id,
            "storage_cluster_name": storage_cluster_name,
            "storage_keys": json.dumps(storage_keys),
            "json_fields": json.dumps(json_fields),
            "field_config_group": json.dumps(field_config_group),
            "original_json_fields": json.dumps(original_json_fields),
            "expires": expires,
            "flush_timeout": json.dumps(flush_timeout),
        }

        # 现阶段仅在多租户模式下添加tenant字段
        if settings.ENABLE_MULTI_TENANT_MODE:
            render_params["tenant"] = self.bk_tenant_id

        return utils.compose_config(
            tpl=tpl,
            render_params=render_params,
            err_msg_prefix="compose doris storage binding config",
        )


class ClusterConfig(models.Model):
    """
    集群信息配置
    """

    # 由于配置原因，namespace实际上与存储类型是绑定的，与实际的使用方无关
    KIND_TO_NAMESPACES_MAP = {
        DataLinkKind.ELASTICSEARCH.value: [BKBASE_NAMESPACE_BK_LOG],
        DataLinkKind.VMSTORAGE.value: [BKBASE_NAMESPACE_BK_MONITOR],
        DataLinkKind.DORIS.value: [BKBASE_NAMESPACE_BK_LOG],
        # Kafka集群需要同时注册到bkmonitor和bklog命名空间
        DataLinkKind.KAFKACHANNEL.value: [BKBASE_NAMESPACE_BK_LOG, BKBASE_NAMESPACE_BK_MONITOR],
    }

    CLUSTER_TYPE_TO_KIND_MAP = {
        "elasticsearch": DataLinkKind.ELASTICSEARCH.value,
        "victoria_metrics": DataLinkKind.VMSTORAGE.value,
        "doris": DataLinkKind.DORIS.value,
        "kafka": DataLinkKind.KAFKACHANNEL.value,
    }

    bk_tenant_id = models.CharField(max_length=255, verbose_name="租户ID")
    namespace = models.CharField(max_length=255, verbose_name="命名空间")
    name = models.CharField(max_length=255, verbose_name="集群名称")
    kind = models.CharField(max_length=255, verbose_name="集群类型")
    origin_config = SymmetricJsonField(verbose_name="原始配置", default=dict)
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    update_time = models.DateTimeField(auto_now=True, verbose_name="最后更新时间")

    class Meta:
        verbose_name = "集群配置"
        verbose_name_plural = verbose_name
        unique_together = (("bk_tenant_id", "namespace", "kind", "name"),)

    @property
    def component_config(self):
        """
        组件完整配置（bkbase侧）
        """
        from metadata.models.data_link.service import get_data_link_component_config

        return get_data_link_component_config(
            bk_tenant_id=self.bk_tenant_id,
            kind=self.kind,
            namespace=self.namespace,
            component_name=self.name,
        )

    def get_cluster(self) -> "ClusterInfo":
        """获取集群信息"""
        from metadata.models.storage import ClusterInfo

        # 将 kind 映射回 cluster_type，需反向映射 CLUSTER_TYPE_TO_KIND_MAP
        kind_to_cluster_type: dict[str, str] = {v: k for k, v in self.CLUSTER_TYPE_TO_KIND_MAP.items()}
        cluster_type: str | None = kind_to_cluster_type.get(self.kind)
        if not cluster_type:
            raise ValueError(f"不支持的集群类型: {self.kind}")
        return ClusterInfo.objects.get(
            bk_tenant_id=self.bk_tenant_id,
            cluster_type=cluster_type,
            cluster_name=self.name,
        )

    def compose_config(self) -> dict[str, Any]:
        """
        组装集群配置
        """
        cluster = self.get_cluster()

        if self.kind == DataLinkKind.ELASTICSEARCH.value:
            return self.compose_es_config(cluster)
        elif self.kind == DataLinkKind.KAFKACHANNEL.value:
            return self.compose_kafka_config(cluster)
        else:
            raise ValueError(f"不支持的集群类型: {self.kind}")

    def compose_kafka_config(self, cluster: "ClusterInfo") -> dict[str, Any]:
        """组装Kafka集群配置

        配置示例:
        {
            "kind": "KafkaChannel",
            "metadata": {
                "tenant": "default",
                "namespace": "bkmonitor",
                "name": "kafka_cluster1",
                "labels": {},
                "annotations": {
                    "StreamToId": "1034" // 可能不存在
                }
            },
            "spec": {
                "host": "kafka.db",
                "port": 9092,
                "role": "outer", // inner/outer
                "streamToId": 1034, // 可能为0或None，可能不存在
                "v3ChannelId": 1, // 可能为None或不存在
                "version": "2.4.x", // 可能为None或不存在
                "auth": { // 可能为None或不存在
                    "sasl": {"enabled": false, "username": "xxxx", "password": "xxx", "mechanisms": ""}
                }
            },
            "status": {
                "phase": "Ok",
                "start_time": "2024-04-24 06:52:51.558663447 UTC",
                "update_time": "2024-04-24 06:52:52.896714120 UTC",
                "message": ""
            }
        }

        说明: streamToId/v3ChannelId/auth/version可能不存在或为None

        Args:
            cluster: 集群信息

        Returns:
            dict[str, Any]: Kafka集群配置
        """
        config = {
            "kind": DataLinkKind.KAFKACHANNEL.value,
            "metadata": {
                "namespace": self.namespace,
                "name": cluster.cluster_name,
                "annotations": {"display_name": cluster.display_name or cluster.cluster_name},
            },
            "spec": {
                "host": cluster.domain_name,
                "port": cluster.port,
                "role": "outer",
            },
        }

        if cluster.gse_stream_to_id != -1:
            config["metadata"]["annotations"]["StreamToId"] = str(cluster.gse_stream_to_id)
            config["spec"]["streamToId"] = cluster.gse_stream_to_id

        default_settings = cast(dict[str, Any] | None, cluster.default_settings)
        if default_settings and default_settings.get("v3_channel_id"):
            config["spec"]["v3ChannelId"] = default_settings["v3_channel_id"]
        if default_settings and default_settings.get("version"):
            config["spec"]["version"] = default_settings["version"]

        if cluster.is_auth or cluster.username:
            config["spec"]["auth"] = {
                "sasl": {
                    "enabled": cluster.is_auth,
                    "username": cluster.username,
                    "password": cluster.password,
                    "mechanism": cluster.sasl_mechanisms,
                }
            }

        if settings.ENABLE_MULTI_TENANT_MODE:
            config["metadata"]["tenant"] = cluster.bk_tenant_id

        return config

    def compose_es_config(self, cluster: "ClusterInfo") -> dict[str, Any]:
        """组装ES集群配置

        配置示例:
        {
            "kind": "ElasticSearch",
            "metadata": {
                "tenant": "default",
                "namespace": "bklog",
                "name": "es_cluster",
                "labels": {},
                "annotations": {}
            },
            "spec": {
                "host": "es.db",
                "port": 9200,
                "user": "xxxx",
                "password": "xxx"
            },
            "status": {
                "phase": "Ok",
                "start_time": "2025-12-11 07:01:48.141601176 UTC",
                "update_time": "2025-12-11 07:01:50.855429609 UTC",
                "message": ""
            }
        }

        Args:
            cluster: 集群信息

        Returns:
            dict[str, Any]: 集群配置
        """

        config = {
            "kind": DataLinkKind.ELASTICSEARCH.value,
            "metadata": {
                "namespace": self.namespace,
                "name": cluster.cluster_name,
            },
            "spec": {
                "host": cluster.domain_name,
                "port": cluster.port,
                "user": cluster.username,
                "password": cluster.password,
            },
        }

        if settings.ENABLE_MULTI_TENANT_MODE:
            config["metadata"]["tenant"] = cluster.bk_tenant_id

        return config

    @classmethod
    def sync_cluster_config(cls, cluster: "ClusterInfo", sync_namespaces: list[str] | None = None) -> None:
        """
        同步集群配置

        Note:
            将集群信息同步到bkbase平台，并更新集群注册状态
            如果集群类型不在支持的类型中，则不需要进行同步

        Args:
            cluster: 集群信息
            sync_namespaces: 指定同步的命名空间列表
        """

        # 根据集群类型获取kind和namespace
        kind = cls.CLUSTER_TYPE_TO_KIND_MAP[cluster.cluster_type]
        namespaces = cls.KIND_TO_NAMESPACES_MAP[kind]

        # 获取或创建bkbase集群配置记录
        for namespace in namespaces:
            # 如果指定同步的命名空间列表不为空，则只同步指定的命名空间
            if sync_namespaces and namespace not in sync_namespaces:
                continue

            cluster_config, _ = ClusterConfig.objects.get_or_create(
                bk_tenant_id=cluster.bk_tenant_id, namespace=namespace, name=cluster.cluster_name, kind=kind
            )

            # 组装配置
            config = cluster_config.compose_config()

            # 注册到bkbase平台
            try:
                api.bkdata.apply_data_link(config=[config], bk_tenant_id=cluster.bk_tenant_id)
            except Exception as e:
                logger.error(f"sync_cluster_config: apply data link error: {e}")
                raise e

            # 更新集群注册状态
            cluster_config.origin_config = config
            cluster_config.save()

        cluster.registered_to_bkbase = True
        cluster.save()

    def delete_config(self):
        """删除数据链路配置"""
        api.bkdata.delete_data_link(
            bk_tenant_id=self.bk_tenant_id,
            kind=DataLinkKind.get_choice_value(self.kind),
            namespace=self.namespace,
            name=self.name,
        )
        self.delete()


@deprecated("已废弃，统一使用DataBusConfig替代")
class LogDataBusConfig(DataLinkResourceConfigBase):
    """
    日志/事件/Trace 等非时序链路清洗总线配置
    """

    kind = DataLinkKind.DATABUS.value
    name = models.CharField(verbose_name="清洗任务名称", max_length=64, db_index=True, unique=True)
    data_id_name = models.CharField(verbose_name="关联消费数据源名称", max_length=64)

    class Meta:
        verbose_name = "非指标数据清洗总线配置"
        verbose_name_plural = verbose_name


@deprecated("已废弃，统一使用ResultTableConfig替代")
class LogResultTableConfig(DataLinkResourceConfigBase):
    """
    日志链路结果表配置（已废弃）
    """

    kind = DataLinkKind.RESULTTABLE.value
    name = models.CharField(verbose_name="结果表名称", max_length=64, db_index=True, unique=True)
    data_type = models.CharField(verbose_name="结果表类型", max_length=64, default="log")

    class Meta:
        verbose_name = "日志结果表配置"
        verbose_name_plural = verbose_name
        unique_together = (("bk_tenant_id", "namespace", "name"),)


# 组件类映射
COMPONENT_CLASS_MAP: dict[str, type[DataLinkResourceConfigBase]] = {
    DataLinkKind.DATAID.value: DataIdConfig,
    DataLinkKind.RESULTTABLE.value: ResultTableConfig,
    DataLinkKind.VMSTORAGEBINDING.value: VMStorageBindingConfig,
    DataLinkKind.ESSTORAGEBINDING.value: ESStorageBindingConfig,
    DataLinkKind.DORISBINDING.value: DorisStorageBindingConfig,
    DataLinkKind.DATABUS.value: DataBusConfig,
    DataLinkKind.CONDITIONALSINK.value: ConditionalSinkConfig,
    DataLinkKind.BASEREPORTSINK.value: BasereportSinkConfig,
}
