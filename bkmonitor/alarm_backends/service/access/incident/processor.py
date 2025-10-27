"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
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

from pika.adapters.blocking_connection import BlockingChannel
from pika.spec import Basic

from alarm_backends.core.cache.strategy import StrategyCacheManager
from alarm_backends.core.storage.rabbitmq import RabbitMQClient
from alarm_backends.service.access.base import BaseAccessProcess
from alarm_backends.service.composite.tasks import check_incident_action_and_composite
from bkmonitor.aiops.incident.models import IncidentSnapshot
from bkmonitor.aiops.incident.operation import IncidentOperationManager
from bkmonitor.documents.alert import AlertDocument
from bkmonitor.documents.base import BulkActionType
from bkmonitor.documents.incident import IncidentDocument, IncidentSnapshotDocument
from constants.alert import EventStatus
from constants.incident import (
    IncidentGraphComponentType,
    IncidentStatus,
    IncidentSyncType,
)
from core.drf_resource import api
from core.errors.incident import IncidentNotFoundError

logger = logging.getLogger("access.incident")


class BaseAccessIncidentProcess(BaseAccessProcess):
    pass


class AccessIncidentProcess(BaseAccessIncidentProcess):
    def __init__(self, broker_url: str, queue_name: str) -> None:
        super().__init__()

        self.broker_url = broker_url
        self.queue_name = queue_name
        self.client = RabbitMQClient(broker_url=broker_url)
        self.client.ping()
        self.actions = []

    def process(self) -> None:
        def callback(ch: BlockingChannel, method: Basic.Deliver, properties: dict, body: str):
            sync_info = json.loads(body)
            self.handle_sync_info(sync_info)
            ch.basic_ack(method.delivery_tag)

        self.client.start_consuming(self.queue_name, callback=callback)

    def check_incident_actions(self, sync_info):
        if sync_info.get("incident_stage") == "stage_exp" and sync_info.get("incident_actions"):
            self.actions = sync_info["incident_actions"]
            return True
        return False

    def handle_sync_info(self, sync_info: dict) -> None:
        """处理rabbitmq中的内容.

        :param sync_info: 同步内容
        """
        if sync_info["sync_type"] == IncidentSyncType.CREATE.value:
            self.create_incident(sync_info)
        elif sync_info["sync_type"] == IncidentSyncType.UPDATE.value:
            self.update_incident(sync_info)

    def create_incident(self, sync_info: dict) -> None:
        """根据同步信息，从AIOPS接口获取故障详情，并创建到监控的ES中.

        :param sync_info: 同步内容
        """
        # 生成故障归档记录
        logger.info(f"[CREATE]Access incident[{sync_info['incident_id']}], sync_info: {json.dumps(sync_info)}")
        try:
            if self.check_incident_actions(sync_info):
                check_incident_action_and_composite.apply_async(
                    kwargs={
                        "incident_id": sync_info["incident_id"],
                        "incident_stage": sync_info["incident_stage"],
                        "incident_actions": self.actions,
                    },
                    countdown=1,
                )
                # Todo: alert级别故障页面展示开发未完成，暂不进行快照和前端展示
                return

            incident_info = sync_info["incident_info"]
            incident_info["incident_id"] = sync_info["incident_id"]
            incident_document = IncidentDocument(**incident_info)

            if sync_info["fpp_snapshot_id"] == "fpp:None":
                snapshot_info = {
                    "bk_biz_id": incident_info["bk_biz_id"],
                    "incident_alerts": [{"id": alert_id} for alert_id in sync_info.get("scope", {}).get("alerts", [])],
                    "rca_summary": {"bk_biz_ids": [incident_info["bk_biz_id"]]},
                }
            else:
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
    ) -> dict[int, AlertDocument]:
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

    def update_incident(self, sync_info: dict) -> None:
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
            if "fpp_snapshot_id" in sync_info and sync_info["fpp_snapshot_id"] != "fpp:None":
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

        # 生成故障快照记录
        try:
            if snapshot:
                # 更新告警所属故障
                snapshot_alerts = self.update_alert_incident_relations(incident_document, snapshot)

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
        self, last_snapshot: IncidentSnapshotDocument, snapshot_alerts: dict[int, AlertDocument]
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
