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

import logging
from typing import List

from django.utils.functional import cached_property
from django.utils.translation import ugettext as _

from alarm_backends.core.alert.alert import Alert, AlertKey
from alarm_backends.core.cache.action_config import ActionConfigCacheManager
from alarm_backends.core.cache.strategy import StrategyCacheManager
from alarm_backends.core.control.strategy import Strategy
from bkmonitor.documents import EventDocument
from bkmonitor.documents.alert import AlertDocument
from bkmonitor.models import (
    ActionInstance,
    ConvergeInstance,
    ConvergeRelation,
    GlobalConfig,
)
from bkmonitor.utils.common_utils import count_md5
from constants import alert as alert_constants
from constants.action import (
    ActionSignal,
    ActionStatus,
    ConvergeType,
    NoticeChannel,
    NoticeWay,
    NoticeWayChannel,
    UserGroupType,
)

logger = logging.getLogger("fta_action.run")


class ActionContext(object):
    """
    处理套餐上下文
    """

    Fields = [
        "notice_way",
        "user_type",
        "notice_channel",
        "notice_receiver",
        "mentioned_users",
        "notice_title",
        "content_template",
        "default_content_template",
        "title_template",
        "default_title_template",
        "alerts_info",
        "user_content",
        "user_title",
        "target",
        "alert_level",
        "level_name",
        "level_color",
        "alarm",
        "alert",
        "event",
        "anomaly_record",
        "content",
        "strategy",
        "business",
        "action",
        "action_instance",
        "action_instance_content",
        "collect_ctx",
    ]

    DEFAULT_TITLE_TEMPLATE = alert_constants.DEFAULT_TITLE_TEMPLATE

    DEFAULT_TEMPLATE = alert_constants.DEFAULT_TEMPLATE

    DEFAULT_ACTION_TEMPLATE = (
        "{{action_instance_content.name}}\n"
        "{{action_instance_content.plugin_type_name}}\n"
        "{{action_instance_content.assignees}}\n"
        "{{action_instance_content.start_time}}\n"
        "{{action_instance_content.end_time}}\n"
        "{{action_instance_content.duration_string}}\n"
        "{{action_instance_content.status_display}}\n"
        "{{action_instance_content.opt_content}}\n"
        "{{action_instance_content.detail_link}}\n"
    )

    ALERT_LEVEL_COLOR = {
        alert_constants.EventSeverity.FATAL: "#EA3636",
        alert_constants.EventSeverity.WARNING: "#FF9C01",
        alert_constants.EventSeverity.REMIND: "#FFDE3A",
    }

    def __init__(
        self,
        action,
        related_actions: List[ActionInstance] = None,
        alerts: List[AlertDocument] = None,
        use_alert_snap=False,
        notice_way=None,
        dynamic_kwargs=None,
    ):
        self.action: ActionInstance = action
        self.user_content = ""
        self.limit = False
        self.converge_type = ConvergeType.ACTION
        self.mention_users = {}
        if self.action:
            for attr, value in self.action.get_context().items():
                if attr in ["notice_way", "notice_receiver"]:
                    value = value[0] if isinstance(value, list) else value
                setattr(self, attr, value)
        if not hasattr(self, "notice_way"):
            setattr(self, "notice_way", notice_way or NoticeWay.WEIXIN)
        self.notice_channel, self.notice_way = self.get_notice_channel()
        dynamic_kwargs = dynamic_kwargs if dynamic_kwargs else {}
        for attr, value in dynamic_kwargs.items():
            setattr(self, attr, value)
        self.all_related_actions = related_actions
        self.converge_type = ConvergeType.ACTION if len(self.related_action_ids) == 1 else self.converge_type
        self.related_alerts = (
            [alert if isinstance(alert, AlertDocument) else AlertDocument(**alert) for alert in alerts]
            if alerts
            else []
        )
        # 是否强制使用缓存
        self.use_alert_snap = use_alert_snap

    def get_notice_channel(self):
        """
        获取对应的通知渠道
        :return:
        """
        notice_way = getattr(self, "notice_way", None)
        if not notice_way:
            # 没有通知方式的，直接用默认的用户渠道
            return NoticeChannel.USER, None
        channel = NoticeWayChannel.MAPPING.get(notice_way)
        if not channel:
            try:
                # 解析出channel信息
                channel, notice_way = notice_way.split("|")
            except ValueError:
                # 如果无法解析也获取不到，默认是用户渠道
                channel = NoticeChannel.USER
        return channel, notice_way

    @cached_property
    def user_type(self):
        """
        告警组类型
        """
        if self.example_action and self.example_action.inputs.get("followed"):
            # 如果当前通知
            return UserGroupType.FOLLOWER
        return None

    @cached_property
    def followed(self):
        """
        是否为关注人
        """

        if self.example_action and self.example_action.inputs.get("followed"):
            # 如果当前通知
            return True
        return False

    @cached_property
    def group_notice_way(self):
        """
        附带用户组类型的通知方法
        """
        if self.user_type:
            return f"{self.user_type}-{self.notice_way}"
        return self.notice_way

    @cached_property
    def mentioned_users(self):
        """
        当前通知的代表提醒人员
        """
        if self.notice_way != NoticeWay.WX_BOT:
            return None
        mention_users = getattr(self, "mention_users", None)
        if mention_users:
            # 如果是单个通知，直接用原action的提醒人员
            return mention_users
        # 如果是汇总的通知，则获取代表事件的提醒信息
        return self.example_action.inputs.get("mention_users")

    @cached_property
    def is_external_channel(self):
        if self.notice_channel and self.notice_channel not in NoticeChannel.DEFAULT_CHANNELS:
            # 如果有channel信息，并且不是默认渠道, 则认为是外部渠道
            return True
        return False

    @cached_property
    def notice_title(self):
        return GlobalConfig.get("NOTICE_TITLE", _("蓝鲸监控"))

    @cached_property
    def related_actions(self):
        return self.all_related_actions or self.get_converged_actions()

    def get_converged_actions(self):
        """
        根据收敛ID获取对应的处理事件
        :param converge_id: 收敛ID
        :return:
        """
        if isinstance(self.action, ConvergeInstance):
            converge_instance = self.action
        else:
            converge_id = getattr(self, "converge_id", None)
            if converge_id is None:
                return []
            converge_instance = ConvergeInstance.objects.get(id=converge_id)
        related_ids = [inst.related_id for inst in ConvergeRelation.objects.filter(converge_id=converge_instance.id)]
        if converge_instance.converge_type == ConvergeType.CONVERGE:
            # 仅支持两层收敛，所以最多再获取一次处理事件信息
            related_ids = list(
                ConvergeRelation.objects.filter(
                    converge_id__in=related_ids, related_type=ConvergeType.ACTION
                ).values_list("related_id", flat=True)
            )
        return list(ActionInstance.objects.filter(id__in=set(related_ids)).filter(status=ActionStatus.SKIPPED))

    @cached_property
    def action_config_id(self):
        """
        对应的套餐ID
        """
        if isinstance(self.action, ActionInstance):
            return self.action.action_config["id"]

        if self.related_actions:
            return self.related_actions[0].action_config["id"]
        return ""

    @cached_property
    def collect_id(self):
        """
        对应监控之前的alert_collect_id
        :return:
        """
        return self.action.es_action_id

    @cached_property
    def token(self):
        """
        连接上对应的token
        :return:
        """
        return count_md5([self.action.es_action_id, int(self.action.create_time.timestamp())])

    @cached_property
    def related_action_ids(self):
        return [action.id for action in self.related_actions]

    @cached_property
    def alert_level(self):
        return self.alert.severity

    @cached_property
    def level_name(self):
        return str(alert_constants.EVENT_SEVERITY_DICT.get(self.alert_level, self.alert_level))

    @cached_property
    def level_color(self):
        """
        级别名称
        :rtype: str
        """
        return self.ALERT_LEVEL_COLOR.get(self.alert_level, "#000000")

    @cached_property
    def alerts(self) -> List[AlertDocument]:
        if self.use_alert_snap and self.related_alerts:
            # 如果强制使用alert缓存并且存在缓存，直接返回
            return self.related_alerts

        alert_ids = self.action.alerts if self.action else []
        alert_keys = {}
        if self.action and self.action.signal != ActionSignal.COLLECT and self.action.alerts:
            # 汇总的通知不需要加载，从关联action里获取即可
            alert_keys[self.action.alerts[0]] = AlertKey(
                alert_id=self.action.alerts[0], strategy_id=self.action.strategy_id
            )
        for action in self.related_actions:
            alert_ids.extend(action.alerts)
            for alert_id in action.alerts:
                if alert_id not in alert_keys:
                    alert_keys[alert_id] = AlertKey(alert_id=alert_id, strategy_id=action.strategy_id)
        alert_ids = list(set(alert_ids))
        alert_docs = [AlertDocument(**alert.data) for alert in Alert.mget(list(alert_keys.values()))]
        if alert_docs:
            return alert_docs
        if not self.related_alerts:
            logger.info("get alert of action(%s) failed, current alert_ids %s", self.action.id, alert_ids)
        return self.related_alerts

    @cached_property
    def alerts_info(self):
        """
        触发的告警列表信息
        """
        return self.get_alerts_dict(self.alerts)

    @cached_property
    def alert(self) -> AlertDocument:
        if self.alerts:
            return self.alerts[0]
        logger.info(
            "get alert of action(%s) failed, current related_actions %s", self.action.id, self.related_action_ids
        )
        return None

    @cached_property
    def event(self):
        """
        适配原来的event
        :return:
        """
        return self.alert

    @cached_property
    def anomaly_record(self):
        if not self.alert:
            return None
        try:
            # 当ES中获取不到的时候，直接返回缓存告警的事件信息
            return self.alert.event_document
        except BaseException as error:
            logger.info("get anomaly_record from alert(%s) failed, error info %s", self.alert.id, str(error))

        latest_time = self.alert.latest_time
        try:
            hits = (
                EventDocument.search(all_indices=True)
                .filter("term", time=latest_time)
                .filter("term", dedupe_md5=self.alert.dedupe_md5)
                .execute()
                .hits
            )
        except BaseException:
            hits = []
        if hits:
            return EventDocument(**hits[0].to_dict())
        return None

    @cached_property
    def converge_context(self):
        from .converge import Converge

        return Converge(self)

    @cached_property
    def collect_ctx(self):
        return self.converge_context

    @cached_property
    def action_instance(self):
        from .action_instance import ActionInstanceContext

        return ActionInstanceContext(self)

    @cached_property
    def alarm(self):
        from .alarm import Alarm

        return Alarm(self)

    @cached_property
    def target(self):
        from .target import Target

        return Target(self)

    @cached_property
    def business(self):
        return self.target.business

    @cached_property
    def strategy(self):
        """
        告警策略
        """
        return Strategy(self.alert.strategy_id, default_config=self.alert.strategy if self.alert else None)

    @cached_property
    def content(self):
        """
        通知内容变量
        """
        from .content import DimensionCollectContent, MultiStrategyCollectContent

        if self.converge_type == ConvergeType.CONVERGE and len(self.related_actions) > 1:
            return MultiStrategyCollectContent(self)
        elif self.converge_type == ConvergeType.ACTION:
            return DimensionCollectContent(self)
        return None

    @cached_property
    def action_instance_content(self):
        from .action_instance import ActionInstanceContent

        return ActionInstanceContent(self)

    @cached_property
    def notice_action_config(self):
        notice = self.strategy.notice
        if not notice:
            return {}
        return ActionConfigCacheManager.get_action_config_by_id(notice["config_id"])

    @cached_property
    def content_template(self):
        """
        自定义告警模板内容
        """
        if getattr(self, "message_tmpl", None):
            template = self.message_tmpl

        if self.action is None:
            template = self.DEFAULT_TEMPLATE
        else:
            try:
                notify_config = {
                    tpl["signal"]: tpl["message_tmpl"]
                    for tpl in self.example_action.action_config.get("execute_config", {})
                    .get("template_detail", {})
                    .get("template", [])
                }
            except BaseException:
                notify_config = {}

            signal = self.example_action.signal

            if signal == ActionSignal.NO_DATA:
                # 无数据告警与异常告警共用模板
                signal = ActionSignal.ABNORMAL

            template = notify_config.get(signal)
            if not template:
                template = self.DEFAULT_TEMPLATE

        # 除了「邮件」「企业微信」其他均不支持发送标题，如果通知配置自定义了标题（非默认模板），将 title 加入 content
        # 忽略首尾的空白符进行比较
        if (
            self.notice_way not in [NoticeWay.MAIL, "rtx"]
            and self.title_template.strip() != self.DEFAULT_TITLE_TEMPLATE.strip()
        ):
            template = "\n".join([self.title_template, template])

        return template

    @cached_property
    def example_action(self):
        """
        代表事件
        :return:
        """
        if self.action.signal == ActionSignal.COLLECT and self.related_actions:
            for related_action in self.related_actions:
                if self.alert.id in related_action.alerts:
                    # 代表action必须要于alert一致
                    return related_action
        return self.action

    @cached_property
    def default_content_template(self):
        return self.DEFAULT_TEMPLATE

    @cached_property
    def title_template(self):
        """
        自定义告警标题内容
        """
        if getattr(self, "title_tmpl", None):
            return self.title_tmpl

        try:
            notify_config = {
                tpl["signal"]: tpl["title_tmpl"]
                for tpl in self.action.action_config.get("execute_config", {})
                .get("template_detail", {})
                .get("template", [])
            }
        except BaseException:
            notify_config = {}

        if self.action.signal == ActionSignal.NO_DATA:
            # 无数据告警与异常告警共用模板
            signal = ActionSignal.ABNORMAL
        else:
            signal = self.action.signal

        template = notify_config.get(signal)
        if not template:
            template = self.DEFAULT_TITLE_TEMPLATE

        # 做默认告警和告警发生状态的分隔
        template = template.replace("{{alarm.name}}{{alarm.display_type}}", "{{alarm.name}} {{alarm.display_type}}")
        return template

    @cached_property
    def default_title_template(self):
        return self.DEFAULT_TITLE_TEMPLATE

    def get_dictionary(self):
        result = {}
        action_id = self.action.id if self.action else "None"
        logger.info("get context dictionary started for action(%s)", action_id)
        for field in self.Fields:
            try:
                result[field] = getattr(self, field)
            except Exception as e:
                result[field] = None
                action_id = self.action.id if self.action else "NULL"
                alert_id = self.alert.id if self.alert else "NULL"
                logger.debug(
                    "action({})|alert({}) create context field({}) error, {}".format(action_id, alert_id, field, e)
                )
        logger.info("get context dictionary finished for action(%s)", self.action.id if self.action else "None")
        return result

    @staticmethod
    def get_alerts_dict(alerts):
        """
        获取alerts的字典信息
        :param alerts:
        :return:
        """
        strategy_cache = {}
        infos = []
        for alert in alerts:
            if alert.strategy_id not in strategy_cache:
                strategy_cache[alert.strategy_id] = StrategyCacheManager.get_strategy_by_id(alert.strategy_id) or {}
            strategy = strategy_cache[alert.strategy_id]

            try:
                current_value = alert.event.extra_info.origin_alarm.data.value
            except Exception:
                current_value = "--"

            infos.append(
                {
                    "id": alert.id,
                    "name": strategy.get("name", "-"),
                    "target": alert.event_document.target,
                    "dimension": ",".join(["{}={}".format(d.display_key, d.display_value) for d in alert.dimensions])
                    or "-",
                    "current_value": current_value,
                }
            )
        return infos


class BaseContextObject(object):
    def __init__(self, parent):
        self.parent = parent
