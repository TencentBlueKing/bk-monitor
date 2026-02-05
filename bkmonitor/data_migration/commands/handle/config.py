"""handle 配置（可变全局注册表）。

说明：
    - 这里存放"可变的全局注册表"，避免与 pipeline 核心逻辑混在一起
    - 之所以单独拆出来，是为了让 export/handle 等调用方可以明确依赖"配置层"
"""

from __future__ import annotations

from .builtins import disable_enable_fields, filter_is_deleted, replace_bk_tenant_id
from .handle import RowTransformer

# 表级别处理映射
#
# key 支持两类：
# - "app_label.ModelName"：指定单张表的处理链
# - "*"：通配处理，会被追加到每张表处理链的最后执行
TABLE_PIPELINE_MAPPING: dict[str, list[RowTransformer]] = {
    "bkmonitor.StrategyModel": [disable_enable_fields],
    "monitor_web.CollectConfigMeta": [disable_enable_fields],
    "monitor_web.UptimeCheckTask": [disable_enable_fields],
    "bkmonitor.ReportItems": [disable_enable_fields],
    "bkmonitor.Report": [disable_enable_fields],
    "metadata.DataSource": [disable_enable_fields],
    "metadata.ResultTable": [disable_enable_fields],
    "bkmonitor.Shield": [filter_is_deleted],
    "apm.ApmApplication": [disable_enable_fields],
    "*": [replace_bk_tenant_id],
}

# =============================================================================
# 全局处理列表（按顺序执行）
# =============================================================================

GLOBAL_PIPELINES: list = []
