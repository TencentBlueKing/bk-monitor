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
import random
import re
import string
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


def _sanitize_name(raw: str) -> str:
    """清洗名称：中文原地转拼音、剔除特殊字符、去空格、减号转下划线、合并连续下划线"""
    parts = []
    for char in raw:
        if "\u4e00" <= char <= "\u9fff":
            parts.append(lazy_pinyin(char)[0])
        elif not re.match(MATCH_DATA_NAME_PATTERN, char):
            parts.append(char)
    refine = "".join(parts)
    refine = refine.replace(" ", "").replace("-", "_")
    return re.sub(r"_+", "_", refine)


def compose_profile_data_id_name(bk_biz_id: int, app_name: str) -> str:
    """
    组装 DataId 资源名称：profile_{bk_biz_id}_{app_name}
    超过 MAX_LENGTH(50) 时截断 app_name 并在末尾补充 5 位随机字符。

    正常格式：profile_{bk_biz_id}_{sanitized_app_name}
    截断格式：profile_{bk_biz_id}_{truncated_app_name}_{random}

    @param bk_biz_id: 业务 ID
    @param app_name: 应用名称
    @return: DataId 资源名称，长度 ≤ 50
    """
    _PREFIX = "profile_"
    _MAX_LENGTH = 50
    _RANDOM_LENGTH = 5

    sanitized = _sanitize_name(app_name)
    # profile_{bk_biz_id}_{sanitized}
    name = f"{_PREFIX}{bk_biz_id}_{sanitized}"

    if len(name) <= _MAX_LENGTH:
        return name

    # 截断：profile_{bk_biz_id}_{truncated}_{random}
    # 固定部分 = 前缀 + bk_biz_id + 2个下划线 + random下划线 + random
    fixed_len = len(_PREFIX) + len(str(bk_biz_id)) + 2 + 1 + _RANDOM_LENGTH
    truncated_max = _MAX_LENGTH - fixed_len
    if truncated_max < 1:
        truncated_max = 1
    truncated = sanitized[:truncated_max].rstrip("_")
    random_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=_RANDOM_LENGTH))
    return f"{_PREFIX}{bk_biz_id}_{truncated}_{random_suffix}"


