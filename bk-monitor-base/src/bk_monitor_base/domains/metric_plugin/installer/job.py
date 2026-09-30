"""
Job 安装器

基于作业平台的脚本执行和文件下发能力，实现采集插件的安装、卸载、启动、停止等操作。

Note:
    1. 与 Nodeman 安装器不同，Job 安装器的任务状态由自己维护，存储在 JobTaskInstanceModel 中。
    2. 每个目标实例（主机、容器、Pod 等）对应一个 JobTaskInstanceModel 实例，实现实例级别的任务管理。
    3. 在 MetricPluginDeployment 的 related_params 中存储 instance_id -> job_inst_id 的映射，
       方便后续通过目标实例找到对应的任务实例进行单独管理。
    4. 任务拆分在 install 阶段完成，按实例创建独立的任务实例。
"""

import logging
import os
import re
import tempfile
from abc import ABC
from pathlib import Path
from typing import Any, Literal, cast, final

import yaml
from django.db import transaction
from typing_extensions import override

from bk_monitor_base.config import get_config
from bk_monitor_base.config.storage import StorageName
from bk_monitor_base.domains.metric_plugin.constants import (
    InstanceType,
    JobTaskActionEnum,
    JobTaskStatusEnum,
    TargetNodeType,
)
from bk_monitor_base.domains.metric_plugin.define import (
    JOB_PLUGIN_BUILT_IN_DIMENSIONS,
    JobTaskInstance,
    MetricPluginDeployment,
    MetricPluginDeploymentScope,
    MetricPluginDeploymentStatusEnum,
    MetricPluginDeploymentVersion,
)
from bk_monitor_base.domains.metric_plugin.errors import (
    DataIDNotFoundError,
    HostInfoNotFoundError,
    MetricPluginDeploymentOperationError,
    ParseOsTypeError,
)
from bk_monitor_base.domains.metric_plugin.installer.base import BaseInstaller
from bk_monitor_base.domains.metric_plugin.installer.define import (
    InstallerStatusResult,
    InstanceStatusInfo,
    InstanceTargetParams,
    JobCollectLogDetail,
    JobCollectLogEntry,
    TargetChangeAnalysis,
)
from bk_monitor_base.domains.metric_plugin.installer.task import (
    submit_install_task,
    submit_start_task,
    submit_stop_task,
    submit_uninstall_task,
)
from bk_monitor_base.domains.metric_plugin.manager.base import OSType
from bk_monitor_base.domains.metric_plugin.manager.job.base import SQLPluginManager
from bk_monitor_base.domains.metric_plugin.manager.tools import get_sql_plugin_manager
from bk_monitor_base.domains.metric_plugin.mock_cmdb_tools import get_host_info, get_os_type_by_collect_host
from bk_monitor_base.domains.metric_plugin.models import (
    JobTaskInstanceModel,
    MetricPluginDeploymentModel,
    MetricPluginDeploymentVersionModel,
)
from bk_monitor_base.infras.path_formatter import PathFormatter, PathStyle
from bk_monitor_base.infras.storage import get_bkrepo_storage

logger = logging.getLogger(__name__)


class JobInstaller(BaseInstaller, ABC):
    """JOB 安装器

    Note:
        1. 该安装器通过作业平台的脚本执行和文件下发能力进行插件的安装、卸载、启动、停止等操作
        2. 每个目标实例（主机、容器、Pod 等）对应一个 JobTaskInstanceModel 实例，支持：
           - 实例级别的任务状态跟踪（pending/running/success/failed/canceled）
           - 实例级别的任务日志记录（每个步骤的执行详情）
           - 通过 instance_id 快速定位任务实例进行管理
        3. 在 MetricPluginDeployment 的 related_params 中记录：
           - job_inst_mapping: instance_id -> job_inst_id 的映射
        4. 部署状态维护在数据库的 MetricPluginDeploymentModel 中
        5. 任务控制需上层自行把控，如当前状态下是否还要继续执行某操作
    """

    # related_params 中存储任务映射的键名
    JOB_INST_MAPPING_KEY: str = "job_inst_mapping"
    BKMONITORBEAT_CONFIG_NAME_TEMPLATE: str = "bkmonitorbeat_{plugin_type}_config_{deployment_id}_{instance_id}.conf"

    def __init__(self, deployment: MetricPluginDeployment, operator: str):
        """初始化 Job 安装器

        Args:
            deployment: 指标插件部署项
            operator: 操作者

        Raises:
            MetricPluginNotFoundError: 插件不存在
        """
        super().__init__(deployment, operator)
        # NOTE: 具体子类中自行初始化，避免类型冲突
        # self.plugin_manager: JobPluginManager = get_job_plugin_manager(self.plugin)
        self.deployment_version: MetricPluginDeploymentVersion | None = None

    @property
    def job_inst_mapping(self) -> dict[str, int]:
        """获取实例到任务实例ID的映射

        Returns:
            dict: instance_id -> job_inst_id 的映射
        """
        return self.deployment.related_params.get(self.JOB_INST_MAPPING_KEY, {})

    @job_inst_mapping.setter
    def job_inst_mapping(self, value: dict[str, int]) -> None:
        """设置实例到任务实例ID的映射

        Args:
            value: instance_id -> job_inst_id 的映射
        """
        self.deployment.related_params[self.JOB_INST_MAPPING_KEY] = value

    def _log(self, level: int, message: str) -> None:
        """记录日志

        Args:
            level: 日志级别
            message: 日志消息
        """
        logger.log(
            level,
            "JobInstaller(%s/%s, %s): %s",
            self.deployment.bk_tenant_id,
            self.deployment.plugin_id,
            self.deployment.id,
            message,
        )

    @staticmethod
    def _label_to_object_type(label: str) -> Literal["HOST", "SERVICE"]:
        """将插件标签转换为目标对象类型"""
        if label in ["os"]:
            return InstanceType.HOST.value
        else:
            return InstanceType.SERVICE.value

    def _extract_targets(self, deployment_version: MetricPluginDeploymentVersion) -> list[dict[str, Any]]:
        """从部署版本中提取目标实例列表

        Args:
            deployment_version: 部署版本

        Returns:
            list: 目标实例列表（可能是主机、容器、Pod 等）
        """
        # 如果是远程采集，使用远程节点
        if deployment_version.remote_scope:
            raise MetricPluginDeploymentOperationError("Job 安装器暂不支持远程采集场景")
        return deployment_version.target_scope.nodes

    def get_task_instance(self, instance_id: str) -> JobTaskInstance | None:
        """根据实例标识获取任务实例

        Args:
            instance_id: 实例标识

        Returns:
            JobTaskInstance | None: 任务实例，不存在则返回 None
        """
        inst_id = self.job_inst_mapping.get(instance_id)
        if not inst_id:
            return None

        try:
            return JobTaskInstanceModel.objects.get(pk=inst_id).to_instance()
        except JobTaskInstanceModel.DoesNotExist:
            return None

    def instance_status(self, _instance_id: str) -> dict[str, Any]:
        raise NotImplementedError(
            "JobInstaller 不直接实现 instance_status 方法，需通过 get_task_instance 获取任务实例后由上层调用者自行处理日志详情的返回格式"
        )


