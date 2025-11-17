import ContainerSvg from '@/images/container-icons/Container.svg';
import NodeSvg from '@/images/container-icons/Node.svg';

/**
 * 采集项状态
 */
export const STATUS_ENUM = [
  {
    text: window.$t('部署中'),
    value: 'running',
    color: '#3A84FF',
    background: '#C5DBFF',
  },
  {
    text: window.$t('正常'),
    value: 'success',
    color: '#3FC06D',
    background: '#DAF6E5',
  },
  {
    text: window.$t('异常'),
    value: 'FAILED',
    color: '#EA3636',
    background: '#FFEBEB',
  },
  {
    text: window.$t('停用'),
    value: 'TERMINATED',
    color: '#979BA5',
    background: '#979ba529',
  },
];
/**
 * 全局日志分类
 */
export const GLOBAL_CATEGORIES_ENUM = [
  { text: window.$t('进程'), value: 'host_process' },
  { text: window.$t('操作系统'), value: 'os' },
  { text: window.$t('主机设备'), value: 'host_device' },
  { text: window.$t('Kubernetes'), value: 'kubernetes' },
  { text: window.$t('服务模块'), value: 'service_module' },
  { text: window.$t('业务应用'), value: 'application_check' },
  { text: window.$t('其他'), value: 'others' },
];
/**
 * 自定义日志分类
 */
export const CUSTOM_TYPE_ENUM = [
  { text: window.$t('日志上报'), value: 'log' },
  { text: window.$t('otlp_trace的上报方式'), value: 'otlp_trace' },
  { text: window.$t('otlp_log的上报方式'), value: 'otlp_log' },
];
/**
 * 日志采集场景
 */
export const COLLECTOR_SCENARIO_ENUM = [
  { value: 'row', text: window.$t('行日志文件') },
  { value: 'section', text: window.$t('段日志文件') },
  { value: 'win_event', text: window.$t('win event日志') },
  { value: 'custom', text: window.$t('自定义') },
  { value: 'redis_slowlog', text: window.$t('Redis慢日志') },
  { value: 'syslog', text: window.$t('Syslog Server') },
  { value: 'kafka', text: window.$t('KAFKA') },
];

/** 表格需要展示的字段 */
export const SETTING_FIELDS = [
  // 采集配置名称
  {
    id: 'collector_config_name',
    label: window.$t('采集名'),
    disabled: true,
  },
  // 用量展示
  {
    id: 'storage_usage',
    label: window.$t('日用量'),
    disabled: true,
  },
  {
    id: 'total_usage',
    label: window.$t('总用量'),
    disabled: true,
  },
  // 存储名
  {
    id: 'table_id',
    label: window.$t('存储名'),
  },
  // 存储名
  {
    id: 'index_set_id',
    label: window.$t('所属索引集'),
  },
  // 接入类型
  {
    id: 'category_name',
    label: window.$t('接入类型'),
  },
  // 日志类型
  {
    id: 'collector_scenario_name',
    label: window.$t('日志类型'),
  },
  // 集群名
  {
    id: 'storage_cluster_name',
    label: window.$t('集群名'),
  },
  // 过期时间
  {
    id: 'retention',
    label: window.$t('过期时间'),
  },
  {
    id: 'label',
    label: window.$t('标签'),
  },
  // 采集状态
  {
    id: 'es_host_state',
    label: window.$t('采集状态'),
  },
  // 更新人
  {
    id: 'updated_by',
    label: window.$t('更新人'),
  },
  // 更新时间
  {
    id: 'updated_at',
    label: window.$t('更新时间'),
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
    label: window.$t('清洗'),
    key: 'clean',
  },
  {
    label: window.$t('脱敏'),
    key: 'desensitization',
  },
  {
    label: window.$t('存储设置'),
    key: 'storage_setting',
  },
  {
    label: window.$t('克隆'),
    key: 'clone',
  },
  {
    label: window.$t('停用'),
    key: 'disable',
  },
  {
    label: window.$t('删除'),
    key: 'delete',
  },
  {
    label: window.$t('一键检测'),
    key: 'one_key_check',
  },
];

/**
 * 显示消息提示
 * @param message 消息内容
 * @param theme 主题类型
 */
