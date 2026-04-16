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
import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, Optional

from django.conf import settings
from pypinyin import lazy_pinyin
from tenacity import RetryError, retry, stop_after_attempt, wait_exponential

from core.drf_resource import api
from metadata.models.data_link.constants import (
    DataLinkKind,
    DataLinkResourceStatus,
    MATCH_DATA_NAME_PATTERN,
)

if TYPE_CHECKING:
    from .datasource import ApmDataSourceConfigBase, ProfileDataSource  # noqa

logger = logging.getLogger("apm")

PROFILING_DORIS_CLEAN_RULES = [
    {"input_id": "__raw_data", "output_id": "json_data", "operator": {"type": "json_de"}},
    {
        "input_id": "json_data",
        "output_id": "raw_data_list",
        "operator": {"type": "get", "key_index": [{"value": "data", "type": "key"}]},
    },
    {"input_id": "raw_data_list", "output_id": "raw_data", "operator": {"type": "iter"}},
    {
        "input_id": "raw_data",
        "output_id": "origin_profiling_data",
        "operator": {"type": "get", "key_index": [{"value": "data", "type": "key"}]},
    },
    {
        "input_id": "raw_data",
        "output_id": "app",
        "operator": {"type": "assign", "key_index": "app", "output_type": "string"},
    },
    {
        "input_id": "raw_data",
        "output_id": "biz_id",
        "operator": {"type": "assign", "key_index": "biz_id", "output_type": "string"},
    },
    {
        "input_id": "raw_data",
        "output_id": "type",
        "operator": {"type": "assign", "key_index": "type", "output_type": "string"},
    },
    {
        "input_id": "raw_data",
        "output_id": "service_name",
        "operator": {"type": "assign", "key_index": "service_name", "output_type": "string"},
    },
    {"input_id": "origin_profiling_data", "output_id": "profiling_data", "operator": {"type": "from_base64"}},
    {"input_id": "profiling_data", "output_id": "samples", "operator": {"type": "from_pprof"}},
    {"input_id": "samples", "output_id": "sample", "operator": {"type": "iter"}},
    {
        "input_id": "sample",
        "output_id": "period_type",
        "operator": {"type": "assign", "key_index": "period_type", "output_type": "string"},
    },
    {
        "input_id": "sample",
        "output_id": "period",
        "operator": {"type": "assign", "key_index": "period", "output_type": "string"},
    },
    {
        "input_id": "sample",
        "output_id": "time",
        "operator": {"type": "assign", "key_index": "time", "output_type": "string"},
    },
    {
        "input_id": "sample",
        "output_id": "duration_nanos",
        "operator": {"type": "assign", "key_index": "duration_nanos", "output_type": "string"},
    },
    {
        "input_id": "sample",
        "output_id": "stacktrace",
        "operator": {"type": "assign", "key_index": "stacktrace", "output_type": "string"},
    },
    {
        "input_id": "sample",
        "output_id": "labels",
        "operator": {"type": "assign", "key_index": "labels", "output_type": "string"},
    },
    {
        "input_id": "sample",
        "output_id": "sample_type",
        "operator": {"type": "assign", "key_index": "sample_type", "output_type": "string"},
    },
    {
        "input_id": "sample",
        "output_id": "value",
        "operator": {"type": "assign", "key_index": "value", "output_type": "string"},
    },
    {
        "input_id": "sample",
        "output_id": "time_output",
        "operator": {
            "type": "assign",
            "key_index": "time",
            "output_type": "string",
            "is_time_field": True,
            "time_format": {"format": "Unix Timestamp", "zone": 8},
        },
    },
]


