"""监控侧节点管理集成的公共值类型，不包含任一版本的远端协议。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CollectionStatistics:
    """采集实例统计；缺失结果用 None 表示，不能伪装成零实例成功。"""

    total: int = 0
    failed: int = 0
    pending: int = 0
    running: int = 0

    def as_cache_data(self) -> dict[str, int]:
        """转换为既有采集页面缓存格式。"""
        return {"total_instance_count": self.total, "error_instance_count": self.failed}
