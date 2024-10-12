from typing import Dict, List, Optional, Tuple

from monitor_web.commons.data_access import PluginDataAccessor
from monitor_web.models.plugin import PluginVersionHistory

from .base import BasePluginManager


class K8sPluginManager(BasePluginManager):
    """
    K8s插件管理器
    """

    def release(
        self, config_version: int, info_version: int, token: List[str] = None, debug: bool = True
    ) -> PluginVersionHistory:
        """
        插件发布
        """
        # 数据接入
        current_version = self.plugin.get_version(config_version, info_version)
        return self._release(current_version, skip_access=True)

    def _release(
        self,
        version: PluginVersionHistory,
        skip_access: bool = False,
        data_label: str = None,
    ) -> PluginVersionHistory:
        """
        插件发布
        """

        # k8s插件需要开启字段黑名单
        if not version.info.enable_field_blacklist:
            version.info.enable_field_blacklist = True
            version.info.save()

        # 数据接入
        if not skip_access:
            PluginDataAccessor(version, self.operator, data_label=data_label).access()

        # 标记为已发布
        version.stage = PluginVersionHistory.Stage.RELEASE
        version.is_packaged = True
        version.save()

        return version

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

    def create_version(self, data) -> Tuple[PluginVersionHistory, bool]:
        version, _ = super().create_version(data)
        # 创建版本后直接发布
        self._release(version, data_label=data.get("data_label"))
        return version, False

    def update_version(self, data, target_config_version: int = None, target_info_version: int = None):
        version, _ = super().update_version(data, target_config_version, target_info_version)
        self._release(version, skip_access=True, data_label=data.get("data_label"))
        return version, False
