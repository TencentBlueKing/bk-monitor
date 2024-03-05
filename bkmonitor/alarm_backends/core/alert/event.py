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
import time

from alarm_backends.constants import DEFAULT_DEDUPE_FIELDS
from bkmonitor.documents import EventDocument
from bkmonitor.utils.common_utils import count_md5
from constants.alert import EventStatus, EventTargetType
from constants.data_source import LABEL_ORDER_LIST, DataTypeLabel, ResultTableLabelObj


class Event:
    # 距今多少秒的事件被认为是过期事件
    # 这些事件仅进行记录，而不会进行告警判断
    DEFAULT_EXPIRED_SECONDS = 24 * 60 * 60

    # 事件默认级别：轻微
    DEFAULT_SEVERITY = 3

    FIELDS = (
        "id",
        "event_id",
        "plugin_id",
        "strategy_id",
        "alert_name",
        "description",
        "severity",
        "data_type",
        "tags",
        "target_type",
        "target",
        "assignee",
        "status",
        "metric",
        "category",
        "dedupe_keys",
        "dedupe_md5",
        "time",
        "anomaly_time",
        "bk_ingest_time",
        "bk_clean_time",
        "create_time",
        "bk_biz_id",
        "ip",
        "bk_cloud_id",
        "bk_service_instance_id",
        "bk_host_id",
        "ipv6",
        "bk_topo_node",
        "extra_info",
    )

    def __init__(self, data: dict, do_clean=True):
        self.data = data
        # 用于去重的标签
        self._dedupe_values = []

        self._dropped = False

        if do_clean:
            self.clean()

    def clean(self):
        """
        处理单条事件
        """
        self.data = self.remove_none_fields()
        self.data["create_time"] = int(time.time())
        self.data["target_type"] = self._clean_target_type()
        self.data["target"] = self._clean_target()
        self.data["metric"] = self._clean_metric()
        self.data["data_type"] = self._clean_data_type()
        self.data["bk_biz_id"] = self._clean_bk_biz_id()
        self.data["dedupe_keys"] = self._clean_dedupe_keys()
        self.data["status"] = self._clean_status()
        self.data["severity"] = self._clean_severity()
        self.data["tags"] = self._clean_tags()
        self.data["time"] = self._clean_time()
        self.data["category"] = self._clean_category()
        self.data["id"] = self._clean_uid()

    def remove_none_fields(self):
        """
        移除空字段
        """
        return {key: value for key, value in self.data.items() if value is not None}

    def _clean_metric(self):
        metric = self.data.get("metric")
        if not metric:
            return []
        if isinstance(metric, str):
            return [metric]
        return metric

    def _clean_data_type(self):
        data_type = self.data.get("data_type", "").lower()
        if data_type in [DataTypeLabel.TIME_SERIES, DataTypeLabel.LOG]:
            return data_type
        return DataTypeLabel.EVENT

    def _clean_bk_biz_id(self):
        return self.data.get("bk_biz_id")

    def _clean_tags(self):
        tags = self.data.get("tags", [])
        cleaned_tags = []
        for tag in tags:
            if isinstance(tag["value"], dict):
                value = json.dumps(tag["value"])
            elif isinstance(tag["value"], (list, tuple)):
                value = [json.dumps(v) if isinstance(v, (dict, list)) else v for v in tag["value"]]
            else:
                value = tag["value"]
            cleaned_tag = {
                "key": str(tag["key"]),
                "value": value,
            }

            if "display_key" in tag:
                cleaned_tag["display_key"] = tag["display_key"]
            if "display_value" in tag:
                cleaned_tag["display_value"] = tag["display_value"]

            cleaned_tags.append(cleaned_tag)
        return cleaned_tags

    def _clean_target(self):
        return self.data.get("target")

    def _clean_category(self):
        category = self.data.get("category", "").lower()
        if category in LABEL_ORDER_LIST:
            return category
        return ResultTableLabelObj.OthersObj.other_rt

    def _clean_target_type(self):
        target_type = self.data.get("target_type") or ""
        if not target_type:
            return EventTargetType.EMPTY
        if target_type.upper() in [EventTargetType.TOPO, EventTargetType.SERVICE, EventTargetType.HOST]:
            return target_type.upper()
        # 如果都不匹配内置的目标类型，则使用事件提供的类型
        return target_type

    def _clean_dedupe_keys(self):
        default_dedupe_keys = copy.deepcopy(DEFAULT_DEDUPE_FIELDS)
        if self.data.get("strategy_id"):
            # 如果有策略ID，就用策略ID，不用告警名称。这是监控特有逻辑
            default_dedupe_keys.remove("alert_name")
        else:
            default_dedupe_keys.remove("strategy_id")

        dedupe_keys = self.data.get("dedupe_keys", [])
        if not isinstance(dedupe_keys, list):
            return default_dedupe_keys

        for key in dedupe_keys:
            if key in default_dedupe_keys:
                continue
            default_dedupe_keys.append(key)
        return default_dedupe_keys

    def _clean_time(self) -> int:
        if "time" in self.data:
            return self.data["time"]
        # 如果没有提供 time 字段，则使用 bk_ingest_time
        return self.data["bk_ingest_time"]

    def _clean_severity(self) -> int:
        severity = self.data.get("severity")
        try:
            severity = int(severity)
            # 将范围锁定在 1 ~ 3
            severity = min(3, severity)
            severity = max(1, severity)
            return severity
        except Exception:
            return self.DEFAULT_SEVERITY

    def _clean_status(self) -> str:
        value = self.data.get("status", "").upper()
        if value in [EventStatus.CLOSED, EventStatus.RECOVERED]:
            return value
        return EventStatus.ABNORMAL

    def cal_dedupe_md5(self):
        self._dedupe_values = []
        for key in self.dedupe_keys:
            value = self.get_field(key)
            self._dedupe_values.append(value)

        self.data["dedupe_md5"] = count_md5(self._dedupe_values)

    def _clean_uid(self) -> str:
        unique_fields = [self.data["plugin_id"], self.data["event_id"], self.data["status"], self.data["time"]]
        return count_md5(unique_fields)

    def get_field(self, key):
        """
        获取具体字段值，支持访问tags
        """
        if key.startswith("tags."):
            # 取 tag 中的字段作为 key
            return self.get_tags_value(key[5:])
        # 取外层字段作为 key
        return self.data.get(key)

    def get_tags_value(self, key: str):
        if key.startswith("tags."):
            key = key[len("tags.") :]
        return self.tags_dict.get(key, {}).get("value")

    def get_tag_display_key(self, key):
        if key.startswith("tags."):
            key = key[len("tags.") :]
        return self.tags_dict.get(key, {}).get("display_key")

    def get_tag_display_value(self, key):
        if key.startswith("tags."):
            key = key[len("tags.") :]
        return self.tags_dict.get(key, {}).get("display_value")

    def set(self, key, value):
        """
        设置字段值
        """
        self.data[key] = value

    @property
    def tags_dict(self):
        if not hasattr(self, "_tags_dict"):
            self._tags_dict = {tag["key"]: tag for tag in self.data.get("tags", []) if "key" in tag}
        return self._tags_dict

    def to_document(self):
        data = self.to_dict()
        return EventDocument(**data)

    def to_dict(self) -> dict:
        data = {}
        for field in self.FIELDS:
            value = getattr(self, field, self.data.get(field))
            if value is not None:
                data[field] = value
        return data

    def to_flatten_dict(self) -> dict:
        """
        转换为扁平字典，将 tags.xxx 作为一级字段
        """
        data = self.to_dict()
        tags = data.pop("tags", [])
        for tag in tags:
            data[f"tags.{tag['key']}"] = tag["value"]
        return data

    def is_dropped(self) -> bool:
        """
        当前事件是否被丢弃
        """
        return self._dropped

    def drop(self):
        """
        丢弃当前事件
        """
        self._dropped = True

    # ===============
    # 事件属性
    # ===============
    @property
    def id(self) -> str:
        return self.data["id"]

    @property
    def event_id(self) -> str:
        return self.data["event_id"]

    @property
    def plugin_id(self) -> str:
        return self.data["plugin_id"]

    @property
    def alert_name(self) -> str:
        return self.data["alert_name"]

    @property
    def strategy_id(self) -> str:
        return self.data.get("strategy_id")

    @property
    def description(self) -> str:
        return self.data.get("description")

    @property
    def category(self) -> str:
        return self.data.get("category")

    @property
    def dedupe_keys(self) -> str:
        return self.data["dedupe_keys"]

    @property
    def dedupe_md5(self) -> str:
        if "dedupe_md5" not in self.data:
            self.cal_dedupe_md5()
        return self.data["dedupe_md5"]

    @property
    def status(self) -> str:
        return self.data["status"]

    @property
    def time(self) -> int:
        return self.data["time"]

    @property
    def anomaly_time(self) -> int:
        return self.data.get("anomaly_time", self.time)

    @property
    def severity(self) -> int:
        return self.data["severity"]

    @property
    def tags(self) -> list:
        return self.data["tags"]

    @property
    def dedupe_values(self) -> list:
        if "dedupe_md5" not in self.data:
            self.cal_dedupe_md5()
        return self._dedupe_values

    @property
    def target_type(self) -> str:
        return self.data.get("target_type", "")

    @property
    def target(self) -> str:
        return self.data.get("target", "")

    @property
    def bk_biz_id(self) -> str:
        return self.data["bk_biz_id"]

    @property
    def extra_info(self):
        return self.data.get("extra_info", {})

    @property
    def data_id(self):
        return self.data.get("data_id", 0)

    @property
    def topic(self):
        return self.data.get("topic", 0)

    @property
    def access_time(self):
        origin_alarm = self.extra_info.get("origin_alarm", {})
        return origin_alarm.get("data", {}).get("access_time", self.time)

    def is_abnormal(self) -> bool:
        """
        是否为异常事件
        """
        return self.status == EventStatus.ABNORMAL

    def is_expired(self, expire_time: int = None):
        """
        判断当前事件是否过期
        """
        default_expire_time = int(time.time() - self.DEFAULT_EXPIRED_SECONDS)
        if not expire_time:
            # 若没有提供过期时间，则默认一天前的事件属于过期
            expire_time = default_expire_time
        else:
            # 若提供的过期时间大于一天，则仍然使用一天作为过期时间
            expire_time = max(expire_time, default_expire_time)
        return self.access_time < expire_time

    def get_process_latency(self):
        """
        获取告警处理延迟
        """
        current_time = time.time()
        try:
            # 尝试取 access_time
            origin_alarm = self.extra_info["origin_alarm"]
            return {
                "access_latency": current_time - origin_alarm["data"]["access_time"],
                "trigger_latency": current_time - origin_alarm["trigger_time"],
            }
        except Exception:
            # 取不到就拉倒，不计算了
            return
