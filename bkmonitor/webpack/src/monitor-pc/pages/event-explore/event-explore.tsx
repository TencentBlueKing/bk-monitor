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
import { Component, Emit, InjectReactive, Prop, ProvideReactive, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

// import { getDataSourceConfig } from 'monitor-api/modules/grafana';
import { eventGenerateQueryString } from 'monitor-api/modules/data_explorer';
import { copyText, Debounce, deepClone } from 'monitor-common/utils';

import RetrievalFilter from '../../components/retrieval-filter/retrieval-filter';
import {
  type IGetValueFnParams,
  ECondition,
  EFieldType,
  EMethod,
  EMode,
  mergeWhereList,
} from '../../components/retrieval-filter/utils';
import { handleTransformToTimestamp } from '../../components/time-range/utils';
import { APIType, getEventViewConfig, RetrievalFilterCandidateValue } from './api-utils';
import DimensionFilterPanel from './components/dimension-filter-panel';
import EventExploreView from './components/event-explore-view';
import EventRetrievalLayout from './components/event-retrieval-layout';
import EventSourceSelect from './components/event-source-select';
import {
  type ConditionChangeEvent,
  type ExploreEntitiesMap,
  type ExploreFieldMap,
  type HideFeatures,
  type IFormData,
  ExploreSourceTypeEnum,
} from './typing';

import type { IWhereItem } from '../../components/retrieval-filter/utils';
import type { TimeRangeType } from '../../components/time-range/time-range';
import type { IFavList } from '../data-retrieval/typings';
import type { IViewOptions } from '../monitor-k8s/typings/book-mark';

import './event-explore.scss';
Component.registerHooks(['beforeRouteEnter', 'beforeRouteLeave']);

interface IEvent {
  onCommonWhereChange: (where: IWhereItem[]) => void;
  onEventSourceTypeChange: (v: ExploreSourceTypeEnum[]) => void;
  onFavorite: (isEdit: boolean) => void;
  onFilterModeChange: (filterMode: EMode) => void;
  onQueryStringChange: (queryString: string) => void;
  onQueryStringInputChange: (val: string) => void;
  onSetRouteParams: (otherQuery: Record<string, any>) => void;
  onShowResidentBtnChange?: (v: boolean) => void;
  onWhereChange: (where: IWhereItem[]) => void;
}

interface IProps {
  commonWhere?: IWhereItem[];
  currentFavorite?: IFavList.favList;
  dataId?: string;
  dataSourceLabel?: string;
  dataTypeLabel?: string;
  defaultShowResidentBtn?: boolean;
  eventSourceType?: ExploreSourceTypeEnum[];
  favoriteList?: IFavList.favGroupList[];
  filter_dict?: IFormData['filter_dict'];
  filterMode?: EMode;
  group_by?: IFormData['group_by'];
  hideFeatures?: HideFeatures;
  queryString?: string;
  source: APIType;
  where?: IWhereItem[];
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
  @Prop({ default: () => [ExploreSourceTypeEnum.ALL], type: Array }) eventSourceType: ExploreSourceTypeEnum[];
  /** UI查询 */
  @Prop({ default: () => [], type: Array }) where: IFormData['where'];
  /** 不显示的功能列表  */
  @Prop({ default: () => [], type: Array }) hideFeatures: HideFeatures;
  /** 常驻筛选 */
  @Prop({ default: () => [], type: Array }) commonWhere: IWhereItem[];
  /** 维度列表 */
  @Prop({ default: () => [], type: Array }) group_by: IFormData['group_by'];
  /** 过滤条件 */
  @Prop({ default: () => ({}), type: Object }) filter_dict: IFormData['filter_dict'];
  @Prop({ default: () => [], type: Array }) favoriteList: IFavList.favGroupList[];
  @Prop({ default: null, type: Object }) currentFavorite: IFavList.favList;
  @Prop({ default: false, type: Boolean }) defaultShowResidentBtn: boolean;

  // 数据时间间隔
  @InjectReactive('timeRange') timeRange: TimeRangeType;
  // 时区
  @InjectReactive('timezone') timezone: string;
  // 刷新间隔
  @InjectReactive('refreshInterval') refreshInterval;
  // 是否立即刷新
  @InjectReactive('refreshImmediate') refreshImmediate: string;
  // 视图变量
  @InjectReactive('viewOptions') viewOptions: IViewOptions;

  @Ref('eventRetrievalLayout') eventRetrievalLayoutRef: EventRetrievalLayout;
  @Ref('eventSourceList') eventSourceListRef: EventSourceSelect;

  loading = false;

  /** 维度列表 */
  fieldList = [];

  /** 标识 KV 模式下，需要跳转到其他页面的字段。 */
  sourceEntities = [];

  queryStringInput = '';

  /** 事件来源列表 */
  eventSourceList = [];

  cacheQueryConfig = null;

  queryConfig = {
    data_source_label: 'custom',
    data_type_label: 'event',
    table: '',
    query_string: '',
    where: [],
    group_by: [],
    filter_dict: {},
  };

  /** 事件源popover实例 */
  eventSourcePopoverInstance = null;
  localEventSourceType = [];
  retrievalFilterCandidateValue: RetrievalFilterCandidateValue = null;

  /** 常驻筛选唯一ID */
  get residentSettingOnlyId() {
    const RESIDENT_SETTING = 'RESIDENT_SETTING';
    if (this.source === APIType.MONITOR) {
      return `${this.source}_${this.dataId}_${RESIDENT_SETTING}`;
    }
    return `${this.source}_${this.commonParams.app_name}_${this.commonParams.service_name}_${RESIDENT_SETTING}`;
  }

  formatTimeRange = [];

  /** 公共参数 */
  @ProvideReactive('commonParams')
  get commonParams() {
    return {
      query_configs: [this.queryConfig],
      app_name: this.viewOptions?.filters?.app_name,
      service_name: this.viewOptions?.filters?.service_name,
      start_time: this.formatTimeRange[0],
      end_time: this.formatTimeRange[1],
    };
  }

  /**
   * @description 将 fieldList 数组 结构转换为 kv 结构，并将 is_dimensions 为 true 拼接 dimensions. 操作前置
   * @description 用于在 KV 模式下，获取 字段类型 Icon，及语句模式查询时使用
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
  get entitiesMapByField(): ExploreEntitiesMap[] {
    if (!this.sourceEntities?.length) {
      return [];
    }
    return this.sourceEntities.reduce((prev, curr) => {
      const { fields, dependent_fields = [] } = curr || {};
      if (!fields?.length) return prev;
      const finalDependentFields = dependent_fields.map(field => this.fieldMapByField?.source?.[field]?.finalName);
      const map = {};
      for (const field of fields) {
        const finalName = this.fieldMapByField?.source?.[field]?.finalName || field;
        map[finalName] = {
          ...curr,
          dependent_fields: finalDependentFields,
        };
      }
      prev.push(map);
      return prev;
    }, []);
  }

  @Watch('refreshImmediate')
  handleRefreshImmediateChange() {
    this.formatTimeRange = handleTransformToTimestamp(this.timeRange);
    this.getViewConfig();
  }

  @Watch('dataId')
  handleDataIdChange() {
    this.getViewConfig();
    this.updateQueryConfig();
  }

  @Watch('dataSourceLabel')
  handleDataSourceLabelChange() {
    this.getViewConfig();
    this.updateQueryConfig();
  }

  @Watch('dataTypeLabel')
  handleDataTypeLabelChange() {
    this.getViewConfig();
    this.updateQueryConfig();
  }

  @Watch('where')
  handleWatchWhereChange() {
    this.updateQueryConfig();
  }

  @Watch('commonWhere')
  handleWatchCommonWhereChange() {
    this.updateQueryConfig();
  }

  @Watch('queryString')
  handleWatchQueryStringChange() {
    this.updateQueryConfig();
  }

  @Watch('timeRange')
  handleTimeRangeChange() {
    this.formatTimeRange = handleTransformToTimestamp(this.timeRange);
    this.getViewConfig();
  }

  @Watch('eventSourceType')
  handleWatchEventSourceTypeChange() {
    this.getViewConfig();
    this.updateQueryConfig();
  }

  @Emit('whereChange')
  handleWhereChange(where: IFormData['where']) {
    return where;
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

  @Emit('setRouteParams')
  setRouteParams(otherQuery = {}) {
    return otherQuery;
  }

  handleModeChange(mode: EMode) {
    this.$emit('filterModeChange', mode);
    if (JSON.stringify(this.cacheQueryConfig) !== JSON.stringify(this.queryConfig)) {
      this.cacheQueryConfig = deepClone(this.queryConfig);
      this.updateQueryConfig();
    }
  }

  mounted() {
    this.retrievalFilterCandidateValue = new RetrievalFilterCandidateValue();
    this.formatTimeRange = handleTransformToTimestamp(this.timeRange);
    this.getViewConfig();
    this.updateQueryConfig();
  }
  @Debounce(100)
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
        app_name: this.viewOptions?.filters?.app_name,
        service_name: this.viewOptions?.filters?.service_name,
        start_time: this.formatTimeRange[0],
        end_time: this.formatTimeRange[1],
        ...(this.eventSourceType.length && !this.eventSourceType.includes(ExploreSourceTypeEnum.ALL)
          ? { sources: this.eventSourceType }
          : {}),
      },
      this.source
    ).catch(() => ({ display_fields: [], entities: [], field: [] }));
    this.loading = false;
    this.fieldList = data.field.map(item => {
      const pinyinStr = this.$bkToPinyin(item.alias, true, '') || '';
      return {
        ...item,
        pinyinStr,
      };
    });
    this.eventSourceList =
      data.sources?.map(item => ({
        id: item.value,
        name: item.alias,
      })) || [];
    this.sourceEntities = data.entities || [];
  }

  /** 关闭维度过滤面板 */
  handleCloseDimensionPanel() {
    this.eventRetrievalLayoutRef.handleClickShrink(false);
  }

  async getRetrievalFilterValueData(params: IGetValueFnParams = {}) {
    return this.retrievalFilterCandidateValue.getFieldsOptionValuesProxy(
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
        start_time: this.formatTimeRange[0],
        end_time: this.formatTimeRange[1],
        isInit__: params?.isInit__,
      },
      this.source
    );
  }

  /** 条件变化触发 */
  handleConditionChange(item: ConditionChangeEvent) {
    const { key, method, value } = item;
    if (this.filterMode === EMode.ui) {
      this.handleWhereChange(
        mergeWhereList(this.where, [{ condition: ECondition.and, key, method, value: [value || ''] }])
      );
      return;
    }
    const finalKey = this.fieldMapByField.source?.[key].finalName;
    let endStr = `NOT ${finalKey} : "${value || ''}"`;
    if (method === EMethod.eq) {
      endStr = `${finalKey} : "${value || ''}"`;
    }
    this.handleQueryStringChange(this.queryString ? `${this.queryString} AND ${endStr}` : `${endStr}`);
  }

  @Emit('commonWhereChange')
  handleCommonWhereChange(where: IWhereItem[]) {
    return where;
  }

  @Emit('showResidentBtnChange')
  handleShowResidentBtnChange(isShow: boolean) {
    return isShow;
  }

  /** 展示事件源选择弹窗 */
  handleShowEventSourcePopover(e: Event) {
    if (this.eventSourcePopoverInstance) {
      this.eventSourcePopoverInstance.destroy();
      this.eventSourcePopoverInstance = null;
    }
    this.localEventSourceType = this.eventSourceType;
    this.eventSourcePopoverInstance = this.$bkPopover(e.currentTarget, {
      content: this.eventSourceListRef.$el,
      placement: 'bottom',
      boundary: 'viewport',
      trigger: 'click',
      arrow: false,
      interactive: true,
      distance: -2,
      theme: 'light event-source-select-popover',
      onHidden: this.handleEventSourceConfirm,
    });
    this.eventSourcePopoverInstance?.show(200);
  }

  handleEventSourceChange(source: ExploreSourceTypeEnum[]) {
    this.localEventSourceType = source;
  }

  handleEventSourceConfirm() {
    if (!this.localEventSourceType.length && this.eventSourceType.includes(ExploreSourceTypeEnum.ALL)) return;
    if (
      this.localEventSourceType.includes(ExploreSourceTypeEnum.ALL) &&
      this.eventSourceType.includes(ExploreSourceTypeEnum.ALL)
    )
      return;
    this.$emit(
      'eventSourceTypeChange',
      !this.localEventSourceType.length ? [ExploreSourceTypeEnum.ALL] : this.localEventSourceType
    );
  }

  handleEventSourceClose() {
    this.eventSourcePopoverInstance?.hide();
  }

  /**
   * @description 清空筛选条件
   *
   **/
  handleClearSearch() {
    this.handleQueryStringChange('');
    this.handleWhereChange([]);
  }

  /** 更新queryConfig */
  @Debounce(100)
  updateQueryConfig() {
    this.formatTimeRange = handleTransformToTimestamp(this.timeRange);
    let queryString = '';
    let where = mergeWhereList(this.where || [], this.commonWhere || []);
    if (this.filterMode === EMode.ui) {
      // 全文检索补充到query_string里
      const fullText = where.find(item => item.key === '*');
      queryString = fullText?.value[0] ? `"${fullText?.value[0]}"` : '';
      where = where.filter(item => item.key !== '*');
    } else {
      queryString = this.queryString;
      where = [];
    }
    if (
      this.source === APIType.APM &&
      this.eventSourceType &&
      !this.eventSourceType.includes(ExploreSourceTypeEnum.ALL)
    ) {
      where.push({ key: 'source', method: 'eq', condition: ECondition.and, value: this.eventSourceType });
    }
    this.queryConfig = {
      data_source_label: this.dataSourceLabel || 'custom',
      data_type_label: this.dataTypeLabel || 'event',
      table: this.dataId,
      query_string: queryString,
      where: where.filter(item => item.value.length),
      group_by: this.group_by || [],
      filter_dict: this.filter_dict || {},
    };
  }

  async handleCopyWhere(where) {
    const whereParams = where.map(w => {
      const type = this.fieldList.find(item => item.name === w.key)?.type;
      return {
        ...w,
        value:
          EFieldType.integer === type
            ? w.value.map(v => {
                const numberV = Number(v);
                return numberV === 0 ? 0 : numberV || v;
              })
            : w.value,
      };
    });
    const copyStr = await eventGenerateQueryString({
      where: whereParams,
    }).catch(() => {
      return '';
    });
    if (copyStr) {
      copyText(copyStr, msg => {
        this.$bkMessage({
          message: msg,
          theme: 'error',
        });
        return;
      });
      this.$bkMessage({
        message: this.$t('复制成功'),
        theme: 'success',
      });
    }
  }

  render() {
    return (
      <div class='event-explore'>
        {this.$scopedSlots.favorite?.('')}
        <div class='right-main-panel'>
          {this.$scopedSlots.header?.('')}
          <div
            style={{
              height: this.hideFeatures.includes('header') ? 'calc(100% - 0px)' : 'calc(100% - 52px)',
            }}
            class='event-retrieval-content'
          >
            {this.loading ? (
              <div class='skeleton-element filter-skeleton' />
            ) : (
              <RetrievalFilter
                commonWhere={this.commonWhere}
                dataId={this.dataId}
                defaultShowResidentBtn={this.defaultShowResidentBtn}
                favoriteList={this.favoriteList as any}
                fields={this.fieldList}
                filterMode={this.filterMode}
                getValueFn={this.getRetrievalFilterValueData}
                isShowFavorite={!this.hideFeatures.includes('favorite') && this.source === APIType.MONITOR}
                queryString={this.queryString}
                residentSettingOnlyId={this.residentSettingOnlyId}
                selectFavorite={this.currentFavorite}
                source={this.source}
                where={this.where}
                onCommonWhereChange={this.handleCommonWhereChange}
                onCopyWhere={this.handleCopyWhere}
                onFavorite={this.handleFavorite}
                onModeChange={this.handleModeChange}
                onQueryStringChange={this.handleQueryStringChange}
                onQueryStringInputChange={this.handleQueryStringInputChange}
                onSearch={this.updateQueryConfig}
                onShowResidentBtnChange={this.handleShowResidentBtnChange}
                onWhereChange={this.handleWhereChange}
              />
            )}

            <EventRetrievalLayout
              ref='eventRetrievalLayout'
              class='content-container'
            >
              <div
                class='dimension-filter-panel'
                slot='aside'
              >
                <DimensionFilterPanel
                  condition={this.queryConfig.where}
                  eventSourceType={this.eventSourceType}
                  hasSourceSelect={this.source === APIType.APM}
                  list={this.fieldList}
                  listLoading={this.loading}
                  queryString={this.queryConfig.query_string}
                  source={this.source}
                  onClose={this.handleCloseDimensionPanel}
                  onConditionChange={this.handleConditionChange}
                  onShowEventSourcePopover={this.handleShowEventSourcePopover}
                />
              </div>
              <div class='result-content-panel'>
                <EventExploreView
                  entitiesMapList={this.entitiesMapByField}
                  eventSourceType={this.eventSourceType}
                  fieldMap={this.fieldMapByField}
                  queryConfig={this.queryConfig}
                  refreshImmediate={this.refreshImmediate}
                  source={this.source}
                  timeRange={this.timeRange}
                  onClearSearch={this.handleClearSearch}
                  onConditionChange={this.handleConditionChange}
                  onSearch={this.updateQueryConfig}
                  onSetRouteParams={this.setRouteParams}
                  onShowEventSourcePopover={this.handleShowEventSourcePopover}
                />
              </div>
            </EventRetrievalLayout>
          </div>
        </div>

        <div style='display: none;'>
          <EventSourceSelect
            ref='eventSourceList'
            list={this.eventSourceList}
            value={this.localEventSourceType}
            onSelect={this.handleEventSourceChange}
          />
        </div>
      </div>
    );
  }
}
