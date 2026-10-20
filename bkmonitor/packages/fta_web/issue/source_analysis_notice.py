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
import re
from urllib.parse import urlencode

from django.conf import settings
from django.utils import timezone

from bkmonitor.documents.issue import IssueDocument
from bkmonitor.models import IssueSourceAnalysisExecution
from bkmonitor.utils.send import Sender
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from bkmonitor.utils.text import cut_str_by_max_bytes
from constants.action import NoticeWay
from constants.issue import SourceAnalysisFailureMessage, SourceAnalysisResultType, SourceAnalysisStatus

logger = logging.getLogger(__name__)


def _single_line(value, max_bytes: int) -> str:
    """约束上游摘要长度与换行，避免挤掉通知末尾的详情链接。"""

    return cut_str_by_max_bytes(re.sub(r"[\r\n\t]+", " ", str(value or "")), max_bytes, "utf-8")


def send_source_analysis_notice(execution: IssueSourceAnalysisExecution) -> None:
    """终态提交后尽力通知点击人；不重试、不回改分析状态，也不向外抛出发送异常。"""

    if not execution.create_user or execution.status not in SourceAnalysisStatus.TERMINAL_STATUSES:
        logger.info("Skip source analysis notification: analysis_id=%s", execution.analysis_id)
        return

    try:
        issue_name = execution.issue_id
        try:
            issue = IssueDocument.get_issue_or_raise(execution.issue_id, bk_biz_id=execution.bk_biz_id)
            issue_name = issue.name or issue_name
        except Exception as error:  # NOCC:broad-except(标题查询失败不阻断终态通知)
            logger.warning(
                "Source analysis notification issue lookup failed: analysis_id=%s, error_type=%s",
                execution.analysis_id,
                type(error).__name__,
            )

        query = urlencode(
            {
                "alarmType": "issues",
                "showDetail": "true",
                "detailId": execution.issue_id,
                "detailBizId": execution.bk_biz_id,
            }
        )
        result_card = (execution.result_payload or {}).get("result_card", {})
        responsibility = result_card.get("responsibility") or {}
        sender = Sender(
            bk_tenant_id=bk_biz_id_to_bk_tenant_id(execution.bk_biz_id),
            title_template_path="notice/source_analysis/default_title.jinja",
            content_template_path="notice/source_analysis/default_content.jinja",
            context={
                "bk_biz_id": execution.bk_biz_id,
                "notice_way": NoticeWay.QY_WEIXIN,
                "succeeded": execution.status == SourceAnalysisStatus.SUCCESS,
                "issue_name": _single_line(issue_name, 120),
                "triggered_at": timezone.localtime(execution.create_time, timezone.get_default_timezone()).strftime(
                    "%H:%M"
                ),
                "description": _single_line(result_card.get("description"), 512),
                "high_confidence": execution.result_type == SourceAnalysisResultType.HIGH_CONFIDENCE,
                "commit_id": _single_line(responsibility.get("commit_id"), 64),
                "author_name": _single_line(
                    responsibility.get("bk_username") or responsibility.get("author_name"), 120
                ),
                "failure_message": _single_line(execution.failure_message, 512),
                "local_failure": execution.failure_message in SourceAnalysisFailureMessage.LOCALIZED_MESSAGES,
                "detail_url": (
                    f"{settings.BK_MONITOR_HOST.rstrip('/')}/?bizId={execution.bk_biz_id}#/trace/alarm-center?{query}"
                ),
            },
        )
        results = sender.send(NoticeWay.QY_WEIXIN, [execution.create_user])
        if not results or not results.get(execution.create_user, {}).get("result"):
            logger.warning("Source analysis notification was not sent: analysis_id=%s", execution.analysis_id)
    except Exception as error:  # NOCC:broad-except(通知失败不能改变任务终态或触发分析重跑)
        logger.warning(
            "Source analysis notification failed: analysis_id=%s, error_type=%s",
            execution.analysis_id,
            type(error).__name__,
        )
