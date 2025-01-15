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
import functools
from typing import Dict, List

import arrow

from bkmonitor.models import Shield
from bkmonitor.utils.shield import BaseShieldDisplayManager
from bkmonitor.utils.time_tools import localtime, now, str2datetime
from constants.shield import ShieldCategory, ShieldCycleType
from core.drf_resource import api, resource
from monitor_web.commons.cc.utils import CmdbUtil


class ShieldDetectManager(object):
    """
    检查是否被屏蔽
    """

    def __init__(self, bk_biz_id, category):
        self.shield_list = self.get_shield_list(bk_biz_id, category)

    def get_shield_list(self, bk_biz_id, category):
        """
        获取屏蔽配置
        """
        shield_list = Shield.objects.filter(bk_biz_id=bk_biz_id, is_enabled=1, end_time__gte=now())

        # 策略列表页判断是否被屏蔽，需要查快捷屏蔽
        if category == ShieldCategory.STRATEGY:
            shield_list = list(shield_list.filter(category=category))

        # 告警事件列表页判断是否被屏蔽，需要看这个时间点有没有被屏蔽
        if category == ShieldCategory.ALERT:
            shield_list = shield_list.filter(begin_time__lte=now())
            shield_list = [shield for shield in shield_list if self.check_time(shield)]

        return shield_list

    def check_shield_status(self, match_info):
        """
        检查是否被屏蔽
        """
        shield_ids = []
        shield_info = {"is_shielded": False, "shield_ids": shield_ids}
        for shield in self.shield_list:
            # 遍历屏蔽的维度进行匹配
            if self.is_shielded(shield, match_info):
                shield_ids.append(shield.id)

        if shield_ids:
            # 兼容以前的数据结构，保证id字段存在
            shield_info.update({"id": shield_ids[0], "is_shielded": True})
        return shield_info

    def is_shielded(self, shield_obj, match_info):
        """
        检测单个屏蔽策略是否生效
        :param shield_obj: 屏蔽策略对象
        :param match_info: 维度信息
        :return:
        """
        # 遍历屏蔽的维度进行匹配
        for key, value in list(shield_obj.dimension_config.items()):
            # 以'_'开头的key不去进行校验
            if key.startswith("_") or not value:
                continue

            if key == "dimension_conditions" and value:
                break

            # 范围屏蔽——ip的情况
            if key == "bk_target_ip" and isinstance(value, list):
                value = ["{}|{}".format(item.get("bk_target_ip"), item.get("bk_target_cloud_id")) for item in value]

            # 范围屏蔽——节点的情况
            if key == "bk_topo_node":
                value = ["{}|{}".format(item.get("bk_obj_id"), item.get("bk_inst_id")) for item in value]

            if key == "dynamic_group":
                value = [str(item["dynamic_group_id"]) for item in value if "dynamic_group_id" in item]

            alarm_set = set(self.get_match_info_value(key, match_info))
            shield_set = set(self.get_list(value))

            # 若未匹配到，则使用下一条屏蔽进行匹配
            if not alarm_set & shield_set:
                break
        else:
            return True
        return False

    def get_match_info_value(self, key, data):
        # 针对告警事件的IP维度，做一些特殊处理，统一返回的格式
        if key == "bk_target_ip":
            ip_value = data.get("bk_target_ip", "")

            first_value = ip_value
            if ip_value and isinstance(ip_value, (list, tuple)):
                first_value = ip_value[0]

            if isinstance(first_value, dict):
                ip_value = first_value.get("bk_target_ip")
                bk_cloud_id = first_value.get("bk_target_cloud_id", first_value.get("bk_cloud_id", "0"))
                return ["{}|{}".format(ip_value, bk_cloud_id)]

            if first_value:
                bk_cloud_id = data.get("bk_target_cloud_id", data.get("bk_cloud_id", "0"))
                return ["{}|{}".format(ip_value, bk_cloud_id)]

        return self.get_list(data.get(key, []))

    @staticmethod
    def check_time(shield):
        """
        判断屏蔽策略是否生效：
        1、对屏蔽的开始和结束时间补上秒数，开始时间补00，结束时间补59
        2、获取屏蔽策略的按周屏蔽的星期设置以及按月屏蔽的天数设置
        3、根据屏蔽的周期类型做不同的判断
        :return: True或False
        """

        # 如果是单次屏蔽，已经在读数据库的时候过滤出来了，以下主要针对复合屏蔽
        if shield.cycle_config.get("type") != ShieldCycleType.ONCE:
            # 当前时间
            time_now = localtime(now())

            # 起止时间
            date_now_str = arrow.get(time_now).format("YYYY-MM-DD")
            begin_time_str = "{} {}".format(date_now_str, shield.cycle_config["begin_time"])
            end_time_str = "{} {}".format(date_now_str, shield.cycle_config["end_time"])
            begin_time = localtime(str2datetime(begin_time_str))
            end_time = localtime(str2datetime(end_time_str))

            # 根据周期类型做不同的判断
            week_list = shield.cycle_config.get("week_list", [])
            day_list = shield.cycle_config.get("day_list", [])
            if (
                shield.cycle_config["type"] == ShieldCycleType.EVERYDAY
                or time_now.weekday() + 1 in week_list
                or time_now.day in day_list
            ):
                if not (begin_time <= time_now <= end_time):
                    return False
        return True

    @staticmethod
    def get_list(obj):
        return obj if isinstance(obj, list) else [obj]


class ShieldDisplayManager(BaseShieldDisplayManager):
    def __init__(self, bk_biz_id=None):
        super(ShieldDisplayManager, self).__init__()
        self.node_manager = CmdbUtil(bk_biz_id)
        self.dynamic_group_name_mapping: Dict[int, Dict[str, str]] = {}

    def _get_dynamic_group_name_mapping(self, bk_biz_id: int):
        if bk_biz_id in self.dynamic_group_name_mapping:
            return self.dynamic_group_name_mapping[bk_biz_id]

        dynamic_group_name_mapping = {}
        dynamic_groups = api.cmdb.search_dynamic_group(bk_biz_id=bk_biz_id, bk_obj_id="host")
        for dynamic_group in dynamic_groups:
            dynamic_group_name_mapping[dynamic_group["id"]] = dynamic_group["name"]
        self.dynamic_group_name_mapping[bk_biz_id] = dynamic_group_name_mapping
        return dynamic_group_name_mapping

    def get_service_name_list(self, bk_biz_id, service_instance_id_list):
        return self.node_manager.get_service_name(bk_biz_id, service_instance_id_list)

    def get_node_path_list(self, bk_biz_id, bk_topo_node_list):
        return self.node_manager.get_node_path(bk_biz_id, bk_topo_node_list)

    def get_dynamic_group_name_list(self, bk_biz_id: int, dynamic_group_list: List[Dict]) -> List:
        dynamic_group_name_mapping = self._get_dynamic_group_name_mapping(bk_biz_id)
        return [
            dynamic_group_name_mapping.get(dynamic_group["dynamic_group_id"], dynamic_group["dynamic_group_id"])
            for dynamic_group in dynamic_group_list
        ]

    @functools.lru_cache(maxsize=128)
    def get_business_name(self, bk_biz_id):
        """根据 bk_biz_id 获取业务名，使用缓存（基于 self 和 bk_biz_id）以提高性能。"""
        business = resource.cc.get_app_by_id(bk_biz_id)
        return business.name
