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
import datetime
from typing import Any, Dict, List, Union

from django.db.models import Q
from django.utils.translation import ugettext as _

from bkm_space.errors import NoRelatedResourceError
from bkmonitor.commons.tools import is_ipv6_biz
from bkmonitor.data_source import load_data_source
from bkmonitor.models import StrategyModel
from bkmonitor.utils.common_utils import host_key
from bkmonitor.utils.thread_backend import InheritParentThread, run_threads
from bkmonitor.utils.time_tools import hms_string, localtime, now
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import api, resource
from monitor_web.models import CollectConfigMeta
from monitor_web.models.uptime_check import UptimeCheckNode, UptimeCheckTask
from monitor_web.uptime_check.constants import BEAT_STATUS


class MonitorStatus(object):
    UNSET = "unset"
    SLIGHT = "slight"
    SERIOUS = "serious"
    NORMAL = "normal"


class BaseMonitorInfo(object):
    SCENARIO = []

    @classmethod
    def check_alert(cls, alert):
        """校验event是否属于当前模块"""
        scenario = alert.get("extra_info", {}).get("strategy", {}).get("scenario", "")
        return scenario in cls.SCENARIO

    def __init__(self, bk_biz_id, alerts):
        self.bk_biz_id = bk_biz_id
        self.alerts = alerts
        self.alert_count = len(alerts)
        self.status = self.get_status()

    def get_status(self):
        """获取模块状态：未接入，无告警，有告警"""
        raise NotImplementedError

    @property
    def get_abnormal_status(self):
        """获取告警是属于普通告警，还是严重告警状态"""
        for alert in self.alerts:
            if alert["severity"] == 1:
                return MonitorStatus.SERIOUS

        # 轻微告警
        return MonitorStatus.SLIGHT

    def get_info(self):
        status_mapping = {
            MonitorStatus.UNSET: self.no_access_info,
            MonitorStatus.SLIGHT: self.abnormal_info,
            MonitorStatus.SERIOUS: self.abnormal_info,
            MonitorStatus.NORMAL: self.normal_info,
        }
        info = status_mapping[self.status]()
        info.update(status=self.status)
        return info

    def no_access_info(self):
        """
        获取未接入时的数据
        :return:
        """
        raise NotImplementedError

    def normal_info(self):
        """
        获取无告警时的数据
        :return:
        """
        raise NotImplementedError

    def abnormal_info(self):
        """
        获取有告警时的数据
        :return:
        """
        raise NotImplementedError

    @staticmethod
    def get_anomaly_msg(alert):
        return alert["event"].get("description", "")


class ServiceMonitorInfo(BaseMonitorInfo):
    SCENARIO = ["component", "service_module"]

    def get_status(self):
        """获取模块状态：未接入，无告警，有告警"""
        if self.alert_count > 0:
            return self.get_abnormal_status

        has_collect = CollectConfigMeta.objects.filter(label__in=self.SCENARIO, bk_biz_id=self.bk_biz_id).exists()
        if has_collect > 0:
            # 无告警
            return MonitorStatus.NORMAL

        # 未接入
        return MonitorStatus.UNSET

    def no_access_info(self):
        return {"step": 1}

    def normal_info(self):
        strategy_count = StrategyModel.objects.filter(bk_biz_id=self.bk_biz_id, scenario__in=self.SCENARIO).count()
        return {"no_monitor_target": strategy_count > 0}

    def abnormal_info(self):
        self.alerts.sort(key=lambda x: x["severity"])
        now_time = now()
        search_time = now_time + datetime.timedelta(minutes=-10)
        strategies = StrategyModel.objects.filter(
            bk_biz_id=self.bk_biz_id, update_time__gte=search_time, scenario__in=self.SCENARIO
        )

        abnormal_events = []
        for alert in self.alerts:
            abnormal_events.append(
                {
                    "event_id": alert["id"],
                    "content": self.get_anomaly_msg(alert),
                    "strategy_name": alert["alert_name"],
                    "level": alert["severity"],
                }
            )

        operations = []
        for s in strategies:
            total_seconds = (now_time - s.update_time).total_seconds()
            time_str = hms_string(
                total_seconds, day_unit=_("天"), hour_unit=_("小时"), minute_unit=_("分钟"), second_unit=_("秒")
            )
            operations.append(_("{}前{}修改了告警策略：{}").format(time_str, s.update_user, s.name))

        return {"abnormal_events": abnormal_events, "operations": operations}


