import base64
import logging
from pathlib import Path
from typing import Any, ClassVar, final

from typing_extensions import override

from bk_monitor_base.domains.metric_plugin.constants import PluginType
from bk_monitor_base.domains.metric_plugin.manager.base import OSType
from bk_monitor_base.domains.metric_plugin.manager.node_man.base import (
    CommandPluginManager,
    OSTypeToPluginDirName,
    TextFile,
)

logger = logging.getLogger(__name__)


@final
class ScriptPluginManager(CommandPluginManager):
    """脚本插件管理器

    允许用户上传脚本文件, 通过bkmonitorbeat定时执行脚本, 脚本的标准输出需要返回 Prometheus 格式的指标数据。

    define 字段定义:
    可以支持多种操作系统类型, 每种操作系统类型对应一个脚本文件。该脚本会被下发到插件目录下, 由start.(sh|bat|ksh)脚本执行。
    {
        "linux": {
            "type": "shell",
            "filename": "script.sh",
            "script_content_base64": "base64编码的脚本内容"
        },
        "windows": {
            "type": "bat",
            "filename": "script.bat",
            "script_content_base64": "base64编码的脚本内容"
        },
        "aix": {
            "type": "ksh",
            "filename": "script.ksh",
            "script_content_base64": "base64编码的脚本内容"
        }
    }
    """

    type: ClassVar[str] = PluginType.SCRIPT
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
        text_files: dict[OSType, list[TextFile]] = {}
        for os_type in self.get_supported_os_types():
            if not self.plugin.define.get(os_type.value):
                continue
            os_config = self.plugin.define[os_type.value]
            text_files[os_type] = [
                {
                    "path": os_config["filename"],
                    "content": base64.b64decode(os_config["script_content_base64"]).decode("utf-8"),
                }
            ]

        return self._make_package(extra_text_files=text_files, is_compress=is_compress)

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
        return self._get_deploy_steps_params(
            bk_biz_id,
            collect_task_id,
            bk_data_ids,
            collect_params,
            plugin_params,
            extra_collect_context={
                "command": f"{{{{ step_data.{self.plugin.id}.control_info.setup_path }}}}/{{{{ step_data.{self.plugin.id}.control_info.start_cmd }}}}"
            },
        )

    @override
    @classmethod
    def _parse_define(
        cls, bk_tenant_id: str, operator: str, extract_dir: Path, plugin_id: str, meta_data: dict[str, Any]
    ) -> dict[str, Any]:
        """解析 define 字段

        根据meta.yaml中的记录，将脚本文件内容转换为base64编码后存储到define中。

        meta.yaml 文件示例如下:
        ```yaml
        plugin_id: lgtt
        plugin_display_name: lgtt
        plugin_type: Script
        tag:
        label: os
        scripts:

        linux:
            type: shell
            filename: lgtt.sh
        windows:
            type: bat
            filename: lgtt.bat
        aix:
            type: ksh
            filename: lgtt.sh

        is_support_remote: False
        ```
        根据meta.yaml中的记录，从各操作系统包下获取脚本文件内容，转换为base64编码后存储到define中。

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
                "linux": {
                    "type": "shell",
                    "filename": "lgtt.sh",
                    "script_content_base64": "base64编码的脚本内容"
                },
                "windows": {
                    "type": "bat",
                    "filename": "lgtt.bat",
                    "script_content_base64": "base64编码的脚本内容"
                },
                "aix": {
                    "type": "ksh",
                    "filename": "lgtt.sh",
                    "script_content_base64": "base64编码的脚本内容"
                }
            }

        Raises:
            ValueError: 如果 scripts 配置不存在、为空或脚本文件不存在
        """
        scripts_config = meta_data.get("scripts", {})
        if not scripts_config:
            raise ValueError("meta.yaml 中未找到 scripts 配置")

        define: dict[str, Any] = {}

        for os_type_str, script_info in scripts_config.items():
            if not isinstance(script_info, dict):
                raise ValueError(f"scripts 配置中 {os_type_str} 的值必须是字典类型")

            script_type_any: Any = script_info.get("type", "")  # pyright: ignore[reportUnknownVariableType]
            script_filename_any: Any = script_info.get("filename", "")  # pyright: ignore[reportUnknownVariableType]

            if not script_type_any or not isinstance(script_type_any, str):
                raise ValueError(f"scripts 配置中 {os_type_str} 缺少 type 字段或类型不正确")
            if not script_filename_any or not isinstance(script_filename_any, str):
                raise ValueError(f"scripts 配置中 {os_type_str} 缺少 filename 字段或类型不正确")

            # 经过 isinstance 检查后，可以安全地使用
            script_type: str = script_type_any
            script_filename: str = script_filename_any

            # 通过 OSType 枚举查找对应的操作系统类型
            os_type_enum: OSType | None = None
            for os_type in OSType:
                if os_type.value == os_type_str:
                    os_type_enum = os_type
                    break

            if not os_type_enum:
                supported_types = [os_type.value for os_type in OSType]
                raise ValueError(f"不支持的操作系统类型: {os_type_str}，支持的类型: {supported_types}")

            # 获取操作系统目录名
            os_dir_name = OSTypeToPluginDirName.get(os_type_enum)
            if not os_dir_name:
                raise ValueError(f"无法找到操作系统类型 {os_type_str} 对应的目录名")

            # 构建脚本文件路径
            script_file_path: Path = extract_dir / os_dir_name / plugin_id / script_filename

            # 检查文件是否存在
            if not script_file_path.exists():
                raise ValueError(f"脚本文件不存在: {script_file_path}")

            # 读取脚本文件内容
            try:
                script_content: str = script_file_path.read_text(encoding="utf-8")
            except Exception as e:
                raise ValueError(f"读取脚本文件失败: {script_file_path}, 错误: {e}") from e

            # 转换为 base64 编码
            try:
                script_content_base64: str = base64.b64encode(script_content.encode("utf-8")).decode("utf-8")
            except Exception as e:
                raise ValueError(f"base64 编码失败: {script_file_path}, 错误: {e}") from e

            # 构建 define 项
            define[os_type_str] = {
                "type": script_type,
                "filename": script_filename,
                "script_content_base64": script_content_base64,
            }

            logger.info(f"解析脚本文件成功: {os_type_str} -> {script_file_path}")

        return define
