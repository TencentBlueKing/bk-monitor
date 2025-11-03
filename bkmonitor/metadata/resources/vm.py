"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
from collections import OrderedDict
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.transaction import atomic
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bkmonitor.utils.request import get_request_tenant_id
from bkmonitor.utils.serializers import TenantIdField
from constants.common import DEFAULT_TENANT_ID
from core.drf_resource import Resource
from metadata import config, models
from metadata.models.space.constants import SpaceTypes
from metadata.service.data_source import query_biz_plugin_data_id_list
from metadata.service.vm_storage import (
    get_table_id_from_vm,
    query_bcs_cluster_vm_rts,
    query_vm_datalink_all,
)
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis

logger = logging.getLogger("metadata")


class CreateVmCluster(Resource):
    class RequestSerializer(serializers.Serializer):
        cluster_name = serializers.CharField(required=True, label="集群名称")
        domain_name = serializers.CharField(required=True, label="集群域名")
        port = serializers.IntegerField(required=False, label="集群端口", default=80)
        description = serializers.CharField(required=False, label="集群描述", default="vm 集群")
        is_default_cluster = serializers.BooleanField(required=False, label="是否设置为默认集群", default=False)

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict:
        bk_tenant_id = get_request_tenant_id()

        # 如果不设置为默认集群，则直接创建记录即可
        validated_request_data["cluster_type"] = models.ClusterInfo.TYPE_VM
        if not validated_request_data["is_default_cluster"]:
            obj = models.ClusterInfo.objects.create(bk_tenant_id=bk_tenant_id, **validated_request_data)
            return {"cluster_id": obj.cluster_id}

        # 否则，需要先把已有的默认集群设置为False，并且在集群创建后刷新空间使用的默认集群信息
        with atomic(config.DATABASE_CONNECTION_NAME):
            models.ClusterInfo.objects.filter(
                bk_tenant_id=bk_tenant_id, cluster_type=models.ClusterInfo.TYPE_VM, is_default_cluster=True
            ).update(is_default_cluster=False)
            obj = models.ClusterInfo.objects.create(bk_tenant_id=bk_tenant_id, **validated_request_data)
            # 刷新空间使用的 vm 集群
            # NOTE: 注意排除掉使用特定集群的空间
            models.SpaceVMInfo.objects.exclude(space_id__in=settings.SINGLE_VM_SPACE_ID_LIST).update(
                vm_cluster_id=obj.cluster_id
            )

        return {"cluster_id": obj.cluster_id}


