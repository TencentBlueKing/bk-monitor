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

from django.conf import settings
from django.utils.translation import gettext as _

from bkmonitor.documents.incident import IncidentDocument
from bkmonitor.utils.send import IncidentSender
from constants.action import NoticeWay
from bkm_space.api import SpaceApi
from constants.incident import IncidentStatus, IncidentLevel

logger = logging.getLogger("incident.notice")


class IncidentNoticeHelper:
    """故障通知辅助类"""

    @classmethod
    def get_incident_context(
        cls,
        incident: IncidentDocument,
        title: str = None,
        is_update: bool = False,
    ) -> dict:
        """
        构建故障通知的上下文

        :param incident: 故障文档对象
        :param title: 通知标题
        :param is_update: 是否为更新通知
        :return: 通知上下文字典
        """

        # 获取业务名称
        try:
            space = SpaceApi.get_space_detail(bk_biz_id=int(incident.bk_biz_id))
            business_name = space.space_name
        except Exception as e:
            business_name = str(incident.bk_biz_id)
            logger.warning(f"获取业务名称失败: {e}")

        # 计算故障持续时间
        duration = cls._format_duration(incident.create_time, incident.end_time)

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

        # 默认标题
        if not title:
            if is_update:
                title = _("故障更新通知")
            else:
                title = _("故障生成通知")

        context = {
            "title": title,
            "incident_name": incident.incident_name or _("未命名故障"),
            "level": level,
            "notify_time": notify_time,
            "business_name": business_name,
            "incident_reason": incident_reason,
            "status": status,
            "duration": duration,
            "number": incident.alert_count or 0,
            "assignees": assignees,
            "url": url,
            "bk_biz_id": incident.bk_biz_id,
            "incident_id": incident.incident_id,
        }

        return context

    @classmethod
    def _format_duration(cls, create_time: int, end_time: int = None) -> str:
        """
        格式化故障持续时间

        :param create_time: 创建时间戳
        :param end_time: 结束时间戳
        :return: 格式化的持续时间字符串
        """
        if not create_time:
            return _("未知")

        end = end_time if end_time else int(time.time())
        duration_seconds = end - create_time

        if duration_seconds < 60:
            return _("{}秒").format(duration_seconds)
        elif duration_seconds < 3600:
            minutes = duration_seconds // 60
            return _("{}分钟").format(minutes)
        elif duration_seconds < 86400:
            hours = duration_seconds // 3600
            minutes = (duration_seconds % 3600) // 60
            if minutes > 0:
                return _("{}小时{}分钟").format(hours, minutes)
            return _("{}小时").format(hours)
        else:
            days = duration_seconds // 86400
            hours = (duration_seconds % 86400) // 3600
            if hours > 0:
                return _("{}天{}小时").format(days, hours)
            return _("{}天").format(days)

    @classmethod
    def _get_incident_reason(cls, incident: IncidentDocument) -> str:
        """
        获取故障根因描述

        :param incident: 故障文档对象
        :return: 故障根因字符串
        """
        # TODO: 根据实际的故障快照数据结构获取根因信息
        # 这里需要根据实际的数据结构来实现
        if incident.snapshot and incident.snapshot.content:
            # 尝试从快照中获取根因信息
            try:
                content = incident.snapshot.content
                if hasattr(content, "incident_root"):
                    return str(content.incident_root)
                elif hasattr(content, "rca_summary"):
                    rca_summary = content.rca_summary
                    if isinstance(rca_summary, dict) and "root_cause" in rca_summary:
                        return str(rca_summary["root_cause"])
            except Exception as e:
                logger.warning(f"Failed to get incident reason: {e}")

        return _("分析中...")

    @classmethod
    def _get_incident_url(cls, incident: IncidentDocument) -> str:
        """
        构建故障详情URL

        :param incident: 故障文档对象
        :return: 故障详情URL
        """
        # 构建故障详情页面URL
        site_url = settings.SITE_URL.rstrip("/")
        return f"{site_url}/?bizId={incident.bk_biz_id}#/trace/incident/detail/{incident.id}"

    @classmethod
    def send_incident_notice(
        cls,
        incident: IncidentDocument,
        chat_ids: list[str] = None,
        user_ids: list[str] = None,
        title: str = None,
        is_update: bool = False,
    ) -> dict[str, dict]:
        """
        发送故障通知（支持多种通知方式）

        :param incident: 故障文档对象
        :param chat_ids: 企业微信群ID列表（用于群机器人通知）
        :param user_ids: 用户ID列表（用于个人通知）
        :param title: 通知标题
        :param is_update: 是否为更新通知
        :return: 发送结果，格式: {notice_way: {receiver: {result, message}}}
        """
        all_results = {}

        # 1. 发送企业微信群机器人通知
        if chat_ids:
            wxwork_bot_result = cls._send_wxwork_bot_notice(
                incident=incident,
                chat_ids=chat_ids,
                title=title,
                is_update=is_update,
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
                    is_update=is_update,
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
        is_update: bool = False,
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
            context = cls.get_incident_context(incident, title, is_update)

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
        is_update: bool = False,
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
            context = cls.get_incident_context(incident, title, is_update)

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
