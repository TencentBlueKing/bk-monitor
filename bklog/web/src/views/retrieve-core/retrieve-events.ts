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
enum RetrieveEvent {
  /**
   * 展示收藏内容
   */
  FAVORITE_ACTIVE_CHANGE = 'favorite-active-change',

  /**
   * 收藏栏是否展示
   */
  FAVORITE_SHOWN_CHANGE = 'favorite-shown-change',

  /**
   * 收藏栏是否仅查看当前索引集
   */
  FAVORITE_VIEW_CURRENT_CHANGE = 'favorite-view-current-change',

  /**
   * 收藏栏宽度变化
   */
  FAVORITE_WIDTH_CHANGE = 'favorite-width-change',

  /**
   * 全局滚动
   */
  GLOBAL_SCROLL = 'global-scroll',

  /**
   * 触发高亮设置
   */
  HILIGHT_TRIGGER = 'hilight-trigger',

  /**
   * 打开索引配置
   */
  INDEX_CONFIG_OPEN = 'index-config-open',

  /**
   * 索引集id 变化
   */
  INDEX_SET_ID_CHANGE = 'index-set-id-change',

  /**
   * 左侧字段信息更新
   */
  LEFT_FIELD_INFO_UPDATE = 'left-field-info-update',

  /**
   * 左侧字段设置是否展示
   */
  LEFT_FIELD_SETTING_SHOWN_CHANGE = 'left-field-setting-shown-change',

  /**
   * 左侧字段设置宽度变化
   */
  LEFT_FIELD_SETTING_WIDTH_CHANGE = 'left-field-setting-width-change',

  /**
   * 检索结果容器resize
   */
  RESULT_ROW_BOX_RESIZE = 'result-row-box-resize',

  /**
   * 搜索时间变化
   */
  SEARCH_TIME_CHANGE = 'search-time-change',

  /**
   * 搜索条件改变
   */
  SEARCH_VALUE_CHANGE = 'search-value-change',

  /**
   * 搜索栏高度变化
   */
  SEARCHBAR_HEIGHT_CHANGE = 'searchbar-height-change',

  /**
   * 搜索中时间改变
   */
  SEARCHING_CHANGE = 'searching-change',

  /**
   * localStorage 变化
   */
  STORAGE_CHANGE = 'storage-change',

  /**
   * 趋势图高度变化
   */
  TREND_GRAPH_HEIGHT_CHANGE = 'trend-graph-height-change',

  /**
   * 趋势图搜索
   */
  TREND_GRAPH_SEARCH = 'trend-graph-search',

  /**
   * 趋势图缩放
   */
  TREND_GRAPH_ZOOM = 'trend-graph-zoom',

  /**
   * 打开别名配置
   */
  ALIAS_CONFIG_OPEN = 'alias_config_open',

  /**
   * 自动刷新日志
   */
  AUTO_REFRESH = 'auto_refresh',
}

export default RetrieveEvent;
