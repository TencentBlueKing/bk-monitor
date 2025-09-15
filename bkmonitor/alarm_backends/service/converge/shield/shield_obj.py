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
import logging

import arrow
from django.utils.translation import gettext as _
from six import string_types

from alarm_backends.core.cache.cmdb.dynamic_group import DynamicGroupManager
from alarm_backends.core.cache.key import NOTICE_SHIELD_KEY_LOCK
from alarm_backends.core.context.utils import get_business_roles
from alarm_backends.core.control.strategy import Strategy
from alarm_backends.service.converge.shield.display_manager import DisplayManager
from bkmonitor.documents.alert import AlertDocument
from bkmonitor.utils import time_tools
from bkmonitor.utils.range import (
    CONDITION_CLASS_MAP,
    TIME_MATCH_CLASS_MAP,
    load_field_instance,
)
from bkmonitor.utils.range.conditions import AndCondition, EqualCondition, OrCondition
from bkmonitor.utils.range.period import TimeMatch, TimeMatchBySingle
from bkmonitor.utils.send import Sender
from constants.shield import ScopeType, ShieldCategory
from core.errors.alarm_backends import StrategyNotFound

logger = logging.getLogger("fta_action")


class ShieldObj:
    """
    每条屏蔽配置对应的obj
    """

    def __init__(self, config):
        self.config = config
        self.id = config["id"]

        self.dimension_check = None
        self.time_check = None
        self.notice_lock_key = NOTICE_SHIELD_KEY_LOCK.get_key(shield_id=self.config["id"])
        self.display_manager = DisplayManager()
        self._parse_dimension_config()
        self._parse_cycle_config()

    @property
    def is_dimension_scope(self):
        return self.config["category"] == ShieldCategory.DIMENSION

    def _parse_cycle_config(self):
        """
         将config_list转成datetime_config_list 避免重复转换
        :return: list
        """
        cycle_config = self.config.get("cycle_config")

        begin_time = TimeMatch.convert_datetime_to_arrow(self.config.get("begin_time"))
        end_time = TimeMatch.convert_datetime_to_arrow(self.config.get("end_time"))

        # 1.拿到时间屏蔽的类型, 如果cycle是{}，则shield_type是-1
        shield_type = int(cycle_config.get("type", "-1"))
        time_match_class = TIME_MATCH_CLASS_MAP.get(shield_type, TimeMatchBySingle)
        self.time_check = time_match_class(cycle_config, begin_time, end_time)

    def _parse_dimension_conditions(self, clean_dimension):
        """
        根据维度信息配置屏蔽条件
        :param clean_dimension:
        :return:
        """
        dimension_conditions = clean_dimension.pop("dimension_conditions", [])
        or_condition = OrCondition()
        and_condition = AndCondition()
        for condition in dimension_conditions:
            field = load_field_instance(condition["key"], condition["value"])
            condition_class = CONDITION_CLASS_MAP.get(condition.get("method"), EqualCondition)
            if condition.get("condition") == "or" and and_condition.conditions:
                or_condition.add(and_condition)
                and_condition = AndCondition()
            and_condition.add(condition_class(field))
        if and_condition.conditions:
            or_condition.add(and_condition)
        if or_condition.conditions:
            self.dimension_check.add(or_condition)

    def _parse_dimension_config(self):
        """
        将config_list转成condition_list 避免重复转换
        :return: list[condition]
        """

        self.dimension_check = AndCondition()

        clean_dimension = self._clean_dimension()
        if self.is_dimension_scope:
            # 如果是按维度屏蔽，直接获取维度信息
            self._parse_dimension_conditions(clean_dimension)
            return
        if self.config["category"] == ShieldCategory.STRATEGY:
            # 如果是按策略屏蔽，需要获取维度信息进行屏蔽配置之后，还需要额外添加一层屏蔽配置
            self._parse_dimension_conditions(clean_dimension)

            # 如果是按照节点进行屏蔽，则需要判断是否是按照业务屏蔽的
            if self.config["scope_type"] == ScopeType.NODE:
                bk_topo_node = clean_dimension.pop("bk_topo_node", [])
                if not (len(bk_topo_node) == 1 and bk_topo_node[0]["bk_obj_id"] == ScopeType.BIZ):
                    clean_dimension["bk_topo_node"] = bk_topo_node

        # 解析动态分组配置
        if self.config["scope_type"] == ScopeType.DYNAMIC_GROUP:
            dynamic_group_ids = set()
            for dg in clean_dimension.pop("dynamic_group", []):
                dynamic_group_ids.add(dg["dynamic_group_id"])
            dynamic_group_ids = list(dynamic_group_ids)

            # 查询动态分组所属的主机
            dynamic_groups = []
            if dynamic_group_ids:
                dynamic_groups = DynamicGroupManager.multi_get(dynamic_group_ids)

            bk_host_ids: set = {0}
            for dynamic_group in dynamic_groups:
                if dynamic_group and dynamic_group.get("bk_obj_id") == "host":
                    bk_host_ids.update(dynamic_group["bk_inst_ids"])
            # 动态分组所属的主机为空，则表示屏蔽规则失效，依然需要将bk_host_id: [0] 设置到待匹配维度中
            clean_dimension["bk_host_id"] = list(bk_host_ids)

        for k, v in list(clean_dimension.items()):
            field = load_field_instance(k, v)
            self.dimension_check.add(EqualCondition(field))

    def _clean_dimension(self):
        """
        对配置中的维度进行初始化，删除下划线开头的，包含all的等
        :return:
        """

        def is_contains_00(para):
            """
            判断是否包含00
            :param : str|list
            :return: bool
            """
            if isinstance(para, string_types):
                return "00" == para
            elif isinstance(para, list):
                return "00" in para
            return False

        def is_start_with__(parm):
            """
            判断key是否以“_”开头
            :param parm:str
            :return: bool
            """
            if isinstance(parm, string_types):
                return parm[0] == "_"
            return False

        def is_contains_all(parm):
            """
            判断当key等于category是value是否是all
            :param parm: dict
            :return: bool
            """
            category = parm.get("category")
            if isinstance(category, string_types):
                return category == "all"
            elif isinstance(category, list):
                return "all" in category
            return False

        del_key = []

        dimension = copy.deepcopy(self.config.get("dimension_config"))

        # 1. 找出 key为category且value为all的维度
        if is_contains_all(dimension):
            del_key.append("category")

        for key, value in list(dimension.items()):
            # 2. 找出value包含00的维度
            # 3. 找出key以下划线打头的维度
            if is_contains_00(value) or is_start_with__(key):
                del_key.append(key)

        # 4. 删除1-3中找出的无效维度配置
        for k in del_key:
            dimension.pop(k)
        return dimension

    def is_match(self, alarm):
        """
        判断时间和维度是否都匹配
        :param alarm: 告警事件
        :rtype Event
        :return: true|false
        """

        source_time = arrow.now()
        dimension = copy.deepcopy(alarm.origin_alarm["data"]["dimensions"])
        dimension["strategy_id"] = alarm.strategy_id
        dimension["level"] = alarm.level
        dimension["metric_id"] = alarm.origin_config["item_list"][0]["metric_id"]

        if "bk_target_ip" in dimension and "ip" not in dimension:
            dimension["ip"] = dimension["bk_target_ip"]

        if "bk_target_cloud_id" in dimension and "bk_cloud_id" not in dimension:
            dimension["bk_cloud_id"] = dimension["bk_target_cloud_id"]

        return self.time_check.is_match(source_time) and self.dimension_check.is_match(dimension)

    def get_now_datetime(self):
        """
        获取当前时间
        """
        return arrow.now()

    def can_send_start_notice(self):
        """
        检查是否满足发送开始通知条件
        """
        if not self.config.get("notice_config"):
            return False
        notice_time = self.config["notice_config"]["notice_time"]

        # 判断依据：x 分钟后在屏蔽范围
        begin_time = self.get_now_datetime()
        end_time = begin_time.replace(minutes=notice_time)
        is_time_match = self.time_check.is_match(end_time)

        if not is_time_match:
            # 未到发送时间，忽略
            return False

        # 查询是否已经发送过

        lock = NOTICE_SHIELD_KEY_LOCK.client.get(self.notice_lock_key)
        if lock:
            # 如果已经有锁，说明已经发送过则则只更新key过期时间
            NOTICE_SHIELD_KEY_LOCK.expire(shield_id=self.config["id"])
            return False
        return True

    def can_send_end_notice(self):
        """
        检查是否满足发送结束通知条件
        """
        if not self.config.get("notice_config"):
            return False
        notice_time = self.config["notice_config"]["notice_time"]

        # 判断依据：x 分钟后不在屏蔽范围
        begin_time = self.get_now_datetime()
        end_time = begin_time.replace(minutes=notice_time + 1)
        is_time_match = not self.time_check.is_match(end_time)

        if not is_time_match:
            # 未到发送时间，忽略
            return False

        lock = NOTICE_SHIELD_KEY_LOCK.client.get(self.notice_lock_key)
        if not lock:
            # 如果没有锁，则无需发送结束通知
            return False

        # 有锁，则说明屏蔽已经在发生，可以发送结束通知
        return True

    def check_and_send_notice(self):
        """
        检查是否满足屏蔽通知条件，若满足则发送
        """
        start_notice_sent_result = None
        end_notice_sent_result = None
        if self.can_send_start_notice():
            # 满足可以进行屏蔽开始通知的时间
            NOTICE_SHIELD_KEY_LOCK.client.set(self.notice_lock_key, "__lock__", NOTICE_SHIELD_KEY_LOCK.ttl)
            start_notice_sent_result = self.send_notice("start")

        if self.can_send_end_notice():
            # 满足可以进行屏蔽结束通知的时间
            NOTICE_SHIELD_KEY_LOCK.client.delete(self.notice_lock_key)
            end_notice_sent_result = self.send_notice("end")

        return start_notice_sent_result, end_notice_sent_result

    def send_notice(self, notice_type):
        """
        发送通知
        :param notice_type: 通知类型，start 或 end
        """
        if not self.config.get("notice_config"):
            return {}

        # 解析通知人员
        notice_receivers = self.parse_notice_receivers()
        if not notice_receivers:
            return {}

        # 获取通知模板上下文
        context = self.get_notice_context(notice_type)

        all_notice_result = {}

        for notice_way in self.config["notice_config"]["notice_way"]:
            sender = Sender(
                title_template_path=f"notice/shield/{notice_way}_title.jinja",
                content_template_path=f"notice/shield/{notice_way}_content.jinja",
                context=context,
            )
            logger.debug(
                "[屏蔽通知] shield({}) 通知方式：{}, 内容：{}".format(self.config["id"], notice_way, sender.content)
            )
            notice_result = sender.send(notice_way, notice_receivers)
            all_notice_result[notice_way] = notice_result

        return all_notice_result

    def parse_notice_receivers(self):
        if not self.config.get("notice_config"):
            return []
        business_roles = get_business_roles(self.config["bk_biz_id"])
        receivers = []
        receivers_set = set()
        for notice_receiver in self.config["notice_config"]["notice_receiver"]:
            receiver_type, receiver_name = notice_receiver.split("#")
            if receiver_type == "user":
                receivers.append(receiver_name)
            else:
                receivers.extend(business_roles.get(receiver_name, []))

        # 去重
        actual_receivers = []
        for name in receivers:
            if name not in receivers_set:
                receivers_set.add(name)
                actual_receivers.append(name)

        return actual_receivers

    def get_notice_context(self, notice_type):
        """
        获取屏蔽通知上下文
        :param notice_type:
        :return:
        """
        if notice_type == "start":
            notice_type_desc = _("开始")
            start_time = self.config["begin_time"]
        else:
            notice_type_desc = _("结束")
            start_time = self.config["end_time"]

        context = {
            "notice_type": notice_type_desc,
            "shield_id": self.config["id"],
            # TODO: 开始时间需要带上日期，需要计算出最近一次的屏蔽时间
            "start_time": time_tools.utc2biz_str(start_time, _format="%H:%M"),
            "category_name": self.display_manager.get_category_name(self.config),
            "cycle_duration": self.display_manager.get_cycle_duration(self.config),
            "shield_content": self.display_manager.get_shield_content(self.config),
            "description": self.config["description"],
        }

        return context


