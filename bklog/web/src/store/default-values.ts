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
import { RouteParams } from './store.type';

const DEFAULT_FIELDS_WIDTH = 200;
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
enum BK_LOG_STORAGE {
  /**
   * 表格行是否换行
   */
  TABLE_LINE_IS_WRAP = '_0',

  /**
   * 是否展示json解析
   */
  TABLE_JSON_FORMAT = '_1',

  /**
   * json解析展示层级
   */
  TABLE_JSON_FORMAT_DEPTH = '_2',

  /**
   * 是否展示行号
   */
  TABLE_SHOW_ROW_INDEX = '_3',

  /**
   * 是否展示空字段
   */
  TABLE_ALLOW_EMPTY_FIELD = '_4',

  /**
   * 是否展开长字段
   */
  IS_LIMIT_EXPAND_VIEW = '_5',

  /**
   * 是否展示字段别名
   */
  SHOW_FIELD_ALIAS = '_6',

  /**
   * 文本溢出（省略设置）start | end | center
   */
  TEXT_ELLIPSIS_DIR = '_7',

  /**
   * 日志检索当前使用的检索类型： 0 - ui模式 1 - 语句模式
   */
  SEARCH_TYPE = '_8',

  /**
   * 左侧字段设置缓存配置
   */
  FIELD_SETTING = '_9',

  /**
   * 索引集激活的tab
   */
  INDEX_SET_ACTIVE_TAB = '_10',

  /**
   * 当前激活的收藏 id
   */
  FAVORITE_ID = '_11',

  /**
   * 当前激活的历史记录 id
   */
  HISTORY_ID = '_12',
}

export { BK_LOG_STORAGE, BkLogGlobalStorageKey };

export const getStorageOptions = () => {
  const storageValue = window.localStorage.getItem(BkLogGlobalStorageKey) ?? '{}';
  let storage = {};
  if (storageValue) {
    try {
      storage = JSON.parse(storageValue);
    } catch (e) {
      console.error(e);
    }
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
      [BK_LOG_STORAGE.INDEX_SET_ACTIVE_TAB]: 'single',
      [BK_LOG_STORAGE.FAVORITE_ID]: undefined,
      [BK_LOG_STORAGE.HISTORY_ID]: undefined,
      [BK_LOG_STORAGE.FIELD_SETTING]: {
        show: true,
        width: DEFAULT_FIELDS_WIDTH,
      },
    },
    storage,
  );
};
