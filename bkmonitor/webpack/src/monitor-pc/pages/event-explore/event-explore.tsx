/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

import { eventViewConfig } from 'monitor-api/modules/data_explorer';
import { getDataSourceConfig } from 'monitor-api/modules/grafana';
import { random } from 'monitor-common/utils';

import RetrievalFilter from '../../components/retrieval-filter/retrieval-filter';
import { mergeWhereList, type IGetValueFnParams } from '../../components/retrieval-filter/utils';
import { DEFAULT_TIME_RANGE, handleTransformToTimestamp } from '../../components/time-range/utils';
import { getDefaultTimezone } from '../../i18n/dayjs';
import FavoriteContainer from '../data-retrieval/favorite-container/favorite-container';
import { APIType, getEventTopK } from './api-utils';
import DimensionFilterPanel from './components/dimension-filter-panel';
import EventExploreView from './components/event-explore-view';
import EventRetrievalHeader from './components/event-retrieval-header';
import EventRetrievalLayout from './components/event-retrieval-layout';

import type { IWhereItem } from '../../components/retrieval-filter/utils';
import type { TimeRangeType } from '../../components/time-range/time-range';
import type { IFormData } from './typing';

import './event-explore.scss';
Component.registerHooks(['beforeRouteEnter', 'beforeRouteLeave']);

@Component
export default class EventRetrievalNew extends tsc<{ source: APIType }> {
  /** 来源 */
  @Prop({ default: APIType.MONITOR }) source: APIType;
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

  @Ref('eventRetrievalLayout') eventRetrievalLayoutRef: EventRetrievalLayout;
  @Ref('favoriteContainer') favoriteContainerRef: FavoriteContainer;

  timer = null;
  loading = false;

  compare: {
    type: 'none';
    value: true;
  };

  /** 当前选择的收藏 */
  currentFavorite = null;

  formData: IFormData = {
    data_source_label: 'custom',
    data_type_label: 'event',
    table: '',
    query_string: '*',
    where: [],
    group_by: [],
    filter_dict: {},
  };

  dataIdList = [];

  @ProvideReactive('fieldList')
  fieldList = [];

  /** 标识 KV 模式下，需要跳转到其他页面的字段。 */
  sourceEntities = [];

  cacheTimeRange = [];
  isShowFavorite = true;

  /**
   * @description 将 fieldList 数组 结构转换为 kv 结构，并将 is_dimensions 为 true 拼接 dimensions. 操作前置
   * @description 用于在 KV 模式下，获取 字段类型 Icon
   */
  @ProvideReactive('fieldMapByField')
  get fieldMapByField() {
    if (!this.fieldList?.length) {
      return { source: {}, target: {} };
    }
    return this.fieldList.reduce(
      (prev, curr) => {
        let finalName = curr.name;
        if (curr.is_dimensions) {
          finalName = `dimensions.${curr.name}`;
        }
        const item = { ...curr, finalName };
        prev.source[curr.name] = item;
        prev.target[finalName] = item;
        return prev;
      },
      {
        source: {},
        target: {},
      }
    );
  }

  /**
   * @description 将 sourceEntities 数组 结构转换为 kv 结构
   * @description 用于在 KV 模式下，判断字段是否开启 跳转到其他页面 入口
   */
  @ProvideReactive('entitiesMapByField')
  get entitiesMapByField() {
    if (!this.sourceEntities?.length) {
      return {};
    }
    return this.sourceEntities.reduce((prev, curr) => {
      const { fields } = curr || {};
      if (!fields?.length) return prev;
      for (const field of fields) {
        const finalName = this.fieldMapByField?.source?.[field]?.finalName || field;
        prev[finalName] = curr;
      }
      return prev;
    }, {});
  }

  /** 公共参数 */
  @ProvideReactive('commonParams')
  get commonParams() {
    return {
      query_configs: [
        {
          ...this.formData,
        },
      ],
      start_time: this.formatTimeRange[0],
      end_time: this.formatTimeRange[1],
    };
  }

