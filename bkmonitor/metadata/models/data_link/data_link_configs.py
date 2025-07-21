"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import logging

from django.conf import settings
from django.db import models

from metadata.models.data_link import constants, utils
from metadata.models.data_link.constants import DataLinkKind

logger = logging.getLogger("metadata")


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
    bk_biz_id = models.BigIntegerField(verbose_name="业务ID", default=settings.DEFAULT_BKDATA_BIZ_ID)
    bk_tenant_id = models.CharField("租户ID", max_length=256, null=True, default="system")

    class Meta:
        abstract = True

    @property
    def component_status(self):
        """
        组件实时状态
        """
        from metadata.models.data_link.service import get_data_link_component_status

        return get_data_link_component_status(self.kind, self.name, self.namespace)

    @property
    def component_config(self):
        """
        组件完整配置（bkbase侧）
        """
        from metadata.models.data_link.service import get_data_link_component_config

        return get_data_link_component_config(kind=self.kind, namespace=self.namespace, component_name=self.name)

    @classmethod
    def compose_config(cls, *args, **kwargs):
        raise NotImplementedError


class DataIdConfig(DataLinkResourceConfigBase):
    """
    链路数据源配置
    """

    kind = DataLinkKind.DATAID.value
    name = models.CharField(verbose_name="数据源名称", max_length=64, db_index=True, unique=True)

    class Meta:
        verbose_name = "数据源配置"
        verbose_name_plural = verbose_name

    def compose_config(self) -> dict:
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
                    "maintainers": {{maintainers}}
                }
            }
            """
        maintainer = settings.BK_DATA_PROJECT_MAINTAINER.split(",")
        render_params = {
            "name": self.name,
            "namespace": self.namespace,
            "bk_biz_id": self.bk_biz_id,  # 数据实际归属的业务ID
            "monitor_biz_id": settings.DEFAULT_BKDATA_BIZ_ID,  # 接入者的业务ID
            "maintainers": json.dumps(maintainer),
        }

        # 现阶段仅在多租户模式下添加tenant字段
        if settings.ENABLE_MULTI_TENANT_MODE:
            logger.info(
                "compose_v4_datalink_config: enable multi tenant mode,add bk_tenant_id->[%s],kind->[%s]",
                self.bk_tenant_id,
                self.kind,
            )

        return utils.compose_config(
            tpl=tpl,
            render_params=render_params,
            err_msg_prefix="compose data_id config",
        )


class VMResultTableConfig(DataLinkResourceConfigBase):
    """
    链路VM结果表配置
    """

    kind = DataLinkKind.RESULTTABLE.value
    name = models.CharField(verbose_name="结果表名称", max_length=64, db_index=True, unique=True)
    data_type = models.CharField(verbose_name="结果表类型", max_length=64, default="metric")

    class Meta:
        verbose_name = "VM结果表配置"
        verbose_name_plural = verbose_name

    def compose_config(self) -> dict:
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
            "bk_biz_id": self.bk_biz_id,  # 数据实际归属的业务ID
            "monitor_biz_id": settings.DEFAULT_BKDATA_BIZ_ID,  # 接入者的业务ID
            "data_type": self.data_type,
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
            err_msg_prefix="compose bkdata table_id config",
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

    # TODO 多租户yaml改造
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
            "bk_biz_id": self.bk_biz_id,  # 数据实际归属的业务ID
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
            "bk_biz_id": self.bk_biz_id,  # 接入者的业务ID
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


class ConditionalSinkConfig(DataLinkResourceConfigBase):
    """
    条件处理配置
    """

    kind = DataLinkKind.CONDITIONALSINK.value
    name = models.CharField(verbose_name="条件处理配置名称", max_length=64, db_index=True, unique=True)

    class Meta:
        verbose_name = "条件处理配置"
        verbose_name_plural = verbose_name

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
            "bk_biz_id": self.bk_biz_id,
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
