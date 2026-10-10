from typing import Any, ClassVar, final

from typing_extensions import override

from bk_monitor_base.domains.metric_plugin.errors import ParseOsTypeError
from bk_monitor_base.domains.metric_plugin.manager.base import OSType
from bk_monitor_base.domains.metric_plugin.manager.job.base import SQLPluginManager


@final
class DB2PluginManager(SQLPluginManager):
    """
    DB2 Job插件管理器
    Repo 必须包含以下文件:
    - job_plugin/job_db2/DB2UniversalPlugin (Linux X86_64)
    - job_plugin/job_db2/db2_driver/linuxx64_odbc_cli.tar.gz (Linux X86_64 DB2驱动依赖包)

    暂时db2的驱动无法做到清理，不确定是否存在采集实例在用，故仅做安装不做清理，仅清理压缩包
    """

    type: ClassVar[str] = "job_db2"
    DB_TYPE: ClassVar[str] = "db2"
    # 启动调试脚本
    START_DEBUG_METRICS_SCRIPTS: dict[OSType, Any] = {
        OSType.LINUX: """
            #!/bin/bash
            if [ -e "/data/IBM" ] && [ "$(ls -A /data/IBM)" ]; then
                chmod +x {file_path}
                {file_path} -f {config_path} -debug true
                exit 0
            fi
            if [ -f "{target_path}/linuxx64_odbc_cli.tar.gz" ]; then
                mkdir -p /data/IBM/
                tar xf {target_path}/linuxx64_odbc_cli.tar.gz -C /data/IBM/
                chmod +x {file_path}
                {file_path} -f {config_path} -debug true
                exit 0
            fi
        """,
    }

    # 各系统版本依赖驱动压缩包路径
    DB2_DRIVER_PACKAGE_PATHS: dict[OSType, str] = {
        OSType.LINUX: "db2_driver/linuxx64_odbc_cli.tar.gz",
    }
    # 各系统版本插件二进制文件路径
    BINARY_PATHS: dict[OSType, str] = {
        OSType.LINUX: "DB2UniversalPlugin",
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
        try:
            driver_package_path = self.DB2_DRIVER_PACKAGE_PATHS[os_type]
            return [f"{self.basic_file_path}/{driver_package_path}"]
        except KeyError:
            raise ParseOsTypeError(f"不支持的操作系统类型: {os_type}")

    @override
    def get_supported_os_types(self) -> list[OSType]:
        """获取支持的操作系统类型"""
        supported_os_types: list[OSType] = []
        for os_type in self.BINARY_PATHS.keys():
            supported_os_types.append(os_type)
        return supported_os_types
