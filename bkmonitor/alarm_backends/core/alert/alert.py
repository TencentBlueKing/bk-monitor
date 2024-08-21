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
from typing import List

from django.conf import settings
from django.utils.translation import ugettext as _
from MySQLdb import DatabaseError as MysqlDatabaseError
from redis.exceptions import RedisError

from alarm_backends.constants import DEFAULT_DEDUPE_FIELDS, NO_DATA_TAG_DIMENSION
from alarm_backends.core.alert.event import Event
from alarm_backends.core.cache.key import (
    ALERT_BUILD_QOS_COUNTER,
    ALERT_DEDUPE_CONTENT_KEY,
    ALERT_SNAPSHOT_KEY,
    ALERT_UUID_SEQUENCE,
    COMPOSITE_QOS_COUNTER,
)
from alarm_backends.core.cluster import get_cluster
from bkmonitor.documents import ActionInstanceDocument, AlertDocument, AlertLog
from bkmonitor.models import ActionInstance
from bkmonitor.strategy.expression import AlertExpressionValue
from bkmonitor.utils.common_utils import count_md5
from constants.action import ActionSignal, AssignMode
from constants.alert import EventStatus
from constants.data_source import DataTypeLabel
from core.prometheus import metrics

logger = logging.getLogger("alert")


class AlertKey:
    """
    告警标识，由告警ID和策略ID组成，用于从缓存中获取快照
    """

    def __init__(self, alert_id: int, strategy_id: int):
        self.alert_id = alert_id or 0
        self.strategy_id = strategy_id or 0

    def get_snapshot_key(self) -> str:
        return ALERT_SNAPSHOT_KEY.get_key(strategy_id=self.strategy_id, alert_id=self.alert_id)

    def __str__(self):
        return f"{self.alert_id}|{self.strategy_id}"


