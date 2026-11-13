#!/usr/bin/env python3
"""
MCP Data Fetcher - 通用MCP数据拉取工具
直接通过HTTP调用MCP服务器,无需经过AI/大模型,避免Token消耗

支持的传输协议:
    - SSE (Server-Sent Events): 通过SSE建立连接,获取endpoint后发送请求
    - streamableHttp: 直接通过HTTP POST发送JSON-RPC请求,响应为SSE格式 (Cursor/CodeBuddy)
    - http: 标准 JSON-RPC 响应；部分网关仍返回 SSE 正文（与 streamableHttp 相同），已自动解析
    - remote: OpenCode/bkai-code 远端 MCP schema,按 http 调用

主要特性:
    - 支持显式配置路径及 Cursor、CodeBuddy、bkai-code、Windsurf、VSCode、Claude Code、OpenClaw、Hermes 配置发现
    - 支持目标环境的 bk-monitor-{env}-{service} 和 bkm-{env}-{service} 配置名称
    - 自动处理SSE格式响应 / JSONC 与 Hermes YAML 配置 / 自动 query_param / body_param 包装
    - 业务层错误检查 / 请求重试 / 结构化输出
    - 友好的错误提示 / 配置验证功能

用法:
    from mcp_data_fetcher import MCPClient

    client = MCPClient()        # 自动检测配置文件
    # 或: client = MCPClient(mcp_config_path="~/.cursor/mcp.json")

    # 验证配置
    client.validate_config()

    # 高级调用 (自动包装参数, 自动校验业务错误)
    result = client.call_bkm_tool("prod", "metrics-query", "execute_range_query", {
        "bk_biz_id": "<bk_biz_id>",
        "promql": "avg(avg_over_time(bkmonitor:system:cpu_summary:usage[1m]))",
        "start_time": "1704067200",
        "end_time": "1704070800",
        "step": "1m"
    })

    # 保存结果 (带结构提示)
    client.save_result(result, "output.json")

    # 底层调用 (手动包装参数)
    result = client.call_tool("bkm-prod-metrics-query", "execute_range_query", {
        "body_param": { ... }
    })

故障排查:
    如遇到问题,请查阅 ../references/troubleshooting.md
"""

import json
import re
import time
import uuid
import requests
import os
import subprocess
import sys
import threading
import warnings
from urllib.parse import urlsplit
from pathlib import Path
from typing import Any, Final


class MCPAuthenticationError(ValueError):
    """服务器返回 HTTP 401（凭据无效或缺失）。"""


class MCPConfigError(ValueError):
    """本地 MCP 配置不兼容；错误不包含配置值或 YAML 源行。"""


class MCPBusinessError(RuntimeError):
    """MCP 业务层返回失败 (result=false)。"""


class MCPProtocolError(ValueError):
    """MCP 协议层错误：响应无法解析为合法的 JSON-RPC 对象（含 SSE 解析失败）。

    通常由网络中断、网关 chunk 截断或服务端响应不规范引起，属于可重试错误。
    """


class MCPServerUnavailableError(ConnectionError):
    """MCP 服务端 5xx 错误（502/503/504），属于可重试错误。"""


MCP_CONFIG_ENV_VARS: Final[tuple[str, ...]] = (
    "BK_MCP_CONFIG_PATH",
    "BKM_MCP_CONFIG_PATH",
    "MCP_CONFIG_PATH",
)


# ---------------------------------------------------------------------------
# 工作空间 / Git Root 检测
# ---------------------------------------------------------------------------


def _detect_workspace_root() -> str:
    """检测工作空间根目录 (git root → cwd)。"""
    try:
        result = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return os.getcwd()


# ---------------------------------------------------------------------------
# MCP 配置文件发现
# ---------------------------------------------------------------------------


def _build_mcp_config_candidates(cwd: str, workspace: str) -> list[str]:
    """构建按优先级排序的 MCP 配置文件候选路径列表。

    对齐 bkai-cli MCP_CLIENTS 官方定义，同时搜索 cwd 和 workspace（git root），去重后返回。
    支持的客户端:
      - Cursor (全局 + 项目级)
      - CodeBuddy (全局 + 项目级)
      - bkai-code (OpenCode JSONC)
      - Windsurf (项目级, 兼容旧/手工配置)
      - VSCode / Copilot (项目级)
      - Claude Code (项目级 .mcp.json + 全局 ~/.claude.json)
      - OpenClaw (全局 ~/.mcporter/mcporter.json)
      - Hermes (全局 ~/.hermes/config.yaml，HERMES_HOME 显式路径在调用方优先处理)
    """
    home = os.path.expanduser("~")
    dirs = [cwd]
    if workspace != cwd:
        dirs.append(workspace)

    candidates: list[str] = []
    seen: set = set()

    def _add(p: str) -> None:
        norm = os.path.normpath(p)
        if norm not in seen:
            seen.add(norm)
            candidates.append(norm)

    # --- Cursor ---
    _add(os.path.join(home, ".cursor", "mcp.json"))  # 全局
    for d in dirs:
        _add(os.path.join(d, ".cursor", "mcp.json"))  # 项目级

    # --- CodeBuddy ---
    _add(os.path.join(home, ".codebuddy", "mcp.json"))  # 全局
    for d in dirs:
        _add(os.path.join(d, ".codebuddy", "mcp.json"))  # 项目级

    # --- bkai-code / OpenCode schema ---
    _add(os.path.join(home, ".bkai-code", "xdg-config", "opencode", "opencode.jsonc"))

    # --- Windsurf ---
    for d in dirs:
        _add(os.path.join(d, ".windsurf", "mcp.json"))  # 项目级

    # --- VSCode / Copilot ---
    for d in dirs:
        _add(os.path.join(d, ".vscode", "mcp.json"))  # 项目级

    # --- Claude Code 项目级 (.mcp.json) ---
    for d in dirs:
        _add(os.path.join(d, ".mcp.json"))

    # --- Claude Code 全局 ---
    _add(os.path.join(home, ".claude.json"))

    # --- OpenClaw 全局 ---
    if sys.platform == "win32":
        _add(os.path.join(home, ".openclaw", "workspace", "config", "mcporter.json"))
        _add(os.path.join(home, ".mcporter", "mcporter.json"))
    else:
        _add(os.path.join(home, ".mcporter", "mcporter.json"))

    # 保持已有 JSON 客户端的优先级；无显式 HERMES_HOME 时作为最后的候选。
    _add(os.path.join(home, ".hermes", "config.yaml"))
    return candidates


def _strip_jsonc_comments(text: str) -> str:
    """去掉 JSONC 注释,保留字符串中的 // 和 /* */。"""
    out: list[str] = []
    i = 0
    in_string = False
    escape = False
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""

        if in_string:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue

        if ch == "/" and nxt == "/":
            i += 2
            while i < len(text) and text[i] not in "\r\n":
                i += 1
            continue

        if ch == "/" and nxt == "*":
            i += 2
            while i + 1 < len(text) and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2 if i + 1 < len(text) else 0
            continue

        out.append(ch)
        i += 1

    return "".join(out)


