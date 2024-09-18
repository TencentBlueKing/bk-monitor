from typing import Dict, List, Optional

from monitor_web.commons.data_access import PluginDataAccessor
from monitor_web.models import PluginVersionHistory

from .base import BasePluginManager


class K8sPluginManager(BasePluginManager):
    """
    K8s插件管理器
    collector_json: {
        "template.yaml": "",
        "values"
    }
    """

    def release(
        self, config_version: int, info_version: int, token: List[str] = None, debug: bool = True
    ) -> PluginVersionHistory:
        """
        插件发布
        """
        # 数据接入
        current_version = self.plugin.get_version(config_version, info_version)

        # k8s插件需要开启字段黑名单
        if not current_version.info.enable_field_blacklist:
            current_version.info.enable_field_blacklist = True
            current_version.info.save()

        # 数据接入
        PluginDataAccessor(current_version, self.operator).access()

        # 标记为已发布
        current_version.stage = PluginVersionHistory.Stage.RELEASE
        current_version.is_packaged = True
        current_version.save()
        return current_version

    def make_package(
        self,
        add_files: Dict[str, List[Dict[str, str]]] = None,
        add_dirs: Dict[str, List[Dict[str, str]]] = None,
        need_tar: bool = True,
    ) -> Optional[str]:
        """
        todo: 目前暂时不需要实现
        """

    def run_export(self) -> str:
        """
        todo: 目前暂时不需要实现
        """
        return ""

    def create_version(self, data):
        version, _ = super().create_version(data)
        # 创建版本后直接发布
        self.release(version.config.id, version.info.id)
        return version, False
