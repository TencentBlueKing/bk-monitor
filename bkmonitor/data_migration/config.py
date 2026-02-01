# 默认导出模型列表，支持 app_label 或 app_label.ModelName
DEFAULT_EXPORT_MODELS: list[str] = [
    "metadata.Label",
    "metadata.BkAppSpaceRecord",
    "metadata.CustomRelationStatus",
    # space
    "metadata.Space",
    "metadata.SpaceType",
    "metadata.SpaceDataSource",
    "metadata.SpaceResource",
    "metadata.SpaceStickyInfo",
    "metadata.SpaceVMInfo",
    "metadata.SpaceRelatedStorageInfo",
    # cluster
    "metadata.ClusterInfo",
    # bcs
    "metadata.BCSClusterInfo",
    "metadata.BcsFederalClusterInfo",
    "metadata.ServiceMonitorInfo",
    "metadata.PodMonitorInfo",
    "metadata.LogCollectorInfo",
    # data source
    "metadata.DataSource",
    "metadata.DataSourceOption",
    "metadata.DataSourceResultTable",
    # result table
    "metadata.ResultTable",
    "metadata.ResultTableOption",
    "metadata.ResultTableField",
    "metadata.ResultTableFieldOption",
    # storage
    "metadata.ESStorage",
    "metadata.AccessVMRecord",
    "metadata.KafkaStorage",
    "metadata.DorisStorage",
    "metadata.StorageClusterRecord",
    "metadata.KafkaTopicInfo",
    "metadata.ESFieldQueryAliasOption",
    # es snapshot
    "metadata.EsSnapshot",
    "metadata.EsSnapshotIndice",
    "metadata.EsSnapshotRepository",
    "metadata.EsSnapshotRestore",
    # custom report
    "metadata.TimeSeriesGroup",
    "metadata.TimeSeriesMetric",
    "metadata.EventGroup",
    "metadata.Event",
    "metadata.LogGroup",
    # collector installer
    "metadata.CustomReportSubscription",
    "metadata.CustomReportSubscriptionConfig",
    "metadata.LogSubscriptionConfig",
    "metadata.PingServerSubscriptionConfig",
    # datalink
    "metadata.BkBaseResultTable",
    "metadata.DataLink",
    "metadata.DataIdConfig",
    "metadata.DataBusConfig",
    "metadata.ClusterConfig",
    "metadata.ResultTableConfig",
    "metadata.ESStorageBindingConfig",
    "metadata.VMStorageBindingConfig",
    "metadata.DorisStorageBindingConfig",
    "metadata.ConditionalSinkConfig",
    # apm
    "apm",
    "apm_web",
    "apm_ebpf",
    # calendars
    "calendars",
    # saas功能
    "monitor.ApplicationConfig",
    "monitor.UptimeCheckTaskSubscription",
    "monitor_web",
    # bkmonitor
    # 策略
    "bkmonitor.StrategyModel",
    "bkmonitor.ItemModel",
    "bkmonitor.DetectModel",
    "bkmonitor.AlgorithmModel",
    "bkmonitor.QueryConfigModel",
    "bkmonitor.StrategyHistoryModel",
    "bkmonitor.StrategyLabel",
    "bkmonitor.NoticeTemplate",
    "bkmonitor.Shield",
    "bkmonitor.UserGroup",
    "bkmonitor.StrategyActionConfigRelation",
    "bkmonitor.NoticeSubscribe",
    # 自愈套餐
    "bkmonitor.ActionConfig",
    "bkmonitor.ActionPlugin",
    # 告警分派
    "bkmonitor.AlertAssignGroup",
    "bkmonitor.AlertAssignRule",
    # 告警源
    "bkmonitor.EventPluginV2",
    "bkmonitor.AlertConfig",
    "bkmonitor.EventPluginInstance",
    # ai
    "bkmonitor.AIFeatureSettings",
    # bcs
    "bkmonitor.BCSCluster",
    # 查询模板
    "bkmonitor.QueryTemplate",
    # 轮值
    "bkmonitor.DutyPlan",
    "bkmonitor.DutyPlanSendRecord",
    "bkmonitor.DutyRule",
    "bkmonitor.DutyRuleRelation",
    "bkmonitor.DutyRuleSnap",
    "bkmonitor.DutyArrange",
    "bkmonitor.DutyArrangeSnap",
    # api token
    "bkmonitor.ApiAuthToken",
    # 默认策略
    "bkmonitor.DefaultStrategyBizAccessModel",
    # 告警中心
    "fta_web.SearchFavorite",
    "fta_web.SearchHistory",
    "fta_web.AlertSuggestion",
    "fta_web.AlertFeedback",
    "fta_web.MetricRecommendationFeedback",
    # 仪表盘订阅报表
    "bkmonitor.ReportItems",
    "bkmonitor.ReportContents",
    # 新订阅报表
    "bkmonitor.ReportChannel",
    "bkmonitor.Report",
    # 主页
    "bkmonitor.HomeAlarmGraphConfig",
    # iam迁移记录
    "bkmonitor.MonitorMigration",
]