def compose_profile_resource_name(app_name: str) -> str:
    """
    组装 Profile V4 链路资源名称，规则与 compose_bkdata_data_id_name 相同，但使用 profile_ 前缀
    @param app_name: 应用名称（原始值，函数内部处理所有清洗逻辑）
    @return: 资源名称
    """
    # 先按正则剔除特殊字符（包括中文）
    refine_name = re.sub(MATCH_DATA_NAME_PATTERN, "", app_name)

    # 针对中文字符进行拼音转换
    chinese_characters = "".join(char for char in app_name if "\u4e00" <= char <= "\u9fff")
    if chinese_characters:
        chinese_pinyin = "".join(lazy_pinyin(chinese_characters))
        refine_name += chinese_pinyin

    # 去除空格，将减号替换为下划线
    refine_name = refine_name.replace(" ", "").replace("-", "_")

    # 替换连续的下划线为单个下划线
    resource_name = f"profile_{re.sub(r'_+', '_', refine_name)}"

    # 控制长度
    if len(refine_name) > 45:
        truncated_name = refine_name[-39:].lower().strip("_")
        hash_suffix = hashlib.md5(refine_name.encode()).hexdigest()[:5]
        resource_name = f"profile_{truncated_name}_{hash_suffix}"

    return resource_name


@dataclass
class DorisStorageConfig:
    # storage_cluster may be updated by bkData, we could update it by changing settings.APM_DORIS_STORAGE_CONFIG
    storage_cluster: str
    expires: str = "3d"
    storage_type: str = "doris"
    data_scenario: str = "custom"

    kafka_config: dict = field(default_factory=dict)

    DEFAULT_STORAGE_CLUSTER: ClassVar[str] = "doris-default1"

    @classmethod
    def default(cls) -> "DorisStorageConfig":
        return cls(storage_cluster=cls.DEFAULT_STORAGE_CLUSTER)

    @classmethod
    def read(cls, forced_config: dict | None = None) -> Optional["DorisStorageConfig"]:
        raw_config = forced_config or settings.APM_DORIS_STORAGE_CONFIG
        if not raw_config:
            return cls.default()

        return cls(**raw_config)


