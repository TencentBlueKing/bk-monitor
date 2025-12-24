export interface IListItemData {
  index_set_id?: string;
  index_set_name?: string;
  index_count?: number;
  icon?: string;
  unEditable?: boolean;
  [key: string]: unknown;
}

/**
 * ========= manage-v2/log-collection 通用类型（hooks/components 复用）=========
 */

/**
 * 卡片配置项（用于分类卡片渲染）
 * - `renderFn/subTitle` 在 Vue JSX 中返回 VNode/JSX 均可，因此用 `unknown` 做兼容，
 *   由具体渲染层（TSX/JSX）自行约束为 `JSX.Element`/`VNodeChild`。
 */
export interface ICardItem {
  /** 卡片唯一标识 */
  key: number | string;
  /** 卡片标题 */
  title: string;
  /** 卡片内容渲染函数 */
  renderFn: () => unknown;
  /** 卡片副标题渲染函数（可选） */
  subTitle?: () => unknown;
}

/** 通用请求参数结构 */
export type IRequestParams = Record<string, unknown>;

/**
 * 通用 API 响应结构
 * - 业务侧经常还会返回 message/code 等字段，因此保留索引签名兜底
 */
export interface IApiResponse<T = unknown> {
  data?: T;
  [key: string]: unknown;
}

/** 结果表字段信息（按页面真实使用字段收敛，其它字段通过索引签名兜底） */
export interface IFieldInfo {
  field_name?: string;
  field_type?: string;
  [key: string]: unknown;
}

/** 结果表信息响应结构（仅收敛 useOperation 里用到的 fields） */
export interface IResultTableInfoResponse extends IApiResponse<{ fields?: IFieldInfo[]; [key: string]: unknown }> {}

/** 索引组列表响应结构 */
export interface IIndexGroupListResponse {
  list?: unknown[];
  total?: number;
  [key: string]: unknown;
}

/** 带权限映射的对象结构（permission[actionId] === true/false） */
export interface IPermissionItem {
  permission?: Record<string, boolean | undefined>;
  [key: string]: unknown;
}

export interface INoQuestParams {
  letterIndex?: number;
  scopeSelectShow?: {
    namespace?: boolean;
    label?: boolean;
    load?: boolean;
    containerName?: boolean;
    annotation?: boolean;
  };
  namespaceStr?: string;
  namespacesExclude?: string;
  containerExclude?: string;
}

export interface ISelectItem {
  id: string;
  name: string;
  value?: string;
}

// 用于描述路径项结构（含value字段的对象）
export interface IPathItem {
  value?: string;
}

// 用于描述分隔符过滤条件结构
export interface ISeparatorFilter {
  fieldindex?: string;
  word?: string;
  op?: string;
  logic_op?: string;
}

// 用于描述过滤条件结构
export interface IConditions {
  type?: string; // 可选值: 'none' | 'match' | 'separator'
  match_type?: string; // 可选值: 'include' | 'exclude'
  match_content?: string;
  separator?: string;
  separator_filters?: ISeparatorFilter[];
}

// 配置参数结构
export interface ICollectionParams {
  multiline_pattern?: string;
  multiline_max_lines?: string;
  multiline_timeout?: string;
  paths?: IPathItem[];
  exclude_files?: string[];
  extra_labels?: IValueItem[];
  conditions?: IConditions;
  winlog_name?: string[];
  winlog_level?: string[];
  winlog_event_id?: string[];
}

export interface IValueItem {
  id: string;
  key: string;
  operator: string;
  value: string;
  type?: string;
}
// 标签选择器结构
export interface ILabelSelector {
  match_labels?: IValueItem[];
  match_expressions?: IValueItem[];
}

// 注解选择器结构
export interface IAnnotationSelector {
  match_annotations?: IValueItem[];
}

// 容器配置项结构
export interface IContainerConfigItem {
  container?: {
    workload_type?: string;
    workload_name?: string;
    container_name?: string;
  };
  typeList?: Array<{ id: string; name: string }>;
  label_selector?: ILabelSelector;
  labelSelector?: ILabelSelector[];
  annotationSelector?: IAnnotationSelector[];
  containerNameList: string[];
  match_labels?: IValueItem[];
  extra_labels: IValueItem[];
  match_expressions?: IValueItem[];
  data_encoding?: string;
  params?: ICollectionParams;
  collector_type?: string;
  namespaces?: string[];
  annotation_selector?: IAnnotationSelector;
  noQuestParams: INoQuestParams;
}
/**
 * 目标节点信息
 * 描述一个在拓扑结构中的节点
 */
export interface ITargetNode {
  bk_inst_id: number;
  bk_obj_id: string;
}

// 完整数据结构接口（所有字段均为可选）
export interface IFormData {
  // 基础表单数据
  target_node_type?: string;
  data_link_id?: string;
  collector_config_name?: string;
  collector_config_name_en?: string;
  bk_biz_id?: number;
  description?: string;
  target_nodes?: ITargetNode[];
  category_id?: string;
  collector_scenario_id?: string;
  environment?: string;
  target_object_type?: string;
  data_encoding?: string;
  parent_index_set_ids?: number[];

  // 容器采集配置
  bcs_cluster_id?: string;
  add_pod_label?: boolean;
  add_pod_annotation?: boolean;
  extra_labels?: IValueItem[];
  configs?: IContainerConfigItem[];
  yaml_config?: string;
  yaml_config_enabled?: boolean;
  // 采集配置
  params?: ICollectionParams;
}

