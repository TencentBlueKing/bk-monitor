from typing import Any, Dict, List, Optional, Tuple

from ...models import PluginVersionHistory
from .base import BasePluginManager


class K8sPluginManager(BasePluginManager):
    def release(
        self, config_version: int, info_version: int, token: List[str] = None, debug: bool = True
    ) -> PluginVersionHistory:
        pass

    def create_version(self, data: Dict[str, Any]) -> Tuple[PluginVersionHistory, bool]:
        pass

    def update_version(
        self, data: Dict[str, Any], target_config_version: int = None, target_info_version: int = None
    ) -> Tuple[PluginVersionHistory, bool]:
        pass

    def make_package(
        self,
        add_files: Dict[str, List[Dict[str, str]]] = None,
        add_dirs: Dict[str, List[Dict[str, str]]] = None,
        need_tar: bool = True,
    ) -> Optional[str]:
        pass

    def run_export(self) -> str:
        return ""