def compose_profile_resource_name(app_name: str, bk_data_id: int) -> str:
    """
    组装 ResultTable / DorisBinding / Databus 资源名称：profile_{app_name}_{bk_data_id}
    超过 MAX_LENGTH(50) 时截断中间的 app_name。

    @param app_name: 应用名称
    @param bk_data_id: BkBase 数据 ID
    @return: 资源名称，长度 ≤ 50
    """
    _PREFIX = "profile_"
    _MAX_LENGTH = 50

    sanitized = _sanitize_name(app_name)
    data_id_str = str(bk_data_id)
    # profile_{sanitized}_{data_id}
    name = f"{_PREFIX}{sanitized}_{data_id_str}"

    if len(name) <= _MAX_LENGTH:
        return name

    # 截断 app_name：profile_{truncated}_{data_id}
    # 固定部分 = 前缀 + 下划线 + data_id = len(prefix) + 1 + len(data_id_str)
    fixed_len = len(_PREFIX) + 1 + len(data_id_str)
    truncated_max = _MAX_LENGTH - fixed_len - 1  # -1 for underscore between truncated and data_id
    if truncated_max < 1:
        truncated_max = 1
    truncated = sanitized[:truncated_max].rstrip("_")
    return f"{_PREFIX}{truncated}_{data_id_str}"


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
    分两步提交：
      1. 提交 DataId，轮询直至就绪，获取 bk_data_id
      2. 用 bk_data_id 构建 ResultTable / DorisBinding / Databus 并提交
    """

    bk_biz_id: int  # profile_bk_biz_id，用于 BkBase API 请求中的 bizId / labels / db 命名
    app_name: str
    bk_tenant_id: str
    maintainer: str
    operator: str
    data_biz_id: int = 0  # 仅用于 DataId 命名（通过 get_tenant_datalink_biz_id 获取）

    config: DorisStorageConfig = field(default_factory=DorisStorageConfig.read)
    _obj: Optional["ProfileDataSource"] = None

    @classmethod
    def from_datasource_instance(
        cls,
        obj: "ProfileDataSource",
        bk_tenant_id: str,
        maintainer: str,
        operator: str,
    ) -> "BkDataDorisV4Provider":
        """从 ProfileDataSource 实例构造 V4 Provider"""
        from bkmonitor.utils.tenant import get_tenant_datalink_biz_id

        datalink_biz_ids = get_tenant_datalink_biz_id(bk_tenant_id, obj.profile_bk_biz_id)

        return cls(
            bk_biz_id=obj.profile_bk_biz_id,
            app_name=obj.app_name,
            bk_tenant_id=bk_tenant_id,
            maintainer=maintainer,
            operator=operator,
            data_biz_id=datalink_biz_ids.data_biz_id,
            _obj=obj,
        )

    # ── 命名 ────────────────────────────────

    def _data_id_name(self) -> str:
        """DataId 资源名称，优先使用已存储的名称"""
        stored = self._obj.bkdata_datalink_config.get("v4_resource_names", {}) if self._obj else {}
        return stored.get("data_id_name") or compose_profile_data_id_name(self.data_biz_id, self.app_name)

    def _result_table_name(self, bk_data_id: int) -> str:
        """ResultTable 资源名称，优先使用已存储的名称"""
        stored = self._obj.bkdata_datalink_config.get("v4_resource_names", {}) if self._obj else {}
        return stored.get("result_table_name") or compose_profile_resource_name(self.app_name, bk_data_id)

    def _doris_binding_name(self, bk_data_id: int) -> str:
        """DorisBinding 资源名称，优先使用已存储的名称"""
        stored = self._obj.bkdata_datalink_config.get("v4_resource_names", {}) if self._obj else {}
        return stored.get("doris_binding_name") or compose_profile_resource_name(self.app_name, bk_data_id)

    def _databus_name(self, bk_data_id: int) -> str:
        """Databus 资源名称，优先使用已存储的名称"""
        stored = self._obj.bkdata_datalink_config.get("v4_resource_names", {}) if self._obj else {}
        return stored.get("databus_name") or compose_profile_resource_name(self.app_name, bk_data_id)

    def get_resource_names(self, bk_data_id: int = 0) -> dict:
        """获取当前资源名称，用于持久化到 bkdata_datalink_config.v4_resource_names"""
        return {
            "data_id_name": self._data_id_name(),
            "result_table_name": self._result_table_name(bk_data_id),
            "doris_binding_name": self._doris_binding_name(bk_data_id),
            "databus_name": self._databus_name(bk_data_id),
        }

    def _maintainers_list(self) -> list:
        """将逗号分隔的 maintainer 字符串转换为列表"""
        return [m.strip() for m in self.maintainer.split(",") if m.strip()]

    def _metadata_labels(self) -> dict:
        """V4 资源的 metadata.labels，与指标链路保持一致"""
        return {"bk_biz_id": str(self.bk_biz_id)}

    # ── 资源配置构建 ──────────────────────────

    def _build_data_id_config(self) -> dict:
        name = self._data_id_name()
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

    def _build_result_table_config(self, bk_data_id: int) -> dict:
        rt_name = self._result_table_name(bk_data_id)
        return {
            "kind": "ResultTable",
            "metadata": {
                "namespace": _V4_NAMESPACE,
                "name": rt_name,
                "labels": self._metadata_labels(),
                "annotations": {},
            },
            "spec": {
                "description": f"App<{self.app_name}> profiling result table",
                "bizId": self.bk_biz_id,
                "alias": rt_name,
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

    def _build_doris_binding_config(self, bk_data_id: int) -> dict:
        dorisbinding_name = self._doris_binding_name(bk_data_id)
        rt_name = self._result_table_name(bk_data_id)
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
                "name": dorisbinding_name,
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
                    "table": dorisbinding_name,
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

    def _build_databus_config(self, bk_data_id: int) -> dict:
        bus_name = self._databus_name(bk_data_id)
        data_id_name = self._data_id_name()
        dorisbinding_name = self._doris_binding_name(bk_data_id)
        config = {
            "kind": "Databus",
            "metadata": {
                "namespace": _V4_NAMESPACE,
                "name": bus_name,
                "labels": self._metadata_labels(),
                "annotations": {},
            },
            "spec": {
                "maintainers": self._maintainers_list(),
                "sources": [{"kind": "DataId", "name": data_id_name, "namespace": _V4_NAMESPACE}],
                "sinks": [{"kind": "DorisBinding", "name": dorisbinding_name, "namespace": _V4_NAMESPACE}],
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

    def _build_step1_configs(self) -> list:
        """第一步：仅提交 DataId"""
        return [self._build_data_id_config()]

    def _build_step2_configs(self, bk_data_id: int) -> list:
        """第二步：提交 ResultTable / DorisBinding / Databus"""
        return [
            self._build_result_table_config(bk_data_id),
            self._build_doris_binding_config(bk_data_id),
            self._build_databus_config(bk_data_id),
        ]

    # ── 轮询 DataId ───────────────────────────

    def _wait_for_data_id(self) -> int:
        """
        轮询 BkBase V4 DataId 资源，直至 phase == "Ok"，返回 dataId 整数值。
        每 10 秒轮询一次，最多 30 次（约 5 分钟），超时后抛出 TimeoutError。
        """
        data_id_name = self._data_id_name()
        kind = DataLinkKind.get_choice_value(DataLinkKind.DATAID.value)  # → "dataids"
        for attempt in range(1, _V4_POLL_MAX_ATTEMPTS + 1):
            logger.info(
                "[ProfileDatasource] polling DataId, name=%s, attempt=%d/%d",
                data_id_name,
                attempt,
                _V4_POLL_MAX_ATTEMPTS,
            )
            response = api.bkdata.get_data_link(
                bk_tenant_id=self.bk_tenant_id,
                kind=kind,
                namespace=_V4_NAMESPACE,
                name=data_id_name,
            )
            phase = response.get("status", {}).get("phase")
            if phase == DataLinkResourceStatus.OK.value:
                raw_data_id = response.get("metadata", {}).get("annotations", {}).get("dataId")
                try:
                    data_id = int(raw_data_id)
                except (TypeError, ValueError):
                    logger.warning(
                        "[ProfileDatasource] DataId phase is Ok but dataId is invalid, "
                        "name=%s, raw_data_id=%r, attempt=%d/%d",
                        data_id_name,
                        raw_data_id,
                        attempt,
                        _V4_POLL_MAX_ATTEMPTS,
                    )
                else:
                    if data_id > 0:
                        logger.info(
                            "[ProfileDatasource] DataId ready, name=%s, data_id=%d",
                            data_id_name,
                            data_id,
                        )
                        return data_id
                    logger.warning(
                        "[ProfileDatasource] DataId phase is Ok but dataId is non-positive, "
                        "name=%s, data_id=%d, attempt=%d/%d",
                        data_id_name,
                        data_id,
                        attempt,
                        _V4_POLL_MAX_ATTEMPTS,
                    )
            logger.info(
                "[ProfileDatasource] DataId not ready yet, name=%s, phase=%s, waiting %ds",
                data_id_name,
                phase,
                _V4_POLL_INTERVAL,
            )
            time.sleep(_V4_POLL_INTERVAL)

        raise TimeoutError(
            f"[ProfileDatasource] DataId {data_id_name!r} did not reach Ok after "
            f"{_V4_POLL_MAX_ATTEMPTS * _V4_POLL_INTERVAL}s"
        )

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=1, max=10))
    def _apply_data_link_with_retry(self, configs: list) -> dict:
        """提交 V4 链路配置，具备重试机制，最多重试 4 次，指数退避"""
        try:
            return api.bkdata.apply_data_link(config=configs, bk_tenant_id=self.bk_tenant_id)
        except Exception as e:
            logger.error(
                "[ProfileDatasource] apply V4 data link error, data_id_name=%s, error=%s",
                self._data_id_name(),
                e,
            )
            raise

    def provider(self) -> dict:
        """
        向 BkBase V4 提交 Profile Doris 链路配置，轮询 DataId 就绪后返回数据源信息。
        分两步提交：第一步提交 DataId，第二步提交其余资源。
        返回格式与 V3 BkDataDorisProvider.provider() 保持一致。
        """
        # 第一步：提交 DataId
        step1_configs = self._build_step1_configs()
        logger.info(
            "[ProfileDatasource] apply V4 data link step 1 (DataId), name=%s, config_count=%d",
            self._data_id_name(),
            len(step1_configs),
        )
        try:
            self._apply_data_link_with_retry(step1_configs)
        except RetryError as e:
            logger.error(
                "[ProfileDatasource] apply V4 data link step 1 retry exhausted, name=%s",
                self._data_id_name(),
            )
            raise e.__cause__ if e.__cause__ else e

        # 轮询 DataId 就绪，获取 bk_data_id
        bk_data_id = self._wait_for_data_id()

        # 第二步：用 bk_data_id 构建并提交其余资源
        step2_configs = self._build_step2_configs(bk_data_id)
        logger.info(
            "[ProfileDatasource] apply V4 data link step 2, bk_data_id=%d, config_count=%d",
            bk_data_id,
            len(step2_configs),
        )
        try:
            self._apply_data_link_with_retry(step2_configs)
        except RetryError as e:
            logger.error(
                "[ProfileDatasource] apply V4 data link step 2 retry exhausted, bk_data_id=%d",
                bk_data_id,
            )
            raise e.__cause__ if e.__cause__ else e

        # result_table_id 格式：{bk_biz_id}_{rt_name}
        rt_name = self._result_table_name(bk_data_id)
        result_table_id = f"{self.bk_biz_id}_{rt_name}"

        # 过期天数：从 config.expires 中提取（格式如 "3d"）
        retention = int(self.config.expires.rstrip("d"))

        return {
            "bk_data_id": bk_data_id,
            "result_table_id": result_table_id,
            "retention": retention,
        }

    # ── 启停（V4：apply=启动，delete=停止）─────────

    def apply(self):
        """
        DataId 和 ResultTable 在 delete 时不会被删除，启动时只需重新 apply DorisBinding 和 Databus。
        使用 bkdata_datalink_config.v4_resource_names 中存储的资源名称。
        """
        v4_names = self._obj.bkdata_datalink_config.get("v4_resource_names", {}) if self._obj else {}
        if not self._obj or not v4_names.get("doris_binding_name"):
            raise ValueError("[ProfileDatasource] cannot apply V4 data link without stored resource names")
        bk_data_id = self._obj.bk_data_id
        # 只提交 DorisBinding 和 Databus
        configs = [
            self._build_doris_binding_config(bk_data_id),
            self._build_databus_config(bk_data_id),
        ]
        logger.info(
            "[ProfileDatasource] apply V4 data link (start), doris_binding_name=%s, databus_name=%s, bk_data_id=%d",
            self._doris_binding_name(bk_data_id),
            self._databus_name(bk_data_id),
            bk_data_id,
        )
        try:
            self._apply_data_link_with_retry(configs)
        except RetryError as e:
            logger.error(
                "[ProfileDatasource] apply V4 data link (start) retry exhausted, doris_binding_name=%s, databus_name=%s",
                self._doris_binding_name(bk_data_id),
                self._databus_name(bk_data_id),
            )
            raise e.__cause__ if e.__cause__ else e

    def delete(self):
        """
        删除 V4 链路资源，等价于停止。
        按创建的逆序删除：Databus → DorisBinding（DataId 和 ResultTable 不删）。
        使用 bkdata_datalink_config.v4_resource_names 中存储的资源名称。
        """
        v4_names = self._obj.bkdata_datalink_config.get("v4_resource_names", {}) if self._obj else {}
        databus_name = v4_names.get("databus_name")
        doris_binding_name = v4_names.get("doris_binding_name")
        if not databus_name and not doris_binding_name:
            return
        # 删除顺序：Databus → DorisBinding（DataId / ResultTable 为基础资源，不删）
        delete_items = []
        if databus_name:
            delete_items.append((DataLinkKind.DATABUS, databus_name))
        if doris_binding_name:
            delete_items.append((DataLinkKind.DORISBINDING, doris_binding_name))
        for kind_enum, name in delete_items:
            kind_value = DataLinkKind.get_choice_value(kind_enum.value)
            logger.info(
                "[ProfileDatasource] delete V4 resource, kind=%s, name=%s",
                kind_value,
                name,
            )
            api.bkdata.delete_data_link(
                bk_tenant_id=self.bk_tenant_id,
                kind=kind_value,
                namespace=_V4_NAMESPACE,
                name=name,
            )
