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

from django.conf import settings
from django.core.management.base import BaseCommand

from core.drf_resource import api
from core.errors.api import BKAPIError
from metadata import config, models


class Command(BaseCommand):
    """
    同步默认的消息队列(stream_to_info)信息到zk或gse，每次部署的时候执行
    """

    DEFAULT_MQ_STREAM_TO_NAME = "default_mq_stream_to"
    DEFAULT_STREAM_TO_REPORT_MODEL = models.DataSource.DEFAULT_MQ_TYPE

    @classmethod
    def sync_to_gse(cls):
        qs = models.ClusterInfo.objects.filter(is_register_to_gse=True)
        if not qs.exists():
            msg = (
                "no MQ for cluster type->[%s]," "maybe admin set something wrong?" % cls.DEFAULT_STREAM_TO_REPORT_MODEL
            )
            print(msg)
            return

        for mq_cluster in qs:
            try:
                if mq_cluster.is_default_cluster:
                    cls.register_default_to_gse(mq_cluster)
                else:
                    cls.register_to_gse(mq_cluster)
            except:  # noqa
                raise  # 这里不对异常捕获，需要抛出去，让Command执行失败

    @classmethod
    def update_stream_to_info_to_gse(cls, mq_cluster):
        """
        刷新数据库的集群信息，比如主机名，端口这些，更新到gse，保持两边一直
        """
        name = "mq_stream_to_{}".format(mq_cluster.cluster_id)
        if mq_cluster.is_default_cluster:
            name = cls.DEFAULT_MQ_STREAM_TO_NAME

        params = {
            "condition": {"stream_to_id": mq_cluster.gse_stream_to_id, "plat_name": config.DEFAULT_GSE_API_PLAT_NAME},
            "operation": {"operator_name": settings.COMMON_USERNAME},
            "specification": {
                "stream_to": {
                    "name": name,
                    "report_mode": cls.DEFAULT_STREAM_TO_REPORT_MODEL,
                    cls.DEFAULT_STREAM_TO_REPORT_MODEL: {
                        "storage_address": [{"ip": mq_cluster.domain_name, "port": mq_cluster.port}],
                        "sasl_username": mq_cluster.username,
                        "sasl_passwd": mq_cluster.password,
                    },
                }
            },
        }
        return api.gse.update_stream_to(**params)

    @classmethod
    def register_stream_to_info_to_gse(cls, mq_cluster):
        name = "mq_stream_to_{}".format(mq_cluster.cluster_id)
        if mq_cluster.is_default_cluster:
            name = cls.DEFAULT_MQ_STREAM_TO_NAME

        params = {
            "metadata": {"plat_name": config.DEFAULT_GSE_API_PLAT_NAME},
            "operation": {"operator_name": settings.COMMON_USERNAME},
            "stream_to": {
                "name": name,
                "report_mode": cls.DEFAULT_STREAM_TO_REPORT_MODEL,
                cls.DEFAULT_STREAM_TO_REPORT_MODEL: {
                    "storage_address": [{"ip": mq_cluster.domain_name, "port": mq_cluster.port}],
                    "sasl_username": mq_cluster.username,
                    "sasl_passwd": mq_cluster.password,
                },
            },
        }
        result = api.gse.add_stream_to(**params)
        mq_cluster.gse_stream_to_id = result["stream_to_id"]
        mq_cluster.save()

    @classmethod
    def is_default_stream_to_id_exists(cls):
        # 判断gse那边，默认的stream_to_id:500是否存在
        try:
            params = {
                "condition": {
                    "stream_to_id": config.ZK_GSE_DATA_CLUSTER_ID,
                    "plat_name": config.DEFAULT_GSE_API_PLAT_NAME,
                },
                "operation": {"operator_name": settings.COMMON_USERNAME},
            }
            result = api.gse.query_stream_to(**params)
            return bool(result)
        except BKAPIError as e:
            print("default zk gse data cluster id:{} not exists, error:{}".format(config.ZK_GSE_DATA_CLUSTER_ID, e))
            return False

    @classmethod
    def register_to_gse(cls, mq_cluster):
        if mq_cluster.gse_stream_to_id != -1:
            # 存在则更新stream_to信息
            cls.update_stream_to_info_to_gse(mq_cluster)
        else:
            cls.register_stream_to_info_to_gse(mq_cluster)

    @classmethod
    def register_default_to_gse(cls, mq_cluster):
        """
        看数据库是否已经更新好了stream_to_id
            - 是，直接更新gse的stream_to的信息，保持和数据库一致
            - 否，则走gse接口查询默认的stream_to_id:500是否存在
                - 存在，则直接使用500这个默认的id，更新到数据库
                - 不存在，则走接口创建一个stream_to_id，更新到数据库
        """
        # 判断数据库的stream_to_id是否存在
        if mq_cluster.gse_stream_to_id != -1:
            # 存在则更新stream_to信息
            cls.update_stream_to_info_to_gse(mq_cluster)
            return

        if cls.is_default_stream_to_id_exists():
            # 存在则直接使用这个stream_to_id, 并更新gse的stream_to信息
            mq_cluster.gse_stream_to_id = config.ZK_GSE_DATA_CLUSTER_ID
            mq_cluster.save()
            cls.update_stream_to_info_to_gse(mq_cluster)
        else:
            # 不存在则调用创建接口
            cls.register_stream_to_info_to_gse(mq_cluster)

    def handle(self, *args, **options):
        """
        同步默认的kafka信息到zk或者gse
        """
        self.sync_to_gse()
