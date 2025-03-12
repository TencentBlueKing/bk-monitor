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
import { Component, ProvideReactive, Ref, Prop, Watch, Emit, InjectReactive } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

// import { getDataSourceConfig } from 'monitor-api/modules/grafana';

import { Debounce } from 'monitor-common/utils';

import RetrievalFilter from '../../components/retrieval-filter/retrieval-filter';
import { EMode, mergeWhereList, type IGetValueFnParams } from '../../components/retrieval-filter/utils';
import { handleTransformToTimestamp } from '../../components/time-range/utils';
import { APIType, getEventTopK, getEventViewConfig } from './api-utils';
import DimensionFilterPanel from './components/dimension-filter-panel';
import EventExploreView from './components/event-explore-view';
import EventRetrievalLayout from './components/event-retrieval-layout';

import type { IWhereItem } from '../../components/retrieval-filter/utils';
import type { TimeRangeType } from '../../components/time-range/time-range';
import type { IFavList } from '../data-retrieval/typings';
import type { IViewOptions } from '../monitor-k8s/typings/book-mark';
import type { ExploreEntitiesMap, ExploreFieldMap, IFormData } from './typing';

import './event-explore.scss';
Component.registerHooks(['beforeRouteEnter', 'beforeRouteLeave']);

interface IProps {
  source: APIType;
  dataId?: string;
  dataTypeLabel?: string;
  dataSourceLabel?: string;
  queryString?: string;
  where?: IWhereItem[];
  commonWhere?: IWhereItem[];
  group_by?: IFormData['group_by'];
  filter_dict?: IFormData['filter_dict'];
  favoriteList?: IFavList.favGroupList[];
  currentFavorite?: IFavList.favList;
  filterMode?: EMode;
}

interface IEvent {
  onWhereChange: (where: IWhereItem[]) => void;
  onQueryStringChange: (queryString: string) => void;
  onFavorite: (isEdit: boolean) => void;
  onFilterModeChange: (filterMode: EMode) => void;
  onQueryStringInputChange: (val: string) => void;
}
@Component
export default class EventExplore extends tsc<
  IProps,
  IEvent,
  {
    favorite?: string;
    header?: string;
  }
