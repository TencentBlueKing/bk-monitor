"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import concurrent.futures
import logging
import json

from alarm_backends.core.alert.alert import Alert, AlertKey
from bkmonitor.documents import AlertDocument
from bkmonitor.documents.base import BulkActionType
from core.drf_resource import api

logger = logging.getLogger("denoise")


class DenoiseProcessor:
    MAX_DENOISE_COUNT = 1000

    """基于业务降噪模型的告警降噪处理模块.

    todo: 如果当前降噪逻辑接入action_instance表，则需要继承BaseActionProcessor
    """

    def __init__(self, alert_ids):
        alert_keys = [AlertKey(alert_id=alert_id, strategy_id=self.strategy_id) for alert_id in alert_ids]
        self.alerts = Alert.mget(alert_keys)

    def process(self):
        """处理降噪告警逻辑."""
        alert_data = []
        for alert in self.alerts:
            alert_data.append(
                {
                    "timestamp": alert.latest_time,
                    "id": alert.id,
                    "alert_name": alert.alert_name,
                    "assignee": alert.assignee,
                    "bk_biz_id": alert.event.bk_biz_id,
                    "dimensions": alert.dimensions,
                    "duration": alert.duration,
                    "event": json.dumps(
                        {
                            "descritpion": alert.event.description,
                            "data_type": alert.event.data_type,
                            "dedupe_keys": alert.event.dedupe_keys,
                            "tags": alert.event.tags,
                        }
                    ),
                    "first_anomaly_time": alert.first_anomaly_time,
                    "severity": alert.severity,
                    "status": alert.status,
                    "strategy": json.dumps(
                        {
                            "items": alert.strategy.items,
                        }
                    ),
                    "strategy_id": alert.strategy_id,
                }
            )

        tasks = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            index = 0
            while index < len(alert_data):
                tasks.append(
                    executor.submit(
                        api.aiops_sdk.kpi_predict,
                        data={"data": alert_data[index : index + self.MAX_DENOISE_COUNT]},
                    )
                )
                index += self.MAX_DENOISE_COUNT

        alert_docs = []
        for future in concurrent.futures.as_completed(tasks):
            try:
                predict_result = future.result()
                for output_data in predict_result:
                    if output_data["is_denoise"]:
                        alert_doc = AlertDocument.get(int(predict_result["__index__"]))
                        alert_doc.is_noise = True
                        alert_doc.denoise_embedding = predict_result["embedding"]
                        alert_docs.append(alert_doc)
            except Exception as e:
                # 统计检测异常的策略
                logger.warning(f"Predict error: {e}")

        AlertDocument.bulk_create(alert_docs, action=BulkActionType.UPDATE)
