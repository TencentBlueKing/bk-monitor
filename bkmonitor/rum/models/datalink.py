"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.db import models

from bkmonitor.utils.db import JsonField

# 全局默认数据链路配置对应的业务 ID。保持与 packages/rum_web/core/discover/precalculation/storage.py
# 中同名常量一致；本模块独立定义以避免 rum_web → rum.models 的循环导入。
GLOBAL_CONFIG_BK_BIZ_ID = 0


class DataLink(models.Model):
    """
    数据链路配置
    预计算数据存储配置数据格式: (可以将预计算数据存储不同集群中)
    {
        "cluster": [
            {
                "cluster_id": 1,
                "table_name": "xx"
            },
            {
                "cluster_id": 2,
                "table_name": "xx"
            }
        ]
    }
    """

    bk_biz_id = models.IntegerField("业务id")
    kafka_cluster_id = models.IntegerField("kafka集群id", null=True)
    elasticsearch_cluster_id = models.IntegerField(
        "默认ES集群ID(在快速创建应用、创建默认预计算集群时会用到)", null=True
    )
    pre_calculate_config = JsonField("RUM 预计算数据存储配置", null=True)

    @classmethod
    def get_data_link(cls, bk_biz_id):
        data_link = cls.objects.filter(bk_biz_id=bk_biz_id).first()
        if data_link:
            return data_link
        # 取全局默认配置
        data_link = cls.objects.filter(bk_biz_id=GLOBAL_CONFIG_BK_BIZ_ID).first()
        return data_link

    @classmethod
    def create_global(cls, **kwargs):
        return cls.objects.create(bk_biz_id=GLOBAL_CONFIG_BK_BIZ_ID, **kwargs)

    def to_json(self):
        return {
            "elasticsearch_cluster_id": self.elasticsearch_cluster_id,
        }