# 默认排除模型列表，支持 app_label 或 app_label.ModelName
EXCLUDE_EXPORT_MODELS: list[str] = [
    # 后台告警表
    "bkmonitor.ActionInstanceLog",
    "bkmonitor.Alert",
    "bkmoitor.Event",
    "bkmonitor.ActionInstance",
    "bkmonitor.ConvergeInstance",
    "bkmonitor.ConvergeRelation",
    "bkmonitor.AnomalyRecord",
    "bkmonitor.AlertCollect",
    "bkmonitor.BaseAlarmbkmonitor.NoticeTemplate",
    # 导入导出历史
    "monitor_web.ImportDetail",
    "monitor_web.ImportHistory",
    "monitor_web.UserAccessRecord",
    "monitor_web.ImportParse",
    "monitor_web.ImportDetail",
    "monitor_web.AlertSolution",
    "monitor_web.CustomTSItem",
    "bkmonitor.Action",
    # 指标缓存
    "bkmonitor.MetricListCache",
    # 用户配置
    "monitor.UserConfig",
    "apm_web.UserVisitRecord",
]


# 表顺序保证（用于解决外键依赖关系）
# 数字越大，优先级越高
TABLE_PRIORITY_MAPPING: dict[str, int] = {
    # 插件采集
    "monitor_web.CollectConfigMeta": 1,
    "monitor_web.DeploymentConfigVersion": 2,
    "monitor_web.PluginVersionHistory": 3,
    "monitor_web.CollectorPluginConfig": 4,
    "monitor_web.CollectorPluginInfo": 4,
    # 自定义事件
    "monitor_web.CustomEventGroup": 2,
    "monitor_web.CustomEventItem": 1,
}


# 导出 SQL 过滤条件（按模型）
#
# 说明:
# - key 为 model_label（格式: app_label.ModelName）
# - value 为 WHERE 条件片段（不包含 WHERE 关键字），会直接拼接进导出 SQL
# - 仅用于导出阶段做数据过滤，不影响导入逻辑
#
# 示例:
# EXPORT_SQL_FILTER_MAPPING = {
#     "bkmonitor.ActionInstance": "is_deleted = 0",
#     "bkmonitor.Alert": "status != 'CLOSED'",
# }
EXPORT_SQL_FILTER_MAPPING: dict[str, str] = {
    "bkmonitor.Shield": "is_deleted = 0",
}

# =====================================================================
# 日志采集源配置
# =====================================================================
#
# 用于按业务归属筛选日志采集数据源（DataSource.type_label="log"）。
# 可按实际部署环境补充更多日志平台 app_code。
LOG_SOURCE_SYSTEMS: set[str] = {"bk_log_search"}


# =====================================================================
# 业务过滤与租户映射配置
# =====================================================================
#
# 处理逻辑：
# 1. 排除 EXCLUDED_BIZ_IDS 中指定的业务数据
# 2. 根据 BIZ_TENANT_ID_MAPPING 将特定业务数据归属到特定租户
# 3. 其他数据的 bk_tenant_id 替换为 DEFAULT_TARGET_TENANT_ID

# 默认目标租户ID
DEFAULT_TARGET_TENANT_ID: str = "tencent"

# 需要排除的业务ID集合
EXCLUDED_BIZ_IDS: set[int] = {2}

# 业务ID到租户ID的映射
BIZ_TENANT_ID_MAPPING: dict[int, str] = {
    19074: "grena",
}
