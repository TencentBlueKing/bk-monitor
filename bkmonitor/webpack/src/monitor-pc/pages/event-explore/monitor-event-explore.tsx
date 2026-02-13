/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { Component, Mixins, Provide, ProvideReactive, Ref } from 'vue-property-decorator';

import { getDataSourceConfig } from 'monitor-api/modules/grafana';
import { random } from 'monitor-common/utils';

import { EMode, whereFormatter } from '../../components/retrieval-filter/utils';
import { DEFAULT_TIME_RANGE } from '../../components/time-range/utils';
import { getDefaultTimezone } from '../../i18n/dayjs';
import UserConfigMixin from '../../mixins/userStoreConfig';
import FavoriteContainer from '../data-retrieval/favorite-container/favorite-container';
import { APIType } from './api-utils';
import EventRetrievalHeader from './components/event-explore-header';
import EventExplore from './event-explore';

import type { IWhereItem } from '../../components/retrieval-filter/utils';
import type { TimeRangeType } from '../../components/time-range/time-range';
import type { IFavList } from '../data-retrieval/typings';
import type { HideFeatures, IFormData } from './typing';

/** 上一次选择的dataId */
const EVENT_EXPLORE_DEFAULT_DATA_ID = 'event_explore_default_data_id';
const LOG_EXPLORE_DEFAULT_DATA_ID = 'log_explore_default_data_id';

@Component
export default class MonitorEventExplore extends Mixins(UserConfigMixin) {
  // 获取收藏容器组件的引用
  @Ref('favoriteContainer') favoriteContainerRef: FavoriteContainer;

  // 数据时间间隔
  @ProvideReactive('timeRange') timeRange: TimeRangeType = DEFAULT_TIME_RANGE;
  // 时区
  @ProvideReactive('timezone') timezone: string = getDefaultTimezone();
  // 刷新间隔
  @ProvideReactive('refreshInterval') refreshInterval = -1;
  // 是否立即刷新
  @ProvideReactive('refreshImmediate') refreshImmediate = '';
  /** 图表框选范围事件所需参数 -- 开启框选功能 */
  @Provide('enableSelectionRestoreAll') enableSelectionRestoreAll = true;
  /** 图表框选范围事件所需参数 -- 是否展示复位按钮 */
  @ProvideReactive('showRestore') showRestore = false;

  @ProvideReactive('hideFeatures') hideFeatures: HideFeatures = [];

  cacheTimeRange = [];
  timer = null;
  /** 是否展示收藏 */
  isShowFavorite = true;

  favoriteList: IFavList.favGroupList[] = [];
  /** 当前选择的收藏 */
  currentFavorite: IFavList.favList = null;

  dataTypeLabel = 'event';
  dataSourceLabel = 'custom';
  defaultDataId = '';
  /** 数据Id */
  dataId = '';
  /** 数据ID列表 */
  dataIdList = [];
  /** 查询语句 */
  queryString = '';
  /** 实时输入的查询语句 */
  queryStringInput = '';
  /** 常驻筛选查询 */
  commonWhere: IWhereItem[] = [];
  /** UI查询 */
  where: IWhereItem[] = [];
  /** 维度列表 */
  group_by: IFormData['group_by'] = [];
  /** 过滤条件 */
  filter_dict: IFormData['filter_dict'] = {};
  /** 用于 日志 和 事件关键字切换 换成查询 */
  cacheQuery = new Map<string, Record<string, any>>();
  filterMode = EMode.ui;
  /** 是否展示常驻筛选 */
  showResidentBtn = false;

  get defaultDataIdKey() {
    if (this.dataTypeLabel === 'log') return LOG_EXPLORE_DEFAULT_DATA_ID;
    return EVENT_EXPLORE_DEFAULT_DATA_ID;
  }

  created() {
    const { hideFeatures } = this.$route.query;
    try {
      this.hideFeatures = JSON.parse(decodeURIComponent(hideFeatures?.toString() || '[]'));
    } catch {
      this.hideFeatures = [];
    }
  }
  async mounted() {
    const isShowFavorite =
      JSON.parse(localStorage.getItem('bk_monitor_data_favorite_show') || 'false') || !!this.$route.query?.favorite_id;

    this.isShowFavorite = isShowFavorite;
    this.getRouteParams();
    this.defaultDataId = await this.handleGetUserConfig(this.defaultDataIdKey);
    await this.getDataIdList(!this.dataId);
  }

  @Provide('handleTimeRangeChange')
  handleTimeRangeChange(timeRange: TimeRangeType) {
    this.showRestore = false;
    this.timeRange = timeRange;
    this.setRouteParams();
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
    this.setRouteParams();
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
    this.setRouteParams();
  }
  handleImmediateRefresh() {
    this.refreshImmediate = random(4);
    this.setRouteParams();
  }

