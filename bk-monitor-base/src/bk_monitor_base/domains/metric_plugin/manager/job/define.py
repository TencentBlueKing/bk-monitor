from datetime import datetime
from enum import Enum
from typing import Any, ClassVar, cast

from django_redis import get_redis_connection
from pydantic import BaseModel, Field, model_validator
from redis.client import Redis

from bk_monitor_base.config.all import get_config


class JobStatus(str, Enum):
    """作业状态"""

    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELED = "canceled"


# 任务阶段定义命名一般取决于 post_query 中设置的 CURRENT_STEP 值
class TASK_DEBUG_STEP(str, Enum):
    """任务阶段"""

    TRANSFER_PLUGIN_TO_HOST = "TRANSFER_PLUGIN_TO_HOST"
    START_DEBUG_METRICS = "START_DEBUG_METRICS"
    PARSE_DEBUG_METRICS = "PARSE_DEBUG_METRICS"
    CLEAN_ENVIRONMENT = "CLEAN_ENVIRONMENT"


SQL_DEBUG_STEP_NAME_MAP: dict[str, str] = {
    TASK_DEBUG_STEP.TRANSFER_PLUGIN_TO_HOST.value: "下发插件到采集主机",
    TASK_DEBUG_STEP.START_DEBUG_METRICS.value: "调试采集任务",
    TASK_DEBUG_STEP.PARSE_DEBUG_METRICS.value: "解析调试采集结果",
    TASK_DEBUG_STEP.CLEAN_ENVIRONMENT.value: "清理调试环境",
}


