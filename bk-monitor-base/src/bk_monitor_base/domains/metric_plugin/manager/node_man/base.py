import base64
import hashlib
import json
import logging
import os
import random
import shutil
import stat
import string
import tarfile
import tempfile
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, ClassVar, Literal, TypedDict, cast

from jinja2.sandbox import SandboxedEnvironment
from typing_extensions import override

from bk_monitor_base.config.all import get_config
from bk_monitor_base.config.storage import StorageName
from bk_monitor_base.domains.metric_plugin.constants import InstanceType, MetricPluginStatus
from bk_monitor_base.domains.metric_plugin.define import CreatePluginParams, MetricPlugin, MetricPluginDeployment
from bk_monitor_base.domains.metric_plugin.errors import (
    ExportPluginFailedError,
    ExportPluginTimeoutError,
    ParsePluginDebugContentError,
    RegisterPluginFailedError,
)
from bk_monitor_base.domains.metric_plugin.manager.base import BaseMetricPluginManager, OSType
from bk_monitor_base.domains.metric_plugin.manager.node_man.datalink import CustomNodemanPluginDataLinker
from bk_monitor_base.domains.metric_plugin.manager.node_man.define import (
    NodemanPluginParamsMode,
    NodemanPluginParamsType,
)
from bk_monitor_base.domains.metric_plugin.models import MetricPluginModel
from bk_monitor_base.infras import third_party_api as api
from bk_monitor_base.infras.cipher import RSACipher
from bk_monitor_base.infras.constant import HEARTBEAT_MESSAGE_ID
from bk_monitor_base.infras.storage import get_storage
from bk_monitor_base.infras.third_party_api.errors import BkApiError
from bk_monitor_base.infras.third_party_api.nodeman.api import (
    PluginConfigTemplateParams,
    create_export_plugin_task,
    create_plugin_config_template,
    create_register_plugin_task,
    get_plugin_info,
    query_export_plugin_task,
    query_plugin_debug,
    query_register_plugin_task,
    release_plugin,
    release_plugin_config_template,
    render_plugin_config_template,
    start_plugin_debug,
    stop_plugin_debug,
    upload_plugin,
)
from bk_monitor_base.infras.types import FILE_OR_CONTENT_TYPE

logger = logging.getLogger(__name__)


DebugStatus = Literal["running", "success", "failed"]


class DebugLogResult(TypedDict):
    metric_json: list[dict[str, Any]]
    last_time: str
    error_message: str
    status: DebugStatus
    log: str


"""
蓝鲸监控节点管理插件是基于监控平台、GSE、节点管理、bkmonitorbeat定义的一种自定义采集插件，它可以支持在主机上安装插件，并提供插件的安装、卸载、启动、停止、调试、上传、导出等功能。

目前支持四种操作系统类型：
- linux_x86_64
- linux_aarch64
- windows_x86_64
- aix_powerpc

标准插件包目录结构订阅如下:

os_type: 操作系统类型
ext: 脚本扩展名，根据操作系统类型，脚本扩展名不同，目前支持的扩展名有：
- linux: sh
- windows: bat
- aix: ksh
plugin_name: 插件名称

external_plugins_{os_type} - 操作系统类型目录
│── {plugin_name} - 插件名
    ├── etc - 插件运行配置目录
    │   ├── bkmonitorbeat_debug.yaml - 插件配置
    │   ├── config.yaml - 插件配置
    │   ├── env.yaml - 插件环境变量
    ├── info - 插件信息目录
    │   ├── config.json - 插件参数订阅，对应MetricPlugin.define
    │   ├── metrics.json - 插件指标订阅，对应MetricPlugin.metrics
    │   ├── description.md - 插件描述，对应MetricPlugin.description_md
    │   ├── meta.yaml - 插件元信息
    │   ├── release.md - 插件发布说明
    │   ├── signature.yaml - 插件签名
    ├── debug.{ext} - 调试脚本
    ├── start.{ext} - 启动脚本
    ├── debug.{ext} - 调试脚本
    ├── reload.{ext} - 重载脚本
    ├── stop.{ext} - 停止脚本
    ├── project.yaml - 插件定义
    ├── VERSION - 插件版本
"""


# 节点管理插件模板目录
NodeManPluginTemplateDir = Path(__file__).parent / "templates"


# 节点管理插件内置维度
INNER_DIMENSIONS: list[str] = [
    "bk_biz_id",
    "bk_target_ip",
    "bk_target_cloud_id",
    "bk_target_topo_level",
    "bk_target_topo_id",
    "bk_target_service_category_id",
    "bk_target_service_instance_id",
    "bk_collect_config_id",
]

# 心跳错误码
BEAT_RUN_ERR = 4001  # 脚本运行报错
BEAT_PARAMS_ERR = 4002  # 脚本命令不合法
BEAT_FORMAT_OUTPUT_ERR = 4003  # 解析脚本标准输出报错

BEAT_ERR = {
    BEAT_RUN_ERR: "脚本运行报错,原因是{}",
    BEAT_PARAMS_ERR: "脚本命令不合法,原因是{}",
    BEAT_FORMAT_OUTPUT_ERR: "解析脚本标准输出报错,原因是{}",
}

