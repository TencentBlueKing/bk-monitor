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
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bkmonitor.utils.serializers import TenantIdField
from core.drf_resource import Resource, api
from metadata import models
from metadata.config import METADATA_RESULT_TABLE_WHITE_LIST
from metadata.models import AccessVMRecord, DataSource
from metadata.models.constants import DataIdCreatedFromSystem
from metadata.models.space.constants import (
    RESULT_TABLE_DETAIL_KEY,
    SPACE_TO_RESULT_TABLE_KEY,
    SpaceTypes,
)
from metadata.utils.redis_tools import RedisTools

logger = logging.getLogger("metadata")


class AddBkDataTableIdsResource(Resource):
    """添加访问计算平台指标发现的结果表"""

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        bkdata_table_ids = serializers.ListField(child=serializers.CharField(), required=True)

    def perform_request(self, validated_request_data):
        bk_tenant_id = validated_request_data["bk_tenant_id"]
        bkdata_table_ids = validated_request_data["bkdata_table_ids"]

        tid_list = list(
            AccessVMRecord.objects.filter(
                bk_tenant_id=bk_tenant_id, vm_result_table_id__in=bkdata_table_ids
            ).values_list("result_table_id", flat=True)
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
        bk_tenant_id = TenantIdField(label="租户ID")
        bk_data_id = serializers.CharField(label="数据源ID", required=True)
        is_complete = serializers.BooleanField(label="是否返回完整信息", default=False)

    def perform_request(self, validated_request_data):
        bk_tenant_id = validated_request_data["bk_tenant_id"]
        bk_data_id = validated_request_data["bk_data_id"]
        is_complete = validated_request_data["is_complete"]
        logger.info(
            "QueryDataLinkInfoResource: start to query bk_data_id: %s, is_complete: %s", bk_data_id, is_complete
        )
        try:
            # 避免缓存问题
            self.bklog_table_ids: list[str] = []
            self.time_series_table_ids: list[str] = []

            # 数据源信息
            try:
                ds = models.DataSource.objects.get(bk_tenant_id=bk_tenant_id, bk_data_id=bk_data_id)
            except models.DataSource.DoesNotExist:
                raise ValidationError(f"QueryDataLinkInfoResource: bk_data_id {bk_data_id} does not exist")
            ds_infos = self._get_data_id_details(ds=ds)

            # 清洗配置信息（Kafka）
            etl_infos = self._get_etl_details(ds=ds)

            dsrt = models.DataSourceResultTable.objects.filter(bk_data_id=bk_data_id)
            table_ids = list(dsrt.values_list("table_id", flat=True))

            # 监控平台结果表信息
            rt_infos = self._get_table_ids_details(bk_tenant_id=bk_tenant_id, table_ids=table_ids)

            # 计算平台结果表信息
            bkbase_infos = self._get_bkbase_details(bk_tenant_id=bk_tenant_id)

            # 若有ES结果表，额外拼接ES结果表信息+索引/别名状态
            es_storage_infos = {}
            if self.bklog_table_ids:
                es_storage_infos = self._get_es_storage_details(bk_tenant_id=bk_tenant_id)

            res = {
                "ds_infos": ds_infos,
                "etl_infos": etl_infos,
                "rt_infos": rt_infos,
                "es_storage_infos": es_storage_infos,
                "bkbase_infos": bkbase_infos,
            }

            if is_complete:
                # 健康状态
                # TimeSeriesGroup -- 指标过期问题
                # 当清洗配置为以下类型时，说明为时序指标数据，需要检查指标是否存在过期问题
                time_series_etl_configs = ["bk_standard_v2_time_series", "bk_standard", "bk_exporter"]
                expired_metrics = []
                if ds.etl_config in time_series_etl_configs:
                    expired_metrics = self._check_expired_metrics(bk_tenant_id=bk_tenant_id, bk_data_id=bk_data_id)

                # 授权访问的space_uid列表
                authorized_space_uids = self._get_authorized_space_uids(
                    bk_tenant_id=bk_tenant_id, bk_data_id=bk_data_id
                )

                # 检查RT-指标路由 RESULT_TABLE_DETAIL_KEY
                time_series_rt_detail_infos = self._check_result_table_detail_metric_router_status(
                    bk_tenant_id=bk_tenant_id
                )

                # 检查SPACE_TO_RESULT_TABLE_DETAIL_KEY 中是否存在对应结果表的路由关系
                space_to_result_table_router_infos = self._check_space_to_result_table_router(
                    bk_tenant_id=bk_tenant_id, table_ids=table_ids, authorized_space_uids=authorized_space_uids
                )
                res.update(
                    {
                        "authorized_space_uids": authorized_space_uids,
                        "expired_metrics": expired_metrics,
                        "rt_detail_router": time_series_rt_detail_infos,
                        "space_to_result_table_router_infos": space_to_result_table_router_infos,
                    }
                )

            return json.dumps(res, ensure_ascii=False)
        except Exception as e:
            logger.error(
                "QueryDataLinkInfoResource: Failed to query data_link information, bk_data_id: %s, error: %s",
                bk_data_id,
                str(e),
            )
            res = {"error_info": f"Error occurs->{str(e)}"}
            return json.dumps(res, ensure_ascii=False)

    def _get_data_id_details(self, ds: models.DataSource):
        """
        组装数据源详情信息
        """
        logger.info("QueryDataLinkInfoResource: start to get bk_data_id infos")
        return {
            "数据源ID": ds.bk_data_id,
            "数据源名称": ds.data_name,
            "请求来源系统": ds.source_system,
            "清洗配置(etl_config)": ds.etl_config,
            "是否启用": ds.is_enable,
            "是否是平台级别": ds.is_platform_data_id,
            "数据源来源": ds.created_from,
            "Consul路径": ds.consul_config_path,
            "Transfer集群ID": ds.transfer_cluster_id,
            "链路版本": "V4链路" if ds.created_from == DataIdCreatedFromSystem.BKDATA.value else "V3链路",
        }

    def _get_etl_details(self, ds: models.DataSource) -> dict[str, Any]:
        """
        获取数据源清洗详情信息
        """
        # 清洗配置信息（Kafka）
        logger.info("QueryDataLinkInfoResource: start to get bk_data_id etl infos")
        etl_infos = {}
        try:
            cluster = models.ClusterInfo.objects.get(bk_tenant_id=ds.bk_tenant_id, cluster_id=ds.mq_cluster_id)
            mq_config = models.KafkaTopicInfo.objects.get(id=ds.mq_config_id)

            etl_infos.update(
                {
                    "前端Kafka集群ID": cluster.cluster_id,
                    "前端Kafka集群名称": cluster.cluster_name,
                    "前端Kafka集群域名": cluster.domain_name,
                    "前端Kafka-Topic": mq_config.topic,
                    "前端Kafka分区数量": mq_config.partition,
                }
            )
        except Exception as e:  # pylint: disable=broad-except
            etl_infos.update({"status": "集群配置获取异常", "info": str(e)})
        return etl_infos

    def _get_table_ids_details(self, bk_tenant_id: str, table_ids: list[str]):
        """
        根据 table_ids，批量获取结果表详情信息
        """
        table_ids_details = {}

        # 批量化处理
        for table_id in table_ids:
            logger.info("QueryDataLinkInfoResource: start to get table_id: %s", table_id)
            try:
                rt = models.ResultTable.objects.get(bk_tenant_id=bk_tenant_id, table_id=table_id)
                if rt.bk_biz_id > 0:
                    space = models.Space.objects.get(
                        bk_tenant_id=bk_tenant_id, space_type_id=SpaceTypes.BKCC.value, space_id=rt.bk_biz_id
                    )
                elif rt.bk_biz_id < 0:
                    space = models.Space.objects.get(bk_tenant_id=bk_tenant_id, id=abs(rt.bk_biz_id))
                else:
                    space = None

                table_ids_details[table_id] = {
                    "存储方案": rt.default_storage,
                    "归属业务ID": rt.bk_biz_id,
                    "空间UID": f"{space.space_type_id}__{space.space_id}" if space else "全局",
                    "空间名称": space.space_name if space else "全局",
                    "是否启用": rt.is_enable,
                    "数据标签(data_label)": rt.data_label,
                }

                backend_kafka_config = models.KafkaStorage.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id)
                if backend_kafka_config:  # 若存在对应的后端Kafka配置，添加至返回信息
                    backend_kafka_cluster_id = backend_kafka_config[0].storage_cluster_id
                    backend_kafka_topic = backend_kafka_config[0].topic
                    backend_kafka_partition = backend_kafka_config[0].partition
                    backend_kafka_cluster = models.ClusterInfo.objects.get(
                        bk_tenant_id=bk_tenant_id, cluster_id=backend_kafka_cluster_id
                    )
                    backend_kafka_cluster_name = backend_kafka_cluster.cluster_name
                    backend_kafka_domain_name = backend_kafka_cluster.domain_name
                    table_ids_details[table_id].update(
                        {
                            "后端Kafka集群ID": backend_kafka_cluster_id,
                            "后端Kafka集群名称": backend_kafka_cluster_name,
                            "后端Kafka集群域名": backend_kafka_domain_name,
                            "后端Kafka-Topic": backend_kafka_topic,
                            "后端Kafka分区数量": backend_kafka_partition,
                        }
                    )

                if rt.default_storage == models.ClusterInfo.TYPE_ES:
                    self.bklog_table_ids.append(rt.table_id)
                else:
                    self.time_series_table_ids.append(rt.table_id)
            except Exception as e:  # pylint: disable=broad-except
                table_ids_details[table_id] = {"status": "查询异常", "info": str(e)}

        return table_ids_details

    def _get_bkbase_details(self, bk_tenant_id: str):
        """
        根据table_ids，批量获取计算平台结果表详情信息
        """
        bkbase_details = []
        for table_id in self.time_series_table_ids:
            logger.info("QueryDataLinkInfoResource: start to get bkbase_details: %s", table_id)
            vmrts = models.AccessVMRecord.objects.filter(bk_tenant_id=bk_tenant_id, result_table_id=table_id)
            if not vmrts.exists():
                bkbase_details.append({"异常信息": "接入计算平台记录不存在！"})
                continue
            for vm in vmrts:
                vm_cluster = models.ClusterInfo.objects.get(bk_tenant_id=bk_tenant_id, cluster_id=vm.vm_cluster_id)
                bkbase_details.append(
                    {
                        "VM结果表ID": vm.vm_result_table_id,
                        "查询集群ID": vm.vm_cluster_id,
                        "接入集群ID": vm.storage_cluster_id,
                        "计算平台ID": vm.bk_base_data_id,
                        "查询集群地址": vm_cluster.domain_name,
                    }
                )
        return bkbase_details

    def _get_es_storage_details(self, bk_tenant_id: str):
        """
        根据bklog_table_ids，批量获取ES存储详情信息,现阶段仅获取当前索引信息供排障使用
        """
        logger.info(
            "QueryDataLinkInfoResource: start to get es_storage_details, bklog_table_ids->[%s]", self.bklog_table_ids
        )
        table_ids_details = {}
        for table_id in self.bklog_table_ids:
            try:
                es_storage = models.ESStorage.objects.get(bk_tenant_id=bk_tenant_id, table_id=table_id)
                es_cluster = models.ClusterInfo.objects.get(
                    bk_tenant_id=bk_tenant_id, cluster_id=es_storage.storage_cluster_id
                )
                current_index_info = es_storage.current_index_info()
                last_index_name = es_storage.make_index_name(
                    current_index_info["datetime_object"],
                    current_index_info["index"],
                    current_index_info["index_version"],
                )
                index_details = es_storage.get_index_info(index_name=last_index_name)
                table_ids_details[table_id] = {
                    "ES索引大小切分阈值(GB)": es_storage.slice_size,
                    "ES索引分片时间间隔(分钟）": es_storage.slice_gap,
                    "ES时区配置": es_storage.time_zone,
                    "ES索引配置信息": es_storage.index_settings,
                    "ES索引集": es_storage.index_set,
                    "ES存储集群": es_storage.storage_cluster_id,
                    "ES存储集群名称": es_cluster.cluster_name,
                    "ES存储集群域名": es_cluster.domain_name,
                    "当前索引详情信息": index_details,
                    "是否需要进行索引轮转": es_storage._should_create_index(),
                }

            except Exception as e:  # pylint: disable=broad-except
                table_ids_details[table_id] = {"status": "查询异常", "info": str(e)}
                continue
        return table_ids_details

    def _check_expired_metrics(self, bk_tenant_id: str, bk_data_id: str):
        """
        针对时序指标类型，检查其是否存在指标过期问题
        """
        expired_metric_infos = []
        logger.info("QueryDataLinkInfoResource: start to check expired metrics")
        try:
            now = timezone.now()
            expired_time = now - timedelta(seconds=settings.TIME_SERIES_METRIC_EXPIRED_SECONDS)
            remote_expired_time = now - timedelta(seconds=5 * 24 * 3600)
            ts_group = models.TimeSeriesGroup.objects.get(bk_data_id=bk_data_id)
            ts_metrics = models.TimeSeriesMetric.objects.filter(group_id=ts_group.time_series_group_id)
            remote_metrics = ts_group.get_metrics_from_redis()
            metric_dict = {metric.field_name: metric for metric in ts_metrics}

            for remote_metric in remote_metrics:
                field_name = remote_metric["field_name"]
                # 检查该指标是否存在于 TimeSeriesMetric 中
                if field_name in metric_dict:
                    metric = metric_dict[field_name]
                    remote_time = datetime.fromtimestamp(remote_metric["last_modify_time"], tz=timezone.utc)
                    time_difference = (remote_time - metric.last_modify_time).total_seconds() / 3600
                    # 检查 last_modify_time 是否超过一个月，若Transfer侧时间超过五天未修改，说明该指标已禁用
                    if (metric.last_modify_time < expired_time) and not (remote_time < remote_expired_time):
                        expired_metric_infos.append(
                            {
                                "metric_name": metric.field_name,
                                "DB上次修改时间": metric.last_modify_time.strftime("%Y-%m-%d %H:%M:%S"),
                                # Note：DB修改时间理论上应该晚于远端修改时间
                                "Transfer/计算平台时间": datetime.fromtimestamp(
                                    remote_metric["last_modify_time"], tz=timezone.utc
                                ).strftime("%Y-%m-%d %H:%M:%S"),
                                "时间差": f"{time_difference}小时",
                            }
                        )
        except Exception:  # pylint: disable=broad-except
            pass
        return expired_metric_infos

    def _get_authorized_space_uids(self, bk_tenant_id: str, bk_data_id: str):
        """
        根据bk_data_id,查询其路由信息
        """
        # 路由信息
        authorized_spaces = list(
            models.SpaceDataSource.objects.filter(bk_tenant_id=bk_tenant_id, bk_data_id=bk_data_id).values_list(
                "space_type_id", "space_id"
            )
        )
        authorized_space_uids = [f"{space_type}__{space_id}" for space_type, space_id in authorized_spaces]
        return authorized_space_uids

    def _check_result_table_detail_metric_router_status(self, bk_tenant_id: str):
        """
        检查结果表指标路由
        若在Transfer/计算平台侧存在指标，但是在RESULT_TABLE_DETAIL中不存在，说明路由异常
        """
        rt_detail_router_infos = []
        for table_id in self.time_series_table_ids:
            try:
                if settings.ENABLE_MULTI_TENANT_MODE:
                    router = RedisTools.hget(RESULT_TABLE_DETAIL_KEY, f"{table_id}|{bk_tenant_id}")
                else:
                    router = RedisTools.hget(RESULT_TABLE_DETAIL_KEY, table_id)

                if not router:
                    rt_detail_router_infos.append({table_id: {"status": "路由不存在"}})
                    continue

                ts_group = models.TimeSeriesGroup.objects.get(bk_tenant_id=bk_tenant_id, table_id=table_id)
                remote_metrics = ts_group.get_metrics_from_redis()
                router_data = json.loads(router.decode("utf-8"))
                # 从 router_data 中提取存在的字段列表
                router_fields = set(router_data["fields"])
                remote_fields = {metric["field_name"] for metric in remote_metrics}

                # 找出在 remote_metrics 中存在但在 router 中不存在的字段
                missing_fields = remote_fields - router_fields
                if missing_fields:
                    rt_detail_router_infos.append({table_id: {"缺失指标": missing_fields}})
                else:
                    rt_detail_router_infos.append({table_id: {"status": "RT详情路由正常"}})
            except models.TimeSeriesGroup.DoesNotExist as e:
                rt_detail_router_infos.append({table_id: {"status": "时序分组不存在", "info": str(e)}})
            except Exception as e:  # pylint: disable=broad-except
                rt_detail_router_infos.append({table_id: {"status": "查询异常", "info": str(e)}})
        return rt_detail_router_infos

    def _check_space_to_result_table_router(
        self, bk_tenant_id: str, table_ids: list[str], authorized_space_uids: list[str]
    ):
        """
        检查空间-结果表路由
        若在空间允许访问的结果表中不包含该table_id对应的结果表，说明空间路由异常
        """
        space_to_result_table_router_infos = {}

        for item in authorized_space_uids:
            try:
                # 从 Redis 获取当前空间的路由信息
                if settings.ENABLE_MULTI_TENANT_MODE:
                    space_router = RedisTools.hget(SPACE_TO_RESULT_TABLE_KEY, f"{item}|{bk_tenant_id}")
                else:
                    space_router = RedisTools.hget(SPACE_TO_RESULT_TABLE_KEY, item)
                if not space_router:
                    continue
                space_router_data: dict[str, dict[str, dict]] = json.loads(space_router.decode("utf-8"))
                space_router_data = {key.split("|")[-1]: value for key, value in space_router_data.items()}
                # 初始化每个空间的记录列表
                space_to_result_table_router_infos[item] = []

                for table_id in table_ids:
                    # 检查 table_id 是否在 space_router 中
                    if table_id in space_router_data:
                        # 保存对应的记录及其 filters
                        record = space_router_data[table_id]
                        # 将所需信息添加到当前 space_uid 的列表中
                        space_to_result_table_router_infos[item].append(
                            {"table_id": table_id, "filters": record["filters"], "status": "正常"}  # 标记状态为正常
                        )
                    else:
                        # 如果记录未找到，记录 table_id 并标记为异常
                        space_to_result_table_router_infos[item].append(
                            {
                                "table_id": table_id,
                                "filters": None,
                                "status": "异常",
                            }  # 由于不存在，filters 设置为 None 并标记状态为异常，需要额外检查
                        )
            except Exception as e:
                space_to_result_table_router_infos[item] = [{"status": "空间路由信息不存在/异常", "info": str(e)}]
                continue

        return space_to_result_table_router_infos


