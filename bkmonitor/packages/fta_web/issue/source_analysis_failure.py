"""将 BKFara 已返回的失败节点整理为可持久化、可展示的纯文本摘要。"""

import re
from html import unescape

from django.utils.html import strip_tags
from django.utils.translation import gettext as _

from constants.issue import SourceAnalysisFailureMessage


MAX_FAILURE_MESSAGE_LENGTH = 2000
MAX_FAILED_TASKS = 5
# 不把节点错误中可能出现的鉴权头、JSON/命令行凭据直接暴露到页面和通知。
AUTHORIZATION_PATTERN = re.compile(r"(?im)(?:x-bkapi-authorization|authorization)[\"']?\s*[:=][^\r\n]*")
CREDENTIAL_PATTERN = re.compile(
    r"(?i)\b[\w-]*(?:token|secret|password|api[_-]?key|access[_-]?key|bk_ticket)[\w-]*"
    r"[\"']?\s*[:=]\s*(?:\"[^\"]*(?:\"|$)|'[^']*(?:'|$)|[^,;\s}\]]+)"
)


def _summary_text(value, max_length: int) -> str:
    if not isinstance(value, str | int) or isinstance(value, bool):
        return ""
    # 只处理摘要所需的有限前缀，避免异常大字段拖慢终态落库。
    text = unescape(str(value)[:8000])
    text = AUTHORIZATION_PATTERN.sub("authorization=******", text)
    text = CREDENTIAL_PATTERN.sub("credential=******", text)
    # 蓝盾插件常把 HTML 帮助链接附在第二段；不展示链接和整段排障指引。
    text = re.split(r"\r?\n\s*\r?\n", text, maxsplit=1)[0]
    return " ".join(strip_tags(text).split())[:max_length]


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
