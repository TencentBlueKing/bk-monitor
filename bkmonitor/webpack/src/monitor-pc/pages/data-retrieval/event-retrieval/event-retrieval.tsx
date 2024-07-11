/* eslint-disable @typescript-eslint/naming-convention */
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
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getGroupByCount } from 'monitor-api/modules/data_explorer';
import { getDataSourceConfig } from 'monitor-api/modules/grafana';
// import { handleTimeRange } from '../../../utils';
import { deepClone } from 'monitor-common/utils/utils';

import { handleGotoLink } from '../../../common/constant';
import { EmptyStatusType } from '../../../components/empty-status/types';
import { handleTransformToTimestamp } from '../../../components/time-range/utils';
import FieldFiltering from '../event-retrieval/field-filtering';
import HandleBtn from '../handle-btn/handle-btn';
import { EventRetrievalViewType, FieldValue, IDataRetrievalView, IEventRetrieval, IFilterCondition } from '../typings';
import FilterCondition from './filter-condition';

import './event-retrieval.scss';

const { i18n } = window;

@Component
export default class EventRetrieval extends tsc<IEventRetrieval.IProps, IEventRetrieval.IEvent> {
  @Prop({ type: Boolean, default: false }) autoQuery: boolean;
  @Prop({ type: Boolean, default: false }) isFavoriteUpdate: boolean;
  @Prop({ type: String, default: '' }) drillKeywords: string;
  @Prop({ type: Object }) compareValue: IDataRetrievalView.ICompareValue;
  @Prop({ type: [String, Number], default: 60 }) eventInterval: EventRetrievalViewType.intervalType;
  @Prop({ type: Object }) queryConfig: IFilterCondition.VarParams;
  @Prop({ default: () => ({}), type: Object }) favCheckedValue: IDataRetrievalView.IProps['favCheckedValue'];
  @Prop({ type: Array }) chartTimeRange: EventRetrievalViewType.IEvent['onTimeRangeChange'];

  /** 收藏回显 */
  isEdit = false;

  /** 配置表单的loading 切换数据类型获取id数据时触发 */
  formLoading = false;

  /** 维度过滤loading 获取维度数据时触发 */
  gourpByLoading = false;

  /** 请求的时间范围换成你 */
  timeRangeCache: [number, number] = null;

  /** 事件类型下拉可选项 */
  eventTypeList: IEventRetrieval.IEventTypeList[] = [
    { id: 'custom_event', name: i18n.t('自定义上报事件') },
    { id: 'bk_monitor_log', name: i18n.t('日志关键字事件') },
  ];

  // 数据id | 采集id 可选列表
  dataIdList = [];

  /** 组件的值管理 */
  localValue: IEventRetrieval.ILocalValue = {
    eventType: 'custom_event',
    result_table_id: '',
    query_string: '*',
    where: [],
  };
  /** 查询语句的缓存 用于diff */
  queryStringCache = '';

  /** 维度列表 */
  groupByList = [];

  /** 查询语句提示tooltios配置 */
  tipsConfig = {
    allowHTML: true,
    width: 255,
    trigger: 'mouseenter',
    theme: 'light',
    content: '#tips-content',
    placement: 'bottom-start',
    boundary: 'window',
  };
  /** 查询语句提示文本 */
  tipsContentList: IEventRetrieval.ITipsContentListItem[] = [
    { label: i18n.t('精确匹配(支持AND、OR)：'), value: ['author:"John Smith" AND age:20'] },
    { label: i18n.t('字段名匹配(*代表通配符):'), value: ['status:active', 'title:(quick brown)'] },
    { label: i18n.t('字段名模糊匹配:'), value: ['vers\\*on:(quick brown)'] },
    { label: i18n.t('通配符匹配:'), value: ['qu?ck bro*'] },
    { label: i18n.t('正则匹配:'), value: ['name:/joh?n(ath[oa]n/'] },
    { label: i18n.t('范围匹配:'), value: ['count:[1 TO 5]', 'count:[1 TO 5}', 'count:[10 TO *]'] },
  ];

  /** 标记是否主动点击查询按钮，失焦则不执行 */
  isClickQuery: boolean | null = false;

  /** 记录总数 */
  total = 0;

