export type ConsitionItem = {
  field: string;
  operator: string;
  value: string[];
  relation?: 'AND' | 'OR';
  isInclude?: boolean;
  field_type?: string;
};

export type RouteParams = {
  addition: ConsitionItem[];
  keyword: string;
  start_time: string;
  end_time: string;
  timezone: string;
  unionList: string[];
  datePickerValue: number;
  host_scopes: string[];
  ip_chooser: string[];
  search_mode: string;
  clusterParams: any;
  index_id?: string;
  bizId: string;
  spaceUid: string;
  format: string;
};
