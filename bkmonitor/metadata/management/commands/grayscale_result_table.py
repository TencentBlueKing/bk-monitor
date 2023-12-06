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

from urllib import parse

from django.core.management.base import BaseCommand, CommandError
from django.db.transaction import atomic

from metadata import config, models


class Command(BaseCommand):
    """
    灰度添加 result_table, 目前只支持 argus 数据源
    """

    def add_arguments(self, parser):
        """
        增加参数配置
        :param parser:
        :return:
        """

        parser.add_argument("table_id", type=str, help="table id, example: system.cpu_summary")

        parser.add_argument("tenant_id", type=str, help="tenant_id, example: system")

        parser.add_argument(
            "cluster_name",
            type=str,
            help="argus cluster name, example: argus-cluster1",
        )

        parser.add_argument(
            "--receive_addr",
            type=str,
            help="argus cluster receive address, example: http://127.0.0.1:19291",
        )

    def init_argus_cluster(self, cluster_name, receive_addr):
        """初始化 argus 集群信息"""

        # 查询已经存在的集群配置
        # 修改和删除, 请通过其他方式操作, 如 sql
        try:
            cluster = models.ClusterInfo.objects.get(
                cluster_name=cluster_name, cluster_type=models.ClusterInfo.TYPE_ARGUS
            )
            return cluster.cluster_id
        except models.ClusterInfo.DoesNotExist:
            pass

        # 新建集群, receive_addr 不能为空
        if not receive_addr:
            raise ValueError("init new cluster, receive_addr can not be empty")

        parse_result = parse.urlparse(receive_addr)
        domain, port = parse_result.netloc.split(":")

        cluster = models.ClusterInfo.create_cluster(
            cluster_name=cluster_name,
            cluster_type=models.ClusterInfo.TYPE_ARGUS,
            domain_name=domain,
            port=port,
            registered_system=models.ClusterInfo.DEFAULT_REGISTERED_SYSTEM,
            operator="system",
            description="init by command",
            username="",
            password="",
            version="",
            custom_option="",
            schema=parse_result.scheme,
            is_ssl_verify=False,
        )

        return cluster.cluster_id

    @atomic(config.DATABASE_CONNECTION_NAME)
    def handle(self, *args, **options):
        table_id = options.get("table_id")
        tenant_id = options.get("tenant_id")
        cluster_name = options.get("cluster_name")
        receive_addr = options.get("receive_addr")

        try:
            cluster_id = self.init_argus_cluster(cluster_name, receive_addr)
        except Exception as err:
            raise CommandError("init argus cluster failed, %s" % err)

        self.stdout.write("grayscale result_table start")

        # 更新 datasource 的配置信息
        obj, created = models.ArgusStorage.objects.get_or_create(
            table_id=table_id, storage_cluster_id=cluster_id, defaults={"tenant_id": tenant_id}
        )
        if created:
            self.stdout.write("create argus datasource %s done" % obj)
        else:
            self.stdout.write("update argus datasource %s done" % obj)

        # 最小化原则, 只更新 consul 配置
        try:
            models.DataSourceResultTable.refresh_consul_config_by_table_id(table_id)
        except Exception as err:
            raise CommandError("grayscale result_table failed, %s" % err)

        self.stdout.write("grayscale result_table success")