class Alert:
    ALERT_EXPRESSION_VALUE_MAPPING = {
        EventStatus.ABNORMAL: AlertExpressionValue.ABNORMAL,
        EventStatus.RECOVERED: AlertExpressionValue.NORMAL,
        EventStatus.CLOSED: AlertExpressionValue.NORMAL,
    }

    # 1个小时没有被更新的告警将被视为关闭
    CLOSE_WINDOW_SIZE = 60 * 60
    RECOVER_WINDOW_SIZE = 0

    def __init__(self, data):
        self.data = data

        self.data_id = None

        self.data_topic = None

        # 是否需要实时更新到DB
        self._refresh_db = False

        # 是否为新告警
        self._is_new = False

        # 告警状态是否发生改变
        self._status_changed = False

        # 流水日志
        self.logs: List[dict] = []

        # 最新事件
        self.last_event = None

        self.init_severity()

    def init_severity(self):
        # 智能监控如果有动态告警级别配置，则从extra_info里获取实际事件级别
        try:
            # 尝试取数据中的extra_info
            origin_alarm = self.extra_info["origin_alarm"]
            origin_extra_info = json.loads(origin_alarm["data"]["values"]["extra_info"])
            self.data["severity"] = origin_extra_info.get("alert_level_msg", {}).get(
                "alert_level", self.data["severity"]
            )
        except Exception:
            # 取不到就拉倒，用默认的
            return

    def update(self, event: Event):
        """
        根据给出的事件更新告警内容
        """
        self.refresh_update_time()
        # 收敛日志
        default_log = dict(
            op_type=AlertLog.OpType.CONVERGE,
            event_id=event.id,
            description=event.description,
            time=event.time,
            status=event.status,
        )

        # 判断事件级别，如果事件级别比告警级别高，则无视事件时间，无脑更新为告警的代表性事件
        if (
            event.status == EventStatus.ABNORMAL
            and event.severity < self.data["severity"]
            and self.severity_source != AssignMode.BY_RULE
        ):
            self.data["severity"] = event.severity
            self.data["event"] = event.to_dict()
            # 级别更新后，需要实时刷新告警
            self._refresh_db = True

            # 告警级别上升日志
            default_log = dict(
                op_type=AlertLog.OpType.SEVERITY_UP,
                event_id=event.id,
                severity=event.severity,
                description=event.description,
                time=event.time,
            )

        # 更新首次异常时间
        if self.data.get("first_anomaly_time") and event.anomaly_time:
            self.data["first_anomaly_time"] = min(self.data["first_anomaly_time"], event.anomaly_time)
        else:
            self.data["first_anomaly_time"] = event.anomaly_time

        if event.time < self.data["begin_time"]:
            # 如果事件时间小于告警开始时间，则更新一下告警开始时间
            self.data["begin_time"] = event.time
            self.add_log(**default_log)
            return

        if event.status == EventStatus.ABNORMAL and event.time < self.data["latest_time"]:
            # 如果事件时间小于当前告警的最新事件时间，则直接返回
            self.add_log(**default_log)
            return

        # 如果事件时间大于最新的一条事件时间，则更新告警
        self.data["latest_time"] = event.time

        if event.status == EventStatus.ABNORMAL:
            self.add_log(**default_log)

            # 更新告警级别：如果新的事件级别大于等于告警级别，才需要更新告警内容
            # (大于的情况已经在前面判断了)
            if event.severity == self.severity:
                self.data["event"] = event.to_dict()

            # 如果 next_status 是恢复，说明已经在等待恢复状态，此时需要打断这种状态，并且记录一条流水
            if self.data.get("next_status") == EventStatus.RECOVERED:
                self.add_log(
                    op_type=AlertLog.OpType.ABORT_RECOVER,
                    event_id=event.id,
                    time=event.time,
                )

            # 延长定时时间
            self.set_next_status(EventStatus.CLOSED, self.CLOSE_WINDOW_SIZE)
            self.data["status"] = EventStatus.ABNORMAL
            if self.assign_tags:
                self.update_top_event_tags(self.assign_tags)
        elif event.status == EventStatus.RECOVERED and self.RECOVER_WINDOW_SIZE:
            # 如果设置了恢复延迟，则设置一个定时
            self.set_next_status(EventStatus.RECOVERED, self.RECOVER_WINDOW_SIZE)
            # 此时仍为异常状态
            self.data["status"] = EventStatus.ABNORMAL

            self.add_log(
                op_type=AlertLog.OpType.DELAY_RECOVER,
                event_id=event.id,
                description=event.description,
                time=event.time,
                next_status=self.data["next_status"],
                next_status_time=self.data["next_status_time"],
            )
        else:
            # 即时设置告警状态
            # 1. status = RECOVERED 且未设置恢复延时
            # 2. status = CLOSED
            if event.status == EventStatus.RECOVERED:
                op_type = AlertLog.OpType.RECOVER
            else:
                op_type = AlertLog.OpType.CLOSE

            self.set_end_status(
                status=event.status,
                op_type=op_type,
                description=event.description,
                end_time=event.time,
                event_id=event.id,
            )

    def update_data_id_info(self, event: Event):
        self.data_id = event.data_id
        self.data_topic = event.topic

    def set_next_status(self, status, seconds):
        self.data["next_status_time"] = int(time.time()) + seconds
        self.data["next_status"] = status

    def clear_next_status(self):
        self.data["next_status_time"] = None
        self.data["next_status"] = None

    def move_to_next_status(self):
        """
        迁移到下一个状态
        """
        if not self.data.get("next_status_time") or not self.data.get("next_status"):
            # 如果没有下一个状态，那么就直接返回
            return False

        if self.data["next_status"] not in [EventStatus.RECOVERED, EventStatus.CLOSED]:
            # 如果状态不合法，则直接返回
            return False

        end_time = int(time.time())

        if self.data["next_status_time"] > end_time:
            return False

        # 如果已经到达了该转换状态的时间，那就进行转换

        # 先打个日志
        if self.data["next_status"] == EventStatus.RECOVERED:
            op_type = AlertLog.OpType.SYSTEM_RECOVER
        else:
            op_type = AlertLog.OpType.SYSTEM_CLOSE

        self.set_end_status(status=self.data["next_status"], op_type=op_type, end_time=end_time)
        return True

    def update_qos_status(self, is_blocked):
        self.data["is_blocked"] = is_blocked

    def is_valid_handle(self, execute_times=0, action_relation_id=None):
        if execute_times == 0 and action_relation_id is None:
            # 如果是没有处理过的的状态，则直接返回True,表示当次要执行
            return True
        handle_record = self.cycle_handle_record.get(str(action_relation_id), {})
        if not handle_record and action_relation_id:
            config_id = None
            if str(self.strategy.get("notice", {}).get("id", 0)) == str(action_relation_id):
                config_id = self.strategy["notice"]["config_id"]
            else:
                for action_config in self.strategy.get("actions", []):
                    if str(action_config["id"]) == str(action_relation_id):
                        config_id = action_config["config_id"]
                        break
            if config_id:
                handle_record = self.get_latest_interval_record(config_id=config_id, relation_id=action_relation_id)
        if handle_record and handle_record.get("execute_times") <= execute_times + 1:
            # 当此次执行的次数要大于记录次数情况下才进行处理
            return True

        return False

    def get_latest_interval_record(self, config_id, relation_id):
        # 根据告警ID搜索出对应的action_id
        if not config_id:
            # 没有处理记录的config_id，直接返回
            return None
        action_queryset = ActionInstance.objects.filter(
            strategy_relation_id=relation_id, need_poll=True, is_polled=False
        )
        action_ids = [
            action.raw_id
            for action in ActionInstanceDocument.mget_by_alert(
                alert_ids=[self.id],
                fields=["raw_id"],
                include={"action_config_id": config_id, "parent_action_id": 0},
            )
        ]
        if not action_ids:
            # 如果ES没有检索到，直接返回
            return None

        action = (
            action_queryset.filter(id__in=action_ids)
            .only("end_time", "execute_times", "inputs", "alerts")
            .order_by("-create_time")
            .first()
        )
        if not action:
            # 如果最近的告警数据不存在，直接返回None
            return None

        return {
            "last_time": int(action.end_time.timestamp()) if action.end_time else int(time.time()),
            "execute_times": action.execute_times,
            "is_shielded": action.inputs.get("is_alert_shielded", False),
            "latest_anomaly_time": action.inputs.get("alert_latest_time", 0),
        }

    @property
    def is_shielded(self):
        return self.data.get("is_shielded", False)

    @property
    def is_handled(self):
        return self.data.get("is_handled", False)

    @property
    def cycle_handle_record(self):
        return self.get_extra_info("cycle_handle_record", {})

    @property
    def strategy(self):
        return self.get_extra_info("strategy")

    @property
    def agg_dimensions(self):
        return self.get_extra_info("agg_dimensions", [])

    @property
    def severity_source(self):
        return self.get_extra_info("severity_source", "")

    @property
    def labels(self):
        return self.data.get("labels")

    @property
    def is_composite_strategy(self):
        """
        检查是否为关联告警策略
        """
        strategy = self.strategy
        if not strategy:
            return False
        for item in strategy.get("items", []):
            for query_config in item["query_configs"]:
                if query_config["data_type_label"] == DataTypeLabel.ALERT:
                    return True
        return False

    def refresh_duration(self):
        """
        刷新告警持续时间
        """
        if self.is_composite_strategy:
            # 如果是关联告警，则按当前时间计算告警持续时间
            current_time = self.end_time or int(time.time())
            duration = current_time - self.first_anomaly_time
        else:
            # 其他情况，按照最新事件时间计算持续时间
            duration = self.latest_time - self.first_anomaly_time
            # 设置60s的冗余时间，避免显示为0
        duration = max(duration, 60)
        self.data["duration"] = duration

    def to_dict(self) -> dict:
        self.init_uid()
        self.refresh_duration()
        return copy.deepcopy(self.data)

    def add_log(self, op_type: str, **params):
        params["op_type"] = op_type
        params["create_time"] = int(time.time())
        self.logs.append(params)

    @property
    def alert_name(self) -> str:
        return self.data["alert_name"]

    @property
    def bk_biz_id(self) -> int:
        return self.top_event.get("bk_biz_id") or 0

    @property
    def extra_info(self):
        return self.data.get("extra_info", {})

    @property
    def dedupe_md5(self) -> str:
        return self.data["dedupe_md5"]

    @property
    def begin_time(self) -> int:
        return self.data["begin_time"]

    @property
    def end_time(self) -> int:
        return self.data.get("end_time")

    @property
    def create_time(self) -> int:
        return self.data["create_time"]

    @property
    def latest_time(self) -> int:
        return self.data["latest_time"]

    @property
    def first_anomaly_time(self) -> int:
        return self.data["first_anomaly_time"]

    @property
    def update_time(self) -> int:
        return self.data["update_time"]

    @property
    def status(self) -> str:
        return self.data["status"]

    @property
    def is_blocked(self):
        return self.data.get("is_blocked", False)

    @property
    def expression_value(self) -> int:
        """
        告警在计算表达式时的取值
        """
        return self.ALERT_EXPRESSION_VALUE_MAPPING.get(self.status, AlertExpressionValue.NORMAL)

    @property
    def id(self) -> str:
        if "id" not in self.data:
            self.init_uid()
        return self.data["id"]

    @property
    def strategy_id(self) -> str:
        return self.data.get("strategy_id")

    @property
    def severity(self) -> int:
        return self.data["severity"]

    @property
    def top_event(self) -> dict:
        return self.data.get("event")

    @property
    def event_severity(self) -> int:
        if self.top_event:
            return self.top_event["severity"]
        return self.severity

    @property
    def dimensions(self) -> List:
        return self.data.get("dimensions", [])

    @property
    def assign_tags(self):
        return self.data.get("assign_tags")

    @property
    def is_ack_signal(self):
        # 是否为ack_signal
        return (
            ActionSignal.ACK in self.notice_signal and self.data.get("is_ack") and not self.data.get("is_ack_noticed")
        )

    @property
    def notice_signal(self):
        """告警通知信号"""
        if self.strategy:
            return self.strategy.get("notice", {}).get("signal", [])
        return []

    def is_abnormal(self) -> bool:
        """
        是否为异常告警
        """
        return self.status == EventStatus.ABNORMAL

    def is_recovering(self) -> bool:
        return self.is_abnormal and self.get_extra_info("is_recovering")

    def is_no_data(self):
        """
        是否为无数据告警
        """
        for dimension in self.top_event.get("tags", []):
            if NO_DATA_TAG_DIMENSION == dimension["key"]:
                return True
        return False

    def add_dimension(self, key, value, display_key=None, display_value=None):
        self.data.setdefault("dimensions", [])

        data = {
            "key": key,
            "value": value,
            "display_key": key if display_key is None else display_key,
            "display_value": value if display_value is None else display_value,
        }

        for dimension in self.data["dimensions"]:
            if dimension["key"] == key:
                # 如果已经有这个key，则在原来的上面修改
                dimension.update(data)
                return

        # 如果没有这个key则追加
        self.data["dimensions"].append(data)

    def update_key_value_field(self, field_name, new_value: List):
        self.data.setdefault(field_name, [])
        field_value_dict = {item["key"]: item for item in self.data[field_name]}
        new_value_dict = {item["key"]: item for item in new_value}
        field_value_dict.update(new_value_dict)
        self.data[field_name] = list(field_value_dict.values())

    def set_dimensions(self, dimensions):
        self.data["dimensions"] = dimensions

    def is_end(self) -> bool:
        return not self.is_abnormal()

    def should_refresh_db(self) -> bool:
        return self._refresh_db

    def should_send_signal(self) -> bool:
        return self._refresh_db and not self.is_blocked

    def is_status_changed(self) -> bool:
        return self._status_changed

    def is_new(self) -> bool:
        return self._is_new

    def get_process_latency(self):
        """
        获取告警处理延迟
        """
        # 尝试取 access_time
        access_time = None
        try:
            origin_alarm = self.get_extra_info("origin_alarm")
            access_time = origin_alarm["data"]["access_time"]
        except Exception:
            # 上面拿不到时间，有可能是事件类型，那就取 bk_ingest_time
            if self.top_event and self.top_event.get("bk_ingest_time"):
                access_time = self.top_event["bk_ingest_time"]

        if not access_time:
            # 取不到就拉倒，不计算了
            return None

        latency = self.create_time - access_time

        if latency < 0:
            # 小于0的是不正常的，需要去掉
            return None
        return latency

    def get_origin_alarm_dimensions(self):
        origin_alarm = self.get_extra_info("origin_alarm")
        if not origin_alarm:
            # 如果没有原始告警的，直接返回alert的dimensions
            return {dimension["key"]: dimension["value"] for dimension in self.dimensions}
        return origin_alarm["data"]["dimensions"]

    def get_extra_info(self, key, default=None):
        """
        获取额外信息
        """
        return self.data.get("extra_info", {}).get(key, default)

    def update_extra_info(self, key, value):
        """
        更新额外信息
        """
        self._refresh_db = True
        self.data.setdefault("extra_info", {})[key] = value

    def update_agg_dimensions(self, strategy):
        """
        更新dimension的维度排序
        """
        agg_dimensions = []
        for item in strategy.get("items", []):
            for query_config in item["query_configs"]:
                if len(query_config.get("agg_dimension", [])) > len(agg_dimensions):
                    agg_dimensions = query_config["agg_dimension"]
        self.update_extra_info("agg_dimensions", agg_dimensions)

    def update_severity_source(self, source=""):
        self.update_extra_info("severity_source", source)

    def update_severity(self, value):
        if not value:
            return
            # 告警级别变更日志
        self.data["severity"] = value

    def update_labels(self, value):
        self.data["labels"] = value

    def update_assign_tags(self, value: List):
        """
        更新分派的tags信息
        """
        if not value:
            return
        all_tags = {item["key"]: item for item in self.data.get("assign_tags", [])}
        new_tags = {item["key"]: item for item in value}
        all_tags.update(new_tags)
        self.data["assign_tags"] = list(all_tags.values())
        self.update_top_event_tags(value)

    def update_top_event_tags(self, value: List):
        if not self.top_event:
            return
        event_tags = {item["key"]: item for item in self.data["event"]["tags"]}
        additional_tags = {item["key"]: item for item in value}
        event_tags.update(additional_tags)
        self.data["event"]["tags"] = list(event_tags.values())

    def to_document(self, include_all_fields=True):
        data = self.to_dict()
        if not self.is_new() and include_all_fields is False:
            # 如果不是第一次生成，不更新以下字段
            for field in ["assignee", "appointee", "assign_tags", "supervisor", "is_ack_noticed"]:
                # 这些字段在开发过程中由另一个进程去更新，这里必须要忽略掉
                data.pop(field, None)

        if "update_time" not in self.data:
            self.refresh_update_time()

        alert_doc = AlertDocument(**data)
        return alert_doc

    def set_end_status(self, status, op_type, description="", end_time=None, **kwargs):
        """
        将告警设置为终止状态
        """
        if not self.is_abnormal():
            return

        end_time = end_time or int(time.time())
        self.data["status"] = status
        self.data["end_time"] = end_time
        self.update_extra_info("end_description", description)
        self.add_log(
            op_type=op_type,
            description=description,
            time=end_time,
            **kwargs,
        )
        self.refresh_update_time()
        self.clear_next_status()
        self._refresh_db = True
        self._status_changed = True

    def list_log_documents(self):
        log_documents = []
        for log in self.logs:
            log["alert_id"] = self.id
            log_documents.append(AlertLog(**log))
        return log_documents

    def refresh_update_time(self):
        self.data["update_time"] = int(time.time())

    def init_uid(self):
        """
        初始化UID
        """
        if "id" in self.data:
            return

        create_time = self.data.get("create_time")
        uid = AlertUIDManager.generate(create_time)
        create_time = AlertUIDManager.parse_timestamp(uid)
        seq_id = AlertUIDManager.parse_sequence(uid)

        self.data["create_time"] = create_time
        self.data["update_time"] = create_time
        self.data["id"] = uid
        self.data["seq_id"] = seq_id

    def set(self, key, value):
        """
        设置字段值
        """
        self.data[key] = value

    @classmethod
    def from_event(cls, event: Event):
        """
        将事件创建为新的告警对象
        """
        create_time = int(time.time())
        data = {
            "dedupe_md5": event.dedupe_md5,
            "create_time": create_time,
            "update_time": create_time,
            "end_time": None,
            "begin_time": event.time,
            "latest_time": event.time,
            "first_anomaly_time": event.anomaly_time,
            "severity": event.severity,
            "event": event.to_dict(),
            "status": event.status,
            "alert_name": event.alert_name,
            "strategy_id": event.strategy_id,
            "labels": event.extra_info.get("strategy", {}).get("labels", []),
            "dimensions": [],
            # extra_info 和 event["extra_info"] 一样
            "extra_info": event.extra_info or {},
            "is_blocked": False,
        }

        alert = cls(data)
        alert.update_data_id_info(event)

        # 补全维度信息
        for index, key in enumerate(event.dedupe_keys):
            if key in DEFAULT_DEDUPE_FIELDS or key == f"tags.{NO_DATA_TAG_DIMENSION}":
                # 默认去重字段不计入维度
                continue
            alert.add_dimension(
                key, event.get_field(key), event.get_tag_display_key(key), event.get_tag_display_value(key)
            )

        alert.set_next_status(EventStatus.CLOSED, cls.CLOSE_WINDOW_SIZE)
        alert._refresh_db = True
        alert._is_new = True
        alert._status_changed = True
        alert.last_event = event
        alert.add_log(
            op_type=AlertLog.OpType.CREATE,
            event_id=event.id,
            description=event.description,
            time=event.time,
        )
        qos_result = alert.qos_check()
        if qos_result["is_blocked"]:
            alert.update_qos_status(True)
            alert.add_log(
                op_type=AlertLog.OpType.ALERT_QOS,
                event_id=int(time.time()),
                description=qos_result["message"],
                time=int(time.time()),
            )
        return alert

    @classmethod
    def get_from_snapshot(cls, alert_key: AlertKey) -> "Alert":
        """
        从Redis中获取告警快照
        :param alert_key: 告警标识
        """
        alert_json = ALERT_SNAPSHOT_KEY.client.get(alert_key.get_snapshot_key())

        if not alert_json:
            return

        try:
            alert_data = json.loads(alert_json)
            return cls(alert_data)
        except Exception as e:
            logger.warning("load alert failed: %s, origin data: %s", e, alert_json)

    @classmethod
    def get_from_es(cls, alert_id: int) -> "Alert":
        alert_doc = AlertDocument.get(alert_id)
        return cls(alert_doc.to_dict())

    @classmethod
    def get(cls, alert_key: AlertKey) -> "Alert":
        try:
            alert = cls.get_from_snapshot(alert_key)
        except (MysqlDatabaseError, RedisError) as error:
            # 如果从 redis获取缓存抛异常的时候，需要记录一下日志，并且此时一定要从ES获取一次
            logger.exception("load alert(%s) from redis failed: %s", alert_key, str(error))
            alert = None
        if not alert:
            alert = cls.get_from_es(alert_key.alert_id)
        return alert

    @classmethod
    def mget(cls, alert_keys: List[AlertKey]) -> List["Alert"]:
        """
        批量获取告警，优先从Redis快照获取，没有则从ES获取
        :param alert_keys: 告警标识列表
        :return: 告警 Alert 对象 列表
        """
        pipeline = ALERT_SNAPSHOT_KEY.client.pipeline(transaction=False)
        for alert_key in alert_keys:
            pipeline.get(alert_key.get_snapshot_key())
        alerts_snapshot = pipeline.execute()

        results = []

        alert_ids_not_found = []

        for index, alert_json in enumerate(alerts_snapshot):
            if not alert_json:
                alert_ids_not_found.append(alert_keys[index].alert_id)
                continue
            try:
                alert_data = json.loads(alert_json)
                results.append(cls(alert_data))
            except Exception as e:
                logger.warning("load alert failed: %s, origin data: %s", e, alert_json)
                alert_ids_not_found.append(alert_keys[index].alert_id)

        if alert_ids_not_found:
            for alert_doc in AlertDocument.mget(alert_ids_not_found):
                results.append(cls(alert_doc.to_dict()))

        return results

    def save_snapshot(self):
        """
        保存到redis快照
        """
        key = ALERT_SNAPSHOT_KEY.get_key(strategy_id=self.strategy_id or 0, alert_id=self.id)
        ALERT_SNAPSHOT_KEY.client.set(key, json.dumps(self.to_dict()), ALERT_SNAPSHOT_KEY.ttl)

    @property
    def key(self) -> AlertKey:
        return AlertKey(alert_id=self.id, strategy_id=self.strategy_id)

    def qos_check(self):
        """
        告警QOS检测
        """
        message = _("当前告警处理正常")
        qos_threshold = settings.QOS_ALERT_THRESHOLD
        if qos_threshold == 0 or not self.is_blocked and not self.is_new():
            # 如果不是新的，并且未被熔断，直接返回
            # 如果当前设置阈值为0表示没有QOS，直接返回
            return {"is_blocked": self.is_blocked, "message": message}

        qos_counter = ALERT_BUILD_QOS_COUNTER
        qos_threshold = {"threshold": qos_threshold, "window": settings.QOS_ALERT_WINDOW}

        signal = "no_data" if self.is_no_data() else EventStatus.ABNORMAL

        # 旧的告警数据需要判断当前是否熔断已经结束所以不计入熔断
        is_blocked, current_count = self.qos_calc(
            signal=signal, qos_counter=qos_counter, threshold=qos_threshold, need_incr=self.is_new()
        )
        if self.is_new():
            if is_blocked:
                # 当被流控的时候，还是上报策略, 没有策略的，按照告警名称来
                metrics.Alert_QOS_COUNT.labels(strategy_id=self.strategy_id or self.alert_name, is_blocked="1").inc()
            metrics.Alert_QOS_COUNT.labels(strategy_id=metrics.TOTAL_TAG, is_blocked="1" if is_blocked else "0").inc()

        if is_blocked:
            # 被熔断，返回熔断日志
            message = _("告警所属策略在当前窗口期（{window} min）内产生的告警数量({current_count})个，已大于QOS阈值({threshold})，当前告警被流控").format(
                window=qos_threshold["window"] // 60, current_count=current_count, threshold=qos_threshold["threshold"]
            )
        else:
            # 不满足熔断条件了
            message = _(
                "告警所属策略在当前窗口期（{window} min）内产生的告警数量({current_count})个，低于QOS阈值({threshold}), 告警流控已解除，将产生新的告警"
            ).format(
                window=qos_threshold["window"] // 60, current_count=current_count, threshold=qos_threshold["threshold"]
            )
        return {"is_blocked": is_blocked, "message": message}

    def qos_calc(self, signal, qos_counter=COMPOSITE_QOS_COUNTER, threshold=None, need_incr=True):
        """
        :param signal: 信号
        :param qos_counter: qos计数器
        :param threshold: QOS规则
        :param need_incr: 是否需要计数
        :return:
        """
        # 限流计数器，监控的告警以策略ID，信号，告警级别作为维度
        qos_dimension = dict(strategy_id=self.strategy_id or 0, signal=signal, severity=self.severity)
        alert_md5 = ""
        if not self.strategy_id:
            # 第三方的告警以业务ID，告警名称，信号，告警级别作为维度
            alert_md5 = count_md5(
                dict(
                    bk_biz_id=self.top_event.get("bk_biz_id", 0),
                    alert_name=self.alert_name,
                    signal=signal,
                    severity=self.severity,
                )
            )
        qos_dimension.update({"alert_md5": alert_md5})
        qos_counter_key = qos_counter.get_key(**qos_dimension)
        client = qos_counter.client
        if threshold is None:
            threshold = {"threshold": settings.QOS_DROP_ACTION_THRESHOLD, "window": settings.QOS_DROP_ACTION_WINDOW}

        if threshold["threshold"] == 0:
            # 如果阈值为0 ，默认不做QOS处理，直接返回
            return False, 0
        qos_window = threshold["window"]
        current_count = 1
        if need_incr:
            result = client.set(qos_counter_key, current_count, nx=True, ex=qos_window)
            if not result:
                current_count = client.incr(qos_counter_key)
                # 这里client对应的是redis-py的Redis对象，对ttl返回值错了一层处理，小于0的统一设置为None
                ttl = client.ttl(qos_counter_key)
                if ttl is None or ttl < 0:
                    client.expire(qos_counter_key, qos_window)
        else:
            current_count = int(client.get(qos_counter_key) or 0)
        return current_count > threshold["threshold"], current_count

    @staticmethod
    def create_qos_log(alerts: List[str], total_count, qos_actions):
        return AlertLog(
            op_type=AlertLog.OpType.ACTION,
            alert_id=alerts,
            description=_("告警所属策略在当前窗口期（%s min）内产生的处理次数为%s次，已超过QOS阈值(%s)，当前告警的(%s)个处理被抑制")
            % (
                settings.QOS_DROP_ACTION_WINDOW // 60,
                total_count,
                settings.QOS_DROP_ACTION_THRESHOLD,
                qos_actions,
            ),
            time=int(time.time()),
            create_time=int(time.time()),
            event_id=int(time.time()),
        )


