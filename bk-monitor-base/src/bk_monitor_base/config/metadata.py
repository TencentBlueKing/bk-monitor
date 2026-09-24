from typing import Any, ClassVar

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from bk_monitor_base.config.base import BaseConfigSettings


class MetadataConfig(BaseConfigSettings):
    """
    metadata 配置
    """

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(validate_by_name=True)

    celery_queue: str = Field(default="", title="metadata任务队列", alias="METADATA_CELERY_QUEUE")

    use_old_model: bool = Field(default=True, title="是否使用旧模型", alias="METADATA_USE_OLD_MODEL")
    backend_database_name: str = Field(
        default="default", alias="METADATA_BACKEND_DATABASE_NAME", description="后台数据库名称"
    )
    aggregation_biz_id: int = Field(default=2, alias="METADATA_AGGREGATION_BIZ_ID", description="聚合网关默认业务ID")
    default_transfer_cluster_id: str = Field(
        default="default", alias="METADATA_DEFAULT_TRANSFER_CLUSTER_ID", description="默认transfer集群"
    )
    default_transfer_cluster_id_for_k8s: str = Field(
        default="default", alias="METADATA_DEFAULT_TRANSFER_CLUSTER_ID_FOR_K8S", description="默认transfer集群"
    )
    influxdb_default_proxy_cluster_name: str = Field(
        default="default",
        alias="METADATA_INFLUXDB_DEFAULT_PROXY_CLUSTER_NAME",
        description="influxdb proxy默认使用集群名",
    )
    influxdb_default_proxy_cluster_name_for_k8s: str = Field(
        default="default",
        alias="METADATA_INFLUXDB_DEFAULT_PROXY_CLUSTER_NAME_FOR_K8S",
        description="influxdb proxy给k8s默认使用集群名",
    )

    ts_data_saved_days: int = Field(default=30, alias="METADATA_TS_DATA_SAVED_DAYS", description="采集数据存储天数")
    time_series_metric_expired_seconds: int = Field(
        default=30 * 24 * 3600, alias="METADATA_TIME_SERIES_METRIC_EXPIRED_SECONDS", description="自定义指标过期时间"
    )

    # BCS相关配置
    bcs_api_gateway_host: str = Field(
        default="", alias="METADATA_BCS_API_GATEWAY_HOST", description="bcs api gateway host"
    )
    bcs_api_gateway_port: int = Field(
        default=443, alias="METADATA_BCS_API_GATEWAY_PORT", description="bcs api gateway port"
    )
    bcs_api_gateway_schema: str = Field(
        default="https", alias="METADATA_BCS_API_GATEWAY_SCHEMA", description="bcs api gateway schema"
    )
    bcs_api_gateway_token: str = Field(
        default="", alias="METADATA_BCS_API_GATEWAY_TOKEN", description="bcs api gateway token"
    )
    bcs_cluster_bk_env_label: str = Field(
        default="", alias="METADATA_BCS_CLUSTER_BK_ENV_LABEL", description="BCS集群配置来源标签"
    )
    bcs_custom_event_storage_cluster_id: str | None = Field(
        default=None, alias="METADATA_BCS_CUSTOM_EVENT_STORAGE_CLUSTER_ID", description="自定义上报存储集群ID"
    )
    bcs_data_convergence_config: dict[str, Any] = Field(
        default={"is_enabled": False, "k8s_metric_rt": "", "custom_metric_rt": ""},
        alias="METADATA_BCS_DATA_CONVERGENCE_CONFIG",
        description="BCS 数据合流配置",
    )
    bcs_kafka_storage_cluster_id: str | None = Field(
        default=None, alias="METADATA_BCS_KAFKA_STORAGE_CLUSTER_ID", description="BCS kafka 存储集群ID"
    )
    debugging_bcs_cluster_id_mapping_biz_id: str = Field(
        default="",
        alias="METADATA_DEBUGGING_BCS_CLUSTER_ID_MAPPING_BIZ_ID",
        description="仅用于测试联调环境映射特定集群到业务",
    )

    # 计算平台相关配置
    is_access_bk_data: bool = Field(default=False, alias="METADATA_IS_ACCESS_BK_DATA", description="是否接入计算平台")
    default_bkdata_biz_id: int = Field(
        default=2, alias="METADATA_DEFAULT_BKDATA_BIZ_ID", description="接入计算平台使用的业务"
    )
    bk_data_bk_biz_id: int = Field(
        default=2, alias="METADATA_BK_DATA_BK_BIZ_ID", description="监控在计算平台使用的公共业务ID"
    )
    bk_data_flow_cluster_group: str = Field(
        default="default_inland",
        alias="METADATA_BK_DATA_FLOW_CLUSTER_GROUP",
        description="计算平台 dataflow 计算集群组",
    )
    bk_data_kafka_broker_url: str = Field(
        default="", alias="METADATA_BK_DATA_KAFKA_BROKER_URL", description="与计算平台对接的消息队列BROKER地址"
    )
    bk_data_project_id: int = Field(
        default=1, alias="METADATA_BK_DATA_PROJECT_ID", description="监控在计算平台使用的公共项目ID"
    )
    bk_data_project_maintainer: str = Field(
        default="admin", alias="METADATA_BK_DATA_PROJECT_MAINTAINER", description="计算平台项目的维护人员"
    )
    bk_data_record_rule_project_id: int = Field(
        default=1,
        alias="METADATA_BK_DATA_RECORD_RULE_PROJECT_ID",
        description="监控使用计算平台的预计算流程的公共项目ID",
    )
    bk_data_rt_id_prefix: str = Field(
        default="community", alias="METADATA_BK_DATA_RT_ID_PREFIX", description="监控在计算平台的数据表前缀"
    )
    enable_v2_vm_data_link: bool = Field(
        default=True, alias="METADATA_ENABLE_V2_VM_DATA_LINK", description="是否启用新版的数据链路"
    )
    default_vm_data_link_namespace: str = Field(
        default="bkmonitor", alias="METADATA_DEFAULT_VM_DATA_LINK_NAMESPACE", description="创建vm链路资源所属的命名空间"
    )
    enable_sync_bkbase_metadata_to_db: bool = Field(
        default=False, alias="METADATA_ENABLE_SYNC_BKBASE_METADATA_TO_DB", description="是否同步bkbase元数据至DB"
    )
    enable_sync_bkbase_meta_task: bool = Field(
        default=False, alias="METADATA_ENABLE_SYNC_BKBASE_META_TASK", description="是否同步bkbase元数据至DB"
    )

    sync_bkbase_meta_biz_batch_size: int = Field(
        default=10,
        alias="METADATA_SYNC_BKBASE_META_BIZ_BATCH_SIZE",
        description="同步计算平台RT元信息时的单轮拉取业务ID个数",
    )
    sync_bkbase_meta_black_biz_id_list: list[str] = Field(
        default_factory=list,
        alias="METADATA_SYNC_BKBASE_META_BLACK_BIZ_ID_LIST",
        description="同步计算平台RT元信息时的黑名单业务ID列表",
    )
    sync_bkbase_meta_supported_storage_types: list[str] = Field(
        default_factory=lambda: ["mysql", "tspider", "hdfs"],
        alias="METADATA_SYNC_BKBASE_META_SUPPORTED_STORAGE_TYPES",
        description="同步计算平台RT元信息时支持的存储类型",
    )

    bk_data_realtime_node_wait_time: int = Field(
        default=10, alias="METADATA_BK_DATA_REALTIME_NODE_WAIT_TIME", description="计算平台实时节点等待时间(秒)"
    )
    bk_data_data_expires_days: int = Field(
        default=30, alias="METADATA_BK_DATA_DATA_EXPIRES_DAYS", description="计算平台中结果表(MYSQL)默认保存天数"
    )
    bk_data_mysql_storage_cluster_name: str = Field(
        default="mysql-default",
        alias="METADATA_BK_DATA_MYSQL_STORAGE_CLUSTER_NAME",
        description="计算平台MYSQL存储集群名称",
    )
    bk_data_mysql_storage_cluster_type: str = Field(
        default="mysql_storage",
        alias="METADATA_BK_DATA_MYSQL_STORAGE_CLUSTER_TYPE",
        description="计算平台MYSQL类存储类型",
    )
    bk_data_druid_storage_cluster_name: str = Field(
        default="", alias="METADATA_BK_DATA_DRUID_STORAGE_CLUSTER_NAME", description="计算平台Druid存储集群名称"
    )
    bk_data_hdfs_storage_cluster_name: str = Field(
        default="hdfs-default",
        alias="METADATA_BK_DATA_HDFS_STORAGE_CLUSTER_NAME",
        description="计算平台HDFS存储集群名称",
    )

    # bkbase redis
    bkbase_redis_host: str = Field(default="", alias="METADATA_BKBASE_REDIS_HOST", description="bkbase redis host")
    bkbase_redis_password: str = Field(
        default="", alias="METADATA_BKBASE_REDIS_PASSWORD", description="bkbase redis password"
    )
    bkbase_redis_port: str = Field(default="", alias="METADATA_BKBASE_REDIS_PORT", description="bkbase redis port")
    bkbase_redis_lock_name: str = Field(
        default="watch_bkbase_meta_redis_lock",
        alias="METADATA_BKBASE_REDIS_LOCK_NAME",
        description="计算平台Redis锁名称",
    )
    enable_v4_event_group_data_link: bool = Field(
        default=False, alias="METADATA_ENABLE_V4_EVENT_GROUP_DATA_LINK", description="是否启用事件组V4数据链路"
    )
    bkbase_redis_pattern: str = Field(
        default="databus_v4_dataid", alias="METADATA_BKBASE_REDIS_PATTERN", description="计算平台Redis监听模式"
    )
    bkbase_redis_reconnect_interval_seconds: int = Field(
        default=2, alias="METADATA_BKBASE_REDIS_RECONNECT_INTERVAL_SECONDS", description="计算平台Redis重连间隔(秒)"
    )
    bkbase_redis_scan_count: int = Field(
        default=1000, alias="METADATA_BKBASE_REDIS_SCAN_COUNT", description="计算平台Redis单次SCAN数量"
    )
    bkbase_redis_task_max_execution_time_seconds: int = Field(
        default=600,
        alias="METADATA_BKBASE_REDIS_TASK_MAX_EXECUTION_TIME_SECONDS",
        description="计算平台Redis任务最大执行时间(秒)",
    )
    bkbase_redis_watch_lock_expire_seconds: int = Field(
        default=60, alias="METADATA_BKBASE_REDIS_WATCH_LOCK_EXPIRE_SECONDS", description="Redis Watch锁过期时间(秒)"
    )
    bkbase_redis_watch_lock_renewal_interval_seconds: int = Field(
        default=15,
        alias="METADATA_BKBASE_REDIS_WATCH_LOCK_RENEWAL_INTERVAL_SECONDS",
        description="Redis Watch锁续约间隔(秒)",
    )

    # 自定义上报相关配置
    is_auto_deploy_custom_report_server: bool = Field(
        default=True, alias="METADATA_IS_AUTO_DEPLOY_CUSTOM_REPORT_SERVER", description="是否自动部署自定义上报服务"
    )
    custom_report_default_proxy_ip: list[str] = Field(
        default_factory=list, alias="METADATA_CUSTOM_REPORT_DEFAULT_PROXY_IP", description="自定义上报默认服务器"
    )
    custom_report_default_deploy_cluster: list[int] = Field(
        default_factory=list,
        alias="METADATA_CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER",
        description="自定义上报默认部署K8S集群",
    )

    # V4链路分业务系统事件初始化配置
    enable_plugin_access_v4_data_link: bool = Field(
        default=False, alias="METADATA_ENABLE_PLUGIN_ACCESS_V4_DATA_LINK", description="插件数据是否启用接入V4链路"
    )
    system_event_default_es_index_replicas: int = Field(
        default=0, alias="METADATA_SYSTEM_EVENT_DEFAULT_ES_INDEX_REPLICAS", description="系统事件默认ES索引副本数"
    )
    system_event_default_es_index_shards: int = Field(
        default=1, alias="METADATA_SYSTEM_EVENT_DEFAULT_ES_INDEX_SHARDS", description="系统事件默认ES索引分片数"
    )

    # GSE消息槽
    gse_slot_id: int = Field(default=0, alias="METADATA_GSE_SLOT_ID", description="GSE消息槽ID")
    gse_slot_token: int = Field(default=0, alias="METADATA_GSE_SLOT_TOKEN", description="GSE消息槽TOKEN")
    is_assign_dataid_by_gse: bool = Field(
        default=True, alias="METADATA_IS_ASSIGN_DATAID_BY_GSE", description="是否通过GSE分配DATAID"
    )

    # ES生命周期管理
    es_index_rotation_sleep_interval_seconds: int = Field(
        default=3, alias="METADATA_ES_INDEX_ROTATION_SLEEP_INTERVAL_SECONDS", description="ES索引轮转等待间隔(秒)"
    )
    es_retain_invalid_alias: bool = Field(
        default=True, alias="METADATA_ES_RETAIN_INVALID_ALIAS", description="当 ES 存在不合法别名时，是否保留该索引"
    )
    es_storage_offset_hours: int = Field(
        default=8, alias="METADATA_ES_STORAGE_OFFSET_HOURS", description="ES采集项整体时间偏移量"
    )

    # DJANGO_REDIS 相关配置
    django_redis_host: str = Field(default="", alias="METADATA_DJANGO_REDIS_HOST", description="django redis host")
    django_redis_port: int = Field(default=6379, alias="METADATA_DJANGO_REDIS_PORT", description="django redis port")
    django_redis_password: str = Field(
        default="", alias="METADATA_DJANGO_REDIS_PASSWORD", description="django redis password"
    )
    django_redis_db: int = Field(default=0, alias="METADATA_DJANGO_REDIS_DB", description="django redis db")

    # kafka 采样接口相关配置
    kafka_tail_api_retry_times: int = Field(
        default=3, alias="METADATA_KAFKA_TAIL_API_RETRY_TIMES", description="Kafka采样接口重试次数"
    )
    kafka_tail_api_retry_interval_seconds: int = Field(
        default=2, alias="METADATA_KAFKA_TAIL_API_RETRY_INTERVAL_SECONDS", description="Kafka采样接口超时时间(秒)"
    )
    kafka_tail_api_timeout_seconds: int = Field(
        default=1000, alias="METADATA_KAFKA_TAIL_API_TIMEOUT_SECONDS", description="Kafka采样接口Consumer超时时间(秒)"
    )

    # 空间与数据源相关配置
    access_dbm_rt_space_uid: list[str] = Field(
        default_factory=list, alias="METADATA_ACCESS_DBM_RT_SPACE_UID", description="访问 dbm 结果表的空间 UID"
    )
    always_running_fake_bcs_cluster_id_list: list[str] = Field(
        default_factory=list,
        alias="METADATA_ALWAYS_RUNNING_FAKE_BCS_CLUSTER_ID_LIST",
        description="特殊的可以不被禁用的BCS集群ID",
    )
    bkci_space_access_plugin_list: list[str] = Field(
        default_factory=list, alias="METADATA_BKCI_SPACE_ACCESS_PLUGIN_LIST", description="蓝盾空间允许访问的插件列表"
    )
    bkpaas_authorized_data_id_list: list[int] = Field(
        default_factory=list,
        alias="METADATA_BKPAAS_AUTHORIZED_DATA_ID_LIST",
        description="需要授权的 PaaS 创建的数据源 ID",
    )
    builtin_data_rt_redis_key: str = Field(
        default="bkmonitorv3:spaces:built_in_result_table_detail",
        alias="METADATA_BUILTIN_DATA_RT_REDIS_KEY",
        description="监控内置可观测数据上报Redis Key",
    )

    # 存储集群相关配置
    default_kafka_storage_cluster_id: int | None = Field(
        default=None, alias="METADATA_DEFAULT_KAFKA_STORAGE_CLUSTER_ID", description="默认 kafka 存储集群ID"
    )
    transfer_builtin_cluster_id: str = Field(
        default="", alias="METADATA_TRANSFER_BUILTIN_CLUSTER_ID", description="Transfer内置的集群ID"
    )

    # 功能开关相关配置
    enable_consul_lite_mode: bool = Field(
        default=False, alias="METADATA_ENABLE_CONSUL_LITE_MODE", description="是否开启Consul Lite模式"
    )
    enable_custom_event_sleep: bool = Field(
        default=False, alias="METADATA_ENABLE_CUSTOM_EVENT_SLEEP", description="是否开启自定义事件休眠"
    )
    enable_direct_area_ping_collect: bool = Field(
        default=True, alias="METADATA_ENABLE_DIRECT_AREA_PING_COLLECT", description="是否开启直连区域的PING采集"
    )
    enable_influxdb_storage: bool = Field(
        default=True, alias="METADATA_ENABLE_INFLUXDB_STORAGE", description="是否启用influxdb"
    )
    enable_ping_alarm: bool = Field(default=True, alias="METADATA_ENABLE_PING_ALARM", description="全局 Ping 告警开关")
    enable_space_builtin_data_link: bool = Field(
        default=False, alias="METADATA_ENABLE_SPACE_BUILTIN_DATA_LINK", description="是否开启空间内置数据链路初始化"
    )

    # 指标相关配置
    fetch_time_series_metric_interval_seconds: int = Field(
        default=7200, alias="METADATA_FETCH_TIME_SERIES_METRIC_INTERVAL_SECONDS", description="获取自定义指标的间隔时间"
    )
    max_metrics_fetch_step: int = Field(
        default=500, alias="METADATA_MAX_METRICS_FETCH_STEP", description="自定义指标拉取最大步长"
    )
    metrics_key_prefix: str = Field(
        default="bkmonitor:metrics_:", alias="METADATA_METRICS_KEY_PREFIX", description="指标Redis键前缀"
    )
    metric_dimensions_key_prefix: str = Field(
        default="bkmonitor:metric_dimensions_",
        alias="METADATA_METRIC_DIMENSIONS_KEY_PREFIX",
        description="指标维度Redis键前缀",
    )

    # 数据源与权限相关配置
    is_restrict_ds_belong_space: bool = Field(
        default=False, alias="METADATA_IS_RESTRICT_DS_BELONG_SPACE", description="是否限制数据源归属具体空间"
    )

    # ES请求相关配置
    metadata_request_es_timeout: dict[str, Any] = Field(
        default_factory=dict, alias="METADATA_METADATA_REQUEST_ES_TIMEOUT", description="metadata请求ES超时时间"
    )
    metadata_request_es_timeout_seconds: int = Field(
        default=10, alias="METADATA_METADATA_REQUEST_ES_TIMEOUT_SECONDS", description="Metadata轮转任务请求ES超时时间"
    )

    # CONSUL配置
    consul_client_host: str = Field(
        default="localhost", alias="METADATA_CONSUL_CLIENT_HOST", description="consul客户端host"
    )
    consul_client_port: int = Field(default=8500, alias="METADATA_CONSUL_CLIENT_PORT", description="consul客户端port")
    consul_https_port: int = Field(default=0, alias="METADATA_CONSUL_HTTPS_PORT", description="consul客户端https port")
    consul_client_cert_file: str | None = Field(
        default=None, alias="METADATA_CONSUL_CLIENT_CERT_FILE", description="consul客户端证书文件路径"
    )
    consul_client_key_file: str | None = Field(
        default=None, alias="METADATA_CONSUL_CLIENT_KEY_FILE", description="consul客户端密钥文件路径"
    )
    consul_server_ca_cert: str | None = Field(
        default=None, alias="METADATA_CONSUL_SERVER_CA_CERT", description="consul服务端CA证书文件路径"
    )
    # VM与存储相关配置
    single_vm_space_id_list: list[str] = Field(
        default_factory=list, alias="METADATA_SINGLE_VM_SPACE_ID_LIST", description="使用独立VM集群的空间ID列表"
    )
    skip_influxdb_table_id_list: list[str] = Field(
        default_factory=list, alias="METADATA_SKIP_INFLUXDB_TABLE_ID_LIST", description="跳过写入influxdb的结果表列表"
    )
    special_rt_route_alias_result_table_list: list[str] = Field(
        default_factory=list,
        alias="METADATA_SPECIAL_RT_ROUTE_ALIAS_RESULT_TABLE_LIST",
        description="使用RT中的路由过滤别名的结果表列表",
    )

    host_disable_monitor_states: list[str] = Field(
        default_factory=lambda: ["备用机", "测试中", "故障中"],
        alias="METADATA_HOST_DISABLE_MONITOR_STATES",
        description="不监控的主机状态列表",
    )

    specify_aes_key: str = Field(default="", alias="METADATA_SPECIFY_AES_KEY", description="特别指定的AES使用密钥")
    bk_data_token_salt: str = Field(default="bk", alias="METADATA_BK_DATA_TOKEN_SALT", description="bk data token salt")
    bk_data_aes_iv: str = Field(
        default="bkbkbkbkbkbkbkbk", alias="METADATA_BK_DATA_AES_IV", description="bkdata aes iv"
    )

    max_task_process_num: int = Field(
        default=1, alias="METADATA_MAX_TASK_PROCESS_NUM", description="后台任务多进程并行数量"
    )
    es_cluster_blacklist: list[int] = Field(
        default_factory=list, alias="METADATA_ES_CLUSTER_BLACKLIST", description="ES集群黑名单列表"
    )

    custom_report_k8s_secrets_config: dict[str, Any] = Field(
        default_factory=dict,
        alias="METADATA_CUSTOM_REPORT_K8S_SECRETS_CONFIG",
        description="自定义上报K8S集群中 Secrets 分配逻辑",
    )

    k8s_operator_deploy_namespace: dict[str, Any] = Field(
        default_factory=dict,
        alias="METADATA_K8S_OPERATOR_DEPLOY_NAMESPACE",
        description="bkmonitor-operator 特殊集群部署命名空间信息",
    )

    enable_ts_metric_filter_by_is_active: bool = Field(
        default=False,
        alias="METADATA_ENABLE_TS_METRIC_FILTER_BY_IS_ACTIVE",
        description="是否根据is_active过滤自定义指标",
    )

    sync_bkbase_cluster_info_update: bool = Field(
        default=False,
        alias="METADATA_SYNC_BKBASE_CLUSTERINFO_UPDATE",
        description="在同步bkbase集群信息时，是否进行更新",
    )
    enable_uptimecheck_bkdata: bool = Field(
        default=True,
        alias="METADATA_ENABLE_UPTIME_CHECK_BKDATA",
        description="是否让拨测默认接入独立 BKData 链路，默认开启",
    )