class JobMetricPluginDebugInst(BaseModel):
    """
    Job指标插件调试实例

    数据样例:
    {
        "id":1, // 自增debug_task_id
        "tenant_id": "system", // 租户id
        "created_at": "2024-12-31 11:23:15.653589", // 创建时间
        "created_by": "operator", // 创建人
        "updated_at": "2024-12-31 11:23:15.653589", // 更新时间
        "updated_by": "operator", // 更新人
        "is_deleted": 0, // 假删除
        "current_task_step": "START_DEBUG_METRICS", // 基于多个celery的task封装多个job阶段任务，不关键，仅记录当前所在步骤便于排查问题而已
        "task_log": [
            {
                "task_step": "CHECK_PLUGIN_EXSIT",
                "messages": "\n************ 检查插件二进制是否存在 -【正在执行】 ************\n\n************ 下发插件及配置文件 -【执行成功】 ************\n", // 每个阶段可能包含多条log，\n进行切割解析
                "log_content": "", // 不一定存在，具体脚本返回的返回值,要求单task_step仅包含一次单阶段的作业平台任务
                "job_instance": "123123121", // 不一定存在，取决于是否需要操作job平台
            },
            {
                "task_step": "TRANSFER_PLUGIN_TO_HOST",
                "messages": "\n************ 下发插件及配置文件 -【正在执行】 ************\n\n************ 下发插件及配置文件 -【执行成功】 ************\n", // 每个阶段可能包含多条log，\n进行切割解析
                "log_content": "",
                "job_instance": "20000123122",
            },
            {
                "task_step": "START_DEBUG_METRICS",
                "messages": "\n************ 启动插件调试 -【正在执行】 ************\n\n************ 启动插件调试 -【执行成功】 ************\n", // 每个阶段可能包含多条log，\n进行切割解析
                "log_content": "disk_usage{disk_name=\"/data\"} 10",
                "job_instance": "20000123123",
            },
        ],
        "debug_status": "success", // success/failed/running 重要，终态前端可以跳转状态了
        "debug_params": "{}", // 各插件具体实现可以不同，调试参数json
        "job_type": "db2", // 取自具体插件实现
        "reason": "", // 调试失败或取消原因
        "metrics": [
            {
                "dimensions":{
                    "disk_name":"/data"
                },
                "metric_name":"disk_usage",
                "metric_value":10
            }
        ], // 调试成功才有
    }
    """

    _redis_client: ClassVar[Redis | None] = None
    _JOB_DEBUG_TASK_ID: ClassVar[str] = ""
    _JOB_DEBUG_TASK_INST_KEY_PREFIX: ClassVar[str] = ""

    @classmethod
    def _get_redis_client(cls) -> Redis:
        """延迟获取 Redis 客户端，避免在类定义时调用 get_redis_connection()"""
        if cls._redis_client is None:
            cls._redis_client = get_redis_connection()
        return cls._redis_client

    @classmethod
    def _get_job_debug_task_id_key(cls) -> str:
        """延迟获取 JOB_DEBUG_TASK_ID 的 Redis key"""
        if not cls._JOB_DEBUG_TASK_ID:
            cls._JOB_DEBUG_TASK_ID = f"{get_config().common.redis_key_prefix}plugin:job_debug_task_id"
        return cls._JOB_DEBUG_TASK_ID

    @classmethod
    def _get_job_debug_task_inst_key_prefix(cls) -> str:
        """延迟获取 JOB_DEBUG_TASK_INST_KEY_PREFIX 的 Redis key 前缀"""
        if not cls._JOB_DEBUG_TASK_INST_KEY_PREFIX:
            cls._JOB_DEBUG_TASK_INST_KEY_PREFIX = f"{get_config().common.redis_key_prefix}plugin:job_debug_task:"
        return cls._JOB_DEBUG_TASK_INST_KEY_PREFIX

    id: int = Field(
        description="自增debug_task_id", default_factory=lambda: JobMetricPluginDebugInst._generate_debug_task_id()
    )
    tenant_id: str = Field(description="租户ID", default="system", max_length=64)
    created_at: datetime = Field(description="创建时间", default_factory=datetime.now)
    created_by: str = Field(description="创建人", default="", max_length=255)
    updated_at: datetime = Field(description="更新时间", default_factory=datetime.now)
    updated_by: str = Field(description="更新人", default="", max_length=255)
    current_task_step: str = Field(description="当前任务步骤", default="")
    task_log: list[dict[str, Any]] = Field(description="任务日志", default_factory=list)
    debug_status: JobStatus = Field(description="调试状态", default=JobStatus.RUNNING)
    debug_params: dict[str, Any] = Field(description="调试参数", default_factory=dict)
    reason: str = Field(description="调试失败或取消原因", default="")
    job_type: str = Field(description="job插件类型", default="")
    job_plugin_id: str = Field(description="job插件ID")
    metrics: list[dict[str, Any]] = Field(description="调试结果指标", default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _sync_user_on_create(cls, data: dict[str, Any]) -> dict[str, Any]:
        if data.get("updated_by") == "":
            data["updated_by"] = data.get("created_by")
        return data

    @classmethod
    def _generate_debug_task_id(cls) -> int:
        """生成Job插件调试任务ID"""
        debug_id: int = cast(int, cls._get_redis_client().incr(name=cls._get_job_debug_task_id_key()))
        return debug_id

    @classmethod
    def _get_debug_task_inst_key(cls, debug_task_id: int, tenant_id: str = "system") -> str:
        """获取Job插件调试任务实例在Redis中的key"""
        return f"{cls._get_job_debug_task_inst_key_prefix()}{tenant_id}{debug_task_id}"

    def save(self, ex: int = 3600, tenant_id: str = "system") -> None:
        """保存调试实例到Redis"""
        debug_task_inst_key = self._get_debug_task_inst_key(self.id, tenant_id=tenant_id)
        self.updated_at = datetime.now()
        self.tenant_id = tenant_id
        self._get_redis_client().set(debug_task_inst_key, self.model_dump_json(), ex=ex)

    def failed(self, reason: str = "未知异常") -> None:
        """设置调试实例为失败状态"""
        # 成功状态不可覆盖，避免不重要的任务失败覆盖状态
        if self.debug_status == JobStatus.SUCCESS:
            return
        self.debug_status = JobStatus.FAILED
        self.reason = reason
        self.save()

    def success(self) -> None:
        """设置调试实例为成功状态"""
        self.debug_status = JobStatus.SUCCESS
        self.save()

    @classmethod
    def get(cls, debug_task_id: int, tenant_id: str = "system") -> "JobMetricPluginDebugInst | None":
        """从Redis获取调试实例"""
        debug_task_inst_key = cls._get_debug_task_inst_key(debug_task_id, tenant_id=tenant_id)
        debug_task_json = cast(str | None, cls._get_redis_client().get(debug_task_inst_key))
        if debug_task_json is None:
            return None
        return cls.model_validate_json(debug_task_json)

    def add_log_entry(
        self,
        task_step: str,
        messages: str,
        log_content: str = "",
        job_instance: str = "",
        cover_message: bool = False,
        **kwargs: dict[str, Any],
    ) -> None:
        """
        添加或者更新日志条目到当前阶段的任务日志中
        Args:
            task_step (str): 任务步骤
            messages (str): 日志消息
            log_content (str): 日志内容
            job_instance (str): 作业实例ID
            cover_message (bool): 是否覆盖已有的消息，默认不覆盖而是追加
            kwargs: 其他可选参数,直接存储
        """
        self.current_task_step = task_step
        # 判断当前阶段是否已经存在，存在则更新，否则添加新条目
        for entry in self.task_log:
            if entry["task_step"] == task_step:
                if cover_message:
                    entry["messages"] = messages
                else:
                    entry["messages"] += messages
                if log_content:
                    entry["log_content"] = log_content
                if job_instance:
                    entry["job_instance"] = job_instance
                for key, value in kwargs.items():
                    entry[key] = value
                self.save()
                return

        log_entry = {
            "task_step": task_step,
            "messages": messages,
            "log_content": log_content,
            "job_instance": job_instance,
            **kwargs,
        }
        self.task_log.append(log_entry)
        self.save()


class SqlContent(BaseModel):
    """
    SQL内容
    {
        "classification_id": "sql1",# sql规则的唯一标识,也是指标的分组id（下发的时候会根据此id实现额外功能）
        "classification_name": "SQL-111", # sql规则的名称 也对应分组名称
        "content": "SELECT 1 as metrics_test;"
    }
    """

    classification_id: str = Field(description="sql规则的唯一标识,也是指标的分组id")
    classification_name: str = Field(description="sql规则的名称 也对应分组名称")
    content: str = Field(description="sql内容")
