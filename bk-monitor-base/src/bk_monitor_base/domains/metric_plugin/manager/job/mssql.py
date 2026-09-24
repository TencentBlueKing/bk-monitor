# pyright: reportUnusedParameter=false
# pyright: reportReturnType=false

from typing import ClassVar, final

from typing_extensions import override

from bk_monitor_base.domains.metric_plugin.errors import ParseOsTypeError
from bk_monitor_base.domains.metric_plugin.manager.base import OSType
from bk_monitor_base.domains.metric_plugin.manager.job.base import SQLPluginManager


@final
class MSSQLPluginManager(SQLPluginManager):
    """
    MSSQL Job插件管理器

    Repo 必须包含以下文件:
    - job_plugin/job_mssql/OracleUniversalPlugin (Linux X86_64)
    - job_plugin/job_mssql/OracleUniversalPlugin_arm (Linux AARCH64)
    """

    type: ClassVar[str] = "job_mssql"
    DB_TYPE: ClassVar[str] = "mssql"
    BINARY_PATHS: dict[OSType, str] = {
        OSType.LINUX: "OracleUniversalPlugin",
        OSType.LINUX_AARCH64: "OracleUniversalPlugin_arm",
    }

    @override
    def get_binary_path(self, os_type: OSType) -> str:
        """获取二进制文件路径"""
        try:
            binary_path_template = f"{self.basic_file_path}/{self.BINARY_PATHS[os_type]}"
        except KeyError:
            raise ParseOsTypeError(f"不支持的操作系统类型: {os_type}")

        return binary_path_template

    @override
    def get_extra_file_source_paths(self, os_type: OSType) -> list[str]:
        """
        获取插件包额外文件路径信息
        Args:
            os_type: 操作系统类型
        Returns:
            额外文件路径列表(repo内相对路径)
        """
        return []

    @override
    def get_supported_os_types(self) -> list[OSType]:
        """获取支持的操作系统类型"""
        supported_os_types: list[OSType] = []
        for os_type in self.BINARY_PATHS.keys():
            supported_os_types.append(os_type)
        return supported_os_types
