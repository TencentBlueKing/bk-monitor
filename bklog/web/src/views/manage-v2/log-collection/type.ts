export interface IListItemData {
  index_set_id?: string;
  index_set_name?: string;
  index_count?: number;
  icon?: string;
  unEditable?: boolean;
  [key: string]: any;
}

export interface ISelectItem {
  id: string;
  name: string;
  value?: string;
}
// 用于描述附加标签结构
export interface IExtraLabel {
  key?: string;
  value?: string;
  operator?: string;
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
  extra_labels?: IExtraLabel[];
  conditions?: IConditions;
  winlog_name?: string[];
  winlog_level?: string[];
  winlog_event_id?: string[];
}

export interface IValueItem {
  key: string;
  operator: string;
  value: string;
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
  label_selector?: ILabelSelector;
  match_labels?: IValueItem[];
  extra_labels: IExtraLabel[];
  match_expressions?: IValueItem[];
  data_encoding?: string;
  params?: ICollectionParams;
  collector_type?: string;
  namespaces?: string[];
  annotation_selector?: IAnnotationSelector;
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
  extra_labels?: IExtraLabel[];
  configs?: IContainerConfigItem[];
  yaml_config?: string;
  yaml_config_enabled?: boolean;
  // 采集配置
  params?: ICollectionParams;
}

export interface IClusterItem {
  id: string;
  name: string;
}
