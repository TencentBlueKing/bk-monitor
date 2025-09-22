export const STATUS_ENUM = [
  {
    text: window.$t("部署中"),
    value: "running",
    color: "#3A84FF",
    background: "#C5DBFF",
  },
  {
    text: window.$t("正常"),
    value: "success",
    color: "#3FC06D",
    background: "#DAF6E5",
  },
  {
    text: window.$t("异常"),
    value: "FAILED",
    color: "#EA3636",
    background: "#FFEBEB",
  },
  {
    text: window.$t("停用"),
    value: "TERMINATED",
    color: "#979BA5",
    background: "#979ba529",
  },
];
/**
 * 全局日志分类
 */
export const GLOBAL_CATEGORIES_ENUM = [
  { text: window.$t("进程"), value: "host_process" },
  { text: window.$t("操作系统"), value: "os" },
  { text: window.$t("主机设备"), value: "host_device" },
  { text: window.$t("Kubernetes"), value: "kubernetes" },
  { text: window.$t("服务模块"), value: "service_module" },
  { text: window.$t("业务应用"), value: "application_check" },
  { text: window.$t("其他"), value: "others" },
];
/**
 * 自定义日志分类
 */
export const CUSTOM_TYPE_ENUM = [
  { text: window.$t("日志上报"), value: "log" },
  { text: window.$t("otlp_trace的上报方式"), value: "otlp_trace" },
  { text: window.$t("otlp_log的上报方式"), value: "otlp_log" },
];
/**
 * 日志采集场景
 */
export const COLLECTOR_SCENARIO_ENUM = [
  { value: "row", text: window.$t("行日志文件") },
  { value: "section", text: window.$t("段日志文件") },
  { value: "win_event", text: window.$t("win event日志") },
  { value: "custom", text: window.$t("自定义") },
  { value: "redis_slowlog", text: window.$t("Redis慢日志") },
  { value: "syslog", text: window.$t("Syslog Server") },
  { value: "kafka", text: window.$t("KAFKA") },
];

/** 表格需要展示的字段 */
export const SETTING_FIELDS = [
  // 采集配置名称
  {
    id: "collector_config_name",
    label: window.$t("采集名"),
    disabled: true,
  },
  // 用量展示
  {
    id: "storage_usage",
    label: window.$t("日用量"),
    disabled: true,
  },
  {
    id: "total_usage",
    label: window.$t("总用量"),
    disabled: true,
  },
  // 存储名
  {
    id: "table_id",
    label: window.$t("存储名"),
  },
  // 存储名
  {
    id: "index_set_id",
    label: window.$t("所属索引集"),
  },
  // 接入类型
  {
    id: "category_name",
    label: window.$t("接入类型"),
  },
  // 日志类型
  {
    id: "collector_scenario_name",
    label: window.$t("日志类型"),
  },
  // 集群名
  {
    id: "storage_cluster_name",
    label: window.$t("集群名"),
  },
  // 过期时间
  {
    id: "retention",
    label: window.$t("过期时间"),
  },
  {
    id: "label",
    label: window.$t("标签"),
  },
  // 采集状态
  {
    id: "es_host_state",
    label: window.$t("采集状态"),
  },
  // 更新人
  {
    id: "updated_by",
    label: window.$t("更新人"),
  },
  // 更新时间
  {
    id: "updated_at",
    label: window.$t("更新时间"),
  },
];

/**
 *  表格操作列【操作】，默认只外放：检索、编辑
    - 日志采集 / 更多：清洗、脱敏、存储设置、克隆、停用、删除、一键检测
    - 计算平台 / 更多：脱敏、删除
    - 第三方 ES / 更多：脱敏、删除
    - 自定义上报的 / 更多：清洗、脱敏、停用、删除
 */
export const MENU_LIST = [
  {
    label: window.$t("清洗"),
    key: "clean",
  },
  {
    label: window.$t("脱敏"),
    key: "desensitization",
  },
  {
    label: window.$t("存储设置"),
    key: "storage_setting",
  },
  {
    label: window.$t("克隆"),
    key: "clone",
  },
  {
    label: window.$t("停用"),
    key: "disable",
  },
  {
    label: window.$t("删除"),
    key: "delete",
  },
  {
    label: window.$t("一键检测"),
    key: "one_key_check",
  },
];
