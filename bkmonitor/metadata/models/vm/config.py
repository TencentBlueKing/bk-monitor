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

from jinja2.sandbox import SandboxedEnvironment as Environment

from metadata.models.vm.constants import VM_RETENTION_TIME, TimestampLen

logger = logging.getLogger("metadata")


class BkDataClean:
    TEMPLATE = """
    {
        "json_config": {
            "extract": {
                "type": "fun",
                "method": "from_json",
                "result": "json",
                "label": "label3d0181",
                "args": [],
                "next": {
                    "type": "branch",
                    "name": "",
                    "label": null,
                    "next": [
                        {
                            "type": "assign",
                            "subtype": "assign_json",
                            "label": "label86a168",
                            "assign": [
                                {
                                    "type": "text",
                                    "assign_to": "dimensions",
                                    "key": "dimensions"
                                }
                            ],
                            "next": null
                        },
                        {
                            "type": "access",
                            "subtype": "access_obj",
                            "label": "labelb7a4b1",
                            "key": "metrics",
                            "result": "metrics",
                            "default_type": "null",
                            "default_value": "",
                            "next": {
                                "type": "fun",
                                "label": "label1dd4f4",
                                "result": "item",
                                "args": [],
                                "method": "items",
                                "next": {
                                    "type": "assign",
                                    "subtype": "assign_obj",
                                    "label": "labelec6235",
                                    "assign": [
                                        {
                                            "type": "double",
                                            "assign_to": "value",
                                            "key": "value"
                                        },
                                        {
                                            "type": "string",
                                            "assign_to": "metric",
                                            "key": "key"
                                        }
                                    ],
                                    "next": null
                                }
                            }
                        },
                        {
                            "type": "assign",
                            "subtype": "assign_obj",
                            "label": "labelc08700",
                            "assign": [
                                {
                                    "type": "long",
                                    "assign_to": "time",
                                    "key": "time"
                                }
                            ],
                            "next": null
                        }
                    ]
                }
            },
            "conf": {
                "time_format": "{{time_format}}",
                "timezone": 8,
                "time_field_name": "time",
                "output_field_name": "timestamp",
                "timestamp_len": {{timestamp_len}},
                "encoding": "UTF-8"
            }
        },
        "result_table_name": "{{result_table_name}}",
        "result_table_name_alias": "{{result_table_name_alias}}",
        "processing_id": "{{bk_biz_id}}_{{result_table_name}}",
        "description": "tsdb",
        "fields": {{fields}}
    }
    """

    def __init__(
        self,
        raw_data_name: str,
        result_table_name: str,
        bk_biz_id: int,
        timestamp_len: int | None = TimestampLen.MILLISECOND_LEN.value,
    ):
        self.raw_data_name = raw_data_name
        self.result_table_name = result_table_name
        self.bk_biz_id = bk_biz_id
        self.timestamp_len = timestamp_len

    @property
    def value(self):
        fields = [
            {
                "field_name": "time",
                "field_type": "long",
                "field_alias": "time",
                "is_dimension": False,
                "field_index": 1,
            },
            {
                "field_name": "value",
                "field_type": "double",
                "field_alias": "value",
                "is_dimension": False,
                "field_index": 2,
            },
            {
                "field_name": "metric",
                "field_type": "string",
                "field_alias": "metric",
                "is_dimension": False,
                "field_index": 3,
            },
            {
                "field_name": "dimensions",
                "field_type": "text",
                "field_alias": "dimensions",
                "is_dimension": False,
                "field_index": 4,
            },
        ]

        # 获取清洗的时间精度
        time_format = TimestampLen.get_choice_value(self.timestamp_len)
        config_str = (
            Environment()
            .from_string(self.TEMPLATE)
            .render(
                {
                    "result_table_name": self.raw_data_name,
                    "result_table_name_alias": self.result_table_name,
                    "fields": json.dumps(fields),
                    "time_format": time_format,
                    "timestamp_len": self.timestamp_len,
                    "bk_biz_id": self.bk_biz_id,
                }
            )
        )
        # 转换为 Dict
        try:
            return json.loads(config_str)
        except Exception as e:
            logger.error("json load error: %s", e)
            raise


class BkDataStorage:
    def __init__(self, bk_table_id: str, vm_cluster: str, expires: str | None = VM_RETENTION_TIME):
        self.bk_table_id = bk_table_id
        self.vm_cluster = vm_cluster
        self.expires = expires

    @property
    def value(self):
        return [
            {
                "result_table_name": self.bk_table_id,
                "storage_type": "vm",
                "expires": self.expires,
                "storage_cluster": self.vm_cluster,
            },
        ]


class BkDataStorageWithDataID:
    def __init__(
        self, raw_data_id: int, result_table_name: str, vm_cluster: str, expires: str | None = VM_RETENTION_TIME
    ):
        self.raw_data_id = raw_data_id
        self.result_table_name = result_table_name
        self.vm_cluster = vm_cluster
        self.expires = expires
        self.data_type = "clean"

    @property
    def value(self):
        fields = [
            {
                "field_name": "time",
                "field_type": "long",
                "field_alias": "time",
                "is_dimension": False,
                "field_index": 1,
                "physical_field": "time",
            },
            {
                "field_name": "value",
                "field_type": "double",
                "field_alias": "value",
                "is_dimension": False,
                "field_index": 2,
                "physical_field": "value",
            },
            {
                "field_name": "metric",
                "field_type": "string",
                "field_alias": "metric",
                "is_dimension": False,
                "field_index": 3,
                "physical_field": "metric",
            },
            {
                "field_name": "dimensions",
                "field_type": "text",
                "field_alias": "dimensions",
                "is_dimension": False,
                "field_index": 4,
                "physical_field": "dimensions",
            },
        ]
        return {
            "raw_data_id": self.raw_data_id,
            "data_type": self.data_type,
            "result_table_name": self.result_table_name,
            "result_table_name_alias": self.result_table_name,
            "storage_type": "vm",
            "storage_cluster": self.vm_cluster,
            "expires": self.expires,
            "fields": fields,
            "config": {"schemaless": True},
        }