@dataclass
class BkDataDorisProvider:
    """BkData Doris 数据提供者"""

    bk_biz_id: int
    app_name: str
    pure_app_name: str
    maintainer: str
    operator: str

    config: DorisStorageConfig = field(default_factory=DorisStorageConfig.read)
    _obj: Optional["ApmDataSourceConfigBase"] = None

    BKBASE_MAX_LENGTH = 50

    @classmethod
    def from_datasource_instance(
        cls, obj: "ProfileDataSource", maintainer: str, operator: str, name_stuffix: str = None
    ) -> "BkDataDorisProvider":
        """从数据源实例中创建数据源提供者"""
        return cls(
            bk_biz_id=obj.profile_bk_biz_id,
            app_name=obj.app_name,
            maintainer=maintainer,
            operator=operator,
            _obj=obj,
            pure_app_name=obj.app_name.replace("-", "_")
            if not name_stuffix
            else f"{obj.app_name}{name_stuffix}".replace("-", "_"),
        )

    def provider(self) -> dict:
        """提供数据源配置"""

        params = self.assemble_params()
        logger.info("[ProfileDatasource] create_data_hub params: %s", params)
        try:
            results = api.bkdata.create_data_hub(params)
        except Exception:
            logger.exception(
                f"[ProfileDatasource] create_data_hub failed, bk_biz_id: {self.bk_biz_id}, app_name: {self.app_name}"
            )
            raise

        bk_data_id = results.get("raw_data_id")
        result_table_ids = results.get("clean_rt_id")
        if None in [bk_data_id, result_table_ids]:
            raise ValueError("[ProfileDatasource] create_data_hub failed, essential fields are missing: %s", results)

        logger.info(
            "[ProfileDatasource] create_data_hub success, bk_data_id: %s, result_table_id: %s",
            bk_data_id,
            result_table_ids,
        )
        return {
            "bk_data_id": bk_data_id,
            "result_table_id": result_table_ids[0],
            # 提取过期天数
            "retention": int(self.config.expires.split("d")[0]),
        }

    def get_result_table_name(self) -> str:
        """获取结果表名"""

        prefix = f"{self._obj.DATASOURCE_TYPE}_"
        suffix = self.pure_app_name
        if len(prefix) + len(suffix) > self.BKBASE_MAX_LENGTH:
            # 如果超过长度，则截断并添加当前秒数防止重复
            suffix = suffix[len(prefix) + len(suffix) - self.BKBASE_MAX_LENGTH + 2 :]
            suffix = datetime.datetime.now().strftime("%S") + suffix

        return f"{prefix}{suffix}"

    def get_clean_params(self) -> list:
        """清洗配置"""
        # clean params is fixed when data format is unified
        return [
            {
                "json_config": {
                    "extract": {
                        "type": "fun",
                        "method": "from_json",
                        "result": "raw_json",
                        "label": "label6600e9",
                        "args": [],
                        "next": {
                            "type": "access",
                            "subtype": "access_obj",
                            "label": "labela8ad98",
                            "key": "data",
                            "result": "raw_data_list",
                            "default_type": "null",
                            "default_value": "",
                            "next": {
                                "type": "fun",
                                "label": "label41cbbb",
                                "result": "raw_data",
                                "args": [],
                                "method": "iterate",
                                "next": {
                                    "type": "branch",
                                    "name": "",
                                    "label": None,
                                    "next": [
                                        {
                                            "type": "access",
                                            "subtype": "access_obj",
                                            "label": "label813a8e",
                                            "key": "data",
                                            "result": "origin_profiling_data",
                                            "default_type": "null",
                                            "default_value": "",
                                            "next": {
                                                "type": "fun",
                                                "method": "from_base64",
                                                "result": "profiling_data",
                                                "label": "labelbfc079",
                                                "args": [],
                                                "next": {
                                                    "type": "fun",
                                                    "method": "from_pprof",
                                                    "result": "samples",
                                                    "label": "label98aa7b",
                                                    "args": [],
                                                    "next": {
                                                        "type": "fun",
                                                        "label": "label914889",
                                                        "result": "sample",
                                                        "args": [],
                                                        "method": "iterate",
                                                        "next": {
                                                            "type": "assign",
                                                            "subtype": "assign_obj",
                                                            "label": "label97dfab",
                                                            "assign": [
                                                                {
                                                                    "type": "string",
                                                                    "assign_to": "period_type",
                                                                    "key": "period_type",
                                                                },
                                                                {
                                                                    "type": "string",
                                                                    "assign_to": "period",
                                                                    "key": "period",
                                                                },
                                                                {"type": "string", "assign_to": "time", "key": "time"},
                                                                {
                                                                    "type": "string",
                                                                    "assign_to": "duration_nanos",
                                                                    "key": "duration_nanos",
                                                                },
                                                                {
                                                                    "type": "string",
                                                                    "assign_to": "stacktrace",
                                                                    "key": "stacktrace",
                                                                },
                                                                {
                                                                    "type": "string",
                                                                    "assign_to": "labels",
                                                                    "key": "labels",
                                                                },
                                                                {
                                                                    "type": "string",
                                                                    "assign_to": "sample_type",
                                                                    "key": "sample_type",
                                                                },
                                                                {
                                                                    "type": "string",
                                                                    "assign_to": "value",
                                                                    "key": "value",
                                                                },
                                                            ],
                                                            "next": None,
                                                        },
                                                    },
                                                },
                                            },
                                        },
                                        {
                                            "type": "assign",
                                            "subtype": "assign_obj",
                                            "label": "labelc97156",
                                            "assign": [
                                                {"type": "string", "assign_to": "app", "key": "app"},
                                                {"type": "string", "assign_to": "biz_id", "key": "biz_id"},
                                                {"type": "string", "assign_to": "type", "key": "type"},
                                                {"type": "string", "assign_to": "service_name", "key": "service_name"},
                                            ],
                                            "next": None,
                                        },
                                    ],
                                },
                            },
                        },
                    },
                    "conf": {
                        "time_format": "Unix Time Stamp(milliseconds)",
                        "timezone": 8,
                        "time_field_name": "time",
                        "output_field_name": "timestamp",
                        "timestamp_len": 13,
                        "encoding": "UTF-8",
                    },
                },
                "result_table_name": self.get_result_table_name(),
                "result_table_name_alias": self.get_result_table_name(),
                "description": "Bk Profiling",
                "fields": [
                    {
                        "field_name": "period_type",
                        "field_type": "string",
                        "field_alias": "period_type",
                        "is_dimension": False,
                        "field_index": 1,
                    },
                    {
                        "field_name": "period",
                        "field_type": "string",
                        "field_alias": "period",
                        "is_dimension": False,
                        "field_index": 2,
                    },
                    {
                        "field_name": "time",
                        "field_type": "string",
                        "field_alias": "time",
                        "is_dimension": False,
                        "field_index": 3,
                    },
                    {
                        "field_name": "duration_nanos",
                        "field_type": "string",
                        "field_alias": "duration_nanos",
                        "is_dimension": False,
                        "field_index": 4,
                    },
                    {
                        "field_name": "stacktrace",
                        "field_type": "string",
                        "field_alias": "stacktrace",
                        "is_dimension": False,
                        "field_index": 5,
                    },
                    {
                        "field_name": "labels",
                        "field_type": "string",
                        "field_alias": "labels",
                        "is_dimension": False,
                        "field_index": 6,
                    },
                    {
                        "field_name": "sample_type",
                        "field_type": "string",
                        "field_alias": "sample_type",
                        "is_dimension": False,
                        "field_index": 7,
                    },
                    {
                        "field_name": "value",
                        "field_type": "string",
                        "field_alias": "value",
                        "is_dimension": False,
                        "field_index": 8,
                    },
                    {
                        "field_name": "app",
                        "field_type": "string",
                        "field_alias": "app",
                        "is_dimension": False,
                        "field_index": 9,
                    },
                    {
                        "field_name": "biz_id",
                        "field_type": "string",
                        "field_alias": "biz_id",
                        "is_dimension": False,
                        "field_index": 10,
                    },
                    {
                        "field_name": "type",
                        "field_type": "string",
                        "field_alias": "type",
                        "is_dimension": False,
                        "field_index": 11,
                    },
                    {
                        "field_name": "service_name",
                        "field_type": "string",
                        "field_alias": "service_name",
                        "is_dimension": False,
                        "field_index": 12,
                    },
                ],
            }
        ]

    def get_common_params(self) -> dict:
        """通用配置"""
        return {
            "bk_biz_id": self.bk_biz_id,
            "maintainer": self.maintainer,
            "bk_username": self.operator,
            "data_scenario": self.config.data_scenario,
        }

    def get_storage_params(self) -> list:
        return [
            {
                "result_table_name": self.get_result_table_name(),
                "storage_type": self.config.storage_type,
                "is_profiling": True,
                "expires": self.config.expires,
                "storage_cluster": self.config.storage_cluster,
            }
        ]

    def get_raw_data_params(self) -> dict:
        """原始数据配置"""
        return {
            "raw_data_name": f"{self.pure_app_name}_doris",
            "raw_data_alias": f"{self.pure_app_name}_doris",
            "data_source_tags": ["server"],
            "tags": [],
            "sensitivity": "private",
            "data_encoding": "UTF-8",
            "data_region": "inland",
            "description": f"App<{self.app_name}> profiling doris",
            "data_scenario": {},
        }

    def assemble_params(self) -> dict:
        """组装参数"""
        params = {
            "common": self.get_common_params(),
            "raw_data": self.get_raw_data_params(),
            "clean": self.get_clean_params(),
            "storage": self.get_storage_params(),
        }
        return params


