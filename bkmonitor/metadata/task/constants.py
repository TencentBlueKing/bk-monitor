"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from metadata import models
from metadata.models.data_link.constants import (
    BKBASE_NAMESPACE_BK_LOG,
    BKBASE_NAMESPACE_BK_MONITOR,
    DataLinkKind,
)

# 计算平台V4链路KIND-STORAGE 映射关系
BKBASE_V4_KIND_STORAGE_CONFIGS = [
    {
        "kind": DataLinkKind.get_choice_value(DataLinkKind.ELASTICSEARCH.value),
        "namespace": BKBASE_NAMESPACE_BK_LOG,
        "field_mappings": {"domain_name": "host", "port": "port", "username": "user", "password": "password"},
        "cluster_type": models.ClusterInfo.TYPE_ES,
    },
    {
        "kind": DataLinkKind.get_choice_value(DataLinkKind.VMSTORAGE.value),
        "namespace": BKBASE_NAMESPACE_BK_MONITOR,
        "field_mappings": {
            "domain_name": "insertHost",
            "port": "insertPort",
            "username": "user",
            "password": "password",
        },
        "cluster_type": models.ClusterInfo.TYPE_VM,
    },
    {
        "kind": DataLinkKind.get_choice_value(DataLinkKind.DORIS.value),
        "namespace": BKBASE_NAMESPACE_BK_LOG,
        "field_mappings": {
            "domain_name": "host",
            "port": "port",
            "username": "user",
            "password": "password",
        },
        "cluster_type": models.ClusterInfo.TYPE_DORIS,
    },
    {
        "kind": DataLinkKind.get_choice_value(DataLinkKind.KAFKACHANNEL.value),
        "namespace": BKBASE_NAMESPACE_BK_LOG,
        "field_mappings": {
            "domain_name": "host",
            "port": "port",
            "username": "auth.sasl.username",
            "password": "auth.sasl.password",
            "sasl_mechanisms": "auth.sasl.mechanism",
            "is_auth": "auth.sasl.enabled",
            "stream_to_id": "streamToId",
            "v3_channel_id": "v3ChannelId",
            "version": "version",
        },
        "cluster_type": models.ClusterInfo.TYPE_KAFKA,
    },
    {
        "kind": DataLinkKind.get_choice_value(DataLinkKind.KAFKACHANNEL.value),
        "namespace": BKBASE_NAMESPACE_BK_MONITOR,
        "field_mappings": {
            "domain_name": "host",
            "port": "port",
            "username": "auth.sasl.username",
            "password": "auth.sasl.password",
            "sasl_mechanisms": "auth.sasl.mechanism",
            "is_auth": "auth.sasl.enabled",
            "stream_to_id": "streamToId",
            "v3_channel_id": "v3ChannelId",
            "version": "version",
        },
        "cluster_type": models.ClusterInfo.TYPE_KAFKA,
    },
]

BKBASE_RT_STORAGE_TYPES_OPTION_NAME = "bkbase_rt_storage_types"
