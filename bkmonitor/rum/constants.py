"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.conf import settings

# 获取需要增加事务的DB链接名
DATABASE_CONNECTION_NAME = getattr(settings, "METADATA_DEFAULT_DATABASE_NAME", "monitor_api")

# RUM 全局数据链路配置（替代 APM 的 DataLink 模型，从 Django settings 中读取）
# kafka 集群 ID，创建 data_id 时作为 mq_cluster 参数
RUM_KAFKA_CLUSTER_ID = getattr(settings, "RUM_KAFKA_CLUSTER_ID", None)
# ES 集群 ID，创建 RumDataSource 结果表时作为默认存储集群
RUM_ELASTICSEARCH_CLUSTER_ID = getattr(settings, "RUM_ELASTICSEARCH_CLUSTER_ID", None)


class ApdexConfigKey:
    """
    Apdex 配置键
    """

    APDEX_VIEW_LOAD = "apdex_view_load"
    APDEX_API_REQUEST = "apdex_api_request"