def _remove_json_trailing_commas(text: str) -> str:
    """去掉对象/数组结尾前的 trailing comma,保留字符串内容。"""
    out: list[str] = []
    i = 0
    in_string = False
    escape = False
    while i < len(text):
        ch = text[i]

        if in_string:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue

        if ch == ",":
            j = i + 1
            while j < len(text) and text[j] in " \t\r\n":
                j += 1
            if j < len(text) and text[j] in "}]":
                i += 1
                continue

        out.append(ch)
        i += 1

    return "".join(out)


def _load_json_config(filepath: str) -> dict[str, Any]:
    """读取 JSON/JSONC 配置文件。"""
    with open(filepath, encoding="utf-8") as f:
        raw_text = f.read()

    text = raw_text
    if filepath.lower().endswith(".jsonc"):
        text = _remove_json_trailing_commas(_strip_jsonc_comments(raw_text))

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        if filepath.lower().endswith(".jsonc"):
            raise
        text = _remove_json_trailing_commas(_strip_jsonc_comments(raw_text))
        data = json.loads(text)

    return data if isinstance(data, dict) else {}


def _hermes_enabled(value: Any, default: bool = True) -> bool:
    """Hermes bool/string 开关语义；格式错误不采用隐式启用兜底。"""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.strip().lower() in ("true", "1", "yes", "on"):
            return True
        if value.strip().lower() in ("false", "0", "no", "off"):
            return False
    raise MCPConfigError("Hermes MCP enabled 配置不是有效布尔值")


def _hermes_env(value: str) -> str:
    def replace(match):
        resolved = os.environ.get(match[1])
        if not resolved:
            raise MCPConfigError("Hermes MCP 配置依赖的环境变量未设置")
        return resolved

    return re.sub(r"\$\{(\w+)\}", replace, value)


def _load_hermes_config(filepath: str) -> dict[str, Any]:
    """只读 Hermes YAML，转换为客户端原有的 mcpServers 内存结构。"""
    try:
        import yaml
    except ImportError:
        raise MCPConfigError("读取 Hermes YAML 需要 PyYAML，请安装本 Skill 的 requirements.txt") from None
    try:
        with open(filepath, encoding="utf-8") as stream:
            raw = yaml.safe_load(stream)
    except (OSError, UnicodeError, yaml.YAMLError):
        raise MCPConfigError("Hermes MCP YAML 缺失、不可读或格式错误") from None
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise MCPConfigError("Hermes 配置顶层必须是对象")
    entries = raw.get("mcp_servers")
    if entries is None:
        entries = {}
    if not isinstance(entries, dict):
        raise MCPConfigError("Hermes mcp_servers 必须是对象")
    if _hermes_enabled(os.environ.get("HERMES_SAFE_MODE"), default=False):
        return {"mcpServers": {}}
    servers = {}
    stdio_count = 0
    for name, entry in entries.items():
        if not isinstance(name, str) or not name or not isinstance(entry, dict):
            raise MCPConfigError("Hermes MCP 服务条目格式错误")
        if not _hermes_enabled(entry.get("enabled")):
            continue
        if "command" in entry and "url" not in entry:
            stdio_count += 1
            continue
        # 不静默丢弃旧客户端不能执行的 OAuth/TLS/tool policy 等控制。
        if set(entry) - {"url", "headers", "type", "transport", "enabled"}:
            raise MCPConfigError("Hermes MCP 网络条目含客户端不支持的选项")
        kind, transport = entry.get("type"), entry.get("transport")
        supported = ("sse", "streamableHttp", "http", "remote")
        if (kind is not None and kind not in supported) or (transport is not None and transport not in supported):
            raise MCPConfigError("Hermes MCP 网络传输类型不支持")
        if kind and transport and (kind == "sse") != (transport == "sse"):
            raise MCPConfigError("Hermes MCP 网络传输类型冲突")
        if kind == "sse" and transport != "sse":
            raise MCPConfigError("Hermes SSE 需要显式 transport=sse")
        # SDK 0.7.0 仅 transport=sse 选择 SSE；URL-only 默认 Streamable HTTP。
        resolved = "sse" if transport == "sse" else (kind or transport or "streamableHttp")
        url = entry.get("url")
        headers = entry.get("headers")
        if headers is None:
            headers = {}
        if not isinstance(url, str) or not isinstance(headers, dict):
            raise MCPConfigError("Hermes MCP url/headers 格式错误")
        url = _hermes_env(url)
        try:
            parsed = urlsplit(url)
            if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username is not None:
                raise ValueError
        except ValueError:
            raise MCPConfigError("Hermes MCP URL 无效") from None
        copied_headers = {}
        for key, value in headers.items():
            if not isinstance(key, str) or not key or not isinstance(value, str):
                raise MCPConfigError("Hermes MCP headers 必须为字符串映射")
            value = _hermes_env(value)
            if "\r" in key + value or "\n" in key + value:
                raise MCPConfigError("Hermes MCP header 不可包含换行")
            copied_headers[key] = value
        servers[name] = {"type": resolved, "url": url, "headers": copied_headers}
    if stdio_count:
        warnings.warn(f"Hermes MCP: 跳过 {stdio_count} 个 stdio 服务；本客户端仅支持 HTTP/SSE", stacklevel=2)
    return {"mcpServers": servers}


def _load_mcp_config(filepath: str) -> dict[str, Any]:
    if str(filepath).lower().endswith((".yaml", ".yml")):
        return _load_hermes_config(filepath)
    return _load_json_config(filepath)


def _has_mcp_servers(filepath: str) -> bool:
    """检测 JSON/JSONC/Hermes YAML 是否包含可用服务；YAML 配置错误不静默回退。"""
    try:
        raw = _load_mcp_config(filepath)
        if not isinstance(raw, dict):
            return False
        if isinstance(raw.get("mcpServers"), dict) and raw["mcpServers"]:
            return True
        if isinstance(raw.get("mcp"), dict) and raw["mcp"]:
            return True
        projects = raw.get("projects")
        if isinstance(projects, dict):
            for proj in projects.values():
                if isinstance(proj, dict):
                    ms = proj.get("mcpServers")
                    if isinstance(ms, dict) and ms:
                        return True
        return False
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return False