class QueryDataIdsByBizIdResource(Resource):
    """
    根据业务ID查询其下所有数据源ID
    @param bk_biz_id 业务ID
    @return [{'bk_data_id': 123, 'monitor_table_id': 'xxx', 'storage_type': 'xxx'}]
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        bk_biz_id = serializers.CharField(label="业务ID", required=True)

    def perform_request(self, validated_request_data: dict[str, Any]) -> list[dict[str, Any]]:
        bk_tenant_id = validated_request_data["bk_tenant_id"]
        bk_biz_id = validated_request_data["bk_biz_id"]

        # 获取所有相关的 ResultTable
        result_tables = models.ResultTable.objects.filter(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id).values(
            "table_id", "default_storage"
        )

        table_ids = [r["table_id"] for r in result_tables]

        # 获取 table_id 对应的 default_storage，存入字典方便后续快速查找
        table_storage_mapping = {r["table_id"]: r["default_storage"] for r in result_tables}

        # 查询 DataSourceResultTable，获取 bk_data_id 和 table_id，确保数据一致性
        data_source_mappings = models.DataSourceResultTable.objects.filter(
            bk_tenant_id=bk_tenant_id, table_id__in=table_ids
        ).values("bk_data_id", "table_id")

        # 组合最终结果
        result = [
            {
                "bk_data_id": item["bk_data_id"],
                "monitor_table_id": item["table_id"],
                "storage_type": table_storage_mapping.get(item["table_id"]),
            }
            for item in data_source_mappings
        ]
        return result


class BizHasDataIdResource(Resource):
    """
    判断业务下是否存在结果表（有 RT 则必有 data_id 关联，不返回具体 DataId）
    @param bk_biz_id 业务ID
    @return {"has_data_id": bool}
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        bk_biz_id = serializers.CharField(label="业务ID", required=True)

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict[str, bool]:
        bk_tenant_id = validated_request_data["bk_tenant_id"]
        bk_biz_id = validated_request_data["bk_biz_id"]

        has_data_id = models.ResultTable.objects.filter(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id).exists()

        return {"has_data_id": has_data_id}