class AlertShieldObj(ShieldObj):
    def get_dimension(self, alert: AlertDocument):
        try:
            dimension = copy.deepcopy(alert.origin_alarm["data"]["dimensions"])
        except BaseException as error:
            # 有可能第三方告警没有维度信息
            dimension = {}
            logger.info("Get origin alarm dimensions  of alert(%s) error, %s", alert.id, str(error))
        alert_dimensions = [d.to_dict() for d in alert.dimensions]
        dimension.update({d["key"]: d.get("value", "") for d in alert_dimensions})
        dimension["strategy_id"] = alert.strategy_id
        dimension["level"] = alert.severity
        dimension["bk_topo_node"] = dimension.get("bk_topo_node") or [
            node for node in alert.event_document.bk_topo_node
        ]
        dimension["bk_host_id"] = dimension.get("bk_host_id") or alert.event_document.bk_host_id
        dimension["bk_biz_id"] = alert.event_document.bk_biz_id
        metric_ids = []

        if alert.strategy_id:
            # 需要判断当前的alert是否有策略ID
            strategy = Strategy(alert.strategy_id, default_config=alert.strategy)
            # 策略缓存获取不到，则无法后续判定，此时 直接抛出异常
            if not strategy.config:
                raise StrategyNotFound(key=alert.strategy_id)

            for query_config in strategy.config["items"][0]["query_configs"]:
                metric_ids.append(query_config["metric_id"])

        dimension["metric_id"] = metric_ids

        if "tags.bk_target_ip" in dimension and "ip" not in dimension:
            dimension["ip"] = dimension["tags.bk_target_ip"]

        if "bk_target_ip" not in dimension and "ip" in dimension:
            dimension["bk_target_ip"] = dimension["ip"]

        if "tags.bk_target_cloud_id" in dimension and "bk_cloud_id" not in dimension:
            dimension["bk_cloud_id"] = dimension["tags.bk_target_cloud_id"]

        if "bk_target_cloud_id" not in dimension and "bk_cloud_id" in dimension:
            dimension["bk_target_cloud_id"] = dimension["bk_cloud_id"]

        if "tags.bk_target_service_instance_id" in dimension and "service_instance_id" not in dimension:
            dimension["service_instance_id"] = dimension["tags.bk_target_service_instance_id"]

        if "bk_service_instance_id" in dimension and "service_instance_id" not in dimension:
            dimension["service_instance_id"] = dimension["bk_service_instance_id"]

        if "bk_target_service_instance_id" not in dimension and "service_instance_id" in dimension:
            dimension["bk_target_service_instance_id"] = dimension["service_instance_id"]

        if "bk_service_instance_id" not in dimension and "service_instance_id" in dimension:
            dimension["bk_service_instance_id"] = dimension["service_instance_id"]

        new_dimensions = {}
        tag_prefix = "tags."
        for key, value in dimension.items():
            new_dimensions[key] = value
            if key.startswith(tag_prefix) and key[len(tag_prefix) :] not in dimension:
                # 将带tags前缀的维度转换为不带前缀，扩大搜索维度  (tags.device_name => device_name)
                new_dimensions[key[len(tag_prefix) :]] = value
        return new_dimensions

    def is_match(self, alert: AlertDocument):
        source_time = arrow.now()
        return self.time_check.is_match(source_time) and self.dimension_check.is_match(self.get_dimension(alert))