def _find_mcp_config() -> str:
    """自动查找第一个存在且包含服务器配置的 MCP 配置文件。

    不仅检查文件是否存在，还会校验文件内容是否包含有效的 mcpServers 配置。
    旧 JSON 候选中的空文件或结构不合法文件自动跳过；显式路径和 Hermes
    YAML 配置错误直接报错，不隐藏错误授权范围。
    """
    for env_name in MCP_CONFIG_ENV_VARS:
        env_value = os.environ.get(env_name, "").strip()
        if not env_value:
            continue
        filepath = os.path.normpath(os.path.expanduser(env_value))
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"{env_name} 指向的 MCP 配置文件不存在: {filepath}")
        if not _has_mcp_servers(filepath):
            raise FileNotFoundError(f"{env_name} 指向的 MCP 配置文件不含有效 mcpServers: {filepath}")
        return filepath

    # 显式 Hermes home 表示当前运行时，优先于遗留客户端文件；缺失或
    # 禁用清单不能偷偷回退到另一个环境/用户的 MCP 配置。
    hermes_home = os.environ.get("HERMES_HOME", "").strip()
    if hermes_home:
        filepath = os.path.join(os.path.expanduser(hermes_home), "config.yaml")
        if not _has_mcp_servers(filepath):
            raise MCPConfigError("HERMES_HOME 中没有可用的 HTTP/SSE MCP 服务")
        return filepath

    cwd = os.getcwd()
    workspace = _detect_workspace_root()
    candidates = _build_mcp_config_candidates(cwd, workspace)

    found_but_empty: list[str] = []
    for filepath in candidates:
        if not os.path.isfile(filepath):
            continue
        if _has_mcp_servers(filepath):
            return filepath
        found_but_empty.append(filepath)

    candidates_str = "\n  ".join(candidates)
    if found_but_empty:
        empty_str = "\n  ".join(found_but_empty)
        raise FileNotFoundError(
            f"找到以下配置文件但其中不含有效 mcpServers:\n  {empty_str}\n\n"
            f"全部搜索路径:\n  {candidates_str}\n"
            f"请运行 `npx @tencent/bkai mcp` 导入配置"
        )
    raise FileNotFoundError(
        f"未找到MCP配置文件,已搜索以下路径:\n  {candidates_str}\n请运行 `npx @tencent/bkai mcp` 导入配置"
    )


# ---------------------------------------------------------------------------
# Server 名称解析
# ---------------------------------------------------------------------------

SERVER_DOMAINS: Final[dict[str, str]] = {
    "metrics-query": "指标查询",
    "log-query": "日志查询",
    "alarm": "告警",
    "event-query": "事件查询",
    "tracing": "链路追踪",
    "metadata-query": "元数据查询",
    "dashboard-query": "仪表盘查询",
    "dashboard-edit": "仪表盘编辑",
    "relation-query": "关联关系查询",
    "metric-anomaly-detection": "指标异常检测",
    "openclaw-recovering": "OpenClaw 自愈分析",
}
_ENV_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")
_SERVER_NAME_PATTERN = re.compile(
    r"^(?:user-)?(?:bk-monitor|bkm)-([a-z][a-z0-9_-]*)-("
    + "|".join(re.escape(name) for name in sorted(SERVER_DOMAINS, key=len, reverse=True))
    + r")$"
)

QUERY_PARAM_TOOLS: Final[set] = {
    # ---- 元数据 (metadata-query) ----
    "search_spaces",
    "list_bcs_clusters",
    # ---- 日志 (log-query) ----
    "list_index_sets",
    "get_index_set_fields",
    # ---- 指标 (metrics-query) ----
    "list_time_series_metrics",
    # ---- 链路追踪 (tracing) ----
    "list_apm_applications",
    "list_apm_services",
    "get_apm_filter_fields",
    # ---- 告警 (alarm) ----
    "get_alert_info",
    "get_alert_k8s_scenarios",
    "get_alert_k8s_metrics",
    "get_alert_k8s_target",
    "get_alert_host_target",
    "get_alert_log_relations",
    # ---- 仪表盘 (dashboard-query) ----
    "get_dashboard_detail_by_uid",
    "get_dashboard_tree_list",
    "get_dashboard_directory_tree_list",
}


def resolve_server_target(env: str, server: str) -> tuple[str, str, str, bool]:
    """Resolve an explicit environment or a complete configured server name."""
    target_env = (env or "").strip().lower()
    target = server.strip().lower()
    match = _SERVER_NAME_PATTERN.fullmatch(target)
    if match:
        resolved_env, domain = match.groups()
        if target_env and target_env != resolved_env:
            raise ValueError("完整 Server 名称与指定环境不一致")
        return resolved_env, domain, target, False
    if not _ENV_PATTERN.fullmatch(target_env):
        raise ValueError("必须显式指定合法的目标环境")
    if target not in SERVER_DOMAINS:
        raise ValueError("未知服务类型；自定义名称请通过 call_tool 使用配置中的完整名称")
    return target_env, target, f"bkm-{target_env}-{target}", False


def build_server_name(env: str, server: str) -> str:
    """从 env + server 构建完整服务器名称。"""
    _, _, full_name, _ = resolve_server_target(env, server)
    return full_name


