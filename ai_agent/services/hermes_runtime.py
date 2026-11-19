"""Hermes 的部署能力检查和受控宿主配置；不包含 SDK 源码。"""

import importlib.util
import os
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def runtime_available():
    return importlib.util.find_spec("hermes_core") is not None


def require_runtime():
    if not runtime_available():
        raise ImproperlyConfigured("Hermes SDK 未安装，请使用包含已授权 SDK 制品的运行镜像")
    if getattr(settings, "AI_AGENT_OTEL_ENABLED", False) and importlib.util.find_spec("bkai_otel_hermes") is None:
        raise ImproperlyConfigured("AI_AGENT_OTEL_ENABLED 已启用，但 Hermes 观测适配包未安装")


def prepare_home():
    """宿主保存业务会话，SDK HOME 只保存固定身份及关闭通用编程能力的配置。"""
    import yaml

    root = Path(getattr(settings, "AI_AGENT_HERMES_HOME", "/tmp/bkmonitor-hermes")).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    files = {
        "SOUL.md": (
            "你是蓝鲸监控平台的智能助手。具体职责、业务范围及输出要求以本轮系统指令为准。\n"
            "只依据提供的上下文和授权工具结果回答；证据不足或查询失败时明确说明。\n"
            "使用简体中文，先给结论和证据。不执行本机命令，不读取或修改本地业务文件。\n"
        ),
        "config.yaml": yaml.safe_dump(
            {
                "agent": {
                    "coding_context": "off",
                    "task_completion_guidance": False,
                    "environment_probe": False,
                    "parallel_tool_call_guidance": False,
                    "tool_use_enforcement": False,
                }
            },
            allow_unicode=True,
        ),
    }
    for name, content in files.items():
        target = root / name
        if target.exists() and target.read_text(encoding="utf-8") == content:
            continue
        descriptor, temporary = tempfile.mkstemp(dir=root, prefix=f".{name}.")
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(content)
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return str(root)
