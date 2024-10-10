export interface IServiceConfig {
  label: string;
  name: string;
  operate: number;
  values: string[];
  value_type: number;
}
export interface IColumn {
  label: string;
  prop: string;
}

export interface IDataItem {
  [key: string]: string;
}