  @Watch('commonParams')
  watchCommonParams() {
    this.setRouteParams();
  }

  @Provide('handleTimeRangeChange')
  handleTimeRangeChange(timeRange: TimeRangeType) {
    this.showRestore = false;
    this.timeRange = timeRange;
    this.getViewConfig();
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
    this.getViewConfig();
  }

  /**
   * @description 恢复数据时间间隔
   */
  @Provide('handleRestoreEvent')
  handleRestoreEventForChart() {
    this.handleTimeRangeChange(JSON.parse(JSON.stringify(this.cacheTimeRange)));
  }

  handleDataIdChange(dataId: string) {
    this.formData.table = dataId;
    this.getViewConfig();
  }

  async handleEventTypeChange(dataType: { data_source_label: string; data_type_label: string }) {
    this.formData.data_source_label = dataType.data_source_label;
    this.formData.data_type_label = dataType.data_type_label;
    await this.getDataIdList();
    await this.getViewConfig();
  }

  handleImmediateRefresh() {
    this.refreshImmediate = random(4);
    this.getViewConfig();
  }

  handleRefreshChange(value: number) {
    this.refreshInterval = value;
    this.setRouteParams();
    this.timer && clearInterval(this.timer);
    if (value > -1) {
      this.timer = setInterval(() => {
        this.handleImmediateRefresh();
      }, value);
    }
  }

  handleTimezoneChange(timezone: string) {
    this.timezone = timezone;
  }

  async getDataIdList(init = true) {
    const list = await getDataSourceConfig({
      data_source_label: this.formData.data_source_label,
      data_type_label: this.formData.data_type_label,
    }).catch(() => []);
    this.dataIdList = list;
    if (init) {
      this.formData.table = list[0]?.id || '';
    }
  }

  async getViewConfig() {
    if (!this.formData.table) {
      this.fieldList = [];
      this.sourceEntities = [];
      return;
    }
    this.loading = true;
    const data = await eventViewConfig({
      data_sources: [
        {
          data_source_label: this.formData.data_source_label,
          data_type_label: this.formData.data_type_label,
          table: this.formData.table,
        },
      ],
      start_time: this.formatTimeRange[0],
      end_time: this.formatTimeRange[1],
    }).catch(() => ({ display_fields: [], entities: [], fields: [] }));
    this.loading = false;
    this.fieldList = data.fields || data.field;
    this.sourceEntities = data.entities || [];
  }

  handleCloseDimensionPanel() {
    this.eventRetrievalLayoutRef.handleClickShrink(false);
  }

  async mounted() {
    const isShowFavorite =
      JSON.parse(localStorage.getItem('bk_monitor_data_favorite_show') || 'false') || !!this.$route.query?.favorite_id;
    this.isShowFavorite = isShowFavorite;
    this.getRouteParams();
    await this.getDataIdList(!this.formData.table);
    await this.getViewConfig();
  }

  async getRetrievalFilterValueData(params: IGetValueFnParams = {}) {
    return getEventTopK({
      limit: params?.limit || 5,
      query_configs: [
        {
          data_source_label: this.formData.data_source_label,
          data_type_label: this.formData.data_type_label,
          table: this.formData.table,
          filter_dict: {},
          where: params?.where || [],
          query_string: params?.queryString || '*',
        },
      ],
      fields: params?.fields || [],
      start_time: this.formatTimeRange[0],
      end_time: this.formatTimeRange[1],
    })
      .then(res => {
        const data = res?.[0] || {};
        console.log(res);
        return {
          count: +data?.distinct_count || 0,
          list:
            data?.list?.map(item => ({
              id: item.value,
              name: item.alias,
            })) || [],
        };
      })
      .catch(() => {
        return {
          count: 0,
          list: [],
        };
      });
  }

