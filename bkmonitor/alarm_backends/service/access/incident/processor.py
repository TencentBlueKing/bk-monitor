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
import copy
import json
import logging
import time
from typing import Dict

from pika.adapters.blocking_connection import BlockingChannel
from pika.spec import Basic

from alarm_backends.core.alert import Alert
from alarm_backends.core.cache.key import ALERT_FIRST_HANDLE_RECORD
from alarm_backends.core.cache.strategy import StrategyCacheManager
from alarm_backends.core.storage.rabbitmq import RabbitMQClient
from alarm_backends.service.access.base import BaseAccessProcess
from alarm_backends.service.fta_action.tasks import create_actions
from bkmonitor.aiops.incident.models import IncidentSnapshot
from bkmonitor.aiops.incident.operation import IncidentOperationManager
from bkmonitor.documents import AlertLog
from bkmonitor.documents.alert import AlertDocument
from bkmonitor.documents.base import BulkActionType
from bkmonitor.documents.incident import IncidentDocument, IncidentSnapshotDocument
from constants.action import ActionSignal
from constants.alert import EventStatus
from constants.incident import (
    IncidentGraphComponentType,
    IncidentStatus,
    IncidentSyncType,
)
from core.drf_resource import api
from core.errors.incident import IncidentNotFoundError
from core.prometheus import metrics

logger = logging.getLogger("access.incident")


class BaseAccessIncidentProcess(BaseAccessProcess):
    pass


