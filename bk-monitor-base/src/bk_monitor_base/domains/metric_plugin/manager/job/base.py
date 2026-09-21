import enum
import json
import logging
import os
import shutil
import stat
import tarfile
import tempfile
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, ClassVar, TypedDict

import yaml
from jinja2.sandbox import SandboxedEnvironment
from typing_extensions import override

from bk_monitor_base.config import get_config
from bk_monitor_base.config.storage import StorageName
from bk_monitor_base.domains.metric_plugin.constants import ETLConfig, MetricPluginStatus
from bk_monitor_base.domains.metric_plugin.define import CreatePluginParams, MetricPlugin
from bk_monitor_base.domains.metric_plugin.errors import (
    DebugInstNotExistError,
    ExportPluginFailedError,
    ExportPluginTimeoutError,
    ParseOsTypeError,
    ParsePluginDebugContentError,
    PluginFileNotFoundError,
)
from bk_monitor_base.domains.metric_plugin.manager.base import BaseMetricPluginManager, OSType
from bk_monitor_base.domains.metric_plugin.manager.job.datalink import CustomSQLPluginDataLinker
from bk_monitor_base.domains.metric_plugin.manager.job.define import JobMetricPluginDebugInst, JobStatus
from bk_monitor_base.domains.metric_plugin.manager.job.task import submit_debug_task
from bk_monitor_base.domains.metric_plugin.mock_cmdb_tools import get_os_type_by_collect_host
from bk_monitor_base.domains.metric_plugin.models import MetricPluginModel
from bk_monitor_base.infras import third_party_api as api
from bk_monitor_base.infras.path_formatter import PathFormatter, PathStyle
from bk_monitor_base.infras.storage import get_storage
from bk_monitor_base.infras.third_party_api.errors import BkApiError

logger = logging.getLogger(__name__)

"""
蓝鲸监控Job插件是基于监控平台、GSE、作业平台、bkmonitorbeat定义的一种自定义采集插件，它可以支持在主机上安装插件，并提供插件的安装、卸载、启动、停止、调试、上传、导出等功能。

目前支持四种操作系统类型：
- linux_x86_64
- linux_aarch64
- windows_x86_64
- aix_powerpc

标准插件包目录结构订阅如下:

os_type: 操作系统类型
plugin_name: 插件名称

job_plugins_{os_type} - 操作系统类型目录
│── {plugin_name} - 插件名
    ├── etc - 插件运行配置目录 - 暂无实际文件，仅预留目录
    ├── info - 插件信息目录
    │   ├── config.json - 插件参数订阅，对应MetricPlugin.define
    │   ├── metrics.json - 插件指标订阅，对应MetricPlugin.metrics
    │   ├── description.md - 插件描述，对应MetricPlugin.description_md
    │   ├── meta.yaml - 插件元信息
    │   ├── release.md - 插件发布说明
    │   ├── signature.yaml - 插件签名
    ├── project.yaml - 插件定义
    ├── VERSION - 插件版本
"""

# 作业平台插件模板目录
JobPluginTemplateDir = Path(__file__).parent / "templates"

# 不同操作系统类型对应的插件路径
OSTypeToPluginDirName = {
    OSType.LINUX: "job_plugins_linux_x86_64",
    OSType.LINUX_AARCH64: "job_plugins_linux_aarch64",
    OSType.WINDOWS: "job_plugins_windows_x86_64",
    OSType.AIX: "job_plugins_aix_powerpc",
}


class JobPluginParamsMode(str, enum.Enum):
    """
    参数模式
    """

    # 命令行选项参数
    OPT_CMD = "opt_cmd"
    # 环境变量
    ENV = "env"


class JobPluginParamsType(str, enum.Enum):
    """
    参数类型
    """

    TEXT = "text"
    PASSWORD = "password"
    SWITCH = "switch"
    FILE = "file"
    ENCRYPT = "encrypt"


def json_dumps_filter(value: Any) -> str:
    """
    json.dumps jinja2 过滤器
    """
    return json.dumps(value, ensure_ascii=False, indent=4)


class TextFile(TypedDict):
    """
    文本文件
    """

    path: str
    content: str


class ExtraFile(TypedDict):
    """
    额外文件
    """

    target_path: str
    source_path: str


