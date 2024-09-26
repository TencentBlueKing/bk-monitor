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

import json
from datetime import datetime, timedelta
from typing import List

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from core.drf_resource import Resource
from metadata import models
from metadata.config import METADATA_RESULT_TABLE_WHITE_LIST
from metadata.models import AccessVMRecord
from metadata.models.constants import DataIdCreatedFromSystem
from metadata.models.space.constants import (
    RESULT_TABLE_DETAIL_KEY,
    SPACE_TO_RESULT_TABLE_KEY,
    SpaceTypes,
)
from metadata.utils.redis_tools import RedisTools


class AddBkDataTableIdsResource(Resource):
    """添加访问计算平台指标发现的结果表"""

    class RequestSerializer(serializers.Serializer):
        bkdata_table_ids = serializers.ListField(child=serializers.CharField(), required=True)

    def perform_request(self, data):
        bkdata_table_ids = data["bkdata_table_ids"]
        self._add_tid_list(bkdata_table_ids)

    def _add_tid_list(self, bkdata_table_ids: List):
        tid_list = list(
            AccessVMRecord.objects.filter(vm_result_table_id__in=bkdata_table_ids).values_list(
                "result_table_id", flat=True
            )
        )
        if not tid_list:
            raise ValidationError("not found bkmonitor table id")

        # 获取已有的数据
        data = RedisTools.get_list(METADATA_RESULT_TABLE_WHITE_LIST)
        data.extend(tid_list)
        # 去重
        data = list(set(data))
        # 保存到redis
        RedisTools.set(METADATA_RESULT_TABLE_WHITE_LIST, json.dumps(data))


