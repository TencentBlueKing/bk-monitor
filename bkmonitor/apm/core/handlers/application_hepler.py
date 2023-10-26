# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - Resource SDK (BlueKing - Resource SDK) available.
Copyright (C) 2022 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""
from django.conf import settings

from apm.models import DataLink
from core.drf_resource import resource


class ApplicationHelper:

    DEFAULT_CLUSTER_TYPE = "elasticsearch"
    DEFAULT_CLUSTER_NAME = "_default"

    @classmethod
    def get_default_cluster_id(cls, bk_biz_id):
        """
        从DataLink/集群列表中获取默认集群
        """

        datalink = DataLink.get_data_link(bk_biz_id)
        if datalink and datalink.elasticsearch_cluster_id:
            return datalink.elasticsearch_cluster_id

        clusters = resource.metadata.query_cluster_info(
            cluster_type=cls.DEFAULT_CLUSTER_TYPE,
            # 兼容metadata逻辑
            registered_system=settings.APP_CODE,
        )
        return next(
            (
                i.get("cluster_config").get("cluster_id")
                for i in clusters
                if i.get("cluster_config", {}).get("registered_system") == cls.DEFAULT_CLUSTER_NAME
            ),
            None,
        )
