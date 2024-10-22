export interface IServiceConfig {
  value: string;
  text: string;
  values: IDataItem[];
}
export interface IColumn {
  label: string;
  prop: string;
}

export interface IDataItem {
  [key: string]: string;
}
export interface IFilterCondition {
  key: string;
  method: string;
  value: IDataItem[];
  condition: string;
}

export interface IFilterType {
  call_filter: IFilterCondition[];
  group_by_filter: IDataItem[];
  time_shift: IDataItem[];
  table_group_by: string[];
}
