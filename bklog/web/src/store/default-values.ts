/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */
// @ts-ignore
import { handleTransformToTimestamp } from '@/components/time-range/utils';
export const getDefaultRetrieveParams = () => {
  return {
    keyword: '*',
    host_scopes: { modules: [], ips: '', target_nodes: [], target_node_type: '' },
    ip_chooser: {},
    addition: [],
    sort_list: [],
    begin: 0,
    size: 50,
    interval: 'auto',
    timezone: 'Asia/Shanghai',
    search_mode: 'sql',
  };
};

export const getDefaultDatePickerValue = () => {
  const datePickerValue = ['now-15m', 'now'];
  const [start_time, end_time] = handleTransformToTimestamp(datePickerValue);

  return { datePickerValue, start_time, end_time };
};

export const DEFAULT_RETRIEVE_PARAMS = getDefaultRetrieveParams();
export const DEFAULT_DATETIME_PARAMS = getDefaultDatePickerValue();

export const IndexSetQueryResult = {
  is_loading: false,
  search_count: 0,
  aggregations: {},
  _shards: {},
  total: 0,
  took: 0,
  list: [],
  origin_log_list: [],
  aggs: {},
  fields: [],
};

export const IndexFieldInfo = {
  is_loading: false,
  fields: [],
  display_fields: [],
  sort_list: [],
  time_field: '',
  time_field_type: '',
  time_field_unit: '',
  config: [],
  config_id: 0,
  aggs_items: [],
};

export const IndexsetItemParams = { ...DEFAULT_RETRIEVE_PARAMS };

export const IndexItem = {
  ids: [],
  isUnionIndex: false,
  items: [],
  catchUnionBeginList: [],
  selectIsUnionSearch: false,
  ...IndexsetItemParams,
  ...DEFAULT_DATETIME_PARAMS,
};

export const logSourceField = () => {
  return {
    description: null,
    es_doc_values: false,
    field_alias: '',
    field_name: (window as any).$t('日志来源'),
    field_operator: [],
    field_type: 'union',
    filterExpand: false,
    filterVisible: false,
    is_analyzed: false,
    is_display: false,
    is_editable: false,
    minWidth: 0,
    tag: 'union-source',
    width: 230,
  };
};

export const indexSetClusteringData = {
  // 日志聚类参数
  name: '',
  is_active: true,
  extra: {
    collector_config_id: null,
    signature_switch: false,
    clustering_field: '',
  },
};
