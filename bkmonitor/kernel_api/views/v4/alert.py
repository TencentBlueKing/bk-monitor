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
import time
from typing import Any

from rest_framework import serializers

from alarm_backends.core.alert.alert import Alert
from alarm_backends.core.cache.key import ALERT_UPDATE_LOCK
from alarm_backends.core.lock.service_lock import multi_service_lock
from alarm_backends.service.alert.manager.checker.close import CloseStatusChecker
from alarm_backends.service.alert.manager.processor import AlertManager
from bkmonitor.documents.alert import AlertDocument
from constants.alert import EventStatus
from core.drf_resource import Resource, resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from fta_web.alert.serializers import AlertIDField
from kernel_api.resource.qos import FailurePublishResource, FailureRecoveryResource
from kernel_api.resource.alert import ListAlertResource

logger = logging.getLogger("kernel_api")


class AlertInfoViewSet(ResourceViewSet):
    """
    根据事件ID获取告警的相关信息
    """

    resource_routes = [
        ResourceRoute("POST", resource.alert.search_alert_by_event, endpoint="search_alert_by_event"),
        ResourceRoute("POST", resource.alert.list_alert_tags, endpoint="list_alert_tags"),
    ]


class SearchAlertViewSet(ResourceViewSet):
    """
    查询告警列表
    """

    resource_routes = [
        ResourceRoute("POST", resource.alert.search_alert, endpoint="search_alert"),
        ResourceRoute("POST", ListAlertResource, endpoint="list_alert"),
    ]


class CloseAlertResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        ids = serializers.ListField(label="告警ID列表", child=AlertIDField())
        message = serializers.CharField(allow_blank=True, label="确认信息", default="")

    def perform_request(self, validated_request_data: dict[str, Any]):
        alert_ids = validated_request_data["ids"]
        max_retries = 3  # 最大重试次数
        retry_interval = 5  # 重试间隔（秒）

        # 需要关闭的告警
        alerts_should_close = set()
        # 已经结束的告警
        alerts_already_end = set()
        # 加锁失败的告警
        alerts_lock_failed = set()

        # 从ES获取告警文档
        alert_docs = AlertDocument.mget(alert_ids)

        # 转换为Alert对象并过滤需要处理的告警
        alerts_to_process = []
        alert_objects_map = {}  # 存储alert对象，避免重复创建
        for alert_doc in alert_docs:
            # 告警状态为异常且未确认，则需要关闭
            if alert_doc.status == EventStatus.ABNORMAL and not alert_doc.is_ack:
                alert_obj = Alert(alert_doc.to_dict())
                alerts_to_process.append(alert_obj)
                alert_objects_map[alert_obj.id] = alert_obj
            else:
                alerts_already_end.add(alert_doc.id)

        # 对需要处理的告警进行加锁处理，支持重试
        retry_count = 0
        while alerts_to_process and retry_count < max_retries:
            retry_count += 1
            current_retry_failed = set()

            logger.info(
                "[CloseAlertResource] Attempt %s/%s to close %s alerts",
                retry_count,
                max_retries,
                len(alerts_to_process),
            )

            lock_keys = [ALERT_UPDATE_LOCK.get_key(dedupe_md5=alert.dedupe_md5) for alert in alerts_to_process]

            with multi_service_lock(ALERT_UPDATE_LOCK, lock_keys) as lock:
                for alert in alerts_to_process:
                    lock_key = ALERT_UPDATE_LOCK.get_key(dedupe_md5=alert.dedupe_md5)
                    if lock.is_locked(lock_key):
                        # 加锁成功，执行关闭操作
                        try:
                            CloseStatusChecker.close(alert, validated_request_data["message"] or "close by api")
                            AlertManager.save_alerts([alert])
                            AlertManager.save_alert_logs([alert])
                            AlertManager.update_alert_cache([alert])
                            AlertManager.update_alert_snapshot([alert])
                            alerts_should_close.add(alert.id)
                            logger.info(
                                "[CloseAlertResource] Successfully closed alert %s on attempt %s",
                                alert.id,
                                retry_count,
                            )
                        except Exception as e:
                            logger.exception("[CloseAlertResource] Failed to close alert %s: %s", alert.id, e)
                            current_retry_failed.add(alert.id)
                    else:
                        # 加锁失败
                        current_retry_failed.add(alert.id)
                        logger.warning(
                            "[CloseAlertResource] Failed to acquire lock for alert %s (dedupe_md5: %s) on attempt %s",
                            alert.id,
                            alert.dedupe_md5,
                            retry_count,
                        )

            # 准备下一轮重试
            if current_retry_failed and retry_count < max_retries:
                logger.info(
                    "[CloseAlertResource] %s alerts failed, waiting %s seconds before retry %s/%s",
                    len(current_retry_failed),
                    retry_interval,
                    retry_count + 1,
                    max_retries,
                )
                time.sleep(retry_interval)
                # 只重试加锁失败的告警
                alerts_to_process = [alert_objects_map[alert_id] for alert_id in current_retry_failed]
            else:
                # 没有失败的告警或已达到最大重试次数
                alerts_lock_failed = current_retry_failed
                break

        # 记录最终加锁失败的告警
        if alerts_lock_failed:
            logger.warning(
                "[CloseAlertResource] Final result: %s alerts failed after %s attempts: %s",
                len(alerts_lock_failed),
                retry_count,
                ", ".join(alerts_lock_failed),
            )

        # 不存在的告警
        alerts_not_exist = set(alert_ids) - alerts_should_close - alerts_already_end - alerts_lock_failed

        return {
            "alerts_close_success": list(alerts_should_close),
            "alerts_not_exist": list(alerts_not_exist),
            "alerts_already_end": list(alerts_already_end),
            "alerts_lock_failed": list(alerts_lock_failed),
        }