class JobPluginManager(BaseMetricPluginManager, ABC):
    """作业平台插件管理器基类

    作业平台类型，核心能力是基于作业平台的脚本执行和文件下发能力，实现可以安装在主机上的插件。
    """

    type: ClassVar[str] = "job"
    FILE_PREFIX: ClassVar[str] = "job_plugin"

    @abstractmethod
    def make_package(self, is_compress: bool = True) -> Path:
        """制作插件包"""

    def _log(self, level: int, message: str):
        """日志打印"""
        logger.log(level, "%s(%s, %s): %s", self.__class__.__name__, self.plugin.id, self.plugin.type, message)

    @property
    def basic_file_path(self) -> str:
        """获取JOB插件文件存储的基本路径"""
        return f"{self.FILE_PREFIX}/{self.type}"

    def _get_package_context(self) -> dict[str, Any]:
        """获取上下文，用于渲染插件包中的文本文件"""
        context = {
            "metric_json": [metric.model_dump(by_alias=True) for metric in self.plugin.metrics],
            "plugin_id": self.plugin.id,
            "plugin_display_name": self.plugin.name,
            "version": f"{self.plugin.version.major}.{self.plugin.version.minor}",
            "config_version": self.plugin.version.major,
            "plugin_type": self.plugin.type,
            "tag": "",
            "label": self.plugin.label,
            "description_md": self.plugin.description_md,
            "config_json": [param.model_dump(by_alias=True) for param in self.plugin.params],
            "collector_json": self.plugin.define,
            "signature": "",
            "is_support_remote": self.plugin.is_support_remote,
            "version_log": self.plugin.version_log,
        }
        return context

    def _create_compress_package(self, plugin_dir: Path) -> Path:
        """创建压缩包"""
        # 获取插件包的父目录
        parent_dir = plugin_dir.parent
        package_path = parent_dir / f"{plugin_dir.name}.tgz"
        package_members = list(plugin_dir.iterdir())
        if not package_members:
            raise ExportPluginFailedError(f"插件包目录为空: {plugin_dir}")

        with tarfile.open(package_path, "w:gz") as tar:
            for package_member in package_members:
                tar.add(package_member, arcname=package_member.name)

        with tarfile.open(package_path, "r:gz") as tar:
            if not any(member.isfile() for member in tar.getmembers()):
                package_path.unlink(missing_ok=True)
                raise ExportPluginFailedError(f"插件包压缩包不包含文件: {package_path}")

        self._log(logging.INFO, f"create compress package {plugin_dir.name}.tgz")
        return package_path

    def _make_package(
        self,
        extra_text_files: dict[OSType, list[TextFile]] | None = None,
        extra_files: dict[OSType, list[ExtraFile]] | None = None,
        is_compress: bool = True,
    ) -> Path:
        """制作插件包

        1. 从作业平台插件模板目录中拷贝所有文件到插件包目录中
        2. 根据上下文渲染插件包中的文本文件
        3. 在插件包中追加extra_files及logo文件

        Args:
            extra_text_files: 额外文本文件，可以按操作系统类型，添加额外文本文件
                {
                    OSType.LINUX: [
                        {
                            "path": "config.yaml",
                            "content": "xxx",
                        }
                    ],
                }
            extra_files: 额外文件，可以按操作系统类型，添加额外文件，path为注入到插件包中的路径，file_path为需要注入的文件/目录路径
                {
                    OSType.LINUX: [
                        {
                            "path": "lib",
                            "file_path": "/tmp/xxxx/lib",
                        }
                    ],
                }
            is_compress: 是否打包压缩
        Returns:
            插件包压缩包或插件包目录路径
        """

        # 获取插件模板目录
        template_dir = JobPluginTemplateDir / self.type
        if not template_dir.exists():
            raise ValueError(f"插件包模板目录不存在: {template_dir}")

        # 在临时目录中创建插件包目录
        plugin_dir = Path(tempfile.mkdtemp()) / self.plugin.id
        plugin_dir.mkdir(parents=True, exist_ok=True)

        # 获取上下文
        context = self._get_package_context()

        # 创建jinja2环境
        engine = SandboxedEnvironment()
        engine.filters["json_dumps"] = json_dumps_filter

        supported_os_types = self.get_supported_os_types()
        if not supported_os_types:
            raise ExportPluginFailedError(f"插件未声明支持的操作系统类型: {self.plugin.id}")

        # 根据当前插件支持的操作系统类型，拷贝插件模板目录到插件包目录中
        for os_type in supported_os_types:
            template_os_dir = template_dir / OSTypeToPluginDirName[os_type]
            if not template_os_dir.exists():
                raise ValueError(f"插件包模板目录不存在: {template_os_dir}")

            plugin_os_dir = plugin_dir / OSTypeToPluginDirName[os_type]

            # 拷贝插件模板目录到插件包目录中
            shutil.copytree(template_os_dir, plugin_os_dir)

            # 调整插件目录名
            plugin_sub_dir = plugin_os_dir / self.plugin.id
            plugin_sub_dir.with_name("plugin_name").rename(plugin_sub_dir)

            # 追加额外文件
            if extra_files:
                for file_info in extra_files.get(os_type, []):
                    shutil.copy(file_info["source_path"], plugin_sub_dir / file_info["target_path"])

            # 追加logo文件
            if self.plugin.logo:
                with open(plugin_sub_dir / "logo.png", "wb") as f:
                    f.write(self.plugin.read_logo())

            # 渲染插件包中的文本文件
            for file in plugin_sub_dir.glob("**/*"):
                # 跳过非文件
                if not file.is_file():
                    continue

                # 添加可执行权限
                os.chmod(file, mode=stat.S_IRWXU)

                # 跳过非文本文件
                try:
                    with open(file, encoding="utf-8") as f:
                        template = engine.from_string(f.read())
                        content = template.render(context)
                        with open(file, "w", encoding="utf-8") as f:
                            f.write(content)
                except Exception:
                    continue

            # 追加额外文本文件，避免纯数据内容被模板引擎二次渲染
            if extra_text_files:
                for file_info in extra_text_files.get(os_type, []):
                    target_file = plugin_sub_dir / file_info["path"]
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(target_file, "w+", encoding="utf-8") as file_obj:
                        file_obj.write(file_info["content"])

        self._log(logging.INFO, f"create plugin package {plugin_dir.name}")

        if is_compress:
            # 压缩插件包
            return self._create_compress_package(plugin_dir)

        return plugin_dir

    @override
    @classmethod
    def _find_plugin_dir(cls, extract_dir: Path) -> tuple[Path, str]:
        """查找插件目录

        Args:
            extract_dir: 解压后的根目录

        Returns:
            (插件目录路径, 插件名称)

        Raises:
            ValueError: 如果未找到有效的插件目录
        """
        for os_plugin_dir in extract_dir.iterdir():
            if not os_plugin_dir.is_dir() or not os_plugin_dir.name.startswith("job_plugins_"):
                continue

            # 查找该操作系统目录下的插件目录
            for sub_dir in os_plugin_dir.iterdir():
                if sub_dir.is_dir():
                    plugin_dir = sub_dir
                    plugin_name = sub_dir.name
                    logger.info(f"找到插件目录: {plugin_dir}")
                    return plugin_dir, plugin_name
        raise ValueError(f"插件包中未找到有效的插件目录: {extract_dir}")

    def _upload_plugin(self, tar_file: Path) -> str:
        """上传插件到REPO

        job插件均上传到bkrepo

        Raises:
            BkApiError: 接口调用失败
        """
        bkrepo_plugin_path = f"job_plugins/{self.plugin.id}/{int(time.time())}/{tar_file.name}"

        # 上传到bkrepo
        with open(tar_file, "rb") as f:
            storage = get_storage(StorageName.JOB)
            storage.save(bkrepo_plugin_path, f)
            self._log(logging.INFO, f"upload plugin to bkrepo success, {bkrepo_plugin_path}")

        return bkrepo_plugin_path

    def _get_debug_os_target_path(self, debug_task_inst_id: int, os_type: OSType) -> str:
        """获取不同操作系统类型对应的插件调试目标路径"""
        linux_path = f"{get_config().blueking.gse.gse_path_variable_linux}/job_plugins/debug_{self.type}_{debug_task_inst_id}/{self.plugin.id}"
        # TODO: 后续应从节点管理适配api传入bk_cloud_id、ip等信息，动态获取不同操作系统类型的gse安装路径
        OS_TARGET_PATH = {
            OSType.LINUX: linux_path,
            OSType.WINDOWS: rf"{get_config().blueking.gse.gse_path_variable_windows}\job_plugins\debug_{self.type}_{debug_task_inst_id}\{self.plugin.id}",
            OSType.LINUX_AARCH64: linux_path,
            OSType.AIX: linux_path,
        }
        return OS_TARGET_PATH.get(os_type, linux_path)

    def start_debug(
        self,
        collect_params: dict[str, Any],
        plugin_params: dict[str, Any],
        collect_host: dict[str, Any],
        operator: str,
    ) -> Any:
        """启动调试

        Args:
            collect_params: 采集参数
            plugin_params: 插件定义参数
            collect_host: 采集主机 例 {"bk_cloud_id":0,"ip":"127.0.0.1"} 或 {"bk_host_id": 1}
            operator: 操作人

        Returns:
            调试任务ID
        """
        # 在redis中创建调试任务实例
        job_metric_debug_inst = JobMetricPluginDebugInst(
            created_by=operator,
            debug_params={
                "collect_params": collect_params,
                "plugin_params": plugin_params,
                "collect_host": collect_host,
            },
            job_type=self.type,
            job_plugin_id=self.plugin.id,
        )
        job_metric_debug_inst.save()

        return self._start_debug(
            collect_params=collect_params,
            plugin_params=plugin_params,
            collect_host=collect_host,
            debug_task_inst_id=job_metric_debug_inst.id,
            operator=operator,
        )

    @abstractmethod
    def _start_debug(
        self,
        collect_params: dict[str, Any],
        plugin_params: dict[str, Any],
        collect_host: dict[str, Any],
        debug_task_inst_id: int,
        operator: str,
    ) -> Any:
        """启动调试

        Args:
            collect_params: 采集参数
            plugin_params: 插件定义参数
            collect_host: 采集主机
            operator: 操作人

        Returns:
            调试任务ID
        """

    def stop_debug(self, task_id: int, operator: str) -> None:
        """停止调试

        标记调试任务状态为已取消, task不再继续执行后续步骤

        Args:
            task_id: 任务ID
            operator: 操作人
        """
        debug_task = JobMetricPluginDebugInst.get(task_id)
        if debug_task is None:
            self._log(logging.WARNING, f"stop debug failed, task_id={task_id} not found")
            return
        debug_task.debug_status = JobStatus.CANCELED
        debug_task.updated_by = operator
        debug_task.save()

    @abstractmethod
    def get_debug_log(self, task_id: int) -> Any:
        """获取调试日志

        Args:
            task_id: 任务ID
        Returns:
            1.调试日志 2.调试状态 3.指标定义(调试成功时返回非空列表)
        Raises:
            PluginDebugError: 获取调试日志失败
        """
        pass

    @override
    def apply_data_link(self, operator: str) -> Any:
        """申请数据链路"""
        pass

    @override
    def delete_data_link(self, operator: str) -> Any:
        """删除数据链路"""
        pass

    def get_data_ids(self, bk_biz_id: int) -> dict[str, int]:  # pyright: ignore[reportUnusedParameter]
        """申请/获取数据ID

        Args:
            bk_biz_id: 业务ID

        Returns:
            数据ID映射, key为数据ID名称, value为数据ID值
        """
        raise NotImplementedError("get_data_ids is not implemented")


