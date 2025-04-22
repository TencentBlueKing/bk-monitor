# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from metadata import models
from metadata.models.data_link.constants import DataLinkKind

# 计算平台V4链路KIND-STORAGE 映射关系
BKBASE_V4_KIND_STORAGE_CONFIGS = [
    {
        "kind": DataLinkKind.get_choice_value(DataLinkKind.ELASTICSEARCH.value),
        "namespace": "bklog",
        "field_mappings": {"domain_name": "host", "port": "port", "username": "user", "password": "password"},
        "cluster_type": models.ClusterInfo.TYPE_ES,
        "storage_name": "es",
    },
    {
        "kind": DataLinkKind.get_choice_value(DataLinkKind.VMSTORAGE.value),
        "namespace": "bkmonitor",
        "field_mappings": {
            "domain_name": "insertHost",
            "port": "insertPort",
            "username": "user",
            "password": "password",
        },
        "cluster_type": models.ClusterInfo.TYPE_VM,
        "storage_name": "vm",
    },
    {
        "kind": DataLinkKind.get_choice_value(DataLinkKind.DORIS.value),
        "namespace": "bklog",
        "field_mappings": {
            "domain_name": "host",
            "port": "port",
            "username": "user",
            "password": "password",
        },
        "cluster_type": models.ClusterInfo.TYPE_DORIS,
        "storage_name": "doris",
    },
]