> {
  // /** 来源 */
  // @ProvideReactive('source')
  @Prop({ default: APIType.MONITOR }) source: APIType;

  /** 数据Id */
  @Prop({ default: '' }) dataId;
  @Prop({ default: EMode.ui }) filterMode: EMode;
  /** 查询语句 */
  @Prop({ default: '' }) queryString;
  @Prop({ default: 'event' }) dataTypeLabel: string;
  @Prop({ default: 'custom' }) dataSourceLabel: string;
  /** UI查询 */
  @Prop({ default: () => [], type: Array }) where: IFormData['where'];
  /** 常驻筛选 */
  @Prop({ default: () => [], type: Array }) commonWhere: IWhereItem[];
  /** 维度列表 */
  @Prop({ default: () => [], type: Array }) group_by: IFormData['group_by'];
  /** 过滤条件 */
  @Prop({ default: () => ({}), type: Object }) filter_dict: IFormData['filter_dict'];
  @Prop({ default: () => [], type: Array }) favoriteList: IFavList.favGroupList[];
  @Prop({ default: null, type: Object }) currentFavorite: IFavList.favList;

  // 数据时间间隔
  @InjectReactive('timeRange') timeRange: TimeRangeType;
  // 时区
  @InjectReactive('timezone') timezone: string;
  // 刷新间隔
  @InjectReactive('refleshInterval') refreshInterval;
  // 是否立即刷新
  @InjectReactive('refleshImmediate') refreshImmediate: string;
  // 视图变量
  @InjectReactive('viewOptions') viewOptions: IViewOptions;

  @Ref('eventRetrievalLayout') eventRetrievalLayoutRef: EventRetrievalLayout;

  loading = false;

  /** 维度列表 */
  fieldList = [];

  /** 标识 KV 模式下，需要跳转到其他页面的字段。 */
  sourceEntities = [];

  queryStringInput = '';

  /**
   * @description 将 fieldList 数组 结构转换为 kv 结构，并将 is_dimensions 为 true 拼接 dimensions. 操作前置
   * @description 用于在 KV 模式下，获取 字段类型 Icon
   */
  get fieldMapByField(): ExploreFieldMap {
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
   * @description 将 sourceEntities 数组 结构转换为 kv 结构，并将 is_dimensions 为 true 拼接 dimensions.后的值作为 key
   * @description 用于在 KV 模式下，判断字段是否开启 跳转到其他页面 入口
   */
  get entitiesMapByField(): ExploreEntitiesMap {
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

  get queryConfig() {
    return {
      data_source_label: this.dataSourceLabel || 'custom',
      data_type_label: this.dataTypeLabel || 'event',
      table: this.dataId,
      query_string: this.filterMode === EMode.queryString ? this.queryString : '',
      where: this.filterMode === EMode.ui ? mergeWhereList(this.where || [], this.commonWhere || []) : [],
      group_by: this.group_by || [],
      filter_dict: this.filter_dict || {},
    };
  }

  /** 公共参数 */
  @ProvideReactive('commonParams')
  get commonParams() {
    const formatTimeRange = handleTransformToTimestamp(this.timeRange);
    return {
      query_configs: [this.queryConfig],
      app_name: this.viewOptions?.filters?.app_name,
      service_name: this.viewOptions?.filters?.service_name,
      start_time: formatTimeRange[0],
      end_time: formatTimeRange[1],
    };
  }

  @Watch('dataId')
  async handleDataIdChange() {
    this.getViewConfig();
  }

  @Watch('dataSourceLabel')
  async handleDataSourceLabelChange() {
    this.getViewConfig();
  }

  @Watch('dataTypeLabel')
  async handleDataTypeLabelChange() {
    this.getViewConfig();
  }

  @Watch('timeRange')
  async handleTimeRangeChange() {
    this.getViewConfig();
  }
  mounted() {
    this.getViewConfig();
  }
  @Debounce(100)
  async getViewConfig() {
    if (!this.dataId) {
      this.fieldList = [];
      this.sourceEntities = [];
      return;
    }
    this.loading = true;
    const formatTimeRange = handleTransformToTimestamp(this.timeRange);
    const data = await getEventViewConfig(
      {
        data_sources: [
          {
            data_source_label: this.dataSourceLabel,
            data_type_label: this.dataTypeLabel,
            table: this.dataId,
          },
        ],
        app_name: this.viewOptions?.filters?.app_name,
        service_name: this.viewOptions?.filters?.service_name,
        start_time: formatTimeRange[0],
        end_time: formatTimeRange[1],
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

  async getRetrievalFilterValueData(params: IGetValueFnParams = {}) {
    const formatTimeRange = handleTransformToTimestamp(this.timeRange);
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
            group_by: this.group_by,
            query_string: params?.queryString || '',
          },
        ],
        app_name: this.viewOptions?.filters?.app_name,
        service_name: this.viewOptions?.filters?.service_name,
        fields: params?.fields || [],
        start_time: formatTimeRange[0],
        end_time: formatTimeRange[1],
      },
      this.source
    )
      .then(res => {
        const data = res?.[0] || {};
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

  @Emit('whereChange')
  handleWhereChange(where: IFormData['where']) {
    return where;
  }

  handleConditionChange(condition: IWhereItem[]) {
    this.handleWhereChange(mergeWhereList(this.where, condition));
  }

  @Emit('queryStringChange')
  handleQueryStringChange(val: string) {
    return val;
  }

  @Emit('queryStringInputChange')
  handleQueryStringInputChange(val) {
    this.queryStringInput = val;
    return val;
  }

  @Emit('favorite')
  handleFavorite(isEdit: boolean) {
    return isEdit;
  }

  @Emit('filterModeChange')
  handleModeChange(mode: EMode) {
    return mode;
  }

  render() {
    return (
      <div class='event-explore'>
        {this.$scopedSlots.favorite?.('')}
        <div class='right-main-panel'>
          {this.$scopedSlots.header?.('')}
          <div class='event-retrieval-content'>
            <RetrievalFilter
              favoriteList={this.favoriteList as any}
              fields={this.fieldList}
              filterMode={this.filterMode}
              getValueFn={this.getRetrievalFilterValueData}
              isQsOperateWrapBottom={this.source === APIType.APM}
              queryString={this.queryString}
              selectFavorite={this.currentFavorite}
              where={this.where}
              onFavorite={this.handleFavorite}
              onModeChange={this.handleModeChange}
              onQueryStringChange={this.handleQueryStringChange}
              onQueryStringInputChange={this.handleQueryStringInputChange}
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
                  entitiesMap={this.entitiesMapByField}
                  fieldMap={this.fieldMapByField}
                  queryConfig={this.queryConfig}
                  refreshImmediate={this.refreshImmediate}
                  source={this.source}
                  onConditionChange={this.handleConditionChange}
                />
              </div>
            </EventRetrievalLayout>
          </div>
        </div>
      </div>
    );
  }
}