class QueryDataLinkInfoResource(Resource):
    """
    查询链路信息
    """

    class RequestSerializer(serializers.Serializer):
        bk_data_id = serializers.CharField(label="数据源ID", required=True)

    def perform_request(self, data):
        bk_data_id = data["bk_data_id"]

        # 数据源信息
        ds = models.DataSource.objects.get(bk_data_id=bk_data_id)
        ds_infos = self._get_data_id_details(ds=ds)

        # 清洗配置信息（Kafka）
        etl_infos = self._get_etl_details(ds=ds)

        dsrt = models.DataSourceResultTable.objects.filter(bk_data_id=bk_data_id)
        table_ids = list(dsrt.values_list('table_id', flat=True))

        # 监控平台结果表信息
        rt_infos = self._get_table_ids_details(table_ids)
        # 计算平台结果表信息
        bkbase_infos = self._get_bkbase_details(table_ids)

        # 健康状态
        # TimeSeriesGroup -- 指标过期问题
        time_series_etl_configs = ['bk_standard_v2_time_series', 'bk_standard', 'bk_exporter']
        expired_metrics = []
        if ds.etl_config in time_series_etl_configs:
            expired_metrics = self._check_expired_metrics(bk_data_id=bk_data_id)

        # 授权访问的space_uid列表
        authorized_space_uids = self._get_authorized_space_uids(bk_data_id=bk_data_id)

        # 检查RT-指标路由 RESULT_TABLE_DETAIL_KEY
        error_rt_detail_infos = self._check_result_table_detail_metric_router_status(table_ids=table_ids)

        # 检查SPACE_TO_RESULT_TABLE_DETAIL_KEY 中是否存在对应结果表的路由关系
        space_to_result_table_router_infos = self._check_space_to_result_table_router(
            table_ids=table_ids, authorized_space_uids=authorized_space_uids
        )

        return {
            "数据源信息": ds_infos,
            "清洗信息": etl_infos,
            "结果表信息": rt_infos,
            "计算平台信息": bkbase_infos,
            "授权访问的空间UID": authorized_space_uids,
            "过期指标信息": expired_metrics,
            '结果表指标路由信息': error_rt_detail_infos,
            '空间路由信息': space_to_result_table_router_infos,
        }

    def _get_data_id_details(self, ds):
        """
        组装数据源详情信息
        """
        return {
            "数据源ID": ds.bk_data_id,
            "数据源名称": ds.data_name,
            "清洗配置(etl_config)": ds.etl_config,
            "是否启用": ds.is_enable,
            "是否是平台级别": ds.is_platform_data_id,
            "数据源来源": ds.created_from,
            "消息队列集群ID": ds.mq_cluster_id,
            'Consul路径': ds.consul_config_path,
            "Transfer集群ID": ds.transfer_cluster_id if ds.created_from == DataIdCreatedFromSystem.BKDATA.value else None,
            "链路版本": "V4链路" if ds.created_from == 'bkdata' else 'V3链路',
        }

    def _get_etl_details(self, ds):
        """
        获取数据源清洗详情信息
        """
        # 清洗配置信息（Kafka）
        cluster = models.ClusterInfo.objects.get(cluster_id=ds.mq_cluster_id)
        mq_config = models.KafkaTopicInfo.objects.get(id=ds.mq_config_id)

        etl_infos = {
            "Kafka集群ID": cluster.cluster_id,
            "Kafka集群名称": cluster.cluster_name,
            "Kafka集群域名": cluster.domain_name,
            "Topic": mq_config.topic,
            "分区数量": mq_config.partition,
        }
        return etl_infos

    def _get_table_ids_details(self, table_ids):
        """
        根据table_ids，批量获取结果表详情信息
        """
        table_ids_details = []
        # 批量化处理
        for table_id in table_ids:
            try:
                rt = models.ResultTable.objects.get(table_id=table_id)
                if rt.bk_biz_id > 0:
                    space = models.Space.objects.get(space_type_id=SpaceTypes.BKCC.value, space_id=rt.bk_biz_id)
                if rt.bk_biz_id < 0:
                    space = models.Space.objects.get(id=abs(rt.bk_biz_id))

                table_ids_details.append(
                    {
                        "结果表ID": rt.table_id,
                        "存储方案": rt.default_storage,
                        "归属业务ID": rt.bk_biz_id,
                        "空间UID": '{}__{}'.format(space.space_type_id, space.space_id) if rt.bk_biz_id != 0 else '全局',
                        "空间名称": space.space_name if rt.bk_biz_id != 0 else '全局',
                        "是否启用": rt.is_enable,
                    }
                )
            except Exception:
                continue

        return table_ids_details

    def _get_bkbase_details(self, table_ids):
        """
        根据table_ids，批量获取计算平台结果表详情信息
        """
        bkbase_details = []
        for table_id in table_ids:
            vmrts = models.AccessVMRecord.objects.filter(result_table_id=table_id)
            if not vmrts.exists():
                bkbase_details.append({"异常信息": "接入计算平台记录不存在！"})
                continue
            for vm in vmrts:
                bkbase_details.append(
                    {
                        "VM结果表ID": vm.vm_result_table_id,
                        "查询集群ID": vm.vm_cluster_id,
                        "接入集群ID": vm.storage_cluster_id,
                        "计算平台ID": vm.bk_base_data_id,
                    }
                )
        return bkbase_details

    def _check_expired_metrics(self, bk_data_id):
        """
        针对时序指标类型，检查其是否存在指标过期问题
        """
        expired_metric_infos = []
        now = timezone.now()
        expired_time = now - timedelta(seconds=settings.TIME_SERIES_METRIC_EXPIRED_SECONDS)
        ts_group = models.TimeSeriesGroup.objects.get(bk_data_id=bk_data_id)
        ts_metrics = models.TimeSeriesMetric.objects.filter(group_id=ts_group.time_series_group_id)
        remote_metrics = ts_group.get_metrics_from_redis()
        metric_dict = {metric.field_name: metric for metric in ts_metrics}

        for remote_metric in remote_metrics:
            field_name = remote_metric['field_name']
            # 检查该指标是否存在于 TimeSeriesMetric 中
            if field_name in metric_dict:
                metric = metric_dict[field_name]
                # 检查 last_modify_time 是否超过一个月
                if metric.last_modify_time < expired_time:
                    remote_time = datetime.fromtimestamp(remote_metric['last_modify_time'], tz=timezone.utc)
                    time_difference = (remote_time - metric.last_modify_time).total_seconds() / 3600
                    expired_metric_infos.append(
                        {
                            'metric_name': metric.field_name,
                            '上次修改时间': metric.last_modify_time,
                            'Transfer/计算平台时间': datetime.fromtimestamp(
                                remote_metric['last_modify_time'], tz=timezone.utc
                            ),
                            "时间差": "{}小时".format(time_difference),
                        }
                    )
        return expired_metric_infos

    def _get_authorized_space_uids(self, bk_data_id):
        """
        根据bk_data_id,查询其路由信息
        """
        # 路由信息
        authorized_spaces = list(
            models.SpaceDataSource.objects.filter(bk_data_id=bk_data_id).values_list("space_type_id", "space_id")
        )
        authorized_space_uids = [f"{space_type}__{space_id}" for space_type, space_id in authorized_spaces]
        return authorized_space_uids

    def _check_result_table_detail_metric_router_status(self, table_ids):
        """
        检查结果表指标路由
        若在Transfer/计算平台侧存在指标，但是在RESULT_TABLE_DETAIL中不存在，说明路由异常
        """
        error_rt_detail_router_infos = []
        for table_id in table_ids:
            router = RedisTools.hget(RESULT_TABLE_DETAIL_KEY, table_id)
            ts_group = models.TimeSeriesGroup.objects.get(table_id=table_id)
            remote_metrics = ts_group.get_metrics_from_redis()
            router_data = json.loads(router.decode('utf-8'))
            # 从 router_data 中提取存在的字段列表
            router_fields = set(router_data["fields"])
            remote_fields = {metric['field_name'] for metric in remote_metrics}

            # 找出在 remote_metrics 中存在但在 router 中不存在的字段
            missing_fields = remote_fields - router_fields
            if missing_fields:
                error_rt_detail_router_infos.append(
                    {
                        table_id: {
                            "缺失指标": missing_fields,
                        }
                    }
                )
            else:
                error_rt_detail_router_infos.append({table_id: {"路由信息": "路由正常"}})
        return error_rt_detail_router_infos

    def _check_space_to_result_table_router(self, table_ids, authorized_space_uids):
        """
        检查空间-结果表路由
        若在空间允许访问的结果表中不包含该table_id对应的结果表，说明空间路由异常
        """
        space_to_result_table_router_infos = {}

        for item in authorized_space_uids:
            # 从 Redis 获取当前空间的路由信息
            space_router = RedisTools.hget(SPACE_TO_RESULT_TABLE_KEY, item)
            space_router_data = json.loads(space_router.decode('utf-8'))

            # 初始化每个空间的记录列表
            space_to_result_table_router_infos[item] = []

            for table_id in table_ids:
                # 检查 table_id 是否在 space_router 中
                if table_id in space_router_data:
                    # 保存对应的记录及其 filters
                    record = space_router_data[table_id]
                    # 将所需信息添加到当前 space_uid 的列表中
                    space_to_result_table_router_infos[item].append(
                        {'table_id': table_id, 'filters': record['filters'], 'status': '正常'}  # 标记状态为正常
                    )
                else:
                    # 如果记录未找到，记录 table_id 并标记为异常
                    space_to_result_table_router_infos[item].append(
                        {'table_id': table_id, 'filters': None, 'status': '异常'}  # 由于不存在，filters 设置为 None  # 标记状态为异常
                    )

        return space_to_result_table_router_infos
