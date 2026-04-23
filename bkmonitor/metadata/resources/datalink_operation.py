"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
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
from typing import Any

from rest_framework import serializers

from bkmonitor.utils.serializers import TenantIdField
from core.drf_resource import Resource, api
from metadata import models
from metadata.models.space.ds_rt import get_space_table_id_data_id
from metadata.models.space.utils import get_related_spaces
from metadata.utils.basic import get_biz_id_by_space_uid
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis

logger = logging.getLogger("metadata")


def extract_cluster_id(data_name):
    # 定义匹配集群ID的正则表达式
    pattern = r"(BCS-K8S-\d+)"
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
        bk_tenant_id = TenantIdField(label="租户ID")
        space_type = serializers.CharField(label="空间类型", required=True)
        space_id = serializers.CharField(label="空间ID", required=True)
        rtx = serializers.CharField(label="用户名", required=True)
        send_mail = serializers.BooleanField(label="是否发送邮件", required=False, default=True)
        with_related_spaces = serializers.BooleanField(label="是否包含关联空间", required=False, default=False)

    def perform_request(self, validated_request_data: dict[str, Any]):
        bk_tenant_id = validated_request_data["bk_tenant_id"]
        space_type = validated_request_data["space_type"]
        space_id = validated_request_data["space_id"]
        rtx = validated_request_data["rtx"]
        send_mail = validated_request_data["send_mail"]
        with_related_spaces = validated_request_data["with_related_spaces"]

        logger.info(
            "SpaceDataLinkMetaReport: try to get space info file, space_type->[%s], space_id->[%s],"
            "with_related_spaces->[%s],send_mail->[%s]",
            space_type,
            space_id,
            with_related_spaces,
            send_mail,
        )
        # 创建内存中的文件缓冲区
        csv_buffer = io.StringIO(newline="")
        writer = csv.writer(csv_buffer)

        writer.writerow(
            [
                "数据DataId",
                "数据源名称",
                "Kafka集群ID",
                "Kafka集群域名",
                "Kafka Topic名称",
                "Kafka分区数",
                "清洗配置类型",
                "链路版本",
                "归属空间名称",
                "归属空间类型",
                "归属空间ID",
                "结果表",
                "计算平台ID",
                "计算平台VMRT",
                "VM存储集群",
                "ES集群名称",
                "ES集群域名",
                "ES过期时间",
                "ES轮转大小(GB)",
            ]
        )

        # 中间处理逻辑保持不变，只需将涉及 temp_file 的操作改为 writer
        space_uid = f"{space_type}__{space_id}"
        bk_biz_id = space_id
        expected_bk_biz_id = get_biz_id_by_space_uid(bk_tenant_id, space_uid)

        # 如果是bkcc空间类型，查询关联的bkci空间
        if space_type == "bkcc" and with_related_spaces:
            related_spaces = get_related_spaces(space_type, space_id, target_space_type_id="bkci")
            logger.info(
                "SpaceDataLinkMetaReport: found related spaces for bkcc space->[%s], related_spaces->[%s]",
                space_uid,
                related_spaces,
            )
        else:
            related_spaces = []

        if space_type != "bkcc":
            space_record = models.Space.objects.get(space_type_id=space_type, space_id=space_id)
            bk_biz_id = -space_record.pk

        data = get_space_table_id_data_id(
            bk_tenant_id=bk_tenant_id,
            space_type=space_type,
            space_id=space_id,
            include_platform_data_id=False,
            from_authorization=False,
        )
        data_ids = list(data.values())

        # 合并bkcc和关联的bkci空间的数据
        for related_space in related_spaces:
            data = get_space_table_id_data_id(
                bk_tenant_id=bk_tenant_id,
                space_type="bkci",
                space_id=related_space,
                include_platform_data_id=False,
                from_authorization=False,
            )
            data_ids.extend(list(data.values()))

        # 使用set去重data_ids
        data_ids = list(set(data_ids))
        table_ids = []
        all_data = []  # 用于存储所有数据，作为 JSON 返回

        for data_id in data_ids:
            ds = models.DataSource.objects.get(bk_tenant_id=bk_tenant_id, bk_data_id=data_id)

            # 获取集群ID
            try:
                cluster_id = extract_cluster_id(data_name=ds.data_name)
                if cluster_id:
                    cluster_bk_biz_id = models.BCSClusterInfo.objects.get(
                        bk_tenant_id=bk_tenant_id, cluster_id=cluster_id
                    ).bk_biz_id
                    if cluster_bk_biz_id != expected_bk_biz_id:  # 若集群归属业务不符合预期，跳过本次循环
                        logger.info(
                            "SpaceDataLinkMetaReport: cluster_id->[%s], data_id->[%s], not independent "
                            "cluster, cluster belongs to->[%s]",
                            cluster_id,
                            ds.bk_data_id,
                            cluster_bk_biz_id,
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
                models.DataSourceResultTable.objects.filter(bk_tenant_id=bk_tenant_id, bk_data_id=data_id).values_list(
                    "table_id", flat=True
                )
            )
            table_ids = table_ids + temp_table_ids

        # 合并 log_table_ids 的处理，查询当前空间及其关联空间的 log_table_ids
        log_table_ids = list(
            models.ResultTable.objects.filter(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id).values_list(
                "table_id", flat=True
            )
        )

        # 如果是 bkcc，查询关联的 bkci 空间的 log_table_ids
        if related_spaces:
            for related_space in related_spaces:
                space_record = models.Space.objects.get(
                    bk_tenant_id=bk_tenant_id, space_type_id="bkci", space_id=related_space
                )
                related_bk_biz_id = -space_record.pk
                log_table_ids.extend(
                    list(
                        models.ResultTable.objects.filter(
                            bk_tenant_id=bk_tenant_id, bk_biz_id=related_bk_biz_id
                        ).values_list("table_id", flat=True)
                    )
                )

        table_ids.extend(log_table_ids)
        table_ids = list(set(table_ids))  # 去重

        for table_id in table_ids:
            try:
                data_id = models.DataSourceResultTable.objects.get(
                    bk_tenant_id=bk_tenant_id, table_id=table_id
                ).bk_data_id
                ds = models.DataSource.objects.get(bk_tenant_id=bk_tenant_id, bk_data_id=data_id)

                mq_config = ds.mq_config

                rt = models.ResultTable.objects.get(bk_tenant_id=bk_tenant_id, table_id=table_id)
                belong_space_name = None
                belong_space_type = None
                belong_space_id = None
                try:
                    if rt.bk_biz_id < 0:
                        belong_space = models.Space.objects.get(bk_tenant_id=bk_tenant_id, id=abs(rt.bk_biz_id))
                        belong_space_name = belong_space.space_name
                        belong_space_type = belong_space.space_type_id
                        belong_space_id = belong_space.space_id
                    else:
                        belong_space = models.Space.objects.get(
                            bk_tenant_id=bk_tenant_id, space_type_id="bkcc", space_id=rt.bk_biz_id
                        )
                        belong_space_name = belong_space.space_name
                        belong_space_type = belong_space.space_type_id
                        belong_space_id = belong_space.space_id
                except Exception as e:
                    logger.warning(
                        "SpaceDataLinkMetaReport: get space info failed, table_id:->[%s],error->[%s]", table_id, e
                    )

                vm_records = models.AccessVMRecord.objects.filter(bk_tenant_id=bk_tenant_id, result_table_id=table_id)
                es_storages = models.ESStorage.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id)
                if vm_records.exists():
                    for vm in vm_records:
                        vm_cluster_id = vm.vm_cluster_id
                        vm_cluster_name = models.ClusterInfo.objects.get(
                            bk_tenant_id=bk_tenant_id, cluster_id=vm_cluster_id
                        ).cluster_name
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
                                belong_space_name,
                                belong_space_type,
                                belong_space_id,
                                table_id,
                                vm.bk_base_data_id,
                                vm.vm_result_table_id,
                                vm_cluster_name,
                                None,
                                None,
                                None,
                                None,
                            ]
                        )
                        all_data.append(
                            {
                                "data_id": ds.bk_data_id,
                                "data_name": ds.data_name,
                                "mq_cluster_id": ds.mq_cluster_id,
                                "mq_cluster_domain": ds.mq_cluster.domain_name,
                                "mq_topic": mq_config.topic,
                                "mq_partition": mq_config.partition,
                                "etl_config": ds.etl_config,
                                "created_from": ds.created_from,
                                "belong_space_name": belong_space_name,
                                "belong_space_type": belong_space_type,
                                "belong_space_id": belong_space_id,
                                "table_id": table_id,
                                "vm_bk_base_data_id": vm.bk_base_data_id,
                                "vm_result_table_id": vm.vm_result_table_id,
                                "vm_cluster_name": vm_cluster_name,
                                "es_cluster_name": None,
                                "es_cluster_domain": None,
                                "es_retention": None,
                                "es_slice_size": None,
                            }
                        )
                elif es_storages.exists():
                    es_record = es_storages[0]
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
                            belong_space_name,
                            belong_space_type,
                            belong_space_id,
                            es_record.table_id,
                            None,
                            None,
                            None,
                            es_cluster.cluster_name,
                            es_cluster.domain_name,
                            es_record.retention,
                            es_record.slice_size,
                        ]
                    )
                    all_data.append(
                        {
                            "data_id": ds.bk_data_id,
                            "data_name": ds.data_name,
                            "mq_cluster_id": ds.mq_cluster_id,
                            "mq_cluster_domain": ds.mq_cluster.domain_name,
                            "mq_topic": mq_config.topic,
                            "mq_partition": mq_config.partition,
                            "etl_config": ds.etl_config,
                            "created_from": ds.created_from,
                            "belong_space_name": belong_space_name,
                            "belong_space_type": belong_space_type,
                            "belong_space_id": belong_space_id,
                            "table_id": table_id,
                            "vm_bk_base_data_id": None,
                            "vm_result_table_id": None,
                            "vm_cluster_name": None,
                            "es_cluster_name": es_cluster.cluster_name,
                            "es_cluster_domain": es_cluster.domain_name,
                            "es_retention": es_record.retention,
                            "es_slice_size": es_record.slice_size,
                        }
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
                            belong_space_name,
                            belong_space_type,
                            belong_space_id,
                            table_id,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                        ]
                    )
                    all_data.append(
                        {
                            "data_id": ds.bk_data_id,
                            "data_name": ds.data_name,
                            "mq_cluster_id": ds.mq_cluster_id,
                            "mq_cluster_domain": ds.mq_cluster.domain_name,
                            "mq_topic": mq_config.topic,
                            "mq_partition": mq_config.partition,
                            "etl_config": ds.etl_config,
                            "created_from": ds.created_from,
                            "belong_space_name": belong_space_name,
                            "belong_space_type": belong_space_type,
                            "belong_space_id": belong_space_id,
                            "table_id": table_id,
                            "vm_bk_base_data_id": None,
                            "vm_result_table_id": None,
                            "vm_cluster_name": None,
                            "es_cluster_name": None,
                            "es_cluster_domain": None,
                            "es_retention": None,
                            "es_slice_size": None,
                        }
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
                    "\ufeff".encode() + csv_content.encode("utf-8-sig")  # 添加 BOM + 兼容 Excel 的编码
                ).decode("utf-8"),  # 兼容中文
            }
        ]

        space_name = models.Space.objects.get(
            bk_tenant_id=bk_tenant_id, space_type_id=space_type, space_id=space_id
        ).space_name
        title = f"监控平台--{space_name} 链路元信息报表"

        if send_mail:
            res = api.cmsi.send_mail(
                bk_tenant_id=bk_tenant_id,
                receiver__username=rtx,
                title=title,
                content=f"{space_name} 链路元信息报表已生成，请查看附件。",
                attachments=attachments,
            )
            logger.info("SpaceDataLinkMetaReport: send msg to->[%s], result->[%s]", rtx, res)

        return {"message": f"空间 {space_name} 的链路元信息报表已生成", "raw_data": all_data}


