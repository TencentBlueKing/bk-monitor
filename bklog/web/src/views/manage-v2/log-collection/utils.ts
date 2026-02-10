import { formatFileSize, random } from '@/common/util';
import type {
  CollectOperateType,
  ICollectListRowData,
  ITableRowItem,
  ISelectItem,
  ILabelSelectorArrayItem,
} from './type';
/**
 * 采集项状态
 */
export const STATUS_ENUM = [
  {
    label: window.$t('部署中'),
    value: 'RUNNING',
    color: '#3A84FF',
    background: '#C5DBFF',
  },
  {
    label: window.$t('部署中'),
    value: 'UNKNOWN',
    color: '#3A84FF',
    background: '#C5DBFF',
  },
  {
    label: window.$t('部署中'),
    value: 'PREPARE',
    color: '#3A84FF',
    background: '#C5DBFF',
  },
  {
    label: window.$t('正常'),
    value: 'SUCCESS',
    color: '#3FC06D',
    background: '#DAF6E5',
  },
  {
    label: window.$t('异常'),
    value: 'FAILED',
    color: '#EA3636',
    background: '#FFEBEB',
  },
  {
    label: window.$t('停用'),
    value: 'TERMINATED',
    color: '#979BA5',
    background: '#979ba529',
  },
];
export const STATUS_ENUM_FILTER = [
  {
    label: window.$t('部署中'),
    value: 'running',
  },
  {
    label: window.$t('正常'),
    value: 'success',
  },
  {
    label: window.$t('异常'),
    value: 'failed',
  },
  {
    label: window.$t('停用'),
    value: 'terminated',
  },
];
/**
 * 全局日志分类
 */
export const GLOBAL_CATEGORIES_ENUM = [
  { label: window.$t('主机日志'), value: 'linux' },
  { label: window.$t('Windows Event 日志'), value: 'winevent' },
  { label: window.$t('容器文件采集'), value: 'container_file' },
  { label: window.$t('容器标准输出'), value: 'container_stdout' },
  { label: window.$t('计算平台'), value: 'bkdata' },
  { label: window.$t('第三方ES'), value: 'es' },
  { label: window.$t('自定义上报'), value: 'custom_report' },
];
/**
 * 自定义日志分类
 */
export const CUSTOM_TYPE_ENUM = [
  { label: window.$t('日志上报'), value: 'log' },
  { label: window.$t('otlp_trace的上报方式'), value: 'otlp_trace' },
  { label: window.$t('otlp_log的上报方式'), value: 'otlp_log' },
];
/**
 * 日志采集场景
 */