class AlertUIDManager:
    """
    告警全局唯一ID生成器
    """

    # 用来存储序列号的 redis key
    SEQUENCE_REDIS_KEY = ALERT_UUID_SEQUENCE

    # 序列号池
    sequence_pool = set()

    @classmethod
    def clear_pool(cls):
        cls.sequence_pool.clear()

    @classmethod
    def preload_pool(cls, count=1):
        """
        将序列号从Redis预读取到本地内存
        """
        poll_size = len(cls.sequence_pool)
        if poll_size >= count:
            # 如果序列号池的大小大于需求量，则无需处理
            return

        # 如果序列号池小于需求量，则补充拉取对应数量的序列号
        fetch_size = count - poll_size
        max_seq = cls.SEQUENCE_REDIS_KEY.client.incrby(cls.SEQUENCE_REDIS_KEY.get_key(), fetch_size)

        cluster = get_cluster()
        if cluster.is_default():
            cls.sequence_pool.update(range(max_seq, max_seq - fetch_size, -1))
        else:
            cls.sequence_pool.update(f"{i}{cluster.code}" for i in range(max_seq, max_seq - fetch_size, -1))

    @classmethod
    def pop_sequence(cls) -> int:
        if not cls.sequence_pool:
            # 如果号池为空，则预读一波
            cls.preload_pool()
        return cls.sequence_pool.pop()

    @classmethod
    def generate(cls, timestamp: int = None) -> str:
        """
        生成 uuid
        格式：4 bytes 时间戳 + 4 bytes 自增序列号 = 8 bytes
        例如：1619775685, 1 => 608bd0c500000001
        """
        if not timestamp:
            timestamp = int(time.time())

        timestamp = str(timestamp)[:10]
        sequence = cls.pop_sequence()

        return f"{timestamp:0>10}{sequence}"

    @classmethod
    def parse_timestamp(cls, uuid: str) -> int:
        """
        从 UUID 反解时间戳
        """
        return AlertDocument.parse_timestamp_by_id(uuid)

    @classmethod
    def parse_sequence(cls, uuid: str) -> int:
        """
        从 UUID 反解时间戳
        """
        return AlertDocument.parse_sequence_by_id(uuid)