class ProcessMonitorInfo(BaseMonitorInfo):
    SCENARIO = ["host_process"]

    def get_status(self):
        if self.alert_count > 0:
            return self.get_abnormal_status
        try:
            api_result = api.cmdb.get_process(bk_biz_id=self.bk_biz_id)
        except NoRelatedResourceError:
            # 如果空间未关联cc资源抛出异常，则视为未接入
            return MonitorStatus.UNSET
        # 如果cmdb没有配置进程视为未接入

        if len(api_result) > 0:
            return MonitorStatus.NORMAL

        return MonitorStatus.UNSET

    def no_access_info(self):
        return {"step": 1}

    def abnormal_info(self):
        abnormal_events = []
        level_count = {
            1: 0,
            2: 0,
            3: 0,
        }
        for alert in self.alerts:
            if sum(level_count.values()) < 8:
                try:
                    items = alert["extra_info"]["strategy"]["items"]
                    if alert["extra_info"]["origin_alarm"]["data"]["dimensions"].get("bk_target_ip", ""):
                        ip = alert["extra_info"]["origin_alarm"]["data"]["dimensions"]["bk_target_ip"]
                    else:
                        ip = alert["extra_info"]["origin_alarm"]["data"]["dimensions"]["ip"]
                except KeyError:
                    continue

                process = items[0]["name"]
                anomaly_message = self.get_anomaly_msg(alert)
                content = _("主机“{}”的{}{}").format(ip, process, anomaly_message)
                abnormal_events.append(
                    {
                        "event_id": alert["id"],
                        "content": content,
                        "type": "serious" if alert["severity"] == 1 else "warning",
                    }
                )

            level_count[alert["severity"]] += 1

        return {
            "abnormal_events": abnormal_events,
            "serious_count": level_count[1],
            "warning_count": level_count[2],
            "notice_count": level_count[3],
            "has_more": self.alert_count > 8,
        }

    def normal_info(self):
        strategy_count = StrategyModel.objects.filter(bk_biz_id=self.bk_biz_id, scenario=self.SCENARIO).count()
        return {"has_monitor": strategy_count > 0}


class OsMonitorInfo(BaseMonitorInfo):
    SCENARIO = ["os"]

    high_risk_label = {
        "bk_monitor.system.load.load5": _("5分钟平均负载"),
        "bk_monitor.system.cpu_summary.usage": _("CPU总使用率"),
        "bk_monitor.system.mem.pct_used": _("应用内存使用占比"),
        "bk_monitor.system.disk.in_use": _("磁盘使用率"),
        "bk_monitor.disk-readonly-gse": _("磁盘只读"),
        "bk_monitor.disk-full-gse": _("磁盘写满"),
        "bk_monitor.ping-gse": _("PING不可达"),
        "bk_monitor.os_restart": _("系统重新启动"),
    }

    def get_status(self):
        if self.alert_count > 0:
            return self.get_abnormal_status

        # 判断CPU使用率，如果有则视为接入了
        data_source = load_data_source(DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES)(
            table="system.cpu_summary",
            metrics=[{"field": "usage", "method": "COUNT", "alias": "count"}],
            filter_dict={"time__gt": "5m", "bk_biz_id": str(self.bk_biz_id)},
        )
        api_result = data_source.query_data(limit=1)
        return MonitorStatus.NORMAL if api_result and api_result[0]["count"] > 0 else MonitorStatus.UNSET

    def no_access_info(self):
        return {
            "step": 1,
        }

    def normal_info(self):
        strategy_count = StrategyModel.objects.filter(bk_biz_id=self.bk_biz_id, scenario__in=self.SCENARIO).count()
        return {"strategy_count": strategy_count}

    @classmethod
    def check_alert(cls, alert) -> bool:
        result = super().check_alert(alert)
        if not result:
            return False
        # 仅允许存在主机维度的告警
        origin_alarm = alert["extra_info"]["origin_alarm"]
        return "bk_host_id" in origin_alarm["dimension_translation"] or (
            {"bk_target_ip", "ip"} & set(origin_alarm["data"]["dimensions"].keys())
        )

    def abnormal_info(self):
        serious_count = 0
        temp_count = 0

        high_risk = []
        other = []
        for alert in self.alerts:
            metric_ids = []
            try:
                query_configs = alert["extra_info"]["strategy"]["items"][0]["query_configs"]
            except KeyError:
                continue
            for query_config in query_configs:
                metric_ids.append(query_config["metric_id"])
            if temp_count < 5:
                origin_alarm = alert["extra_info"]["origin_alarm"]

                if "bk_host_id" in origin_alarm["dimension_translation"]:
                    ip = origin_alarm["dimension_translation"]["bk_host_id"]["display_value"]
                elif origin_alarm["data"]["dimensions"].get("bk_target_ip", ""):
                    ip = origin_alarm["data"]["dimensions"]["bk_target_ip"]
                else:
                    ip = origin_alarm["data"]["dimensions"]["ip"]

                content = _("主机“{}”的{}").format(ip, self.get_anomaly_msg(alert))

                if set(metric_ids) & set(self.high_risk_label.keys()):
                    high_risk.append({"event_id": alert["id"], "content": content, "type": "serious"})
                    serious_count += 1
                else:
                    other.append({"event_id": alert["id"], "content": content, "type": "warning"})
            else:
                if set(metric_ids) & set(self.high_risk_label.keys()):
                    serious_count += 1

            temp_count += 1

        return {
            "high_risk": high_risk,
            "other": other,
            "has_more": self.alert_count > 8,
            "high_risk_count": serious_count,
            "other_count": temp_count - serious_count,
        }


