"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
import time
from datetime import datetime

import arrow
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext as _

from bkmonitor.documents.incident import IncidentDocument
from bkmonitor.utils.send import IncidentSender
from constants.action import NoticeWay
from bkm_space.api import SpaceApi
from constants.incident import IncidentStatus, IncidentLevel, IncidentOperationType

logger = logging.getLogger("incident.notice")


class IncidentNoticeHelper:
    """故障通知辅助类"""

    @classmethod
    def get_incident_context(
        cls, incident: IncidentDocument, title: str = None, operation_type: IncidentOperationType = None, **kwargs
    ) -> dict:
        """
        构建故障通知的上下文

        :param incident: 故障文档对象
        :param title: 通知标题
        :param operation_type: 通知类型
        :return: 通知上下文字典
        """

        # 获取业务名称
        try:
            space = SpaceApi.get_space_detail(bk_biz_id=int(incident.bk_biz_id))
            business_name = f"[{int(incident.bk_biz_id)}]{space.space_name}"
        except Exception as e:
            business_name = str(incident.bk_biz_id)
            logger.warning(f"获取业务名称失败: {e}")

        # 计算故障持续时间
        duration_info = cls._format_duration(incident.begin_time, incident.end_time)

        # 获取故障根因
        incident_reason = cls._get_incident_reason(incident)

        # 获取故障状态
        status = IncidentStatus(incident.status).alias if incident.status else _("未知")

        # 获取故障级别
        level = IncidentLevel(incident.level).alias if incident.level else _("未知")

        # 获取故障负责人
        assignees = ", ".join(incident.assignees) if incident.assignees else _("未分配")

        # 构建故障详情URL
        url = cls._get_incident_url(incident)

        # 通知时间
        notify_time = datetime.fromtimestamp(int(time.time())).strftime("%Y-%m-%d %H:%M:%S")

        # 属性状态变化
        incident_key = kwargs.get("incident_key")
        from_value = kwargs.get("from_value") or "null"
        to_value = kwargs.get("to_value") or "null"
        incident_key_alias = kwargs.get("incident_key_alias") or incident_key

        # 故障合并信息
        link_incident_name = (kwargs.get("link_incident_name"),)

        # 默认标题
        if not title:
            # 根据操作类型确定通知标题
            title_map = {
                IncidentOperationType.CREATE: f"【{duration_info['duration_range'][0]}】发生【{incident.incident_name}】",
                IncidentOperationType.OBSERVE: f"故障当前状态 观察中，已持续【{duration_info['duration_msg']}】",
                IncidentOperationType.RECOVER: f"【{incident.incident_name}】故障已恢复",
                IncidentOperationType.UPDATE: f"【{incident_key_alias}】原始值：{from_value} → 最新值：{to_value}"
                if incident_key
                else "故障状态更新",
                IncidentOperationType.MERGE: f"故障【{link_incident_name}】并入当前故障"
                if link_incident_name
                else "故障合并",
                IncidentOperationType.MERGE_TO: f"当前故障合并入故障【{link_incident_name}】"
                if link_incident_name
                else "故障合并",
            }
            title = title_map.get(operation_type, "故障通知")

        context = {
            "title": title,
            "incident_name": incident.incident_name or _("未命名故障"),
            "level": level,
            "begin_time": incident.begin_time,
            "notify_time": notify_time,
            "business_name": business_name,
            "incident_reason": incident_reason,
            "status": status,
            "duration": f"{duration_info['duration_msg']}{duration_info['duration_range_msg']}",
            "number": incident.alert_count or 0,
            "assignees": assignees,
            "url": url,
            "bk_biz_id": incident.bk_biz_id,
            "incident_id": incident.incident_id,
        }

        return context

    @classmethod
    def _format_duration(cls, begin_time: int, end_time: int = None) -> dict:
        """
        格式化故障持续时间

        :param begin_time: 故障开始时间戳
        :param end_time: 结束时间戳
        :return: 格式化的持续时间字符串
        """
        if not begin_time:
            return _("未知")

        end = end_time if end_time else int(time.time())
        duration_seconds = end - begin_time

        # 将时间戳转换为本地时区的格式化字符串
        tz_name = timezone.get_current_timezone().zone
        begin_time_str = arrow.get(begin_time).to(tz_name).strftime("%Y-%m-%d %H:%M:%S")
        end_time_str = arrow.get(end).to(tz_name).strftime("%Y-%m-%d %H:%M:%S")

        if duration_seconds < 60:
            duration_msg = _("{}秒").format(duration_seconds)
        elif duration_seconds < 3600:
            minutes = duration_seconds // 60
            duration_msg = _("{}分钟").format(minutes)
        elif duration_seconds < 86400:
            hours = duration_seconds // 3600
            minutes = (duration_seconds % 3600) // 60
            if minutes > 0:
                duration_msg = _("{}小时{}分钟").format(hours, minutes)
            else:
                duration_msg = _("{}小时").format(hours)
        else:
            days = duration_seconds // 86400
            hours = (duration_seconds % 86400) // 3600
            if hours > 0:
                duration_msg = _("{}天{}小时").format(days, hours)
            else:
                duration_msg = _("{}天").format(days)
        return {
            "duration_msg": duration_msg,
            "duration_range": [begin_time_str, end_time_str],
            "duration_range_msg": f"({begin_time_str} 至 {end_time_str})",
        }

    @classmethod
    def _get_incident_reason(cls, incident: IncidentDocument) -> str:
        """
        获取故障根因描述

        :param incident: 故障文档对象
        :return: 故障根因字符串
        """
        return incident.incident_reason or incident.incident_name

    @classmethod
    def _get_incident_url(cls, incident: IncidentDocument) -> str:
        """
        构建故障详情URL

        :param incident: 故障文档对象
        :return: 故障详情URL
        """
        # 构建故障详情页面URL
        site_url = settings.BK_MONITOR_HOST.rstrip("/")
        return f"{site_url}/?bizId={incident.bk_biz_id}#/trace/incident/detail/{incident.id}"

    @classmethod
    def send_incident_notice(
        cls,
        incident: IncidentDocument,
        chat_ids: list[str] = None,
        user_ids: list[str] = None,
        title: str = None,
        operation_type: IncidentOperationType = None,
        **kwargs,
    ) -> dict[str, dict]:
        """
        发送故障通知（支持多种通知方式）

        :param incident: 故障文档对象
        :param chat_ids: 企业微信群ID列表（用于群机器人通知）
        :param user_ids: 用户ID列表（用于个人通知）
        :param title: 通知标题
        :param operation_type: 操作类型
        :return: 发送结果，格式: {notice_way: {receiver: {result, message}}}
        """
        all_results = {}

        # 1. 发送企业微信群机器人通知
        if chat_ids:
            wxwork_bot_result = cls._send_wxwork_bot_notice(
                incident=incident, chat_ids=chat_ids, title=title, operation_type=operation_type, **kwargs
            )
            if wxwork_bot_result:
                all_results[NoticeWay.WX_BOT] = wxwork_bot_result

        # 2. 发送个人通知（企业微信、邮件、短信等）
        if user_ids:
            # 默认通知方式为企业微信
            notice_ways = [NoticeWay.QY_WEIXIN]

            for notice_way in notice_ways:
                personal_result = cls._send_personal_notice(
                    incident=incident,
                    user_ids=user_ids,
                    notice_way=notice_way,
                    title=title,
                    operation_type=operation_type,
                    **kwargs,
                )
                if personal_result:
                    all_results[notice_way] = personal_result

        return all_results

    @classmethod
    def _send_wxwork_bot_notice(
        cls,
        incident: IncidentDocument,
        chat_ids: list[str],
        title: str = None,
        operation_type: IncidentOperationType = None,
        **kwargs,
    ) -> dict:
        """
        发送企业微信群机器人通知

        :param incident: 故障文档对象
        :param chat_ids: 企业微信群ID列表
        :param title: 通知标题
        :param is_update: 是否为更新通知
        :return: 发送结果
        """
        if not chat_ids:
            logger.debug(f"No chat_ids provided for incident {incident.incident_id}")
            return {}

        if not settings.WXWORK_BOT_WEBHOOK_URL:
            logger.warning("WXWORK_BOT_WEBHOOK_URL not configured")
            return {}

        try:
            # 构建通知上下文
            context = cls.get_incident_context(incident, title, operation_type, **kwargs)

            # 创建发送器
            sender = IncidentSender(
                context=context,
                title_template_path="notice/incident/markdown_title.jinja",
                content_template_path="notice/incident/markdown_content.jinja",
            )

            # 发送通知
            result = sender.send(
                notice_way=NoticeWay.WX_BOT,
                notice_receivers=chat_ids,
            )

            logger.info(f"Sent wxwork_bot notice for incident {incident.incident_id} to {len(chat_ids)} chat(s)")

            return result

        except Exception as e:
            logger.exception(f"Failed to send wxwork_bot notice for incident {incident.incident_id}: {e}")
            return {}

    @classmethod
    def _send_personal_notice(
        cls,
        incident: IncidentDocument,
        user_ids: list[str],
        notice_way: str,
        title: str = None,
        operation_type: IncidentOperationType = None,
        **kwargs,
    ) -> dict:
        """
        发送个人通知（企业微信、邮件、短信等）

        :param incident: 故障文档对象
        :param user_ids: 用户ID列表
        :param notice_way: 通知方式
        :param title: 通知标题
        :param is_update: 是否为更新通知
        :return: 发送结果
        """
        if not user_ids:
            logger.debug(f"No user_ids provided for incident {incident.incident_id}")
            return {}

        try:
            # 构建通知上下文
            context = cls.get_incident_context(incident, title, operation_type, **kwargs)

            # 根据通知方式选择模板
            if notice_way == NoticeWay.MAIL:
                # 邮件使用HTML模板
                title_template = "notice/incident/mail_title.jinja"
                content_template = "notice/incident/mail_content.jinja"
            elif notice_way == NoticeWay.SMS:
                # 短信使用纯文本模板
                title_template = "notice/incident/sms_title.jinja"
                content_template = "notice/incident/sms_content.jinja"
            else:
                # 企业微信等使用markdown模板
                title_template = "notice/incident/markdown_title.jinja"
                content_template = "notice/incident/markdown_content.jinja"

            # 创建发送器
            sender = IncidentSender(
                context=context,
                title_template_path=title_template,
                content_template_path=content_template,
            )

            # 发送通知
            result = sender.send(
                notice_way=notice_way,
                notice_receivers=user_ids,
            )

            logger.info(f"Sent {notice_way} notice for incident {incident.incident_id} to {len(user_ids)} user(s)")

            return result

        except Exception as e:
            logger.exception(f"Failed to send {notice_way} notice for incident {incident.incident_id}: {e}")
            return {}