class AlertCache:
    # todo 下面两个可以合并
    @staticmethod
    def save_alert_to_cache(alerts: List[Alert]):
        alerts_to_saved = {}
        for alert in alerts:
            current_alert = alerts_to_saved.get(alert.dedupe_md5)
            if not current_alert or alert.create_time > current_alert.create_time:
                # 哪些告警需要刷新到缓存呢？
                # 1. 从未出现过的维度
                # 2. 维度已经出现过，但告警的创建时间更加新
                alerts_to_saved[alert.dedupe_md5] = alert

        update_count = 0
        finished_count = 0
        # 通过 pipeline 批量更新告警，由于这些告警维度都各不相同，更新的先后顺序就都无所谓了
        pipeline = ALERT_DEDUPE_CONTENT_KEY.client.pipeline(transaction=False)
        for alert in alerts_to_saved.values():
            key = ALERT_DEDUPE_CONTENT_KEY.get_key(strategy_id=alert.strategy_id or 0, dedupe_md5=alert.dedupe_md5)
            if alert.is_end():
                # 如果告警已经结束，不做删除，更新告警内容
                finished_count += 1
            else:
                # 如果告警未结束就更新
                update_count += 1
            pipeline.set(key, json.dumps(alert.to_dict()), ALERT_DEDUPE_CONTENT_KEY.ttl)
        pipeline.execute()
        return update_count, finished_count

    @staticmethod
    def save_alert_snapshot(alerts: List[Alert]):
        if not alerts:
            return 0

        pipeline = ALERT_SNAPSHOT_KEY.client.pipeline(transaction=False)
        snapshot_count = 0
        for alert in alerts:
            # 已经结束的告警保存快照备用
            key = ALERT_SNAPSHOT_KEY.get_key(strategy_id=alert.strategy_id or 0, alert_id=alert.id)
            pipeline.set(key, json.dumps(alert.to_dict()), ALERT_SNAPSHOT_KEY.ttl)
            snapshot_count += 1

        pipeline.execute()
        return snapshot_count
