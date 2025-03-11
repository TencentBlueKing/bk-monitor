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
import { Component, Provide, ProvideReactive, Ref, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getDataSourceConfig } from 'monitor-api/modules/grafana';
import { random } from 'monitor-common/utils';

import RetrievalFilter from '../../components/retrieval-filter/retrieval-filter';
import { EMode, mergeWhereList, type IGetValueFnParams } from '../../components/retrieval-filter/utils';
import { DEFAULT_TIME_RANGE, handleTransformToTimestamp } from '../../components/time-range/utils';
import { getDefaultTimezone } from '../../i18n/dayjs';
import FavoriteContainer from '../data-retrieval/favorite-container/favorite-container';
import { APIType, getEventTopK, getEventViewConfig } from './api-utils';
import DimensionFilterPanel from './components/dimension-filter-panel';
import EventExploreView from './components/event-explore-view';
import EventRetrievalHeader from './components/event-retrieval-header';
import EventRetrievalLayout from './components/event-retrieval-layout';
import EventExplore from './event-explore';

import type { IWhereItem } from '../../components/retrieval-filter/utils';
import type { TimeRangeType } from '../../components/time-range/time-range';
import type { IFormData } from './typing';

@Component
export default class MonitorEventExplore extends tsc<object> {
  @Ref('favoriteContainer') favoriteContainerRef: FavoriteContainer;

  // 数据时间间隔
  @ProvideReactive('timeRange') timeRange: TimeRangeType = DEFAULT_TIME_RANGE;
  // 时区
  @ProvideReactive('timezone') timezone: string = getDefaultTimezone();
  // 刷新间隔
  @ProvideReactive('refleshInterval') refreshInterval = -1;
  // 是否立即刷新
  @ProvideReactive('refleshImmediate') refreshImmediate = '';
  /** 图表框选范围事件所需参数 -- 开启框选功能 */
  @Provide('enableSelectionRestoreAll') enableSelectionRestoreAll = true;
  /** 图表框选范围事件所需参数 -- 是否展示复位按钮 */
  @ProvideReactive('showRestore') showRestore = false;

  @ProvideReactive('formatTimeRange')
  get formatTimeRange() {
    return handleTransformToTimestamp(this.timeRange);
  }
  cacheTimeRange = [];
  timer = null;
  /** 是否展示收藏 */
  isShowFavorite = true;

  favoriteList = [];
  /** 当前选择的收藏 */
  currentFavorite = null;

  dataTypeLabel = 'event';
  dataSourceLabel = 'custom';
  /** 数据Id */
  dataId = '';
  /** 数据ID列表 */
  dataIdList = [];
  /** 查询语句 */
  queryString = '';
  /** UI查询 */
  where: IFormData['where'] = [];
  /** 维度列表 */
  group_by: IFormData['group_by'] = [];
  /** 过滤条件 */
  filter_dict: IFormData['filter_dict'] = {};
  /** 用于 日志 和 事件关键字切换 换成查询 */
  cacheQuery: IFormData = null;
  compare: { type: 'none'; value: string[] } = {
    type: 'none',
    value: [],
  };
  get formData(): IFormData {
    return {
      data_source_label: this.dataSourceLabel || 'custom',
      data_type_label: this.dataTypeLabel || 'event',
      table: this.dataId,
      query_string: this.queryString,
      where: this.where || [],
      group_by: this.group_by || [],
      filter_dict: this.filter_dict || {},
    };
  }

  async mounted() {
    const isShowFavorite =
      JSON.parse(localStorage.getItem('bk_monitor_data_favorite_show') || 'false') || !!this.$route.query?.favorite_id;
    this.isShowFavorite = isShowFavorite;
    // this.getRouteParams();
    await this.getDataIdList(!this.dataId);
    // await this.getViewConfig();
  }

  @Provide('handleTimeRangeChange')
  handleTimeRangeChange(timeRange: TimeRangeType) {
    this.showRestore = false;
    this.timeRange = timeRange;
    // this.getViewConfig();
  }
  /**
   * @description 更改数据时间间隔（其中 Provide 主要提供图表组件框选事件需要）
   */
  @Provide('handleChartDataZoom')
  handleTimeRangeChangeForChart(timeRange: TimeRangeType) {
    if (JSON.stringify(this.timeRange) === JSON.stringify(timeRange)) {
      return;
    }
    this.showRestore = true;
    this.cacheTimeRange = JSON.parse(JSON.stringify(this.timeRange));
    this.timeRange = timeRange;
    // this.getViewConfig();
  }
  /**
   * @description 恢复数据时间间隔
   */
  @Provide('handleRestoreEvent')
  handleRestoreEventForChart() {
    this.handleTimeRangeChange(JSON.parse(JSON.stringify(this.cacheTimeRange)));
  }
  handleTimezoneChange(timezone: string) {
    this.timezone = timezone;
  }
  handleImmediateRefresh() {
    this.refreshImmediate = random(4);
    // this.getViewConfig();
  }

  handleRefreshChange(value: number) {
    this.refreshInterval = value;
    // this.setRouteParams();
    this.timer && clearInterval(this.timer);
    if (value > -1) {
      this.timer = setInterval(() => {
        this.handleImmediateRefresh();
      }, value);
    }
  }
  /** 收藏夹显隐 */
  favoriteShowChange(show: boolean) {
    this.isShowFavorite = show;
    localStorage.setItem('bk_monitor_data_favorite_show', `${show}`);
  }

