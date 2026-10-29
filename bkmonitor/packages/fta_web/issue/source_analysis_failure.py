"""将 BKFara 已返回的失败节点整理为可持久化、可展示的纯文本摘要。"""

import re
from html import unescape

from django.core.exceptions import SuspiciousOperation
from django.utils.html import strip_tags
from django.utils.translation import gettext as _

from constants.issue import SourceAnalysisFailureMessage


MAX_FAILURE_MESSAGE_LENGTH = 2000
MAX_FAILED_TASKS = 5
# 错误文本可能混合命令行、转义 JSON 和多行 Header，不能靠下一个引号判断凭据的结束。
# 命中敏感键后保守隐藏整个字段余下的内容；允许序列化产生的多层反斜杠。
CREDENTIAL_PATTERN = re.compile(
    r"(?is)\b[\w-]*(?:authorization|token|secret|password|api[_-]?key|access[_-]?key|bk_ticket)[\w-]*"
    r"[\\\"']*\s*[:=].*"
)


def _summary_text(value, max_length: int) -> str:
    if not isinstance(value, str | int) or isinstance(value, bool):
        return ""
    # 只处理摘要所需的有限前缀，避免异常大字段拖慢终态落库。
    text = unescape(str(value)[:8000])
    try:
        text = strip_tags(text)
    except (SuspiciousOperation, AssertionError):
        # Django 深度保护和 HTMLParser 的非法标记段都可能拒绝上游文本。
        # 仅舍弃异常字段，不阻断失败终态落库，也不能回退展示原始 HTML。
        return ""
    # HTML 清理可能把被标签拆开的敏感键重新连接，脱敏必须在其后进行。
    text = CREDENTIAL_PATTERN.sub("credential=******", text)
    return " ".join(text.split())[:max_length]


def build_bkfara_failure_message(failure: dict) -> str:
    """兼容两种节点错误结构；合并重复节点，并保留旧协议的顶层消息兜底。"""

    message = _summary_text(failure.get("message"), 500) or SourceAnalysisFailureMessage.BKFARA_TASK_FAILED
    details = failure.get("details")
    if not isinstance(details, dict):
        return message

    tasks = {}
    for field, id_key, name_key, message_key in (
        ("failed_tasks", "task_id", "task_name", "error_message"),
        ("error_info_list", "taskId", "taskName", "errorMsg"),
    ):
        items = details.get(field)
        if not isinstance(items, list):
            continue
        for item in items[:20]:
            if not isinstance(item, dict):
                continue
            name = _summary_text(item.get(name_key), 100)
            error = _summary_text(item.get(message_key), 400)
            code = _summary_text(item.get("errorCode"), 40)
            if not (name or error or code):
                continue
            task_id = _summary_text(item.get(id_key), 100)
            key = task_id or (name, error)
            if key not in tasks:
                if len(tasks) >= MAX_FAILED_TASKS:
                    continue
                tasks[key] = {"name": name, "error": error, "code": code}
            else:
                for attr, value in (("name", name), ("error", error), ("code", code)):
                    tasks[key][attr] = tasks[key][attr] or value

    summaries = [message]
    for task in tasks.values():
        name = task["name"] or _("流水线节点")
        code = f" [{task['code']}]" if task["code"] else ""
        error = f": {task['error']}" if task["error"] else ""
        summaries.append(f"{name}{code}{error}")
    return " | ".join(summaries)[:MAX_FAILURE_MESSAGE_LENGTH]