class QueryVmDatalink(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_data_id = serializers.IntegerField(required=True, label="数据源 ID")

    def perform_request(self, data: OrderedDict) -> dict:
        return query_vm_datalink_all(data["bk_data_id"])


class QueryVmRtBySpace(Resource):
    class RequestSerializer(serializers.Serializer):
        space_type = serializers.CharField(required=True, label="空间类型")
        space_id = serializers.CharField(required=True, label="空间 ID")

    def perform_request(self, data: OrderedDict) -> dict:
        # 通过空间转换业务ID
        biz_id = models.Space.objects.get_biz_id_by_space(space_type=data["space_type"], space_id=data["space_id"])
        if not biz_id:
            raise ValidationError(f"not found space by space_type: {data['space_type']}, space_id: {data['space_id']}")
        biz_id = int(biz_id)
        # 如果是空间类型为业务类型，则还需要查看是否有配置插件
        tids = list(
            models.ResultTable.objects.filter(bk_biz_id=biz_id, default_storage="influxdb", is_enable=True).values_list(
                "table_id", flat=True
            )
        )
        if data["space_type"] == SpaceTypes.BKCC.value:
            biz_data_ids = query_biz_plugin_data_id_list(biz_id_list=[biz_id])
            data_id_list = biz_data_ids.get(biz_id) or []
            if data_id_list:
                _tids = list(
                    models.DataSourceResultTable.objects.filter(bk_data_id__in=data_id_list).values_list(
                        "table_id", flat=True
                    )
                )
                # 过滤可用的结果表
                tids.extend(
                    models.ResultTable.objects.filter(
                        table_id__in=_tids, default_storage="influxdb", is_enable=True
                    ).values_list("table_id", flat=True)
                )
        # 获取计算平台的结果表(后续获取不到计算平台数据源ID，不返回具体的计算平台数据源ID)
        return list(
            models.AccessVMRecord.objects.filter(result_table_id__in=tids).values_list("vm_result_table_id", flat=True)
        )


class QueryBcsClusterVmTableIds(Resource):
    class RequestSerializer(serializers.Serializer):
        bcs_cluster_id = serializers.CharField(required=True, label="BCS 集群ID")

    def perform_request(self, data: OrderedDict) -> dict:
        return query_bcs_cluster_vm_rts(data["bcs_cluster_id"])


class SwitchKafkaCluster(Resource):
    class RequestSerializer(serializers.Serializer):
        table_id = serializers.CharField(required=False, allow_blank=True, label="结果表ID")
        bk_base_data_id = serializers.IntegerField(required=False, label="计算平台数据源ID")
        vm_table_id = serializers.CharField(required=False, allow_blank=True, label="VM结果表ID")
        kafka_cluster_id = serializers.IntegerField(required=True, label="要切换的kafka集群ID")

        def validate(self, attrs: OrderedDict) -> dict:
            # 三个字段不能全为空， table_id 优先级最高，bk_base_data_id次之，最后是 vm 的结果表 id
            if not (attrs.get("table_id") or attrs.get("bk_base_data_id") or attrs.get("vm_table_id")):
                raise ValidationError("params [table_id], [bk_base_data_id]及[vm_table_id] is null")
            # 转换为监控的最小单元 table_id
            # 如果 table_id 存在，则直接返回
            data = {"kafka_cluster_id": attrs["kafka_cluster_id"]}
            if attrs.get("table_id"):
                data.update({"table_id": attrs["table_id"]})
                return data

            data.update(get_table_id_from_vm(attrs.get("bk_base_data_id"), attrs.get("vm_table_id")))
            return data

    def perform_request(self, validated_request_data: OrderedDict) -> None:
        # 若开启多租户模式，需要获取租户ID
        if settings.ENABLE_MULTI_TENANT_MODE:
            bk_tenant_id = get_request_tenant_id()
            logger.info("SwitchKafkaCluster: enable multi tenant mode,bk_tenant_id->[%s]", bk_tenant_id)
        else:
            bk_tenant_id = DEFAULT_TENANT_ID

        try:
            obj = models.KafkaStorage.objects.get(
                table_id=validated_request_data["table_id"], bk_tenant_id=bk_tenant_id
            )
        except models.KafkaStorage.DoesNotExist:
            raise ValidationError(f"not found kafka storage by table_id: {validated_request_data['table_id']}")

        # 如果相同则直接返回
        if obj.storage_cluster_id == validated_request_data["kafka_cluster_id"]:
            return

        obj.storage_cluster_id = validated_request_data["kafka_cluster_id"]
        obj.save(update_fields=["storage_cluster_id"])

        # 获取数据源
        try:
            bk_data_id = models.DataSourceResultTable.objects.get(
                table_id=validated_request_data["table_id"], bk_tenant_id=bk_tenant_id
            ).bk_data_id
        except models.DataSourceResultTable.DoesNotExist:
            raise ValidationError(f"not found data source by table_id: {validated_request_data['table_id']}")
        try:
            ds = models.DataSource.objects.get(bk_data_id=bk_data_id)
        except models.DataSource.DoesNotExist:
            raise ValidationError(f"not found data source by bk_data_id: {bk_data_id}")
        # 刷新数据源对应的 consul 记录
        ds.refresh_consul_config()


class NotifyDataLinkVmChange(Resource):
    """
    TODO：临时接口，待全量切换至V4后，统一使用V4数据一致性方案
    通知监控平台,某条链路发生了存储VM集群变更,只适用于V3链路
    """

    class RequestSerializer(serializers.Serializer):
        cluster_name = serializers.CharField(required=True, label="集群名称")
        vmrt = serializers.CharField(required=True, label="VM结果表ID")

    def perform_request(self, validated_request_data):
        bk_tenant_id = get_request_tenant_id()
        cluster_name = validated_request_data.get("cluster_name")
        vmrt = validated_request_data.get("vmrt")
        logger.info("NotifyDataLinkChangeStorageCluster: vmrt->[%s] will change to cluster->[%s]", vmrt, cluster_name)

        try:
            vm_cluster = models.ClusterInfo.objects.get(bk_tenant_id=bk_tenant_id, cluster_name=cluster_name)
        except models.ClusterInfo.DoesNotExist:
            logger.error("NotifyDataLinkChangeStorageCluster: can't find vm cluster name [%s]", cluster_name)
            raise ValidationError(f"can't find vm cluster name [{cluster_name}]")

        vm_records = models.AccessVMRecord.objects.filter(bk_tenant_id=bk_tenant_id, vm_result_table_id=vmrt)
        if not vm_records.exists():
            logger.warning("NotifyDataLinkChangeStorageCluster: no record for vm result table [%s]", vmrt)
            raise ValidationError(f"no record for vm result table [{vmrt}]")

        with transaction.atomic():
            vm_records.update(vm_cluster_id=vm_cluster.cluster_id)

        logger.info("NotifyDataLinkChangeStorageCluster: vmrt->[%s] has changed to cluster->[%s]", vmrt, cluster_name)


class QueryMetaInfoByVmrt(Resource):
    """
    根据VMRT查询关联的元信息,包含DataId、TableId、DataName、BkBizId
    """

    class RequestSerializer(serializers.Serializer):
        vmrt = serializers.CharField(required=True, label="VM结果表ID")

    def perform_request(self, validated_request_data):
        vmrt = validated_request_data.get("vmrt")

        try:
            vm_record = models.AccessVMRecord.objects.get(vm_result_table_id=vmrt)
        except models.AccessVMRecord.DoesNotExist:
            raise (ValidationError(f"not found vm record by vmrt: {vmrt}"))

        result_table_id = vm_record.result_table_id
        result_table = models.ResultTable.objects.get(table_id=result_table_id)
        data_id = models.DataSourceResultTable.objects.get(table_id=result_table_id).bk_data_id
        data_source = models.DataSource.objects.get(bk_data_id=data_id)

        return {
            "bk_data_id": data_id,
            "data_name": data_source.data_name,
            "monitor_table_id": result_table.table_id,
            "vm_result_table_id": vmrt,
            "bk_biz_id": result_table.bk_biz_id,
        }


class ModifyClusterByVmrts(Resource):
    """
    根据VMRT批量修改存储集群
    """

    class RequestSerializer(serializers.Serializer):
        vmrts = serializers.ListField(required=True, label="VM结果表ID列表")
        cluster_name = serializers.CharField(required=True, label="集群名称")
        bk_tenant_id = TenantIdField(label="租户ID")

    def perform_request(self, validated_request_data):
        vmrts = validated_request_data["vmrts"]
        cluster_name = validated_request_data["cluster_name"]
        bk_tenant_id = validated_request_data["bk_tenant_id"]

        logger.info("ModifyClusterByVmrts: vmrts->[%s] will change to cluster->[%s]", vmrts, cluster_name)

        try:
            vm_cluster = models.ClusterInfo.objects.get(bk_tenant_id=bk_tenant_id, cluster_name=cluster_name)
        except models.ClusterInfo.DoesNotExist:
            logger.error("ModifyClusterByVmrts: can't find vm cluster name [%s]", cluster_name)
            raise ValidationError(f"can't find vm cluster name [{cluster_name}]")
        except Exception as e:  # pylint: disable=broad-except
            logger.error("ModifyClusterByVmrts: get vm cluster name [%s] error: %s", cluster_name, e)
            raise ValidationError(f"get vm cluster name [{cluster_name}] error: {e}")

        # 查找关联的VM接入记录
        vm_queryset = models.AccessVMRecord.objects.filter(vm_result_table_id__in=vmrts, bk_tenant_id=bk_tenant_id)

        # 事务操作,批量更新集群ID
        with transaction.atomic():
            vm_queryset.update(vm_cluster_id=vm_cluster.cluster_id)

        logger.info("ModifyClusterByVmrts: vmrts->[%s] has changed to cluster->[%s]", vmrts, cluster_name)

        # 统计监控侧RT列表,执行更新
        result_table_ids = list(vm_queryset.values_list("result_table_id", flat=True))

        # 推送路由
        client = SpaceTableIDRedis()
        client.push_table_id_detail(table_id_list=result_table_ids, is_publish=True, bk_tenant_id=bk_tenant_id)

        logger.info("ModifyClusterByVmrts: vmrts->[%s] push router successfully", vmrts)

        return True