  handleRefreshChange(value: number) {
    this.refreshInterval = value;
    this.timer && clearInterval(this.timer);
    if (value > -1) {
      this.timer = setInterval(() => {
        this.handleImmediateRefresh();
      }, value);
    }
    this.setRouteParams();
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
      const {
        result_table_id,
        data_source_label,
        data_type_label,
        query_string,
        where,
        group_by,
        filter_dict,
        filterMode,
        commonWhere,
        showResidentBtn,
      } = queryConfig;
      this.dataId = result_table_id;
      this.dataSourceLabel = data_source_label;
      this.dataTypeLabel = data_type_label;
      this.queryString = query_string;
      this.where = whereFormatter(where);
      this.group_by = group_by;
      this.filter_dict = filter_dict;
      this.timeRange = compareValue.tools.timeRange;
      this.refreshInterval = compareValue.tools.refreshInterval || -1;
      this.timezone = compareValue.tools.timezone;
      this.filterMode = filterMode || EMode.ui;
      this.commonWhere = commonWhere || [];
      this.showResidentBtn = showResidentBtn || false;
    } else {
      // 选择检索
      if (!this.dataId) {
        this.dataId = this.dataIdList[0].id;
        this.dataSourceLabel = 'custom';
        this.dataTypeLabel = 'event';
      }
      this.queryString = '*';
      this.where = [];
      this.group_by = [];
      this.filter_dict = {};
      this.timeRange = DEFAULT_TIME_RANGE;
      this.refreshInterval = -1;
      this.filterMode = EMode.ui;
      this.timezone = getDefaultTimezone();
      this.commonWhere = [];
    }
    this.setRouteParams();
  }

  /** 收藏功能 */
  handleFavorite(isEdit = false) {
    const params = {
      queryConfig: {
        result_table_id: this.dataId,
        data_source_label: this.dataSourceLabel,
        data_type_label: this.dataTypeLabel,
        query_string: this.filterMode === EMode.queryString ? this.queryStringInput : '',
        where: this.filterMode === EMode.ui ? this.where : [],
        group_by: this.group_by,
        filter_dict: this.filter_dict,
        filterMode: this.filterMode,
        commonWhere: this.commonWhere,
        showResidentBtn: this.showResidentBtn,
      },
      compareValue: {
        compare: {
          type: 'none',
          value: [],
        },
        tools: {
          timeRange: this.timeRange,
          refreshInterval: this.refreshInterval,
          timezone: this.timezone,
        },
      },
    };
    if (isEdit) {
      this.favoriteContainerRef.handleFavorite(
        { ...this.currentFavorite, config: params },
        isEdit,
        this.$tc('成功覆盖当前收藏')
      );
    } else {
      this.favoriteContainerRef.handleFavorite(params, isEdit);
    }
  }

  /** 切换数据ID */
  handleDataIdChange(dataId: string) {
    this.dataId = dataId;
    this.handleSetUserConfig(this.defaultDataIdKey, JSON.stringify(dataId));
    this.where = [];
    this.queryString = '';
    this.commonWhere = [];
    this.setRouteParams();
  }

  /** 事件类型切换 */
  async handleEventTypeChange(dataType: { data_source_label: string; data_type_label: string }) {
    this.cacheQuery.set(
      this.dataTypeLabel,
      structuredClone({
        where: this.where,
        dataId: this.dataId,
        query_string: this.queryString,
        group_by: this.group_by,
        filter_dict: this.filter_dict,
        dataIdList: this.dataIdList,
      })
    );
    const cacheQuery = this.cacheQuery.get(dataType.data_type_label);
    let list = cacheQuery?.dataIdList || [];
    if (!list.length) {
      list = await getDataSourceConfig({
        data_source_label: dataType.data_source_label,
        data_type_label: dataType.data_type_label,
        return_dimensions: false,
      }).catch(() => []);
    }
    this.dataId = cacheQuery?.dataId || list[0]?.id || '';
    this.dataIdList = list;
    this.dataSourceLabel = dataType.data_source_label;
    this.dataTypeLabel = dataType.data_type_label;
    this.where = cacheQuery?.where || [];
    this.queryString = cacheQuery?.query_string || '';
    this.group_by = cacheQuery?.group_by || [];
    this.filter_dict = cacheQuery?.filter_dict || {};
    this.setRouteParams();
  }

  async getDataIdList(init = true) {
    const list = await getDataSourceConfig({
      data_source_label: this.dataSourceLabel,
      data_type_label: this.dataTypeLabel,
      return_dimensions: false,
    }).catch(() => []);
    this.dataIdList = list;
    if (init) {
      if (list.find(item => item.id === this.defaultDataId)) {
        this.dataId = this.defaultDataId;
      } else {
        this.dataId = list[0]?.id || '';
      }
    }
  }

  /** where条件修改 */
  handleWhereChange(where: IFormData['where']) {
    this.where = where;
    this.setRouteParams();
  }

  /** 常驻筛选项修改 */
  handleCommonWhereChange(where: IWhereItem[]) {
    this.commonWhere = where;
    this.setRouteParams();
  }

  /** queryString变化 */
  handleQueryStringChange(queryString: string) {
    this.queryString = queryString;
    this.setRouteParams();
  }
  handleGroupByChange(group_by: IFormData['group_by']) {
    this.group_by = group_by;
    this.setRouteParams();
  }

  handleFilterChange(filter_dict: IFormData['filter_dict']) {
    this.filter_dict = filter_dict;
    this.setRouteParams();
  }

  /** 语句模式和UI模式切换 */
  handleFilterModeChange(mode: EMode) {
    this.filterMode = mode;
    if (mode === EMode.queryString) this.showResidentBtn = false;
    this.setRouteParams();
  }

  /** queryString input输入 */
  handleQueryStringInputChange(val: string) {
    this.queryStringInput = val;
  }

  /** 常驻筛选显隐 */
  handleShowResidentBtnChange(isShow: boolean) {
    this.showResidentBtn = isShow;
    this.setRouteParams();
  }

  /** 兼容以前的事件检索URL格式 */
  getRouteParams() {
    const { targets, from, to, timezone, refreshInterval, filterMode, commonWhere, showResidentBtn, favoriteId } =
      this.$route.query;
    if (targets) {
      try {
        const targetsList = JSON.parse(decodeURIComponent(targets as string));
        const [
          {
            data: {
              query_configs: [
                {
                  data_type_label,
                  data_source_label,
                  result_table_id,
                  table,
                  where,
                  query_string: queryString,
                  group_by: groupBy,
                  filter_dict: filterDict,
                },
              ],
            },
          },
        ] = targetsList;
        this.dataTypeLabel = data_type_label || 'event';
        this.dataSourceLabel = data_source_label || 'custom';
        this.dataId = result_table_id || table;
        this.where = whereFormatter(where || []);
        this.queryString = queryString || '';
        this.group_by = groupBy || [];
        this.filter_dict = filterDict || {};
        this.timeRange = from ? [from as string, to as string] : DEFAULT_TIME_RANGE;
        this.timezone = (timezone as string) || getDefaultTimezone();
        this.refreshInterval = Number(refreshInterval) || -1;
        this.filterMode = [EMode.ui, EMode.queryString].includes(filterMode as EMode)
          ? (filterMode as EMode)
          : EMode.ui;
        this.commonWhere = favoriteId ? [] : JSON.parse((commonWhere as string) || '[]');
        this.showResidentBtn = JSON.parse((showResidentBtn as string) || 'false') || false;
      } catch (error) {
        console.log('route query:', error);
      }
    }
  }

  setRouteParams(otherQuery = {}) {
    const query = {
      ...this.$route.query,
      from: this.timeRange[0],
      to: this.timeRange[1],
      timezone: this.timezone,
      refreshInterval: String(this.refreshInterval),
      targets: JSON.stringify([
        {
          data: {
            query_configs: [
              {
                result_table_id: this.dataId,
                data_type_label: this.dataTypeLabel,
                data_source_label: this.dataSourceLabel,
                where: this.where,
                query_string: this.queryString,
                group_by: this.group_by,
                filter_dict: this.filter_dict,
              },
            ],
          },
        },
      ]),
      filterMode: this.filterMode,
      commonWhere: JSON.stringify(this.commonWhere),
      showResidentBtn: String(this.showResidentBtn),
      favoriteId: String(this.currentFavorite?.id || ''),
      ...otherQuery,
    };

    const targetRoute = this.$router.resolve({
      query,
    });

    /** 防止出现跳转当前地址导致报错 */
    if (targetRoute.resolved.fullPath !== this.$route.fullPath) {
      this.$router.replace({
        query,
      });
    }
  }

  render() {
    return (
      <EventExplore
        scopedSlots={{
          favorite: () =>
            !this.hideFeatures.includes('favorite') ? (
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
            ) : undefined,
          header: () =>
            !this.hideFeatures.includes('header') ? (
              <EventRetrievalHeader
                slot='header'
                dataId={this.dataId}
                dataIdList={this.dataIdList}
                dataSourceLabel={this.dataSourceLabel}
                dataTypeLabel={this.dataTypeLabel}
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
            ) : undefined,
        }}
        commonWhere={this.commonWhere}
        currentFavorite={this.currentFavorite}
        dataId={this.dataId}
        dataIdList={this.dataIdList}
        dataSourceLabel={this.dataSourceLabel}
        dataTypeLabel={this.dataTypeLabel}
        defaultShowResidentBtn={this.showResidentBtn}
        favoriteList={this.favoriteList}
        filter_dict={this.filter_dict}
        filterMode={this.filterMode}
        group_by={this.group_by}
        hideFeatures={this.hideFeatures}
        queryString={this.queryString}
        source={APIType.MONITOR}
        where={this.where}
        onCommonWhereChange={this.handleCommonWhereChange}
        onFavorite={this.handleFavorite}
        onFilterModeChange={this.handleFilterModeChange}
        onQueryStringChange={this.handleQueryStringChange}
        onQueryStringInputChange={this.handleQueryStringInputChange}
        onSetRouteParams={this.setRouteParams}
        onShowResidentBtnChange={this.handleShowResidentBtnChange}
        onWhereChange={this.handleWhereChange}
      />
    );
  }
}