  /** 当前数据源与数据类型的类型 自定义上报事件 | 日志关键字事件 */
  get currentSourceAndTypeLabel(): IEventRetrieval.EventTypeChange {
    const paramsMap: IEventRetrieval.SourceAndTypeLabelMap = {
      custom_event: {
        data_source_label: 'custom',
        data_type_label: 'event',
      },
      bk_monitor_log: {
        data_source_label: 'bk_monitor',
        data_type_label: 'log',
      },
    };
    return paramsMap[this.localValue.eventType];
  }

  /** 当前可选的维度信息列表 */
  get currentDimensionsList() {
    return this.currentDataIdItem?.dimensions || [];
  }

  /** 选中的 数据id | 采集id 数据 */
  get currentDataIdItem() {
    return this.dataIdList.find(item => item.id === this.localValue.result_table_id);
  }

  /** 自定义事件 | 日志的metric_field */
  get currentMetricField() {
    return this.localValue.eventType === 'custom_event' ? '_index' : this.currentDataIdItem?.metrics[0]?.id;
  }

  /** 第一条维度变量接口的请求参数 */
  get currentGroupByVarPramas(): IFilterCondition.VarParams {
    if (this.isEdit) return this.queryConfig;
    return {
      ...this.currentSourceAndTypeLabel,
      metric_field: this.currentMetricField,
      metric_field_cache: this.currentDataIdItem?.metrics[0]?.id || '',
      result_table_id: this.localValue.result_table_id,
      query_string: this.localValue.query_string.trim(),
      where: this.localValue.where.map((item, index) => ({
        ...item,
        condition: !!index ? item.condition : undefined,
      })),
    };
  }

  /** 图表的时间范围 */
  get timeRange() {
    // const { startTime: start_time, endTime: end_time } = handleTimeRange(this.compareValue.tools.timeRange);
    const [start_time, end_time] = handleTransformToTimestamp(this.compareValue.tools.timeRange);
    return {
      start_time,
      end_time,
    };
  }

  created() {
    if (this.$route.query?.queryConfig) {
      const { data_source_label, data_type_label, result_table_id, where } = JSON.parse(
        this.$route.query.queryConfig as string
      );
      this.localValue.where = where;
      this.localValue.result_table_id = result_table_id;
      this.localValue.eventType = `${data_source_label}_${data_type_label}` as IEventRetrieval.ILocalValue['eventType'];
    }

    if (!this.$route.query?.targets) {
      this.initData(!this.localValue.result_table_id);
    }
  }

  @Watch('eventInterval')
  @Watch('compareValue.tools.timeRange')
  timeRangeChange() {
    this.getGroupByList();
  }

  @Watch('chartTimeRange')
  handleChartTimeRange(list: [number, number]) {
    const isSame = JSON.stringify(this.timeRangeCache) === JSON.stringify(list);
    list && !isSame && this.getGroupByList({ start_time: list[0], end_time: list[1] });
  }

  @Watch('queryConfig', { immediate: true })
  queryConfigChange(config) {
    if (config) {
      this.isEdit = true;
      const { where, result_table_id, query_string, data_source_label, data_type_label } = this.queryConfig;
      this.localValue.where = where;
      this.localValue.result_table_id = result_table_id;
      this.localValue.query_string = query_string;
      this.localValue.eventType = `${data_source_label}_${data_type_label}` as IEventRetrieval.ILocalValue['eventType'];
      this.initData(!result_table_id);
    }
  }

  @Watch('drillKeywords')
  handleDrillSearch(keywords: string) {
    if (keywords === '') return;
    if (keywords !== this.localValue.query_string) {
      this.localValue.query_string = keywords;
      this.handleEventQuery();
    }
  }

  /**
   * @description: 初始化数据以及相关接口请求
   */
  async initData(needInit = true) {
    this.groupByList = [];
    this.dataIdList = [];
    await this.getDataId(needInit);
    this.handleEventQuery();
  }

  /** 切换事件类型 */
  @Emit('eventTypeChange')
  handleChangeEventType(): IEventRetrieval.EventTypeChange {
    this.localValue.where = [];
    this.localValue.query_string = '*';
    this.initData();
    return this.currentSourceAndTypeLabel;
  }