def wrap_tool_arguments(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """根据工具类型自动包装为 query_param 或 body_param。"""
    key = "query_param" if tool_name in QUERY_PARAM_TOOLS else "body_param"
    return {key: payload}


def normalize_payload(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """自动修正高频易错参数(类型转换、字段别名等)。"""
    normalized = dict(payload)

    if "bk_biz_id" in normalized and normalized["bk_biz_id"] is not None:
        normalized["bk_biz_id"] = str(normalized["bk_biz_id"])

    for ts_field in ("start_time", "end_time"):
        if ts_field in normalized and normalized[ts_field] is not None:
            normalized[ts_field] = str(int(float(normalized[ts_field])))

    if tool_name == "get_alert_info":
        if "alert_id" in normalized and "id" not in normalized:
            normalized["id"] = str(normalized["alert_id"])
            del normalized["alert_id"]
        if "id" in normalized and normalized["id"] is not None:
            normalized["id"] = str(normalized["id"])

    if tool_name == "list_alerts":
        biz_id = normalized.get("bk_biz_id")
        if biz_id is not None:
            biz_str = str(biz_id)
            normalized["bk_biz_id"] = biz_str
            if "bk_biz_ids" not in normalized:
                normalized["bk_biz_ids"] = [biz_str]
        if isinstance(normalized.get("bk_biz_ids"), list):
            normalized["bk_biz_ids"] = [str(i) for i in normalized["bk_biz_ids"]]

    return normalized


def validate_query_window(start_time: int, end_time: int) -> None:
    """Reject reversed, empty, or oversized single-request query windows."""
    if start_time < 0 or end_time <= start_time or end_time - start_time > 86400:
        raise ValueError("查询窗口必须是 Unix 秒，且满足 0 < 结束减开始 <= 86400；更长范围请拆分")


# ---------------------------------------------------------------------------
# MCP 结果解析与输出
# ---------------------------------------------------------------------------


def _extract_json_from_text(text: str) -> Any | None:
    """从 MCP text 内容中提取 JSON 对象或数组。"""
    stripped = text.strip()
    if not stripped:
        return None

    candidates = [stripped]
    fence_match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, re.DOTALL)
    if fence_match:
        candidates.insert(0, fence_match.group(1).strip())

    decoder = json.JSONDecoder()
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

        for match in re.finditer(r"[\{\[]", candidate):
            snippet = candidate[match.start() :].lstrip()
            try:
                parsed, _ = decoder.raw_decode(snippet)
                return parsed
            except json.JSONDecodeError:
                continue

    return None


def parse_mcp_result(result: Any) -> Any:
    """解析 MCP 返回结果, 提取实际数据。

    MCP 返回格式: {"content": [{"type": "text", "text": "JSON字符串"}]}
    """
    if isinstance(result, str):
        parsed = _extract_json_from_text(result)
        return parsed if parsed is not None else result

    if not isinstance(result, dict):
        return result

    content = result.get("content", [])
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "text":
                continue
            text = item.get("text", "")
            if not isinstance(text, str):
                continue
            parsed = _extract_json_from_text(text)
            if parsed is not None:
                return parsed

    return result


def raise_if_business_error(result: dict[str, Any], context: str = "") -> None:
    """检查 MCP 业务层是否返回失败 (result=false)。"""
    parsed = parse_mcp_result(result)
    if not isinstance(parsed, dict):
        return
    body = parsed.get("response_body", parsed)
    if isinstance(body, dict) and body.get("result") is False:
        message = body.get("message", str(body))
        prefix = f"[{context}] " if context else ""
        raise MCPBusinessError(f"{prefix}MCP 调用失败: {message}")


def output_result(result: Any, output: str) -> None:
    """将结果写入 JSON 文件, 并输出路径、大小和顶层结构提示。"""
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    size = os.path.getsize(output)
    print(f"已保存: {output} ({size} bytes)")
    _print_structure_hint(result)


def _print_structure_hint(result: Any) -> None:
    """输出顶层结构提示 (供模型参考)。"""
    if isinstance(result, dict):
        keys = list(result.keys())
        print(f"顶层 keys: {keys}")
        for k in keys:
            v = result[k]
            if isinstance(v, list):
                print(f"  {k}: list[{len(v)}]")
            elif isinstance(v, dict):
                print(f"  {k}: dict, keys={list(v.keys())}")
    elif isinstance(result, list):
        print(f"顶层: list[{len(result)}]")
        if result and isinstance(result[0], dict):
            print(f"  [0] keys: {list(result[0].keys())}")


# ---------------------------------------------------------------------------
# MCPClient
# ---------------------------------------------------------------------------


class MCPClient:
    """通用 MCP 客户端 - 支持 SSE、streamableHttp 和 http 协议"""

    def __init__(self, mcp_config_path: str = None, verbose: bool = False):
        """
        初始化。

        Args:
            mcp_config_path: 显式 MCP 配置路径；为 None 时按配置发现顺序只读加载。
            verbose: 是否打印详细调试信息
        """
        if mcp_config_path is None:
            mcp_config_path = _find_mcp_config()
        else:
            mcp_config_path = os.path.expanduser(mcp_config_path)

        self.verbose = verbose
        self.mcp_config_path = mcp_config_path

        if not os.path.exists(mcp_config_path):
            raise FileNotFoundError(f"MCP配置文件不存在: {mcp_config_path}")

        try:
            raw = _load_mcp_config(mcp_config_path)
        except json.JSONDecodeError as e:
            raise ValueError(f"MCP配置文件格式错误: {e}")

        self.config = raw
        self.servers = raw.get("mcpServers", {})

        # Claude Code ~/.claude.json: projects[项目路径].mcpServers
        if not self.servers and isinstance(raw.get("projects"), dict):
            self.servers = self._resolve_claude_projects(raw["projects"])

        # bkai-code / OpenCode schema: 顶层 mcp
        if not self.servers and isinstance(raw.get("mcp"), dict):
            self.servers = raw["mcp"]

        if not self.servers:
            raise ValueError(
                f"MCP配置文件中没有找到任何服务器配置: {mcp_config_path}\n请运行 `npx @tencent/bkai mcp` 重新导入"
            )

        self.output_dir = os.path.join(os.getcwd(), "bkmonitor-files")

    @staticmethod
    def _resolve_claude_projects(projects: dict[str, Any]) -> dict[str, Any]:
        """从 Claude Code 的 projects 结构中解析 mcpServers。

        优先匹配当前工作目录: 精确匹配 > 子目录匹配(最长前缀) > 任意第一个有效项目。
        """
        try:
            cwd_real = os.path.realpath(os.getcwd())
        except (OSError, ValueError):
            cwd_real = os.path.abspath(os.getcwd())

        best_servers: dict[str, Any] | None = None
        best_key: tuple[int, int] = (-1, -1)  # (priority, path_length)

        for path_key, proj in projects.items():
            if not isinstance(proj, dict):
                continue
            ms = proj.get("mcpServers")
            if not isinstance(ms, dict) or not ms:
                continue
            try:
                root_real = os.path.realpath(path_key)
            except (OSError, ValueError):
                root_real = os.path.abspath(path_key)

            root_norm = root_real.rstrip(os.sep)
            if cwd_real == root_norm:
                cand = (2, len(root_norm))
            elif cwd_real.startswith(root_norm + os.sep):
                cand = (1, len(root_norm))
            else:
                continue

            if cand[0] > best_key[0] or (cand[0] == best_key[0] and cand[1] > best_key[1]):
                best_key = cand
                best_servers = ms

        if best_servers is not None:
            return best_servers

        for proj in projects.values():
            if isinstance(proj, dict):
                ms = proj.get("mcpServers")
                if isinstance(ms, dict) and ms:
                    return ms

        return {}

    # -----------------------------------------------------------------------
    # 服务器管理
    # -----------------------------------------------------------------------

    def list_servers(self, show_details: bool = False) -> list:
        """列出可用的 MCP 服务器。"""
        servers = []
        for name, config in self.servers.items():
            transport = config.get("type") or config.get("transport")
            if transport in ("sse", "streamableHttp", "http", "remote"):
                servers.append(name)
                if show_details:
                    print(f"  - {name} ({transport})")

        if show_details and not servers:
            print("  (未找到支持的MCP服务器)")

        return servers

    def find_server(self, env: str, domain: str) -> str:
        """Find one server in the selected environment; never fall back across environments."""
        target_env, service, full_name, _ = resolve_server_target(env, domain)
        available = self.list_servers()
        if _SERVER_NAME_PATTERN.fullmatch(domain.strip().lower()):
            if full_name not in available:
                raise ValueError("配置中没有指定的完整 Server 名称")
            return full_name
        aliases = {
            "metrics-query": ("metrics-query", "metrics"),
            "log-query": ("log-query", "log"),
            "alarm": ("alarm", "alerts"),
            "event-query": ("event-query", "event"),
            "dashboard-query": ("dashboard-query", "dashboard"),
        }.get(service, (service,))
        candidates = {
            f"{prefix}{gateway}-{target_env}-{alias}"
            for prefix in ("", "user-")
            for gateway in ("bk-monitor", "bkm")
            for alias in aliases
        }
        matches = [name for name in available if name in candidates]
        if len(matches) != 1:
            raise ValueError("目标环境未找到唯一 Server；请从 list_servers 选择完整名称后调用 call_tool")
        return matches[0]

    def validate_config(self) -> bool:
        """验证 MCP 配置。"""
        print("=" * 60)
        print("MCP配置验证")
        print("=" * 60)
        print(f"配置文件: {self.mcp_config_path}")
        print(f"服务器数量: {len(self.servers)}")
        print("\n可用服务器:")

        servers = self.list_servers(show_details=True)

        if not servers:
            print("\n❌ 没有找到可用的MCP服务器")
            return False

        print("\n✅ 配置验证通过")
        return True

    # -----------------------------------------------------------------------
    # 核心调用方法
    # -----------------------------------------------------------------------

    # 可重试异常: 网络层 (ConnectionError/Timeout) + 协议层 (SSE 解析失败) + 5xx
    _RETRYABLE_EXCEPTIONS: Final[tuple[type, ...]] = (
        ConnectionError,
        TimeoutError,
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        requests.exceptions.ChunkedEncodingError,
        MCPProtocolError,
        MCPServerUnavailableError,
    )

    def call_tool(
        self, server_name: str, tool_name: str, arguments: dict[str, Any], timeout: int = 60, retries: int = 1
    ) -> dict[str, Any]:
        """
        调用 MCP 工具 (底层接口, 参数需调用方自行包装)。

        Args:
            server_name: MCP 服务器名称 (完整名)
            tool_name: 工具名称
            arguments: 已包装好的参数 (含 body_param 或 query_param)
            timeout: 单次超时秒数
            retries: 失败重试次数 (默认 1, 覆盖 SSE 解析失败/网络错误/5xx)
        """
        if server_name not in self.servers:
            available = self.list_servers()
            raise ValueError(
                f"服务器 '{server_name}' 不存在\n"
                f"可用服务器: {available}\n"
                f"提示: 使用 client.find_server(env, domain) 自动查找"
            )

        server_config = self.servers[server_name]
        transport = server_config.get("type") or server_config.get("transport")

        if transport not in ("sse", "streamableHttp", "http", "remote"):
            raise ValueError(
                f"服务器 '{server_name}' 使用不支持的传输协议: {transport}\n"
                f"支持的协议: sse, streamableHttp, http, remote"
            )

        last_error: BaseException | None = None
        for attempt in range(1 + retries):
            try:
                if transport == "streamableHttp":
                    return self._call_tool_streamable_http(server_name, tool_name, arguments, timeout)
                elif transport in ("http", "remote"):
                    return self._call_tool_http(server_name, tool_name, arguments, timeout)
                else:
                    return self._call_tool_sse(server_name, tool_name, arguments, timeout)
            except self._RETRYABLE_EXCEPTIONS as e:
                last_error = e
                if attempt < retries:
                    wait = min(2**attempt, 10)
                    err_label = type(e).__name__
                    print(f"   ⚠️  第 {attempt + 1} 次重试 (等待 {wait}s, {err_label}): {e}")
                    time.sleep(wait)

        assert last_error is not None
        raise last_error

    def call_bkm_tool(
        self, env: str, domain: str, tool_name: str, payload: dict[str, Any], timeout: int = 60, retries: int = 1
    ) -> dict[str, Any]:
        """
        高级调用接口: 自动解析服务器名、包装参数、检查业务错误。

        Args:
            env: 用户已确认的目标环境标识
            domain: 服务域 (metrics-query/log-query/alarm/...)
            tool_name: 工具名称
            payload: 原始业务参数 (无需包装 body_param/query_param)
            timeout: 单次超时秒数
            retries: 失败重试次数
        """
        server_name = self.find_server(env, domain)
        normalized = normalize_payload(tool_name, payload)
        arguments = wrap_tool_arguments(tool_name, normalized)

        try:
            result = self.call_tool(server_name, tool_name, arguments, timeout=timeout, retries=retries)
        except Exception as exc:
            raise RuntimeError(f"MCP 调用失败: server={server_name}, tool={tool_name}\n原始错误: {exc}") from exc

        raise_if_business_error(result, context=f"{server_name}/{tool_name}")
        return result

    # -----------------------------------------------------------------------
    # 协议实现: SSE
    # -----------------------------------------------------------------------

    def _call_tool_sse(
        self, server_name: str, tool_name: str, arguments: dict[str, Any], timeout: int = 60
    ) -> dict[str, Any]:
        server_config = self.servers[server_name]
        print(f"📡 调用 {server_name}/{tool_name}... (SSE)")

        sse_url = server_config["url"]
        base_headers = server_config.get("headers", {}).copy()

        response_data: dict[str, Any] = {"result": None, "error": None}
        endpoint: dict[str, str | None] = {"url": None}
        request_id = str(uuid.uuid4())

        if self.verbose:
            print(f"   连接: {sse_url}")

        sse_headers = base_headers.copy()
        sse_headers.update({"Accept": "text/event-stream", "Cache-Control": "no-cache"})

        try:
            sse_response = requests.get(sse_url, headers=sse_headers, stream=True, timeout=timeout)
            sse_response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"SSE连接失败: {e}") from e

        def listen_sse():
            event_type = None
            data_buffer: list[str] = []

            for line in sse_response.iter_lines(decode_unicode=True):
                if line is None:
                    continue

                if line == "":
                    if event_type and data_buffer:
                        full_data = "".join(data_buffer)

                        if event_type == "endpoint":
                            full_data = full_data.strip()
                            if full_data.startswith("/"):
                                from urllib.parse import urlparse

                                p = urlparse(sse_url)
                                endpoint["url"] = f"{p.scheme}://{p.netloc}{full_data}"
                            else:
                                endpoint["url"] = full_data

                        elif event_type == "message":
                            try:
                                msg = json.loads(full_data)
                                if msg.get("id") == request_id:
                                    response_data["error"] = msg.get("error")
                                    response_data["result"] = msg.get("result")
                                    return
                            except json.JSONDecodeError:
                                pass

                    event_type = None
                    data_buffer = []

                elif line.startswith("event:"):
                    event_type = line[6:].strip()

                elif line.startswith("data:"):
                    data_content = line[5:]
                    if data_content.startswith(" "):
                        data_content = data_content[1:]
                    data_buffer.append(data_content)

                else:
                    if data_buffer:
                        data_buffer.append(line)

                if response_data["result"] or response_data["error"]:
                    break

        listener = threading.Thread(target=listen_sse, daemon=True)
        listener.start()

        for _ in range(50):
            if endpoint["url"]:
                break
            time.sleep(0.1)

        if not endpoint["url"]:
            sse_response.close()
            raise RuntimeError("无法获取endpoint")

        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }

        post_headers = base_headers.copy()
        post_headers["Content-Type"] = "application/json"

        if self.verbose:
            print(f"   请求: {tool_name}")
            print(f"   参数: {json.dumps(arguments, ensure_ascii=False, indent=2)}")

        try:
            resp = requests.post(endpoint["url"], json=payload, headers=post_headers, timeout=timeout)
            if resp.status_code not in (200, 202):
                resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"请求失败: {e}") from e

        listener.join(timeout=timeout)
        sse_response.close()

        if response_data["error"]:
            raise RuntimeError(f"MCP错误: {response_data['error']}")
        if response_data["result"] is None:
            raise RuntimeError("无响应")

        print("   ✓ 完成")
        return response_data["result"]

    # -----------------------------------------------------------------------
    # 协议实现: streamableHttp
    # -----------------------------------------------------------------------

    def _call_tool_streamable_http(
        self, server_name: str, tool_name: str, arguments: dict[str, Any], timeout: int = 60
    ) -> dict[str, Any]:
        server_config = self.servers[server_name]
        print(f"📡 调用 {server_name}/{tool_name}... (streamableHttp)")

        url = server_config["url"]
        headers = server_config.get("headers", {}).copy()
        headers["Content-Type"] = "application/json"
        headers.setdefault("Accept", "application/json, text/event-stream")

        request_id = str(uuid.uuid4())
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }

        if self.verbose:
            print(f"   请求URL: {url}")
            print(f"   工具名称: {tool_name}")
            print(f"   请求参数: {json.dumps(arguments, ensure_ascii=False, indent=2)}")

        # 用 stream=True 实时按 SSE 协议读取，匹配到 request_id 立即返回
        # 兼容大响应、网关分块、服务器流式 progress 通知等场景
        result = self._stream_jsonrpc_request(
            url=url,
            headers=headers,
            payload=payload,
            request_id=request_id,
            tool_name=tool_name,
            timeout=timeout,
        )

        if isinstance(result, dict) and "error" in result:
            error = result["error"]
            error_msg = error.get("message", str(error)) if isinstance(error, dict) else str(error)
            raise RuntimeError(f"MCP错误: {error_msg}")

        if isinstance(result, dict) and "result" not in result:
            raise MCPProtocolError(f"响应中没有 result 字段 (tool={tool_name})\n响应顶层 keys: {list(result.keys())}")

        print("   ✓ 完成")
        return result.get("result") if isinstance(result, dict) else result

    # -----------------------------------------------------------------------
    # 协议实现: http
    # -----------------------------------------------------------------------

    def _call_tool_http(
        self, server_name: str, tool_name: str, arguments: dict[str, Any], timeout: int = 60
    ) -> dict[str, Any]:
        server_config = self.servers[server_name]
        print(f"📡 调用 {server_name}/{tool_name}... (http)")

        url = server_config["url"]
        headers = server_config.get("headers", {}).copy()
        headers["Content-Type"] = "application/json"
        headers.setdefault("Accept", "application/json, text/event-stream")

        request_id = str(uuid.uuid4())
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }

        if self.verbose:
            print(f"   请求URL: {url}")
            print(f"   请求参数: {json.dumps(arguments, ensure_ascii=False, indent=2)}")

        result = self._stream_jsonrpc_request(
            url=url,
            headers=headers,
            payload=payload,
            request_id=request_id,
            tool_name=tool_name,
            timeout=timeout,
        )

        if isinstance(result, dict) and "error" in result:
            error = result["error"]
            error_msg = error.get("message", str(error)) if isinstance(error, dict) else str(error)
            raise RuntimeError(f"MCP错误: {error_msg}")

        print("   ✓ 完成")
        return result.get("result") if isinstance(result, dict) else result

    # -----------------------------------------------------------------------
    # 流式 JSON-RPC 请求 (streamableHttp / http / remote 共用)
    # -----------------------------------------------------------------------

    def _stream_jsonrpc_request(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        request_id: str,
        tool_name: str,
        timeout: int,
    ) -> dict[str, Any]:
        """以 stream=True 实时读取响应:
        - 服务端响应 SSE 时, 按事件解析, 命中 request_id 立即返回(早退)
        - 服务端响应 application/json 时, 完整读完再解析
        - 解析失败时自动 dump 原始响应到 bkmonitor-files/_mcp_failed_responses/
          供用户复盘
        """
        response: requests.Response | None = None
        try:
            try:
                response = requests.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=timeout,
                    stream=True,
                )
                self._raise_for_http_status(response)
            except requests.exceptions.Timeout as e:
                raise TimeoutError(f"请求超时 (>{timeout}秒)\n提示: 可以尝试增加 timeout 参数或减小查询范围") from e
            except requests.exceptions.RequestException as e:
                raise ConnectionError(f"请求失败: {e}") from e

            content_type = response.headers.get("Content-Type", "")
            ct_lower = content_type.lower()

            # 路径 A: SSE 流式增量解析 (实时按事件读取)
            if "text/event-stream" in ct_lower:
                if self.verbose:
                    print("   检测到 SSE 流 (Content-Type), 走流式读取")
                buffered_chunks: list[str] = []
                result, all_text = self._stream_sse_until_match(
                    response=response,
                    request_id=request_id,
                    tool_name=tool_name,
                    chunk_collector=buffered_chunks,
                )
                if result is not None:
                    return result
                # 实时解析未命中, 用 buffered fallback (跨事件拼接 / 兼容非规范服务器)
                fallback = self._decode_jsonrpc_body(
                    text_body=all_text,
                    content_type=content_type,
                    request_id=request_id,
                    tool_name=tool_name,
                    save_failed_dump=True,
                )
                return fallback

            # 路径 B: 非 SSE → 一次性读取完整内容
            try:
                raw_bytes = response.content
            except requests.exceptions.ChunkedEncodingError as e:
                raise MCPServerUnavailableError(f"响应分块传输被截断: {e}") from e
            text_body = self._decode_response_body(raw_bytes, response)
            return self._decode_jsonrpc_body(
                text_body=text_body,
                content_type=content_type,
                request_id=request_id,
                tool_name=tool_name,
                save_failed_dump=True,
            )
        finally:
            if response is not None:
                response.close()

    def _stream_sse_until_match(
        self,
        response: requests.Response,
        request_id: str,
        tool_name: str,
        chunk_collector: list[str],
    ) -> tuple[dict[str, Any] | None, str]:
        """逐行读取 SSE 流, 命中 request_id 立即返回。

        :return: (匹配到的 JSON-RPC 对象 或 None, 完整的响应文本) — 即便提前命中, 也会
                 把已读到的 raw 行返回给调用方, 便于失败时落盘排查。
        """
        candidates_with_id_or_result: list[dict[str, Any]] = []
        data_buffer: list[str] = []
        raw_text_lines: list[str] = []

        def _try_parse_event(buf: list[str]) -> dict[str, Any] | None:
            if not buf:
                return None
            for variant in ("\n".join(buf), "".join(buf)):
                stripped = variant.strip()
                if not stripped or stripped == "[DONE]":
                    continue
                obj = _extract_json_from_text(stripped)
                if isinstance(obj, dict):
                    return obj
            return None

        try:
            iterator = response.iter_lines(decode_unicode=False, chunk_size=8192)
            for raw_bytes_line in iterator:
                if raw_bytes_line is None:
                    continue
                line = self._decode_sse_line(raw_bytes_line)
                raw_text_lines.append(line)

                if line == "":
                    obj = _try_parse_event(data_buffer)
                    data_buffer = []
                    if obj is None:
                        continue
                    if obj.get("id") == request_id:
                        return obj, "\n".join(raw_text_lines)
                    if "result" in obj or "error" in obj or "id" in obj:
                        candidates_with_id_or_result.append(obj)
                    continue

                if not line.startswith("data:"):
                    # 忽略 event:/id:/retry:/`:` 注释
                    continue

                payload_str = line[5:]
                if payload_str.startswith(" "):
                    payload_str = payload_str[1:]
                data_buffer.append(payload_str)

            # 末尾没有空行的最后一帧
            obj = _try_parse_event(data_buffer)
            if isinstance(obj, dict):
                if obj.get("id") == request_id:
                    return obj, "\n".join(raw_text_lines)
                if "result" in obj or "error" in obj:
                    candidates_with_id_or_result.append(obj)
        except requests.exceptions.ChunkedEncodingError as e:
            raise MCPServerUnavailableError(f"SSE 流分块传输被截断: {e}") from e
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"SSE 流读取失败: {e}") from e

        chunk_collector.append("\n".join(raw_text_lines))

        # 流读完仍未命中 request_id, 优先返回最后一个含 result/error 的对象
        for obj in reversed(candidates_with_id_or_result):
            if "result" in obj or "error" in obj:
                return obj, "\n".join(raw_text_lines)
        if candidates_with_id_or_result:
            return candidates_with_id_or_result[-1], "\n".join(raw_text_lines)

        return None, "\n".join(raw_text_lines)

    @staticmethod
    def _decode_sse_line(raw_bytes_line: bytes) -> str:
        """SSE 行解码: UTF-8 优先, errors='replace' 兜底, 兼容服务器编码不一致。"""
        if isinstance(raw_bytes_line, str):
            return raw_bytes_line.rstrip("\r")
        try:
            return raw_bytes_line.decode("utf-8").rstrip("\r")
        except UnicodeDecodeError:
            return raw_bytes_line.decode("utf-8", errors="replace").rstrip("\r")

    @staticmethod
    def _decode_response_body(raw_bytes: bytes, response: requests.Response) -> str:
        """解析 HTTP 响应正文, UTF-8 优先(MCP 协议默认编码)。"""
        if not raw_bytes:
            return ""
        try:
            return raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            encoding = response.encoding or response.apparent_encoding or "utf-8"
            try:
                return raw_bytes.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                return raw_bytes.decode("utf-8", errors="replace")

    # -----------------------------------------------------------------------
    # 协议错误处理 + 响应正文解析
    # -----------------------------------------------------------------------

    @staticmethod
    def _raise_for_http_status(response: requests.Response) -> None:
        """根据 HTTP 状态码抛出更具体的异常 (5xx 标记为可重试)。"""
        status = response.status_code
        if status < 400:
            return
        snippet = (response.text or "")[:200]
        if status == 401:
            raise MCPAuthenticationError("认证失败 (401)\n提示: 请检查配置文件中的 Token 是否有效")
        if status == 403:
            raise PermissionError("权限不足 (403)\n提示: 请检查 Token 是否有访问该资源的权限")
        if status in (408, 425, 429) or 500 <= status < 600:
            raise MCPServerUnavailableError(f"服务端错误 ({status}): {snippet}")
        raise ConnectionError(f"请求失败 ({status}): {snippet}")

    def _decode_jsonrpc_body(
        self,
        text_body: str,
        content_type: str,
        request_id: str,
        tool_name: str,
        save_failed_dump: bool = False,
    ) -> dict[str, Any]:
        """统一解析 streamableHttp / http / remote 协议的响应正文。

        解析策略 (按优先级):
          1) Content-Type 含 text/event-stream → SSE
          2) 正文以 ``event:`` / ``data:`` / ``:`` (comment) 开头 → SSE
          3) 否则尝试整体 JSON
          4) 整体 JSON 失败时回退 SSE 解析 (兼容服务端误标 Content-Type)
          5) SSE 解析失败时回退整体 JSON (兼容只有空 SSE 心跳的场景)
          6) 跨事件拼接 ``data:`` 行作为最后一道 fallback (处理某些非规范服务器)
          7) 全部失败抛 ``MCPProtocolError`` (可重试) + 自动 dump 原始响应
        """
        ct_lower = (content_type or "").lower()
        looks_sse_by_ct = "text/event-stream" in ct_lower
        looks_sse_by_body = self._response_body_looks_like_sse(text_body)
        prefer_sse = looks_sse_by_ct or looks_sse_by_body

        attempts: list[tuple[str, str]] = []

        def _try_sse(label: str) -> dict[str, Any] | None:
            parsed = self._parse_sse_response(text_body, request_id=request_id)
            if parsed is None:
                attempts.append((label, "SSE 解析未匹配到 JSON-RPC 对象"))
            return parsed

        def _try_json(label: str) -> dict[str, Any] | None:
            stripped = (text_body or "").strip()
            if not stripped:
                attempts.append((label, "响应正文为空"))
                return None
            try:
                parsed = json.loads(stripped)
                return parsed if isinstance(parsed, dict) else None
            except json.JSONDecodeError as exc:
                attempts.append((label, f"JSON 解析失败: {exc}"))
                return None

        def _try_concatenated_sse(label: str) -> dict[str, Any] | None:
            """跨事件拼接所有 data: 行 (处理某些把单个 JSON 拆到多个 SSE 帧的服务器)。"""
            data_lines: list[str] = []
            for raw_line in (text_body or "").splitlines():
                line = raw_line.rstrip("\r")
                if not line.startswith("data:"):
                    continue
                payload_str = line[5:]
                if payload_str.startswith(" "):
                    payload_str = payload_str[1:]
                data_lines.append(payload_str)
            if not data_lines:
                attempts.append((label, "正文中没有 data: 行"))
                return None
            for combined in ("\n".join(data_lines), "".join(data_lines)):
                stripped = combined.strip()
                if not stripped or stripped == "[DONE]":
                    continue
                obj = _extract_json_from_text(stripped)
                if isinstance(obj, dict):
                    return obj
            attempts.append((label, f"拼接 {len(data_lines)} 条 data: 行后仍非合法 JSON"))
            return None

        result: dict[str, Any] | None = None
        if prefer_sse:
            if self.verbose and looks_sse_by_ct:
                print("   检测到 SSE 格式响应 (Content-Type)")
            result = _try_sse("primary-sse")
            if result is None:
                result = _try_json("fallback-json")
            if result is None:
                result = _try_concatenated_sse("fallback-concatenated-sse")
        else:
            result = _try_json("primary-json")
            if result is None:
                result = _try_sse("fallback-sse")
            if result is None:
                result = _try_concatenated_sse("fallback-concatenated-sse")

        if result is None:
            preview = (text_body or "")[:200].replace("\n", "\\n")
            details = "; ".join(f"{label}: {reason}" for label, reason in attempts)
            dump_path = None
            if save_failed_dump:
                dump_path = self._dump_failed_response(
                    text_body=text_body,
                    content_type=content_type,
                    tool_name=tool_name,
                    request_id=request_id,
                    attempts=attempts,
                )
            dump_msg = f"\n  原始响应已保存: {dump_path}" if dump_path else ""
            raise MCPProtocolError(
                "响应无法解析为合法的 JSON-RPC 对象 "
                f"(tool={tool_name}, content_type={content_type or '<missing>'}, "
                f"body_len={len(text_body or '')})\n"
                f"  尝试: {details}\n"
                f"  响应内容(前 200 字符): {preview}"
                f"{dump_msg}"
            )
        return result

    def _dump_failed_response(
        self,
        text_body: str,
        content_type: str,
        tool_name: str,
        request_id: str,
        attempts: list[tuple[str, str]],
    ) -> str | None:
        """把无法解析的响应正文保存到 ``bkmonitor-files/_mcp_failed_responses/``,
        便于复盘。失败时静默返回 None (不影响主流程)。
        """
        try:
            ts = time.strftime("%Y%m%d_%H%M%S")
            out_dir = os.path.join(self.output_dir, "_mcp_failed_responses")
            os.makedirs(out_dir, exist_ok=True)
            fname = f"{tool_name}_{ts}_{request_id[:8]}.txt"
            fpath = os.path.join(out_dir, fname)
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(f"# tool: {tool_name}\n")
                f.write(f"# request_id: {request_id}\n")
                f.write(f"# content_type: {content_type or '<missing>'}\n")
                f.write(f"# body_bytes: {len(text_body or '')}\n")
                line_count = (text_body or "").count("\n") + 1 if text_body else 0
                data_count = sum(1 for ln in (text_body or "").splitlines() if ln.startswith("data:"))
                f.write(f"# line_count: {line_count}, data_lines: {data_count}\n")
                for label, reason in attempts:
                    f.write(f"# attempt[{label}]: {reason}\n")
                f.write("# --- raw body ---\n")
                f.write(text_body or "")
            return fpath
        except (OSError, ValueError):
            return None

    # -----------------------------------------------------------------------
    # SSE 响应解析
    # -----------------------------------------------------------------------

    def _response_body_looks_like_sse(self, text: str) -> bool:
        head = (text or "").lstrip()[:64]
        if not head:
            return False
        # 标准 SSE 字段：data:/event:/id:/retry:/: (comment)
        return (
            head.startswith("data:")
            or head.startswith("event:")
            or head.startswith("id:")
            or head.startswith("retry:")
            or head.startswith(":")
        )

    def _parse_sse_response(self, text: str, request_id: str | None = None) -> dict[str, Any] | None:
        """从 SSE 正文中解析 JSON-RPC 对象。

        兼容场景:
          - 多行 ``data:`` 拼接的 JSON (JSON 字符串中含 \\n 后被网关 chunk 截断)
          - ``event:``/``id:``/``retry:``/``:`` 注释行混入
          - 心跳/keepalive 事件 (空 data 或 ``: ping``)
          - 末尾事件没有终止空行
          - 字段值包含 SSE 心跳但目标 JSON 在更早事件
        """
        candidates: list[dict[str, Any]] = []

        def flush_event(data_lines: list[str]) -> None:
            if not data_lines:
                return
            payload_variants = ["\n".join(data_lines), "".join(data_lines)]
            for payload_str in payload_variants:
                payload_str = payload_str.strip()
                if not payload_str:
                    continue
                if payload_str == "[DONE]":
                    return
                parsed = _extract_json_from_text(payload_str)
                if isinstance(parsed, dict):
                    candidates.append(parsed)
                    return

        data_buffer: list[str] = []
        for raw_line in (text or "").splitlines():
            line = raw_line.rstrip("\r")
            if line == "":
                flush_event(data_buffer)
                data_buffer = []
                continue
            # 忽略 SSE 注释、event:、id:、retry: 字段（仅消费 data:）
            if not line.startswith("data:"):
                continue
            payload_str = line[5:]
            if payload_str.startswith(" "):
                payload_str = payload_str[1:]
            data_buffer.append(payload_str)
        flush_event(data_buffer)

        if not candidates:
            return None

        if request_id:
            for obj in candidates:
                if obj.get("id") == request_id:
                    return obj

        for obj in reversed(candidates):
            if "result" in obj or "error" in obj:
                return obj

        return candidates[-1]

    # -----------------------------------------------------------------------
    # 文件输出
    # -----------------------------------------------------------------------

    def save_result(self, data: Any, filename: str, output_dir: str = None) -> str:
        """保存结果到 JSON 文件。

        Args:
            data: 要保存的数据
            filename: 文件名 (仅文件名, 禁止带目录前缀)
            output_dir: 输出目录, 默认为当前工作目录下的 bkmonitor-files
        """
        if output_dir is None:
            output_dir = self.output_dir

        Path(output_dir).mkdir(parents=True, exist_ok=True)
        filepath = os.path.join(output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        size = os.path.getsize(filepath)
        print(f"✅ 已保存: {filepath} ({size} bytes)")
        _print_structure_hint(data)
        return filepath


# ---------------------------------------------------------------------------
# 便捷函数
# ---------------------------------------------------------------------------


def fetch_data(server: str, tool: str, args: dict, output_name: str = None, verbose: bool = False) -> dict:
    """通用数据获取函数。"""
    client = MCPClient(verbose=verbose)
    result = client.call_tool(server, tool, args)

    if output_name:
        filename = f"{output_name}_{time.strftime('%Y%m%d_%H%M%S')}.json"
        client.save_result(result, filename)

    return result


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("MCP Data Fetcher - 直接拉取观测数据(无需AI Token)")
    print("=" * 60)

    client = MCPClient()

    if not client.validate_config():
        sys.exit(1)

    print(f"\n📂 工作目录: {os.getcwd()}")
    print("📁 数据保存: ./bkmonitor-files/")

    print("\n" + "=" * 60)
    print("使用示例:")
    print("=" * 60)
    print("""
# 高级调用 (自动包装参数, 自动校验业务错误)
result = client.call_bkm_tool("prod", "metrics-query", "execute_range_query", {
    "bk_biz_id": "<bk_biz_id>",
    "promql": "avg(avg_over_time(bkmonitor:system:cpu_summary:usage[1m]))",
    "start_time": str(int(time.time()) - 3600),
    "end_time": str(int(time.time())),
    "step": "1m"
})

# 保存结果 (带结构提示)
client.save_result(result, "cpu_metrics.json")
""")

    print("\n💡 提示: 如遇到问题,请查阅 ../references/troubleshooting.md")