class SyncBkBaseResultTableFieldsResource(Resource):
    """
    同步 BKBase 结果表字段到监控平台

    根据传入的 result_table_id（VMRT），从 BKBase 获取结果表结构，
    并同步字段（维度和指标）到本地 ResultTableField 表，最后推送路由。

    使用场景：预计算 v4 接口接入，无需自动发现，直接同步字段。
    """

    # BKBase 字段类型到监控平台字段类型的映射
    FIELD_TYPE_MAPPING = {
        "int": models.ResultTableField.FIELD_TYPE_INT,
        "long": models.ResultTableField.FIELD_TYPE_LONG,
        "float": models.ResultTableField.FIELD_TYPE_FLOAT,
        "double": models.ResultTableField.FIELD_TYPE_FLOAT,
        "string": models.ResultTableField.FIELD_TYPE_STRING,
        "text": models.ResultTableField.FIELD_TYPE_STRING,
        "boolean": models.ResultTableField.FIELD_TYPE_BOOLEAN,
        "timestamp": models.ResultTableField.FIELD_TYPE_TIMESTAMP,
    }

    # 需要忽略的系统字段
    IGNORED_FIELDS = {"timestamp", "_startTime_", "_endTime_", "time"}

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        result_table_ids = serializers.ListField(
            child=serializers.CharField(),
            label="BKBase结果表ID列表（VMRT）",
            help_text="例如：['00001_TotalGame_1min_group']，前缀数字为业务ID（space_id）",
            min_length=1,
        )
        data_label = serializers.CharField(
            label="数据标签",
            required=False,
            allow_blank=True,
            default="",
            help_text="可选的数据标签，用于推送 data_label 路由",
        )

    # BKBase 短链路固定使用 bkcc 空间类型
    BKBASE_SHORT_CHAIN_SPACE_TYPE = "bkcc"

    def perform_request(self, validated_request_data: dict[str, Any]):
        bk_tenant_id = validated_request_data["bk_tenant_id"]
        result_table_ids = validated_request_data["result_table_ids"]
        data_label = validated_request_data.get("data_label", "")
        # BKBase 短链路固定使用 bkcc 空间类型
        space_type = self.BKBASE_SHORT_CHAIN_SPACE_TYPE

        logger.info(
            "SyncBkBaseResultTableFieldsResource: start to sync fields for result_table_ids->[%s], bk_tenant_id->[%s],"
            "data_label->[%s], space_type->[%s]",
            result_table_ids,
            bk_tenant_id,
            data_label,
            space_type,
        )

        results = []
        updated_table_ids = []
        # 收集所有需要更新空间路由的 space_id 集合
        space_ids_to_update: set[str] = set()

        for vmrt in result_table_ids:
            try:
                # 从 vmrt 中提取 space_id（VMRT 格式: {biz_id}_{data_name}）
                space_id = self._extract_space_id_from_vmrt(vmrt)
                if not space_id:
                    raise ValueError(f"无法从 VMRT '{vmrt}' 中解析 space_id，VMRT 应以数字前缀开头，如 '100864_xxx'")

                # 同步单个结果表的字段
                result = self._sync_single_result_table(
                    bk_tenant_id=bk_tenant_id,
                    vmrt=vmrt,
                    data_label=data_label,
                    space_type=space_type,
                    space_id=space_id,
                )
                results.append(result)
                if result.get("status") == "success":
                    updated_table_ids.append(result["table_id"])
                    # 收集需要更新的 space_id
                    if space_id:
                        space_ids_to_update.add(space_id)
            except Exception as e:
                logger.exception(
                    "SyncBkBaseResultTableFieldsResource: failed to sync fields for vmrt->[%s], error->[%s]",
                    vmrt,
                    e,
                )
                results.append(
                    {
                        "vmrt": vmrt,
                        "status": "failed",
                        "message": str(e),
                    }
                )

        # 将成功更新的字段推送路由
        if updated_table_ids:
            logger.info(
                "SyncBkBaseResultTableFieldsResource: pushing router for table_ids->[%s]",
                updated_table_ids,
            )
            space_redis = SpaceTableIDRedis()

            # 1. 推送结果表详情路由(在哪个集群查询， 有哪些字段可以查询)
            space_redis.push_table_id_detail(
                table_id_list=updated_table_ids,
                is_publish=True,
                bk_tenant_id=bk_tenant_id,
            )

            # 2. 推送空间路由(这个空间下有哪些结果表可以查询)
            for sid in space_ids_to_update:
                logger.info(
                    "SyncBkBaseResultTableFieldsResource: pushing space_table_ids for space_type->[%s], space_id->[%s]",
                    space_type,
                    sid,
                )
                space_redis.push_space_table_ids(
                    space_type=space_type,
                    space_id=sid,
                    is_publish=True,
                )

            # 3. 如果提供了 data_label，推送 data_label 路由(这个标签对应哪些结果表)
            if data_label:
                logger.info(
                    "SyncBkBaseResultTableFieldsResource: pushing data_label_table_ids for data_label->[%s]",
                    data_label,
                )
                space_redis.push_data_label_table_ids(
                    data_label_list=[data_label],
                    table_id_list=updated_table_ids,
                    is_publish=True,
                    bk_tenant_id=bk_tenant_id,
                )

        return {
            "total": len(result_table_ids),
            "success_count": len(updated_table_ids),
            "results": results,
        }

    @staticmethod
    def _extract_space_id_from_vmrt(vmrt: str) -> str:
        """
        从 VMRT 中提取 space_id

        VMRT 格式通常为: {biz_id}_{data_name}，如 "100864_DsRecordUpload_TotalGame_1min_group"
        :param vmrt: BKBase 结果表ID
        :return: 提取的 space_id
        """
        parts = vmrt.split("_")
        if parts and parts[0].isdigit():
            return parts[0]
        return ""

    def _sync_single_result_table(
        self,
        bk_tenant_id: str,
        vmrt: str,
        data_label: str = "",
        space_type: str = "bkcc",
        space_id: str = "",
    ) -> dict[str, Any]:
        """
        同步单个 BKBase 结果表的字段

        :param bk_tenant_id: 租户ID
        :param vmrt: BKBase 结果表ID（VMRT）
        :param data_label: 数据标签（可选）
        :param space_type: 空间类型
        :param space_id: 空间ID
        :return: 同步结果
        """
        # 构建监控平台的 table_id
        table_id = f"{vmrt}.__default__".lower()

        # 检查结果表是否存在
        if not models.ResultTable.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id).exists():
            raise ValueError(f"结果表 {table_id} 不存在，请先创建结果表")

        # 从 BKBase 获取结果表结构
        logger.info(
            "SyncBkBaseResultTableFieldsResource: fetching result table info from bkdata for vmrt->[%s]",
            vmrt,
        )
        table_info = api.bkdata.get_result_table(bk_tenant_id=bk_tenant_id, result_table_id=vmrt)

        if not table_info:
            raise ValueError(f"无法从 BKBase 获取结果表 {vmrt} 的信息")

        fields = table_info.get("fields", [])
        if not fields:
            raise ValueError(f"结果表 {vmrt} 没有字段信息")

        # 解析字段，区分维度和指标
        metrics = []
        dimensions = []
        for field in fields:
            field_name = field.get("field_name", "")

            # 跳过系统字段
            if field_name in self.IGNORED_FIELDS:
                continue

            field_type = self._map_field_type(field.get("field_type", "string"))
            is_dimension = field.get("is_dimension", False)
            if field_type in ["string", "text"]:
                is_dimension = True

            field_data = {
                "field_name": field_name,
                "field_type": field_type,
                "description": field.get("description", "") or field.get("field_alias", "") or field_name,
                "is_dimension": is_dimension,
                # 保留 BKBase 侧的原始操作人和时间信息
                "created_by": field.get("created_by", ""),
                "created_at": field.get("created_at", ""),
                "updated_by": field.get("updated_by", ""),
                "updated_at": field.get("updated_at", ""),
            }

            if field_data["is_dimension"]:
                dimensions.append(field_data)
            else:
                metrics.append(field_data)

        # 同步字段到数据库
        created_count, updated_count = self._sync_fields_to_db(
            bk_tenant_id=bk_tenant_id,
            table_id=table_id,
            metrics=metrics,
            dimensions=dimensions,
        )

        # 更新或创建 BkBaseShortChainResultTable 记录（用于短链路空间路由）
        self._update_short_chain_record(
            bk_tenant_id=bk_tenant_id,
            table_id=table_id,
            vmrt=vmrt,
            bk_biz_id=int(space_id),
            data_label=data_label,
        )

        # 如果提供了 data_label，更新结果表的 data_label
        if data_label:
            models.ResultTable.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id).update(
                data_label=data_label
            )

        logger.info(
            "SyncBkBaseResultTableFieldsResource: synced fields for table_id->[%s], "
            "created->[%d], updated->[%d], metrics->[%d], dimensions->[%d]",
            table_id,
            created_count,
            updated_count,
            len(metrics),
            len(dimensions),
        )

        return {
            "vmrt": vmrt,
            "table_id": table_id,
            "status": "success",
            "metrics_count": len(metrics),
            "dimensions_count": len(dimensions),
            "created_count": created_count,
            "updated_count": updated_count,
            "space_type": space_type,
            "space_id": space_id,
            "data_label": data_label,
        }

    def _update_short_chain_record(
        self,
        bk_tenant_id: str,
        table_id: str,
        vmrt: str,
        bk_biz_id: int,
        data_label: str,
    ) -> None:
        """
        更新或创建 BkBaseShortChainResultTable 记录

        :param bk_tenant_id: 租户ID
        :param table_id: 监控平台结果表ID
        :param vmrt: BKBase 结果表ID
        :param bk_biz_id: 业务ID
        :param data_label: 数据标签
        """
        defaults = {
            "bkbase_rt_id": vmrt,
            "bk_biz_id": bk_biz_id,
            "data_label": data_label,
        }
        _, created = models.BkBaseShortChainResultTable.objects.update_or_create(
            bk_tenant_id=bk_tenant_id,
            table_id=table_id,
            defaults=defaults,
        )
        logger.info(
            "SyncBkBaseResultTableFieldsResource: %s BkBaseShortChainResultTable for table_id->[%s], "
            "vmrt->[%s], bk_biz_id->[%s]",
            "created" if created else "updated",
            table_id,
            vmrt,
            bk_biz_id,
        )

    def _map_field_type(self, bkdata_field_type: str) -> str:
        """
        将 BKBase 字段类型映射为监控平台字段类型

        :param bkdata_field_type: BKBase 字段类型
        :return: 监控平台字段类型
        """
        return self.FIELD_TYPE_MAPPING.get(
            bkdata_field_type.lower(),
            models.ResultTableField.FIELD_TYPE_STRING,
        )

    def _sync_fields_to_db(
        self,
        bk_tenant_id: str,
        table_id: str,
        metrics: list[dict],
        dimensions: list[dict],
    ) -> tuple[int, int]:
        """
        同步字段到数据库，不存在则新建，存在则更新

        :param bk_tenant_id: 租户ID
        :param table_id: 结果表ID
        :param metrics: 指标字段列表
        :param dimensions: 维度字段列表
        :return: (创建数量, 更新数量)
        """
        created_count = 0
        updated_count = 0

        all_fields = []
        for field in metrics:
            all_fields.append(
                {
                    **field,
                    "tag": models.ResultTableField.FIELD_TAG_METRIC,
                }
            )
        for field in dimensions:
            all_fields.append(
                {
                    **field,
                    "tag": models.ResultTableField.FIELD_TAG_DIMENSION,
                }
            )

        # 从结果表中获取现有字段
        existing_fields = {
            f.field_name: f
            for f in models.ResultTableField.objects.filter(
                bk_tenant_id=bk_tenant_id,
                table_id=table_id,
            )
        }

        fields_to_create = []
        fields_to_update = []

        for field_data in all_fields:
            field_name = field_data["field_name"]
            existing_field = existing_fields.get(field_name)

            creator = field_data.get("created_by") or "system"
            updater = field_data.get("updated_by") or "system"
            # 解析 BKBase 侧的时间，格式为 "2026-02-04 11:59:55"
            updated_at = self._parse_bkdata_datetime(field_data.get("updated_at"))

            if existing_field:
                # 更新现有字段
                need_update = False
                if existing_field.field_type != field_data["field_type"]:
                    existing_field.field_type = field_data["field_type"]
                    need_update = True
                if existing_field.tag != field_data["tag"]:
                    existing_field.tag = field_data["tag"]
                    need_update = True
                if existing_field.description != field_data["description"]:
                    existing_field.description = field_data["description"]
                    need_update = True

                if need_update:
                    existing_field.last_modify_user = updater
                    if updated_at:
                        existing_field.last_modify_time = updated_at
                    fields_to_update.append(existing_field)
            else:
                # 创建新字段
                fields_to_create.append(
                    models.ResultTableField(
                        bk_tenant_id=bk_tenant_id,
                        table_id=table_id,
                        field_name=field_name,
                        field_type=field_data["field_type"],
                        description=field_data["description"],
                        tag=field_data["tag"],
                        is_config_by_user=False,
                        creator=creator,
                        last_modify_user=updater,
                    )
                )

        # 批量创建
        if fields_to_create:
            models.ResultTableField.objects.bulk_create(fields_to_create, batch_size=100)
            created_count = len(fields_to_create)

        # 批量更新
        if fields_to_update:
            models.ResultTableField.objects.bulk_update(
                fields_to_update,
                fields=["field_type", "tag", "description", "last_modify_user", "last_modify_time"],
                batch_size=100,
            )
            updated_count = len(fields_to_update)

        return created_count, updated_count

    @staticmethod
    def _parse_bkdata_datetime(datetime_str: str | None):
        """
        解析 BKBase 返回的时间字符串

        :param datetime_str: 时间字符串，格式为 "2026-02-04 11:59:55"
        :return: datetime 对象，解析失败返回 None
        """
        if not datetime_str:
            return None

        from datetime import datetime

        from django.utils import timezone

        try:
            # BKBase 返回的时间格式为 "2026-02-04 11:59:55"
            naive_dt = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
            # 转换为带时区的时间（假设为服务器本地时区）
            return timezone.make_aware(naive_dt)
        except (ValueError, TypeError):
            return None
