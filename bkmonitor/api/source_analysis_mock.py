"""Issue 源码分析临时上游 Mock。

该模块只用于 DevOps、AIDEV、BKFara 尚未就绪时的前后端联调。Mock 复用正式接口协议，
不绕过 BKM 的规则校验、Celery 调度、状态机、结果校验和持久化。联调结束后应
删除本文件、配置开关、两个 API 适配层调用钩子、蓝盾/知识库 Mock 分支和对应测试。
"""

import hashlib
import time

from django.conf import settings
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _

from constants.issue import SourceAnalysisResultType


class SourceAnalysisMockError(Exception):
    """让正式状态机把 Mock 配置错误收敛为不可重试失败。"""

    data = {
        "code": "SOURCE_ANALYSIS_MOCK_INVALID_INPUT",
        "message": _("Source analysis mock input is invalid."),
        "retryable": False,
    }


class SourceAnalysisUpstreamMock:
    """集中模拟源码分析依赖的蓝盾、AIDEV 资源和 BKFara 四接口。"""

    BKCI_PROJECT_ID = "mock-source-analysis-project"
    BKCI_REPOSITORY_ALIAS = "mock-source-analysis-repository"
    BKCI_PROJECTS = (
        {
            "id": BKCI_PROJECT_ID,
            "name": _("[Mock] 源码分析联调项目"),
        },
    )
    BKCI_REPOSITORIES = {
        BKCI_PROJECT_ID: (
            {
                "id": BKCI_REPOSITORY_ALIAS,
                "name": BKCI_REPOSITORY_ALIAS,
                "scm_type": "GIT",
            },
        ),
    }

    AIDEV_AGENT_ACTION = "/openapi/aidev/private/v1/agents/"
    AIDEV_SKILL_ACTION = "/openapi/aidev/private/v1/skills/"

    BKFARA_ENSURE_SCENE_ACTION = "/incident/issue_analysis/ensure_scene/"
    BKFARA_GET_SCENE_ACTION = "/incident/issue_analysis/get_scene_status/"
    BKFARA_TRIGGER_ACTION = "/incident/issue_analysis/trigger/"
    BKFARA_GET_TASK_ACTION = "/incident/issue_analysis/get_task/"

    SCENARIO_HIGH_CONFIDENCE = "high_confidence"
    SCENARIO_INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    SCENARIO_RETRYABLE_FAILURE = "retryable_failure"
    SCENARIO_TERMINAL_FAILURE = "terminal_failure"

    AGENTS = (
        {
            "id": "mock-agent-high-confidence",
            "agent_name": _("[Mock] 高置信度分析成功"),
            "scenario": SCENARIO_HIGH_CONFIDENCE,
        },
        {
            "id": "mock-agent-insufficient-evidence",
            "agent_name": _("[Mock] 证据不足分析成功"),
            "scenario": SCENARIO_INSUFFICIENT_EVIDENCE,
        },
        {
            "id": "mock-agent-retryable-failure",
            "agent_name": _("[Mock] 可重试分析失败"),
            "scenario": SCENARIO_RETRYABLE_FAILURE,
        },
        {
            "id": "mock-agent-terminal-failure",
            "agent_name": _("[Mock] 不可重试分析失败"),
            "scenario": SCENARIO_TERMINAL_FAILURE,
        },
    )
    SKILLS = (
        {"id": "mock-skill-code-search", "skill_name": _("[Mock] 代码检索 Skill")},
        {"id": "mock-skill-log-analysis", "skill_name": _("[Mock] 告警日志分析 Skill")},
    )
    KNOWLEDGE_BASES = (
        {"id": "mock-kb-service", "name": _("[Mock] 业务服务知识库")},
        {"id": "mock-kb-troubleshooting", "name": _("[Mock] 故障排查知识库")},
    )

    TASK_CACHE_TIMEOUT_SECONDS = 24 * 60 * 60
    TASK_CACHE_PREFIX = "issue-source-analysis-mock-task:"

    @staticmethod
    def is_enabled() -> bool:
        """集中读取临时开关，便于联调结束后整体删除适配点。"""

        return settings.ISSUE_SOURCE_ANALYSIS_UPSTREAM_MOCK_ENABLED

    @staticmethod
    def duration_seconds() -> int:
        return max(0, settings.ISSUE_SOURCE_ANALYSIS_MOCK_DURATION_SECONDS)

    @classmethod
    def list_bkci_project_options(cls) -> list[dict]:
        """返回源码分析专用的蓝盾项目，避免 Mock 影响其他蓝盾调用方。"""

        return [{"id": str(item["id"]), "name": str(item["name"])} for item in cls.BKCI_PROJECTS]

    @classmethod
    def list_bkci_repository_options(cls, project_id: str) -> list[dict]:
        """按 Mock 项目返回 Git 代码库，供配置保存复用同一校验链路。"""

        return [dict(item) for item in cls.BKCI_REPOSITORIES.get(str(project_id), ())]

    @classmethod
    def supports_aidev_action(cls, action: str) -> bool:
        return action in {cls.AIDEV_AGENT_ACTION, cls.AIDEV_SKILL_ACTION}

    @classmethod
    def list_aidev_resources(cls, action: str, params: dict) -> dict:
        if action == cls.AIDEV_AGENT_ACTION:
            items = cls.AGENTS
            name_field = "agent_name"
        elif action == cls.AIDEV_SKILL_ACTION:
            items = cls.SKILLS
            name_field = "skill_name"
        else:
            raise ValueError(f"unsupported AIDEV mock action: {action}")
        return cls._paginate(items, name_field, params)

    @classmethod
    def list_knowledge_base_options(cls, params: dict) -> dict:
        result = cls._paginate(cls.KNOWLEDGE_BASES, "name", params)
        return {
            "total": result["count"],
            "list": [{"id": str(item["id"]), "name": str(item["name"])} for item in result["results"]],
        }

    @classmethod
    def visible_knowledge_base_ids(cls) -> set[str]:
        return {str(item["id"]) for item in cls.KNOWLEDGE_BASES}

    @staticmethod
    def _paginate(items: tuple[dict, ...], name_field: str, params: dict) -> dict:
        keyword = str(params.get("fuzzy") or params.get("keyword") or "").strip().lower()
        filtered = [item for item in items if not keyword or keyword in str(item[name_field]).lower()]
        page = int(params.get("page", 1))
        page_size = int(params.get("page_size", 20))
        start = (page - 1) * page_size
        return {"count": len(filtered), "results": list(filtered[start : start + page_size])}

    @classmethod
    def perform_bkfara_request(cls, action: str, params: dict) -> dict:
        handlers = {
            cls.BKFARA_ENSURE_SCENE_ACTION: cls._ensure_scene,
            cls.BKFARA_GET_SCENE_ACTION: cls._get_scene,
            cls.BKFARA_TRIGGER_ACTION: cls._trigger,
            cls.BKFARA_GET_TASK_ACTION: cls._get_task,
        }
        try:
            handler = handlers[action]
        except KeyError as error:
            raise ValueError(f"unsupported BKFara mock action: {action}") from error
        return handler(params)

    @staticmethod
    def _ensure_scene(params: dict) -> dict:
        scene_identity = ":".join(map(str, (params["bk_tenant_id"], params["bk_biz_id"], params["devops_project_id"])))
        scene_hash = hashlib.sha256(scene_identity.encode("utf-8")).hexdigest()[:32]
        return {
            "provision_id": f"mock-provision-{scene_hash}",
            "status": "ready",
            "terminal": True,
            "phase": None,
        }

    @staticmethod
    def _get_scene(params: dict) -> dict:
        return {
            "provision_id": params["provision_id"],
            "status": "ready",
            "terminal": True,
            "phase": None,
        }

    @classmethod
    def _trigger(cls, params: dict) -> dict:
        agent_id = str(params["inputs"]["agent_id"])
        scenario_by_agent = {str(item["id"]): str(item["scenario"]) for item in cls.AGENTS}
        try:
            scenario = scenario_by_agent[agent_id]
        except KeyError as error:
            raise SourceAnalysisMockError from error

        task_id = f"mock:{scenario}:{params['client_request_id']}"
        cache.add(
            cls._task_cache_key(task_id),
            time.time(),
            timeout=cls.TASK_CACHE_TIMEOUT_SECONDS,
        )
        return {
            "analysis_task_id": task_id,
            "status": "queued",
            "terminal": False,
            "phase": "bkflow_starting",
            "next_poll_after_seconds": 2,
        }

    @classmethod
    def _get_task(cls, params: dict) -> dict:
        task_id = str(params["analysis_task_id"])
        scenario = cls._parse_task_scenario(task_id)
        cache_key = cls._task_cache_key(task_id)
        started_at = cache.get(cache_key)
        if started_at is None:
            started_at = time.time()
            cache.set(cache_key, started_at, timeout=cls.TASK_CACHE_TIMEOUT_SECONDS)

        duration = cls.duration_seconds()
        if time.time() - float(started_at) < duration:
            return {
                "analysis_task_id": task_id,
                "status": "running",
                "terminal": False,
                "phase": "devops_running",
                "next_poll_after_seconds": 2,
            }

        if scenario in {cls.SCENARIO_HIGH_CONFIDENCE, cls.SCENARIO_INSUFFICIENT_EVIDENCE}:
            return {
                "analysis_task_id": task_id,
                "status": "succeeded",
                "terminal": True,
                "result": cls._build_success_result(scenario),
                "error": None,
            }

        retryable = scenario == cls.SCENARIO_RETRYABLE_FAILURE
        return {
            "analysis_task_id": task_id,
            "status": "failed",
            "terminal": True,
            "result": None,
            "error": {
                "code": "MOCK_ANALYSIS_FAILED",
                "message": str(_("Mock 源码分析失败，用于验证前端失败状态。")),
                "retryable": retryable,
                "request_id": f"mock-request-{task_id.rsplit(':', 1)[-1]}",
                "details": {"stage": "ai_analysis"},
            },
        }

    @classmethod
    def _parse_task_scenario(cls, task_id: str) -> str:
        parts = task_id.split(":", 2)
        if len(parts) != 3 or parts[0] != "mock":
            raise SourceAnalysisMockError
        scenario = parts[1]
        supported = {
            cls.SCENARIO_HIGH_CONFIDENCE,
            cls.SCENARIO_INSUFFICIENT_EVIDENCE,
            cls.SCENARIO_RETRYABLE_FAILURE,
            cls.SCENARIO_TERMINAL_FAILURE,
        }
        if scenario not in supported:
            raise SourceAnalysisMockError
        return scenario

    @classmethod
    def _build_success_result(cls, scenario: str) -> dict:
        if scenario == cls.SCENARIO_INSUFFICIENT_EVIDENCE:
            return {
                "schema_version": "1.0.0",
                "result_type": SourceAnalysisResultType.INSUFFICIENT_EVIDENCE,
                "result_card": {
                    "description": str(_("现有告警证据不足，无法确认唯一责任提交。")),
                    "responsibility": None,
                },
                "content_type": "text/markdown",
                "content": str(
                    _(
                        "# 源码分析报告\n\n"
                        "当前缺少告警时刻运行镜像与 Commit 的唯一映射，暂时无法定位责任提交。\n\n"
                        "## 建议补充\n\n- 告警时刻运行镜像摘要\n- 镜像与 Commit 的构建关联记录"
                    )
                ),
            }

        return {
            "schema_version": "1.0.0",
            "result_type": SourceAnalysisResultType.HIGH_CONFIDENCE,
            "result_card": {
                "description": str(_("空值校验被删除，导致登录请求出现空指针异常。")),
                "responsibility": {
                    "commit_id": "a3fa531",
                    "commit_message": "remove redundant null check",
                    "author_name": "Edwin Wu",
                    "bk_username": "edwinwu",
                },
            },
            "content_type": "text/markdown",
            "content": str(
                _(
                    "# 源码分析报告\n\n"
                    "## 根因\n\n登录态为空时仍直接读取用户信息，触发空指针异常。\n\n"
                    "## 责任变更\n\n```diff\n- if (userSession == null) return;\n+ validateToken(userSession);\n```\n\n"
                    "## 修复建议\n\n恢复空值保护，并补充登录态过期的单元测试。"
                )
            ),
        }

    @classmethod
    def _task_cache_key(cls, task_id: str) -> str:
        return f"{cls.TASK_CACHE_PREFIX}{task_id}"
