"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, Optional

from django.conf import settings

from core.drf_resource import api

if TYPE_CHECKING:
    from .datasource import ApmDataSourceConfigBase

logger = logging.getLogger("apm")


@dataclass
class DorisStorageConfig:
    # storage_cluster may be updated by bkData, we could update it by changing settings.APM_DORIS_STORAGE_CONFIG
    storage_cluster: str
    expires: str = "30d"
    storage_type: str = "doris"
    data_scenario: str = "custom"

    kafka_config: dict = field(default_factory=dict)

    DEFAULT_STORAGE_CLUSTER: ClassVar[str] = "doris-default1"

    @classmethod
    def default(cls) -> "DorisStorageConfig":
        return cls(storage_cluster=cls.DEFAULT_STORAGE_CLUSTER)

    @classmethod
    def read(cls, forced_config: Optional[dict] = None) -> Optional["DorisStorageConfig"]:
        raw_config = forced_config or settings.APM_DORIS_STORAGE_CONFIG
        if not raw_config:
            return cls.default()

        return cls(**raw_config)


@dataclass
class BkDataDorisProvider:
    """BkData Doris 数据提供者"""

    bk_biz_id: int
    app_name: str
    operator: str

    config: DorisStorageConfig = field(default_factory=DorisStorageConfig.read)
    _obj: Optional["ApmDataSourceConfigBase"] = None

    @classmethod
    def from_datasource_instance(cls, obj: "ApmDataSourceConfigBase", operator: str) -> "BkDataDorisProvider":
        """从数据源实例中创建数据源提供者"""
        return cls(bk_biz_id=obj.bk_biz_id, app_name=obj.app_name, operator=operator, _obj=obj)

    def provider(self, **options) -> dict:
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
        return f"{self._obj.DATASOURCE_TYPE}_{self._obj.app_name}"

    def get_clean_params(self) -> list:
        """清洗配置"""
        # clean params is fixed when data format is unified
        return [
            {
                "json_config": {
                    'extract': {
                        'type': 'fun',
                        'method': 'from_json',
                        'result': 'raw_json',
                        'label': 'label6600e9',
                        'args': [],
                        'next': {
                            'type': 'access',
                            'subtype': 'access_obj',
                            'label': 'labela8ad98',
                            'key': 'data',
                            'result': 'raw_data_list',
                            'default_type': 'null',
                            'default_value': '',
                            'next': {
                                'type': 'fun',
                                'label': 'label41cbbb',
                                'result': 'raw_data',
                                'args': [],
                                'method': 'iterate',
                                'next': {
                                    'type': 'branch',
                                    'name': '',
                                    'label': None,
                                    'next': [
                                        {
                                            'type': 'access',
                                            'subtype': 'access_obj',
                                            'label': 'label813a8e',
                                            'key': 'data',
                                            'result': 'origin_profiling_data',
                                            'default_type': 'null',
                                            'default_value': '',
                                            'next': {
                                                'type': 'fun',
                                                'method': 'from_base64',
                                                'result': 'profiling_data',
                                                'label': 'labelbfc079',
                                                'args': [],
                                                'next': {
                                                    'type': 'fun',
                                                    'method': 'from_pprof',
                                                    'result': 'samples',
                                                    'label': 'label98aa7b',
                                                    'args': [],
                                                    'next': {
                                                        'type': 'fun',
                                                        'label': 'label914889',
                                                        'result': 'sample',
                                                        'args': [],
                                                        'method': 'iterate',
                                                        'next': {
                                                            'type': 'assign',
                                                            'subtype': 'assign_obj',
                                                            'label': 'label97dfab',
                                                            'assign': [
                                                                {
                                                                    'type': 'string',
                                                                    'assign_to': 'period_type',
                                                                    'key': 'period_type',
                                                                },
                                                                {
                                                                    'type': 'string',
                                                                    'assign_to': 'period',
                                                                    'key': 'period',
                                                                },
                                                                {'type': 'string', 'assign_to': 'time', 'key': 'time'},
                                                                {
                                                                    'type': 'string',
                                                                    'assign_to': 'duration_nanos',
                                                                    'key': 'duration_nanos',
                                                                },
                                                                {
                                                                    'type': 'string',
                                                                    'assign_to': 'stacktrace',
                                                                    'key': 'stacktrace',
                                                                },
                                                                {
                                                                    'type': 'string',
                                                                    'assign_to': 'labels',
                                                                    'key': 'labels',
                                                                },
                                                                {
                                                                    'type': 'string',
                                                                    'assign_to': 'sample_type',
                                                                    'key': 'sample_type',
                                                                },
                                                                {
                                                                    'type': 'string',
                                                                    'assign_to': 'value',
                                                                    'key': 'value',
                                                                },
                                                            ],
                                                            'next': None,
                                                        },
                                                    },
                                                },
                                            },
                                        },
                                        {
                                            'type': 'assign',
                                            'subtype': 'assign_obj',
                                            'label': 'labelc97156',
                                            'assign': [
                                                {'type': 'string', 'assign_to': 'app', 'key': 'app'},
                                                {'type': 'string', 'assign_to': 'biz_id', 'key': 'biz_id'},
                                                {'type': 'string', 'assign_to': 'type', 'key': 'type'},
                                                {'type': 'string', 'assign_to': 'service_name', 'key': 'service_name'},
                                            ],
                                            'next': None,
                                        },
                                    ],
                                },
                            },
                        },
                    },
                    'conf': {
                        'time_format': "Unix Time Stamp(milliseconds)",
                        'timezone': 8,
                        'time_field_name': 'time',
                        'output_field_name': 'timestamp',
                        'timestamp_len': 13,
                        'encoding': 'UTF-8',
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
            "maintainer": self.operator,
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
            "raw_data_name": f"{self.app_name}_doris",
            "raw_data_alias": f"{self.app_name}_doris",
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