@final
class SQLInstaller(JobInstaller):
    """SQL 安装器"""

    TARGET_PARAMS_KEY_TEMPLATE_FIELD: str = "target_params_key_template"
    DEFAULT_TARGET_PARAMS_KEY_TEMPLATE: str = "{{ target.instance_id }}"
    TARGET_PARAMS_KEY_TEMPLATE_PATTERN = re.compile(r"\{\{\s*target\.([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")
    PLAIN_DURATION_NUMBER_PATTERN = re.compile(r"^\d+(?:\.\d+)?$")
    GO_DURATION_PATTERN = re.compile(r"^(?:\d+(?:\.\d+)?(?:ns|us|µs|μs|ms|s|m|h))+$")
    METRIC_TARGET_KEY: str = "__metric_target"
    DMS_INSERT_MODE: str = "dms_insert"
    DMS_HOST_TYPE: str = "host"
    DMS_SERVICE_TYPE: str = "service"
    DMS_CUSTOM_TYPE: str = "custom"

    CHMOD_PLUGIN_SCRIPTS: dict[OSType, str] = {
        OSType.LINUX: "chmod +x {binary_target_file_path}",
        OSType.LINUX_AARCH64: "chmod +x {binary_target_file_path}",
        OSType.AIX: "chmod +x {binary_target_file_path}",
    }

    RESTART_BKMONITORBEAT_SCRIPTS: dict[OSType, str] = {
        OSType.LINUX: "cd {bkmonitorbeat_binary_dir_path} && ./restart.sh bkmonitorbeat",
        OSType.LINUX_AARCH64: "cd {bkmonitorbeat_binary_dir_path} && ./restart.sh bkmonitorbeat",
        OSType.AIX: "cd {bkmonitorbeat_binary_dir_path} && ./restart.ksh bkmonitorbeat",
    }

    REMOVE_CONFIG_SCRIPTS: dict[OSType, str] = {
        OSType.LINUX: "rm -f {bkmonitorbeat_config_file}",
        OSType.LINUX_AARCH64: "rm -f {bkmonitorbeat_config_file}",
        OSType.AIX: "rm -f {bkmonitorbeat_config_file}",
    }

    REMOVE_PLUGIN_SCRIPTS: dict[OSType, str] = {
        OSType.LINUX: "rm -rf {plugin_subscription_path}",
        OSType.LINUX_AARCH64: "rm -rf {plugin_subscription_path}",
        OSType.AIX: "rm -rf {plugin_subscription_path}",
    }

    def __init__(self, deployment: MetricPluginDeployment, operator: str):
        """初始化 SQL 安装器

        Args:
            deployment: 指标插件部署项
            operator: 操作者

        Raises:
            MetricPluginNotFoundError: 插件不存在
        """
        super().__init__(deployment, operator)
        self.plugin_manager: SQLPluginManager = get_sql_plugin_manager(self.plugin)

    @override
    def _log(self, level: int, message: str) -> None:
        """记录日志

        Args:
            level: 日志级别
            message: 日志消息
        """
        logger.log(
            level,
            "SQLInstaller(%s/%s, %s): %s",
            self.deployment.bk_tenant_id,
            self.deployment.plugin_id,
            self.deployment.id,
            message,
        )

    def get_data_ids(self) -> dict[str, int]:
        """获取数据ID"""
        return self.plugin_manager.get_data_ids(bk_biz_id=self.deployment.bk_biz_id)

    @staticmethod
    def _normalize_host_target(target: dict[str, Any]) -> dict[str, Any]:
        """将 Job 主机实例 ID 还原为 CMDB 可识别的主机查询参数"""
        normalized_target = dict(target)
        if normalized_target.get("bk_host_id") is not None:
            return normalized_target

        instance_id = normalized_target.get("instance_id")
        if not isinstance(instance_id, str) or not instance_id.startswith("host_"):
            return normalized_target

        host_id = instance_id.removeprefix("host_")
        if host_id.isdigit():
            normalized_target["bk_host_id"] = int(host_id)
        return normalized_target

    @override
    def _extract_targets(self, deployment_version: MetricPluginDeploymentVersion) -> list[dict[str, Any]]:
        """提取任务目标，远程采集时将采集目标均分到远程执行节点。"""
        if deployment_version.remote_scope and deployment_version.remote_scope.nodes:
            remote_nodes = deployment_version.remote_scope.nodes
            targets: list[dict[str, Any]] = []
            for index, metric_target in enumerate(deployment_version.target_scope.nodes):
                execute_target = remote_nodes[index % len(remote_nodes)].copy()
                execute_target[self.METRIC_TARGET_KEY] = metric_target
                targets.append(execute_target)
            return targets
        return deployment_version.target_scope.nodes

    @staticmethod
    def _is_remote_collect(deployment_version: MetricPluginDeploymentVersion) -> bool:
        return bool(deployment_version.remote_scope and deployment_version.remote_scope.nodes)

    def _get_label_target(
        self, deploy_target: dict[str, Any], deployment_version: MetricPluginDeploymentVersion
    ) -> dict[str, Any]:
        """获取 labels 和实例参数对应的采集目标。"""
        if not self._is_remote_collect(deployment_version):
            return deploy_target

        # 远程采集时 deploy_target 是实际执行节点，labels 和参数必须使用采集目标。
        # 采集目标由 _extract_targets 在轮询分配远程执行节点时注入，避免依赖远程节点与目标节点数量一致。
        metric_target = deploy_target.get(self.METRIC_TARGET_KEY)
        if isinstance(metric_target, dict):
            return cast(dict[str, Any], metric_target)

        raise MetricPluginDeploymentOperationError(
            "SQL 远程采集任务缺少采集目标信息，请通过 _extract_targets 构造任务目标"
        )

    def get_instance_info(self, target: dict[str, Any]) -> dict[str, Any]:
        """获取目标实例信息

        Args:
            target: 目标实例信息字典，可能是主机、对象模型实例，服务实例 等（暂时支持主机目标）

        Returns:
            dict: 目标实例信息字典 example: {"instance_id":"1", "bk_cloud_id": 0, "ip": "127.0.0.1", "bk_host_id": 1, "os_type": OSType.LINUX, ...}
        """
        normalized_target = self._normalize_host_target(target)
        host_info: dict[str, Any] | None = get_host_info(normalized_target)
        if host_info is None:
            raise ValueError(f"无法获取主机信息: {target}")
        instance_id: str = ""
        # 主机类型：优先使用参数传入的 bk_host_id
        if normalized_target.get("bk_host_id") is not None:
            instance_id = str(normalized_target["bk_host_id"])
        # 主机类型：参数包含 ip + bk_cloud_id 翻译成 bk_host_id
        elif normalized_target.get("ip") and normalized_target.get("bk_cloud_id") is not None:
            instance_id = str(host_info.get("bk_host_id"))
        if not instance_id:
            raise ValueError(f"无法生成实例ID，缺少必要字段: {target}")

        # 替换所有 . 为 _
        instance_id = str(instance_id).replace(".", "_")

        # 主机类实例id统一添加host_前缀，避免与其他类型实例id冲突
        host_info["instance_id"] = f"host_{instance_id}"
        return host_info

    @classmethod
    def _render_target_params_key(cls, template: str, target: dict[str, Any]) -> str:
        """根据目标信息渲染部署参数 key 模板"""
        if not template:
            raise MetricPluginDeploymentOperationError("目标参数 key 模板不能为空")

        def replace_target_field(match: re.Match[str]) -> str:
            field_name = match.group(1)
            value = target.get(field_name)
            if value is None:
                raise MetricPluginDeploymentOperationError(f"目标参数 key 模板字段不存在或为空: target.{field_name}")
            return str(value)

        params_key = cls.TARGET_PARAMS_KEY_TEMPLATE_PATTERN.sub(replace_target_field, template)
        if "{{" in params_key or "}}" in params_key:
            raise MetricPluginDeploymentOperationError(f"目标参数 key 模板格式不支持: {template}")
        return params_key

    def _get_target_params(
        self, target: dict[str, Any], deployment_version: MetricPluginDeploymentVersion
    ) -> InstanceTargetParams:
        """获取目标实例的参数
        Note:
            deployment_version.params 中包含了采集参数和插件参数，且 collector 与 plugin 字段内均是目标参数 key 为 key 的字典。
            目标参数 key 默认使用实例 id，也可以通过 target_params_key_template 配置，例如：
            "{{ target.instance_id }}" 或 "{{ target.bk_cloud_id }}_{{ target.ip }}"。
        Args:
            target: 目标实例信息字典，可能是主机、对象模型实例，服务实例 等（暂时支持主机目标）

        Returns:
            dict: 目标实例的参数字典
        """
        instance_info = self.get_instance_info(target)
        target_params_key_template = deployment_version.params.get(
            self.TARGET_PARAMS_KEY_TEMPLATE_FIELD,
            self.DEFAULT_TARGET_PARAMS_KEY_TEMPLATE,
        )
        if not isinstance(target_params_key_template, str):
            raise MetricPluginDeploymentOperationError("目标参数 key 模板必须是字符串")
        target_params_key = self._render_target_params_key(target_params_key_template, instance_info)
        collector_params = deployment_version.params.get("collector", {})
        plugin_params = deployment_version.params.get("plugin", {})

        _target_params: InstanceTargetParams = {
            "collector_params": collector_params.get(target_params_key, {}),
            "plugin_params": plugin_params.get(target_params_key, {}),
        }
        return _target_params

    @staticmethod
    def _get_collect_instance_info(job_inst: JobTaskInstance) -> dict[str, Any]:
        return job_inst.collect_instance_info or job_inst.instance_info

    def generate_config_yaml(self, job_inst: JobTaskInstance) -> str:
        """生成配置文件内容

        Args:
            job_inst: 任务实例

        Returns:
            str: 配置文件repo路径
        """
        job_id = job_inst.id
        if job_id is None:
            raise MetricPluginDeploymentOperationError("任务实例ID未设置，无法生成配置文件")
        plugin_params = job_inst.execute_params.get("plugin_params", {})

        # 生成配置文件内容
        config_yaml_content = self.plugin_manager.generate_config_yaml_content(plugin_params=plugin_params)
        # 写入到临时文件
        plugin_dir = Path(tempfile.mkdtemp())
        plugin_dir.mkdir(parents=True, exist_ok=True)
        local_config_path = plugin_dir / f"{str(job_id)}_sql_config.yml"
        with open(local_config_path, "w") as f:
            yaml.safe_dump(config_yaml_content, f)
        # 上传到 repo 里面
        remote_config_path = f"{self.plugin_manager.basic_file_path}/{str(job_id)}/sql_config.yml"
        storage = get_bkrepo_storage(StorageName.JOB)
        with open(local_config_path, "rb") as f:
            storage.save(remote_config_path, f)
        return remote_config_path

    def _generate_task_id(self, task_name: str) -> int:
        """
        生成任务ID（Job类型特有）
        使用内置hash函数对 task_name 进行哈希后取绝对值对900000000取模再加100000000，确保任务ID的唯一性和稳定性（9位数字）
        例如：task_name = "job_mysql_132_211" -> task_id = 965407863

        :return: 任务ID（9位整数类型）
        """

        task_id = abs(hash(task_name)) % 900000000 + 100000000
        return task_id

    @staticmethod
    def _normalize_label_value(value: Any) -> str:
        """将 labels 值规范化为 bkmonitorbeat 可消费的字符串。"""
        if value is None or value == "":
            return "-"
        return str(value)

    @classmethod
    def _get_service_label_value(cls, target: dict[str, Any], label_key: str) -> Any:
        service_info = target.get("service")
        if not isinstance(service_info, dict):
            return None
        service_info = cast(dict[str, Any], service_info)

        service_labels = service_info.get("labels")
        if not isinstance(service_labels, dict):
            return None
        service_labels = cast(dict[str, Any], service_labels)

        return service_labels.get(label_key)

    def _build_extra_dimensions(self, plugin_params: dict[str, Any], target: dict[str, Any]) -> dict[str, str]:
        """从 dms_insert 插件参数构建额外 labels。"""
        extra_dimensions: dict[str, str] = {}
        for param_config in self.plugin.params:
            if param_config.mode != self.DMS_INSERT_MODE:
                continue

            param_value = plugin_params.get(param_config.name)
            if param_value is None:
                continue
            if not isinstance(param_value, dict):
                raise ValueError(f"dms_insert param value must be dict, got {param_value}")
            param_mapping = cast(dict[Any, Any], param_value)

            param_type = param_config.type.lower()
            for dms_key, dms_value in param_mapping.items():
                if not dms_key:
                    continue

                label_key = str(dms_key)
                label_value_key = str(dms_value)
                label_value: Any
                if param_type == self.DMS_HOST_TYPE:
                    label_value = target.get(label_value_key, dms_value)
                elif param_type == self.DMS_SERVICE_TYPE:
                    label_value = self._get_service_label_value(target, label_value_key)
                elif param_type == self.DMS_CUSTOM_TYPE:
                    label_value = dms_value
                else:
                    label_value = dms_value

                extra_dimensions[label_key] = self._normalize_label_value(label_value)
        return extra_dimensions

    def _build_builtin_dimensions(self, target: dict[str, Any]) -> dict[str, str]:
        """构建 Job 插件固定注入 labels，并校验覆盖内置维度声明。"""
        dimensions = {
            "bk_collect_config_id": str(self.deployment.id),
            "bk_target_cloud_id": str(target.get("bk_cloud_id", "")),
            "bk_target_ip": str(target.get("ip", "")),
            "bk_target_host_id": str(target.get("bk_host_id", "")),
        }
        missing_dimensions = {dimension.field_name for dimension in JOB_PLUGIN_BUILT_IN_DIMENSIONS} - set(dimensions)
        if missing_dimensions:
            raise MetricPluginDeploymentOperationError(
                f"Job 插件固定注入 labels 缺少内置维度: {sorted(missing_dimensions)}"
            )
        return dimensions

    @classmethod
    def _normalize_bkmonitorbeat_duration(cls, value: Any, default: str, field_name: str) -> str:
        if value is None or value == "":
            value = default
        if isinstance(value, bool):
            raise MetricPluginDeploymentOperationError(f"bkmonitorbeat {field_name} 不能是布尔值")
        if isinstance(value, int | float):
            value = f"{value}s"

        duration = str(value).strip().lower()
        if cls.PLAIN_DURATION_NUMBER_PATTERN.fullmatch(duration):
            duration = f"{duration}s"
        elif duration.endswith("sec") and cls.PLAIN_DURATION_NUMBER_PATTERN.fullmatch(duration.removesuffix("sec")):
            duration = f"{duration.removesuffix('sec')}s"
        elif duration.endswith("min") and cls.PLAIN_DURATION_NUMBER_PATTERN.fullmatch(duration.removesuffix("min")):
            duration = f"{duration.removesuffix('min')}m"

        if not cls.GO_DURATION_PATTERN.fullmatch(duration):
            raise MetricPluginDeploymentOperationError(
                f"bkmonitorbeat {field_name} 必须是 Go duration 字符串，例如 60s、1m、1h30m，当前值: {value}"
            )
        return duration

    def _generate_bkmonitorbeat_yaml(
        self, job_inst: JobTaskInstance, config_target_file_path: str, binary_target_file_path: str
    ) -> str:
        """生成 bkmonitorbeat 配置文件

        Args:
            job_inst: 任务实例

        Returns:
            str: bkmonitorbeat 配置文件 repo 路径
        """
        plugin_id = self.plugin_manager.plugin.id
        data_id = self.get_data_ids().get("bk_data_id")
        if data_id is None:
            raise DataIDNotFoundError("无法获取数据ID，无法生成 bkmonitorbeat 配置文件")
        # 任务名称
        task_name: str = f"{self.plugin_manager.type}_{plugin_id}_{job_inst.id}"
        collect_params = job_inst.execute_params.get("collector_params", {})
        label_target = job_inst.instance_info
        bk_cloud_id = label_target.get("bk_cloud_id")
        ip = label_target.get("ip")
        if bk_cloud_id is None or ip is None:
            raise HostInfoNotFoundError(f"目标主机信息缺少必要字段, target: {label_target}")
        plugin_params = job_inst.execute_params.get("plugin_params", {})
        extra_dimensions = self._build_extra_dimensions(plugin_params=plugin_params, target=label_target)
        built_in_dimensions = self._build_builtin_dimensions(label_target)
        period = self._normalize_bkmonitorbeat_duration(
            collect_params.get("period"), default="60s", field_name="period"
        )
        timeout = self._normalize_bkmonitorbeat_duration(
            collect_params.get("timeout"), default="60s", field_name="timeout"
        )
        bkmonitorbeat_config_dict: dict[str, Any] = {
            "type": "script",
            "name": task_name,
            "version": 1.0,
            "max_timeout": "86400s",
            "min_period": "3s",
            "dataid": data_id,
            "tasks": [
                {
                    "task_id": self._generate_task_id(
                        task_name
                    ),  # NOTE: 此处任务id的作用,确保与nodeman下发的task_id不冲突即可
                    "bk_biz_id": self.deployment.bk_biz_id,
                    "period": period,
                    "user_env": {},
                    "timeout": timeout,
                    "dataid": data_id,
                    "command": f"{binary_target_file_path} -f {config_target_file_path}",
                    "labels": [
                        {
                            **built_in_dimensions,
                            **extra_dimensions,
                        }
                    ],
                }
            ],
        }

        # 写入到临时文件
        plugin_dir = Path(tempfile.mkdtemp())
        plugin_dir.mkdir(parents=True, exist_ok=True)
        local_config_path = plugin_dir / self.BKMONITORBEAT_CONFIG_NAME_TEMPLATE.format(
            plugin_type=self.plugin_manager.type,
            deployment_id=self.deployment.id,
            instance_id=job_inst.instance_id,
        )
        with open(local_config_path, "w") as f:
            yaml.safe_dump(bkmonitorbeat_config_dict, f, encoding="utf-8")
        # 上传到 repo 里面 与debug的区别是第二段path没有debug_前缀
        bkmonitorbeat_conf_name = os.path.basename(local_config_path)
        remote_config_path = f"{self.plugin_manager.basic_file_path}/{str(job_inst.id)}/{bkmonitorbeat_conf_name}"
        storage = get_bkrepo_storage(StorageName.JOB)
        with open(local_config_path, "rb") as f:
            storage.save(remote_config_path, f)
        return remote_config_path

    def _get_bkmonitorbeat_target_path(self, os_type: OSType) -> str:
        """获取 bkmonitorbeat 下发目标路径
        Args:
            job_inst: 任务实例
            os_type: 操作系统类型

        Returns:
            str: bkmonitorbeat 下发目标路径     "/usr/local/{settings.BK_GSE_PATH_VARIABLE}/plugins/etc/bkmonitorbeat"
        """
        linux_path = f"{get_config().blueking.gse.gse_path_variable_linux}/plugins/etc/bkmonitorbeat"
        # TODO: 后续应从节点管理适配api传入bk_cloud_id、ip等信息，动态获取不同操作系统类型的gse安装路径
        OS_TARGET_PATH = {
            OSType.LINUX: linux_path,
            OSType.WINDOWS: rf"{get_config().blueking.gse.gse_path_variable_windows}\plugins\etc\bkmonitorbeat",
            OSType.LINUX_AARCH64: linux_path,
            OSType.AIX: linux_path,
        }
        return OS_TARGET_PATH.get(os_type, linux_path)

    def _get_bkmonitorbeat_binary_dir_path(self, os_type: OSType) -> str:
        """获取 bkmonitorbeat 二进制所在目录的路径
        Args:
            os_type: 操作系统类型

        Returns:
            str: bkmonitorbeat 二进制所在目录的路径
        """
        linux_path = f"{get_config().blueking.gse.gse_path_variable_linux}/plugins/bin"
        windows_path = rf"{get_config().blueking.gse.gse_path_variable_windows}\plugins\bin"
        OS_BINARY_PATH = {
            OSType.LINUX: linux_path,
            OSType.WINDOWS: windows_path,
            OSType.LINUX_AARCH64: linux_path,
            OSType.AIX: linux_path,
        }
        return OS_BINARY_PATH.get(os_type, linux_path)

    def get_os_subscription_path(self, instance_id: str, os_type: OSType) -> str:
        """
        获取不同操作系统类型对应的插件下发的订阅目录的路径，例如: /usr/local/gse/plugins/job_plugins/{plugin_type}_{deployment_id}_{instance_id}
        Args:
            instance_id: 实例ID
            os_type: 操作系统类型
        """
        deployment_id = self.deployment.id
        linux_path = f"{get_config().blueking.gse.gse_path_variable_linux}/job_plugins/{self.plugin_manager.type}_{deployment_id}_{instance_id}"
        # TODO: 后续应从节点管理适配api传入bk_cloud_id、ip等信息，动态获取不同操作系统类型的gse安装路径
        OS_TARGET_PATH = {
            OSType.LINUX: linux_path,
            OSType.WINDOWS: rf"{get_config().blueking.gse.gse_path_variable_windows}\job_plugins\{self.plugin_manager.type}_{deployment_id}_{instance_id}",
            OSType.LINUX_AARCH64: linux_path,
            OSType.AIX: linux_path,
        }
        return OS_TARGET_PATH.get(os_type, linux_path)

    def get_os_target_path(self, instance_id: str, os_type: OSType) -> str:
        """获取不同操作系统类型对应的插件下发采集目标路径"""
        if os_type == OSType.WINDOWS:
            return rf"{self.get_os_subscription_path(instance_id=instance_id, os_type=os_type)}\{self.plugin.id}"
        return f"{self.get_os_subscription_path(instance_id=instance_id, os_type=os_type)}/{self.plugin.id}"

    def _analyze_target_changes(
        self,
        current_version: MetricPluginDeploymentVersion | None,
        new_version: MetricPluginDeploymentVersion,
    ) -> TargetChangeAnalysis:
        """根据新旧版本分析目标实例的变更类型
        分析各目标实例需要执行的操作：
        - targets_to_add: 仅下发（新增的目标，旧版本不存在）
        - targets_to_remove: 仅清理（删除的目标，新版本不存在）
        - targets_to_update: 清理+下发（新旧版本都存在但参数 hash 有变化）
        - targets_unchanged: 无变化（新旧版本都存在且参数 hash 相同）

        Args:
            current_version: 当前部署版本，如果为 None 表示首次部署
            new_version: 新部署版本

        Returns:
            TargetChangeAnalysis: 包含四类目标实例列表的分析结果,当前一定是主机目标 [{"bk_host_id": 1,"bk_cloud_id":0,"ip": "127.0.0.1"...},...]
        """
        # 初始化结果
        result: TargetChangeAnalysis = {
            "targets_to_add": [],
            "targets_to_remove": [],
            "targets_to_update": [],
            "targets_unchanged": [],
        }

        # 如果没有当前版本，说明是首次部署，所有目标都是新增
        if current_version is None:
            result["targets_to_add"] = self._extract_targets(new_version).copy()
            self._log(
                logging.DEBUG,
                f"首次部署，所有目标为新增: {len(result['targets_to_add'])} 个",
            )
            return result

        # 构建旧版本目标的 instance_id -> target 映射
        old_targets_map: dict[str, dict[str, Any]] = {}
        for target in self._extract_targets(current_version):
            try:
                instance_id = self.get_instance_info(self._get_label_target(target, current_version))["instance_id"]
                old_targets_map[instance_id] = target
            except ValueError:
                # 无法生成实例ID的目标跳过
                self._log(
                    logging.WARN,
                    f"旧版本目标无法生成实例ID，跳过: {target}",
                )
                continue

        # 构建新版本目标的 instance_id -> target 映射
        new_targets_map: dict[str, dict[str, Any]] = {}
        for target in self._extract_targets(new_version):
            try:
                instance_id = self.get_instance_info(self._get_label_target(target, new_version))["instance_id"]
                new_targets_map[instance_id] = target
            except ValueError:
                # 无法生成实例ID的目标跳过
                self._log(
                    logging.WARN,
                    f"新版本目标无法生成实例ID，跳过: {target}",
                )
                continue

        old_instance_ids = set(old_targets_map.keys())
        new_instance_ids = set(new_targets_map.keys())

        # 分析目标变更
        # 1. 仅下发：新增的目标（在新版本中存在，旧版本中不存在）
        added_ids = new_instance_ids - old_instance_ids
        result["targets_to_add"] = [new_targets_map[inst_id] for inst_id in added_ids]

        # 2. 仅清理：删除的目标（在旧版本中存在，新版本中不存在）
        removed_ids = old_instance_ids - new_instance_ids
        result["targets_to_remove"] = [old_targets_map[inst_id] for inst_id in removed_ids]

        # 3. 处理新旧版本都存在的目标，比对参数 hash 是否变化
        common_ids = old_instance_ids & new_instance_ids

        for inst_id in common_ids:
            old_target = old_targets_map[inst_id]
            new_target = new_targets_map[inst_id]

            # 比对目标对应的实例参数是否有变化
            old_params = self._get_target_params(old_target, current_version)
            new_params = self._get_target_params(new_target, new_version)
            old_collect_instance_info = self.get_instance_info(old_target)
            new_collect_instance_info = self.get_instance_info(new_target)

            if old_params != new_params or old_collect_instance_info != new_collect_instance_info:
                # 参数有变化，需要清理+下发
                result["targets_to_update"].append(new_target)
            else:
                # 参数无变化
                result["targets_unchanged"].append(new_target)

        self._log(
            logging.DEBUG,
            f"目标变更分析完成: 新增={len(result['targets_to_add'])}, 删除={len(result['targets_to_remove'])}, 更新={len(result['targets_to_update'])}, 无变化={len(result['targets_unchanged'])}",
        )

        return result

    def _create_task_instances(
        self,
        action: JobTaskActionEnum,
        targets: list[dict[str, Any]] | None = None,
    ) -> dict[str, int]:
        """为目标实例列表创建任务实例

        按目标拆分，每个目标对应一个 JobTaskInstanceModel 实例。

        Args:
            action: 操作类型
            targets: 目标实例列表，如果为 None 则从 deployment_version 中提取

        Returns:
            dict: instance_id -> job_inst_id 的映射
        """
        inst_mapping: dict[str, int] = {}
        if self.deployment_version is None:
            raise MetricPluginDeploymentOperationError("目标部署版本未设置，无法创建任务实例")

        # 解析目标：优先使用传入的 targets，否则从 deployment_version 中提取
        if targets is None:
            targets = self._extract_targets(self.deployment_version)

        if not targets:
            self._log(logging.DEBUG, f"无目标实例需要创建任务, 操作类型: {action.value}")
            return inst_mapping

        with transaction.atomic():
            for target in targets:
                target_params = self._get_target_params(target, deployment_version=self.deployment_version)
                instance_info = self.get_instance_info(self._get_label_target(target, self.deployment_version))
                collect_instance_info = self.get_instance_info(target)
                instance_id = instance_info["instance_id"]

                task_instance = JobTaskInstanceModel.objects.create(
                    bk_tenant_id=self.deployment.bk_tenant_id,
                    bk_biz_id=self.deployment.bk_biz_id,
                    action=action.value,
                    status=JobTaskStatusEnum.PENDING.value,
                    instance_id=instance_id,
                    instance_info=instance_info,
                    collect_instance_info=collect_instance_info,
                    execute_params=target_params,
                    created_by=self.operator,
                )

                inst_mapping[instance_id] = task_instance.pk
                self._log(
                    logging.DEBUG,
                    f"创建任务实例: {task_instance.pk}, 实例: {instance_id}, 操作类型: {action.value}",
                )

        self._log(
            logging.INFO,
            f"批量创建任务实例完成, 操作类型: {action.value}, 实例数量: {len(inst_mapping)}",
        )

        return inst_mapping

    def get_all_task_instances(self) -> list[JobTaskInstanceModel]:
        """获取当前映射中的所有任务实例

        Returns:
            list: 任务实例列表
        """
        inst_ids = list(self.job_inst_mapping.values())
        if not inst_ids:
            return []
        return list(JobTaskInstanceModel.objects.filter(pk__in=inst_ids))

    def _check_support(self, deployment_version: MetricPluginDeploymentVersion) -> None:
        """检查插件和部署项是否支持 SQL 安装器
        Note:
            1. 目前仅支持主机类型的插件安装
            2. 仅支持主机目标类型的安装
        Args:
            deployment_version: 部署版本

        Raises:
            MetricPluginDeploymentOperationError: 不支持 SQL 安装器
        """
        if self._label_to_object_type(self.plugin.label) != InstanceType.HOST.value:
            raise MetricPluginDeploymentOperationError("SQL 安装器暂不支持非主机类型插件的安装操作")
        if deployment_version.target_scope.node_type != TargetNodeType.HOST.value:
            raise MetricPluginDeploymentOperationError("SQL 安装器暂不支持非主机目标类型的安装操作")

    def _build_common_task_context(self, job_inst: JobTaskInstance) -> dict[str, Any]:
        """构建任务公共上下文"""
        collector_params = job_inst.execute_params.get("collector_params", {})
        # 目标信息: 创建任务实例时已经解析过
        collect_target: dict[str, Any] = self._get_collect_instance_info(job_inst)
        # 解析标准目标服务器信息
        bk_host_id = collect_target.get("bk_host_id")
        if not bk_host_id:
            raise ParseOsTypeError(f"主机信息缺少必要字段 target: {collect_target}")
        target_server = self.plugin_manager.parse_target_server(collect_host=collect_target)

        # 获取插件二进制参数
        os_type = get_os_type_by_collect_host(collect_target)
        if os_type is None:
            raise ParseOsTypeError(f"无法解析操作系统类型, target: {collect_target}")
        # 插件下发调用job所需用户
        if os_type in [OSType.WINDOWS]:
            account_alias = collector_params.get("job_account_alias", "system")
        else:
            account_alias = collector_params.get("job_account_alias", "root")
        return {
            "job_task_inst_id": job_inst.id,
            # "plugin": self.plugin.model_dump(), # 需要序列化，不方便传递
            "os_type": os_type.value,
            "target_server": target_server,
            "account_alias": account_alias,
        }

    def _build_install_task_context(self, job_inst: JobTaskInstance) -> dict[str, Any]:
        """构建任务上下文"""
        # 任务上下文参数
        task_params: dict[str, Any] = self._build_common_task_context(job_inst=job_inst)
        # 目标参数: 采集参数 + 插件参数
        collector_params = job_inst.execute_params.get("collector_params", {})
        plugin_params = job_inst.execute_params.get("plugin_params", {})

        task_params.update(collector_params)
        task_params.update(plugin_params)
        # 目标信息: 创建任务实例时已经解析过
        collect_target: dict[str, Any] = self._get_collect_instance_info(job_inst)
        bk_host_id = collect_target.get("bk_host_id")
        if not bk_host_id:
            raise ParseOsTypeError(f"主机信息缺少必要字段 target: {collect_target}")
        # 获取插件二进制参数
        os_type = get_os_type_by_collect_host(collect_target)
        if os_type is None:
            raise ParseOsTypeError(f"无法解析操作系统类型, target: {collect_target}")
        if job_inst.id is None:
            raise MetricPluginDeploymentOperationError("任务实例ID未设置，无法获取任务参数")

        target_path = self.get_os_target_path(instance_id=job_inst.instance_id, os_type=os_type)
        binary_path = self.plugin_manager.get_binary_path(os_type=os_type)
        task_params["target_path"] = target_path
        task_params["binary_path"] = binary_path

        # 生成下发采集用的 sql_config.yml 文件
        sql_yaml_file_path = self.generate_config_yaml(job_inst=job_inst)
        # 采集用的 sql_config.yml 文件路径
        task_params["sql_config_file_path"] = sql_yaml_file_path

        # 添加需要的额外下发的文件
        extra_file_source_paths = self.plugin_manager.get_extra_file_source_paths(os_type=os_type)
        task_params["extra_file_source_paths"] = extra_file_source_paths

        # 计算二进制下发后路径
        binary_file_name = os.path.basename(binary_path)
        binary_target_file_path = os.path.join(target_path, binary_file_name)
        if os_type == OSType.WINDOWS:
            binary_target_file_path = PathFormatter.format_path(binary_target_file_path, style=PathStyle.WINDOWS)
        else:
            binary_target_file_path = PathFormatter.format_path(binary_target_file_path, style=PathStyle.POSIX)
        # 计算配置文件下发后路径
        config_file_name = os.path.basename(sql_yaml_file_path)
        config_target_file_path = os.path.join(target_path, config_file_name)
        if os_type == OSType.WINDOWS:
            config_target_file_path = PathFormatter.format_path(config_target_file_path, style=PathStyle.WINDOWS)
        else:
            config_target_file_path = PathFormatter.format_path(config_target_file_path, style=PathStyle.POSIX)
        # bkmonitorbeat conf 文件路径
        bkmonitorbeat_conf_path = self._generate_bkmonitorbeat_yaml(
            job_inst=job_inst,
            config_target_file_path=config_target_file_path,
            binary_target_file_path=binary_target_file_path,
        )
        task_params["bkmonitorbeat_conf_source_file_path"] = bkmonitorbeat_conf_path
        # bkmonitorbeat 下发目录的路径
        task_params["bkmonitorbeat_conf_target_path"] = self._get_bkmonitorbeat_target_path(os_type=os_type)
        task_params["bkmonitorbeat_binary_dir_path"] = self._get_bkmonitorbeat_binary_dir_path(os_type=os_type)

        # 补充 bkmonitorbeat_config_file 和 bkmonitorbeat_path
        bkmonitorbeat_target_path = task_params.get("bkmonitorbeat_conf_target_path", "")
        bkmonitorbeat_conf_name = self.BKMONITORBEAT_CONFIG_NAME_TEMPLATE.format(
            plugin_type=self.plugin_manager.type,
            deployment_id=self.deployment.id,
            instance_id=job_inst.instance_id,
        )
        if os_type == OSType.WINDOWS:
            bkmonitorbeat_config_file = rf"{bkmonitorbeat_target_path}\{bkmonitorbeat_conf_name}"
        else:
            bkmonitorbeat_config_file = f"{bkmonitorbeat_target_path}/{bkmonitorbeat_conf_name}"
        plugin_subscription_path = self.get_os_subscription_path(instance_id=job_inst.instance_id, os_type=os_type)
        # 准备脚本参数
        script_params = {
            "bkmonitorbeat_binary_dir_path": task_params.get("bkmonitorbeat_binary_dir_path"),
            "bkmonitorbeat_config_file": bkmonitorbeat_config_file,
            "plugin_target_path": target_path,  # 插件二进制下发目标路径
            "plugin_subscription_path": plugin_subscription_path,
            "binary_target_file_path": binary_target_file_path,  # 插件二进制下发完整路径
        }

        # 渲染脚本
        restart_bkmonitorbeat_script = self.RESTART_BKMONITORBEAT_SCRIPTS.get(
            os_type, self.RESTART_BKMONITORBEAT_SCRIPTS[OSType.LINUX]
        ).format(**script_params)

        chmod_plugin_script = self.CHMOD_PLUGIN_SCRIPTS.get(os_type, self.CHMOD_PLUGIN_SCRIPTS[OSType.LINUX]).format(
            **script_params
        )

        remove_config_script = self.REMOVE_CONFIG_SCRIPTS.get(os_type, self.REMOVE_CONFIG_SCRIPTS[OSType.LINUX]).format(
            **script_params
        )

        remove_plugin_script = self.REMOVE_PLUGIN_SCRIPTS.get(os_type, self.REMOVE_PLUGIN_SCRIPTS[OSType.LINUX]).format(
            **script_params
        )

        ext_context: dict[str, Any] = {
            # Plugin subscription_path
            "plugin_subscription_path": plugin_subscription_path,
            # Bkmonitorbeat config
            "bkmonitorbeat_config_file": bkmonitorbeat_config_file,
            "bkmonitorbeat_target_path": bkmonitorbeat_target_path,
            # Scripts
            "restart_bkmonitorbeat_script": restart_bkmonitorbeat_script,
            "remove_config_script": remove_config_script,
            "remove_plugin_script": remove_plugin_script,
            "chmod_plugin_script": chmod_plugin_script,
        }
        task_params.update(ext_context)
        return task_params

    @override
    def install(self, deployment_version: MetricPluginDeploymentVersion) -> Any:
        """安装特定的部署版本

        Note:
            1. 比对当前部署版本与新部署版本，判断是否存在差异
            2. 如果相同，则跳过
            3. 如果不同，创建新的部署版本记录，并设置为当前版本
            4. 按主机拆分，为每个主机创建独立的任务实例
            5. 返回差异比对结果和任务映射
            6. 新旧版本目标差异时，需要对新增/删除的目标实例进行下发/清理操作，更新的目标实例则进行清理+下发操作完成更新

        Args:
            deployment_version: 部署版本

        Returns:
            dict: 包含以下字段的结果字典：
                - job_inst_mapping: instance_id -> job_inst_id 的映射
                - diff_result: 版本差异比对结果
                - target_changes: 目标变更分析结果，包含：
                    - targets_to_add: 仅下发（新增的目标）
                    - targets_to_remove: 仅清理（删除的目标）
                    - targets_to_update: 清理+下发（更新的目标）
                    - targets_unchanged: 无变化的目标
        """
        # 加载当前版本（如果尚未加载）
        if not self.deployment_version:
            self.deployment_version = self._get_current_deployment_version()
        # 检查是否支持 SQL 安装器
        self._check_support(deployment_version)

        # 比对当前版本与新版本，判断是否存在差异(不存在current_version则视为有变化)
        is_modified, diff_result = self.get_version_diff(self.deployment_version, deployment_version)
        # 如果没有变化，则复用上一版本的版本号，不产生新版本记录
        if not is_modified:
            if not self.deployment_version:
                raise RuntimeError("安装逻辑错误：当前版本不存在且新版本无变化")
            deployment_version.version = self.deployment_version.version

        deployment_model = MetricPluginDeploymentModel.objects.get(id=deployment_version.deployment_id)
        # 分析目标变更，确定哪些需要下发、清理、更新
        target_changes = self._analyze_target_changes(self.deployment_version, deployment_version)

        # TODO: 兜底检查，如果部分实例未完成部署，禁止继续安装新版本

        # 更新当前版本对象为新版本对象，以便后续 _create_task_instances 等方法使用
        self.deployment_version = deployment_version

        # 根据 target_changes 分类创建任务实例
        inst_mapping: dict[str, int] = {}

        # 需要执行的全部任务实例
        need_execute_task_instance_ids: set[int] = set()
        with transaction.atomic():
            # 保存版本记录并更新当前版本标识
            remote_scope = deployment_version.remote_scope
            MetricPluginDeploymentVersionModel.objects.update_or_create(
                bk_tenant_id=deployment_version.bk_tenant_id,
                bk_biz_id=deployment_version.bk_biz_id,
                deployment=deployment_model,
                version=deployment_version.version,
                defaults={
                    "plugin_version": f"{deployment_version.plugin_version.major}.{deployment_version.plugin_version.minor}",
                    "params": deployment_version.params,
                    "target_node_type": deployment_version.target_scope.node_type,
                    "target_nodes": deployment_version.target_scope.nodes,
                    "remote_node_type": remote_scope.node_type if remote_scope else "",
                    "remote_nodes": remote_scope.nodes if remote_scope else [],
                    "is_current": True,
                    "created_by": deployment_version.created_by,
                },
            )
            # 将该部署项的其他版本设置为非当前版本
            MetricPluginDeploymentVersionModel.objects.filter(
                deployment=deployment_model,
                bk_tenant_id=deployment_model.bk_tenant_id,
                bk_biz_id=deployment_model.bk_biz_id,
            ).exclude(version=deployment_version.version).update(is_current=False)

            # 1. 新增的目标：创建 INSTALL 任务（仅下发）
            if target_changes["targets_to_add"]:
                add_mapping = self._create_task_instances(
                    action=JobTaskActionEnum.INSTALL,
                    targets=target_changes["targets_to_add"],
                )
                inst_mapping.update(add_mapping)
                need_execute_task_instance_ids.update(add_mapping.values())

            # 2. 删除的目标：创建 UNINSTALL 任务（仅清理）
            if target_changes["targets_to_remove"]:
                remove_mapping = self._create_task_instances(
                    action=JobTaskActionEnum.UNINSTALL,
                    targets=target_changes["targets_to_remove"],
                )
                # inst_mapping 中移除这部分实例关联
                for inst_id in remove_mapping.keys():
                    inst_mapping.pop(inst_id, None)
                need_execute_task_instance_ids.update(remove_mapping.values())

            # 3. 更新的目标：创建 UPDATE 任务（清理+下发）
            if target_changes["targets_to_update"]:
                update_mapping = self._create_task_instances(
                    action=JobTaskActionEnum.UPDATE,
                    targets=target_changes["targets_to_update"],
                )
                inst_mapping.update(update_mapping)
                need_execute_task_instance_ids.update(update_mapping.values())
        # 获取需要执行的任务实例
        all_job_instances: list[JobTaskInstance] = [
            i.to_instance() for i in JobTaskInstanceModel.objects.filter(pk__in=need_execute_task_instance_ids).all()
        ]
        # 更新映射关系
        self.job_inst_mapping = inst_mapping
        # 更新部署状态为部署中
        self.deployment.status = MetricPluginDeploymentStatusEnum.DEPLOYING.value

        self._save()
        self._log(
            logging.INFO,
            f"开始安装部署版本 {deployment_version.version}, 新增: {len(target_changes['targets_to_add'])}, 删除: {len(target_changes['targets_to_remove'])}, 更新: {len(target_changes['targets_to_update'])}, 无变化: {len(target_changes['targets_unchanged'])}",
        )
        # 触发任务下发
        for job_instance in all_job_instances:
            try:
                if job_instance.id is None:
                    raise MetricPluginDeploymentOperationError("任务实例ID未设置，无法提交任务")
                if job_instance.action == JobTaskActionEnum.INSTALL:
                    task_params: dict[str, Any] = self._build_install_task_context(
                        job_inst=job_instance,
                    )
                    job_instance.execute_params.update(
                        {
                            "task_params": task_params,
                        }
                    )
                    JobTaskInstanceModel.save_instance(job_instance)
                    # NOTE: TRANSFER_PLUGIN -> TRANSFER_BKMONITORBEAT_CONFIG -> CHMOD_PLUGIN -> RESTART_BKMONITORBEAT
                    submit_install_task(job_instance.id, task_params)
                elif job_instance.action == JobTaskActionEnum.UNINSTALL:
                    task_params = self._build_uninstall_task_context(
                        job_inst=job_instance,
                    )
                    job_instance.execute_params.update(
                        {
                            "task_params": task_params,
                        }
                    )
                    JobTaskInstanceModel.save_instance(job_instance)
                    # NOTE: REMOVE_PLUGIN -> REMOVE_CONFIG -> RESTART_BKMONITORBEAT
                    submit_uninstall_task(job_instance.id, task_params)
                elif job_instance.action == JobTaskActionEnum.UPDATE:
                    task_params = self._build_install_task_context(
                        job_inst=job_instance,
                    )
                    job_instance.execute_params.update(
                        {
                            "task_params": task_params,
                        }
                    )
                    JobTaskInstanceModel.save_instance(job_instance)
                    # 实际上task内是先卸载再安装（根据job action会二次判断）
                    # NOTE: REMOVE_PLUGIN -> REMOVE_CONFIG -> RESTART_BKMONITORBEAT -> TRANSFER_PLUGIN -> TRANSFER_BKMONITORBEAT_CONFIG -> CHMOD_PLUGIN -> RESTART_BKMONITORBEAT
                    submit_uninstall_task(job_instance.id, task_params)

            except Exception as e:
                job_instance.fail_task(f"下发任务触发失败: {e}")
                logger.exception("下发任务触发失败")
                JobTaskInstanceModel.save_instance(job_instance)
        return {
            "deployment_id": self.deployment.id,
            "job_inst_mapping": inst_mapping,
            "diff_result": diff_result,
            "target_changes": target_changes,
        }

    def _build_uninstall_task_context(self, job_inst: JobTaskInstance) -> dict[str, Any]:
        """获取目标实例的卸载任务参数

        Args:
            job_inst: 任务实例
        Returns:
            dict: 目标实例的卸载任务参数字典
        """
        task_params: dict[str, Any] = self._build_common_task_context(job_inst=job_inst)

        target: dict[str, Any] = self._get_collect_instance_info(job_inst)
        collect_host = target.get("bk_host_id")
        if not collect_host:
            raise ParseOsTypeError(f"主机信息缺少必要字段, target: {target}")
        os_type = get_os_type_by_collect_host(target)
        if os_type is None:
            raise ParseOsTypeError(f"无法解析操作系统类型, target: {target}")
        if job_inst.id is None:
            raise MetricPluginDeploymentOperationError("任务实例ID未设置，无法获取卸载任务参数")
        # 渲染删除插件脚本
        task_params["plugin_target_path"] = self.get_os_target_path(instance_id=job_inst.instance_id, os_type=os_type)
        task_params["plugin_subscription_path"] = self.get_os_subscription_path(
            instance_id=job_inst.instance_id, os_type=os_type
        )
        task_params["remove_plugin_script"] = self.REMOVE_PLUGIN_SCRIPTS.get(
            os_type, self.REMOVE_PLUGIN_SCRIPTS[OSType.LINUX]
        ).format(plugin_subscription_path=task_params["plugin_subscription_path"])
        # 渲染删除 bkmonitorbeat 配置文件脚本
        bkmonitorbeat_target_path = self._get_bkmonitorbeat_target_path(os_type=os_type)
        bkmonitorbeat_conf_name = self.BKMONITORBEAT_CONFIG_NAME_TEMPLATE.format(
            plugin_type=self.plugin_manager.type,
            deployment_id=self.deployment.id,
            instance_id=job_inst.instance_id,
        )
        if os_type == OSType.WINDOWS:
            bkmonitorbeat_config_file = rf"{bkmonitorbeat_target_path}\{bkmonitorbeat_conf_name}"
        else:
            bkmonitorbeat_config_file = f"{bkmonitorbeat_target_path}/{bkmonitorbeat_conf_name}"
        task_params["remove_config_script"] = self.REMOVE_CONFIG_SCRIPTS.get(
            os_type, self.REMOVE_CONFIG_SCRIPTS[OSType.LINUX]
        ).format(bkmonitorbeat_config_file=bkmonitorbeat_config_file)
        # 渲染重启 bkmonitorbeat 脚本
        task_params["restart_bkmonitorbeat_script"] = self.RESTART_BKMONITORBEAT_SCRIPTS.get(
            os_type, self.RESTART_BKMONITORBEAT_SCRIPTS[OSType.LINUX]
        ).format(bkmonitorbeat_binary_dir_path=self._get_bkmonitorbeat_binary_dir_path(os_type=os_type))

        return task_params

    def _build_stop_task_context(self, job_inst: JobTaskInstance) -> dict[str, Any]:
        """获取采集项的停止任务参数

        Args:
            job_inst: 任务实例
        Returns:
            dict: 目标实例的卸载任务参数字典
        """
        task_params: dict[str, Any] = self._build_common_task_context(job_inst=job_inst)

        target: dict[str, Any] = self._get_collect_instance_info(job_inst)
        collect_host = target.get("bk_host_id")
        if not collect_host:
            raise ParseOsTypeError(f"主机信息缺少必要字段, target: {target}")
        os_type = get_os_type_by_collect_host(target)
        if os_type is None:
            raise ParseOsTypeError(f"无法解析操作系统类型, target: {target}")
        if job_inst.id is None:
            raise MetricPluginDeploymentOperationError("任务实例ID未设置，无法获取卸载任务参数")
        # 渲染删除 bkmonitorbeat 配置文件脚本
        bkmonitorbeat_target_path = self._get_bkmonitorbeat_target_path(os_type=os_type)
        bkmonitorbeat_conf_name = self.BKMONITORBEAT_CONFIG_NAME_TEMPLATE.format(
            plugin_type=self.plugin_manager.type,
            deployment_id=self.deployment.id,
            instance_id=job_inst.instance_id,
        )
        if os_type == OSType.WINDOWS:
            bkmonitorbeat_config_file = rf"{bkmonitorbeat_target_path}\{bkmonitorbeat_conf_name}"
        else:
            bkmonitorbeat_config_file = f"{bkmonitorbeat_target_path}/{bkmonitorbeat_conf_name}"
        task_params["remove_config_script"] = self.REMOVE_CONFIG_SCRIPTS.get(
            os_type, self.REMOVE_CONFIG_SCRIPTS[OSType.LINUX]
        ).format(bkmonitorbeat_config_file=bkmonitorbeat_config_file)
        # 渲染重启 bkmonitorbeat 脚本
        task_params["restart_bkmonitorbeat_script"] = self.RESTART_BKMONITORBEAT_SCRIPTS.get(
            os_type, self.RESTART_BKMONITORBEAT_SCRIPTS[OSType.LINUX]
        ).format(bkmonitorbeat_binary_dir_path=self._get_bkmonitorbeat_binary_dir_path(os_type=os_type))

        return task_params

    @override
    def uninstall(self) -> Any:
        """卸载插件

        Raises:
            MetricPluginDeploymentOperationError: 部署状态不允许卸载
        """
        self._deployment_status_refresh()
        # 检查状态是否允许卸载
        if self.deployment.status in [
            MetricPluginDeploymentStatusEnum.DEPLOYING.value,
            MetricPluginDeploymentStatusEnum.STARTING.value,
            MetricPluginDeploymentStatusEnum.STOPPING.value,
            MetricPluginDeploymentStatusEnum.INITIALIZING.value,
        ]:
            raise MetricPluginDeploymentOperationError(f"部署状态为 {self.deployment.status}非终态，无法卸载")
        # 获取当前版本
        current_version = self._get_current_deployment_version()
        if not current_version:
            raise MetricPluginDeploymentOperationError("当前版本不存在")
        self.deployment_version = current_version
        # 1. 创建任务实例
        inst_mapping = self._create_task_instances(JobTaskActionEnum.UNINSTALL)
        # 2. 提交任务
        for _instance_id, job_inst_id in inst_mapping.items():
            job_inst = JobTaskInstanceModel.objects.get(pk=job_inst_id).to_instance()

            context = self._build_uninstall_task_context(
                job_inst=job_inst,
            )
            job_inst.execute_params.update(
                {
                    "task_params": context,
                }
            )
            JobTaskInstanceModel.save_instance(job_inst)
            # TODO: REMOVE_PLUGIN -> REMOVE_CONFIG -> RESTART_BKMONITORBEAT
            submit_uninstall_task(job_inst_id, context)

        # 删除部署版本和部署项
        MetricPluginDeploymentVersionModel.objects.filter(deployment_id=self.deployment.id).delete()
        MetricPluginDeploymentModel.objects.filter(id=self.deployment.id).delete()

    @override
    def stop(self) -> Any:
        """
        停止插件

        Note:
            1. 只有运行中状态才能执行停止操作
        """
        self._deployment_status_refresh()
        if self.deployment.status != MetricPluginDeploymentStatusEnum.RUNNING.value:
            raise MetricPluginDeploymentOperationError(f"部署状态为 {self.deployment.status}，无法停止")
        if self.deployment_version is None:
            self.deployment_version = self._get_current_deployment_version()
        if self.deployment_version is None:
            raise MetricPluginDeploymentOperationError("当前部署版本不存在，无法停止")
        inst_mapping = self._create_task_instances(JobTaskActionEnum.STOP)

        for _instance_id, job_inst_id in inst_mapping.items():
            job_inst = JobTaskInstanceModel.objects.get(pk=job_inst_id).to_instance()
            # TODO: stop task params need refector,too many not used params
            task_params = self._build_stop_task_context(
                job_inst=job_inst,
            )
            job_inst.execute_params.update(
                {
                    "task_params": task_params,
                }
            )
            JobTaskInstanceModel.save_instance(job_inst)

            # NOTE: REMOVE_CONFIG -> RESTART_BKMONITORBEAT
            submit_stop_task(job_inst_id, task_params)
        # 更新映射关系
        self.job_inst_mapping = inst_mapping
        self.deployment.status = MetricPluginDeploymentStatusEnum.STOPPING.value
        self._save()

    @override
    def start(self) -> Any:
        """启动插件

        Note:
            只有在已停止状态下才能启动

        """
        self._deployment_status_refresh()
        if self.deployment.status != MetricPluginDeploymentStatusEnum.STOPPED.value:
            raise MetricPluginDeploymentOperationError(f"部署状态为 {self.deployment.status}，无法启动")
        if self.deployment_version is None:
            self.deployment_version = self._get_current_deployment_version()
        if self.deployment_version is None:
            raise MetricPluginDeploymentOperationError("当前部署版本不存在，无法启动")
        inst_mapping = self._create_task_instances(JobTaskActionEnum.START)

        for _instance_id, job_inst_id in inst_mapping.items():
            job_inst = JobTaskInstanceModel.objects.get(pk=job_inst_id).to_instance()
            task_params = self._build_install_task_context(
                job_inst=job_inst,
            )
            job_inst.execute_params.update(
                {
                    "task_params": task_params,
                }
            )
            JobTaskInstanceModel.save_instance(job_inst)
            # NOTE: TRANSFER_BKMONITORBEAT_CONFIG -> CHMOD_PLUGIN -> RESTART_BKMONITORBEAT
            submit_start_task(job_inst_id, task_params)

        # 更新映射关系
        self.job_inst_mapping = inst_mapping
        self.deployment.status = MetricPluginDeploymentStatusEnum.STARTING.value
        self._save()

    @override
    def retry(self, scope: MetricPluginDeploymentScope | None = None) -> Any:
        """重试失败的任务
        TODO: 目前仅支持安装阶段的重试，后续可扩展到停止、启动等操作的重试，当前仅支持采集项整体重试，例如部分实例成功了，部分实例失败，会全部先卸载后安装！

        Args:
            scope: 操作范围，如果为 None，则重试所有失败的主机

        Raises:
            MetricPluginDeploymentOperationError: 版本不存在或没有可重试的任务
        """
        self._deployment_status_refresh()
        targets = []
        if self.deployment_version is None:
            self.deployment_version = self._get_current_deployment_version()
        if self.deployment_version is None:
            raise MetricPluginDeploymentOperationError("当前部署版本不存在，无法重试")
        self._check_support(self.deployment_version)
        instance_ids: list[str] = []
        if scope and scope.nodes:
            instance_ids = [self.get_instance_info(node)["instance_id"] for node in scope.nodes]
        if instance_ids:
            all_targets = self._extract_targets(self.deployment_version)
            for t in all_targets:
                info = self.get_instance_info(self._get_label_target(t, self.deployment_version))
                if info["instance_id"] in instance_ids:
                    targets.append(t)
        # 没有指定范围，则重试所有失败的任务
        else:
            targets = self._extract_targets(self.deployment_version)
        # TODO: 是否过滤已经成功的实例，且过滤掉非终态的实例?
        inst_mapping = self._create_task_instances(JobTaskActionEnum.RETRY, targets=targets)

        for _instance_id, job_inst_id in inst_mapping.items():
            job_inst = JobTaskInstanceModel.objects.get(pk=job_inst_id).to_instance()

            task_params = self._build_install_task_context(
                job_inst=job_inst,
            )
            job_inst.execute_params.update(
                {
                    "task_params": task_params,
                }
            )
            JobTaskInstanceModel.save_instance(job_inst)

            # Retry: Uninstall -> Install
            submit_uninstall_task(job_inst_id, task_params)

        # 更新映射关系
        self.job_inst_mapping = inst_mapping
        self.deployment.status = MetricPluginDeploymentStatusEnum.DEPLOYING.value
        self._save()

        return {"job_inst_mapping": inst_mapping}

    @override
    def run(self, action: str | None = None, scope: MetricPluginDeploymentScope | None = None) -> Any:
        """主动执行操作
        NOTE: job类型插件暂不支持该操作
        Args:
            action: 操作类型，根据插件类型自定义
            scope: 操作范围，如果为 None，则为全部
        Raises:
            NotImplementedError: 主动执行操作待实现
        """
        raise NotImplementedError("主动执行操作待实现")

    @override
    def revoke(self, scope: MetricPluginDeploymentScope | None = None) -> Any:
        """终止执行 暂不支持

        Args:
            scope: 操作范围，如果为 None，则终止所有运行中的任务

        Returns:
            dict: 被终止的任务映射
        Raises:
            NotImplementedError: 该功能暂不支持
        """
        raise NotImplementedError("任务终止功能待实现")

    def _build_instance_status_info(self, task: JobTaskInstance, with_detail: bool = False) -> InstanceStatusInfo:
        """构建实例状态信息

        Args:
            task: 任务实例（JobTaskInstance
            with_detail: 是否包含详细信息

        Returns:
            InstanceStatusInfo: 实例状态信息
        """
        # 统一获取 task_id
        task_id = task.id
        if task_id is None:
            raise MetricPluginDeploymentOperationError("任务实例ID未设置，无法获取状态信息")
        # 统一获取 to_dict 方法
        detail_dict = task.to_dict()

        info: InstanceStatusInfo = {
            "task_id": task_id,
            "status": task.status,
            "current_step": task.current_step,
            "error_message": task.error_message,
        }
        if with_detail:
            info["detail"] = detail_dict
        return info

    def _deployment_status_refresh(self) -> None:
        """刷新部署项的整体状态"""
        all_tasks = self.get_all_task_instances()
        if not all_tasks:
            self._log(logging.DEBUG, "无任务实例，跳过状态刷新")
            return

        statuses = {task.status for task in all_tasks}

        # NOTE: 整理状态优先级： FAILED > RUNNING/PENDING > SUCCESS > others
        if JobTaskStatusEnum.FAILED.value in statuses:
            self.deployment.status = MetricPluginDeploymentStatusEnum.FAILED.value
        elif JobTaskStatusEnum.RUNNING.value in statuses or JobTaskStatusEnum.PENDING.value in statuses:
            # 需要根据任务的 action 来决定部署状态
            # 取最新的任务来判断（按创建时间倒序，取第一个）
            latest_task = max(all_tasks, key=lambda t: t.created_at)
            if latest_task.action == JobTaskActionEnum.STOP.value:
                self.deployment.status = MetricPluginDeploymentStatusEnum.STOPPING.value
            elif latest_task.action == JobTaskActionEnum.START.value:
                self.deployment.status = MetricPluginDeploymentStatusEnum.STARTING.value
            else:
                self.deployment.status = MetricPluginDeploymentStatusEnum.DEPLOYING.value
        elif statuses == {JobTaskStatusEnum.SUCCESS.value}:
            # 需要根据任务的 action 来决定最终状态
            # 取最新的任务来判断（按创建时间倒序，取第一个）
            latest_task = max(all_tasks, key=lambda t: t.created_at)
            if latest_task.action == JobTaskActionEnum.STOP.value:
                self.deployment.status = MetricPluginDeploymentStatusEnum.STOPPED.value
            elif latest_task.action in [
                JobTaskActionEnum.INSTALL.value,
                JobTaskActionEnum.START.value,
                JobTaskActionEnum.UPDATE.value,
            ]:
                self.deployment.status = MetricPluginDeploymentStatusEnum.RUNNING.value
            else:
                self.deployment.status = MetricPluginDeploymentStatusEnum.RUNNING.value
        else:
            self.deployment.status = MetricPluginDeploymentStatusEnum.STOPPED.value

        self._save()

    @override
    def status(self, instance_id: str | None = None, with_detail: bool = False) -> InstallerStatusResult:
        """获取执行状态

        Args:
            instance_id: 实例ID，如果为 None，则返回所有实例的状态
            with_detail: 是否返回详细信息

        Returns:
            InstallerStatusResult: 状态信息
        Raises:
            MetricPluginDeploymentOperationError: 版本不存在或实例ID无效
        """
        # 获取状态前先刷新部署状态
        self._deployment_status_refresh()
        result: InstallerStatusResult = {
            "deployment_status": self.deployment.status,
            "instance_count": len(self.job_inst_mapping),
        }

        if instance_id:
            # 返回指定实例的状态
            task = self.get_task_instance(instance_id)
            if task and task.id:
                result["instance_status"] = {instance_id: self._build_instance_status_info(task, with_detail)}
            else:
                result["instance_status"] = {instance_id: {"status": "unknown"}}
        else:
            # 返回所有实例的状态
            instance_statuses: dict[str, InstanceStatusInfo] = {}
            for inst_key, inst_id in self.job_inst_mapping.items():
                try:
                    task = JobTaskInstanceModel.objects.get(pk=inst_id).to_instance()
                    instance_statuses[inst_key] = self._build_instance_status_info(task, with_detail)
                except JobTaskInstanceModel.DoesNotExist:
                    instance_statuses[inst_key] = {"status": "unknown"}
            result["instance_status"] = instance_statuses

        self._log(logging.DEBUG, f"获取状态: deployment_status={result['deployment_status']}")

        return result

    @override
    def instance_status(self, instance_id: str) -> dict[str, Any]:
        """获取单个实例的状态信息

        Args:
            instance_id: 实例ID

        Returns:
            dict: 包含实例状态和原始日志条目的字典，结构可参考 JobCollectLogDetail
        Raises:
            MetricPluginDeploymentOperationError: 版本不存在或实例ID无效
        """
        status_result = self.status(instance_id=instance_id, with_detail=True)
        instance_status = status_result.get("instance_status", {}).get(instance_id)
        if not instance_status:
            raise MetricPluginDeploymentOperationError(f"实例ID {instance_id} 无效，无法获取状态")
        task_log: list[JobCollectLogEntry] = []
        for log_entry in instance_status.get("detail", {}).get("task_log", []):
            task_log.append(
                {
                    "step": log_entry.get("step", ""),
                    "status": log_entry.get("status", ""),
                    "messages": log_entry.get("messages", ""),
                    "job_instance_id": log_entry.get("job_instance_id"),
                    "timestamp": log_entry.get("timestamp", ""),
                    "extra": log_entry.get("extra", {}),
                }
            )
        collect_log_detail: JobCollectLogDetail = {
            "instance_id": instance_id,
            "status": instance_status.get("status", ""),
            "current_step": instance_status.get("current_step", ""),
            "error_message": instance_status.get("error_message", ""),
            "task_log": task_log,
        }
        task_id = instance_status.get("task_id")
        if task_id is not None:
            collect_log_detail["task_id"] = task_id
        return dict(collect_log_detail)
