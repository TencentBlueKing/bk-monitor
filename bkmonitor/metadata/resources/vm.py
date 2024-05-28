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

from collections import OrderedDict
from typing import Dict

from django.conf import settings
from django.db.models import Q
from django.db.transaction import atomic
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from core.drf_resource import Resource
from metadata import config, models
from metadata.models.space.constants import SpaceTypes
from metadata.models.space.space_data_source import get_real_biz_id
from metadata.service.data_source import query_biz_plugin_data_id_list
from metadata.service.vm_storage import (
    get_table_id_from_vm,
    query_bcs_cluster_vm_rts,
    query_vm_datalink,
)


class QueryBizByBkBase(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_base_data_id_list = serializers.ListField(child=serializers.IntegerField(), required=False, default=[])
        bk_base_vm_table_id_list = serializers.ListField(child=serializers.CharField(), required=False, default=[])

        def validate(self, data: OrderedDict) -> OrderedDict:
            # 判断参数不能同时为空
            if not (data.get("bk_base_data_id_list") or data.get("bk_base_vm_table_id_list")):
                raise ValueError("params is null")
            return data

    def perform_request(self, data):
        bk_base_data_id_list = data.get("bk_base_data_id_list") or []
        bk_base_vm_table_id_list = data.get("bk_base_vm_table_id_list") or []

        # 获取 table id
        table_id_bk_base_data_ids = {
            qs["result_table_id"]: qs["bk_base_data_id"]
            for qs in models.AccessVMRecord.objects.filter(
                Q(bk_base_data_id__in=bk_base_data_id_list) | Q(vm_result_table_id__in=bk_base_vm_table_id_list)
            ).values("result_table_id", "bk_base_data_id")
        }

        # 通过 table id 获取对应的业务信息
        table_id_biz_ids = {
            qs["table_id"]: qs["bk_biz_id"]
            for qs in models.ResultTable.objects.filter(table_id__in=table_id_bk_base_data_ids.keys()).values(
                "table_id", "bk_biz_id"
            )
        }

        # 针对业务为`0`的业务，需要通过 tsgroup 或 eventgroup 过滤，然后通过 dataname 进行拆分
        zero_biz_table_id_list = [table_id for table_id, biz_id in table_id_biz_ids.items() if biz_id == 0]

        # 获取对应的 data id
        table_id_data_ids = {
            qs["table_id"]: qs["bk_data_id"]
            for qs in models.DataSourceResultTable.objects.filter(table_id__in=zero_biz_table_id_list).values(
                "bk_data_id", "table_id"
            )
        }
        # 获取 data name
        data_id_names = {}
        data_id_space_uid_map = {}
        for qs in models.DataSource.objects.filter(bk_data_id__in=table_id_data_ids.values()).values(
            "bk_data_id", "data_name", "space_uid"
        ):
            data_id_names[qs["bk_data_id"]] = qs["data_name"]
            data_id_space_uid_map[qs["bk_data_id"]] = qs["space_uid"]
        # 查询是否在指定的表中
        data_id_ts_group_flag = {
            obj["bk_data_id"]: True
            for obj in models.TimeSeriesGroup.objects.filter(table_id__in=zero_biz_table_id_list).values("bk_data_id")
        }
        data_id_event_group_flag = {
            obj["bk_data_id"]: True
            for obj in models.EventGroup.objects.filter(table_id__in=zero_biz_table_id_list).values("bk_data_id")
        }
        bk_base_data_id_biz_id = {}
        # 获取对应的数据
        for table_id, bk_biz_id in table_id_biz_ids.items():
            # 跳过没有匹配到数据
            bk_base_data_id = table_id_bk_base_data_ids.get(table_id)
            if not bk_base_data_id:
                continue
            # NOTE: 应该不会有小于 0 的业务，当业务 ID 大于 0 时，直接返回
            if bk_biz_id > 0:
                bk_base_data_id_biz_id[bk_base_data_id] = bk_biz_id
                continue

            # 获取 0 业务对应的真实业务 ID
            data_id = table_id_data_ids.get(table_id)
            if not data_id:
                bk_base_data_id_biz_id[bk_base_data_id] = 0

            data_name = data_id_names.get(data_id)
            space_uid = data_id_space_uid_map.get(data_id)
            is_in_ts_group = data_id_ts_group_flag.get(data_id) or False
            is_in_event_group = data_id_event_group_flag.get(data_id) or False
            bk_biz_id = get_real_biz_id(data_name, is_in_ts_group, is_in_event_group, space_uid)
            bk_base_data_id_biz_id[bk_base_data_id] = bk_biz_id

        return bk_base_data_id_biz_id


class CreateVmCluster(Resource):
    class RequestSerializer(serializers.Serializer):
        cluster_name = serializers.CharField(required=True, label="集群名称")
        domain_name = serializers.CharField(required=True, label="集群域名")
        port = serializers.IntegerField(required=False, label="集群端口", default=80)
        description = serializers.CharField(required=False, label="集群描述", default="vm 集群")
        is_default_cluster = serializers.BooleanField(required=False, label="是否设置为默认集群", default=False)

    def perform_request(self, data: OrderedDict) -> Dict:
        # 如果不设置为默认集群，则直接创建记录即可
        data["cluster_type"] = models.ClusterInfo.TYPE_VM
        if not data["is_default_cluster"]:
            obj = models.ClusterInfo.objects.create(**data)
            return {"cluster_id": obj.cluster_id}

        # 否则，需要先把已有的默认集群设置为False，并且在集群创建后刷新空间使用的默认集群信息
        with atomic(config.DATABASE_CONNECTION_NAME):
            models.ClusterInfo.objects.filter(cluster_type=models.ClusterInfo.TYPE_VM, is_default_cluster=True).update(
                is_default_cluster=False
            )
            obj = models.ClusterInfo.objects.create(**data)
            # 刷新空间使用的 vm 集群
            # NOTE: 注意排除掉使用特定集群的空间
            models.SpaceVMInfo.objects.exclude(space_id__in=settings.SINGLE_VM_SPACE_ID_LIST).update(
                vm_cluster_id=obj.cluster_id
            )

        return {"cluster_id": obj.cluster_id}


class QueryVmDatalink(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_data_id = serializers.IntegerField(required=True, label="数据源 ID")

    def perform_request(self, data: OrderedDict) -> Dict:
        return query_vm_datalink(data["bk_data_id"])


class QueryVmRtBySpace(Resource):
    class RequestSerializer(serializers.Serializer):
        space_type = serializers.CharField(required=True, label="空间类型")
        space_id = serializers.CharField(required=True, label="空间 ID")

    def perform_request(self, data: OrderedDict) -> Dict:
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

    def perform_request(self, data: OrderedDict) -> Dict:
        return query_bcs_cluster_vm_rts(data["bcs_cluster_id"])


class SwitchKafkaCluster(Resource):
    class RequestSerializer(serializers.Serializer):
        table_id = serializers.CharField(required=False, allow_blank=True, label="结果表ID")
        bk_base_data_id = serializers.IntegerField(required=False, label="计算平台数据源ID")
        vm_table_id = serializers.CharField(required=False, allow_blank=True, label="VM结果表ID")
        kafka_cluster_id = serializers.IntegerField(required=True, label="要切换的kafka集群ID")

        def validate(self, attrs: OrderedDict) -> Dict:
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
        try:
            obj = models.KafkaStorage.objects.get(table_id=validated_request_data["table_id"])
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
                table_id=validated_request_data["table_id"]
            ).bk_data_id
        except models.DataSourceResultTable.DoesNotExist:
            raise ValidationError(f"not found data source by table_id: {validated_request_data['table_id']}")
        try:
            ds = models.DataSource.objects.get(bk_data_id=bk_data_id)
        except models.DataSource.DoesNotExist:
            raise ValidationError(f"not found data source by bk_data_id: {bk_data_id}")
        # 刷新数据源对应的 consul 记录
        ds.refresh_consul_config()
