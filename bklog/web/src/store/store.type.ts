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
enum BK_LOG_STORAGE {
  /**
   * 当前 bk_biz_id
   */
  BK_BIZ_ID = '_14',

  /**
   * 当前space_uid
   */
  BK_SPACE_UID = '_13',

  /**
   * 缓存趋势图历史选择的起止时间列表
   */
  CACHED_BATCH_LIST = '_18',

  /**
   * 常用业务ID列表
   */
  COMMON_SPACE_ID_LIST = '_16',

  /**
   * 当前激活的收藏 id
   */
  FAVORITE_ID = 'f_11',

  /**
   * 左侧字段设置缓存配置
   */
  FIELD_SETTING = '_9',

  /**
   * 当前激活的历史记录 id
   */
  HISTORY_ID = 'h_12',

  /**
   * 索引集激活的tab
   * single - 单选
   * union - 多选
   */
  INDEX_SET_ACTIVE_TAB = '_10',

  /**
   * 是否展开长字段
   */
  IS_LIMIT_EXPAND_VIEW = '_5',

  /**
   * 最后选择索引ID
   */
  LAST_INDEX_SET_ID = '_15',

  /**
   * 日志检索当前使用的检索类型： 0 - ui模式 1 - 语句模式
   */
  SEARCH_TYPE = '_8',

  /**
   * 是否展示字段别名
   */
  SHOW_FIELD_ALIAS = '_6',

  /**
   * 是否展示空字段
   */
  TABLE_ALLOW_EMPTY_FIELD = '_4',

  /**
   * 是否展示json解析
   */
  TABLE_JSON_FORMAT = '_1',

  /**
   * json解析展示层级
   */
  TABLE_JSON_FORMAT_DEPTH = '_2',

  /**
   * 表格行是否换行
   */
  TABLE_LINE_IS_WRAP = '_0',

  /**
   * 是否展示行号
   */
  TABLE_SHOW_ROW_INDEX = '_3',

  /**
   * 表格是否展示日志来源
   */
  TABLE_SHOW_SOURCE_FIELD = '_19',

  /**
   * 文本溢出（省略设置）start | end | center
   */
  TEXT_ELLIPSIS_DIR = '_7',
  /**
   * 趋势图是否折叠
   */
  TREND_CHART_IS_FOLD = '_17',
}

export { BK_LOG_STORAGE };

export const SEARCH_MODE_DIC = ['ui', 'sql'];

export type ConsitionItem = {
  field: string;
  operator: string;
  value: string[];
  relation?: 'AND' | 'OR';
  isInclude?: boolean;
  field_type?: string;
  hidden_values?: string[];
  disabled?: boolean;
};

/**
 * 路由参数类型定义
 */
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
  [BK_LOG_STORAGE.HISTORY_ID]: string;
  [BK_LOG_STORAGE.FAVORITE_ID]: string;
};

export type FieldInfoItemArgs = {
  field_alias?: string;
  is_display?: boolean;
  is_editable?: boolean;
  tag?: string;
  origin_field?: string;
  es_doc_values?: boolean;
  is_analyzed?: boolean;
  is_virtual_obj_node?: boolean;
  field_operator?: string[];
  is_built_in?: boolean;
  is_case_sensitive?: boolean;
  is_virtual_alias_field?: boolean;
  tokenize_on_chars?: string;
  description?: string;
  filterVisible?: boolean;
};

export type FieldInfoItem = FieldInfoItemArgs & {
  field_type: string;
  field_name: string;
};