# BkBase V4 声明式链路接入（Profile Doris）
_V4_NAMESPACE = "bklog"
_V4_POLL_INTERVAL = 10  # 秒
_V4_POLL_MAX_ATTEMPTS = 30  # 最多等待 5 分钟


@dataclass
class BkDataDorisV4Provider:
    """
    使用 BkBase V4 声明式 API 接入 Profile Doris 数据源。
    提交顺序：DataId → ResultTable → DorisBinding → Databus（一次性提交）
    轮询 DataId 直至 phase == "Ok" 后返回数据源信息。
    """

    bk_biz_id: int
    app_name: str
    bk_tenant_id: str
    maintainer: str
    operator: str

    config: DorisStorageConfig = field(default_factory=DorisStorageConfig.read)
    _obj: Optional["ApmDataSourceConfigBase"] = None

    @classmethod
    def from_datasource_instance(
        cls,
        obj: "ProfileDataSource",
        bk_tenant_id: str,
        maintainer: str,
        operator: str,
    ) -> "BkDataDorisV4Provider":
        """从 ProfileDataSource 实例构造 V4 Provider"""
        return cls(
            bk_biz_id=obj.profile_bk_biz_id,
            app_name=obj.app_name,
            bk_tenant_id=bk_tenant_id,
            maintainer=maintainer,
            operator=operator,
            _obj=obj,
        )

    # ── 内部工具 ──────────────────────────────

    def _resource_name(self) -> str:
        """DataId / ResultTable / DorisBinding 的资源名称"""
        return compose_profile_resource_name(self.app_name)

    def _databus_name(self) -> str:
        """Databus 资源名称，格式：doris_{resource_name}"""
        return f"doris_{self._resource_name()}"

    def _maintainers_list(self) -> list:
        """将逗号分隔的 maintainer 字符串转换为列表"""
        return [m for m in self.maintainer.split(",") if m]

    def _metadata_labels(self) -> dict:
        """V4 资源的 metadata.labels，与指标链路保持一致"""
        return {"bk_biz_id": str(self.bk_biz_id)}

    # ── 资源配置构建 ──────────────────────────

    def _build_data_id_config(self, name: str) -> dict:
        return {
            "kind": "DataId",
            "metadata": {
                "namespace": _V4_NAMESPACE,
                "name": name,
                "labels": self._metadata_labels(),
                "annotations": {},
            },
            "spec": {
                "description": f"App<{self.app_name}> profiling data id",
                "alias": name,
                "bizId": self.bk_biz_id,
                "maintainers": self._maintainers_list(),
                "eventType": "log",
            },
        }

    def _build_result_table_config(self, name: str) -> dict:
        return {
            "kind": "ResultTable",
            "metadata": {
                "namespace": _V4_NAMESPACE,
                "name": name,
                "labels": self._metadata_labels(),
                "annotations": {},
            },
            "spec": {
                "description": f"App<{self.app_name}> profiling result table",
                "bizId": self.bk_biz_id,
                "alias": name,
                "maintainers": self._maintainers_list(),
                "dataType": "log",
                "fields": [
                    {
                        "field_name": "timestamp",
                        "field_alias": "timestamp",
                        "field_type": "timestamp",
                        "is_dimension": False,
                        "field_index": 1,
                    },
                    {
                        "field_name": "period_type",
                        "field_alias": "period_type",
                        "field_type": "string",
                        "is_dimension": False,
                        "field_index": 2,
                    },
                    {
                        "field_name": "period",
                        "field_alias": "period",
                        "field_type": "string",
                        "is_dimension": False,
                        "field_index": 3,
                    },
                    {
                        "field_name": "time",
                        "field_alias": "time",
                        "field_type": "string",
                        "is_dimension": False,
                        "field_index": 4,
                    },
                    {
                        "field_name": "duration_nanos",
                        "field_alias": "duration_nanos",
                        "field_type": "string",
                        "is_dimension": False,
                        "field_index": 5,
                    },
                    {
                        "field_name": "stacktrace",
                        "field_alias": "stacktrace",
                        "field_type": "string",
                        "is_dimension": False,
                        "field_index": 6,
                    },
                    {
                        "field_name": "labels",
                        "field_alias": "labels",
                        "field_type": "string",
                        "is_dimension": False,
                        "field_index": 7,
                    },
                    {
                        "field_name": "sample_type",
                        "field_alias": "sample_type",
                        "field_type": "string",
                        "is_dimension": False,
                        "field_index": 8,
                    },
                    {
                        "field_name": "value",
                        "field_alias": "value",
                        "field_type": "string",
                        "is_dimension": False,
                        "field_index": 9,
                    },
                    {
                        "field_name": "app",
                        "field_alias": "app",
                        "field_type": "string",
                        "is_dimension": False,
                        "field_index": 10,
                    },
                    {
                        "field_name": "biz_id",
                        "field_alias": "biz_id",
                        "field_type": "string",
                        "is_dimension": False,
                        "field_index": 11,
                    },
                    {
                        "field_name": "type",
                        "field_alias": "type",
                        "field_type": "string",
                        "is_dimension": False,
                        "field_index": 12,
                    },
                    {
                        "field_name": "service_name",
                        "field_alias": "service_name",
                        "field_type": "string",
                        "is_dimension": False,
                        "field_index": 13,
                    },
                ],
            },
        }

    def _build_doris_binding_config(self, name: str, rt_name: str) -> dict:
        if not settings.APM_PROFILE_V4_DORIS_BINDING_CLUSTER:
            raise ValueError(
                "[ProfileDatasource] APM_PROFILE_V4_DORIS_BINDING_CLUSTER is required for V4 data link, "
                "please configure it in GlobalConfig"
            )
        storage_cluster = settings.APM_PROFILE_V4_DORIS_BINDING_CLUSTER
        return {
            "kind": "DorisBinding",
            "metadata": {
                "annotations": {},
                "labels": self._metadata_labels(),
                "name": name,
                "namespace": _V4_NAMESPACE,
            },
            "spec": {
                "data": {"name": rt_name, "namespace": _V4_NAMESPACE, "kind": "ResultTable"},
                "storage": {"name": storage_cluster, "namespace": _V4_NAMESPACE, "kind": "Doris"},
                "storage_config": {
                    "table_type": "duplicate_table",
                    "is_profiling": True,
                    "unique_partition_table": False,
                    "db": f"mapleleaf_{self.bk_biz_id}",
                    "table": name,
                    "storage_keys": [],
                    "json_fields": [],
                    "original_json_fields": [],
                    "field_config_group": {},
                    "expires": self.config.expires,
                    "sample_table_name": f"{rt_name}_sample_{self.bk_biz_id}",
                    "label_table_name": f"{rt_name}_label_{self.bk_biz_id}",
                    "flush_timeout": 300,
                },
            },
        }

    def _build_databus_config(self, databus_name: str, data_id_name: str, doris_binding_name: str) -> dict:
        config = {
            "kind": "Databus",
            "metadata": {
                "namespace": _V4_NAMESPACE,
                "name": databus_name,
                "labels": self._metadata_labels(),
                "annotations": {},
            },
            "spec": {
                "maintainers": self._maintainers_list(),
                "sources": [{"kind": "DataId", "name": data_id_name, "namespace": _V4_NAMESPACE}],
                "sinks": [{"kind": "DorisBinding", "name": doris_binding_name, "namespace": _V4_NAMESPACE}],
                "transforms": [
                    {
                        "kind": "Clean",
                        "rules": PROFILING_DORIS_CLEAN_RULES,
                        "filter_rules": "True",
                    }
                ],
                "subTaskNum": 1,
            },
        }
        if settings.APM_PROFILE_V4_DATABUS_PREFER_CLUSTER:
            config["spec"]["preferCluster"] = {
                "kind": "DatabusCluster",
                "namespace": _V4_NAMESPACE,
                "name": settings.APM_PROFILE_V4_DATABUS_PREFER_CLUSTER,
            }
        return config

    def _build_configs(self) -> list:
        """构建 V4 链路的全部资源配置（提交顺序：DataId → ResultTable → DorisBinding → Databus）"""
        name = self._resource_name()
        databus_name = self._databus_name()
        return [
            self._build_data_id_config(name),
            self._build_result_table_config(name),
            self._build_doris_binding_config(name, name),
            self._build_databus_config(databus_name, name, name),
        ]

    # ── 轮询 DataId ───────────────────────────

    def _wait_for_data_id(self, name: str) -> int:
        """
        轮询 BkBase V4 DataId 资源，直至 phase == "Ok"，返回 dataId 整数值。
        每 10 秒轮询一次，最多 30 次（约 5 分钟），超时后抛出 TimeoutError。
        """
        kind = DataLinkKind.get_choice_value(DataLinkKind.DATAID.value)  # → "dataids"
        for attempt in range(1, _V4_POLL_MAX_ATTEMPTS + 1):
            logger.info(
                "[ProfileDatasource] polling DataId, name=%s, attempt=%d/%d",
                name,
                attempt,
                _V4_POLL_MAX_ATTEMPTS,
            )
            response = api.bkdata.get_data_link(
                bk_tenant_id=self.bk_tenant_id,
                kind=kind,
                namespace=_V4_NAMESPACE,
                name=name,
            )
            phase = response.get("status", {}).get("phase")
            if phase == DataLinkResourceStatus.OK.value:
                data_id = int(response.get("metadata", {}).get("annotations", {}).get("dataId", 0))
                logger.info(
                    "[ProfileDatasource] DataId ready, name=%s, data_id=%d",
                    name,
                    data_id,
                )
                return data_id
            logger.info(
                "[ProfileDatasource] DataId not ready yet, name=%s, phase=%s, waiting %ds",
                name,
                phase,
                _V4_POLL_INTERVAL,
            )
            time.sleep(_V4_POLL_INTERVAL)

        raise TimeoutError(
            f"[ProfileDatasource] DataId {name!r} did not reach Ok after {_V4_POLL_MAX_ATTEMPTS * _V4_POLL_INTERVAL}s"
        )

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=1, max=10))
    def _apply_data_link_with_retry(self, configs: list) -> dict:
        """提交 V4 链路配置，具备重试机制，最多重试 4 次，指数退避"""
        try:
            return api.bkdata.apply_data_link(config=configs, bk_tenant_id=self.bk_tenant_id)
        except Exception as e:
            logger.error(
                "[ProfileDatasource] apply V4 data link error, name=%s, error=%s",
                self._resource_name(),
                e,
            )
            raise

    def provider(self) -> dict:
        """
        向 BkBase V4 提交 Profile Doris 链路配置，轮询 DataId 就绪后返回数据源信息。
        返回格式与 V3 BkDataDorisProvider.provider() 保持一致。
        """
        name = self._resource_name()
        configs = self._build_configs()
        logger.info("[ProfileDatasource] apply V4 data link, name=%s, config_count=%d", name, len(configs))
        try:
            self._apply_data_link_with_retry(configs)
        except RetryError as e:
            logger.error("[ProfileDatasource] apply V4 data link retry exhausted, name=%s", name)
            raise e.__cause__ if e.__cause__ else e

        bk_data_id = self._wait_for_data_id(name)

        # result_table_id 格式与 V3 保持一致：{profile_bk_biz_id}_{rt_name}
        result_table_id = f"{self.bk_biz_id}_{name}"

        # 过期天数：从 config.expires 中提取（格式如 "3d"）
        retention = int(self.config.expires.rstrip("d"))

        return {
            "bk_data_id": bk_data_id,
            "result_table_id": result_table_id,
            "retention": retention,
        }
