import type { GradeConfiguration } from '@/features/retrieval/core/interface';
/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
import type { ConsitionItem, FieldInfoItem } from './store.type';
export interface IndexSetTag { tag_id: number; name: string; color?: string; }
/** resolveIndexItemAttr normalizes backend index_set_id into a string. */
export interface IndexSetOption {
  index_set_id: string;
  index_set_name?: string;
  indexName: string;
  unique_id?: string;
  scenario_id?: string;
  collector_config_id?: number | null;
  support_doris?: boolean;
  lightenName: string;
  tagSearchName?: string;
  tagAllID?: number;
  name?: string;
  query_string?: string;
  addition?: ConsitionItem[];
  no_data_check_time?: string;
  index_set_ids?: (number | string)[];
  index_set_names?: string[];
  id?: number;
  is_favorite?: boolean;
  isNotVal?: boolean;
  tags?: IndexSetTag[];
  children?: IndexSetOption[];
  indices?: { result_table_id: string; index_set_id?: string | number }[];
  permission?: Record<string, boolean>;
  [key: string]: unknown;
}
/** Logs have a runtime schema; fixed transport metadata and arbitrary values are distinct. */
export type LogRecord = Record<string, unknown>;
export type SortEntry = [string, string];
export interface QueryResultState {
  is_loading: boolean;
  is_pagination_loading: boolean;
  exception_msg: string;
  is_error: boolean;
  search_count: number;
  aggregations: Record<string, unknown>;
  _shards: Record<string, number>;
  total: number;
  took: number;
  list: LogRecord[];
  origin_log_list: LogRecord[];
  row_keys: string[];
  row_query_key: string;
  cached_count: number;
  aggs: Record<string, unknown>;
  fields: FieldInfoItem[];
}
export interface FieldConfigurationState {
  fields?: FieldInfoItem[];
  is_loading: boolean;
  field_scope: string;
  fieldNameIndex?: Record<string, FieldInfoItem>;
  queryAliasIndex?: Record<string, FieldInfoItem>;
  field_meta_version: number;
  display_fields: string[];
  sort_list: SortEntry[];
  default_sort_list: SortEntry[];
  time_field: string;
  time_field_type: string;
  time_field_unit: string;
  config: { id: number; name?: string; [key: string]: unknown }[];
  config_id: number;
  last_eggs_request_token: string | null;
  custom_config: {
    grade_options: GradeConfiguration;
  };
  user_custom_config: {
    filterSetting: FieldInfoItem[];
    displayFields: string[];
    fieldsWidth: Record<string, number>;
    filterAddition: ConsitionItem[];
  };
}

export interface QueryFieldOperator { operator: string; label: string; placeholder?: string; }
export interface QueryField {
  field_name: string; field_type: string | null; field_alias: string | null;
  field_id?: string | number | null; is_virtual_alias_field?: boolean; query_alias?: string; is_full_text?: boolean;
  field_operator: QueryFieldOperator[]; disabled?: boolean; hidden_values?: string[];
}

export interface RetrieveCustomConfig {
  fieldsWidth: Record<string, number>;
  displayFields: string[];
  filterSetting: QueryField[];
  filterAddition: ConsitionItem[];
  fixedFilterAddition: boolean;
  sortList: SortEntry[];
}
