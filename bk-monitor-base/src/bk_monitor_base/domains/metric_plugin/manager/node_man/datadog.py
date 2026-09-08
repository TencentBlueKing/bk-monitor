import logging
import os
import shutil
import tarfile
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any, ClassVar, final

import yaml
from typing_extensions import override

from bk_monitor_base.domains.metric_plugin.constants import PluginType
from bk_monitor_base.domains.metric_plugin.manager.base import OSType
from bk_monitor_base.domains.metric_plugin.manager.node_man.base import (
    CommandPluginManager,
    ExtraFile,
    NodeManPluginTemplateDir,
    OSTypeToPluginDirName,
)
from bk_monitor_base.domains.uploaded_file.operation import save_file
from bk_monitor_base.infras.types import FILE_OR_CONTENT_TYPE

logger = logging.getLogger(__name__)


@final
class DataDogPluginManager(CommandPluginManager):
    """DataDog插件管理器"""

    type: ClassVar[str] = PluginType.DATADOG
    _SUB_CONFIG_NAME: ClassVar[str] = "bkmonitorbeat_script.conf"

    @override
    def get_supported_os_types(self) -> list[OSType]:
        """获取支持的操作系统类型"""
        supported_os_types: list[OSType] = []
        for os_type in OSType:
            if os_type.value in self.plugin.define:
                supported_os_types.append(os_type)
        return supported_os_types

    @override
    def make_package(self, is_compress: bool = True) -> Path:
        """制作插件包
        Args:
            is_compress: 是否压缩
        Returns:
            如果不需要压缩，则返回插件包目录路径；如果需要压缩，则返回压缩包路径
        """
        extra_files: dict[OSType, list[ExtraFile]] = {}
        for os_type in self.get_supported_os_types():
            if not self.plugin.define.get(os_type.value):
                continue
            # os_config = self.plugin.define[os_type.value]
            # file_id = os_config["file_id"]
            file_path = NodeManPluginTemplateDir / self.type / OSTypeToPluginDirName[os_type] / "lib"
            # todo 待处理，根据文件ID(file_id)获取文件内容并解压到插件包的指定路径 file_path
            extra_files[os_type] = [
                {
                    "target_path": str(file_path),
                    "source_path": "lib",
                }
            ]
        return self._make_package(is_compress=is_compress, extra_files=extra_files)

    @override
    def _get_debug_config_context(
        self,
        collect_params: dict[str, Any],
        plugin_params: dict[str, Any],
        target_nodes: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """构建调试配置上下文
        Args:
            collect_params: 采集参数
            plugin_params: 插件参数
            target_nodes: 目标节点列表
        Returns:
            调试配置上下文
        """

        context = {
            "conf.yaml": plugin_params,
            "env.yaml": plugin_params,
            "bkmonitorbeat_debug.yaml": collect_params,
        }

        return context

    @override
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
            bk_biz_id: 蓝鲸业务ID
            collect_task_id: 采集任务ID
            bk_data_ids: 数据ID映射
            collect_params: 采集参数，如采集周期，超时时间，绑定IP/端口，可以理解为内置参数
            plugin_params: 插件定义参数，用户自定义的参数
            target_nodes: 采集目标节点
        Returns:
            部署步骤参数列表
        """

        # 补全逻辑：python_path参数应该放plugin_params里
        if collect_params.get("python_path"):
            plugin_params["python_path"] = collect_params["python_path"]

        collect_params["command"] = (
            f"{{{{ step_data.{self.plugin.id}.control_info.setup_path }}}}/{{{{ step_data.{self.plugin.id}.control_info.start_cmd }}}}"
        )

        # 处理插件参数
        _, _, extra_dimensions = self._process_plugin_params(collect_params, plugin_params)

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
                        {"name": "conf.yaml", "version": str(self.plugin.version.major)},
                    ],
                },
                "params": {
                    "context": {
                        "datadog_check_name": plugin_params["datadog_check_name"],
                        "python_path": plugin_params["python_path"],
                    }
                },
            },
            # bkmonitorbeat子配置文件
            {
                "id": self.plugin.id,
                "type": "PLUGIN",
                "config": {
                    "plugin_name": "bkmonitorbeat",
                    "plugin_version": "latest",
                    "config_templates": [{"name": self._SUB_CONFIG_NAME, "version": "latest"}],
                },
                "params": {
                    "context": {
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
                        "command": collect_params["command"],
                    }
                },
            },
        ]

        return steps

    @override
    @classmethod
    def check_file(cls, file_or_content: FILE_OR_CONTENT_TYPE, os_type: OSType) -> tuple[bool, str, dict[str, Any]]:
        """校验文件是否符合DataDog插件文件要求

        Args:
            file_or_content: 文件或内容
            os_type: 操作系统类型
        Returns:
            (是否合法, 错误原因, 提取信息)
            extract_info: {
                "datadog_check_name": "consul",
                "config_yaml": "xxx",
            }
        """
        plugin_tmp_dir: str | None = None
        try:
            # 创建临时目录用于解压文件
            plugin_tmp_dir = tempfile.mkdtemp(prefix="datadog_plugin_check_")

            # 解压文件
            extracted_path = cls._extract_file(file_or_content, plugin_tmp_dir)

            # 根据 os_type 确定插件目录路径
            plugin_dir_name = OSTypeToPluginDirName[os_type]
            plugin_os_path = os.path.join(extracted_path, plugin_dir_name)

            # 检查操作系统目录是否存在
            if not os.path.exists(plugin_os_path):
                return False, f"上传的DataDog插件包缺少 {plugin_dir_name} 目录", {}

            # 获取插件目录下的第一个子目录
            os_dir_contents = os.listdir(plugin_os_path)
            if not os_dir_contents:
                return False, f"上传的DataDog插件包中 {plugin_dir_name} 目录为空", {}

            plugin_subdir = os_dir_contents[0]
            plugin_base_path = os.path.join(plugin_os_path, plugin_subdir)

            # 验证lib文件夹是否存在
            lib_path = os.path.join(plugin_base_path, "lib")
            if not os.path.exists(lib_path):
                return False, "上传的DataDog插件包缺少 lib 文件夹", {}

            # 验证conf.yaml.tpl文件是否存在
            conf_yaml_path = os.path.join(plugin_base_path, "etc", "conf.yaml.tpl")
            if not os.path.exists(conf_yaml_path):
                conf_yaml_path = os.path.join(plugin_base_path, "etc", "conf.yaml.example")
                if not os.path.exists(conf_yaml_path):
                    return False, "上传的DataDog插件包缺少 conf.yaml.example 配置模板文件", {}

            # 验证meta.yaml文件和datadog_check_name字段是否存在
            meta_yaml_path = os.path.join(plugin_base_path, "info", "meta.yaml")
            if not os.path.exists(meta_yaml_path):
                return False, "上传的DataDog插件包缺少 meta.yaml 配置模板文件", {}

            with open(meta_yaml_path, encoding="utf-8") as f:
                meta_yaml_data = yaml.safe_load(f)
            if not meta_yaml_data or not isinstance(meta_yaml_data, dict) or "datadog_check_name" not in meta_yaml_data:
                return False, "上传的DataDog插件包中 meta.yaml 缺少 datadog_check_name", {}

            return (
                True,
                "",
                {
                    "datadog_check_name": meta_yaml_data["datadog_check_name"],
                    "config_yaml": meta_yaml_data["config_yaml"],
                },
            )
        except Exception as e:
            return False, f"校验DataDog插件文件时发生错误: {str(e)}", {}
        finally:
            # 清理临时目录
            if plugin_tmp_dir and os.path.exists(plugin_tmp_dir):
                try:
                    shutil.rmtree(plugin_tmp_dir)
                except Exception:
                    pass  # 忽略清理失败的错误

    @classmethod
    def _extract_file(cls, file_data: FILE_OR_CONTENT_TYPE, file_path: str) -> str:
        """解压tar.gz文件到指定路径

        Args:
            file_data: 文件数据
            file_path: 解压目标路径
        Returns:
            解压后的路径
        """
        fileobj: Any = None
        should_close = False

        try:
            # 处理不同类型的文件数据
            if isinstance(file_data, bytes):
                fileobj = BytesIO(file_data)
            elif isinstance(file_data, str):
                # 如果是字符串路径，直接打开文件
                fileobj = open(file_data, "rb")  # noqa: SIM115
                should_close = True
            else:
                # 文件对象类型，需要重置位置
                if hasattr(file_data, "seek"):
                    file_data.seek(0)
                fileobj = file_data

            with tarfile.open(fileobj=fileobj, mode="r:gz") as tar:
                for member in tar.getmembers():
                    # 只处理普通文件，避免符号链接等特殊文件类型带来的安全风险
                    if not member.isreg():
                        continue
                    # 规范化路径并检查安全性，防止路径遍历攻击
                    member_path = os.path.normpath(member.name)
                    if member_path.startswith("..") or member_path.startswith("/"):
                        continue
                    # 通过TarInfo对象安全地提取文件内容
                    f = tar.extractfile(member)
                    if f is None:
                        continue
                    with f:
                        target_path = os.path.join(file_path, member_path)
                        # 确保解压路径在预期的临时目录内
                        if not os.path.realpath(target_path).startswith(os.path.realpath(file_path)):
                            continue
                        # 确保目标目录存在
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        with open(target_path, "wb") as target_file:
                            target_file.write(f.read())
        finally:
            # 如果是字符串路径打开的文件，需要关闭
            if should_close and fileobj is not None and hasattr(fileobj, "close"):
                fileobj.close()

        return file_path

    @override
    @classmethod
    def _parse_define(
        cls, bk_tenant_id: str, operator: str, extract_dir: Path, plugin_id: str, meta_data: dict[str, Any]
    ) -> dict[str, Any]:
        """解析 define 字段

        meta.yaml 文件示例如下:
        ```yaml
        plugin_id: bkplugin_consul
        plugin_display_name: Consul
        plugin_type: DataDog
        tag:
        label: component
        is_support_remote: True
        datadog_check_name: consul
        ```

        从meta.yaml中获取datadog_check_name字段，并记录在 define 字段中
        将info/config.yaml.tpl文件内容记录在 define 字段中，key为config_yaml
        将各操作系统包下的lib文件夹压缩为zip文件，上传到uploaded_file模块，并记录file_token和file_name

        Args:
            bk_tenant_id: 租户ID
            operator: 操作人
            extract_dir: 解压根目录路径
            plugin_id: 插件ID
            meta_data: meta.yaml 文件内容

        Returns:
            define 字段内容
            Example:
            {
                "datadog_check_name": "consul",
                "config_yaml": "xxx",
                "windows": {
                    "file_token": "xxx",
                    "file_name": "bkplugin_consul-lib-windows.zip"
                },
                "linux": {
                    "file_token": "xxx",
                    "file_name": "bkplugin_consul-lib-linux.zip"
                }
            }

        Raises:
            ValueError: 如果 meta.yaml 文件内容不合法
        """
        define: dict[str, Any] = {}

        # 1. 提取 datadog_check_name
        datadog_check_name = meta_data.get("datadog_check_name")
        if not datadog_check_name or not isinstance(datadog_check_name, str):
            raise ValueError("meta.yaml 中缺少 datadog_check_name 字段或字段值不合法")
        define["datadog_check_name"] = datadog_check_name
        logger.info(msg=f"提取 datadog_check_name: {datadog_check_name}")

        # 2. 读取配置文件内容
        # 首先尝试找到任意一个插件目录来读取配置文件
        config_yaml_content = ""
        plugin_dir_found: Path | None = None

        # 遍历所有操作系统目录，找到第一个存在的插件目录
        for os_plugin_dir in extract_dir.iterdir():
            if not os_plugin_dir.is_dir() or not os_plugin_dir.name.startswith("external_plugins_"):
                continue

            # 查找该操作系统目录下的插件目录
            for sub_dir in os_plugin_dir.iterdir():
                if sub_dir.is_dir():
                    plugin_dir_found = sub_dir
                    break

            if plugin_dir_found:
                break

        if plugin_dir_found:
            # 优先尝试读取 info/config.yaml.tpl
            config_yaml_path = plugin_dir_found / "info" / "config.yaml.tpl"
            if not config_yaml_path.exists():
                # 如果不存在，尝试读取 etc/conf.yaml.tpl
                config_yaml_path = plugin_dir_found / "etc" / "conf.yaml.tpl"
                if not config_yaml_path.exists():
                    # 最后尝试读取 etc/conf.yaml.example
                    config_yaml_path = plugin_dir_found / "etc" / "conf.yaml.example"

            if config_yaml_path.exists():
                try:
                    config_yaml_content = config_yaml_path.read_text(encoding="utf-8")
                    logger.info(f"读取配置文件成功: {config_yaml_path}")
                except Exception as e:
                    logger.warning(f"读取配置文件失败: {config_yaml_path}, 错误: {e}")
            else:
                logger.warning("未找到配置文件，已尝试: info/config.yaml.tpl, etc/conf.yaml.tpl, etc/conf.yaml.example")

        define["config_yaml"] = config_yaml_content

        # 3. 处理各操作系统的 lib 文件夹
        for os_type in OSType:
            os_dir_name = OSTypeToPluginDirName.get(os_type)
            if not os_dir_name:
                logger.warning(f"操作系统类型 {os_type.value} 没有对应的目录名，跳过")
                continue

            # 构建操作系统目录路径
            os_dir_path = extract_dir / os_dir_name
            if not os_dir_path.exists():
                logger.debug(f"操作系统目录不存在: {os_dir_path}，跳过")
                continue

            # 查找插件子目录
            plugin_subdir: Path | None = None
            for sub_dir in os_dir_path.iterdir():
                if sub_dir.is_dir():
                    plugin_subdir = sub_dir
                    break

            if not plugin_subdir:
                logger.warning(f"在 {os_dir_path} 中未找到插件子目录，跳过")
                continue

            # 检查 lib 文件夹是否存在
            lib_path = plugin_subdir / "lib"
            if not lib_path.exists() or not lib_path.is_dir():
                logger.warning(f"lib 文件夹不存在: {lib_path}，跳过")
                continue

            # 压缩 lib 文件夹为 zip 文件
            zip_filename = f"{plugin_id}-lib-{os_type.value}.zip"
            temp_zip_path = Path(tempfile.mkdtemp()) / zip_filename

            try:
                # 创建 zip 文件
                with zipfile.ZipFile(temp_zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                    # 遍历 lib 目录下的所有文件
                    for root, _, files in os.walk(lib_path):
                        for file in files:
                            file_path = Path(root) / file
                            # 计算相对路径，保持 lib/ 前缀
                            # lib_path 是 plugin_dir/lib，relative_to(lib_path.parent) 会得到 lib/... 格式
                            arcname = file_path.relative_to(lib_path.parent)
                            zipf.write(file_path, arcname)

                logger.info(f"压缩 lib 文件夹成功: {lib_path} -> {temp_zip_path}")

                # 读取 zip 文件内容
                zip_content = temp_zip_path.read_bytes()

                # 上传到 uploaded_file 模块
                file_info = save_file(
                    bk_tenant_id=bk_tenant_id,
                    usage="datadog_plugin",
                    created_by=operator,
                    file_or_content=zip_content,
                    filename=zip_filename,
                    description=f"DataDog插件 {plugin_id} 的 {os_type.value} lib 文件夹",
                )

                # 记录到 define
                define[os_type.value] = {"file_token": file_info.token, "file_name": zip_filename}

                logger.info(f"上传 lib zip 文件成功: {os_type.value} -> {zip_filename}, file_token: {file_info.token}")

            except Exception as e:
                logger.error(f"处理 {os_type.value} 的 lib 文件夹失败: {e}", exc_info=True)
                raise ValueError(f"处理 {os_type.value} 的 lib 文件夹失败: {e}") from e
            finally:
                # 清理临时 zip 文件
                if temp_zip_path.exists():
                    try:
                        temp_zip_path.unlink()
                        temp_zip_path.parent.rmdir()
                    except Exception:
                        pass  # 忽略清理失败的错误

        return define