  /**
   * @description: 获取 数据id | 采集id 列表数据接口
   * @Param needInit 是否需要默认选中第一条数据
   */
  getDataId(needInit = true) {
    this.formLoading = true;
    return getDataSourceConfig({ ...this.currentSourceAndTypeLabel })
      .then(list => {
        this.dataIdList = list;
        if (needInit) {
          this.localValue.result_table_id = list?.[0]?.id || '';
        }

        if (!this.dataIdList.length) this.emptyStatusChange('empty');
        return list;
      })
      .finally(() => (this.formLoading = false));
  }

  /**
   * @description: 数据Id | 采集Id 需要清空过滤条件和查询语句
   */
  handleInitLocalValue() {
    this.localValue.where = [];
    this.localValue.query_string = '*';
    this.handleQueryProxy();
  }

  /** 自动查询 */
  handleQueryProxy() {
    if (this.autoQuery) this.handleEventQuery();
  }

  /** 修改过滤条件 */
  @Emit('whereChange')
  handleConditionChange(list: IFilterCondition.localValue[]) {
    this.localValue.where = list;
    this.handleQueryProxy();
    return list;
  }

  /** 查询图表和表格操作 */
  @Emit('query')
  handleEventQuery(): IFilterCondition.VarParams {
    this.isClickQuery === null && (this.isClickQuery = true);
    if (this.isEdit) this.isEdit = false;
    this.handleChartTitleChange();
    this.getGroupByList();
    this.emptyStatusChange(this.localValue.result_table_id ? 'search-empty' : 'empty');
    this.$emit('change', this.localValue);
    // 每次查询若输入框的值与kv列表下钻的值不同则清空下钻查询语句
    if (this.drillKeywords !== this.localValue.query_string) this.handleClearDrillKeywords();
    return deepClone(this.currentGroupByVarPramas);
  }

  /**
   * @description: 清空操作
   */
  handleClearQuery() {
    this.localValue.eventType = 'custom_event';
    this.localValue.query_string = '*';
    this.localValue.where = [];
    this.initData();
  }

  /** 添加一条收藏 */
  @Emit('addFav')
  handleAddEventFav(arg) {
    return arg;
  }

  /** 更新记录总数 */
  @Emit('countChange')
  handleCountChange(count: number) {
    return count;
  }

  @Emit('clearDrillKeywords')
  handleClearDrillKeywords() {}

  /**
   * @description: 获取维度列表数据
   */

  getGroupByList(timeRange?: { start_time: number; end_time: number }) {
    if (!this.currentGroupByVarPramas.result_table_id) return;
    timeRange = timeRange ? timeRange : this.timeRange;
    this.timeRangeCache = [timeRange.start_time, timeRange.end_time];
    const params = {
      ...timeRange,
      ...this.currentGroupByVarPramas,
      filter_dict: {},
      index_set_id: '',
    };
    this.gourpByLoading = true;
    return getGroupByCount(params)
      .then(res => {
        this.handleCountChange(res.total);
        this.groupByList = res.count.map(item => new FieldValue(item));
        this.total = res.total;
      })
      .catch(() => {
        this.emptyStatusChange('500');
      })
      .finally(() => (this.gourpByLoading = false));
  }

  @Emit('emptyStatusChange')
  emptyStatusChange(val: EmptyStatusType) {
    return val;
  }

  /**
   * @description: 添加过滤条件
   * @param {IFilterCondition} val
   * @return {*}
   */
  handleAddFilterCondition(val: IFilterCondition.localValue) {
    this.localValue.where.push(val);
    this.handleQueryProxy();
  }

  /**
   * @description: 查询语句失去焦点自动查询
   */
  handleQueryStringBlur() {
    /** 若点击查询失焦则不执行，直至本次查询完成 */
    if (this.isClickQuery) {
      this.isClickQuery = false;
      return;
    }
    const isSame = this.queryStringCache.trim() === this.localValue.query_string.trim();
    !isSame && this.handleQueryProxy();
  }

  /**
   * @description: 更新图表名
   * @param {*}
   * @return {string} title
   */
  @Emit('chartTitleChange')
  handleChartTitleChange() {
    const title = this.dataIdList.find(item => item.id === this.localValue.result_table_id)?.name || '';
    return title;
  }

  /**
   * @description: 查询语句聚焦
   */
  handleInputFocus() {
    this.queryStringCache = this.localValue.query_string;
    this.isClickQuery = null;
  }

  /**
   * @description: 切换自动查询开关
   * @param {boolean} val
   */
  handleAutoQueryChange(val?: boolean) {
    this.$emit('autoQueryChange', !!val);
  }