  handleFavoriteListChange(list) {
    this.favoriteList = list;
  }
  /** 选择收藏或者新检索 */
  handleSelectFavorite(data) {
    if (!this.currentFavorite && !data) return;
    this.currentFavorite = data;
    if (data) {
      // 选择收藏
      const { compareValue, queryConfig } = data.config;
      // 兼容以前的
      const { result_table_id, data_source_label, data_type_label, query_string, where, group_by, filter_dict } =
        queryConfig;
      this.dataId = result_table_id;
      this.dataSourceLabel = data_source_label;
      this.dataTypeLabel = data_type_label;
      this.queryString = query_string;
      this.where = where;
      this.group_by = group_by;
      this.filter_dict = filter_dict;
      this.timeRange = compareValue.tools.timeRange;
      this.refreshInterval = compareValue.tools.refleshInterval || compareValue.tools.refreshInterval;
      this.timezone = compareValue.tools.timezone;
      this.compare = compareValue.compare;
    } else {
      // 选择检索
      this.dataId = this.dataIdList[0].id;
      this.dataSourceLabel = 'custom';
      this.dataTypeLabel = 'event';
      this.queryString = '*';
      this.where = [];
      this.group_by = [];
      this.filter_dict = {};
      this.timeRange = DEFAULT_TIME_RANGE;
      this.refreshInterval = -1;
      this.timezone = getDefaultTimezone();
    }
  }
  /** 收藏功能 */
  handleFavorite(isEdit = false) {
    const params = {
      queryConfig: {
        ...this.formData,
        result_table_id: this.dataId,
      },
      compareValue: {
        compare: this.compare,
        tools: {
          timeRange: this.timeRange,
          refreshInterval: this.refreshInterval,
          timezone: this.timezone,
        },
      },
    };
    if (isEdit) {
      this.favoriteContainerRef.handleFavorite({ ...this.currentFavorite, config: params }, isEdit);
    } else {
      this.favoriteContainerRef.handleFavorite(params, isEdit);
    }
  }

  /** 切换数据ID */
  handleDataIdChange(dataId: string) {
    this.dataId = dataId;
    // this.getViewConfig();
  }
  /** 事件类型切换 */
  async handleEventTypeChange(dataType: { data_source_label: string; data_type_label: string }) {
    // todo 还原上次切换前数据
    this.cacheQuery = JSON.parse(JSON.stringify(this.formData)); // 缓存原始数据查询
    this.dataSourceLabel = dataType.data_source_label;
    this.dataTypeLabel = dataType.data_type_label;
    await this.getDataIdList();
    // await this.getViewConfig();
  }
  async getDataIdList(init = true) {
    const list = await getDataSourceConfig({
      data_source_label: this.dataSourceLabel,
      data_type_label: this.dataTypeLabel,
    }).catch(() => []);
    this.dataIdList = list;
    if (init) {
      this.dataId = list[0]?.id || '';
    }
  }
  handleWhereChange(where: IFormData['where']) {
    this.where = where;
  }
  handleQueryStringChange(queryString: string) {
    this.queryString = queryString;
  }
  handleGroupByChange(group_by: IFormData['group_by']) {
    this.group_by = group_by;
  }
  handleFilterChange(filter_dict: IFormData['filter_dict']) {
    this.filter_dict = filter_dict;
  }
  handleCompareChange(compare: { type: 'none'; value: string[] }) {
    this.compare = compare;
  }
  render() {
    return (
      <EventExplore
        scopedSlots={{
          favorite: () => (
            <div
              style={{ display: this.isShowFavorite ? 'block' : 'none' }}
              class='left-favorite-panel'
              slot='favorite'
            >
              <FavoriteContainer
                ref='favoriteContainer'
                dataId={this.dataId}
                favoriteSearchType='event'
                isShowFavorite={this.isShowFavorite}
                onFavoriteListChange={this.handleFavoriteListChange}
                onSelectFavorite={this.handleSelectFavorite}
                onShowChange={this.favoriteShowChange}
              />
            </div>
          ),
          header: () => (
            <EventRetrievalHeader
              slot='header'
              dataIdList={this.dataIdList}
              formData={this.formData}
              isShowFavorite={this.isShowFavorite}
              refreshInterval={this.refreshInterval}
              timeRange={this.timeRange}
              timezone={this.timezone}
              onDataIdChange={this.handleDataIdChange}
              onEventTypeChange={this.handleEventTypeChange}
              onFavoriteShowChange={this.favoriteShowChange}
              onImmediateRefresh={this.handleImmediateRefresh}
              onRefreshChange={this.handleRefreshChange}
              onTimeRangeChange={this.handleTimeRangeChange}
              onTimezoneChange={this.handleTimezoneChange}
            />
          ),
        }}
        dataId={this.dataId}
        dataSourceLabel={this.dataSourceLabel}
        dataTypeLabel={this.dataTypeLabel}
        filter_dict={this.filter_dict}
        group_by={this.group_by}
        queryString={this.queryString}
        source={APIType.MONITOR}
        where={this.where}
        onQueryStringChange={this.handleQueryStringChange}
        onWhereChange={this.handleWhereChange}
      />
    );
  }
}
