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
import VueRouter from 'vue-router';
import RouteUrlResolver from './url-resolver';
import { RouteParams, BK_LOG_STORAGE } from './store.type';

const DEFAULT_FIELDS_WIDTH = 200;

export const logSourceField = () => {
  return {
    description: null,
    es_doc_values: false,
    field_alias: '',
    field_name: window.mainComponent.$t('日志来源'),
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

export const routeQueryKeys = [
  'addition',
  'bizId',
  'end_time',
  'keyword',
  'spaceUid',
  'start_time',
  'timezone',
  'unionList',
];

const BkLogGlobalStorageKey = 'STORAGE_KEY_BKLOG_GLOBAL';

export { BkLogGlobalStorageKey };

const getUrlArgs = () => {
  const router = new VueRouter({
    routes: [
      {
        path: '',
        redirect: 'retrieve',
        meta: {
          title: '检索',
          navId: 'retrieve',
        },
      },
      {
        name: 'retrieve',
        path: '/retrieve/:indexId?',
      },
    ],
  });

  const hash = window.location.hash.replace(/^#/, '');
  const route = router.resolve(hash);
  const urlResulver = new RouteUrlResolver({ route: route.resolved });
  urlResulver.setResolver('index_id', () => route.resolved.params.indexId ?? '');
  return urlResulver.convertQueryToStore<RouteParams>();
};

export const URL_ARGS = getUrlArgs();

export const getDefaultRetrieveParams = () => {
  return {
    keyword: '',
    host_scopes: { modules: [], ips: '', target_nodes: [], target_node_type: '' },
    ip_chooser: {},
    addition: [],
    sort_list: [],
    begin: 0,
    size: 50,
    interval: 'auto',
    timezone: 'Asia/Shanghai',
    search_mode: 'ui',
    ...URL_ARGS,
  };
};

export const getDefaultDatePickerValue = () => {
  const datePickerValue = ['now-15m', 'now'];
  const format = localStorage.getItem('SEARCH_DEFAULT_TIME_FORMAT') ?? 'YYYY-MM-DD HH:mm:ss';
  const [start_time, end_time] = handleTransformToTimestamp(datePickerValue, format);

  return { datePickerValue, start_time, end_time, format };
};

export const DEFAULT_RETRIEVE_PARAMS = getDefaultRetrieveParams();
export const DEFAULT_DATETIME_PARAMS = getDefaultDatePickerValue();

export const IndexSetQueryResult = {
  is_loading: false,
  exception_msg: '',
  is_error: false,
  request_counter: 0,
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
  request_counter: 0,
  fields: [],
  display_fields: [],
  sort_list: [],
  time_field: '',
  time_field_type: '',
  time_field_unit: '',
  config: [],
  config_id: 0,
  aggs_items: {},
  last_eggs_request_token: null,
  custom_config: {
    grade_options: {
      disabled: false,
      type: 'normal',
      field: null,
      settings: [],
    },
  },
  user_custom_config: {
    filterSetting: [],
    displayFields: [],
    fieldsWidth: {},
    filterAddition: [],
  },
};

export const IndexsetItemParams = { ...DEFAULT_RETRIEVE_PARAMS };

export const IndexItem = {
  ids: URL_ARGS.unionList?.length ? URL_ARGS.unionList : [URL_ARGS.index_id],
  isUnionIndex: URL_ARGS.unionList?.length ?? false,
  items: [],
  catchUnionBeginList: [],
  selectIsUnionSearch: URL_ARGS.unionList?.length ?? false,
  chart_params: {
    activeGraphCategory: 'table',
    chartActiveType: 'table',
    dimensions: [],
    sql: '',
    xFields: [],
    yFields: [],
    // 这里的fromCollectionActiveTab用于标识当前来自收藏的点击操作是否已经激活图表分析Tab
    // 这里每次的收藏选择应该只会激活一次
    fromCollectionActiveTab: undefined,
  },
  ...IndexsetItemParams,
  ...DEFAULT_DATETIME_PARAMS,
};

export const getStorageOptions = () => {
  const storageValue = window.localStorage.getItem(BkLogGlobalStorageKey) ?? '{}';
  let storage = {};
  if (storageValue) {
    try {
      storage = JSON.parse(storageValue);

      let update = false;
      // 对旧版缓存进行还原操作
      // 映射旧版配置到新版key，同时移除旧版key
      [
        ['fieldSetting', BK_LOG_STORAGE.FIELD_SETTING],
        ['indexSetActiveTab', BK_LOG_STORAGE.INDEX_SET_ACTIVE_TAB],
        ['isLimitExpandView', BK_LOG_STORAGE.IS_LIMIT_EXPAND_VIEW],
        ['searchType', BK_LOG_STORAGE.SEARCH_TYPE],
        ['showFieldAlias', BK_LOG_STORAGE.SHOW_FIELD_ALIAS],
        ['tableAllowEmptyField', BK_LOG_STORAGE.TABLE_ALLOW_EMPTY_FIELD],
        ['tableJsonFormat', BK_LOG_STORAGE.TABLE_JSON_FORMAT],
        ['tableJsonFormatDepth', BK_LOG_STORAGE.TABLE_JSON_FORMAT_DEPTH],
        ['tableLineIsWrap', BK_LOG_STORAGE.TABLE_LINE_IS_WRAP],
        ['tableShowRowIndex', BK_LOG_STORAGE.TABLE_SHOW_ROW_INDEX],
        ['textEllipsisDir', BK_LOG_STORAGE.TEXT_ELLIPSIS_DIR],
      ].forEach(([k1, k2]) => {
        if (storage[k1] !== undefined) {
          storage[k2] = storage[k1];
          delete storage[k1];
          update = true;
        }
      });

      if (update) {
        window.localStorage.setItem(BkLogGlobalStorageKey, JSON.stringify(storage));
      }
    } catch (e) {
      console.error(e);
    }
  }

  let activeTab = 'single';

  if (URL_ARGS[BK_LOG_STORAGE.FAVORITE_ID]) {
    activeTab = 'favorite';
  }

  if (URL_ARGS[BK_LOG_STORAGE.HISTORY_ID]) {
    activeTab = 'history';
  }

  return Object.assign(
    {
      [BK_LOG_STORAGE.TABLE_LINE_IS_WRAP]: false,
      [BK_LOG_STORAGE.TABLE_JSON_FORMAT]: false,
      [BK_LOG_STORAGE.TABLE_JSON_FORMAT_DEPTH]: 1,
      [BK_LOG_STORAGE.TABLE_SHOW_ROW_INDEX]: false,
      [BK_LOG_STORAGE.TABLE_ALLOW_EMPTY_FIELD]: false,
      [BK_LOG_STORAGE.IS_LIMIT_EXPAND_VIEW]: false,
      [BK_LOG_STORAGE.SHOW_FIELD_ALIAS]: true,
      [BK_LOG_STORAGE.TEXT_ELLIPSIS_DIR]: 'end',
      [BK_LOG_STORAGE.SEARCH_TYPE]: 0,
      [BK_LOG_STORAGE.INDEX_SET_ACTIVE_TAB]: activeTab,
      [BK_LOG_STORAGE.FAVORITE_ID]: URL_ARGS[BK_LOG_STORAGE.FAVORITE_ID],
      [BK_LOG_STORAGE.HISTORY_ID]: URL_ARGS[BK_LOG_STORAGE.HISTORY_ID],
      [BK_LOG_STORAGE.FIELD_SETTING]: {
        show: true,
        width: DEFAULT_FIELDS_WIDTH,
      },
    },
    storage,
  );
};
