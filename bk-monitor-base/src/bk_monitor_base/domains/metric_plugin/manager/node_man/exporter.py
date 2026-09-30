import logging
import os
import tempfile
from pathlib import Path
from typing import Any, ClassVar, final

from typing_extensions import override

from bk_monitor_base.domains.metric_plugin.constants import PluginType
from bk_monitor_base.domains.metric_plugin.manager.base import OSType
from bk_monitor_base.domains.metric_plugin.manager.node_man.base import (
    CommandPluginManager,
    ExtraFile,
    OSTypeToPluginDirName,
)
from bk_monitor_base.domains.uploaded_file.operation import get_file, save_file
from bk_monitor_base.infras.types import FILE_OR_CONTENT_TYPE

logger = logging.getLogger(__name__)


@final
class ExporterPluginManager(CommandPluginManager):
    """
    Exporter插件管理器
    """

    type: ClassVar[str] = PluginType.EXPORTER
    _SUB_CONFIG_NAME: ClassVar[str] = "bkmonitorbeat_prometheus.conf"

    _EXPORTER_DIR_NAME: ClassVar[str] = "metric_plugin/exporter/"

    @override
    def get_supported_os_types(self) -> list[OSType]:
        """获取支持的操作系统类型"""
        supported_os_types: list[OSType] = []
        for os_type in OSType:
            if os_type.value in self.plugin.define:
                supported_os_types.append(os_type)
        return supported_os_types

    @override
    def _get_package_context(self) -> dict[str, Any]:
        """获取上下文，用于渲染插件包中的文本文件"""

        context = super()._get_package_context()
        # 端口探测能力，当 port 未配置时，默认探测 10000-65535 端口；当 port 配置了默认值时，优先探测默认值端口，再探测 10000-65535 端口
        context["port_range"] = "10000-65535"
        try:
            default_port = [x for x in self.plugin.params if x.name == "port"][0].default
            if default_port:
                context["port_range"] = f"{default_port},10000-65535"
        except Exception:
            pass
        return context

    @override
    def make_package(self, is_compress: bool = True) -> Path:
        """制作插件包

        从 plugin.define 中读取每个操作系统的 file_token 和 file_name，
        通过 uploaded_file 模块获取文件，并将二进制文件注入到插件包中。

        Args:
            is_compress: 是否压缩

        Returns:
            如果不需要压缩，则返回插件包目录路径；如果需要压缩，则返回压缩包路径
        """
        extra_files: dict[OSType, list[ExtraFile]] = {}
        temp_dir = Path(tempfile.mkdtemp())

        try:
            # 遍历插件支持的所有操作系统类型
            for os_type in self.get_supported_os_types():
                # 从 define 中获取该操作系统类型的配置
                os_define = self.plugin.define.get(os_type.value)
                if not os_define:
                    logger.warning(f"插件 {self.plugin.id} 的操作系统类型 {os_type.value} 在 define 中不存在，跳过")
                    continue

                # 获取 file_token
                file_token = os_define.get("file_token")
                if not file_token:
                    logger.warning(f"插件 {self.plugin.id} 的操作系统类型 {os_type.value} 缺少 file_token，跳过")
                    continue

                # 获取文件信息
                try:
                    file_info = get_file(bk_tenant_id=self.plugin.bk_tenant_id, file_token=file_token)
                except Exception as e:
                    error_msg = (
                        f"获取插件 {self.plugin.id} 的操作系统类型 {os_type.value} 的二进制文件失败: "
                        f"file_token={file_token}, 租户ID={self.plugin.bk_tenant_id}. "
                        f"请确保文件已通过 uploaded_file 模块上传并迁移。错误: {e}"
                    )
                    logger.error(error_msg, exc_info=True)
                    raise ValueError(error_msg) from e

                # 固定二进制文件名为 plugin_id 或 plugin_id.exe
                target_filename = self.plugin.id
                if os_type == OSType.WINDOWS:
                    target_filename += ".exe"

                # 将文件保存到临时目录
                temp_file_path = temp_dir / f"{os_type.value}_{target_filename}"
                with open(temp_file_path, "wb") as f:
                    # 读取文件内容并写入临时文件
                    # 确保文件指针在开始位置
                    if hasattr(file_info.file, "seek"):
                        file_info.file.seek(0)
                    # 读取文件内容
                    file_content = file_info.file.read()
                    f.write(file_content)

                # 设置文件权限为可执行（如果需要）
                os.chmod(temp_file_path, 0o755)

                # 构建 extra_files
                if os_type not in extra_files:
                    extra_files[os_type] = []
                extra_files[os_type].append(
                    ExtraFile(
                        source_path=str(temp_file_path),
                        target_path=target_filename,
                    )
                )

                logger.info(
                    f"插件 {self.plugin.id} 的操作系统类型 {os_type.value} 的二进制文件已准备: {target_filename}"
                )
        except Exception as e:
            logger.error(f"准备插件 {self.plugin.id} 的二进制文件失败: {e}", exc_info=True)
            raise

        return self._make_package(extra_files=extra_files, is_compress=is_compress)

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
            collect_params: 采集参数，如采集周期，超时时间，绑定IP/端口，可以理解为内置参数
            plugin_params: 插件定义参数，用户自定义的参数
            target_nodes: 采集目标节点

        Returns:
            部署步骤参数列表
        """
        # 处理端口参数
        if collect_params.get("port"):
            plugin_params["port"] = collect_params["port"]
        else:
            plugin_params["port"] = "{{ control_info.listen_port }}"
            collect_params["port"] = f"{{{{ step_data.{self.plugin.id}.control_info.listen_port }}}}"

        # 处理差异化指标
        diff_fields: str = self.plugin.define.get("diff_fields", "")
        diff_metrics = diff_fields.split(",") if diff_fields else []

        return self._get_deploy_steps_params(
            bk_biz_id,
            collect_task_id,
            bk_data_ids,
            collect_params,
            plugin_params,
            extra_collect_context={
                "metric_url": f"{collect_params['host']}:{collect_params['port']}/metrics",
                "diff_metrics": diff_metrics,
            },
        )

    @override
    def _get_debug_config_context(
        self, collect_params: dict[str, Any], plugin_params: dict[str, Any], target_nodes: list[dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        collect_params["metric_url"] = f"{collect_params['host']}:{collect_params['port']}/metrics"
        return super()._get_debug_config_context(collect_params, plugin_params, target_nodes)

    @classmethod
    def check_file(cls, file_or_content: FILE_OR_CONTENT_TYPE, os_type: OSType) -> tuple[bool, str, dict[str, Any]]:
        """校验文件是否符合Exporter插件文件要求

        Args:
            file_or_content: 文件或内容
            os_type: 操作系统类型

        Returns:
            (是否合法, 错误原因, 提取信息)
        """
        filename = None
        header = b""

        try:
            if isinstance(file_or_content, bytes):
                header = file_or_content[:4]
            elif isinstance(file_or_content, str):
                pass
            else:
                if hasattr(file_or_content, "name"):
                    filename = getattr(file_or_content, "name", None)

                if hasattr(file_or_content, "read"):
                    pos = file_or_content.tell() if hasattr(file_or_content, "tell") else 0
                    if hasattr(file_or_content, "seek"):
                        file_or_content.seek(0)

                    content = file_or_content.read(4)
                    if hasattr(file_or_content, "seek"):
                        file_or_content.seek(pos)

                    if isinstance(content, str):
                        header = content.encode("utf-8")
                    elif isinstance(content, bytes):
                        header = content
        except Exception:
            pass

        match os_type:
            case OSType.WINDOWS:
                # 1. 检查文件名 (如果有)
                if filename and not filename.lower().endswith(".exe"):
                    return False, f"文件{filename}不是windows下的可执行文件", {}
                # 2. 检查长度
                if len(header) < 2:
                    return False, "文件不是有效的可执行文件", {}
                # 3. 检查文件头 (MZ)
                if header[:2] != b"MZ":
                    return False, "文件不是windows下的可执行文件", {}

                return True, "", {}

            case OSType.LINUX | OSType.LINUX_AARCH64:
                # 1. 检查文件名 (如果有) - linux下不能以exe结尾
                if filename and filename.lower().endswith(".exe"):
                    return False, f"文件{filename}不是linux下的可执行文件", {}
                # 2. 检查长度/内容
                if len(header) < 4:
                    return False, "文件不是有效的可执行文件", {}
                # 3. 检查文件头 (ELF)
                if header != b"\x7fELF":
                    return False, "文件不是linux下的可执行文件", {}
                return True, "", {}

            case OSType.AIX:
                return True, "", {}

    @override
    @classmethod
    def _parse_define(
        cls, bk_tenant_id: str, operator: str, extract_dir: Path, plugin_id: str, meta_data: dict[str, Any]
    ) -> dict[str, Any]:
        """解析 define 字段

        exporter的二进制文件名字是固定的
        1. windows: {plugin_id}.exe
        2. 其他: {plugin_id}

        读取对应的二进制文件，通过uploaded_file模块上传文件，并记录file_token和file_name

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
                "windows": {
                    "file_token": "file_token",
                    "file_name": "lgtt.exe"
                },
                "linux": {
                    "file_token": "file_token",
                    "file_name": "lgtt"
                }
                "aix": {
                    "file_token": "file_token",
                    "file_name": "lgtt"
                }
            }

        Raises:
            ValueError: 如果 plugin_id 不存在、二进制文件不存在或上传文件失败
        """
        define: dict[str, Any] = {}

        # 遍历支持的操作系统类型
        for os_type in OSType:
            # 获取操作系统目录名
            os_dir_name = OSTypeToPluginDirName.get(os_type)
            if not os_dir_name:
                logger.warning(f"操作系统类型 {os_type.value} 没有对应的目录名，跳过")
                continue

            # 构建操作系统目录路径
            os_dir_path: Path = extract_dir / os_dir_name
            if not os_dir_path.exists() or not os_dir_path.is_dir():
                logger.warning(f"操作系统目录不存在: {os_dir_path}, 跳过")
                continue

            # 构建二进制文件名
            if os_type == OSType.WINDOWS:
                binary_filename = f"{plugin_id}.exe"
            else:
                binary_filename = plugin_id

            # 构建二进制文件路径
            binary_file_path: Path = os_dir_path / plugin_id / binary_filename

            # 检查文件是否存在
            if not binary_file_path.exists():
                raise ValueError(f"二进制文件不存在: {binary_file_path}")

            # 读取二进制文件内容
            try:
                binary_content: bytes = binary_file_path.read_bytes()
            except Exception as e:
                raise ValueError(f"读取二进制文件失败: {binary_file_path}, 错误: {e}") from e

            # 通过 save_file 上传文件，获取 file_token
            try:
                file_info = save_file(
                    bk_tenant_id=bk_tenant_id,
                    usage="exporter_plugin",
                    created_by=operator,
                    file_or_content=binary_content,
                    filename=binary_filename,
                    description=f"Exporter插件 {plugin_id} 的 {os_type.value} 二进制文件",
                )
            except Exception as e:
                raise ValueError(f"上传二进制文件失败: {binary_file_path}, 错误: {e}") from e

            # 构建 define 项
            define[os_type.value] = {"file_token": file_info.token, "file_name": binary_filename}

            logger.info(f"解析二进制文件成功: {os_type.value} -> {binary_file_path}, file_token: {file_info.token}")

        return define
