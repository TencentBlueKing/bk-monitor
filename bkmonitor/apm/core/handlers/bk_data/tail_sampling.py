"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
import json
import os
import time
from json import JSONDecodeError

from django.conf import settings
from django.utils import timezone

from apm.core.handlers.bk_data.constants import FlowStatus
from apm.core.handlers.bk_data.flow import ApmFlow
from apm.models import TraceDataSource
from bkmonitor.dataflow.task.apm_tail_sampling import APMTailSamplingTask, TailSamplingFlinkNode
from constants.apm import FlowType, normalize_app_name
from core.drf_resource import api
from metadata.models import ClusterInfo, DataIdConfig, ResultTableOption
from metadata.models.data_link.constants import BKBASE_NAMESPACE_BK_LOG, DataLinkResourceStatus
from metadata.models.data_link.data_link import DataLink


class TailSamplingFlow(ApmFlow):
    """APM Trace 尾部采样 Flow。"""

    _NAME = "apmTailSamplingFlow"
    _FLOW = APMTailSamplingTask
    _FLOW_TYPE = FlowType.TAIL_SAMPLING.value
    # Flow入库的ES存储资源命名格式
    _BKDATA_ES_CLUSTER_NAME_FORMAT = "apm_storage_{cluster_name}"
    _BKDATA_ES_CLUSTER_ID_FORMAT = "apm_storage_id_{cluster_id}"
    _FLINK_CODE_FILENAME = os.path.join(settings.BASE_DIR, "apm/core/handlers/bk_data/tail_sampling_flink.java")
    # bkbase dataId直连方式接入用到的场景ID 为协商的固定值
    _BKDATA_CUSTOM_SCENARIO_ID = 47
    _STORAGE_REGISTRY_AREA_CODE = settings.APM_APP_BKDATA_STORAGE_REGISTRY_AREA_CODE
    # Flow 的命名空间对应 BKBase 项目名。
    _FLOW_NAMESPACE_FORMAT = "project_v3_{project_id}"
    _V4_FLOW_ES_REPLICAS = 1
    # V4 尾部采样资源状态轮询参数。
    _V4_RESOURCE_WAIT_SECONDS = 500
    _V4_POLL_INTERVAL_SECONDS = 10

    def __init__(self, trace_datasource, config):
        super().__init__(trace_datasource.bk_biz_id, trace_datasource.app_name, trace_datasource.bk_data_id, config)

    @property
    def bkbase_project_id(self):
        return settings.APM_APP_BKDATA_TAIL_SAMPLING_PROJECT_ID

    @property
    def deploy_description(self):
        return f"APM应用: {self.app_name} 业务ID: {self.bk_biz_id}Trace数据源"

    @property
    def deploy_name(self):
        return f"bkapm_trace_{self.bk_biz_id}_{normalize_app_name(self.app_name)}"

    @property
    def cleans_description(self):
        return f"APM应用: {self.app_name} 业务ID: {self.bk_biz_id}尾部采样Trace清洗配置"

    @property
    def cleans_names(self):
        return "bkapm_tail"

    @property
    def cleans_fields(self):
        return [
            {
                "field_name": "span_id",
                "field_type": "string",
                "field_alias": "span id",
                "is_dimension": False,
                "field_index": 1,
            },
            {
                "field_name": "trace_id",
                "field_type": "string",
                "field_alias": "trace id",
                "is_dimension": False,
                "field_index": 2,
            },
            {
                "field_name": "span_info",
                "field_type": "text",
                "field_alias": "span info",
                "is_dimension": False,
                "field_index": 3,
            },
            {
                "field_name": "datetime",
                "field_type": "string",
                "field_alias": "datetime",
                "is_dimension": False,
                "field_index": 4,
            },
        ]

    @property
    def cleans_config(self):
        return {
            "extract": {
                "type": "fun",
                "method": "from_json",
                "result": "mid1",
                "label": "labele63a9a",
                "args": [],
                "next": {
                    "type": "branch",
                    "name": "",
                    "label": None,
                    "next": [
                        {
                            "type": "access",
                            "subtype": "access_obj",
                            "label": "label0732ee",
                            "key": "items",
                            "result": "items",
                            "default_type": "null",
                            "default_value": "",
                            "next": {
                                "type": "fun",
                                "label": "labelf7840e",
                                "result": "mid",
                                "args": [],
                                "method": "iterate",
                                "next": {
                                    "type": "branch",
                                    "name": "",
                                    "label": None,
                                    "next": [
                                        {
                                            "type": "assign",
                                            "subtype": "assign_obj",
                                            "label": "label817fa7",
                                            "assign": [
                                                {"type": "string", "assign_to": "span_id", "key": "span_id"},
                                                {"type": "string", "assign_to": "trace_id", "key": "trace_id"},
                                            ],
                                            "next": None,
                                        },
                                        {
                                            "type": "assign",
                                            "subtype": "assign_json",
                                            "label": "labela80eb4",
                                            "assign": [
                                                {"type": "text", "assign_to": "span_info", "key": "__all_keys__"}
                                            ],
                                            "next": None,
                                        },
                                    ],
                                },
                            },
                        },
                        {
                            "type": "assign",
                            "subtype": "assign_obj",
                            "label": "labelcfb6b8",
                            "assign": [{"type": "string", "assign_to": "datetime", "key": "datetime"}],
                            "next": None,
                        },
                    ],
                },
            },
            "conf": {
                "time_format": "yyyy-MM-dd HH:mm:ss",
                "timezone": 8,
                "time_field_name": "datetime",
                "output_field_name": "timestamp",
                "timestamp_len": 0,
                "encoding": "UTF-8",
            },
        }

    @property
    def cleans_table_id(self):
        return f"{self.cleans_names}_{normalize_app_name(self.app_name)}"[:50]

    @classmethod
    def get_deploy_params(cls, bk_biz_id, data_id, operator, name, deploy_description=None, extra_maintainers=None):
        """使用dataId互认方式接入数据源"""
        maintainers = ",".join(list(set([operator] + cls.bkbase_maintainer() + extra_maintainers or [])))

        return {
            "operator": operator,
            "bk_username": operator,
            "data_scenario": "custom",
            "data_scenario_id": cls._BKDATA_CUSTOM_SCENARIO_ID,
            "permission": "permission",
            "bk_biz_id": bk_biz_id,
            "description": deploy_description or name,
            "access_raw_data": {
                "tags": [],
                "raw_data_name": name,
                "maintainer": maintainers,
                "raw_data_alias": name,
                "data_source_tags": ["server"],
                "data_region": "inland",
                "data_source": "data_source",
                "data_encoding": "UTF-8",
                "sensitivity": "private",
                "description": deploy_description or name,
                "preassigned_data_id": data_id,
            },
        }

    def flow_instance(self):
        """
        获取尾部采样的ES存储信息 Flow中入库存储需要和应用绑定的APM存储一致
        """
        es_extra_data = {}
        instance = TraceDataSource.objects.get(bk_biz_id=self.bk_biz_id, app_name=self.app_name)

        # Step1: 获取应用的ES配置并对接入Bkbase
        # Res1: 获取Trace数据表名称
        es_extra_data["table_name"] = instance.result_table_id.replace(".", "_")
        self.logger.info(f"es_extra_data collect, table_name: {es_extra_data['table_name']}")

        storage = instance.storage
        if not storage:
            raise ValueError(f"trace datasource {self.bk_biz_id} {self.app_name} not found storage")

        # Res2: 获取过期时间
        es_extra_data["retention"] = storage.retention
        self.logger.info(f"es_extra_data collect, retention: {es_extra_data['retention']}")

        # Res3: 获取bkdata集群
        all_resources = api.bkdata.query_resource_list()
        cluster_info = ClusterInfo.objects.get(bk_tenant_id=self.bk_tenant_id, cluster_id=storage.storage_cluster_id)
        bkdata_cluster_name = self._BKDATA_ES_CLUSTER_NAME_FORMAT.format(cluster_name=cluster_info.cluster_name)
        bkdata_cluster_id = self._BKDATA_ES_CLUSTER_ID_FORMAT.format(cluster_id=cluster_info.cluster_id)

        if bkdata_cluster_id not in [i.get("resource_group_id") for i in all_resources]:
            self.logger.info(f"resource_set_id: {bkdata_cluster_id} not in resource list, start check if registry")

            # 获取集群冷热配置
            try:
                custom_options = json.loads(
                    cluster_info.consul_config.get("cluster_config", {}).get("custom_option", ""),
                )
                support_warm = custom_options.get("hot_warm_config", {}).get("is_enabled", False)
            except (JSONDecodeError, AttributeError) as e:
                self.logger.info(f"retrieve hot-warm config failed: {e} consul config: {cluster_info.consul_config}")
                support_warm = False

            params = {
                "bk_username": settings.APM_APP_BKDATA_OPERATOR,
                "bk_biz_id": self.bkdata_bk_biz_id,
                "resource_set_id": bkdata_cluster_id,
                "resource_set_name": bkdata_cluster_name,
                "geog_area_code": self._STORAGE_REGISTRY_AREA_CODE,
                "category": "es",
                "provider": "user",
                "purpose": "此集群由APM创建",
                "share": False,
                "admin": [settings.APM_APP_BKDATA_OPERATOR],
                "tag": [],
                "connection_info": {
                    "enable_auth": True,
                    "support_node_tag": support_warm,
                    "has_cold_nodes": False,
                    "host": cluster_info.domain_name,
                    "hot_node_num": 1,
                    "hot_save_days": 7,
                    "password": cluster_info.password,
                    "port": cluster_info.port,
                    "save_days": 30,
                    "transport": cluster_info.port,
                    "user": cluster_info.username,
                    "username": cluster_info.username,
                },
                "version": "1",
            }

            resource_info = api.bkdata.get_or_create_resource_set(params)
            if resource_info.get("resource_set_id"):
                if resource_info["resource_set_id"] != bkdata_cluster_id:
                    self.logger.info(
                        f"detected ES(host: {cluster_info.domain_name}) has been registered, "
                        f"will use the resource whose resource_set_id is {resource_info['resource_set_id']}"
                    )
                    bkdata_cluster_id = resource_info["resource_set_id"]
                    bkdata_cluster_name = resource_info["resource_set_name"]
                else:
                    self.logger.info(
                        f"register bkdata resource: {bkdata_cluster_id}({bkdata_cluster_name}) successfully"
                    )
            else:
                raise ValueError(f"[get_or_create_resource_set] response abnormal, response: {resource_info}")

        # 查看此资源是否已授权项目
        resource_info = api.bkdata.get_resource_set(resource_set_id=bkdata_cluster_id)
        auth_proj = [i.get("id") for i in resource_info.get("authorized_projects", [])]
        self.logger.info(f"bkdata resource: {bkdata_cluster_id}({bkdata_cluster_name}) auth proj: {auth_proj}")
        if self.bkbase_project_id not in auth_proj:
            self.logger.info(
                f"{self.bkbase_project_id} not in"
                f" resource: {bkdata_cluster_id}({bkdata_cluster_name}) auth proj, start to auth"
            )
            auth_proj_params = {
                "bk_username": settings.APM_APP_BKDATA_OPERATOR,
                "authorized_projects": auth_proj + [self.bkbase_project_id],
            }
            api.bkdata.update_resource_set({"resource_set_id": bkdata_cluster_id, **auth_proj_params})
            self.logger.info(f"{self.bkbase_project_id} <-------> {bkdata_cluster_id} auth successfully")

        es_extra_data["cluster_name"] = bkdata_cluster_id
        self.logger.info(f"es_extra_data collect, cluster_name: {es_extra_data['cluster_name']}")

        # Step2: 获取计算节点代码
        with open(self._FLINK_CODE_FILENAME, encoding="utf-8") as f:
            content = f.read()

        return super().flow_instance(es_extra_data=es_extra_data, flink_code=content)

    @property
    def flow_namespace(self) -> str:
        """返回 V4 Flow 所在的 BKBase 项目 namespace。"""
        if not self.bkbase_project_id:
            raise ValueError("APM_APP_BKDATA_TAIL_SAMPLING_PROJECT_ID is empty")
        return self._FLOW_NAMESPACE_FORMAT.format(project_id=self.bkbase_project_id)

    @property
    def bkbase_resource_tenant(self) -> str:
        """单租户使用 BKBase 默认租户，多租户使用应用所属租户。"""
        return self.bk_tenant_id if settings.ENABLE_MULTI_TENANT_MODE else "default"

    def start(self):
        """全局开关关闭时保留 V3，开启后统一使用 V4。"""
        if not settings.ENABLE_APM_TRACE_TAIL_SAMPLING_V4:
            return super().start()
        return self._start_v4()

    def _start_v4(self) -> None:
        """已有尾采只更新 Flow；首次开启才创建前置资源并切断直写链路。"""
        try:
            if self.flow.databus_clean_result_table_id:
                self._update_existing_v4_flow()
            else:
                trace_datasource = TraceDataSource.objects.get(bk_biz_id=self.bk_biz_id, app_name=self.app_name)
                self._create_v4_flow(trace_datasource)
        except Exception as error:
            self._raise_exc(f"apply tail sampling V4 resources failed: {error}", FlowStatus.CONFIG_FLOW_FAILED.value)

        self._update_field(
            {
                "is_finished": True,
                "finished_time": timezone.now(),
                "last_process_time": timezone.now(),
                "status": FlowStatus.SUCCESS.value,
            }
        )

    def _update_existing_v4_flow(self) -> None:
        """从 BKBase 读取既有 Flow，只更新采样参数并保留其资源引用。"""
        flow_name = self._v4_flow_name()
        flow_namespace = self._FLOW_NAMESPACE_FORMAT.format(project_id=self.flow.project_id)
        remote = api.bkdata.get_data_link(
            bk_tenant_id=self.bk_tenant_id,
            kind="flows",
            namespace=flow_namespace,
            name=flow_name,
        )
        phase = (remote.get("status") or {}).get("phase")
        if phase != DataLinkResourceStatus.OK.value:
            raise ValueError(f"已有 Flow({flow_namespace}/{flow_name}) 状态为 {phase}，暂不更新")

        metadata = remote["metadata"]
        spec = copy.deepcopy(remote["spec"])
        flink_node = next(node for node in spec["nodes"] if node["kind"] == "FlinkCodeNode")
        programming_args = json.loads(flink_node["programming_args"])
        programming_args.update(self._v4_programming_args(programming_args["input_table_id"], flink_node["output"]))
        flink_node["programming_args"] = json.dumps(programming_args, ensure_ascii=False, separators=(",", ":"))
        spec["desired_status"] = "running"

        flow_config = {
            "kind": "Flow",
            "metadata": {
                key: metadata[key]
                for key in ("tenant", "namespace", "name", "labels", "annotations")
                if key in metadata
            },
            "spec": spec,
            "status": None,
        }
        self._apply_v4_resources([flow_config])

    def _create_v4_flow(self, trace_datasource: TraceDataSource) -> None:
        """首次开启时声明五字段资源与 Flow，成功后停用原直写链路。"""
        source, source_configs = self._compose_v4_tail_source(trace_datasource)
        storage = self._resolve_v4_es_storage(trace_datasource)
        flow_config = self.compose_v4_flow_config(source=source, storage=storage)
        self._apply_v4_resources([*source_configs, flow_config])

        # 切断直写成功后才记录新 Flow；若失败，下次仍重走可幂等的创建路径。
        self._disable_direct_trace_datalink(trace_datasource)
        self._update_field(
            {
                "project_id": str(self.bkbase_project_id),
                "flow_id": flow_config["metadata"]["name"],
                "deploy_data_id": str(trace_datasource.bk_data_id),
                "databus_clean_id": source["name"],
                "databus_clean_result_table_id": source["result_table_id"],
                "databus_clean_config": source_configs[-1],
            }
        )

    def _compose_v4_tail_source(self, trace_datasource: TraceDataSource) -> tuple[dict, list[dict]]:
        """组装 V4 直写应用所需的五字段前置清洗资源。"""
        data_id_config = (
            DataIdConfig.objects.filter(
                bk_tenant_id=self.bk_tenant_id,
                namespace=BKBASE_NAMESPACE_BK_LOG,
                bk_data_id=trace_datasource.bk_data_id,
            )
            .exclude(name="")
            .order_by("-last_modify_time", "-id")
            .first()
        )
        if data_id_config is None:
            raise ValueError(f"Trace DataId({trace_datasource.bk_data_id}) 尚未注册到 {BKBASE_NAMESPACE_BK_LOG}")

        source_bk_biz_id = self.bk_biz_id
        name = f"bkapm_tail_{trace_datasource.bk_data_id}_tail_v4"
        result_table_id = f"{source_bk_biz_id}_{name}"
        maintainers = [self.application.create_user]
        labels = {"bk_biz_id": str(source_bk_biz_id)}

        # 资源元数据组装
        data_id_ref = {
            "kind": "DataId",
            "tenant": self.bkbase_resource_tenant,
            "namespace": data_id_config.namespace,
            "name": data_id_config.name,
        }
        kafka_ref = self._parse_resource_setting(
            settings.APM_TRACE_TAIL_SAMPLING_V4_KAFKA_CHANNEL,
            kind="KafkaChannel",
        )
        result_table_ref = {
            "kind": "ResultTable",
            "tenant": data_id_ref["tenant"],
            "namespace": data_id_ref["namespace"],
            "name": name,
        }
        channel_binding_ref = {**result_table_ref, "kind": "ChannelBinding"}

        # 下发资源配置组装
        result_table_config = {
            "kind": "ResultTable",
            "metadata": {
                "tenant": result_table_ref["tenant"],
                "namespace": result_table_ref["namespace"],
                "name": result_table_ref["name"],
                "labels": labels,
                "annotations": {},
            },
            "spec": {
                "description": f"APM tail sampling input for data id {trace_datasource.bk_data_id}",
                "bizId": source_bk_biz_id,
                "alias": name,
                "region": None,
                "maintainers": maintainers,
                "dataType": "log",
                "predefinedResultTableId": None,
                "fields": self._tail_result_table_fields(),
                "sensitivity": "private",
            },
            "status": None,
        }
        channel_binding_config = {
            "kind": "ChannelBinding",
            "metadata": {
                "tenant": channel_binding_ref["tenant"],
                "namespace": channel_binding_ref["namespace"],
                "name": channel_binding_ref["name"],
                "labels": labels,
                "annotations": {},
            },
            "spec": {"data": result_table_ref, "channel": kafka_ref},
            "status": None,
        }
        databus_config = {
            "kind": "Databus",
            "metadata": {
                "tenant": data_id_ref["tenant"],
                "namespace": data_id_ref["namespace"],
                "name": name,
                "labels": labels,
                "annotations": {},
            },
            "spec": {
                "sources": [data_id_ref],
                "sinks": [channel_binding_ref],
                "transforms": [
                    {
                        "kind": "Clean",
                        "rules": self._tail_clean_rules(),
                        "filter_rules": "True",
                        "context_map": None,
                        "error_strategy": "drop",
                        "join": None,
                    }
                ],
                "subTaskNum": 1,
                "preferCluster": None,
                "maintainers": maintainers,
                "autoOffsetReset": "latest",
                "consumerGroup": f"bkmonitor_{name}_clean",
                "batch": None,
            },
            "status": None,
        }
        source = {**result_table_ref, "result_table_id": result_table_id}
        return source, [result_table_config, channel_binding_config, databus_config]

    @staticmethod
    def _parse_resource_setting(value: str, kind: str) -> dict[str, str]:
        """解析全局配置中的 tenant/namespace/name BKBase 资源引用。"""
        parts = [part.strip() for part in value.split("/")]
        if len(parts) != 3 or not all(parts):
            raise ValueError(f"{kind} 必须配置为 tenant/namespace/name，实际为 {value!r}")
        return {"kind": kind, "tenant": parts[0], "namespace": parts[1], "name": parts[2]}

    @staticmethod
    def _tail_result_table_fields() -> list[dict]:
        """返回尾部采样 Flink 输入 RT 的五字段定义。"""
        fields = [
            ("timestamp", "timestamp", "event timestamp", "timestamp"),
            ("span_id", "span id", "span id", "string"),
            ("trace_id", "trace id", "trace id", "string"),
            ("span_info", "span info", "original span json", "string"),
            ("datetime", "datetime", "original datetime", "string"),
        ]
        return [
            {
                "field_name": name,
                "field_alias": alias,
                "description": description,
                "field_type": field_type,
                "is_dimension": False,
                "field_index": index,
            }
            for index, (name, alias, description, field_type) in enumerate(fields)
        ]

    @staticmethod
    def _tail_clean_rules() -> list[dict]:
        """返回将 Trace 原始数据转换为五字段 RT 的清洗规则。"""
        return [
            {
                "input_id": "__raw_data",
                "output_id": "mid1",
                "operator": {"type": "json_de", "error_strategy": "drop"},
            },
            {
                "input_id": "mid1",
                "output_id": "items",
                "operator": {
                    "type": "get",
                    "key_index": [{"type": "key", "value": "items"}],
                    "missing_strategy": None,
                },
            },
            {"input_id": "items", "output_id": "mid", "operator": {"type": "iter"}},
            *[
                {
                    "input_id": "mid",
                    "output_id": field_name,
                    "operator": {
                        "type": "assign",
                        "key_index": key_index,
                        "input_type": input_type,
                        "output_type": "string",
                        "alias": alias,
                        "is_dimension": False,
                        "is_time_field": False,
                    },
                }
                for field_name, key_index, input_type, alias in (
                    ("span_id", "span_id", "string", "span id"),
                    ("trace_id", "trace_id", "string", "trace id"),
                    ("span_info", None, "text", "span info"),
                )
            ],
            {
                "input_id": "mid1",
                "output_id": "datetime",
                "operator": {
                    "type": "assign",
                    "key_index": "datetime",
                    "input_type": "string",
                    "output_type": "string",
                    "alias": "datetime",
                    "is_dimension": False,
                    "is_time_field": True,
                    "time_format": {"format": "%Y-%m-%d %H:%M:%S", "zone": 8},
                },
            },
        ]

    def _resolve_v4_es_storage(self, trace_datasource: TraceDataSource) -> dict:
        """从原生 V4 Trace 存储配置确定同一 ES 资源与索引别名。"""
        storage = trace_datasource.storage
        if storage is None:
            raise ValueError(f"trace datasource {self.bk_biz_id} {self.app_name} not found storage")

        return {
            "tenant": self.bkbase_resource_tenant,
            "namespace": BKBASE_NAMESPACE_BK_LOG,
            "name": storage.storage_cluster.cluster_name,
            "retention": storage.retention,
            "replicas": self._V4_FLOW_ES_REPLICAS,
            "timezone": storage.time_zone,
            "table_name": trace_datasource.result_table_id.replace(".", "_"),
        }

    def _v4_programming_args(self, input_table_id: str, output_table_id: str) -> dict:
        """生成新建和更新 Flow 共用的尾采参数。"""
        return {
            "input_table_id": input_table_id,
            "output_table_id": output_table_id,
            "trace_session_gap_min": self.config.get(
                "tail_trace_session_gap_min", TailSamplingFlinkNode._TRACE_GAP_MIN
            ),
            "trace_mark_timeout_min": self.config.get(
                "tail_trace_mark_timeout", TailSamplingFlinkNode._TRACE_TIMEOUT_MIN
            ),
            "sampling_conditions": self.config.get("tail_conditions") or [],
            "max_span_count": TailSamplingFlinkNode._MAX_SPAN_COUNT,
            "random_sampling_ratio": self.config.get("tail_percentage", TailSamplingFlinkNode._SAMPLING_RATIO),
        }

    def compose_v4_flow_config(self, source: dict, storage: dict) -> dict:
        """组装尾部采样 V4 Flow 的声明配置。"""
        stream_cluster = settings.APM_TRACE_TAIL_SAMPLING_V4_STREAM_CLUSTER
        input_table_id = source["result_table_id"]
        output_table_id = f"{input_table_id}_output"
        source_node_name = f"stream_source_{self.data_id}_tail_v4"
        flink_node_name = "tail_sampling"
        with open(self._FLINK_CODE_FILENAME, encoding="utf-8") as flink_file:
            flink_code = flink_file.read().strip()

        programming_args = self._v4_programming_args(input_table_id, output_table_id)
        flink_instance = TailSamplingFlinkNode(
            source_rt_id=input_table_id,
            flink_code=flink_code,
            name=flink_node_name,
        )
        output_fields = [
            {
                "field_name": field.field_name,
                "field_alias": field.field_alias,
                "description": "",
                "field_type": field.field_type,
                "is_dimension": False,
                "field_index": index,
            }
            for index, field in enumerate(flink_instance.output_fields)
        ]
        return {
            "kind": "Flow",
            "metadata": {
                "tenant": source["tenant"],
                "namespace": self.flow_namespace,
                "name": self._v4_flow_name(),
                "labels": {},
                "annotations": {},
            },
            "spec": {
                "nodes": [
                    {
                        "kind": "StreamSourceNode",
                        "name": source_node_name,
                        "data": {
                            "kind": "ResultTable",
                            "tenant": source["tenant"],
                            "namespace": source["namespace"],
                            "name": source["name"],
                        },
                    },
                    {
                        "kind": "FlinkCodeNode",
                        "name": flink_node_name,
                        "inputs": [source_node_name],
                        "programming_args": json.dumps(programming_args, ensure_ascii=False, separators=(",", ":")),
                        "code": flink_code,
                        "dt_event_time_field": "",
                        "output": output_table_id,
                        "output_fields": output_fields,
                        "data": None,
                    },
                    {
                        "kind": "EsStorageNode",
                        "name": f"elastic_storage_{self.data_id}_tail_v4",
                        "input": flink_node_name,
                        "storage": {
                            "kind": "ElasticSearch",
                            "tenant": storage["tenant"],
                            "namespace": storage["namespace"],
                            "name": storage["name"],
                        },
                        "write_alias": {
                            "TimeBased": {
                                "format": f"write_%Y%m%d_{storage['table_name']}",
                                "timezone": storage["timezone"],
                            }
                        },
                        "expires": f"{storage['retention']}d",
                        "replicas": storage["replicas"],
                        "unique_field_list": ["trace_id", "span_id"],
                        "analyzed_fields": [],
                        "doc_value_fields": ["dtEventTimeStamp", "timestamp"],
                        "json_field_list": ["status", "events", "links", "attributes", "resource"],
                        "flattened_fields": [],
                        "tokenizers": None,
                        "data": None,
                    },
                ],
                "operation_config": {
                    "start_position": "continue",
                    "stream_sql_deploy_config": {
                        "cluster": stream_cluster,
                        "deploy_mode": None,
                        "deploy_config": None,
                    },
                    "batch_sql_deploy_config": None,
                },
                "maintainers": [self.application.create_user],
                "desired_status": "running",
            },
            "status": None,
        }

    def _v4_flow_name(self) -> str:
        """复用迁移 Flow 名称，或按 Data ID 生成新 Flow 名称。"""
        if self.flow.flow_id:
            flow_id = str(self.flow.flow_id)
            return f"flow_v3_{flow_id}" if flow_id.isdigit() else flow_id
        return f"bkapm_tail_sampling_{self.data_id}_tail_v4"

    def _apply_v4_resources(self, configs: list[dict]) -> None:
        """一次声明全部资源，并等待本次声明的资源全部 Ok。"""
        api.bkdata.apply_data_link(bk_tenant_id=self.bk_tenant_id, config=configs)
        resource_kinds = {
            "ResultTable": "resulttables",
            "ChannelBinding": "channelbindings",
            "Databus": "databuses",
            "Flow": "flows",
        }
        for config in configs:
            self._wait_resource_ok(resource_kinds[config["kind"]], config["metadata"])

    def _wait_resource_ok(self, kind: str, resource: dict) -> None:
        """轮询本次声明的 BKBase 资源，直到 Ok、失败或超时。"""
        deadline = time.monotonic() + self._V4_RESOURCE_WAIT_SECONDS
        while True:
            remote = api.bkdata.get_data_link(
                bk_tenant_id=self.bk_tenant_id,
                kind=kind,
                namespace=resource["namespace"],
                name=resource["name"],
            )
            status = remote.get("status") or {}
            phase = status.get("phase")
            message = status.get("message") or ""
            if phase == DataLinkResourceStatus.OK.value:
                return
            if phase in {DataLinkResourceStatus.FAILED.value, DataLinkResourceStatus.TERMINATED.value}:
                raise ValueError(
                    f"BKBase {kind}/{resource['namespace']}/{resource['name']} phase={phase}, message={message}"
                )
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"wait BKBase {kind}/{resource['namespace']}/{resource['name']} timeout, "
                    f"phase={phase}, message={message}"
                )
            time.sleep(self._V4_POLL_INTERVAL_SECONDS)

    def _disable_direct_trace_datalink(self, trace_datasource: TraceDataSource) -> None:
        """新资源全部 Ok 后删除原生 V4 Trace 的直写 ES DataLink。"""
        direct_links = [
            data_link
            for data_link in DataLink.objects.filter(
                bk_tenant_id=self.bk_tenant_id,
                data_link_strategy=DataLink.BK_LOG,
                bk_data_id=trace_datasource.bk_data_id,
            )
            if trace_datasource.result_table_id in (data_link.table_ids or [])
        ]
        if len(direct_links) > 1:
            raise ValueError(
                f"Trace DataId({trace_datasource.bk_data_id}) 匹配到多个直写 DataLink: "
                f"{[data_link.data_link_name for data_link in direct_links]}"
            )

        value, value_type = ResultTableOption._parse_value(False)
        ResultTableOption.objects.update_or_create(
            bk_tenant_id=self.bk_tenant_id,
            table_id=trace_datasource.result_table_id,
            name=ResultTableOption.OPTION_ENABLE_V4_LOG_DATA_LINK,
            defaults={
                "value": value,
                "value_type": value_type,
                "creator": self.application.create_user if self.application else self.bkbase_operator,
            },
        )
        if direct_links:
            direct_links[0].delete_data_link()