class SQLPluginManager(JobPluginManager, ABC):
    """作业平台SQL插件管理器基类

    基于作业平台的脚本执行和文件下发能力，实现可以安装在主机上的SQL采集插件。
    """

    type: ClassVar[str] = "sql_job"
    DB_TYPE: ClassVar[str] = "mysql"
    PLUGIN_REPO_TAR_PATH_KEY: ClassVar[str] = "bkrepo_plugin_tar_path"
    SQL_CONFIG_YAML_KEY: ClassVar[list[str]] = [
        "db_type",
        "host",
        "port",
        "password",
        "session",
        "sql_content",
        "time",
        "user",
        "name",
        "parse_rules",
    ]
    SQL_CONFIG_INT_KEYS: ClassVar[set[str]] = {"port", "session", "time"}
    SQL_CONTENT_INFO_FILE: ClassVar[str] = "info/sql_content.json"
    # 启动调试脚本
    START_DEBUG_METRICS_SCRIPTS: dict[OSType, Any] = {
        OSType.LINUX: """
            #!/bin/bash
            chmod +x {file_path}
            {file_path} -f {config_path} -debug true
        """,
        OSType.LINUX_AARCH64: """
            #!/bin/bash
            chmod +x {file_path}
            {file_path} -f {config_path} -debug true
        """,
    }

    # 清理环境脚本
    CLEAN_ENV_SCRIPTS: dict[OSType, Any] = {
        OSType.LINUX: """
            #!/bin/bash
            rm -rf {file_path}
        """,
        OSType.LINUX_AARCH64: """
            #!/bin/bash
            rm -rf {file_path}
        """,
    }
    # 兼容旧版本plugin_category
    plugin_category: ClassVar[str] = "SQL"

    @property
    def data_name(self) -> str:
        return f"{get_config().domains.space.global_space_id}_{self.plugin_category.lower()}_{self.plugin.id}"

    @abstractmethod
    def get_binary_path(self, os_type: OSType) -> str:
        """获取二进制文件路径"""
        pass

    @abstractmethod
    def get_extra_file_source_paths(self, os_type: OSType) -> list[str]:
        """
        获取插件包额外文件路径信息
        Args:
            os_type: 操作系统类型
        Returns:
            额外文件路径列表(repo内相对路径)
        """
        pass

    @override
    def _get_package_context(self) -> dict[str, Any]:
        """
        获取插件包上下文信息
        sql类型的插件需要上下文包含  sql_content: sql插件的sql定义  会渲染到 sql_config.yaml 中
        """
        context = super()._get_package_context()
        context.update(
            {
                "sql_content": self.get_sql_content_json(),
            }
        )
        return context

    @override
    def get_debug_log(self, task_id: int) -> Any:
        """获取调试日志

        Args:
            task_id: 任务ID
        Returns:
            1.调试日志 2.调试状态 3.指标定义(调试成功时返回非空列表)
        Raises:
            PluginDebugError: 获取调试日志失败
        """
        debug_task = JobMetricPluginDebugInst.get(task_id)
        if debug_task is None:
            raise ParsePluginDebugContentError(f"获取调试日志失败, 任务id {task_id} 不存在")
        task_log = [self._format_debug_task_log_entry(log_entry) for log_entry in debug_task.task_log]
        metric_json = []
        if debug_task.debug_status == JobStatus.SUCCESS:
            # 调试成功，返回指标定义
            metric_json = debug_task.metrics
        return task_log, debug_task.debug_status, metric_json

    @classmethod
    def _format_debug_task_log_entry(cls, log_entry: dict[str, Any]) -> dict[str, Any]:
        messages = str(log_entry.get("messages", ""))
        log_content = str(log_entry.get("log_content", ""))
        if log_content:
            messages = f"{messages}\n{log_content}" if messages else log_content

        raw_job_instance_id = log_entry.get("job_instance_id") or log_entry.get("job_instance")
        job_instance_id = cls._parse_job_instance_id(raw_job_instance_id)
        return {
            "step": log_entry.get("task_step", log_entry.get("step", "")),
            "status": cls._infer_debug_log_status(messages),
            "messages": messages,
            "job_instance_id": job_instance_id,
            "timestamp": log_entry.get("timestamp", ""),
            "extra": {
                key: value
                for key, value in log_entry.items()
                if key
                not in {"task_step", "step", "messages", "log_content", "job_instance", "job_instance_id", "timestamp"}
            },
        }

    @staticmethod
    def _parse_job_instance_id(raw_job_instance_id: Any) -> int | None:
        if raw_job_instance_id in (None, ""):
            return None
        try:
            return int(raw_job_instance_id)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _infer_debug_log_status(messages: str) -> str:
        if "【执行失败】" in messages or "失败" in messages:
            return JobStatus.FAILED.value
        if "【执行成功】" in messages or "成功" in messages:
            return JobStatus.SUCCESS.value
        if "【正在执行】" in messages or "正在执行" in messages:
            return JobStatus.RUNNING.value
        return ""

    def _get_custom_sql_plugin_datalinker(self) -> CustomSQLPluginDataLinker:
        """获取自定义SQL插件数据链路器"""
        return CustomSQLPluginDataLinker(plugin=self.plugin, plugin_model=self._get_plugin_model())

    @override
    def apply_data_link(self, operator: str) -> None:
        """申请数据链路

        创建数据ID和结果表, 存入插件的related_params中，函数可重入，多次调用不会重复申请数据链路。

        Args:
            operator: 操作人
        """
        self._get_custom_sql_plugin_datalinker().apply_data_ids(operator=operator)
        self._get_custom_sql_plugin_datalinker().apply_result_tables(operator=operator)
        return None

    @override
    def refresh_metrics(self, operator: str) -> None:
        """刷新插件指标配置。"""
        self._get_custom_sql_plugin_datalinker().refresh_metrics(operator=operator)
        self.plugin: MetricPlugin = self._get_plugin_model().to_plugin(version=self.plugin.version)

    @override
    def delete_data_link(self, operator: str) -> Any:
        """删除数据链路

        删除数据ID和结果表相关配置，函数可重入，多次调用不会有影响。

        Args:
            operator: 操作人
        """
        self._get_custom_sql_plugin_datalinker().delete_data_ids()
        self._get_custom_sql_plugin_datalinker().delete_result_tables()
        return None

    @override
    def get_data_ids(self, bk_biz_id: int) -> dict[str, int]:
        """获取数据ID

        优先使用插件的related_params中的data_id, 如果不存在, 则从metadata中通过data_name查询数据ID
        如果还不存在, 则注册一个数据ID并保存到插件的related_params中

        Args:
            bk_biz_id: 业务ID

        Returns:
            bk_data_id: 数据ID
        """
        if self.plugin.related_params.get("bk_data_id"):
            return {"bk_data_id": self.plugin.related_params["bk_data_id"]}

        # 为了兼容旧版本中不记录bk_data_id，而是通过固定的data_name规则来查询数据ID
        try:
            data_source = api.metadata.get_data_source(bk_tenant_id=self.plugin.bk_tenant_id, data_name=self.data_name)
            bk_data_id = data_source["bk_data_id"]
        except BkApiError:
            # 创建数据源
            bk_data_id = api.metadata.create_data_source(
                bk_tenant_id=self.plugin.bk_tenant_id,
                data_name=self.data_name,
                etl_config=ETLConfig.BK_EXPORTER.value,  # job插件数据链路使用标准的bk_exporter配置
                source_label="bk_monitor",
                type_label="time_series",
                operator=self.plugin.updated_by,
                is_custom_source=True,
            )

        # 更新插件的related_params中的bk_data_id
        self.plugin.related_params["bk_data_id"] = bk_data_id
        # 更新插件的related_params中的data_name，兼容旧版本通过data_name查询数据ID的逻辑
        self.plugin.related_params["data_name"] = self.data_name
        MetricPluginModel.objects.filter(
            bk_tenant_id=self.plugin.bk_tenant_id, bk_biz_id=bk_biz_id, plugin_id=self.plugin.id
        ).update(related_params=self.plugin.related_params)

        return {"bk_data_id": bk_data_id}

    @override
    def export_package(self, operator: str) -> str:
        """导出插件包
        返回repo内插件包文件下载url

        Returns:
            插件包的下载路径

        Raises:
            BkApiError: 接口调用失败
        """
        # 检查插件状态
        if self.plugin.status != MetricPluginStatus.RELEASE:
            raise ExportPluginFailedError(f"plugin {self.plugin.id}({self.plugin.version_str()}) is not released")
        bkrepo_plugin_path = self.plugin.related_params.get(self.PLUGIN_REPO_TAR_PATH_KEY)
        if bkrepo_plugin_path:
            return get_storage(StorageName.JOB).url(bkrepo_plugin_path)
        raise ExportPluginTimeoutError()

    def _download_binary(self, os_type: OSType) -> Path:
        """下载二进制文件到本地"""

        plugin_dir = Path(tempfile.mkdtemp()) / f"binary_{self.plugin.id}_{os_type.value}"
        plugin_dir.mkdir(parents=True, exist_ok=True)
        source_path = self.get_binary_path(os_type=os_type)
        target_path = plugin_dir / os.path.basename(source_path)
        # 下载文件
        with get_storage(StorageName.JOB).open(source_path, "rb") as f_remote:
            with open(target_path, "wb") as f_local:
                f_local.write(f_remote.read())

        return target_path

    def get_sql_content_json(self) -> list[dict[str, Any]]:
        """
        获取解析规则的json格式

        格式应满足SqlContent的模型定义

        例子：
        sql_content = [
            {
                "classification_id": "sql1",# sql规则的唯一标识,也是指标的分组id（下发的时候会根据此id实现额外功能）
                "classification_name": "SQL-111", # sql规则的名称 也对应分组名称
                "content": "SELECT 1 as metrics_test;"
            }
        ]
        """
        sql_content = self.plugin.define.get("sql_content", [])
        return sql_content

    def _get_sql_content_info_files(self) -> dict[OSType, list[TextFile]]:
        """获取需要写入插件 info 目录的 SQL 定义文件。"""
        content = json.dumps(self.get_sql_content_json(), ensure_ascii=False, indent=4)
        return {
            os_type: [TextFile(path=self.SQL_CONTENT_INFO_FILE, content=content)]
            for os_type in self.get_supported_os_types()
        }

    def get_parse_rules_json(self) -> list[dict[str, Any]]:
        """
        获取扩展插件sql解析规则
        parse_rules = {
            'sql1': {
                'osuser': {
                    'tag': 'dimension',
                    'field_name': 'osuser',
                    'alias_name': 'osuser',
                    'field_type': 'string',
                    'enabled_state': True,
                    'unit': ''
                }
            }
        }
        """
        sql_mapping = self.get_sql_content_json()
        sql_table_map_sql_content = {sql_msg["classification_id"]: sql_msg["content"] for sql_msg in sql_mapping}
        return_data: dict[str, Any] = {}
        for metric_obj in self.plugin.metrics:
            variate = [
                {
                    "object_name": metric_field.name,
                    "object_new_name": metric_field.name,
                    "object_type": metric_field.monitor_type,
                }
                for metric_field in metric_obj.fields
            ]
            return_data[metric_obj.table_name] = {
                "sql": sql_table_map_sql_content[metric_obj.table_name],
                "variate": variate,
            }
        return list(return_data.values())

    @classmethod
    def _normalize_sql_config_types(cls, sql_config_json: dict[str, Any]) -> None:
        """归一化 SQL 插件配置字段类型。"""
        for key in cls.SQL_CONFIG_INT_KEYS:
            value = sql_config_json.get(key)
            if value in (None, ""):
                continue
            if isinstance(value, bool):
                raise ValueError(f"SQL插件配置字段 {key} 必须为整数")
            try:
                sql_config_json[key] = int(value)
            except (TypeError, ValueError) as err:
                raise ValueError(f"SQL插件配置字段 {key} 必须为整数") from err

    def generate_config_yaml_content(self, plugin_params: dict[str, Any]) -> dict[str, Any]:
        """
        生成 sql_config.yml 文件内容
        Args:
            plugin_params: 插件参数
        Returns:
            sql_config.yml 文件内容
        """
        sql_config_json: dict[str, Any] = dict()
        # 加载插件定义的参数
        sql_config_json.update(plugin_params)
        # 添加 db_type 定义
        sql_config_json.update({"db_type": self.DB_TYPE})
        # 添加 sql_content 定义
        define_sql_content = self.get_sql_content_json()
        sql_config_json.update(
            {
                "sql_content": [sql.get("content") for sql in define_sql_content if "content" in sql],
            }
        )
        # 添加解析规则(映射成prometheus格式)
        define_parse_rules = self.get_parse_rules_json()
        sql_config_json.update(
            {
                "parse_rules": define_parse_rules,
            }
        )

        # 裁剪多余的字段
        for item in list(sql_config_json.keys()):
            if item not in self.SQL_CONFIG_YAML_KEY:
                sql_config_json.pop(item)
        self._normalize_sql_config_types(sql_config_json)
        # 转换为 yaml 格式
        config_json_str = json.dumps(sql_config_json)
        yaml_content = yaml.safe_load(config_json_str)
        return yaml_content

    def _generate_debug_yaml(self, debug_inst: JobMetricPluginDebugInst) -> str:
        """
        生成调试用的 sql_config.yml 文件
        Args:
            debug_inst: 调试实例
        Returns:
            Path: repo里面的 sql_config.yml 文件路径
        """
        plugin_params = debug_inst.debug_params.get("plugin_params", {})
        yaml_content = self.generate_config_yaml_content(plugin_params=plugin_params)
        # 写入到临时文件
        plugin_dir = Path(tempfile.mkdtemp())
        plugin_dir.mkdir(parents=True, exist_ok=True)
        local_config_path = plugin_dir / f"{str(debug_inst.id)}_sql_config.yml"
        with open(local_config_path, "w") as f:
            yaml.safe_dump(yaml_content, f)
        # 上传到 repo 里面
        remote_config_path = f"{self.basic_file_path}/debug_{str(debug_inst.id)}/sql_config.yml"
        storage = get_storage(StorageName.JOB)
        with open(local_config_path, "rb") as f:
            storage.save(remote_config_path, f)
        return remote_config_path

    @override
    def make_package(self, is_compress: bool = True) -> Path:
        """
        制作插件包
        由于sql插件需要携带二进制的依赖，因此需要在制作插件包时添加额外的文件
        """
        file_local_paths: dict[OSType, Path] = {}
        # 预下载二进制文件
        for os_type in self.get_supported_os_types():
            file_local_paths[os_type] = self._download_binary(os_type=os_type)
        extra_files: dict[OSType, list[ExtraFile]] = {}
        for os_type in self.get_supported_os_types():
            if os_type not in file_local_paths:
                raise PluginFileNotFoundError(f"内置的插件文件不存在: {os_type}")
            extra_files[os_type] = []
            # 添加repo内置的二进制文件
            file_path = file_local_paths[os_type]
            extra_files[os_type].append(
                ExtraFile(
                    source_path=str(file_path),
                    target_path=os.path.basename(file_path),
                )
            )
        return self._make_package(
            extra_text_files=self._get_sql_content_info_files(),
            extra_files=extra_files,
            is_compress=is_compress,
        )

    def parse_target_server(
        self,
        collect_host: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        获取目标服务器信息
        Args:
            collect_host: 采集主机信息
        Returns:
            目标服务器信息 | None: 无法解析目标服务器信息
        """
        # 构建target_server参数
        target_server: dict[str, Any] = {}
        if "ip" in collect_host and "bk_cloud_id" in collect_host:
            target_server = {
                "ip_list": [
                    {
                        "bk_cloud_id": collect_host["bk_cloud_id"],
                        "ip": collect_host["ip"],
                    }
                ]
            }
            return target_server
        elif "bk_host_id" in collect_host:
            target_server = {"host_id_list": [collect_host["bk_host_id"]]}
            return target_server
        return None

    @override
    def _start_debug(
        self,
        collect_params: dict[str, Any],
        plugin_params: dict[str, Any],
        collect_host: dict[str, Any],
        debug_task_inst_id: int,
        operator: str,
    ) -> int:
        """启动调试

        Args:
            collect_params: 采集参数
            plugin_params: 插件定义参数
            collect_host: 采集主机
            operator: 操作人

        Returns:
            调试任务ID
        """
        job_metric_debug_inst = JobMetricPluginDebugInst.get(debug_task_inst_id)
        if job_metric_debug_inst is None:
            raise DebugInstNotExistError(f"调试实例不存在，debug_task_inst_id: {debug_task_inst_id}")
        os_type = get_os_type_by_collect_host(collect_host=collect_host)
        if os_type is None:
            raise ParseOsTypeError(f"无法解析操作系统类型, collect_host: {collect_host}")
        # 二进制文件路径
        binary_path = self.get_binary_path(os_type=os_type)
        # 下发
        target_path = self._get_debug_os_target_path(debug_task_inst_id=debug_task_inst_id, os_type=os_type)
        task_params: dict[str, Any] = {
            "binary_path": binary_path,
            "target_path": target_path,
        }
        # 获取插件包上下文作为调试上下文
        task_params.update(self._get_package_context())

        # 调试调用job所需用户
        if os_type in [OSType.WINDOWS]:
            task_params["account_alias"] = collect_params.get("job_account_alias", "system")
        else:
            task_params["account_alias"] = collect_params.get("job_account_alias", "root")

        # SQL插件不制作插件包，直接使用二进制文件和生成的配置文件

        # 生成调试用的 sql_config.yml 文件
        debug_yaml_file_path = self._generate_debug_yaml(debug_inst=job_metric_debug_inst)
        # 调试用的 sql_config.yml 文件路径
        task_params["debug_yaml_file_path"] = debug_yaml_file_path

        # 添加需要的额外下发的文件
        extra_file_source_paths = self.get_extra_file_source_paths(os_type=os_type)
        task_params["extra_file_source_paths"] = extra_file_source_paths

        # 解析标准目标服务器信息
        target_server = self.parse_target_server(collect_host=collect_host)
        task_params["target_server"] = target_server
        task_params["os_type"] = os_type.value

        # 计算二进制下发后路径
        binary_file_name = os.path.basename(binary_path)
        binary_target_file_path = os.path.join(target_path, binary_file_name)
        if os_type == OSType.WINDOWS:
            binary_target_file_path = PathFormatter.format_path(binary_target_file_path, style=PathStyle.WINDOWS)
        else:
            binary_target_file_path = PathFormatter.format_path(binary_target_file_path, style=PathStyle.POSIX)
        # 计算配置文件下发后路径
        config_file_name = os.path.basename(debug_yaml_file_path)
        config_target_file_path = os.path.join(target_path, config_file_name)
        if os_type == OSType.WINDOWS:
            config_target_file_path = PathFormatter.format_path(config_target_file_path, style=PathStyle.WINDOWS)
        else:
            config_target_file_path = PathFormatter.format_path(config_target_file_path, style=PathStyle.POSIX)
        # 调试需要执行的生成脚本内容
        START_DEBUG_METRICS_SCRIPT: str | None = self.START_DEBUG_METRICS_SCRIPTS.get(os_type, None)
        if START_DEBUG_METRICS_SCRIPT is None:
            raise ParseOsTypeError(f"不支持的操作系统类型: {os_type}")
        start_debug_script_content = START_DEBUG_METRICS_SCRIPT.format(
            file_path=binary_target_file_path, config_path=config_target_file_path, target_path=target_path
        )
        task_params["start_debug_script_content"] = start_debug_script_content

        # 调试后清理脚本内容
        CLEAN_ENV_SCRIPT = self.CLEAN_ENV_SCRIPTS.get(os_type, None)
        if CLEAN_ENV_SCRIPT is None:
            raise ParseOsTypeError(f"不支持的操作系统类型: {os_type}")
        env_clean_script_content = CLEAN_ENV_SCRIPT.format(file_path=target_path)
        task_params["env_clean_script_content"] = env_clean_script_content

        # 更新调试实例的调试参数
        job_metric_debug_inst.debug_params.update(task_params)
        job_metric_debug_inst.save()

        # 插件实例放入上下文
        task_params["plugin"] = self.plugin.model_dump()
        # 启动调试任务
        submit_debug_task(
            debug_task_inst_id=job_metric_debug_inst.id,
            context=task_params,
        )
        return job_metric_debug_inst.id

    @override
    def release_plugin_version(
        self, operator: str, apply_data_link: bool = True, md5_list: list[str] | None = None
    ) -> None:
        """发布插件到REPO

        1. 上传模板插件包到repo
        2. 更新插件版本状态为已发布

        Raises:
            BkApiError: 接口调用失败
        """
        # 制作插件包
        plugin_package_path = self.make_package(is_compress=True)
        # 上传插件包到repo
        bkrepo_plugin_path = self._upload_plugin(tar_file=plugin_package_path)
        # 插件包repo路径保存到插件的related_params中
        self.plugin.related_params[self.PLUGIN_REPO_TAR_PATH_KEY] = bkrepo_plugin_path
        MetricPluginModel.objects.filter(
            bk_tenant_id=self.plugin.bk_tenant_id, bk_biz_id=self.plugin.bk_biz_id, plugin_id=self.plugin.id
        ).update(related_params=self.plugin.related_params)
        # 更新插件版本状态为已发布
        super().release_plugin_version(operator=operator, apply_data_link=apply_data_link, md5_list=md5_list)

    @override
    def register(self, operator: str) -> list[str]:
        """注册插件

        作业平台插件无需register操作，直接返回空列表
        """
        return []

    @override
    @classmethod
    def _parse_define(
        cls,
        bk_tenant_id: str,
        operator: str,
        extract_dir: Path,
        plugin_id: str,
        meta_data: dict[str, Any],
    ) -> dict[str, Any]:
        """解析插件定义

        各插件子类需要实现此方法来解析插件特定的 define 字段。

        Args:
            bk_tenant_id: 租户ID
            operator: 操作人
            extract_dir: 解压根目录路径
            plugin_name: 插件名称
            meta_data: meta.yaml 解析后的数据

        Returns:
            插件定义字典，将赋值给 CreatePluginParams.define
        """
        plugin_dir, _ = cls._find_plugin_dir(extract_dir)
        sql_content_file = plugin_dir / cls.SQL_CONTENT_INFO_FILE
        if not sql_content_file.exists():
            return {}

        with open(sql_content_file, encoding="utf-8") as file_obj:
            sql_content: Any = json.load(file_obj)
        if not isinstance(sql_content, list):
            raise ValueError(f"{cls.SQL_CONTENT_INFO_FILE} 必须是列表格式，当前格式: {type(sql_content).__name__}")
        return {"sql_content": sql_content}

    @override
    @classmethod
    def parse_package(cls, bk_tenant_id: str, package_file: Path, operator: str) -> CreatePluginParams:
        """解析插件包

        Args:
            bk_tenant_id: 租户ID
            package_file: 插件包文件路径
            operator: 操作人

        Returns:
            CreatePluginParams: 创建插件参数
        """
        return super().parse_package(bk_tenant_id=bk_tenant_id, package_file=package_file, operator=operator)
