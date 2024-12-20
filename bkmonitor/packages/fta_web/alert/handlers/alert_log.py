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
from typing import List

from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from bkmonitor.documents import AlertDocument, AlertLog
from bkmonitor.models import NO_DATA_TAG_DIMENSION
from bkmonitor.utils.time_tools import utc2datetime
from constants.alert import EVENT_SEVERITY_DICT, EventSeverity


class AlertLogHandler:
    OP_TYPE_DISPLAY = {
        AlertLog.OpType.CREATE: _lazy("告警产生"),
        AlertLog.OpType.CONVERGE: _lazy("告警收敛"),
        AlertLog.OpType.RECOVER: _lazy("告警恢复"),
        AlertLog.OpType.CLOSE: _lazy("告警关闭"),
        AlertLog.OpType.RECOVERING: _lazy("告警恢复中"),
        AlertLog.OpType.DELAY_RECOVER: _lazy("延迟恢复"),
        AlertLog.OpType.ABORT_RECOVER: _lazy("中断恢复"),
        AlertLog.OpType.SYSTEM_RECOVER: _lazy("系统恢复"),
        AlertLog.OpType.SYSTEM_CLOSE: _lazy("系统关闭"),
        AlertLog.OpType.ACK: _lazy("告警确认"),
        AlertLog.OpType.SEVERITY_UP: _lazy("告警级别调整"),
        AlertLog.OpType.ACTION: _lazy("处理动作"),
        AlertLog.OpType.ALERT_QOS: _lazy("告警流控"),
        AlertLog.OpType.EVENT_DROP: _lazy("事件忽略"),
    }

    def __init__(self, alert_id: str):
        self.alert = AlertDocument.get(alert_id)
        self.log_records = []

    def search(self, operate_list: List = None, offset: int = None, limit: int = None):
        self.log_records = []

        search_object = (
            AlertLog.search(all_indices=True)
            .params(ignore_unavailable=True, preserve_order=True)
            .filter("term", alert_id=self.alert.id)
            .sort("-create_time", "op_type", "-_doc")
        )

        if operate_list:
            search_object = search_object.filter("terms", op_type=operate_list)

        if offset:
            search_object = search_object.filter("range", create_time={"lt": offset})

        for hit in search_object.scan():
            if limit and len(self.log_records) >= limit:
                # 如果需要返回的记录已经大于limit，那么还需要判断以下情况
                last_record = self.log_records[-1]
                if (
                    last_record["operate"] != AlertLog.OpType.CONVERGE or hit.op_type != AlertLog.OpType.CONVERGE
                ) or hit.create_time < last_record["offset"]:
                    # 1. 如果下一条记录还是收敛类型，需要将剩余的收敛记录合并完
                    # 2. 如果下一条记录的时间戳与上一条记录相同，也要继续处理
                    break

            self.handle_hit(hit)
        return self.log_records

    def handle_hit(self, hit):
        content_handlers = {
            AlertLog.OpType.CREATE: self.add_record_create,
            AlertLog.OpType.CONVERGE: self.add_record_converge,
            AlertLog.OpType.RECOVER: self.add_record_recover,
            AlertLog.OpType.CLOSE: self.add_record_close,
            AlertLog.OpType.DELAY_RECOVER: self.add_record_delay_recover,
            AlertLog.OpType.ABORT_RECOVER: self.add_record_abort_recover,
            AlertLog.OpType.SYSTEM_RECOVER: self.add_record_system_recover,
            AlertLog.OpType.SYSTEM_CLOSE: self.add_record_system_close,
            AlertLog.OpType.ACK: self.add_record_ack,
            AlertLog.OpType.SEVERITY_UP: self.add_record_severity_up,
            AlertLog.OpType.ACTION: self.add_record_action,
            AlertLog.OpType.ALERT_QOS: self.add_record_action,
            AlertLog.OpType.EVENT_DROP: self.add_record_event_drop,
        }

        record = {
            "action_id": hit.meta.id,
            "time": utc2datetime(hit.create_time),
            "operate": hit.op_type,
            "operate_display": self.OP_TYPE_DISPLAY.get(hit.op_type, hit.op_type),
            "offset": hit.create_time,
        }

        op_type = hit.op_type

        if op_type in content_handlers:
            content_handlers[op_type](AlertLog(**hit.to_dict()), record)
        else:
            self.add_record_default(AlertLog(**hit.to_dict()), record)

    def add_record_create(self, hit, record):
        """
        告警产生
        """
        contents = [hit.description]
        source_time = utc2datetime(self.alert.begin_time)

        if self.alert.strategy and self.alert.strategy["items"][0]["algorithms"]:
            item = self.alert.strategy["items"][0]
            detect = self.alert.strategy["detects"][0]
            if NO_DATA_TAG_DIMENSION in self.alert.origin_alarm["data"]["dimensions"]:
                continuous = item["no_data_config"]["continuous"]
                contents.append(_(" 达到了触发告警条件（数据连续丢失{}个周期）").format(continuous))
            else:
                trigger_config = detect["trigger_config"]
                contents.append(
                    _(" 达到了触发告警条件（{}周期内满足{}次检测算法）").format(trigger_config["check_window"], trigger_config["count"])
                )
        record.update({"source_time": source_time, "index": 0, "contents": contents})
        self.log_records.append(record)

    def add_record_recover(self, hit, record):
        record.update(
            {
                "contents": [hit.description],
            }
        )
        self.log_records.append(record)

    def add_record_delay_recover(self, hit, record):
        record.update(
            {"contents": [hit.description, _("根据系统配置，告警将于 {} 延时恢复").format(utc2datetime(hit.next_status_time))]}
        )
        self.log_records.append(record)

    def add_record_abort_recover(self, hit, record):
        if hit.description:
            record.update({"contents": [hit.description]})
        else:
            record.update({"contents": [_("在延时恢复的时间窗口收到了新的异常事件，延时恢复被中断")]})
        self.log_records.append(record)

    def add_record_system_recover(self, hit, record):
        record.update({"contents": [_("延时恢复时间窗口结束，告警已恢复")]})
        self.log_records.append(record)

    def add_record_ack(self, hit, record):
        if hit.description:
            contents = [_("{}确认了该告警事件并备注：").format(hit.operator), hit.description]
        else:
            contents = [_("{}确认了该告警事件").format(hit.operator)]
        record.update({"contents": contents})
        self.log_records.append(record)

    def add_record_close(self, hit, record):
        record.update(
            {
                "contents": [hit.description],
            }
        )
        self.log_records.append(record)

    def add_record_default(self, hit, record):
        record.update(
            {
                "contents": [hit.description],
            }
        )
        self.log_records.append(record)

    def add_record_system_close(self, hit, record):
        record.update(
            {
                "contents": [_("长时间未收到新的异常事件，系统关闭告警")],
            }
        )
        self.log_records.append(record)

    def add_record_event_drop(self, hit, record):
        contents = [hit.description, _("告警级别【{}】低于当前告警触发级别，系统已忽略").format(EventSeverity.get_display_name(hit.severity))]
        self.record_collect(hit, record, AlertLog.OpType.EVENT_DROP, contents)

    def add_record_converge(self, hit, record):
        self.record_collect(hit, record)

    def record_collect(self, hit, record, op_type=AlertLog.OpType.CONVERGE, contents=None):
        """
        汇总部分收敛记录和告警事件丢弃记录
        """

        record.update(
            {
                "index": 0,
                "contents": contents if contents else [hit.description],
                "time": utc2datetime(hit.create_time),
                "begin_time": utc2datetime(hit.create_time),
                "is_multiple": False,
                "source_time": utc2datetime(hit.time),
                "begin_source_time": utc2datetime(hit.time),
                "source_timestamp": hit.time,
                "begin_source_timestamp": hit.time,
                "count": 1,
                "offset": hit.create_time,
            }
        )

        should_create = False
        if not self.log_records:
            should_create = True
        elif self.log_records[-1]["operate"] != op_type:
            # 如果前一条记录不是收敛类型，就增加一条新的
            should_create = True
        elif len(self.log_records) == 1:
            # 如果只有一条流水，且上一条是收敛，则让上一条显示详情，然后另开一条新的做收敛
            should_create = True
        elif self.log_records[-2]["operate"] != op_type:
            # 如果有两条以上的流水，且上条是收敛，上上条不是收敛，也需要另开一条新的做收敛
            should_create = True
        if should_create:
            self.log_records.append(record)
        else:
            # 如果前一条记录是收敛类型，就在原来的基础上更新
            last_record = self.log_records[-1]
            last_record["time"] = max(record["time"], last_record["time"])
            last_record["begin_time"] = min(record["begin_time"], last_record["begin_time"])
            last_record["source_time"] = max(record["source_time"], last_record["source_time"])
            last_record["begin_source_time"] = min(record["begin_source_time"], last_record["begin_source_time"])
            last_record["source_timestamp"] = max(record["source_timestamp"], last_record["source_timestamp"])
            last_record["begin_source_timestamp"] = min(
                record["begin_source_timestamp"], last_record["begin_source_timestamp"]
            )
            last_record["is_multiple"] = True
            last_record["count"] += 1
            last_record["offset"] = min(record["offset"], last_record["offset"])

    def add_record_severity_up(self, hit, record):
        record.update(
            {
                "contents": [_("收到了更高级别的事件，告警级别上升为：{}").format(EVENT_SEVERITY_DICT.get(hit.severity, hit.severity))],
            }
        )
        self.log_records.append(record)

    def add_record_action(self, hit, record):
        data = hit.to_dict()
        try:
            content = json.loads(data.get("description", ""))
        except BaseException:
            content = {"text": data.get("description", "")}
        record.update(
            {
                "contents": [content.get("text", "")],
                "action_plugin_type": content.get("action_plugin_type"),
            }
        )
        # router_info 供前端拼接路由，拼接好的 url 用于第三方跳转
        if "router_info" in content:
            record["router_info"] = content["router_info"]
        else:
            record["url"] = content.get("url", "")

        record.update({"action_id": hit["event_id"]})
        self.log_records.append(record)