class IntelligentDiagnosisMetadataResource(Resource):
    """
    元数据智能诊断接口
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        bk_data_id = serializers.CharField(label="数据源ID", required=True)

    def perform_request(self, validated_request_data):
        from metadata.agents.diagnostic.metadata_diagnostic_agent import MetadataDiagnosisAgent

        bk_data_id = validated_request_data["bk_data_id"]
        bk_tenant_id = validated_request_data["bk_tenant_id"]

        if not DataSource.objects.filter(bk_tenant_id=bk_tenant_id, bk_data_id=bk_data_id).exists():
            logger.warning("data source not found, bk_tenant_id->[%s], bk_data_id->[%s]", bk_tenant_id, bk_data_id)
            return {"error": f"DataSource {bk_tenant_id}->{bk_data_id} 不存在"}

        logger.info("agents: try to diagnose bk_data_id->[%s]", bk_data_id)
        try:
            report = MetadataDiagnosisAgent.diagnose(bk_data_id=int(bk_data_id))
            return json.dumps(report, ensure_ascii=False)  # 适配中文返回
        except Exception as e:  # pylint: disable=broad-except
            logger.exception("metadata diagnose error, bk_data_id->[%s], error->[%s]", bk_data_id, e)
            return {"error": f"诊断过程中发生错误: {str(e)}"}


class GseSlotResource(Resource):
    """
    接收GSE消息槽的异步处理接口
    """

    class RequestSerializer(serializers.Serializer):
        message_id = serializers.CharField(label="消息ID")
        bk_agent_id = serializers.CharField(label="Agent ID")
        content = serializers.CharField(required=False, label="请求内容")

    def perform_request(self, validated_request_data: dict[str, str]):
        if not settings.GSE_SLOT_ID or not settings.GSE_SLOT_TOKEN:
            logger.warning("GseSlotResource: gse slot id or token is not set, skip")
            return False

        from metadata.task.tasks import process_gse_slot_message

        logger.info("GseSlotResource: receive gse slot message, %s", validated_request_data)
        process_gse_slot_message.delay(
            message_id=validated_request_data["message_id"],
            bk_agent_id=validated_request_data["bk_agent_id"],
            content=validated_request_data["content"],
            received_at=timezone.now().isoformat(),
        )

        return True


class QueryDataLinkMetadataResource(Resource):
    """
    [v2 改造] 查询数据链路元数据 - 扁平行数组

    沿用 v1 url ``/metadata/query_datalink_metadata/``, 改造 response shape:
    - v1: ``{ query, data_source, frontend_kafka, result_tables[] }`` 嵌套
    - v2: 返回 list, 由蓝鲸框架包装成 ``{ result, code, message, data: [...] }``

    一行 = ``(bk_tenant_id, bk_data_id, table_id)`` 组合, 共 ~98 字段平铺.

    入参 (4 选 1, ``bk_tenant_id`` 必填):
        - ``bk_data_id``         监控侧数据源 ID
        - ``result_table_id``    监控侧结果表 ID
        - ``vm_result_table_id`` VM 侧 RT ID
        - ``component_name``     V4 BKBase 资源名 ``{namespace}-{name}`` (P3 实现)
    """

    # 多 BCS 命名格式: ``bcs_k8s_40510`` / ``BCS-K8S-40510``
    BCS_CLUSTER_PATTERN = re.compile(r"bcs[_-]k8s[_-](\d+)", re.IGNORECASE)
    # BCSClusterInfo 中以 *DataID 命名的 6 个 dataid 字段
    _BCS_CLUSTER_DATAID_FIELDS = (
        "K8sMetricDataID",
        "CustomMetricDataID",
        "K8sEventDataID",
        "CustomEventDataID",
        "SystemLogDataID",
        "CustomLogDataID",
    )
    # *Config kind 映射 (用于 bkbase_components.kind)
    _V4_COMPONENT_CONFIGS: tuple[tuple[Any, str], ...] = ()  # 实例方法内初始化, 避免 import 时 model 未加载
    # P2 runtime: 单调用超时 + 线程池规模
    _RUNTIME_TIMEOUT_SEC = 3.0
    _MAX_RUNTIME_WORKERS = 16
    # P3 联邦集群策略 (用于 bcs_federal_info 填充)
    _BCS_FEDERAL_STRATEGIES = ("bcs_federal_subset_time_series", "bcs_federal_proxy_time_series")

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        bk_data_id = serializers.CharField(label="数据源ID", required=False, allow_null=True, allow_blank=True)
        result_table_id = serializers.CharField(label="结果表ID", required=False, allow_null=True, allow_blank=True)
        vm_result_table_id = serializers.CharField(
            label="VM结果表ID", required=False, allow_null=True, allow_blank=True
        )
        component_name = serializers.CharField(
            label="V4 BKBase 资源名 {namespace}-{name}", required=False, allow_null=True, allow_blank=True
        )

        def validate(self, attrs):
            if not any(attrs.get(k) for k in ("bk_data_id", "result_table_id", "vm_result_table_id", "component_name")):
                raise serializers.ValidationError(
                    "At least one of 'bk_data_id', 'result_table_id', 'vm_result_table_id', "
                    "'component_name' must be provided. "
                    "至少需要提供四个查询参数之一。"
                )
            return attrs

    def perform_request(self, validated_request_data) -> list[dict[str, Any]]:
        bk_tenant_id = validated_request_data["bk_tenant_id"]

        # Step 1: 入参解析为 (bk_data_id, table_id) 目标列表
        targets = self._resolve_targets(
            bk_tenant_id=bk_tenant_id,
            bk_data_id=validated_request_data.get("bk_data_id"),
            result_table_id=validated_request_data.get("result_table_id"),
            vm_result_table_id=validated_request_data.get("vm_result_table_id"),
            component_name=validated_request_data.get("component_name"),
        )
        if not targets:
            return []

        # Step 2: 批量预取上下文
        ctx = self._prefetch_context(bk_tenant_id, targets)

        # Step 3: 遍历组装扁平行
        rows: list[dict[str, Any]] = []
        for data_id, table_id in targets:
            try:
                rows.append(self._build_row(bk_tenant_id, data_id, table_id, ctx))
            except Exception as e:  # pylint: disable=broad-except
                logger.warning(
                    "QueryDataLinkMetadataResource: failed to build row (data_id=%s, table_id=%s): %s",
                    data_id,
                    table_id,
                    e,
                )
                rows.append(
                    {
                        "data_id": data_id,
                        "result_table_id": table_id,
                        "error": f"Failed to build row: {e}",
                    }
                )

        # Step 4: 并发拉取 runtime 字段 (BKBase V4 API + ES live + 组件 status)
        try:
            self._enrich_with_runtime(rows, ctx)
        except Exception as e:  # pylint: disable=broad-except
            logger.warning("QueryDataLinkMetadataResource: runtime enrich failed (non-fatal): %s", e)

        # Step 5: 清理行内的临时引用 (_instance / _databus_link_name 等), 避免序列化问题
        for row in rows:
            row.pop("_databus_link_name", None)
            comps = row.get("bkbase_components")
            if isinstance(comps, list):
                for comp in comps:
                    if isinstance(comp, dict):
                        comp.pop("_instance", None)
        return rows

    # ============================================================
    # Step 1: 入参解析
    # ============================================================

    def _resolve_targets(
        self,
        bk_tenant_id: str,
        bk_data_id: str | None,
        result_table_id: str | None,
        vm_result_table_id: str | None,
        component_name: str | None,
    ) -> list[tuple[int, str]]:
        """优先级 bk_data_id > result_table_id > vm_result_table_id > component_name."""
        if bk_data_id:
            return self._resolve_by_data_id(bk_tenant_id, bk_data_id)
        if result_table_id:
            return self._resolve_by_table_id(bk_tenant_id, result_table_id)
        if vm_result_table_id:
            return self._resolve_by_vm_rt_id(bk_tenant_id, vm_result_table_id)
        if component_name:
            return self._resolve_by_component_name(bk_tenant_id, component_name)
        return []

    def _resolve_by_data_id(self, bk_tenant_id: str, bk_data_id: str) -> list[tuple[int, str]]:
        try:
            data_id_int = int(bk_data_id)
        except (TypeError, ValueError):
            return []
        if not models.DataSource.objects.filter(bk_tenant_id=bk_tenant_id, bk_data_id=data_id_int).exists():
            return []
        table_ids = list(
            models.DataSourceResultTable.objects.filter(bk_tenant_id=bk_tenant_id, bk_data_id=data_id_int).values_list(
                "table_id", flat=True
            )
        )
        return [(data_id_int, t) for t in table_ids]

    def _resolve_by_table_id(self, bk_tenant_id: str, table_id: str) -> list[tuple[int, str]]:
        dsrt = models.DataSourceResultTable.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id).first()
        if not dsrt:
            return []
        return [(int(dsrt.bk_data_id), table_id)]

    def _resolve_by_vm_rt_id(self, bk_tenant_id: str, vm_rt_id: str) -> list[tuple[int, str]]:
        vm_rec = models.AccessVMRecord.objects.filter(bk_tenant_id=bk_tenant_id, vm_result_table_id=vm_rt_id).first()
        if not vm_rec:
            return []
        return self._resolve_by_table_id(bk_tenant_id, vm_rec.result_table_id)

    def _resolve_by_component_name(self, bk_tenant_id: str, component_name: str) -> list[tuple[int, str]]:
        """V4 BKBase 资源名反查 (DataLink-first + 7 ``*Config`` fallback).

        格式 ``{namespace}-{name}``:
            - ``bklog-bklog_301_xxx``   → ns=bklog, name=bklog_301_xxx
            - ``bkmonitor-bkm_xxx``     → ns=bkmonitor, name=bkm_xxx
            - 无 ns 前缀                  → 跨 {bkmonitor, bklog} 都试

        流程:
            Step 1: ``DataLink.objects.filter(namespace=ns, data_link_name=name)`` 直查命中
            Step 2: fallback 扫 7 个 ``*Config`` (按 ``name=name``), 命中拿 ``data_link_name`` 回 Step 1
            Step 3: 展开 ``link.table_ids[]`` 为 ``(bk_data_id, table_id)`` 列表
        """
        if "-" in component_name:
            prefix, _, suffix = component_name.partition("-")
            if prefix in ("bkmonitor", "bklog"):
                namespaces, name = [prefix], suffix
            else:
                namespaces, name = ["bkmonitor", "bklog"], component_name
        else:
            namespaces, name = ["bkmonitor", "bklog"], component_name

        if not name:
            return []

        config_models = (
            models.DataIdConfig,
            models.ResultTableConfig,
            models.VMStorageBindingConfig,
            models.ESStorageBindingConfig,
            models.DorisStorageBindingConfig,
            models.DataBusConfig,
            models.ConditionalSinkConfig,
        )

        for ns in namespaces:
            link = models.DataLink.objects.filter(bk_tenant_id=bk_tenant_id, namespace=ns, data_link_name=name).first()

            if not link:
                for cfg_cls in config_models:
                    try:
                        cfg = cfg_cls.objects.filter(bk_tenant_id=bk_tenant_id, namespace=ns, name=name).first()
                    except Exception as e:  # pylint: disable=broad-except
                        logger.warning("scan %s for component_name failed: %s", cfg_cls.__name__, e)
                        continue
                    if cfg and getattr(cfg, "data_link_name", None):
                        link = models.DataLink.objects.filter(
                            bk_tenant_id=bk_tenant_id, namespace=ns, data_link_name=cfg.data_link_name
                        ).first()
                        if link:
                            break

            if link:
                try:
                    data_id = int(link.bk_data_id)
                except (TypeError, ValueError):
                    data_id = link.bk_data_id
                return [(data_id, tid) for tid in (link.table_ids or [])]

        return []

    # ============================================================
    # Step 2: 批量预取
    # ============================================================

    def _prefetch_context(self, bk_tenant_id: str, targets: list[tuple[int, str]]) -> dict[str, Any]:
        """批量预取所有依赖对象到 dict, 避免逐行 N+1 查询."""
        data_ids = list({d for d, _ in targets})
        table_ids = list({t for _, t in targets})

        # ---- DataSource ----
        data_sources = {
            ds.bk_data_id: ds
            for ds in models.DataSource.objects.filter(bk_tenant_id=bk_tenant_id, bk_data_id__in=data_ids)
        }

        # ---- ResultTable ----
        result_tables = {
            rt.table_id: rt
            for rt in models.ResultTable.objects.filter(bk_tenant_id=bk_tenant_id, table_id__in=table_ids)
        }

        # ---- KafkaTopicInfo (DataSource.mq_config_id → KafkaTopicInfo.id) ----
        mq_config_ids = [ds.mq_config_id for ds in data_sources.values() if ds.mq_config_id]
        kafka_topics = (
            {kt.id: kt for kt in models.KafkaTopicInfo.objects.filter(id__in=mq_config_ids)} if mq_config_ids else {}
        )

        # ---- 各 Storage 模型 (按 table_id 索引) ----
        es_storages = {
            s.table_id: s for s in models.ESStorage.objects.filter(bk_tenant_id=bk_tenant_id, table_id__in=table_ids)
        }
        doris_storages = {
            s.table_id: s for s in models.DorisStorage.objects.filter(bk_tenant_id=bk_tenant_id, table_id__in=table_ids)
        }
        kafka_storages = {
            s.table_id: s for s in models.KafkaStorage.objects.filter(bk_tenant_id=bk_tenant_id, table_id__in=table_ids)
        }

        # ---- AccessVMRecord (一 RT 多条, 按 table_id group) ----
        vm_records: dict[str, list[Any]] = {}
        for vm in models.AccessVMRecord.objects.filter(bk_tenant_id=bk_tenant_id, result_table_id__in=table_ids):
            vm_records.setdefault(vm.result_table_id, []).append(vm)

        # ---- V4 链路 ----
        bkbase_rts = {
            br.monitor_table_id: br
            for br in models.BkBaseResultTable.objects.filter(bk_tenant_id=bk_tenant_id, monitor_table_id__in=table_ids)
        }
        data_link_names = list({br.data_link_name for br in bkbase_rts.values() if br.data_link_name})
        data_links = (
            {
                dl.data_link_name: dl
                for dl in models.DataLink.objects.filter(bk_tenant_id=bk_tenant_id, data_link_name__in=data_link_names)
            }
            if data_link_names
            else {}
        )
        databus_configs = (
            {
                dc.data_link_name: dc
                for dc in models.DataBusConfig.objects.filter(
                    bk_tenant_id=bk_tenant_id, data_link_name__in=data_link_names
                )
            }
            if data_link_names
            else {}
        )

        # 组件清单: 扫 7 个 *Config, 按 data_link_name group
        components_by_link: dict[str, list[dict[str, Any]]] = {}
        if data_link_names:
            v4_config_models = (
                (models.DataIdConfig, "DataId"),
                (models.ResultTableConfig, "ResultTable"),
                (models.VMStorageBindingConfig, "VmStorageBinding"),
                (models.ESStorageBindingConfig, "ElasticSearchBinding"),
                (models.DorisStorageBindingConfig, "DorisBinding"),
                (models.DataBusConfig, "Databus"),
                (models.ConditionalSinkConfig, "ConditionalSink"),
            )
            for cfg_cls, kind in v4_config_models:
                try:
                    qs = cfg_cls.objects.filter(bk_tenant_id=bk_tenant_id, data_link_name__in=data_link_names)
                    for cfg in qs:
                        components_by_link.setdefault(cfg.data_link_name, []).append(
                            {
                                "kind": kind,
                                "name": getattr(cfg, "name", None),
                                "namespace": getattr(cfg, "namespace", None),
                                "data_link_name": cfg.data_link_name,
                                "status": None,  # P2 runtime fetch
                                "message": None,  # P2 runtime fetch
                                "status_error": None,  # P2 runtime fetch
                                # P2 内部使用: 保存 *Config 实例, 用于 component_status 拉取;
                                # 行返回前会 pop 掉, 不出现在响应中
                                "_instance": cfg,
                            }
                        )
                except Exception as e:  # pylint: disable=broad-except
                    logger.warning("prefetch components for %s failed: %s", cfg_cls.__name__, e)

        # ---- ClusterInfo 全量预取 (按 cluster_id 索引) ----
        cluster_ids: set[int] = set()
        for ds in data_sources.values():
            if ds.mq_cluster_id:
                cluster_ids.add(ds.mq_cluster_id)
        for s in list(es_storages.values()) + list(doris_storages.values()) + list(kafka_storages.values()):
            if s.storage_cluster_id:
                cluster_ids.add(s.storage_cluster_id)
        for vms in vm_records.values():
            for vm in vms:
                if vm.vm_cluster_id:
                    cluster_ids.add(vm.vm_cluster_id)
                if vm.storage_cluster_id:
                    cluster_ids.add(vm.storage_cluster_id)
        clusters = (
            {
                c.cluster_id: c
                for c in models.ClusterInfo.objects.filter(bk_tenant_id=bk_tenant_id, cluster_id__in=list(cluster_ids))
            }
            if cluster_ids
            else {}
        )

        # ---- Space (按 bk_biz_id, 业务正负值处理) ----
        # 兜底后的 bk_biz_id 才能准确查 Space, 这里不预取, 在 build_row 时按需查
        # 但常用业务可一次性扫到, lazy 即可

        # ---- BCSClusterInfo: 反查 (path 3) ----
        bcs_cluster_by_data_id: dict[int, str] = {}
        if data_ids:
            q = Q()
            for field in self._BCS_CLUSTER_DATAID_FIELDS:
                q |= Q(**{f"{field}__in": data_ids})
            try:
                for bci in models.BCSClusterInfo.objects.filter(bk_tenant_id=bk_tenant_id).filter(q):
                    for field in self._BCS_CLUSTER_DATAID_FIELDS:
                        did = getattr(bci, field, None)
                        if did and did in data_ids:
                            bcs_cluster_by_data_id[did] = bci.cluster_id
            except Exception as e:  # pylint: disable=broad-except
                logger.warning("prefetch BCSClusterInfo failed: %s", e)

        # ---- BcsFederalClusterInfo: 联邦集群信息 (P3) ----
        # 关心两类匹配:
        #   - fed_builtin_metric_table_id / fed_builtin_event_table_id ∈ table_ids
        #   - sub_cluster_id ∈ 当前行可能的 bcs_cluster_id (通过 data_name 解析得到)
        candidate_sub_clusters: set[str] = set()
        for ds in data_sources.values():
            m = self.BCS_CLUSTER_PATTERN.search(ds.data_name or "")
            if m:
                candidate_sub_clusters.add(f"BCS-K8S-{m.group(1)}")
        # AccessVMRecord.bcs_cluster_id 也加进去
        for vms in vm_records.values():
            for vm in vms:
                bid = getattr(vm, "bcs_cluster_id", None)
                if bid:
                    candidate_sub_clusters.add(bid)

        fed_by_table_id: dict[str, Any] = {}
        fed_by_sub_cluster_id: dict[str, Any] = {}
        if table_ids or candidate_sub_clusters:
            try:
                fed_q = Q(is_deleted=False)
                fed_or = Q()
                if table_ids:
                    fed_or |= Q(fed_builtin_metric_table_id__in=table_ids)
                    fed_or |= Q(fed_builtin_event_table_id__in=table_ids)
                if candidate_sub_clusters:
                    fed_or |= Q(sub_cluster_id__in=list(candidate_sub_clusters))
                qs = models.BcsFederalClusterInfo.objects.filter(fed_q & fed_or)
                for fed in qs:
                    if fed.fed_builtin_metric_table_id:
                        fed_by_table_id[fed.fed_builtin_metric_table_id] = fed
                    if fed.fed_builtin_event_table_id:
                        fed_by_table_id[fed.fed_builtin_event_table_id] = fed
                    if fed.sub_cluster_id:
                        fed_by_sub_cluster_id[fed.sub_cluster_id] = fed
            except Exception as e:  # pylint: disable=broad-except
                logger.warning("prefetch BcsFederalClusterInfo failed: %s", e)

        return {
            "data_sources": data_sources,
            "result_tables": result_tables,
            "kafka_topics": kafka_topics,
            "es_storages": es_storages,
            "doris_storages": doris_storages,
            "kafka_storages": kafka_storages,
            "vm_records": vm_records,
            "bkbase_rts": bkbase_rts,
            "data_links": data_links,
            "databus_configs": databus_configs,
            "components_by_link": components_by_link,
            "clusters": clusters,
            "bcs_cluster_by_data_id": bcs_cluster_by_data_id,
            "fed_by_table_id": fed_by_table_id,
            "fed_by_sub_cluster_id": fed_by_sub_cluster_id,
        }

    # ============================================================
    # Step 3: 组装单行
    # ============================================================

    def _build_row(
        self,
        bk_tenant_id: str,
        data_id: int,
        table_id: str,
        ctx: dict[str, Any],
    ) -> dict[str, Any]:
        ds = ctx["data_sources"].get(data_id)
        rt = ctx["result_tables"].get(table_id)
        if not ds or not rt:
            return {
                "data_id": data_id,
                "result_table_id": table_id,
                "error": "DataSource or ResultTable missing",
            }

        row: dict[str, Any] = {}
        row.update(self._build_identity_block(ds, rt, ctx))
        row.update(self._build_biz_space_block(bk_tenant_id, data_id, rt, ctx))
        row.update(self._build_kafka_frontend_block(ds, ctx))
        row.update(self._build_transfer_block(ds))
        row.update(self._build_kafka_backend_block(table_id, ctx))
        row.update(self._build_shipper_runtime_block())  # P2: 全 null 占位
        row.update(self._build_v4_databus_block(table_id, ds, ctx))
        row.update(self._build_vm_block(table_id, ctx))
        row.update(self._build_es_block(table_id, ctx))
        row.update(self._build_doris_block(table_id, ctx))
        row.update(self._build_bcs_block(data_id, ds, rt, ctx))
        row.update(self._build_placeholder_block())  # collect_config_id / 拓扑字段
        row.update(self._build_runtime_error_fields())  # bkbase_remote_error / es_runtime_error

        # 派生字段: bk_base_data_id + effective_storage
        row["bk_base_data_id"] = self._resolve_bk_base_data_id(table_id, data_id, ds, ctx)
        row["effective_storage"] = self._derive_effective_storage(row["default_storage"], table_id, ctx)
        return row

    # ============================================================
    # Block builders
    # ============================================================

    def _build_identity_block(self, ds: Any, rt: Any, ctx: dict[str, Any]) -> dict[str, Any]:
        is_v4 = ds.created_from == DataIdCreatedFromSystem.BKDATA.value
        data_link_strategy = None
        bkbase_namespace = None
        has_conditional_sink = False
        if is_v4:
            br = ctx["bkbase_rts"].get(rt.table_id)
            if br and br.data_link_name:
                dl = ctx["data_links"].get(br.data_link_name)
                if dl:
                    data_link_strategy = getattr(dl, "data_link_strategy", None) or None
                    bkbase_namespace = getattr(dl, "namespace", None) or None
                comps = ctx["components_by_link"].get(br.data_link_name, [])
                has_conditional_sink = any(c.get("kind") == "ConditionalSink" for c in comps)

        return {
            "id": rt.id,
            "bk_tenant_id": ds.bk_tenant_id,
            "data_id": ds.bk_data_id,
            "data_name": ds.data_name,
            "result_table_id": rt.table_id,
            "result_table_name": rt.table_id.rsplit(".", 1)[-1] if "." in rt.table_id else rt.table_id,
            "result_table_name_zh": getattr(rt, "table_name_zh", None) or None,
            "datalink_version": "v4" if is_v4 else "v3",
            "etl_config": ds.etl_config,
            "source_system": ds.source_system,
            "data_link_strategy": data_link_strategy,
            "bkbase_namespace": bkbase_namespace,
            "has_conditional_sink": has_conditional_sink,
            "default_storage": rt.default_storage,
            "is_data_id_enabled": ds.is_enable,
            "is_result_table_enabled": rt.is_enable,
            "is_platform_data_id": ds.is_platform_data_id,
            "data_label": rt.data_label,
            "created_at": self._format_dt(rt.create_time),
            "updated_at": self._format_dt(rt.last_modify_time),
            "data_source_created_at": self._format_dt(ds.create_time),
            "creator": ds.creator or None,
        }

    def _build_biz_space_block(
        self,
        bk_tenant_id: str,
        data_id: int,
        rt: Any,
        ctx: dict[str, Any],
    ) -> dict[str, Any]:
        # 真实有效 bk_biz_id (四路兜底): rt.bk_biz_id==0 时回填
        bk_biz_id = rt.bk_biz_id
        if bk_biz_id == 0:
            resolved = self._resolve_real_bk_biz_id(bk_tenant_id, data_id)
            if resolved is not None:
                bk_biz_id = resolved

        # Space 信息 (lazy 查, 不预取)
        bk_biz_name = None
        space_uid = "global"
        try:
            if bk_biz_id > 0:
                space = models.Space.objects.get(
                    bk_tenant_id=bk_tenant_id,
                    space_type_id=SpaceTypes.BKCC.value,
                    space_id=bk_biz_id,
                )
                bk_biz_name = space.space_name
                space_uid = f"{space.space_type_id}__{space.space_id}"
            elif bk_biz_id < 0:
                space = models.Space.objects.get(bk_tenant_id=bk_tenant_id, id=abs(bk_biz_id))
                bk_biz_name = space.space_name
                space_uid = f"{space.space_type_id}__{space.space_id}"
        except models.Space.DoesNotExist:
            pass
        except Exception as e:  # pylint: disable=broad-except
            logger.warning("get Space failed for bk_biz_id=%s: %s", bk_biz_id, e)

        return {
            "bk_biz_id": bk_biz_id,
            "bk_biz_name": bk_biz_name,
            "space_uid": space_uid,
        }

    def _build_kafka_frontend_block(self, ds: Any, ctx: dict[str, Any]) -> dict[str, Any]:
        out = {
            "kafka_instance_id": None,
            "kafka_inner_cluster_name": None,
            "kafka_app": None,  # BKBase 职责, 恒 null
            "kafka_host": None,
            "topic_name": None,
            "current_partition_num": None,
        }
        cluster = ctx["clusters"].get(ds.mq_cluster_id) if ds.mq_cluster_id else None
        if cluster:
            out["kafka_instance_id"] = cluster.cluster_id
            out["kafka_inner_cluster_name"] = cluster.cluster_name
            out["kafka_host"] = cluster.domain_name
        kt = ctx["kafka_topics"].get(ds.mq_config_id) if ds.mq_config_id else None
        if kt:
            out["topic_name"] = kt.topic
            out["current_partition_num"] = kt.partition
        return out

    def _build_transfer_block(self, ds: Any) -> dict[str, Any]:
        return {
            "transfer_cluster": ds.transfer_cluster_id or None,
            "transfer_cluster_pod_num": None,  # 占位 null
        }

    def _build_kafka_backend_block(self, table_id: str, ctx: dict[str, Any]) -> dict[str, Any]:
        out = {
            "backend_kafka_cluster_id": None,
            "backend_kafka_host": None,
            "backend_kafka_topic": None,
            "backend_kafka_partition": None,
        }
        ks = ctx["kafka_storages"].get(table_id)
        if not ks:
            return out
        cluster = ctx["clusters"].get(ks.storage_cluster_id) if ks.storage_cluster_id else None
        out.update(
            {
                "backend_kafka_cluster_id": ks.storage_cluster_id,
                "backend_kafka_host": cluster.domain_name if cluster else None,
                "backend_kafka_topic": ks.topic,
                "backend_kafka_partition": ks.partition,
            }
        )
        return out

    def _build_shipper_runtime_block(self) -> dict[str, Any]:
        """V3 内部 Kafka shipper, 5 个字段都是 P2 runtime, P1 全 null."""
        return {
            "shipper_kafka_instance_id": None,
            "kafka_shipper_cluster_name": None,
            "kafka_shipper_host": None,
            "kafka_shipper_topic_name": None,
            "kafka_shipper_topic_partition_num": None,
        }

    def _build_v4_databus_block(self, table_id: str, ds: Any, ctx: dict[str, Any]) -> dict[str, Any]:
        """V4 Databus 块: 17 字段; P1 本地, P2 补 runtime."""
        out = {
            "databus_name": None,
            "databus_v4_cluster_name": None,
            "databus_v4_subtask_name": None,  # P2
            "databus_v4_kafka_instance_id": None,  # P2
            "databus_kafka_host": None,  # P2
            "databus_topic_name": None,  # P2
            "databus_topic_partition_num": None,  # P2
            "databus_vm_cluster_domain": None,  # P2
            "dispatch_cluster": None,  # P2
            "dispatch_cluster_count": None,  # P2
            "dispatch_cluster_task_name": None,  # P2
            "dispatch_task_count": None,  # P2
            "bkbase_status": None,
            "bkbase_table_id": None,
            "bkbase_rt_name": None,
            "bkbase_components": None,
        }
        if ds.created_from != DataIdCreatedFromSystem.BKDATA.value:
            return out
        br = ctx["bkbase_rts"].get(table_id)
        if not br:
            # V3→V4 迁移场景, 本地无 BkBaseResultTable; P2 通过远端 API 拼装
            return out

        out["bkbase_status"] = br.status or None
        out["bkbase_table_id"] = br.bkbase_table_id or None
        out["bkbase_rt_name"] = br.bkbase_rt_name or None

        dc = ctx["databus_configs"].get(br.data_link_name) if br.data_link_name else None
        if dc:
            out["databus_name"] = dc.name or None
            # ``databus_v4_cluster_name`` 来自 ``DataBusConfig.component_config.spec.preferCluster.name``,
            # ``component_config`` 是 @property 触发远端调用, 在 P2 ``_enrich_with_runtime`` 中并发拉取.
            # 暂存 link_name 到行内 (传递给 runtime 阶段), 输出前会 pop 掉.
            out["_databus_link_name"] = br.data_link_name

        comps = ctx["components_by_link"].get(br.data_link_name, [])
        out["bkbase_components"] = comps or None
        return out

    def _build_vm_block(self, table_id: str, ctx: dict[str, Any]) -> dict[str, Any]:
        out = {
            "vm_rt_name": None,
            "vm_cluster_id": None,
            "vm_cluster_domain": None,
            "vm_cluster_name": None,
            "vm_storage_cluster_id": None,
            "vm_records_count": 0,
        }
        vms = ctx["vm_records"].get(table_id, [])
        if not vms:
            return out

        out["vm_records_count"] = len(vms)

        # 主接入: 取 latest by create_time (兜底取第一条)
        def _ct(v):
            return getattr(v, "create_time", None) or datetime.min.replace(tzinfo=timezone.utc)

        primary = sorted(vms, key=_ct, reverse=True)[0]
        cluster = ctx["clusters"].get(primary.vm_cluster_id) if primary.vm_cluster_id else None
        out.update(
            {
                "vm_rt_name": primary.vm_result_table_id or None,
                "vm_cluster_id": primary.vm_cluster_id,
                "vm_cluster_domain": cluster.domain_name if cluster else None,
                "vm_cluster_name": cluster.cluster_name if cluster else None,
                "vm_storage_cluster_id": primary.storage_cluster_id,
            }
        )
        return out

    def _build_es_block(self, table_id: str, ctx: dict[str, Any]) -> dict[str, Any]:
        out = {
            "es_cluster_id": None,
            "es_cluster_domain": None,
            "es_cluster_name": None,
            "es_app": None,  # BKBase 职责
            "es_index_name": None,
            "es_index_shard_num": None,
            "es_retention_days": None,
            "es_slice_size_gb": None,
            "es_slice_gap_minutes": None,
            "es_time_zone": None,
            "es_index_settings": None,
            "es_mapping_settings": None,
            "es_current_index_name": None,  # P2
            "es_current_index_info": None,  # P2
            "es_should_rotate_index": None,  # P2
        }
        es = ctx["es_storages"].get(table_id)
        if not es:
            return out
        cluster = ctx["clusters"].get(es.storage_cluster_id) if es.storage_cluster_id else None
        out.update(
            {
                "es_cluster_id": es.storage_cluster_id,
                "es_cluster_domain": cluster.domain_name if cluster else None,
                "es_cluster_name": cluster.cluster_name if cluster else None,
                "es_index_name": es.index_set or None,
                "es_index_shard_num": self._parse_index_shard_num(es.index_settings),
                "es_retention_days": es.retention,
                "es_slice_size_gb": es.slice_size,
                "es_slice_gap_minutes": es.slice_gap,
                "es_time_zone": es.time_zone,
            }
        )
        out["es_index_settings"] = self._safe_json_loads(es.index_settings)
        out["es_mapping_settings"] = self._safe_json_loads(es.mapping_settings)
        return out

    def _build_doris_block(self, table_id: str, ctx: dict[str, Any]) -> dict[str, Any]:
        out = {
            "doris_cluster_id": None,
            "doris_cluster_domain": None,
            "doris_cluster_name": None,
            "doris_app": None,  # BKBase 职责
            "doris_table_name": None,
            "doris_table_type": None,
            "doris_expire_days": None,
            "doris_bucket_size": None,  # P2: 主源 BKBase API
        }
        doris = ctx["doris_storages"].get(table_id)
        if not doris:
            return out
        cluster = ctx["clusters"].get(doris.storage_cluster_id) if doris.storage_cluster_id else None
        out.update(
            {
                "doris_cluster_id": doris.storage_cluster_id,
                "doris_cluster_domain": cluster.domain_name if cluster else None,
                "doris_cluster_name": cluster.cluster_name if cluster else None,
                "doris_table_name": getattr(doris, "bkbase_table_id", None) or None,
                "doris_table_type": getattr(doris, "table_type", None) or None,
                "doris_expire_days": getattr(doris, "expire_days", None),
            }
        )
        return out

    def _build_bcs_block(self, data_id: int, ds: Any, rt: Any, ctx: dict[str, Any]) -> dict[str, Any]:
        cluster_id, source = self._resolve_bcs_cluster_id(data_id, ds, rt, ctx)

        # 拿当前行的 data_link_strategy (仅 V4 链路才有), 用于联邦判定
        data_link_strategy = None
        br = ctx["bkbase_rts"].get(rt.table_id) if ds.created_from == DataIdCreatedFromSystem.BKDATA.value else None
        if br and br.data_link_name:
            dl = ctx["data_links"].get(br.data_link_name)
            if dl:
                data_link_strategy = getattr(dl, "data_link_strategy", None) or None

        federal_info = self._build_bcs_federal_info(rt, data_link_strategy, cluster_id, ctx)
        return {
            "bcs_cluster_id": cluster_id,
            "bcs_cluster_id_source": source,
            "bcs_federal_info": federal_info,
        }

    def _build_bcs_federal_info(
        self,
        rt: Any,
        data_link_strategy: str | None,
        bcs_cluster_id: str | None,
        ctx: dict[str, Any],
    ) -> dict[str, Any] | None:
        """填充 ``bcs_federal_info`` (仅联邦相关 RT 才填).

        命中条件 (任一):
            (a) ``data_link_strategy ∈ BCS_FEDERAL_STRATEGIES``
            (b) ``table_id`` 命中 ``BcsFederalClusterInfo.fed_builtin_metric_table_id`` 或 ``fed_builtin_event_table_id``

        匹配优先级:
            1. 按 ``table_id`` 查 (fed_builtin 路径, 命中即返)
            2. 否则按 ``bcs_cluster_id`` 查 (sub_cluster_id 路径), 仅当策略匹配联邦
        """
        fed_by_table = ctx.get("fed_by_table_id", {})
        fed_by_sub = ctx.get("fed_by_sub_cluster_id", {})

        matched = fed_by_table.get(rt.table_id)
        if not matched and data_link_strategy in self._BCS_FEDERAL_STRATEGIES and bcs_cluster_id:
            matched = fed_by_sub.get(bcs_cluster_id)

        if not matched:
            return None
        return {
            "fed_cluster_id": getattr(matched, "fed_cluster_id", None),
            "host_cluster_id": getattr(matched, "host_cluster_id", None),
            "sub_cluster_id": getattr(matched, "sub_cluster_id", None),
            "fed_namespaces": list(getattr(matched, "fed_namespaces", None) or []),
            "fed_builtin_metric_table_id": getattr(matched, "fed_builtin_metric_table_id", None) or None,
            "fed_builtin_event_table_id": getattr(matched, "fed_builtin_event_table_id", None) or None,
        }

    def _build_placeholder_block(self) -> dict[str, Any]:
        """占位字段, 恒 null."""
        return {
            "kafka_broker_num": None,
            "es_node_num": None,
            "doris_node_num": None,
            "collect_config_id": None,  # P4 待 bklog 反查
        }

    def _build_runtime_error_fields(self) -> dict[str, Any]:
        """P2 运行时错误字段, P1 全 null."""
        return {
            "bkbase_remote_error": None,
            "es_runtime_error": None,
        }

    # ============================================================
    # 派生字段
    # ============================================================

    def _resolve_bk_base_data_id(self, table_id: str, data_id: int, ds: Any, ctx: dict[str, Any]) -> int | None:
        """AccessVMRecord.bk_base_data_id 优先; V4 原生 fallback bk_data_id."""
        vms = ctx["vm_records"].get(table_id, [])
        for vm in vms:
            if vm.bk_base_data_id:
                return vm.bk_base_data_id
        if ds.created_from == DataIdCreatedFromSystem.BKDATA.value:
            return data_id
        return None

    def _derive_effective_storage(self, default_storage: str | None, table_id: str, ctx: dict[str, Any]) -> str | None:
        """``InfluxDB`` 历史遗留: 如有 ``AccessVMRecord``, 视为 VM."""
        if default_storage == models.ClusterInfo.TYPE_INFLUXDB:
            if ctx["vm_records"].get(table_id):
                return models.ClusterInfo.TYPE_VM
        return default_storage

    def _resolve_real_bk_biz_id(self, bk_tenant_id: str, data_id: int) -> int | None:
        """``ResultTable.bk_biz_id==0`` 时按 TimeSeriesGroup → EventGroup → LogGroup → SpaceDataSource(bkcc) 顺序回填."""
        for group_model in (models.TimeSeriesGroup, models.EventGroup, models.LogGroup):
            try:
                group = group_model.objects.filter(bk_tenant_id=bk_tenant_id, bk_data_id=data_id).first()
                if group and group.bk_biz_id != 0:
                    return group.bk_biz_id
            except Exception as e:  # pylint: disable=broad-except
                logger.warning(
                    "resolve bk_biz_id from %s failed for data_id %s: %s",
                    group_model.__name__,
                    data_id,
                    e,
                )

        try:
            space_ds = models.SpaceDataSource.objects.filter(
                bk_tenant_id=bk_tenant_id, bk_data_id=data_id, from_authorization=False
            ).first()
            if space_ds and space_ds.space_type_id == SpaceTypes.BKCC.value:
                return int(space_ds.space_id)
        except Exception as e:  # pylint: disable=broad-except
            logger.warning("resolve bk_biz_id from SpaceDataSource failed: %s", e)
        return None

    def _resolve_bcs_cluster_id(
        self, data_id: int, ds: Any, rt: Any, ctx: dict[str, Any]
    ) -> tuple[str | None, str | None]:
        """三路兜底: name_parse → AccessVMRecord → BCSClusterInfo. 返回 (cluster_id, source)."""
        # Path 1: name_parse on data_name (兼容 V3 / V4 命名)
        m = self.BCS_CLUSTER_PATTERN.search(ds.data_name or "")
        if m:
            return f"BCS-K8S-{m.group(1)}", "name_parse"

        # Path 2: AccessVMRecord.bcs_cluster_id
        vms = ctx["vm_records"].get(rt.table_id, [])
        for vm in vms:
            bid = getattr(vm, "bcs_cluster_id", None)
            if bid:
                return bid, "access_vm_record"

        # Path 3: BCSClusterInfo 反查
        cid = ctx["bcs_cluster_by_data_id"].get(data_id)
        if cid:
            return cid, "bcs_cluster_info"
        return None, None

    # ============================================================
    # 辅助
    # ============================================================

    @staticmethod
    def _format_dt(dt: datetime | None) -> str | None:
        if not dt:
            return None
        try:
            return dt.isoformat()
        except Exception:  # pylint: disable=broad-except
            return None

    @staticmethod
    def _safe_json_loads(text: Any) -> Any:
        if not text:
            return None
        if not isinstance(text, str):
            return text
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError, ValueError):
            return None

    @classmethod
    def _parse_index_shard_num(cls, index_settings: Any) -> int | None:
        """从 ESStorage.index_settings (JSON 字符串) 提取 ``number_of_shards``."""
        parsed = cls._safe_json_loads(index_settings)
        if not isinstance(parsed, dict):
            return None
        n = parsed.get("number_of_shards")
        if n is None:
            return None
        try:
            return int(n)
        except (ValueError, TypeError):
            return None

    # ============================================================
    # P2 Runtime: 并发拉取 BKBase / ES / 组件 status
    # ============================================================

    def _enrich_with_runtime(self, rows: list[dict[str, Any]], ctx: dict[str, Any]) -> None:
        """对所有行并发执行 runtime 字段拉取.

        三类外部调用:
            - BKBase V4 元数据 API (拼装 ``branches[]`` → ``dispatch_* / kafka_shipper_* / databus_kafka_host`` 等)
            - DataBus ``component_config.spec.preferCluster.name`` (远端 @property)
            - ES live 索引信息 (``ESStorage.current_index_info / get_index_info / _should_create_index``)
            - 各 ``*Config.component_status`` (远端 @property)

        策略: 收集所有任务一次性提交线程池; 单调用超时 ``_RUNTIME_TIMEOUT_SEC``; 失败降级 ``null`` + 写 ``*_error``.
        """
        if not rows:
            return

        tasks: list[tuple[dict[str, Any], str, dict[str, Any]]] = []
        for row in rows:
            if row.get("error"):
                continue

            # BKBase 元数据 (V4 + V3→V4 迁移都可尝试; 仅在有 ID 时才发)
            if row.get("bk_base_data_id") or row.get("vm_rt_name"):
                tasks.append(
                    (
                        row,
                        "bkbase_metadata",
                        {
                            "bk_base_data_id": row.get("bk_base_data_id"),
                            "vm_rt_name": row.get("vm_rt_name"),
                        },
                    )
                )

            # ES live (任何有 ES 存储的行)
            if row.get("es_cluster_id"):
                tasks.append((row, "es_runtime", {"table_id": row.get("result_table_id")}))

            # DataBus preferCluster (仅 V4 链路)
            link_name = row.get("_databus_link_name")
            if link_name:
                tasks.append((row, "databus_prefer_cluster", {"data_link_name": link_name}))

            # 各组件 status (仅 V4 链路有 bkbase_components)
            comps = row.get("bkbase_components") or []
            for idx, comp in enumerate(comps):
                if isinstance(comp, dict) and comp.get("_instance") is not None:
                    tasks.append((row, "component_status", {"comp_idx": idx}))

        if not tasks:
            return

        with ThreadPoolExecutor(max_workers=self._MAX_RUNTIME_WORKERS) as ex:
            future_meta = {
                ex.submit(self._dispatch_runtime, kind, args, ctx, row): (row, kind, args) for row, kind, args in tasks
            }
            for fut in as_completed(future_meta):
                row, kind, args = future_meta[fut]
                try:
                    result = fut.result(timeout=self._RUNTIME_TIMEOUT_SEC + 1.0)
                except Exception as e:  # pylint: disable=broad-except
                    self._record_runtime_error(row, kind, args, f"task crashed: {e}")
                    continue
                try:
                    self._apply_runtime_result(row, kind, args, result, ctx)
                except Exception as e:  # pylint: disable=broad-except
                    logger.warning("apply runtime result failed (kind=%s): %s", kind, e)
                    self._record_runtime_error(row, kind, args, f"apply failed: {e}")

    def _dispatch_runtime(
        self,
        kind: str,
        args: dict[str, Any],
        ctx: dict[str, Any],
        row: dict[str, Any],
    ) -> Any:
        """线程池任务入口. 按 kind 分发到具体 fetcher; 单 fetch 失败返回 ``{"_error": ...}``."""
        try:
            if kind == "bkbase_metadata":
                return self._fetch_bkbase_metadata(args.get("bk_base_data_id"), args.get("vm_rt_name"))
            if kind == "databus_prefer_cluster":
                dc = ctx.get("databus_configs", {}).get(args["data_link_name"])
                return self._fetch_databus_prefer_cluster(dc)
            if kind == "es_runtime":
                es_storage = ctx.get("es_storages", {}).get(args["table_id"])
                return self._fetch_es_runtime(es_storage)
            if kind == "component_status":
                comp = (row.get("bkbase_components") or [])[args["comp_idx"]]
                return self._fetch_component_status(comp.get("_instance"))
            return None
        except Exception as e:  # pylint: disable=broad-except
            return {"_error": str(e)}
        finally:
            try:
                from django.db import close_old_connections

                close_old_connections()
            except Exception:  # pylint: disable=broad-except
                pass

    def _fetch_bkbase_metadata(self, bk_base_data_id: int | None, vm_rt_name: str | None) -> dict[str, Any] | None:
        """调 BKBase V4 元数据 API. 返回 dict 含 ``branches[]``; 失败返回 ``{"_error": ...}``."""
        if not (bk_base_data_id or vm_rt_name):
            return None
        params: dict[str, Any] = {}
        if bk_base_data_id:
            try:
                params["bk_data_id"] = int(bk_base_data_id)
            except (TypeError, ValueError):
                return {"_error": f"invalid bk_base_data_id: {bk_base_data_id}"}
        elif vm_rt_name:
            params["vm_result_table_id"] = vm_rt_name
        try:
            return api.bkdata.get_data_link_metadata(**params)
        except Exception as e:  # pylint: disable=broad-except
            logger.warning("fetch bkbase metadata failed, params=%s: %s", params, e)
            return {"_error": str(e)}

    def _fetch_databus_prefer_cluster(self, dc: Any) -> Any:
        """读 ``DataBusConfig.component_config.spec.preferCluster.name`` (远端调用)."""
        if not dc:
            return None
        try:
            cc = dc.component_config
        except Exception as e:  # pylint: disable=broad-except
            return {"_error": f"component_config fetch failed: {e}"}
        if not isinstance(cc, dict):
            return None
        spec = cc.get("spec") or {}
        pc = spec.get("preferCluster") or {}
        name = pc.get("name")
        return name if isinstance(name, str) and name else None

    def _fetch_es_runtime(self, es_storage: Any) -> dict[str, Any] | None:
        """ES live: ``current_index_info`` + ``get_index_info`` + ``_should_create_index``."""
        if not es_storage:
            return None
        out: dict[str, Any] = {}
        try:
            current = es_storage.current_index_info() or {}
            out["current_index_info_raw"] = current
            if current:
                try:
                    out["current_index_name"] = es_storage.make_index_name(
                        current.get("datetime_object"),
                        current.get("index"),
                        current.get("index_version"),
                    )
                except Exception as e:  # pylint: disable=broad-except
                    logger.warning("make_index_name failed: %s", e)
                if out.get("current_index_name"):
                    try:
                        out["current_index_detail"] = es_storage.get_index_info(out["current_index_name"])
                    except Exception as e:  # pylint: disable=broad-except
                        logger.warning("get_index_info failed: %s", e)
        except Exception as e:  # pylint: disable=broad-except
            return {"_error": f"current_index_info failed: {e}"}

        try:
            out["should_rotate"] = bool(es_storage._should_create_index())  # noqa: SLF001
        except Exception as e:  # pylint: disable=broad-except
            logger.warning("_should_create_index failed: %s", e)
            out["should_rotate"] = None
        return out

    def _fetch_component_status(self, cfg_instance: Any) -> Any:
        """读 ``*Config.component_status`` (远端 BKBase API)."""
        if cfg_instance is None:
            return None
        try:
            status_data = cfg_instance.component_status
        except Exception as e:  # pylint: disable=broad-except
            return {"_error": str(e)}
        if isinstance(status_data, dict):
            return (
                status_data.get("phase") or status_data.get("status"),
                status_data.get("message"),
            )
        if isinstance(status_data, str):
            return status_data, None
        return None, None

    def _apply_runtime_result(
        self,
        row: dict[str, Any],
        kind: str,
        args: dict[str, Any],
        result: Any,
        ctx: dict[str, Any],
    ) -> None:
        """把 fetch 结果 merge 到 row."""
        if isinstance(result, dict) and "_error" in result:
            self._record_runtime_error(row, kind, args, result["_error"])
            return

        if kind == "bkbase_metadata":
            self._apply_bkbase_metadata(row, result)
        elif kind == "databus_prefer_cluster":
            if isinstance(result, str):
                row["databus_v4_cluster_name"] = result
        elif kind == "es_runtime":
            self._apply_es_runtime(row, result)
        elif kind == "component_status":
            comp = (row.get("bkbase_components") or [])[args["comp_idx"]]
            status, message = result if isinstance(result, tuple) and len(result) == 2 else (None, None)
            comp["status"] = status
            comp["message"] = message

    def _apply_bkbase_metadata(self, row: dict[str, Any], result: Any) -> None:
        """从 BKBase V4 API 响应 (``branches[]``) 抽取字段写入 row."""
        if not isinstance(result, dict):
            return
        branches = result.get("branches") or []
        if not branches or not isinstance(branches[0], dict):
            return
        b = branches[0]

        # V4 Databus runtime
        mapping = {
            "dispatch_cluster": "dispatch_cluster",
            "dispatch_cluster_count": "dispatch_cluster_count",
            "dispatch_task_count": "dispatch_task_count",
            "kafka_shipper_cluster_name": "kafka_shipper_cluster_name",
            "kafka_shipper_host": "kafka_shipper_host",
            "kafka_shipper_topic_name": "kafka_shipper_topic_name",
            "kafka_shipper_topic_partition_num": "kafka_shipper_topic_partition_num",
        }
        for branch_key, row_key in mapping.items():
            val = b.get(branch_key)
            if val is not None:
                row[row_key] = val

        # 双写: dispatch_cluster_task_name → databus_v4_subtask_name
        task_name = b.get("dispatch_cluster_task_name")
        if task_name is not None:
            row["dispatch_cluster_task_name"] = task_name
            row["databus_v4_subtask_name"] = task_name

        # branches 命名转换
        if b.get("kafka_host") is not None:
            row["databus_kafka_host"] = b.get("kafka_host")
        if b.get("kafka_topic_name") is not None:
            row["databus_topic_name"] = b.get("kafka_topic_name")
        if b.get("kafka_topic_partition_num") is not None:
            row["databus_topic_partition_num"] = b.get("kafka_topic_partition_num")
        if b.get("vm_cluster_domain") is not None:
            row["databus_vm_cluster_domain"] = b.get("vm_cluster_domain")

    def _apply_es_runtime(self, row: dict[str, Any], result: Any) -> None:
        if not isinstance(result, dict):
            return
        if result.get("current_index_name") is not None:
            row["es_current_index_name"] = result.get("current_index_name")
        if result.get("current_index_detail") is not None:
            row["es_current_index_info"] = result.get("current_index_detail")
        elif result.get("current_index_info_raw") is not None:
            row["es_current_index_info"] = result.get("current_index_info_raw")
        if result.get("should_rotate") is not None:
            row["es_should_rotate_index"] = result.get("should_rotate")

    def _record_runtime_error(
        self,
        row: dict[str, Any],
        kind: str,
        args: dict[str, Any],
        msg: str,
    ) -> None:
        """记录 runtime 错误信息. 不阻断行返回."""
        msg_short = f"[{kind}] {msg}"
        if kind in ("bkbase_metadata", "databus_prefer_cluster"):
            prev = row.get("bkbase_remote_error") or ""
            row["bkbase_remote_error"] = (prev + msg_short + "; ").strip()
        elif kind == "es_runtime":
            row["es_runtime_error"] = msg
        elif kind == "component_status":
            comp_idx = args.get("comp_idx")
            comps = row.get("bkbase_components") or []
            if isinstance(comp_idx, int) and 0 <= comp_idx < len(comps):
                comps[comp_idx]["status_error"] = msg
            else:
                prev = row.get("bkbase_remote_error") or ""
                row["bkbase_remote_error"] = (prev + msg_short + "; ").strip()


class GetDataLinkMetadataResource(Resource):
    """
    查询数据链路元数据 - 通过计算平台 v4 meta API
    """

    class RequestSerializer(serializers.Serializer):
        bk_data_id = serializers.IntegerField(label="计算平台数据ID", required=False)
        vm_result_table_id = serializers.CharField(label="VM结果表ID", required=False)

        def validate(self, attrs):
            if not (bool(attrs.get("bk_data_id")) ^ bool(attrs.get("vm_result_table_id"))):
                raise serializers.ValidationError(
                    "bk_data_id and vm_result_table_id are mutually exclusive, one must be specified"
                )
            return attrs

    def perform_request(self, validated_request_data):
        logger.info("GetDataLinkMetadataResource: querying metadata with params: %s", validated_request_data)
        result = api.bkdata.get_data_link_metadata(**validated_request_data)
        return result
