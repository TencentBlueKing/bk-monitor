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
from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bkmonitor.utils.serializers import TenantIdField
from core.drf_resource import Resource
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
    查询数据链路元数据 - 简化的结构化API，用于程序化提取
    返回英文字段的结构化数据，不包含复杂的路由信息
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        bk_data_id = serializers.CharField(label="数据源ID", required=True)

    def perform_request(self, validated_request_data):
        bk_tenant_id = validated_request_data["bk_tenant_id"]
        bk_data_id = validated_request_data["bk_data_id"]

        try:
            # 获取数据源
            ds = models.DataSource.objects.get(bk_tenant_id=bk_tenant_id, bk_data_id=bk_data_id)

            # 构建结构化响应
            result = {
                "data_source": self._build_data_source_info(ds),
                "kafka_config": self._build_kafka_config(ds),
                "result_tables": self._build_result_tables_info(bk_tenant_id, bk_data_id),
            }

            return result

        except models.DataSource.DoesNotExist:
            raise ValidationError(f"Data source {bk_data_id} does not exist")
        except Exception as e:
            logger.error(
                "QueryDataLinkMetadataResource: Failed to query metadata, bk_data_id: %s, error: %s",
                bk_data_id,
                str(e),
            )
            raise ValidationError(f"Failed to query metadata: {str(e)}")

    def _build_data_source_info(self, ds: models.DataSource) -> dict[str, Any]:
        """构建数据源基础信息"""
        return {
            "bk_data_id": ds.bk_data_id,
            "data_name": ds.data_name,
            "source_system": ds.source_system,
            "etl_config": ds.etl_config,
            "is_enabled": ds.is_enable,
            "is_platform_data_id": ds.is_platform_data_id,
            "created_from": ds.created_from,
            "transfer_cluster_id": ds.transfer_cluster_id,
            "data_link_version": "v4" if ds.created_from == DataIdCreatedFromSystem.BKDATA.value else "v3",
        }

    def _build_kafka_config(self, ds: models.DataSource) -> dict[str, Any]:
        """构建Kafka配置信息"""
        try:
            cluster = models.ClusterInfo.objects.get(bk_tenant_id=ds.bk_tenant_id, cluster_id=ds.mq_cluster_id)
            mq_config = models.KafkaTopicInfo.objects.get(id=ds.mq_config_id)

            return {
                "cluster_id": cluster.cluster_id,
                "cluster_name": cluster.cluster_name,
                "domain_name": cluster.domain_name,
                "topic": mq_config.topic,
                "partition": mq_config.partition,
            }
        except Exception as e:
            logger.warning("Failed to get Kafka config for data_id %s: %s", ds.bk_data_id, str(e))
            return {"error": f"Failed to retrieve Kafka configuration: {str(e)}"}

    def _build_result_tables_info(self, bk_tenant_id: str, bk_data_id: str) -> list[dict[str, Any]]:
        """构建结果表信息列表"""
        result_tables = []

        # 获取该数据源的所有结果表
        dsrt = models.DataSourceResultTable.objects.filter(bk_data_id=bk_data_id)
        table_ids = list(dsrt.values_list("table_id", flat=True))

        for table_id in table_ids:
            try:
                rt = models.ResultTable.objects.get(bk_tenant_id=bk_tenant_id, table_id=table_id)

                # 获取空间信息
                space_info = self._get_space_info(bk_tenant_id, rt.bk_biz_id)

                # 构建基础结果表信息
                rt_info = {
                    "table_id": table_id,
                    "storage_type": rt.default_storage,
                    "bk_biz_id": rt.bk_biz_id,
                    "space_uid": space_info["space_uid"],
                    "space_name": space_info["space_name"],
                    "is_enabled": rt.is_enable,
                    "data_label": rt.data_label,
                }

                # 添加存储特定信息
                if rt.default_storage == models.ClusterInfo.TYPE_ES:
                    rt_info["storage_details"] = self._get_es_storage_info(bk_tenant_id, table_id)
                elif (
                    rt.default_storage == models.ClusterInfo.TYPE_VM
                    or rt.default_storage == models.ClusterInfo.TYPE_INFLUXDB
                ):
                    rt_info["storage_details"] = self._get_vm_storage_info(bk_tenant_id, table_id)

                # 如果存在后端Kafka配置，添加到返回信息
                backend_kafka = self._get_backend_kafka_info(bk_tenant_id, table_id)
                if backend_kafka:
                    rt_info["backend_kafka"] = backend_kafka

                result_tables.append(rt_info)

            except Exception as e:
                logger.warning("Failed to get info for table_id %s: %s", table_id, str(e))
                result_tables.append(
                    {
                        "table_id": table_id,
                        "error": f"Failed to retrieve table information: {str(e)}",
                    }
                )

        return result_tables

    def _get_space_info(self, bk_tenant_id: str, bk_biz_id: int) -> dict[str, str]:
        """获取空间信息"""
        try:
            if bk_biz_id > 0:
                space = models.Space.objects.get(
                    bk_tenant_id=bk_tenant_id, space_type_id=SpaceTypes.BKCC.value, space_id=bk_biz_id
                )
            elif bk_biz_id < 0:
                space = models.Space.objects.get(bk_tenant_id=bk_tenant_id, id=abs(bk_biz_id))
            else:
                return {"space_uid": "global", "space_name": "Global"}

            return {
                "space_uid": f"{space.space_type_id}__{space.space_id}",
                "space_name": space.space_name,
            }
        except Exception:
            return {"space_uid": "unknown", "space_name": "Unknown"}

    def _get_backend_kafka_info(self, bk_tenant_id: str, table_id: str) -> dict[str, Any] | None:
        """获取后端Kafka配置信息"""
        try:
            kafka_storage = models.KafkaStorage.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id).first()
            if not kafka_storage:
                return None

            cluster = models.ClusterInfo.objects.get(
                bk_tenant_id=bk_tenant_id, cluster_id=kafka_storage.storage_cluster_id
            )

            return {
                "cluster_id": kafka_storage.storage_cluster_id,
                "cluster_name": cluster.cluster_name,
                "domain_name": cluster.domain_name,
                "topic": kafka_storage.topic,
                "partition": kafka_storage.partition,
            }
        except Exception:
            return None

    def _get_es_storage_info(self, bk_tenant_id: str, table_id: str) -> dict[str, Any]:
        """获取ES存储信息"""
        try:
            es_storage = models.ESStorage.objects.get(bk_tenant_id=bk_tenant_id, table_id=table_id)
            es_cluster = models.ClusterInfo.objects.get(
                bk_tenant_id=bk_tenant_id, cluster_id=es_storage.storage_cluster_id
            )

            return {
                "type": "elasticsearch",
                "cluster_id": es_storage.storage_cluster_id,
                "cluster_name": es_cluster.cluster_name,
                "domain_name": es_cluster.domain_name,
                "index_set": es_storage.index_set,
                "slice_size_gb": es_storage.slice_size,
                "slice_gap_minutes": es_storage.slice_gap,
            }
        except Exception as e:
            return {"type": "elasticsearch", "error": str(e)}

    def _get_vm_storage_info(self, bk_tenant_id: str, table_id: str) -> dict[str, Any]:
        """获取VM（VictoriaMetrics/计算平台）存储信息"""
        try:
            vm_records = models.AccessVMRecord.objects.filter(bk_tenant_id=bk_tenant_id, result_table_id=table_id)

            if not vm_records.exists():
                return {"type": "vm", "error": "No VM access record found"}

            vm_info_list = []
            for vm in vm_records:
                try:
                    vm_cluster = models.ClusterInfo.objects.get(bk_tenant_id=bk_tenant_id, cluster_id=vm.vm_cluster_id)
                    vm_info_list.append(
                        {
                            "vm_result_table_id": vm.vm_result_table_id,
                            "vm_cluster_id": vm.vm_cluster_id,
                            "storage_cluster_id": vm.storage_cluster_id,
                            "bk_base_data_id": vm.bk_base_data_id,
                            "domain_name": vm_cluster.domain_name,
                        }
                    )
                except Exception as e:
                    logger.warning("Failed to get VM cluster info: %s", str(e))
                    continue

            return {"type": "vm", "records": vm_info_list}
        except Exception as e:
            return {"type": "vm", "error": str(e)}