# 不同操作系统类型对应的插件路径
OSTypeToPluginDirName = {
    OSType.LINUX: "external_plugins_linux_x86_64",
    OSType.LINUX_AARCH64: "external_plugins_linux_aarch64",
    OSType.WINDOWS: "external_plugins_windows_x86_64",
    OSType.AIX: "external_plugins_aix_powerpc",
}


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


class NodemanPluginManager(BaseMetricPluginManager, ABC):
    """节点管理插件管理器基类

    节点管理类型，核心能力是基于节点管理的插件和订阅能力，实现可以安装在主机上的插件。
    """

    type: ClassVar[str] = "nodeman"
    _SUB_CONFIG_NAME: ClassVar[str] = "bkmonitorbeat_plugin_type.conf"
    config_files: ClassVar[list[str]] = ["env.yaml.tpl"]

    @abstractmethod
    def make_package(self, is_compress: bool = True) -> Path:
        """制作插件包"""

    def _log(self, level: int, message: str):
        """日志打印"""
        logger.log(level, "%s(%s, %s): %s", self.__class__.__name__, self.plugin.id, self.plugin.type, message)

    def _get_custom_nodeman_plugin_datalinker(self) -> CustomNodemanPluginDataLinker:
        """获取自定义节点管理插件数据链路器"""
        return CustomNodemanPluginDataLinker(plugin=self.plugin, plugin_model=self._get_plugin_model())

    @override
    def apply_data_link(self, operator: str) -> None:
        """申请数据链路

        创建数据ID和结果表, 存入插件的related_params中，函数可重入，多次调用不会重复申请数据链路。

        Args:
            operator: 操作人
        """
        self._get_custom_nodeman_plugin_datalinker().apply_data_ids(operator=operator)
        self._get_custom_nodeman_plugin_datalinker().apply_result_tables(operator=operator)
        return None

    @override
    def refresh_metrics(self, operator: str) -> None:
        """刷新插件指标配置。"""
        self._get_custom_nodeman_plugin_datalinker().refresh_metrics(operator=operator)
        self.plugin: MetricPlugin = self._get_plugin_model().to_plugin(version=self.plugin.version)

    @override
    def apply_data_link_with_deployment(self, deployment: MetricPluginDeployment, operator: str) -> Any:
        """申请数据链路(基于插件部署项)

        Args:
            deployment: 插件部署项
            operator: 操作人
        """
        return None

    @override
    def delete_data_link(self, operator: str) -> Any:
        """删除数据链路

        删除数据ID和结果表相关配置，函数可重入，多次调用不会有影响。

        Args:
            operator: 操作人
        """
        self._get_custom_nodeman_plugin_datalinker().delete_data_ids()
        self._get_custom_nodeman_plugin_datalinker().delete_result_tables()
        return None

    @override
    def delete_data_link_with_deployment(self, deployment: "MetricPluginDeployment", operator: str) -> Any:
        """删除数据链路(基于插件部署项)

        Args:
            deployment: 插件部署项
            operator: 操作人
        """
        return None

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
        with tarfile.open(parent_dir / f"{plugin_dir.name}.tgz", "w:gz") as tar:
            # 将plugin_dir目录下的子目录加入压缩包
            for sub_dir in plugin_dir.iterdir():
                if sub_dir.is_dir():
                    tar.add(sub_dir, arcname=sub_dir.name)
        self._log(logging.INFO, f"create compress package {plugin_dir.name}.tgz")
        return parent_dir / f"{plugin_dir.name}.tgz"

    def _make_package(
        self,
        extra_text_files: dict[OSType, list[TextFile]] | None = None,
        extra_files: dict[OSType, list[ExtraFile]] | None = None,
        is_compress: bool = True,
    ) -> Path:
        """制作插件包

        1. 从节点管理插件模板目录中拷贝所有文件到插件包目录中
        2. 根据上下文渲染插件包中的文本文件
        3. 在插件包中追加extra_files及logo文件

        Args:
            extra_text_files: 额外文本文件，可以按操作系统类型，添加额外文本文件
                {
                    OSType.LINUX: [
                        {
                            "path": "plugin.sh",
                            "content": "xxx",
                        }
                    ],
                }
            extra_files: 额外文件，可以按操作系统类型，添加额外文件，key为注入到插件包中的路径，value为需要注入的文件/目录路径
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
        template_dir = NodeManPluginTemplateDir / self.type
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

        # 根据当前插件支持的操作系统类型，拷贝插件模板目录到插件包目录中
        for os_type in self.get_supported_os_types():
            template_os_dir = template_dir / OSTypeToPluginDirName[os_type]
            if not template_os_dir.exists():
                raise ValueError(f"插件包模板目录不存在: {template_os_dir}")

            plugin_os_dir = plugin_dir / OSTypeToPluginDirName[os_type]

            # 拷贝插件模板目录到插件包目录中
            shutil.copytree(template_os_dir, plugin_os_dir)

            # 调整插件目录名
            plugin_sub_dir = plugin_os_dir / self.plugin.id
            plugin_sub_dir.with_name("plugin_name").rename(plugin_sub_dir)

            # 追加额外文本文件
            if extra_text_files:
                for file_info in extra_text_files.get(os_type, []):
                    with open(plugin_sub_dir / file_info["path"], "w+") as f:
                        f.write(file_info["content"])

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

        self._log(logging.INFO, f"create plugin package {plugin_dir.name}")

        if is_compress:
            # 压缩插件包
            return self._create_compress_package(plugin_dir)

        return plugin_dir

    def _upload_plugin(self, tar_file: Path) -> str:
        """上传插件到节点管理

        1. 先上传到bkrepo
        2. 然后上传到节点管理

        Raises:
            BkApiError: 接口调用失败
        """
        bkrepo_plugin_path = f"nodeman_plugins/{self.plugin.id}/{int(time.time())}/{tar_file.name}"

        # 计算文件md5
        hash_obj = hashlib.md5()
        with open(tar_file, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_obj.update(chunk)
        md5 = hash_obj.hexdigest()

        # 上传到bkrepo
        with open(tar_file, "rb") as f:
            storage = get_storage(StorageName.DEFAULT)
            storage.save(bkrepo_plugin_path, f)
            self._log(logging.INFO, f"upload plugin to bkrepo success, {bkrepo_plugin_path}")

        # 上传到节点管理
        result = upload_plugin(
            bk_tenant_id=self.plugin.bk_tenant_id,
            file_name=tar_file.name,
            download_url=storage.url(bkrepo_plugin_path),
            md5=md5,
        )
        self._log(logging.INFO, f"upload plugin to nodeman success, {tar_file.name}")
        return result["name"]

    def _register_plugin(
        self,
        plugin_name: str,
        operator: str,  # pyright: ignore[reportUnusedParameter]
    ) -> Any:
        """注册插件到节点管理

        Raises:
            BkApiError: 接口调用失败
            RegisterPluginFailedError: 注册插件失败
        """
        job_id = create_register_plugin_task(
            bk_tenant_id=self.plugin.bk_tenant_id, file_name=plugin_name, is_release=False
        )

        self._log(logging.INFO, f"create register plugin task, {plugin_name}, job_id: {job_id}")

        max_loop = 60
        while max_loop > 0:
            # 查询任务状态
            result = query_register_plugin_task(bk_tenant_id=self.plugin.bk_tenant_id, job_id=job_id)
            if result.get("status") == "FAILED":
                self._log(
                    logging.ERROR, f"register plugin failed, {plugin_name}, job_id: {job_id}, {result['message']}"
                )
                raise RegisterPluginFailedError(result["message"])

            if result["is_finish"]:
                self._log(logging.INFO, f"register plugin success, {plugin_name}, job_id: {job_id}")
                return

            time.sleep(1)
            max_loop -= 1
        else:
            self._log(logging.WARNING, f"register plugin timeout, {plugin_name}")
            raise RegisterPluginFailedError("注册插件超时")

    def _register_template(
        self,
        tar_file: Path,
        operator: str,  # pyright: ignore[reportUnusedParameter]
    ):
        """注册模板到节点管理

        读取插件etc目录下的.tpl文件，将其内容注册为节点管理的插件模板

        Args:
            tar_file: 插件包路径
            operator: 操作人

        Raises:
            BkApiError: 接口调用失败
        """
        params: PluginConfigTemplateParams = {
            "plugin_version": "*",
            "version": str(self.plugin.version.major),
            "format": "yaml",
            "is_release_version": False,
            "plugin_name": self.plugin.id,
            "file_path": "etc",
            "content": "",
            "md5": "",
            "name": "",
        }
        top_path = os.path.dirname(tar_file)
        dir_path = os.path.join(top_path, self.plugin.id)
        yaml_path = os.path.join(dir_path, os.listdir(dir_path)[0], self.plugin.id, "etc")

        for root, _, filenames in os.walk(yaml_path):
            for filename in filenames:
                if not filename.endswith(".tpl"):
                    # 不以 .tpl 结尾的，不注册为模板
                    continue
                with open(os.path.join(root, filename), "rb") as f:
                    content = f.read()
                params["name"] = filename.replace(".tpl", "")
                params["content"] = base64.b64encode(content).decode("utf-8")
                params["md5"] = hashlib.md5(content).hexdigest()
                create_plugin_config_template(bk_tenant_id=self.plugin.bk_tenant_id, params=params)
                self._log(logging.INFO, f"register template {params['name']} success")

    @override
    def register(self, operator: str) -> list[str]:
        """注册插件到节点管理

        1. 制作插件包
        2. 上传插件到bkrepo，然后再上传到节点管理
        3. 创建插件注册任务，然后轮询等待任务结果
        4. 检查插件状态并获取md5列表
        5. 注册插件模板

        Args:
            operator: 操作人

        Returns:
            md5列表

        Raises:
            RegisterPluginFailedError: 注册插件失败
            BkApiError: 接口调用失败
        """
        # 制作插件压缩包
        tar_file_path = self.make_package(is_compress=True)
        # 上传插件到节点管理
        plugin_name = self._upload_plugin(tar_file=tar_file_path)
        # 注册插件到节点管理
        self._register_plugin(operator=operator, plugin_name=plugin_name)
        # 检查插件是否注册成功，并获取md5列表，用于后续release
        plugin_infos = get_plugin_info(
            bk_tenant_id=self.plugin.bk_tenant_id,
            name=self.plugin.id,
            version=self.plugin.version_str(),
        )
        # 如果插件信息为空，说明插件注册存在问题
        if not plugin_infos:
            self._log(logging.WARNING, f"register plugin failed, {plugin_name}")
            raise RegisterPluginFailedError("get plugin info empty")
        md5_list = [plugin_info.md5 for plugin_info in plugin_infos]
        # 注册插件模板文件到节点管理
        self._register_template(operator=operator, tar_file=tar_file_path)
        # 删除临时目录
        shutil.rmtree(tar_file_path.parent)
        return md5_list

    @override
    def release_plugin_version(
        self, operator: str, apply_data_link: bool = True, md5_list: list[str] | None = None
    ) -> None:
        """发布插件到节点管理

        1. 发布配置文件
        2. 发布插件
        3. 更新插件版本状态为已发布

        Raises:
            BkApiError: 接口调用失败
        """
        # 发布配置文件
        for config_file in self.config_files:
            release_plugin_config_template(
                bk_tenant_id=self.plugin.bk_tenant_id,
                plugin_name=self.plugin.id,
                plugin_version="*",
                name=config_file,
                version=self.plugin.version.major,
            )
            self._log(logging.INFO, f"release config file {config_file} success")

        package_version = self.plugin.version_str()
        if not md5_list:
            plugin_infos = get_plugin_info(
                bk_tenant_id=self.plugin.bk_tenant_id,
                name=self.plugin.id,
                version=package_version,
            )
            if not plugin_infos:
                self._log(logging.WARNING, f"release plugin failed, {self.plugin.bk_tenant_id}/{self.plugin.id}")
                return
            md5_list = [plugin_info.md5 for plugin_info in plugin_infos]

        self._log(logging.INFO, f"release plugin {self.plugin.id}, version: {package_version}, md5_list: {md5_list}")
        release_plugin(
            bk_tenant_id=self.plugin.bk_tenant_id,
            name=self.plugin.id,
            version=package_version,
            md5_list=md5_list,
        )

        # 更新插件版本状态为已发布
        super().release_plugin_version(operator=operator, apply_data_link=apply_data_link, md5_list=md5_list)

    @abstractmethod
    def _get_debug_config_context(
        self,
        collect_params: dict[str, Any],
        plugin_params: dict[str, Any],
        target_nodes: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """用于渲染调试配置上下文

        Args:
            collect_params: 采集参数，如采集周期，超时时间，绑定IP/端口，可以理解为内置参数
            plugin_params: 插件定义参数，用户自定义的参数
            target_nodes: 采集目标节点

        Returns:
            调试配置上下文
        """

    @abstractmethod
    def get_deploy_steps_params(
        self,
        bk_biz_id: int,
        collect_task_id: int,
        bk_data_ids: dict[str, int],
        collect_params: dict[str, Any],
        plugin_params: dict[str, Any],
        target_nodes: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """获取部署步骤参数

        Args:
            collect_params: 采集参数，如采集周期，超时时间，绑定IP/端口，可以理解为内置参数
            plugin_params: 插件定义参数，用户自定义的参数
            target_nodes: 采集目标节点

        Returns:
            部署步骤参数列表
        """

    def start_debug(
        self,
        collect_params: dict[str, Any],
        plugin_params: dict[str, Any],
        collect_host: dict[str, Any],
        target_nodes: list[dict[str, Any]],
        operator: str,  # pyright: ignore[reportUnusedParameter]
    ) -> Any:
        """启动调试

        Args:
            collect_params: 采集参数
            plugin_params: 插件定义参数
            collect_host: 采集主机
            target_nodes: 采集目标节点
            operator: 操作人

        Returns:
            调试任务ID
        """

        # 获取调试配置上下文
        contexts = self._get_debug_config_context(
            collect_params=collect_params,
            plugin_params=plugin_params,
            target_nodes=target_nodes,
        )

        # 渲染调试配置文件
        config_ids: list[int] = []
        for config_name, context in contexts.items():
            render_result = render_plugin_config_template(
                bk_tenant_id=self.plugin.bk_tenant_id,
                plugin_name=self.plugin.id,
                plugin_version="*",
                name=config_name,
                version=str(self.plugin.version.major),
                data=context,
            )
            config_ids.append(render_result["id"])

        # 启动调试任务
        task_id = start_plugin_debug(
            bk_tenant_id=self.plugin.bk_tenant_id,
            params={
                "plugin_name": self.plugin.id,
                "version": self.plugin.version_str(),
                "config_ids": config_ids,
                "host_info": collect_host,
            },
        )
        return task_id

    def stop_debug(
        self,
        task_id: int,
        operator: str,  # pyright: ignore[reportUnusedParameter]
    ) -> None:
        """停止调试

        Args:
            task_id: 任务ID
            operator: 操作人

        Raises:
            BkApiError: 接口调用失败
        """
        stop_plugin_debug(
            bk_tenant_id=self.plugin.bk_tenant_id,
            task_id=task_id,
        )

    def _parse_debug_content(self, content: str) -> tuple[list[dict[str, Any]], str, str]:
        """解析调试日志

        Args:
            content: 原始日志

        Returns:
            1. 指标信息
            2. 最新时间
            3. 错误信息

        Raises:
            ParsePluginDebugContentError: 数据解析失败
        """

        def _valid_data(data: str) -> tuple[Literal[True], str] | tuple[Literal[False], dict[str, Any]]:
            """校验数据格式

            Args:
                data: 原始数据

            Returns:
                两种情况
                1. 校验失败，返回原始数据
                2. 校验成功，返回解析后的数据

            Raises:
                ParsePluginDebugContentError: 数据解析失败
            """
            if '"beat"' not in data:
                return True, data
            try:
                message_detail: dict[str, Any] = json.loads(data)
            except Exception as error:
                logger.error("[query_debug] Parsing data error：%s；The last 50 char:%s", error, data[-50:])
                raise ParsePluginDebugContentError(error) from error
            if message_detail["dataid"] == HEARTBEAT_MESSAGE_ID or message_detail["type"] == "status":
                # 心跳数据，不需要
                return True, data
            return False, message_detail

        def _exporter_log_parser(
            message_detail: dict[str, Any], metric_json: list[dict[str, Any]], metric_name_cache: list[str]
        ) -> None:
            """解析exporter数据

            Args:
                message_detail: 消息详情
                metric_json: 指标数据
                metric_name_cache: 指标名称缓存（会在函数内部被修改）
            """
            metrics: list[dict[str, Any]] = message_detail["prometheus"]["collector"].get("metrics", [])
            for metric in metrics:
                if metric["key"] not in metric_name_cache:
                    if not metric["key"].strip():
                        continue
                    dimensions: list[dict[str, str]] = []
                    for key, value in list(metric["labels"].items()):
                        if key in INNER_DIMENSIONS:
                            continue
                        dimensions.append({"dimension_name": key, "dimension_value": value})
                    metric_json.append(
                        {"metric_name": metric["key"], "metric_value": metric["value"], "dimensions": dimensions}
                    )
                    metric_name_cache.append(metric["key"])

        def _common_log_parser(
            message_detail: dict[str, Any],
            metric_json: list[dict[str, Any]],
            metric_name_cache: list[str],
            dimension_info: dict[str, Any],
        ) -> None:
            """解析通用日志格式

            Args:
                message_detail: 消息详情
                metric_json: 指标数据
                metric_name_cache: 指标名称缓存（会在函数内部被修改）
                dimension_info: 维度信息
            """
            if message_detail.get("message", "") != "success":
                return
            for metric_name, metric_value in message_detail["metrics"].items():
                if not metric_name.strip():
                    continue
                if metric_name not in metric_name_cache:
                    dimension_info[metric_name] = {"dimensions": [], "dimension_name": []}
                    for key, value in list(message_detail["dimensions"].items()):
                        if key in INNER_DIMENSIONS:
                            continue
                        dimension_info[metric_name]["dimensions"].append(
                            {"dimension_name": key, "dimension_value": value}
                        )
                        dimension_info[metric_name]["dimension_name"].append(key)
                    metric_json.append(
                        {
                            "metric_name": metric_name,
                            "metric_value": metric_value,
                            "dimensions": dimension_info[metric_name]["dimensions"],
                        }
                    )
                    metric_name_cache.append(metric_name)
                else:
                    for key, value in list(message_detail["dimensions"].items()):
                        if key in INNER_DIMENSIONS:
                            continue
                        if key not in dimension_info[metric_name]["dimension_name"]:
                            dimension_info[metric_name]["dimensions"].append(
                                {"dimension_name": key, "dimension_value": value}
                            )
                            dimension_info[metric_name]["dimension_name"].append(key)

        def _get_error_message(message: dict[str, Any]) -> str:
            """获取错误信息

            Args:
                message: 消息内容

            Returns:
                错误信息
            """
            err_message = ""
            error_code = message.get("error_code") or 0
            if error_code in BEAT_ERR:
                err_message = "\n\n\n{}".format(BEAT_ERR[error_code].format(message.get("message", "UNKNOWN")))
            elif "error" in message and message["error"]:
                err_message = "\n\n\n{}".format(BEAT_ERR[BEAT_RUN_ERR].format(message["error"]))
            return err_message

        metric_json: list[dict[str, Any]] = []
        message_list = content.strip().split("\n")
        metric_name_cache: list[str] = []
        dimension_info: dict[str, str] = {}
        log_type: str | None = None
        valid_message: dict[str, Any] = {}
        error_message = ""
        for detail in message_list:
            # 校验数据格式
            is_invalid, message_detail = _valid_data(detail)
            if is_invalid:
                continue
            message_detail = cast(dict[str, Any], message_detail)

            # 收集错误信息
            error_message += _get_error_message(message_detail)

            # 确认数据类型
            if not log_type:
                log_type = "exporter" if "prometheus" in message_detail else "common"

            # 解析数据
            valid_message = message_detail
            if log_type == "exporter":
                _exporter_log_parser(message_detail, metric_json, metric_name_cache)
            else:
                _common_log_parser(message_detail, metric_json, metric_name_cache, dimension_info)
        else:
            # 获取时间
            timestamp = valid_message.get("time", int(time.time()))
            last_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))

        # 检查指标名称和维度名称是否重复
        metric_name: set[str] = set()
        dimension_name: set[str] = set()
        for metric in metric_json:
            metric_name.add(metric["metric_name"])
            for dimension in metric["dimensions"]:
                dimension_name.add(dimension["dimension_name"])
        intersection = set(metric_name) & set(dimension_name)
        if metric_name & dimension_name:
            raise ParsePluginDebugContentError(f"指标维度存在重名,{intersection}")
        return metric_json, last_time, error_message

    def get_debug_log(
        self,
        task_id: int,
        operator: str,  # pyright: ignore[reportUnusedParameter]
    ) -> DebugLogResult:
        """获取调试日志

        Args:
            task_id: 任务ID
            operator: 操作人
        """
        debug_result = query_plugin_debug(
            bk_tenant_id=self.plugin.bk_tenant_id,
            task_id=task_id,
        )

        api_status = debug_result["status"]
        status: DebugStatus
        if api_status == "SUCCESS":
            status = "success"
        elif api_status in ("FAILED", "PART_FAILED", "TERMINATED"):
            status = "failed"
        else:
            status = "running"

        log = debug_result["message"]
        metric_json, last_time, error_message = self._parse_debug_content(log)
        return {
            "metric_json": metric_json,
            "last_time": last_time,
            "error_message": error_message,
            "status": status,
            "log": log,
        }

    @override
    def export_package(self, operator: str) -> str:
        """导出插件包

        1. 向节点管理创建导入任务
        2. 定时查询导入任务完成情况
        3. 导出成功后，返回插件包的下载路径

        Returns:
            插件包的下载路径

        Raises:
            BkApiError: 接口调用失败
        """
        # 检查插件状态
        if self.plugin.status != MetricPluginStatus.RELEASE:
            raise ExportPluginFailedError(f"plugin {self.plugin.id}({self.plugin.version_str()}) is not released")

        job_id = create_export_plugin_task(
            bk_tenant_id=self.plugin.bk_tenant_id,
            category="gse_plugin",
            query_params={
                "project": self.plugin.id,
                "version": self.plugin.version_str(),
            },
            bk_app_code=get_config().blueking.app_code,
            creator=operator,
        )
        max_loop = 15
        while max_loop > 0:
            max_loop -= 1
            result = query_export_plugin_task(
                bk_tenant_id=self.plugin.bk_tenant_id,
                job_id=job_id,
            )
            if result["is_finish"]:
                if result["is_failed"]:
                    error_message = result.get("error_message", "")
                    self._log(logging.ERROR, f"export plugin failed: {error_message}")
                    raise ExportPluginFailedError(error_message)
                return result["download_url"]
            time.sleep(2)

        raise ExportPluginTimeoutError()

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
        return {}

    @override
    @classmethod
    def parse_package(cls, bk_tenant_id: str, package_file: Path, operator: str) -> CreatePluginParams:
        """解析插件包

        先将压缩包解压到临时目录，然后解析插件包。
        支持解析标准的监控平台蓝鲸插件包，插件包结构如下：
        ├── external_plugins_linux_x86_64
        │   └── bkplugin_mysql
        │       ├── VERSION
        │       ├── info
        │       │   ├── config.json
        │       │   ├── description.md
        │       │   ├── meta.yaml
        |       |   ├── logo.png
        │       │   ├── metrics.json
        │       │   ├── release.md
        │       │   └── signature.yaml
        │       ├── project.yaml
        └── external_plugins_windows_x86_64
            └── bkplugin_mysql
                ├── VERSION
                ├── info
                │   ├── config.json
                │   ├── description.md
                │   ├── meta.yaml
                │   ├── metrics.json
                │   ├── release.md
                │   └── signature.yaml
                ├── project.yaml



        meta.yaml 文件示例如下：
        ```yaml
        plugin_id: bkplugin_mysql
        plugin_display_name: MySQL
        plugin_type: Exporter
        tag: xxx
        is_support_remote: True
        label: component
        ```

        release.md 需要记录在version_log中
        config.json 需要记录在params中
        VERSION 需要记录在version中
        metrics.json 需要记录在metrics中
        description.md 需要记录在description_md中
        logo.png 需要记录在logo中

        Args:
            bk_tenant_id: 租户ID
            package_file: 插件包文件路径
            operator: 操作人

        Returns:
            CreatePluginParams: 创建插件参数
        """

        return super().parse_package(bk_tenant_id, package_file, operator)

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
            data_source = api.metadata.get_data_source(
                bk_tenant_id=self.plugin.bk_tenant_id, data_name=f"{self.plugin.type.lower()}_{self.plugin.id}"
            )
            bk_data_id = data_source["bk_data_id"]
        except BkApiError:
            # 创建数据源
            random_suffix = "".join(random.choices(string.ascii_letters + string.digits, k=8))
            bk_data_id = api.metadata.create_data_source(
                bk_tenant_id=self.plugin.bk_tenant_id,
                operator=self.plugin.updated_by,
                data_name=f"{self.plugin.type}_{self.plugin.id}_{random_suffix}",
                etl_config=self._get_custom_nodeman_plugin_datalinker().get_etl_config(),
                source_label="bk_monitor",
                type_label="time_series",
                is_custom_source=True,
            )

        # 更新插件的related_params中的bk_data_id
        self.plugin.related_params["bk_data_id"] = bk_data_id
        MetricPluginModel.objects.filter(
            bk_tenant_id=self.plugin.bk_tenant_id, bk_biz_id=bk_biz_id, plugin_id=self.plugin.id
        ).update(related_params=self.plugin.related_params)

        return {"bk_data_id": bk_data_id}

    def get_target_instance_type(self) -> InstanceType:
        """获取实例类型"""
        if self.plugin.label in ["service_module", "component"]:
            return InstanceType.SERVICE
        else:
            return InstanceType.HOST

    @classmethod
    def check_file(cls, file_or_content: FILE_OR_CONTENT_TYPE, os_type: OSType) -> tuple[bool, str, dict[str, Any]]:  # pyright: ignore[reportUnusedParameter]
        """校验文件是否符合插件文件要求

        Args:
            file_or_content: 文件或内容
            os_type: 操作系统类型

        Returns:
            (是否合法, 错误原因, 提取信息)
        """
        return True, "", {}


class CommandPluginManager(NodemanPluginManager, ABC):
    """
    通用命令行插件管理器
    """

    # 节点管理 base64 识别前缀
    NODEMAN_BASE64_PREFIX: str = "$NODEMAN_BASE64_PREFIX$"

    def _process_plugin_params(
        self, collect_params: dict[str, Any], plugin_params: dict[str, Any]
    ) -> tuple[dict[str, str], list[dict[str, str]], dict[str, str]]:
        """通用处理采集参数

        Args:
            collect_params: 采集参数，包括采集周期，超时时间，绑定IP/端口等
            plugin_params: 插件定义参数，用户自定义的参数

        Returns:
            处理后的采集参数，文件列表
        """
        cmd_args = ""
        env_vars: dict[str, str] = {}
        user_files: list[dict[str, str]] = []
        extra_dimensions: dict[str, str] = {}

        # 按照插件参数的定义处理参数
        for param_config in self.plugin.params:
            param_name = param_config.name
            param_mode = param_config.mode
            param_type = param_config.type
            param_value = plugin_params.get(param_name)

            # 过滤无效参数
            if param_value is None:
                continue

            # 处理文件类型参数
            if param_type == NodemanPluginParamsType.FILE:
                user_files.append(
                    {
                        "filename": param_value["filename"],
                        "file_base64": self.NODEMAN_BASE64_PREFIX + param_value["file_base64"],
                    }
                )

                # 将参数值替换为文件路径
                param_value = f"etc/{param_value['filename']}"

            # 使用采集器参数对变量进行渲染
            if isinstance(param_value, str):
                for k, v in list(collect_params.items()):
                    replace_key = f"${{{k}}}"
                    if isinstance(v, str) and param_mode != NodemanPluginParamsMode.DMS_INSERT:
                        param_value = param_value.replace(replace_key, v)

            # 处理加密类型参数
            if param_type == NodemanPluginParamsType.ENCRYPT:
                config = get_config()
                if config.encryption.rsa_private_key and isinstance(param_value, str):
                    try:
                        # 使用RSA加密参数值
                        cipher = RSACipher(config.encryption.rsa_private_key)
                        encrypted_value = cipher.encrypt(param_value.encode("utf-8"))
                        param_value = encrypted_value.decode("utf-8")
                    except Exception as e:
                        logging.warning(f"Failed to encrypt parameter {param_name}: {e}")
                        # 如果加密失败，使用原始值

            # 根据参数模式处理参数
            if param_mode == NodemanPluginParamsMode.ENV:
                # 环境变量
                env_vars[param_name] = param_value

            elif param_mode == NodemanPluginParamsMode.OPT_CMD:
                # 选项参数，拼接到命令行参数中
                if param_type == NodemanPluginParamsType.SWITCH:
                    if param_value == "true":
                        cmd_args += f"{param_name} "
                elif param_value:
                    cmd_args += f"{param_name} {param_value} "

            elif param_mode == NodemanPluginParamsMode.POS_CMD:
                # 位置参数，直接将参数值拼接进去
                cmd_args += f"{param_value} "

            elif param_mode == NodemanPluginParamsMode.DMS_INSERT:
                # 维度注入参数，更新至labels的模板中
                if not isinstance(param_value, dict):
                    raise ValueError(f"dms_insert param value must be dict, got {param_value}")

                param_value = cast(dict[str, str], param_value)
                for dms_key, dms_value in param_value.items():
                    if param_type == NodemanPluginParamsType.HOST:
                        # TODO: 此处注入 host 本只需 "{{ " + f"cmdb_instance.host.{dms_value} or '-'" + " }}"
                        # 添加原始值是因为鲸眼老版本错误的用法，把 type 传成了 host。后续需要一个版本进行 migration 刷一次数据，把 host -> custom，然后再删除这个兼容逻辑
                        extra_dimensions[dms_key] = (
                            "{{ " + f"cmdb_instance.host.{dms_value} or '{dms_value}' or '-'" + " }}"
                        )
                    elif param_type == NodemanPluginParamsType.SERVICE:
                        extra_dimensions[dms_key] = (
                            "{{ " + f"cmdb_instance.service.labels['{dms_value}'] or '-'" + " }}"
                        )
                    elif param_type == NodemanPluginParamsType.CUSTOM:
                        # 自定义维度 k,v 注入
                        extra_dimensions[dms_key] = dms_value

        # 将命令行参数添加到环境变量
        env_vars["cmd_args"] = cmd_args

        return env_vars, user_files, extra_dimensions

    def _get_deploy_steps_params(
        self,
        bk_biz_id: int,
        collect_task_id: int,
        bk_data_ids: dict[str, int],
        collect_params: dict[str, Any],
        plugin_params: dict[str, Any],
        extra_collect_context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """获取部署步骤参数

        Args:
            bk_biz_id: 蓝鲸业务ID
            collect_task_id: 采集任务ID
            bk_data_ids: 数据ID映射
            collect_params: 采集参数，如采集周期，超时时间，绑定IP/端口，可以理解为内置参数
            plugin_params: 插件定义参数，用户自定义的参数
            extra_config_file_context: 额外的配置文件上下文
            extra_collect_context: 额外的采集上下文

        Returns:
            部署步骤参数列表
        """
        # 处理插件参数
        env_vars, user_files, extra_dimensions = self._process_plugin_params(collect_params, plugin_params)

        # 将用户文件添加到环境变量
        for index, user_file in enumerate(user_files):
            env_vars[f"file{index + 1}"] = user_file["filename"]
            env_vars[f"file{index + 1}_content"] = user_file["file_base64"]

        bkmonitorbeat_context: dict[str, Any] = {
            "period": str(collect_params.get("period", 60)),
            "task_id": str(collect_task_id),
            "bk_biz_id": str(bk_biz_id),
            "config_name": self.plugin.id,
            "config_version": "1.0",
            "namespace": self.plugin.id,
            "timeout": str(collect_params.get("timeout", 60)),
            "max_timeout": str(collect_params.get("timeout", 60)),
            "dataid": bk_data_ids["bk_data_id"],
            "labels": {
                "$for": "cmdb_instance.scope",
                "$item": "scope",
                "$body": {
                    "bk_target_host_id": "{{ cmdb_instance.host.bk_host_id }}",
                    "bk_target_ip": "{{ cmdb_instance.host.bk_host_innerip }}",
                    "bk_target_cloud_id": "{{ cmdb_instance.host.bk_cloud_id[0].id if cmdb_instance.host.bk_cloud_id is iterable and cmdb_instance.host.bk_cloud_id is not string else cmdb_instance.host.bk_cloud_id }}",
                    "bk_target_topo_level": "{{ scope.bk_obj_id }}",
                    "bk_target_topo_id": "{{ scope.bk_inst_id }}",
                    "bk_target_service_category_id": "{{ cmdb_instance.service.service_category_id | default('', true) }}",
                    "bk_target_service_instance_id": "{{ cmdb_instance.service.id }}",
                    "bk_collect_config_id": str(collect_task_id),
                    **extra_dimensions,
                },
            },
            **extra_collect_context,
        }

        exclude_metrics = collect_params.get("exclude_metrics", [])
        if exclude_metrics:
            bkmonitorbeat_context["metric_relabel_configs"] = [
                {
                    "source_labels": ["__name__"],
                    "regex": "|".join(exclude_metrics),
                    "action": "drop",
                }
            ]

        steps: list[dict[str, Any]] = [
            # 配置文件下发
            {
                "id": self.plugin.id,
                "type": "PLUGIN",
                "config": {
                    "plugin_name": self.plugin.id,
                    "plugin_version": self.plugin.version_str(),
                    "config_templates": [
                        {"name": "env.yaml", "version": str(self.plugin.version.major)},
                        *[
                            {
                                "name": f"{{{{file{index + 1}}}}}",
                                "version": str(self.plugin.version.major),
                                "content": f"{{{{file{index + 1}_content}}}}",
                            }
                            for index in range(len(user_files))
                        ],
                    ],
                },
                "params": {"context": env_vars},
            },
            # bkmonitorbeat子配置文件
            {
                "id": "bkmonitorbeat",
                "type": "PLUGIN",
                "config": {
                    "plugin_name": "bkmonitorbeat",
                    "plugin_version": "latest",
                    "config_templates": [{"name": self._SUB_CONFIG_NAME, "version": "latest"}],
                },
                "params": {"context": bkmonitorbeat_context},
            },
        ]
        return steps

    @override
    def _get_debug_config_context(
        self,
        collect_params: dict[str, Any],
        plugin_params: dict[str, Any],
        target_nodes: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """渲染调试配置上下文

        Args:
            collect_params: 采集参数
            plugin_params: 插件参数
            host: 主机信息
            target_nodes: 目标节点列表

        Returns:
            调试配置上下文
        """

        # 处理插件参数
        env_vars, user_files, extra_dimensions = self._process_plugin_params(collect_params, plugin_params)

        # 渲染上下文
        context: dict[str, Any] = {
            "env.yaml": env_vars,
            "bkmonitorbeat_debug.yaml": {
                "labels": {"$for": "cmdb_instance.scope", "$item": "scope", "$body": extra_dimensions},
                **collect_params,
            },
        }

        # 添加用户文件
        for index, file in enumerate(user_files):
            context[f"{{{{file{index + 1}}}}}"] = {
                f"file{index + 1}": file["filename"],
                f"file{index + 1}_content": file["file_base64"],
            }

        return context