  /** 兼容以前的事件检索URL格式 */
  getRouteParams() {
    const { targets, from, to, timezone, refreshInterval } = this.$route.query;
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
                  where,
                  query_string: queryString,
                  group_by: groupBy,
                  filter_dict: filterDict,
                },
              ],
            },
          },
        ] = targetsList;
        this.formData = {
          data_type_label,
          data_source_label,
          table: result_table_id,
          where: where || [],
          query_string: queryString || '',
          group_by: groupBy || [],
          filter_dict: filterDict || {},
        };

        this.timeRange = from ? [from as string, to as string] : DEFAULT_TIME_RANGE;
        this.timezone = (timezone as string) || getDefaultTimezone();
        this.refreshInterval = Number(refreshInterval) || -1;
      } catch (error) {
        console.log('route query:', error);
      }
    }
  }

  setRouteParams() {
    const { table: result_table_id, ...other } = this.formData;
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
                ...other,
                result_table_id,
              },
            ],
          },
        },
      ]),
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

  handleWhereChange(where) {
    this.formData.where = where;
  }

  @Provide('handleConditionChange')
  handleConditionChange(condition: IWhereItem[]) {
    this.formData.where = mergeWhereList(this.formData.where, condition);
  }

  /** 选择收藏或者新检索 */
  handleSelectFavorite(data) {
    this.currentFavorite = data;
    if (data) {
      // 选择收藏
      const { compareValue, queryConfig } = data;
      // 兼容以前的
      const { result_table_id, ...params } = queryConfig;
      this.formData = {
        ...params,
        table: result_table_id,
      };
      this.timeRange = compareValue.tools.timeRange;
      this.refreshInterval = compareValue.tools.refleshInterval || compareValue.tools.refreshInterval;
      this.timezone = compareValue.tools.timezone;
      this.compare = compareValue.compare;
    } else {
      // 选择检索
      this.formData = {
        data_source_label: 'custom',
        data_type_label: 'event',
        table: '',
        query_string: '*',
        where: [],
        group_by: [],
        filter_dict: {},
      };
      this.timeRange = DEFAULT_TIME_RANGE;
      this.refreshInterval = -1;
      this.timezone = getDefaultTimezone();
    }
  }

  favoriteShowChange(show: boolean) {
    this.isShowFavorite = show;
    localStorage.setItem('bk_monitor_data_favorite_show', `${show}`);
  }

  handleFavorite() {
    const { table, ...params } = this.formData;
    this.favoriteContainerRef.handleFavorite({
      queryConfig: {
        ...params,
        result_table_id: table,
      },
      compareValue: {
        compare: this.compare,
        tools: {
          timeRange: this.timeRange,
          refreshInterval: this.refreshInterval,
          timezone: this.timezone,
        },
      },
    });
  }

  render() {
    return (
      <div class='event-explore'>
        <div
          style={{ display: this.isShowFavorite ? 'block' : 'none' }}
          class='left-favorite-panel'
        >
          <FavoriteContainer
            ref='favoriteContainer'
            dataId={this.formData.table}
            favoriteSearchType='event'
            isShowFavorite={this.isShowFavorite}
            onSelectFavorite={this.handleSelectFavorite}
            onShowChange={this.favoriteShowChange}
          />
        </div>

        <div class='right-main-panel'>
          <EventRetrievalHeader
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
          <div class='event-retrieval-content'>
            <RetrievalFilter
              fields={this.fieldList}
              getValueFn={this.getRetrievalFilterValueData}
              where={this.formData.where}
              onFavorite={this.handleFavorite}
              onWhereChange={this.handleWhereChange}
            />
            <EventRetrievalLayout
              ref='eventRetrievalLayout'
              class='content-container'
            >
              <div
                class='dimension-filter-panel'
                slot='aside'
              >
                <DimensionFilterPanel
                  condition={this.formData.where}
                  list={this.fieldList}
                  listLoading={this.loading}
                  onClose={this.handleCloseDimensionPanel}
                  onConditionChange={this.handleConditionChange}
                />
              </div>
              <div class='result-content-panel'>
                <EventExploreView
                  queryConfig={this.formData}
                  source={this.source}
                />
              </div>
            </EventRetrievalLayout>
          </div>
        </div>
      </div>
    );
  }
}
