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
import { Component, Provide, ProvideReactive, Ref, Prop, Watch, Emit, Inject } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

// import { getDataSourceConfig } from 'monitor-api/modules/grafana';

import RetrievalFilter from '../../components/retrieval-filter/retrieval-filter';
import { EMode, mergeWhereList, type IGetValueFnParams } from '../../components/retrieval-filter/utils';
import { DEFAULT_TIME_RANGE, handleTransformToTimestamp } from '../../components/time-range/utils';
import { getDefaultTimezone } from '../../i18n/dayjs';
import { APIType, getEventTopK, getEventViewConfig } from './api-utils';
import DimensionFilterPanel from './components/dimension-filter-panel';
import EventExploreView from './components/event-explore-view';
import EventRetrievalLayout from './components/event-retrieval-layout';

import type { IWhereItem } from '../../components/retrieval-filter/utils';
import type { TimeRangeType } from '../../components/time-range/time-range';
import type { IFormData } from './typing';

import './event-explore.scss';
Component.registerHooks(['beforeRouteEnter', 'beforeRouteLeave']);
interface IEvent {
  onWhereChange: (where: IFormData['where']) => void;
  onQueryStringChange: (queryString: string) => void;
}
@Component
export default class EventRetrievalNew extends tsc<
  {
    source: APIType;
    dataId: string;
    dataTypeLabel: string;
    dataSourceLabel: string;
    queryString: string;
    where: IFormData['where'];
    group_by: IFormData['group_by'];
    filter_dict: IFormData['filter_dict'];
  },
  IEvent
> {
  // /** 来源 */
  // @ProvideReactive('source')
  @Prop({ default: APIType.MONITOR }) source: APIType;

  /** 数据Id */
  @Prop({ default: '' }) dataId;
  /** 查询语句 */
  @Prop({ default: '' }) queryString;
  @Prop({ default: 'event' }) dataTypeLabel: string;
  @Prop({ default: 'custom' }) dataSourceLabel: string;
  /** UI查询 */
  @Prop({ default: () => [], type: Array }) where: IFormData['where'];
  /** 维度列表 */
  @Prop({ default: () => [], type: Array }) group_by: IFormData['group_by'];
  /** 过滤条件 */
  @Prop({ default: () => ({}), type: Object }) filter_dict: IFormData['filter_dict'];

  // 数据时间间隔
  @Inject('timeRange') timeRange: TimeRangeType;
  // 时区
  @Inject('timezone') timezone: string;
  // 刷新间隔
  @Inject('refleshInterval') refreshInterval;
  // 是否立即刷新
  @Inject('refleshImmediate') refreshImmediate;

  @ProvideReactive('formatTimeRange')
  get formatTimeRange() {
    return handleTransformToTimestamp(this.timeRange);
  }

  @Ref('eventRetrievalLayout') eventRetrievalLayoutRef: EventRetrievalLayout;

  timer = null;
  loading = false;

  compare: {
    type: 'none';
    value: true;
  };

  /** 当前选择的收藏 */
  currentFavorite = null;

  /** 维度列表 */
  @ProvideReactive('fieldList')
  fieldList = [];

  /** 标识 KV 模式下，需要跳转到其他页面的字段。 */
  sourceEntities = [];

  filterMode = EMode.ui;

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
          data_source_label: this.dataSourceLabel || 'custom',
          data_type_label: this.dataTypeLabel || 'event',
          table: this.dataId,
          query_string: this.queryString,
          where: this.where || [],
          group_by: this.group_by || [],
          filter_dict: this.filter_dict || {},
        },
      ],
      start_time: this.formatTimeRange[0],
      end_time: this.formatTimeRange[1],
    };
  }

  /** 回填URL */
  @Watch('commonParams')
  watchCommonParams() {
    this.setRouteParams();
  }

  async getViewConfig() {
    if (!this.dataId) {
      this.fieldList = [];
      this.sourceEntities = [];
      return;
    }
    this.loading = true;
    const data = await getEventViewConfig(
      {
        data_sources: [
          {
            data_source_label: this.dataSourceLabel,
            data_type_label: this.dataTypeLabel,
            table: this.dataId,
          },
        ],
        start_time: this.formatTimeRange[0],
        end_time: this.formatTimeRange[1],
      },
      this.source
    ).catch(() => ({ display_fields: [], entities: [], fields: [] }));
    this.loading = false;
    this.fieldList = data.fields || data.field;
    this.sourceEntities = data.entities || [];
  }

  /** 关闭维度过滤面板 */
  handleCloseDimensionPanel() {
    this.eventRetrievalLayoutRef.handleClickShrink(false);
  }

  async mounted() {
    // const isShowFavorite =
    //   JSON.parse(localStorage.getItem('bk_monitor_data_favorite_show') || 'false') || !!this.$route.query?.favorite_id;
    // this.isShowFavorite = isShowFavorite;
    this.getRouteParams();
    // await this.getDataIdList(!this.formData.table);
    await this.getViewConfig();
  }

  async getRetrievalFilterValueData(params: IGetValueFnParams = {}) {
    return getEventTopK(
      {
        limit: params?.limit || 5,
        query_configs: [
          {
            data_source_label: this.dataSourceLabel,
            data_type_label: this.dataTypeLabel,
            table: this.dataId,
            filter_dict: {},
            where: params?.where || [],
            query_string: params?.queryString || '*',
          },
        ],
        fields: params?.fields || [],
        start_time: this.formatTimeRange[0],
        end_time: this.formatTimeRange[1],
      },
      this.source
    )
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
    const { targets, from, to, timezone, refreshInterval, filterMode } = this.$route.query;
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
        this.filterMode = (
          [EMode.ui, EMode.queryString].includes(filterMode as EMode) ? filterMode : EMode.ui
        ) as EMode;
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
      filterMode: this.filterMode,
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
  @Emit('whereChange')
  handleWhereChange(where: IFormData['where']) {
    return where;
  }

  @Provide('handleConditionChange')
  handleConditionChange(condition: IWhereItem[]) {
    this.handleWhereChange(mergeWhereList(this.where, condition));
  }
  @Emit('queryStringChange')
  handleQueryStringChange(val: string) {
    return val;
  }

  handleModeChange(mode: EMode) {
    this.filterMode = mode;
  }

  render() {
    return (
      <div class='event-explore'>
        {this.$scopedSlots.favorite?.()}
        <div class='right-main-panel'>
          {this.$scopedSlots.header?.()}
          <div class='event-retrieval-content'>
            <RetrievalFilter
              favoriteList={this.favoriteList as any}
              fields={this.fieldList}
              filterMode={this.filterMode}
              getValueFn={this.getRetrievalFilterValueData}
              queryString={this.queryString}
              selectFavorite={this.currentFavorite}
              where={this.where}
              onFavorite={this.handleFavorite}
              onModeChange={this.handleModeChange}
              onQueryStringChange={this.handleQueryStringChange}
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
                  condition={this.where}
                  list={this.fieldList}
                  listLoading={this.loading}
                  onClose={this.handleCloseDimensionPanel}
                  onConditionChange={this.handleConditionChange}
                />
              </div>
              <div class='result-content-panel'>
                <EventExploreView
                  queryConfig={{
                    data_source_label: this.dataSourceLabel || 'custom',
                    data_type_label: this.dataTypeLabel || 'event',
                    table: this.dataId,
                    query_string: this.queryString,
                    where: this.where || [],
                    group_by: this.group_by || [],
                    filter_dict: this.filter_dict || {},
                  }}
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
