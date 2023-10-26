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

from typing import Dict

from alarm_backends.core.cache.bcs_cluster import BcsClusterCacheManager
from alarm_backends.service.alert.enricher.translator.base import BaseTranslator
from constants.data_source import DataSourceLabel, DataTypeLabel


class BcsClusterTranslator(BaseTranslator):
    """
    bcs集群字段名翻译
    """

    def is_enabled(self) -> bool:
        return (
            self.data_source_label == DataSourceLabel.BK_MONITOR_COLLECTOR
            and self.data_type_label == DataTypeLabel.TIME_SERIES
            and self.strategy.get("scenario") == "kubernetes"
        )

    def translate(self, data: Dict) -> Dict:
        field = data.get("bcs_cluster_id")
        if not field:
            return data
        bcs_cluster_id = field.value
        cluster_info = BcsClusterCacheManager.get(bcs_cluster_id)
        if not cluster_info:
            return data
        # 修改集群ID的值，包含集群名称
        cluster_name = cluster_info.get("name")
        if cluster_name:
            field.display_value = f"{bcs_cluster_id}({cluster_name})"

        return data
