"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.drf_resource import api
from metadata import models
from metadata.models.constants import DataIdCreatedFromSystem
from metadata.models.data_link import utils
from metadata.models.space.constants import EtlConfigs
from metadata.models.vm.utils import access_v2_bkdata_vm
from metadata.service.data_source import modify_data_id_source


class Command(BaseCommand):
    """
    将数据源从InfluxDB链路，迁移至BkBase V4链路
    """

    help = "switch data id from influxdb to bkbase v4"

    def add_arguments(self, parser):
        parser.add_argument("--bk_data_id", type=str, help="switched target data id")
        parser.add_argument("--kafka_name", type=str, help="switched target bkbase kafka_name")
        parser.add_argument("--bk_biz_id", type=str, help="switched source bk_biz_id")

    def handle(self, *args, **options):
        self.stdout.write("start to switch switch data id from influxdb to bkbase v4")
        bk_data_id = int(options.get("bk_data_id"))
        kafka_name = options.get("kafka_name", "kafka_outer_default")
        bk_biz_id = options.get("bk_biz_id", settings.DEFAULT_BKDATA_BIZ_ID)

        # 校验不能为空
        if not bk_data_id:
            raise CommandError("bk_data_id must given!")

        datasource = models.DataSource.objects.get(bk_data_id=bk_data_id)
        # Step1. 校验，非单指标单表类型不允许迁移
        if datasource.etl_config != EtlConfigs.BK_STANDARD_V2_TIME_SERIES.value:
            raise CommandError("only support bk_standard_v2_time_series type datasource!")

        # Step2. 更改数据源来源为bkdata，并删除Consul+停用Transfer
        modify_data_id_source(
            bk_tenant_id=datasource.bk_tenant_id,
            data_id_list=[bk_data_id],
            source_type=DataIdCreatedFromSystem.BKDATA.value,
        )

        # Step3. 将数据源信息同步至BkBase，组装配置
        bkbase_data_name = utils.compose_bkdata_data_id_name(datasource.data_name)
        self.stdout.write(
            f"data_id: {bk_data_id}, kafka_name: {kafka_name} use bkbase_data_name: {bkbase_data_name} to access bkbase"
        )
        # 创建DataId实例（计算平台侧）
        data_id_ins, _ = models.DataIdConfig.objects.get_or_create(
            name=bkbase_data_name, namespace="bkmonitor", bk_biz_id=bk_biz_id
        )
        # 组装DataId Config
        config = self.compose_data_id_config(
            data_id_ins=data_id_ins, datasource=datasource, kafka_name="kafka_outer_default"
        )
        # 将bk_data_id修改为int
        config["spec"]["predefined"]["dataId"] = int(config["spec"]["predefined"]["dataId"])

        self.stdout.write(f"use data_id_config->{config} to access bkbase")

        # Step4. 下发DataId Config至BkBase
        api.bkdata.apply_data_link(bk_tenant_id=datasource.bk_tenant_id, config=[config])

        # Step5. 将完整链路接入至BkBase
        table_id = models.DataSourceResultTable.objects.get(bk_data_id=bk_data_id).table_id
        self.stdout.write(
            f"use bk_data_id->{bk_data_id},bk_biz_id->{bk_biz_id},table_id->{table_id} to access bkbase v4"
        )
        access_v2_bkdata_vm(
            bk_tenant_id=datasource.bk_tenant_id, bk_biz_id=bk_biz_id, table_id=table_id, data_id=bk_data_id
        )

        # Step6. 验证此前接入的资源是否畅通
        self.stdout.write(f"bk_data_id->{bk_data_id}, bkbase component config->{data_id_ins.component_config}")

    def compose_data_id_config(self, data_id_ins, datasource, kafka_name) -> dict:
        """
        组装生成DataId配置
        @param data_id_ins: 数据源实例（计算平台侧）
        @param datasource: 数据源
        @param kafka_name: kafka名称（计算平台侧）
        @return: data_id配置
        """
        bk_data_id = int(datasource.bk_data_id)  # 确保bk_data_id是整数
        topic = str(datasource.mq_config.topic)  # 确保topic_name是字符串
        self.stdout.write(f"use bk_data_id->{bk_data_id},topic->{topic} to compose config")

        tpl = """
        {
            "kind": "DataId",
            "metadata": {
                "name": "{{name}}",
                "namespace": "{{namespace}}",
                "labels": {"bk_biz_id": "{{bk_biz_id}}"}
            },
            "spec": {
                "alias": "{{name}}",
                "bizId": {{monitor_biz_id}},
                "description": "{{name}}",
                "maintainers": {{maintainers}},
                "predefined": {
                    "dataId": "{{bk_data_id}}",
                    "channel": {
                        "kind": "KafkaChannel",
                        "namespace": "{{namespace}}",
                        "name": "{{kafka_name}}"
                    },
                    "topic": "{{topic_name}}"
                }
            }
        }
        """

        maintainer = settings.BK_DATA_PROJECT_MAINTAINER.split(",")
        return utils.compose_config(
            tpl=tpl,
            render_params={
                "name": data_id_ins.name,
                "namespace": data_id_ins.namespace,
                "bk_biz_id": data_id_ins.bk_biz_id,  # 数据实际归属的业务ID
                "monitor_biz_id": settings.DEFAULT_BKDATA_BIZ_ID,  # 接入者的业务ID
                "maintainers": json.dumps(maintainer),
                "bk_data_id": bk_data_id,
                "kafka_name": kafka_name,
                "topic_name": topic,
            },
            err_msg_prefix="compose data_id config",
        )