class AlertViewSet(ResourceViewSet):
    """
    兼容全量事件中心告警接口
    """

    resource_routes = [
        ResourceRoute("GET", resource.alert.list_allowed_biz, endpoint="allowed_biz"),
        ResourceRoute("GET", resource.alert.list_search_history, endpoint="search_history"),
        ResourceRoute("POST", resource.alert.search_alert, endpoint="alert/search"),
        ResourceRoute("POST", resource.alert.export_alert, endpoint="alert/export"),
        ResourceRoute("POST", resource.alert.alert_date_histogram, endpoint="alert/date_histogram"),
        ResourceRoute("POST", resource.alert.list_alert_tags, endpoint="alert/tags"),
        ResourceRoute("GET", resource.alert.alert_detail, endpoint="alert/detail"),
        ResourceRoute("GET", resource.alert.get_experience, endpoint="alert/get_experience"),
        ResourceRoute("POST", resource.alert.save_experience, endpoint="alert/save_experience"),
        ResourceRoute("POST", resource.alert.delete_experience, endpoint="alert/delete_experience"),
        ResourceRoute("POST", resource.alert.list_alert_log, endpoint="alert/log"),
        ResourceRoute("POST", resource.alert.search_event, endpoint="event/search"),
        ResourceRoute("POST", resource.alert.alert_event_count, endpoint="alert/event_count"),
        ResourceRoute("POST", resource.alert.alert_related_info, endpoint="alert/related_info"),
        ResourceRoute("POST", resource.alert.alert_extend_fields, endpoint="alert/extend_fields"),
        ResourceRoute("POST", resource.alert.ack_alert, endpoint="alert/ack"),
        ResourceRoute("POST", resource.alert.alert_graph_query, endpoint="alert/graph_query"),
        ResourceRoute("POST", resource.alert.event_date_histogram, endpoint="event/date_histogram"),
        ResourceRoute("POST", resource.alert.search_action, endpoint="action/search"),
        ResourceRoute("GET", resource.alert.action_detail, endpoint="action/detail"),
        ResourceRoute("GET", resource.alert.sub_action_detail, endpoint="action/detail/sub_actions"),
        ResourceRoute("POST", resource.alert.export_action, endpoint="action/export"),
        ResourceRoute("POST", resource.alert.action_date_histogram, endpoint="action/date_histogram"),
        ResourceRoute("POST", resource.alert.validate_query_string, endpoint="validate_query_string"),
        # 策略配置快照详情
        ResourceRoute("GET", resource.alert.strategy_snapshot, endpoint="strategy_snapshot"),
        ResourceRoute("POST", resource.alert.alert_top_n, endpoint="alert/top_n"),
        ResourceRoute("POST", resource.alert.action_top_n, endpoint="action/top_n"),
        ResourceRoute("POST", resource.alert.event_top_n, endpoint="event/top_n"),
        # 根据主机查询对应已下发的日志平台采集索引列表
        ResourceRoute("POST", resource.alert.list_index_by_host, endpoint="list_index_by_host"),
        # 告警反馈
        ResourceRoute("POST", resource.alert.feedback_alert, endpoint="alert/create_feedback"),
        ResourceRoute("GET", resource.alert.list_alert_feedback, endpoint="alert/list_feedback"),
        # 维度下钻
        ResourceRoute("GET", resource.alert.dimension_drill_down, endpoint="alert/dimension_drill_down"),
        # 指标推荐
        ResourceRoute("GET", resource.alert.metric_recommendation, endpoint="alert/metric_recommendation"),
        # 指标推荐反馈
        ResourceRoute(
            "POST", resource.alert.metric_recommendation_feedback, endpoint="alert/metric_recommendation_feedback"
        ),
        # 主机多指标异常检测告警详情图表
        ResourceRoute("GET", resource.alert.multi_anomaly_detect_graph, endpoint="alert/multi_anomaly_detect_graph"),
        # 业务统计相关接口
        ResourceRoute("GET", resource.alert.get_four_metrics_strategy, endpoint="alert/get_four_metrics_strategy"),
        ResourceRoute("GET", resource.alert.get_tmp_data, endpoint="alert/get_tmp_data"),
        ResourceRoute("GET", resource.alert.get_four_metrics_data, endpoint="alert/get_four_metrics_data"),
        ResourceRoute("POST", CloseAlertResource(), endpoint="alert/close"),
    ]


class QosViewSet(ResourceViewSet):
    """
    流控管理模块
    """

    resource_routes = [
        ResourceRoute("POST", FailurePublishResource(), endpoint="failure/publish"),
        ResourceRoute("POST", FailureRecoveryResource(), endpoint="failure/recovery"),
    ]
