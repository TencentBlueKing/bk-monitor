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
import base64
import csv
import io
import logging
import re

from rest_framework import serializers

from core.drf_resource import Resource, api
from metadata import models
from metadata.models.space.ds_rt import get_space_table_id_data_id
from metadata.utils.basic import get_biz_id_by_space_uid

logger = logging.getLogger("metadata")


def extract_cluster_id(data_name):
    # 定义匹配集群ID的正则表达式
    pattern = r'(BCS-K8S-\d+)'
    # 使用re.search查找匹配的内容
    match = re.search(pattern, data_name)
    # 如果找到匹配内容，返回匹配的字符串
    if match:
        return match.group(1)
    return None


class SpaceDataLinkMetaReport(Resource):
    """
    空间链路元信息报表
    """

    class RequestSerializer(serializers.Serializer):
        space_type = serializers.CharField(label="空间类型", required=True)
        space_id = serializers.CharField(label="空间ID", required=True)
        rtx = serializers.CharField(label="用户名", required=True)

    def perform_request(self, validated_request_data):
        space_type = validated_request_data["space_type"]
        space_id = validated_request_data["space_id"]
        rtx = validated_request_data["rtx"]

        logger.info(
            "SpaceDataLinkMetaReport: try to get space info file, space_type->[%s], space_id->[%s]",
            space_type,
            space_id,
        )
        # 创建内存中的文件缓冲区
        csv_buffer = io.StringIO(newline='')
        writer = csv.writer(csv_buffer)

        # 写入 CSV 文件的头部
        writer.writerow(
            [
                '数据DataId',
                '数据源名称',
                'Kafka集群名称',
                'Kafka集群域名',
                'Kafka Topic名称',
                'Kafka分区数',
                '清洗配置类型',
                '链路版本',
                '归属空间',
                '结果表',
                '计算平台ID',
                '计算平台VMRT',
                'ES集群名称',
                'ES集群域名',
                'ES过期时间',
                'ES轮转大小(GB)',
            ]
        )

        # 中间处理逻辑保持不变，只需将涉及 temp_file 的操作改为 writer
        space_uid = f'{space_type}__{space_id}'
        bk_biz_id = space_id
        expected_bk_biz_id = get_biz_id_by_space_uid(space_uid)

        if space_type != 'bkcc':
            space_record = models.Space.objects.get(space_type_id=space_type, space_id=space_id)
            bk_biz_id = -space_record.id

        data = get_space_table_id_data_id(
            space_type, space_id, include_platform_data_id=False, from_authorization=False
        )
        data_ids = list(data.values())
        table_ids = []

        # 使用 tqdm 包装 es_storages 以显示进度条
        for data_id in data_ids:
            ds = models.DataSource.objects.get(bk_data_id=data_id)

            # 获取集群ID
            try:
                cluster_id = extract_cluster_id(data_name=ds.data_name)
                if cluster_id:
                    bk_biz_id = models.BCSClusterInfo.objects.get(cluster_id=cluster_id).bk_biz_id
                    if bk_biz_id != expected_bk_biz_id:  # 若集群归属业务不符合预期，跳过本次循环
                        logger.info(
                            "SpaceDataLinkMetaReport: cluster_id->[%s], data_id->[%s], not independent "
                            "cluster, cluster belongs to->[%s]",
                            cluster_id,
                            ds.bk_data_id,
                            bk_biz_id,
                        )
                        continue
            except Exception as e:  # pylint: disable=broad-except
                logger.info(
                    "SpaceDataLinkMetaReport: failed to extract cluster_id, data_id->[%s], error->[%s]",
                    ds.bk_data_id,
                    e,
                )
                continue

            temp_table_ids = list(
                models.DataSourceResultTable.objects.filter(bk_data_id=data_id).values_list('table_id', flat=True)
            )
            table_ids = table_ids + temp_table_ids
        log_table_ids = list(models.ResultTable.objects.filter(bk_biz_id=bk_biz_id).values_list('table_id', flat=True))
        table_ids = table_ids + log_table_ids
        table_ids = list(set(table_ids))
        for table_id in table_ids:
            try:
                data_id = models.DataSourceResultTable.objects.get(table_id=table_id).bk_data_id
                ds = models.DataSource.objects.get(bk_data_id=data_id)

                mq_config = ds.mq_config

                vm_records = models.AccessVMRecord.objects.filter(result_table_id=table_id)
                es_storages = models.ESStorage.objects.filter(table_id=table_id)
                if vm_records.exists():
                    for vm in vm_records:
                        writer.writerow(
                            [
                                ds.bk_data_id,
                                ds.data_name,
                                ds.mq_cluster_id,
                                ds.mq_cluster.domain_name,
                                mq_config.topic,
                                mq_config.partition,
                                ds.etl_config,
                                ds.created_from,
                                space_id,
                                table_id,
                                vm.bk_base_data_id,
                                vm.vm_result_table_id,
                                None,
                                None,
                                None,
                                None,
                            ]
                        )
                elif es_storages.exists():
                    es_record = es_storages.first()
                    es_cluster = models.ClusterInfo.objects.get(cluster_id=es_record.storage_cluster_id)
                    writer.writerow(
                        [
                            ds.bk_data_id,
                            ds.data_name,
                            ds.mq_cluster_id,
                            ds.mq_cluster.domain_name,
                            mq_config.topic,
                            mq_config.partition,
                            ds.etl_config,
                            ds.created_from,
                            space_id,
                            table_id,
                            None,
                            None,
                            es_cluster.cluster_name,
                            es_cluster.domain_name,
                            es_record.retention,
                            es_record.slice_size,
                        ]
                    )
                else:
                    writer.writerow(
                        [
                            ds.bk_data_id,
                            ds.data_name,
                            ds.mq_cluster_id,
                            ds.mq_cluster.domain_name,
                            mq_config.topic,
                            mq_config.partition,
                            ds.etl_config,
                            ds.created_from,
                            space_id,
                            table_id,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                        ]
                    )
            except Exception as e:  # pylint: disable=broad-except
                logger.error(
                    "SpaceDataLinkMetaReport: failed to get space info file, table_id->[%s], error->[%s]", table_id, e
                )
                continue
        # 获取内存中的 CSV 内容
        csv_content = csv_buffer.getvalue()
        csv_buffer.close()

        # 构建返回结构
        attachments = [
            {
                "filename": f"{space_type}_{space_id}_data_info.csv",
                "disposition": "attachment",
                "type": "csv",
                "content": base64.b64encode(
                    '\ufeff'.encode('utf-8') + csv_content.encode('utf-8-sig')  # 添加 BOM + 兼容 Excel 的编码
                ).decode(
                    'utf-8'
                ),  # 兼容中文
            }
        ]

        space_name = models.Space.objects.get(space_type_id=space_type, space_id=space_id).space_name
        title = f"监控平台--{space_name} 链路元信息报表"

        res = api.cmsi.send_msg(
            receiver__username=rtx,
            title=title,
            content=f"{space_name} 链路元信息报表已生成，请查看附件。",
            msg_type='mail',
            attachments=attachments,
        )
        logger.info("SpaceDataLinkMetaReport: send msg to->[%s], result->[%s]", rtx, res)

        return {"message": f"空间 {space_name} 的链路元信息报表已生成", "attachments": attachments, 'msg': res.get('message')}
