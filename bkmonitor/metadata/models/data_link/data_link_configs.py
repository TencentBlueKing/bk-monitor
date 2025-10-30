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
from typing import TYPE_CHECKING, Any, ClassVar

from django.conf import settings
from django.db import models
from typing_extensions import deprecated

from bkmonitor.utils.tenant import get_tenant_datalink_biz_id
from core.drf_resource import api
from metadata.models.data_link import constants, utils
from metadata.models.data_link.constants import DataLinkKind
from metadata.models.space.constants import LOG_EVENT_ETL_CONFIGS

logger = logging.getLogger("metadata")

if TYPE_CHECKING:
    from metadata.models.data_source import DataSource


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
    )

    kind = models.CharField(verbose_name="配置类型", max_length=64, choices=CONFIG_KIND_CHOICES)
    name = models.CharField(verbose_name="实例名称", max_length=64)
    namespace = models.CharField(
        verbose_name="命名空间", max_length=64, default=settings.DEFAULT_VM_DATA_LINK_NAMESPACE
    )
    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    last_modify_time = models.DateTimeField("最后更新时间", auto_now=True)
    status = models.CharField(verbose_name="状态", max_length=64)
    data_link_name = models.CharField(verbose_name="数据链路名称", max_length=64)
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
    name = models.CharField(verbose_name="数据源名称", max_length=64, db_index=True, unique=True)

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

    def compose_config(self, event_type="metric") -> dict:
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
                    "event_type": "{{event_type}}"
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
        }

        # 现阶段仅在多租户模式下添加tenant字段
        if settings.ENABLE_MULTI_TENANT_MODE:
            logger.info(
                "compose_v4_datalink_config: enable multi tenant mode,add bk_tenant_id->[%s],kind->[%s]",
                self.bk_tenant_id,
                self.kind,
            )
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
    name = models.CharField(verbose_name="结果表名称", max_length=64, db_index=True, unique=True)
    data_type = models.CharField(verbose_name="结果表类型", max_length=64, default="metric")

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
    name = models.CharField(verbose_name="存储配置名称", max_length=64, db_index=True, unique=True)
    es_cluster_name = models.CharField(verbose_name="ES集群名称", max_length=64)
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
            logger.info(
                "compose_v4_datalink_config: enable multi tenant mode,add bk_tenant_id->[%s],kind->[%s]",
                self.bk_tenant_id,
                self.kind,
            )
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
    name = models.CharField(verbose_name="存储配置名称", max_length=64, db_index=True, unique=True)
    vm_cluster_name = models.CharField(verbose_name="VM集群名称", max_length=64)

    class Meta:
        verbose_name = "VM存储配置"
        verbose_name_plural = verbose_name
        unique_together = (("bk_tenant_id", "namespace", "name"),)

    def compose_config(
        self,
    ) -> dict:
        """
        组装VM存储配置，与结果表相关联
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
                    "storage": {
                        "kind": "VmStorage",
                        "name": "{{vm_name}}",
                        {% if tenant %}
                        "tenant": "{{ tenant }}",
                        {% endif %}
                        "namespace": "{{namespace}}"
                    }
                }
            }
            """
        maintainer = settings.BK_DATA_PROJECT_MAINTAINER.split(",")

        render_params = {
            "name": self.name,
            "namespace": self.namespace,
            "bk_biz_id": self.datalink_biz_ids.label_biz_id,  # 数据实际归属的业务ID
            "rt_name": self.name,
            "vm_name": self.vm_cluster_name,
            "maintainers": json.dumps(maintainer),
        }

        # 现阶段仅在多租户模式下添加tenant字段
        if settings.ENABLE_MULTI_TENANT_MODE:
            logger.info(
                "compose_v4_datalink_config: enable multi tenant mode,add bk_tenant_id->[%s],kind->[%s]",
                self.bk_tenant_id,
                self.kind,
            )
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
    name = models.CharField(verbose_name="清洗任务名称", max_length=64, db_index=True, unique=True)
    data_id_name = models.CharField(verbose_name="关联消费数据源名称", max_length=64)

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
    ) -> dict:
        """
        组装清洗任务配置，需要声明 where -> how -> where
        需要注意：DataBusConfig和Sink的name需要相同
        @param data_id_name: 数据源名称 即从哪里读取数据
        @param sinks: 处理配置列表
        @param transform_kind: 转换类型
        @param transform_name: 转换名称
        @param transform_format: 转换格式
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
                        "kind": "{{transform_kind}}",
                        "name": "{{transform_name}}",
                        "format": "{{transform_format}}"
                    }
                ]
            }
        }
        """
        maintainer = settings.BK_DATA_PROJECT_MAINTAINER.split(",")
        render_params = {
            "name": self.name,
            "namespace": self.namespace,
            "bk_biz_id": self.datalink_biz_ids.label_biz_id,
            "sinks": json.dumps(sinks),
            "sink_name": self.name,
            "data_id_name": self.data_id_name,
            "transform_kind": transform_kind,
            "transform_name": transform_name,
            "transform_format": transform_format,
            "maintainers": json.dumps(maintainer),
        }

        # 现阶段仅在多租户模式下添加tenant字段
        if settings.ENABLE_MULTI_TENANT_MODE:
            logger.info(
                "compose_v4_datalink_config: enable multi tenant mode,add bk_tenant_id->[%s],kind->[%s]",
                self.bk_tenant_id,
                self.kind,
            )
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
            logger.info(
                "compose_v4_datalink_config: enable multi tenant mode,add bk_tenant_id->[%s],kind->[%s]",
                self.bk_tenant_id,
                self.kind,
            )
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
            logger.info(
                "compose_v4_datalink_config: enable multi tenant mode,add bk_tenant_id->[%s],kind->[%s]",
                self.bk_tenant_id,
                self.kind,
            )
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
    name = models.CharField(verbose_name="条件处理配置名称", max_length=64, db_index=True, unique=True)

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
            logger.info(
                "compose_v4_datalink_config: enable multi tenant mode,add bk_tenant_id->[%s],kind->[%s]",
                self.bk_tenant_id,
                self.kind,
            )
            render_params["tenant"] = self.bk_tenant_id

        return utils.compose_config(
            tpl=tpl,
            render_params=render_params,
            err_msg_prefix="compose vm conditional sink config",
        )


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
    name = models.CharField(verbose_name="Doris存储绑定配置名称", max_length=64, db_index=True, unique=True)

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
                "labels": {"bk_biz_id": "{{monitor_biz_id}}"}},
                "name": "{{name}}",
                "namespace": "{{namespace}}"
            },
            "spec": {
                "data": {
                    "name": "{{name}}",
                    "namespace": "{{namespace}}",
                    "kind": "ResultTable"
                },
                "storage": {
                    "name": "{{storage_cluster_name}}",
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
            "expires": expires,
            "flush_timeout": json.dumps(flush_timeout),
        }
        return utils.compose_config(
            tpl=tpl,
            render_params=render_params,
            err_msg_prefix="compose doris storage binding config",
        )


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