export const showMessage = (message: string, theme: 'error' | 'success' | 'warning' = 'success'): void => {
  window.mainComponent?.$bkMessage({ message, theme });
};

// 常量定义
export const TARGET_TYPES = {
  TOPO: 'TOPO',
  INSTANCE: 'INSTANCE',
  SERVICE_TEMPLATE: 'SERVICE_TEMPLATE',
  SET_TEMPLATE: 'SET_TEMPLATE',
  DYNAMIC_GROUP: 'DYNAMIC_GROUP',
} as const;

export const collectTargetTarget = {
  // 已(动态)选择 静态主机 节点 服务模板 集群模板
  INSTANCE: '已选择{0}个静态主机',
  TOPO: '已动态选择{0}个节点',
  SERVICE_TEMPLATE: '已选择{0}个服务模板',
  SET_TEMPLATE: '已选择{0}个集群模板',
  DYNAMIC_GROUP: '已选择{0}个动态组',
};
/**
 * 日志种类
 */
export const LOG_SPECIES_LIST = [
  {
    id: 'Application',
    name: window.$t('应用程序(Application)'),
  },
  {
    id: 'Security',
    name: window.$t('安全(Security)'),
  },
  {
    id: 'System',
    name: window.$t('系统(System)'),
  },
  {
    id: 'Other',
    name: window.$t('其他'),
  },
];
/**
 * 日志类型
 */
export const LOG_TYPE_LIST = [
  { text: window.$t('行日志'), value: 'row' },
  { text: window.$t('段日志'), value: 'section' },
];

/**
 * 采集方式列表
 */
export const COLLECT_METHOD_LIST = [
  { id: 'container_log_config', img: ContainerSvg, name: window.$t('按 container 采集'), isDisable: false },
  { id: 'node_log_config', img: NodeSvg, name: window.$t('按 node 采集'), isDisable: false },
];

/** 操作符列表 */
export const OPERATOR_SELECT_LIST: ISelectItem[] = [
  {
    id: 'eq',
    name: window.$t('等于'),
  },
  {
    id: 'neq',
    name: window.$t('不等于'),
  },
  {
    id: 'include',
    name: window.$t('包含'),
  },
  {
    id: 'exclude',
    name: window.$t('不包含'),
  },
  {
    id: 'regex',
    name: window.$t('正则匹配'),
  },
  {
    id: 'nregex',
    name: window.$t('正则不匹配'),
  },
];
export interface ISelectItem {
  id: string;
  name: string;
  value?: string;
}

export interface ITableRowItem {
  fieldindex: string;
  word: string;
  op: string;
  tableIndex: number;
  logic_op?: logicOpType;
}

type logicOpType = 'and' | 'or';

export type btnType = 'match' | 'none' | 'separator';

/** 操作符列表 */
export const operatorSelectList: Array<ISelectItem> = [
  {
    id: 'eq',
    name: window.mainComponent.$t('等于'),
  },
  {
    id: 'neq',
    name: window.mainComponent.$t('不等于'),
  },
  {
    id: 'include',
    name: window.mainComponent.$t('包含'),
  },
  {
    id: 'exclude',
    name: window.mainComponent.$t('不包含'),
  },
  {
    id: 'regex',
    name: window.mainComponent.$t('正则匹配'),
  },
  {
    id: 'nregex',
    name: window.mainComponent.$t('正则不匹配'),
  },
];

/** 过滤类型 */
export const btnGroupList: Array<ISelectItem> = [
  {
    id: 'match',
    name: window.mainComponent.$t('字符串'),
  },
  {
    id: 'separator',
    name: window.mainComponent.$t('分隔符'),
  },
];

/** 操作符映射 */
export const operatorMapping = {
  '!=': 'neq',
};

export const tableRowBaseObj: ITableRowItem = {
  fieldindex: '',
  word: '',
  op: '=',
  tableIndex: 0,
};

export const operatorMappingObj = {
  eq: window.mainComponent.$t('等于'),
  neq: window.mainComponent.$t('不等于'),
  include: window.mainComponent.$t('包含'),
  exclude: window.mainComponent.$t('不包含'),
  regex: window.mainComponent.$t('正则匹配'),
  nregex: window.mainComponent.$t('正则不匹配'),
};
