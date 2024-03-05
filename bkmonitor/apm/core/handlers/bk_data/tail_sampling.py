# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import os

from django.conf import settings

from apm.core.handlers.bk_data.flow import ApmFlow
from apm.models import TraceDataSource
from bkmonitor.dataflow.task.apm_tail_sampling import APMTailSamplingTask
from constants.apm import FlowType
from core.drf_resource import api
from metadata.models import ClusterInfo


class TailSamplingFlow(ApmFlow):
    """
    APM虚拟指标Flow
    """

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

    def __init__(self, trace_datasource, config):
        super(TailSamplingFlow, self).__init__(
            trace_datasource.bk_biz_id, trace_datasource.app_name, trace_datasource.bk_data_id, config
        )

    @property
    def bkbase_project_id(self):
        return settings.APM_APP_BKDATA_TAIL_SAMPLING_PROJECT_ID

    @property
    def deploy_description(self):
        return f"APM应用: {self.app_name} 业务ID: {self.bk_biz_id}Trace数据源"

    @property
    def deploy_name(self):
        return f"bkapm_trace_{self.bk_biz_id}_{self.app_name}"

    @property
    def cleans_description(self):
        return f"APM应用: {self.app_name} 业务ID: {self.bk_biz_id}尾部采样Trace清洗配置"

    @property
    def cleans_names(self):
        return f"bkapm_tail"

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
        return f"{self.cleans_names}_{self.app_name}"[:50]

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
        instance = TraceDataSource.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name).first()

        # Step1: 获取应用的ES配置并对接入Bkbase
        # Res1: 获取Trace数据表名称
        es_extra_data["table_name"] = instance.result_table_id.replace(".", "_")
        self.logger.info(f"es_extra_data collect, table_name: {es_extra_data['table_name']}")

        storage = instance.storage
        # Res2: 获取过期时间
        es_extra_data["retention"] = storage.retention
        self.logger.info(f"es_extra_data collect, retention: {es_extra_data['retention']}")

        # Res3: 获取bkdata集群
        all_resources = api.bkdata.query_resource_list()
        cluster_info = ClusterInfo.objects.filter(cluster_id=storage.storage_cluster_id).first()
        bkdata_cluster_name = self._BKDATA_ES_CLUSTER_NAME_FORMAT.format(cluster_name=cluster_info.cluster_name)
        bkdata_cluster_id = self._BKDATA_ES_CLUSTER_ID_FORMAT.format(cluster_id=cluster_info.cluster_id)
        if bkdata_cluster_id not in [i.get("resource_group_id") for i in all_resources]:
            self.logger.info(f"check bkdata cluster_id: {bkdata_cluster_id} not in resource_sets, start register")

            # 在bkdata中监控业务中注册此ES资源
            params = {
                "bk_username": settings.APM_APP_BKDATA_OPERATOR,
                "bk_biz_id": settings.BK_DATA_BK_BIZ_ID,
                "resource_set_id": bkdata_cluster_id,
                "resource_set_name": bkdata_cluster_name,
                "geog_area_code": self._STORAGE_REGISTRY_AREA_CODE,
                "category": "es",
                "provider": "user",
                "purpose": f"此集群由APM创建",
                "share": False,
                "admin": [settings.APM_APP_BKDATA_OPERATOR],
                "tag": [],
                "connection_info": {
                    "enable_auth": True,
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
            api.bkdata.create_resource_set(params)
            self.logger.info(f"register bkdata resource: {bkdata_cluster_id}({bkdata_cluster_name}) successfully")

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
        with open(self._FLINK_CODE_FILENAME, "r", encoding="utf-8") as f:
            content = f.read()

        return super(TailSamplingFlow, self).flow_instance(es_extra_data=es_extra_data, flink_code=content)