class UptimeCheckMonitorInfo(BaseMonitorInfo):
    SCENARIO = ["uptimecheck"]

    def get_status(self):
        if self.alert_count > 0:
            return self.get_abnormal_status

        if UptimeCheckTask.objects.filter(bk_biz_id=self.bk_biz_id).exists():
            return MonitorStatus.NORMAL

        return MonitorStatus.UNSET

    def no_access_info(self):
        node_exist = UptimeCheckNode.objects.filter(Q(bk_biz_id=self.bk_biz_id) | Q(is_common=True)).exists()
        return {"step": 2 if node_exist else 1}

    @classmethod
    def get_task_data(cls, task: Dict[str, Any]) -> Dict[str, Any]:
        recent_task_data: Dict[str, Union[str, float, int]] = resource.uptime_check.get_recent_task_data(
            {"task_id": task["id"], "type": "available"}
        )
        task_data: Dict[str, Any] = {
            "task_id": task["id"],
            "task_name": task["name"],
            "available": recent_task_data.get("available"),
        }
        if task_data["available"] is not None:
            task_data["available"] = task_data["available"] * 100
        return task_data

    @classmethod
    def collect_task_datas(
        cls,
        task: Dict[str, Any],
        task_id__notice_data_map: Dict[int, Dict[str, Any]],
        task_id__warning_data_map: Dict[int, Dict[str, Any]],
    ):
        task_data: Dict[str, Any] = cls.get_task_data(task)
        if task_data["available"] is not None:
            if task_data["available"] < 60:
                task_id__warning_data_map[task["id"]] = task_data
            elif task_data["available"] < 80:
                task_id__notice_data_map[task["id"]] = task_data

    def normal_info(self):
        # 按需取字段，在字段均命中索引时 DB 查询无需回表，同时数据行数多的情况下也能加速返回
        task_list: List[Dict[str, Any]] = list(
            UptimeCheckTask.objects.filter(bk_biz_id=self.bk_biz_id).values("id", "name")
        )

        # bksql 不支持 __in lookup，考虑到单个请求耗时较短（< 30ms），此处采用多线程并发调用降低整体请求耗时
        task_id__notice_data_map: Dict[int, Dict[str, Any]] = {}
        task_id__warning_data_map: Dict[int, Dict[str, Any]] = {}
        th_list: List[InheritParentThread] = [
            InheritParentThread(
                target=self.collect_task_datas, args=(task, task_id__notice_data_map, task_id__warning_data_map)
            )
            for task in task_list
        ]
        run_threads(th_list)

        carrieroperator_count: int = (
            UptimeCheckNode.objects.filter(Q(bk_biz_id=self.bk_biz_id) | Q(is_common=True))
            .values("carrieroperator")
            .distinct()
            .count()
        )

        return {
            "single_supplier": carrieroperator_count == 1,
            "notice_task": list(task_id__notice_data_map.values()),
            "warning_task": list(task_id__warning_data_map.values()),
        }

    def get_task_id(self, alert):
        for query_config in alert["extra_info"]["strategy"]["items"][0]["query_configs"]:
            for condition in query_config.get("agg_condition", []):
                if condition["key"] == "task_id":
                    task_id = condition["value"]
                    return int(task_id[0])

    def abnormal_info(self):
        abnormal_events_dick = {}
        for alert in self.alerts:
            try:
                task_id = self.get_task_id(alert)
            except Exception:
                continue
            else:
                abnormal_events_dick[task_id] = {
                    "event_id": alert["id"],
                    "task_id": task_id,
                    "title": alert["extra_info"]["strategy"]["items"][0]["name"],
                }

        task_list = UptimeCheckTask.objects.filter(id__in=[e["task_id"] for e in list(abnormal_events_dick.values())])
        for task in task_list:
            title = abnormal_events_dick[task.id]["title"]
            title = "{}{}".format(task.name, title)
            abnormal_events_dick[task.id].update(title=title)

        now_time = now()
        search_time = now_time + datetime.timedelta(minutes=-10)
        strategies = StrategyModel.objects.filter(
            bk_biz_id=self.bk_biz_id, update_time__gte=search_time, scenario__in=self.SCENARIO
        )
        operations = []
        for s in strategies:
            total_seconds = (localtime(now_time) - s.update_time).total_seconds()
            time_str = hms_string(
                total_seconds, day_unit=_("天"), hour_unit=_("小时"), minute_unit=_("分钟"), second_unit=_("秒")
            )
            operations.append(_("{}前{}修改了告警策略：{}").format(time_str, s.update_user, s.name))

        all_node_status = resource.uptime_check.uptime_check_beat(bk_biz_id=self.bk_biz_id)
        node_status_mapping = {}
        for node_status in all_node_status:
            if is_ipv6_biz(self.bk_biz_id):
                node_status_mapping[str(node_status["bk_host_id"])] = node_status
            else:
                node_status_mapping[
                    host_key(ip=node_status["ip"], bk_cloud_id=str(node_status["bk_cloud_id"]))
                ] = node_status

        node_list = UptimeCheckNode.objects.filter(Q(bk_biz_id=self.bk_biz_id) | Q(is_common=True))
        abnormal_node = []
        id_to_host = {}
        ip_to_host = {}
        bk_host_ids = [node.bk_host_id for node in node_list if node.bk_host_id]
        origin_ips = [node.ip for node in node_list if not node.bk_host_id]
        ip_hosts = api.cmdb.get_host_without_biz(ips=origin_ips)["hosts"]
        hosts = api.cmdb.get_host_without_biz(bk_host_ids=bk_host_ids)["hosts"]
        all_hosts = ip_hosts + hosts
        ip_to_host.update(
            {
                host_key(ip=host.bk_host_innerip, bk_cloud_id=str(host.bk_cloud_id)): host
                for host in all_hosts
                if host.bk_host_innerip
            }
        )
        id_to_host.update({host.bk_host_id: host for host in all_hosts})

        for node in node_list:
            if node.bk_host_id:
                host_instance = id_to_host.get(node.bk_host_id, None)
            else:
                host_instance = ip_to_host.get(host_key(ip=node.ip, bk_cloud_id=str(node.plat_id)), None)
            if not host_instance:
                # host_id/ip失效，无法找到对应主机实例，拨测节点标记为失效状态
                status = int(BEAT_STATUS["INVALID"])
            else:
                if is_ipv6_biz(self.bk_biz_id):
                    status = int(node_status_mapping.get(str(host_instance.bk_host_id), {}).get("status"))
                else:
                    status = int(
                        node_status_mapping.get(
                            host_key(ip=host_instance.bk_host_innerip, bk_cloud_id=str(host_instance.bk_cloud_id)), {}
                        ).get("status")
                    )
            if status is not None and status != 0:
                abnormal_node.append(
                    {
                        "ip": node.ip,
                        "bk_cloud_id": node.plat_id,
                        "name": node.name,
                        "status": status,
                        "isp": node.carrieroperator,
                    }
                )

        return {
            "task": {"abnormal_events": list(abnormal_events_dick.values()), "operations": operations},
            "node": {"abnormal_nodes": abnormal_node},
        }