  render() {
    // 查询语句的提示内容
    const tipsContentTpl = () => (
      <div
        id='tips-content'
        class='query-tips-content-wrapper'
      >
        <div class='tips-content-title'>
          {this.$t('可输入SQL语句进行快速查询')}
          <a
            class='link'
            target='_blank'
            onClick={() => handleGotoLink('bkLogQueryString')}
          >
            {this.$t('查看语法')}
            <i class='icon-monitor icon-mc-link'></i>
          </a>
        </div>
        <ul class='tips-content-list'>
          {this.tipsContentList.map(item => (
            <li class='tips-content-item'>
              <div class='tips-content-item-label'>{item.label}</div>
              {item.value.map(val => (
                <div class='tips-content-item-val'>{val}</div>
              ))}
            </li>
          ))}
        </ul>
      </div>
    );
    return (
      <div class='event-retrieval-wrapper'>
        <div
          class='event-retrieval-bg'
          v-bkloading={{ isLoading: this.formLoading }}
        >
          <div class='er-from-item'>
            <div class='er-from-item-label'>{this.$t('事件类型')}</div>
            <bk-select
              vModel={this.localValue.eventType}
              clearable={false}
              onSelected={this.handleChangeEventType}
            >
              {this.eventTypeList.map(item => (
                <bk-option
                  id={item.id}
                  name={item.name}
                />
              ))}
            </bk-select>
          </div>
          {['custom_event', 'bk_monitor_log'].includes(this.localValue.eventType) ? (
            <div class='er-from-item'>
              <div class='er-from-item-label'>
                {this.$t(this.localValue.eventType === 'custom_event' ? '数据ID' : '采集ID')}
              </div>
              <bk-select
                key={JSON.stringify(this.dataIdList)}
                vModel={this.localValue.result_table_id}
                clearable={false}
                ext-popover-cls={'event-retrieval-data-id-select-popover'}
                searchable={true}
                onSelected={this.handleInitLocalValue}
              >
                {this.localValue.eventType === 'custom_event'
                  ? this.dataIdList.map(item => (
                      <bk-option
                        id={item.id}
                        key={item.id}
                        name={item.name}
                      >
                        <span class='event-item-name'>
                          <span
                            class='name-text'
                            v-bk-overflow-tips
                          >
                            {item.name}
                          </span>
                          {!!item?.is_platform && <span class='platform-tag'>{this.$t('平台数据')}</span>}
                        </span>
                      </bk-option>
                    ))
                  : this.dataIdList.map(item => (
                      <bk-option
                        id={item.id}
                        key={item.id}
                        name={item.name}
                      />
                    ))}
              </bk-select>
            </div>
          ) : undefined}
          <div class='er-from-item'>
            <div class='er-from-item-label'>
              {this.$t('查询语句')}
              <i
                class='icon-monitor icon-mc-help-fill'
                v-bk-tooltips={this.tipsConfig}
              ></i>
            </div>
            <bk-input
              class='query-string-input'
              vModel={this.localValue.query_string}
              type='textarea'
              onBlur={this.handleQueryStringBlur}
              onFocus={this.handleInputFocus}
            />
          </div>
          <div class='er-from-item'>
            <FilterCondition
              groupBy={this.currentDimensionsList}
              value={this.localValue.where}
              varParams={this.currentGroupByVarPramas}
              onChange={this.handleConditionChange}
            />
          </div>
          <HandleBtn
            style='padding-top: 8px;'
            autoQuery={this.autoQuery}
            canFav={Boolean(this.localValue.result_table_id)}
            canQuery={true}
            favCheckedValue={this.favCheckedValue}
            isFavoriteUpdate={this.isFavoriteUpdate}
            onAddFav={this.handleAddEventFav}
            onClear={this.handleClearQuery}
            onQuery={this.handleEventQuery}
            onQueryTypeChange={this.handleAutoQueryChange}
          />
        </div>
        <FieldFiltering
          class='field-filtering'
          v-bkloading={{ isLoading: this.gourpByLoading }}
          total={this.total}
          value={this.groupByList}
          onAddCondition={this.handleAddFilterCondition}
          onChange={list => (this.groupByList = list)}
        />
        {tipsContentTpl()}
      </div>
    );
  }
}