export interface IClusterItem {
  id: string;
  name: string;
  is_shared?: boolean;
}

/**
 * 采集项列表行数据（manage-v2/log-collection 列表页使用）
 * - 字段按页面/Hook 真实使用收敛，未覆盖字段通过索引签名兜底
 */
export interface ICollectListPermissionMap {
  [actionId: string]: boolean | undefined;
}

export type CollectTypeKey =
  | 'linux'
  | 'winevent'
  | 'container_file'
  | 'container_stdout'
  | 'bkdata'
  | 'es'
  | 'custom_report'
  | string;

export type CollectOperateType =
  | 'add'
  | 'view'
  | 'status'
  | 'edit'
  | 'field'
  | 'search'
  | 'clean'
  | 'storage'
  | 'clone'
  | 'masking'
  | 'start'
  | 'stop'
  | 'delete'
  | 'one_key_check'
  | string;

export interface ICollectListRowData {
  collector_config_id?: number | string;
  /** index_set_id 在不同场景可能是 string/number */
  index_set_id?: number | string;
  /** 计算平台/第三方 ES 可能存在多个索引集 */
  bkdata_index_set_ids?: Array<number | string>;
  table_id?: number | string;
  status?: string;
  itsm_ticket_status?: string;
  storage_cluster_id?: number;
  log_access_type?: CollectTypeKey;
  permission?: ICollectListPermissionMap;
  [key: string]: unknown;
}

export interface IAuthResourceItem {
  type: string;
  id: string | number;
}

export interface IAuthApplyDataParams {
  action_ids: string[];
  resources: IAuthResourceItem[];
}

export interface ICheckAllowedResponse {
  isAllowed?: boolean;
  [key: string]: unknown;
}

export interface IGetApplyDataResponse<T = unknown> {
  data?: T;
  [key: string]: unknown;
}

export interface ITableRowItem {
  fieldindex: string;
  word: string;
  op: string;
  tableIndex: number;
  logic_op?: logicOpType;
}

export interface ILabelSelectorArrayItem extends Record<string, unknown> {
  id: string | number;
  type: string;
}

type logicOpType = 'and' | 'or';

export type btnType = 'match' | 'none' | 'separator';

/**
 * ========= ES索引选择对话框相关类型 =========
 */

/**
 * 时间字段类型
 * - date: 日期类型
 * - long: 长整型（时间戳）
 */
export type TimeFieldType = 'date' | 'long';

/**
 * 时间精度单位
 * - second: 秒
 * - millisecond: 毫秒
 * - microsecond: 微秒
 */
export type TimeFieldUnit = 'second' | 'millisecond' | 'microsecond';

/**
 * 时间字段信息接口
 * 用于描述 ES 索引中的时间相关字段
 */
export interface ITimeField {
  /** 字段名称 */
  field_name: string;
  /** 字段类型 */
  field_type: TimeFieldType;
  [key: string]: unknown;
}

/**
 * 时间索引配置接口
 * 用于描述索引的时间字段配置信息
 */
export interface ITimeIndex {
  /** 时间字段名称 */
  time_field: string;
  /** 时间字段类型 */
  time_field_type: TimeFieldType;
  /** 时间精度单位（仅当 time_field_type 为 'long' 时必填） */
  time_field_unit?: TimeFieldUnit;
}

/**
 * ES索引项接口
 * 用于描述一个 ES 索引的基本信息
 */
export interface IEsIndexItem {
  /** 结果表ID（索引名称） */
  result_table_id: string;
  [key: string]: unknown;
}

/**
 * ES索引配置数据接口
 * 用于描述 ES 索引选择对话框的配置数据
 */
export interface IEsIndexConfigData {
  /** 存储集群ID */
  storage_cluster_id: number | string;
  /** 索引列表 */
  indexes: IEsIndexItem[];
  [key: string]: unknown;
}

/**
 * ES索引选择表单数据接口
 * 用于描述 ES 索引选择对话框的表单数据
 */
export interface IEsSelectFormData {
  /** 结果表ID（索引名称，支持通配符 *） */
  resultTableId: string;
  /** 时间字段名称 */
  time_field?: string;
  /** 时间字段类型 */
  time_field_type?: TimeFieldType;
  /** 时间精度单位（仅当 time_field_type 为 'long' 时必填） */
  time_field_unit?: TimeFieldUnit;
}

/**
 * ES索引表格数据项接口
 * 用于描述表格中显示的索引信息
 */
export interface IEsIndexTableDataItem {
  /** 结果表ID */
  result_table_id: string;
  [key: string]: unknown;
}

/**
 * 时间单位选项接口
 * 用于描述时间精度单位选择器的选项
 */
export interface ITimeUnitOption {
  /** 显示名称 */
  name: string;
  /** 单位ID */
  id: TimeFieldUnit;
}

/**
 * ES索引适配请求数据接口
 * 用于描述调用适配接口时的请求数据结构
 */
export interface IEsIndexAdaptRequest {
  scenario_id: string;
  bk_biz_id: number | string;
  storage_cluster_id: number | string;
  /** 已有索引列表，使用新的时间字段配置 */
  basic_indices: Array<{
    index: string;
    time_field: string;
    time_field_type: TimeFieldType;
  }>;
  /** 新增的索引 */
  append_index: {
    index: string;
    time_field: string;
    time_field_type: TimeFieldType;
  };
}