export const COLLECTOR_SCENARIO_ENUM = [
  { value: 'row', label: window.$t('行日志文件') },
  { value: 'section', label: window.$t('段日志文件') },
  { value: 'win_event', label: window.$t('win event日志') },
  { value: 'custom', label: window.$t('自定义') },
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
    disabled: true,
  },
  // 接入类型
  {
    id: 'log_access_type',
    label: window.$t('接入类型'),
    disabled: true,
  },
  // 日志类型
  {
    id: 'collector_scenario_id',
    label: window.$t('日志类型'),
    disabled: true,
  },
  // 集群名
  {
    id: 'storage_display_name',
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
    disabled: true,
  },
  // 创建人
  {
    id: 'created_by',
    label: window.$t('创建人'),
    disabled: true,
  },
  // 更新时间
  {
    id: 'created_at',
    label: window.$t('创建时间'),
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
  // {
  //   label: window.$t('脱敏'),
  //   key: 'desensitization',
  // },
  {
    label: window.$t('存储设置'),
    key: 'storage',
  },
  {
    label: window.$t('克隆'),
    key: 'clone',
  },
  {
    label: window.$t('停用'),
    key: 'stop',
  },
  {
    label: window.$t('启用'),
    key: 'start',
  },
  {
    label: window.$t('删除'),
    key: 'delete',
  },
  // {
  //   label: window.$t('一键检测'),
  //   key: 'one_key_check',
  // },
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
  { id: 'container_log_config', icon: 'container', name: window.$t('按 container 采集'), isDisable: false },
  { id: 'node_log_config', icon: 'node', name: window.$t('按 node 采集'), isDisable: false },
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
/**
 * 可见范围单选列表
 */

export const visibleScopeSelectList = [
  { id: 'current_biz', name: window.mainComponent.$t('当前空间可见') },
  { id: 'multi_biz', name: window.mainComponent.$t('多空间选择') },
  { id: 'all_biz', name: window.mainComponent.$t('全平台') },
];

/**
 * 格式化字节大小为可读字符串。
 *
 * @param {number|undefined} size - 需要格式化的字节大小。
 *
 * @returns {string} 格式化后的文件大小字符串，或默认字符串 `'--'`。
 */
export function formatBytes(size) {
  if (size === undefined) {
    return '--';
  }
  if (size === 0) {
    return '0';
  }
  return formatFileSize(size, true);
}
/**
 * 表格各操作项是否可以点击
 * @param row
 * @param operateType
 * @returns
 */
export const getOperatorCanClick = (row: ICollectListRowData, operateType: CollectOperateType) => {
  const status = row.status?.toLowerCase();
  const isTerminated = status === 'terminated';
  const isSuccess = status === 'success';
  const isFailed = status === 'failed';
  const isCompleted = row.storage_cluster_id !== -1; // 采集项已完成：storage_cluster_id 存在

  switch (operateType) {
    case 'search':
      // 检索 - 判定 is_search 字段
      return !!(row.is_search as boolean);
    case 'edit':
      // 编辑 - 采集状态不为"停用"
      return !isTerminated;
    case 'clean':
      // 清洗 - 采集状态不为"停用"
      return !isTerminated;
    case 'storage':
      // 存储设置 - 采集项已完成且采集状态不为"停用"
      return isCompleted && !isTerminated;
    case 'clone':
      // 克隆 - 无限制条件
      return true;
    case 'stop':
      // 停用 - 采集状态为"正常"或"异常"
      return isSuccess || isFailed;
    case 'start':
      // 启用 - 采集状态为"停用"
      return isTerminated;
    case 'delete':
      // 删除 - 采集状态为"停用"
      return isTerminated;
    default:
      return true;
  }
};

export const getLabelSelectorArray = (
  selector: Record<string, Array<Record<string, unknown>>>,
): ILabelSelectorArrayItem[] => {
  return Object.entries(selector).reduce<ILabelSelectorArrayItem[]>((pre, [labelKey, labelVal]) => {
    pre.push(...labelVal.map(item => ({ ...item, id: random(10), type: labelKey })));
    return pre;
  }, []);
};

export const getContainerNameList = (containerName = '') => {
  const splitList = containerName.split(',');
  if (splitList.length === 1 && splitList[0] === '') return [];
  return splitList;
};

/**
 * 处理exclude_files，完成格式转换+空值过滤
 * @param {Array} excludeFiles 原始exclude_files值（对象数组/字符串数组）
 * @returns {Array<string>} 标准化后的非空字符串数组
 */
export const formatExcludeFiles = excludeFiles => {
  // 1. 容错处理：非数组/空数组直接返回空数组
  if (!Array.isArray(excludeFiles) || excludeFiles.length === 0) {
    return [];
  }

  const resultArr = [];
  // 2. 遍历数组，区分「对象项」和「字符串项」
  excludeFiles.forEach(item => {
    // 情况A：元素是对象，且包含value属性 → 提取value
    if (typeof item === 'object' && item !== null && 'value' in item) {
      const val = item.value;
      // 过滤空值：仅保留非空的字符串
      if (val && typeof val === 'string') {
        resultArr.push(val);
      }
    } else if (typeof item === 'string') {
      // 情况B：元素是字符串 → 直接保留（已符合格式）
      resultArr.push(item);
    }
  });

  return resultArr;
};