class AccessIncidentProcess(BaseAccessIncidentProcess):
    def __init__(self, broker_url: str, queue_name: str) -> None:
        super(AccessIncidentProcess, self).__init__()

        self.broker_url = broker_url
        self.queue_name = queue_name
        self.client = RabbitMQClient(broker_url=broker_url)
        self.client.ping()
        self.actions = []

    def process(self) -> None:
        def callback(ch: BlockingChannel, method: Basic.Deliver, properties: Dict, body: str):
            sync_info = json.loads(body)
            self.handle_sync_info(sync_info)
            ch.basic_ack(method.delivery_tag)

        self.client.start_consuming(self.queue_name, callback=callback)

    def check_incident_actions(self, sync_info):
        if sync_info.get("incident_stage") == "stage_exp" and sync_info.get("incident_actions"):
            self.actions = sync_info["incident_actions"]
            return True
        return False

    def push_action(self):
        if not self.actions:
            return

        # 对于满足条件的策略，推送信号到Action模块执行动作
        for action in self.actions:
            success_actions = 0
            qos_actions = 0
            related_alerts = action.get("related_alerts")
            if not related_alerts or str(action.get("signal")).lower() != ActionSignal.INCIDENT.lower():
                continue
            top_alert = Alert(data=related_alerts[0])
            operate_attrs = {
                "strategy_id": action["strategy_id"],
                "signal": action["signal"],
                "alert_ids": [top_alert.id],
                "alerts": [top_alert.to_document()],
                "severity": action["severity"],
            }
            # 限流计数器，监控的告警以策略ID，信号，告警级别作为维度
            try:
                is_qos, current_count = top_alert.qos_calc(action["signal"])
                logger.info(
                    "[composite send action] alert(%s) strategy(%s) signal(%s) severity(%s) ",
                    top_alert.id,
                    action["strategy_id"],
                    action["signal"],
                    action["severity"],
                )
                if not is_qos:
                    create_actions.delay(**operate_attrs)
                    success_actions += 1
                else:
                    # 达到阈值之后，触发流控
                    logger.info(
                        "[action qos triggered] alert(%s) strategy(%s) signal(%s) severity(%s) qos_count: %s",
                        top_alert.id,
                        action["strategy_id"],
                        action["signal"],
                        action["severity"],
                        current_count,
                    )
                    qos_actions += 1

                    # 被QOS的，按照策略维度发送一份
                    # 被QOS的情况下，需要删除首次处理记录
                    first_handle_key = ALERT_FIRST_HANDLE_RECORD.get_key(
                        strategy_id=top_alert.strategy_id or 0, alert_id=top_alert.id, signal=action["signal"]
                    )
                    ALERT_FIRST_HANDLE_RECORD.client.delete(first_handle_key)

                    metrics.COMPOSITE_PUSH_ACTION_COUNT.labels(
                        strategy_id=action["strategy_id"], signal=action["signal"], is_qos="1", status="success"
                    ).inc()

                metrics.COMPOSITE_PUSH_ACTION_COUNT.labels(
                    strategy_id=metrics.TOTAL_TAG,
                    signal=action["signal"],
                    is_qos="1" if is_qos else "0",
                    status="success",
                ).inc()
            except Exception as e:
                logger.exception(
                    "[composite push action ERROR] alert(%s) strategy(%s) detail: %s",
                    top_alert.id,
                    action["strategy_id"],
                    e,
                )
                metrics.COMPOSITE_PUSH_ACTION_COUNT.labels(
                    strategy_id=metrics.TOTAL_TAG, is_qos="0", signal=action["signal"], status="failed"
                ).inc()
                continue
            if qos_actions:
                # 如果有被qos的事件， 进行日志记录
                qos_log = Alert.create_qos_log([top_alert.id], current_count, qos_actions)
                AlertLog.bulk_create([qos_log])

    def handle_sync_info(self, sync_info: Dict) -> None:
        """处理rabbitmq中的内容.

        :param sync_info: 同步内容
        """
        if sync_info["sync_type"] == IncidentSyncType.CREATE.value:
            self.create_incident(sync_info)
        elif sync_info["sync_type"] == IncidentSyncType.UPDATE.value:
            self.update_incident(sync_info)

    def create_incident(self, sync_info: Dict) -> None:
        """根据同步信息，从AIOPS接口获取故障详情，并创建到监控的ES中.

        :param sync_info: 同步内容
        """
        # 生成故障归档记录
        logger.info(f"[CREATE]Access incident[{sync_info['incident_id']}], sync_info: {json.dumps(sync_info)}")
        try:
            if self.check_incident_actions(sync_info):
                self.push_action()
                # Todo: alert级别故障页面展示开发未完成，暂不进行快照和前端展示
                return

            incident_info = sync_info["incident_info"]
            incident_info["incident_id"] = sync_info["incident_id"]
            incident_document = IncidentDocument(**incident_info)
            snapshot_info = api.bkdata.get_incident_snapshot(snapshot_id=sync_info["fpp_snapshot_id"])

            snapshot = IncidentSnapshotDocument(
                incident_id=sync_info["incident_id"],
                bk_biz_ids=sync_info["scope"]["bk_biz_ids"],
                status=incident_info["status"],
                alerts=sync_info["scope"]["alerts"],
                events=sync_info["scope"]["events"],
                create_time=sync_info["rca_time"],
                content=snapshot_info,
                fpp_snapshot_id=sync_info["fpp_snapshot_id"],
            )
            logger.info(f"[CREATE]Success to init incident[{sync_info['incident_id']}] data")
        except Exception as e:
            logger.error(f"[CREATE]Access incident error: {e}", exc_info=True)
            return

        # 更新告警所属故障
        self.update_alert_incident_relations(incident_document, snapshot)

        # 生成故障快照记录
        try:
            IncidentSnapshotDocument.bulk_create([snapshot], action=BulkActionType.CREATE)

            # 补充快照记录并写入ES
            incident_document.snapshot = snapshot
            incident_document.status_order = IncidentStatus(incident_document.status).order
            incident_document.alert_count = len(snapshot.alerts)
            snapshot_model = IncidentSnapshot(copy.deepcopy(snapshot.content.to_dict()))
            self.generate_incident_labels(incident_document, snapshot_model)
            incident_document.generate_handlers(snapshot_model)
            incident_document.generate_assignees(snapshot_model)
            api.bkdata.update_incident_detail(
                incident_id=sync_info["incident_id"],
                assignees=incident_document.assignees,
                handlers=incident_document.handlers,
                labels=incident_document.labels,
            )
            IncidentDocument.bulk_create([incident_document], action=BulkActionType.CREATE)
            logger.info(f"[CREATE]Success to access incident[{sync_info['incident_id']}] as document")
        except Exception as e:
            logger.error(f"[CREATE]Access incident as document error: {e}", exc_info=True)
            return

        # 记录故障流转
        try:
            IncidentOperationManager.record_create_incident(
                incident_id=sync_info["incident_id"],
                operate_time=incident_info["create_time"],
                alert_count=len(sync_info["scope"]["alerts"]),
                assignees=incident_document.assignees,
            )
        except Exception as e:
            logger.error(f"[CREATE]Record incident operations error: {e}", exc_info=True)
            return

    def update_alert_incident_relations(
        self, incident_document: IncidentDocument, snapshot: IncidentSnapshotDocument
    ) -> Dict[int, AlertDocument]:
        """更新告警关联故障的关联关系

        :param incident_document: 故障实例
        :param snapshot: 故障快照
        :return: 告警字典，用于复用告警的内容
        """
        snapshot_alerts = {}
        update_alerts = []
        for item in snapshot.content.incident_alerts:
            alert_doc = AlertDocument.get(item["id"])
            snapshot_alerts[item["id"]] = alert_doc
            if alert_doc.incident_id == incident_document.id:
                continue

            alert_doc.incident_id = incident_document.id
            update_alerts.append(alert_doc)

        AlertDocument.bulk_create(update_alerts, action=BulkActionType.UPDATE)

        return snapshot_alerts

    def update_incident(self, sync_info: Dict) -> None:
        """根据同步信息，从AIOPS接口获取故障详情，并更新到监控的ES中.

        :param sync_info: 同步内容
        """
        logger.info(f"[UPDATE]Access incident[{sync_info['incident_id']}], sync_info: {json.dumps(sync_info)}")
        snapshot = None
        # 更新故障归档记录
        try:
            incident_info = sync_info["incident_info"]
            incident_info["incident_id"] = sync_info["incident_id"]
            incident_document = IncidentDocument.get(
                f"{incident_info['create_time']}{incident_info['incident_id']}", fetch_remote=False
            )
            if "fpp_snapshot_id" in sync_info and sync_info["fpp_snapshot_id"]:
                snapshot_info = api.bkdata.get_incident_snapshot(snapshot_id=sync_info["fpp_snapshot_id"])

                snapshot = IncidentSnapshotDocument(
                    incident_id=sync_info["incident_id"],
                    bk_biz_ids=sync_info["scope"]["bk_biz_ids"],
                    status=incident_info["status"],
                    alerts=sync_info["scope"]["alerts"],
                    events=sync_info["scope"]["events"],
                    create_time=sync_info["rca_time"],
                    content=snapshot_info,
                    fpp_snapshot_id=sync_info["fpp_snapshot_id"],
                )

            logger.info(f"[UPDATE]Success to init incident[{sync_info['incident_id']}] data")
        except IncidentNotFoundError as e:
            logger.warn(f"[UPDATE]Access incident error: {e}, CREATE IT", exc_info=True)
            self.create_incident(sync_info)
            return
        except Exception as e:
            logger.error(f"[UPDATE]Access incident error: {e}", exc_info=True)
            return

        # 更新告警所属故障
        snapshot_alerts = self.update_alert_incident_relations(incident_document, snapshot)

        # 生成故障快照记录
        try:
            if snapshot:
                IncidentSnapshotDocument.bulk_create([snapshot], action=BulkActionType.CREATE)

                # 补充快照记录并写入ES
                self.generate_alert_operations(incident_document.snapshot, snapshot_alerts)
                incident_document.snapshot = snapshot
                incident_document.alert_count = len(snapshot.alerts)
                snapshot_model = IncidentSnapshot(copy.deepcopy(snapshot.content.to_dict()))
                self.generate_incident_labels(incident_document, snapshot_model)
                incident_document.generate_handlers(snapshot_model)
                incident_document.generate_assignees(snapshot_model)
                api.bkdata.update_incident_detail(
                    incident_id=sync_info["incident_id"],
                    assignees=incident_document.assignees,
                    handlers=incident_document.handlers,
                    labels=incident_document.labels,
                )
                api.bkdata.update_incident_detail(incident_id=sync_info["incident_id"], labels=incident_document.labels)

            IncidentDocument.bulk_create([incident_document], action=BulkActionType.UPDATE)
            logger.info(f"[UPDATE]Success to access incident[{sync_info['incident_id']}] as document")
        except Exception as e:
            logger.error(f"[UPDATE]Access incident as document error: {e}", exc_info=True)
            return

        # 记录故障流转
        try:
            for incident_key, update_info in sync_info["update_attributes"].items():
                if update_info["from"]:
                    IncidentOperationManager.record_update_incident(
                        incident_id=sync_info["incident_id"],
                        operate_time=incident_info["update_time"],
                        incident_key=incident_key,
                        from_value=update_info["from"],
                        to_value=update_info["to"],
                    )
                    if incident_key == "status":
                        if update_info["to"] == IncidentStatus.RECOVERING.value:
                            incident_document.end_time = int(time.time())
                        elif update_info["to"] == IncidentStatus.ABNORMAL.value:
                            incident_document.end_time = None
                        api.bkdata.update_incident_detail(
                            incident_id=sync_info["incident_id"],
                            end_time=incident_document.end_time,
                        )
                setattr(incident_document, incident_key, update_info["to"])

            incident_document.status_order = IncidentStatus(incident_document.status).order
            IncidentDocument.bulk_create([incident_document], action=BulkActionType.UPDATE)
        except Exception as e:
            logger.error(f"[UPDATE]Record incident operations error: {e}", exc_info=True)
            return

    def generate_incident_labels(self, incident, snapshot) -> None:
        """生成故障标签

        :param snapshot: 故障分析结果图谱快照信息
        """
        strategy_ids = set()
        for incident_alert in snapshot.alert_entity_mapping.values():
            if incident_alert.entity.component_type == IncidentGraphComponentType.PRIMARY:
                strategy_ids.add(incident_alert.strategy_id)

        strategies = StrategyCacheManager.get_strategy_by_ids(list(strategy_ids))
        labels = []
        for strategy in strategies:
            labels.extend(strategy["labels"])
        whole_labels = list(set(labels) | set(incident.labels))
        incident.labels = whole_labels

    def generate_alert_operations(
        self, last_snapshot: IncidentSnapshotDocument, snapshot_alerts: Dict[int, AlertDocument]
    ) -> None:
        """生成故障快照记录的告警操作记录."""
        last_snapshot_alerts = {item["id"]: item for item in last_snapshot.content.incident_alerts}
        for alert_doc in snapshot_alerts.values():
            if alert_doc.id not in last_snapshot_alerts:
                IncidentOperationManager.record_incident_alert_trigger(
                    last_snapshot.incident_id,
                    int(int(alert_doc.begin_time) / 1000),
                    alert_doc.alert_name,
                    alert_doc.id,
                )
            elif (
                alert_doc.id in last_snapshot_alerts
                and last_snapshot_alerts[alert_doc.id]["alert_status"] != alert_doc.status
            ):
                operation = {
                    EventStatus.RECOVERED: IncidentOperationManager.record_incident_alert_recover,
                    EventStatus.CLOSED: IncidentOperationManager.record_incident_alert_invalid,
                }.get(alert_doc.status)
                if operation:
                    operation(
                        last_snapshot.incident_id,
                        int(int(alert_doc.begin_time) / 1000),
                        alert_doc.alert_name,
                        alert_doc.id,
                    )
