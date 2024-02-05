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
import { Component, Emit, InjectReactive, Prop, ProvideReactive, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { monitorDrag } from '../../../../monitor-common/utils/drag-directive';
import { deepClone, random } from '../../../../monitor-common/utils/utils';
import type { TimeRangeType } from '../../../components/time-range/time-range';
import CompareSelect from '../../monitor-k8s/components/panel-tools/compare-select';
import PanelsTools from '../../monitor-k8s/components/panel-tools/panel-tools';
// import PanelHeader from '../../monitor-k8s/components/panel-header/panel-header';
import { DASHBOARD_PANEL_COLUMN_KEY, OptionsItem, PanelToolsType } from '../../monitor-k8s/typings';
import DashboardPanels from '../../performance/performance-detail/dashboard-panels.vue';
import EventRetrievalView from '../event-retrieval/event-retrieval-view';
import IndexList, { IIndexListItem } from '../index-list/index-list';
// import ComparePanel from '../../performance/performance-detail/compare-panel.vue';
import { EventRetrievalViewType, FieldValue, IDataRetrieval, IDataRetrievalView, IFilterCondition } from '../typings';

import RetrievalEmptyShow from './retrieval-empty-show';

import './data-retrieval-view.scss';

const INDEX_PANEL_WIDTH = 208;
const { i18n } = window;
type chartType = IDataRetrievalView.chartType;

@Component({
  directives: {
    monitorDrag
  }
})
export default class DataRetrievalView extends tsc<IDataRetrievalView.IProps, IDataRetrievalView.IEvent> {
  @Prop({
    default: () => ({
      compare: {
        type: 'none',
        value: true
      },
      tools: {
        refleshInterval: -1,
        timeRange: 3600000
      }
    }),
    type: Object
  })
  compareValue: IDataRetrievalView.IProps['compareValue'];
  // @Prop({ default: () => [], type: Array }) favoritesList: IDataRetrievalView.IProps['favoritesList'];
  // @Prop({ default: () => ({}), type: Object }) favCheckedValue: IDataRetrievalView.IProps['favCheckedValue'];
  @Prop({ default: true, type: Boolean }) leftShow: boolean;
  @Prop({ default: () => [], type: Array }) queryResult: any[]; // 查询结果数据
  @Prop({ default: 0, type: Number }) queryTimeRange: number; // 查询时长
  @Prop({ default: false, type: Boolean }) canAddStrategy: boolean; // 是否能添加策略
  @Prop({ default: 'monitor', type: String }) retrievalType: IDataRetrieval.tabId;
  @Prop({ default: () => [], type: Array }) eventFieldList: FieldValue[];
  @Prop({ type: Object }) eventMetricParams: IFilterCondition.VarParams;
  @Ref() eventRetrievalViewRef: EventRetrievalView;
  @Prop({ type: [Number, String], default: 'auto' }) eventChartInterval: EventRetrievalViewType.intervalType;
  @Prop({ type: Number, default: 0 }) eventCount: number;
  @Prop({ type: String, default: '' }) eventChartTitle: string;
  @Prop({ type: Array, default: () => [] }) indexList: IIndexListItem[];
  @Prop({ default: true, type: Boolean }) needCompare: boolean;
  @Prop({ type: Number, default: 0 }) refleshNumber: number;
  @Prop({ type: Boolean, default: false }) queryLoading: boolean;
  @Prop({ type: String, default: 'empty' }) emptyStatus: IDataRetrievalView.IProps['emptyStatus'];
  /** 时区 */
  @Prop({ type: String, default: window.timezone }) timezone: string;
  @ProvideReactive('downSampleRange') downSampleRange = 'auto';
  @InjectReactive('onlyShowView') onlyShowView: boolean;
  loading = false;

  /** 图表联动id */
  groupId = random(10);

  /** 查询图表的总数 */
  chartCount = 0;

  /** 视图排版模式 */
  chartType: chartType = 0;

  /** 顶部操作栏所需值 */
  localCompareValue: IDataRetrievalView.ICompareValue = null;

  /** 图表配置 */
  chartOption: Object = {
    tool: {
      list: ['save', 'more', 'fullscreen', 'set', 'strategy', 'area', 'relate-alert'] // 要显示的工具栏的配置id 空数组则为不显示
    },
    annotation: {
      show: true,
      list: ['ip', 'process', 'strategy']
    }
  };
  /** 对比类型列表 */
  compareList: IDataRetrievalView.IOptionItem[] = [
    {
      id: 'none',
      name: i18n.t('不对比')
    },
    {
      id: 'target',
      name: i18n.t('目标对比')
    },
    {
      id: 'time',
      name: i18n.t('时间对比')
    },
    {
      id: 'metric',
      name: i18n.t('指标对比')
    }
  ];
  /** 时间范围选择列表 */
  timerangeList: IDataRetrievalView.IOptionItem[] = [
    {
      name: i18n.t('近{n}分钟', { n: 5 }),
      value: 5 * 60 * 1000
    },
    {
      name: i18n.t('近{n}分钟', { n: 15 }),
      value: 15 * 60 * 1000
    },
    {
      name: i18n.t('近{n}分钟', { n: 30 }),
      value: 30 * 60 * 1000
    },
    {
      name: i18n.t('近{n}小时', { n: 1 }),
      value: 1 * 60 * 60 * 1000
    },
    {
      name: i18n.t('近{n}小时', { n: 3 }),
      value: 3 * 60 * 60 * 1000
    },
    {
      name: i18n.t('近{n}小时', { n: 6 }),
      value: 6 * 60 * 60 * 1000
    },
    {
      name: i18n.t('近{n}小时', { n: 12 }),
      value: 12 * 60 * 60 * 1000
    },
    {
      name: i18n.t('近{n}小时', { n: 24 }),
      value: 24 * 60 * 60 * 1000
    },
    {
      name: i18n.t('近 {n} 天', { n: 2 }),
      value: 2 * 24 * 60 * 60 * 1000
    },
    {
      name: i18n.t('近 {n} 天', { n: 7 }),
      value: 7 * 24 * 60 * 60 * 1000
    },
    {
      name: i18n.t('近 {n} 天', { n: 30 }),
      value: 30 * 24 * 60 * 60 * 1000
    },
    {
      name: i18n.t('今天'),
      value: 'today'
    },
    {
      name: i18n.t('昨天'),
      value: 'yesterday'
    },
    {
      name: i18n.t('前天'),
      value: 'beforeYesterday'
    },
    {
      name: i18n.t('本周'),
      value: 'thisWeek'
    }
  ];
  /** 时间对比列表 */
  timeshiftList: IDataRetrievalView.IOptionItem[] = [
    {
      id: '1h',
      name: i18n.t('1 小时前')
    },
    {
      id: '1d',
      name: i18n.t('昨天')
    },
    {
      id: '1w',
      name: i18n.t('上周')
    },
    {
      id: '1M',
      name: i18n.t('一月前')
    }
  ];

  /** 强制图表key */
  dashboardPanelsKey = 'dashboardPanelsKey';

  /** 索引面板展示状态 */
  isShowIndex = false;
  /** 索引面板宽度 */
  indexPanelWidth = INDEX_PANEL_WIDTH;

  /** 是否禁用图表分栏布局按钮 */
  disabledLayout = true;

  /** 查询图表时长提示 */
  get searchTipsObj(): IDataRetrievalView.ISearchTipsObj {
    return {
      value: this.localCompareValue.compare.value as boolean,
      show: true,
      time: this.queryTimeRange,
      showSplit: false,
      showAddStrategy: this.canAddStrategy
    };
  }

  get timeRangeListFormatter(): OptionsItem[] {
    return this.timerangeList.map(item => {
      const id = item.value as string;
      return {
        id,
        name: item.name
      };
    });
  }

  get hasTips() {
    return (
      !this.onlyShowView && this.retrievalType === 'monitor' && this.searchTipsObj.show && !!this.queryResult?.length
    );
  }

  @Watch('compareValue', { immediate: true, deep: true })
  valueUpdate() {
    this.localCompareValue = deepClone(this.compareValue);
  }

  @Watch('indexList', { immediate: true })
  indexListChange(list: IIndexListItem[]) {
    this.handleShowIndexPanel(!!list.length);
  }

  @Watch('queryResult')
  queryResultChange(val) {
    if (val.length <= 1) this.chartType = 0;
    this.disabledLayout = val.length <= 1;
    this.isShowIndex = val.length > 1;
  }

  created() {
    this.chartType = +localStorage.getItem(DASHBOARD_PANEL_COLUMN_KEY) || 0;
  }

  @Emit('timeRangeChange')
  handelTimeRangeChange(timeRange: TimeRangeType) {
    // if (Array.isArray(timeRange)) {
    //   this.handleTimerangeList(timeRange);
    // }
    return timeRange;
  }

  @Emit('refleshIntervalChange')
  handleRefleshChange(val: number) {
    return val;
  }

  /**
   * @description: 操作栏值更新
   * @param {IDataRetrievalView} data
   * @return {*}
   */
  @Emit('compareChange')
  handleComparePanelChange(data: IDataRetrievalView.ICompareComChange) {
    if (Array.isArray(data.tools.timeRange)) {
      this.handleTimerangeList(data.tools.timeRange);
    } else if (data.type === 'compare' && data.compare.type === 'time') {
      this.handleTimeshiftList(data.compare.value as string);
    } else if (data.type === 'compare' && data.compare.type === 'none') {
      data.compare.value = true;
    }
    return data;
  }
  @Emit('compareValueChange')
  handleCompareChange() {
    return this.localCompareValue.compare;
  }

  @Emit('drillKeywordsSearch')
  handleDrillSearch(keywords: string) {
    return keywords;
  }

  /** 时间对比变更 */
  handleCompareTimeChange(list: string[]) {
    this.localCompareValue.compare.value = list;
    this.handleCompareChange();
  }

  /** 对比类型变更 */
  handleCompareTypeChange(type: PanelToolsType.CompareId) {
    const defaultValueMap: PanelToolsType.ICompareValueType = {
      none: this.localCompareValue.compare.type === 'none' ? Boolean(this.localCompareValue.compare.value) : true,
      metric: [],
      target: [],
      time: ['1d']
    };
    this.localCompareValue.compare.type = type;
    this.localCompareValue.compare.value = defaultValueMap[type];
    this.handleCompareChange();
  }

  /**
   * @description: 切换视图布局
   * @param {chartType} type 视图布局模式
   * @return {*}
   */
  handleChartChange(type: chartType) {
    this.chartType = type;
  }

  /**
   * @description: 新增自定义时间范围
   * @param {string} list 时间范围
   * @return {*}
   */
  handleTimerangeList(list: string[]) {
    const valStr = `${list[0]} -- ${list[1]}`;
    const item = this.timerangeList.find(item => item.name === valStr);
    if (!item) {
      this.timerangeList.push({
        name: valStr,
        value: valStr
      });
    }
  }

  /**
   * @description: 新增自定时间对比列表
   * @param {*} val
   * @return {*}
   */
  handleTimeshiftList(val: string | string[]) {
    if (typeof val === 'string') {
      const item = this.timeshiftList.find(item => item.id === val);
      if (!item) {
        this.timeshiftList.push({
          name: val,
          id: val
        });
      }
    } else if (Array.isArray(val)) {
      const itemList = val.filter(id => !this.timeshiftList.some(item => item.id === id));
      if (itemList.length) {
        itemList.forEach(id => {
          this.timeshiftList.push({
            name: id,
            id
          });
        });
      }
    }
  }

  /**
   * @description: 展开左侧栏
   */
  @Emit('showLeft')
  handleShowLeft(): boolean {
    return true;
  }

  /**
   * @description: 删除收藏
   * @param {number} id
   * @return {*}
   */
  @Emit('deleteFav')
  handleDeleteFav(id: number) {
    return id;
  }

  /**
   * @description: 选中收藏
   */
  @Emit('selectFav')
  emitSelectFav(data: IDataRetrieval.ILocalValue) {
    return data;
  }

  /**
   * @description: 合并视图操作
   * @param {*} val 开关
   * @return {boolean}}
   */
  @Emit('splitChange')
  handleSplitChange(val: boolean) {
    return val;
  }

  /**
   * @description: 新建策略
   */
  handleAddStrategy() {
    this.$emit('addStrategy');
  }

  /**
   * @description: 强制刷新图表
   */
  @Watch('refleshNumber')
  handleImmediateReflesh() {
    if (this.retrievalType === 'monitor') this.dashboardPanelsKey = random(8);
    if (this.retrievalType === 'event') this.eventRetrievalViewRef.updateViewData();
  }

  @Emit('eventIntervalChange')
  handleEventChartIntervalChange(interval) {
    return interval;
  }

  /**
   * @description: 事件查询添加策略
   * @param {IFilterCondition} queryConfig
   */
  @Emit('addEventStrategy')
  handleAddEventStrategy(queryConfig: IFilterCondition.VarParams) {
    return queryConfig;
  }

  @Emit('timeRangeChangeEvent')
  handleTimeRangeChange(timeRange: EventRetrievalViewType.IEvent['onTimeRangeChange']) {
    return timeRange;
  }

  /** 展示索引面板 */
  handleShowIndexPanel(show?: boolean) {
    if (this.disabledLayout) return;
    setTimeout(() => {
      this.isShowIndex = show ?? !this.isShowIndex;
    }, 0);
    // this.indexPanelWidth = this.isShowIndex ? INDEX_PANEL_WIDTH : 0;
  }

  /**
   * 选中索引 调到指定图表
   * @param id
   */
  handleSelectIndex({ id }) {
    document.querySelector('.chart-wrapper-old .scroll-in')?.classList.remove('scroll-in');
    const dom = document.getElementById(id);
    if (!dom) return;
    dom.scrollIntoView?.();
    dom.classList.add('scroll-in');
  }
  handleDownSampleChange(downSampleRange: string) {
    this.downSampleRange = downSampleRange;
  }
  render() {
    return (
      <div class='data-retrieval-view'>
        <div class='view-header-wrapper'>
          {/* <ComparePanel
            class="compare-wrap"
            value={this.localCompareValue}
            needTarget={false}
            needSplit={false}
            chartType={this.chartType}
            timerangeList={this.timerangeList}
            timeshiftList={this.timeshiftList}
            compareList={this.compareList}
            favoritesList={this.favoritesList}
            favCheckedValue={this.favCheckedValue}
            compareHide={this.retrievalType === 'event'}
            hasViewChangeIcon={this.retrievalType !== 'event'}
            on-on-immediate-reflesh={this.handleImmediateReflesh}
            on-select-fav={this.emitSelectFav}
            on-delete-fav={this.handleDeleteFav}
            on-change={this.handleComparePanelChange}
            on-chart-change={this.handleChartChange}
          >
            {this.leftShow ? undefined : (
              <span slot="pre" class="tool-icon right" onClick={this.handleShowLeft}>
                <i class="arrow-right icon-monitor icon-double-up"></i>
              </span>
            )}
          </ComparePanel> */}
          {/* <PanelHeader
            // timeRangeList={this.timeRangeListFormatter}
            timeRange={this.compareValue.tools?.timeRange}
            refleshInterval={this.compareValue.tools.refleshInterval}
            favoritesList={this.favoritesList}
            favCheckedValue={this.favCheckedValue}
            showDownSample={false}
            downSampleRange={this.downSampleRange}
            onDownSampleChange={this.handleDownSampleChange}
            onImmediateReflesh={this.handleImmediateReflesh}
            onTimeRangeChange={this.handelTimeRangeChange}
            onRefleshIntervalChange={this.handleRefleshChange}
            onSelectFav={this.emitSelectFav}
            onDeleteFav={this.handleDeleteFav}>
            {this.leftShow ? undefined : (
              <span slot="pre" class="tool-icon right" onClick={this.handleShowLeft}>
                <i class="arrow-right icon-monitor icon-double-up"></i>
              </span>
            )}
          </PanelHeader> */}
        </div>
        <div
          class={['charts-view-wrapper', { 'is-event': this.retrievalType === 'event' }]}
          v-bkloading={{ isLoading: this.loading }}
        >
          {this.hasTips ? (
            <div class='total-tips'>
              <div class='tips-text'>
                <span>{`${this.$t('找到 {count} 条结果 , 耗时  {time} ms', {
                  count: this.chartCount,
                  time: this.searchTipsObj.time
                })}`}</span>
                {this.searchTipsObj.showAddStrategy ? (
                  <span>
                    ,
                    <span
                      class='add-strategy-btn'
                      onClick={this.handleAddStrategy}
                    >
                      {this.$t('添加监控策略')}
                    </span>
                  </span>
                ) : undefined}
              </div>
            </div>
          ) : undefined}
          <div class={['charts-view-main', { 'has-tips': this.hasTips }]}>
            <div
              class='charts-view-left'
              style={{ flex: 1, width: `calc(100% - ${this.indexPanelWidth}px)` }}
            >
              {!this.onlyShowView && this.retrievalType === 'monitor' ? (
                <PanelsTools
                  class='panels-tools'
                  needSplit={this.compareValue.compare.type === 'none'}
                  split={
                    this.compareValue.compare.type === 'none' ? (this.compareValue.compare.value as boolean) : undefined
                  }
                  layoutActive={this.chartType}
                  disabledLayout={this.disabledLayout}
                  onSplitChange={this.handleSplitChange}
                  onLayoutChange={this.handleChartChange}
                >
                  <span
                    slot='prepend'
                    class='panels-tools-prepend'
                  >
                    <CompareSelect
                      type={this.compareValue.compare.type}
                      timeValue={
                        this.compareValue.compare.type === 'time'
                          ? (this.compareValue.compare.value as string[])
                          : undefined
                      }
                      needCompare={this.needCompare}
                      onTimeChange={this.handleCompareTimeChange}
                      onTypeChange={this.handleCompareTypeChange}
                    />
                  </span>
                  <span
                    slot='append'
                    class={['icon-monitor icon-mc-list', { active: this.isShowIndex, disabled: this.disabledLayout }]}
                    onClick={() => this.handleShowIndexPanel()}
                  ></span>
                </PanelsTools>
              ) : undefined}
              {
                // eslint-disable-next-line no-nested-ternary
                this.retrievalType === 'monitor' ? (
                  this.queryResult?.length ? (
                    <DashboardPanels
                      class='dashboard-panels-list'
                      key={this.dashboardPanelsKey}
                      groupsData={this.queryResult}
                      searchTipsObj={{ show: false }}
                      compareValue={this.localCompareValue}
                      chartType={this.chartType}
                      chartOption={this.chartOption}
                      groupId={this.groupId}
                      on-split-change={this.handleSplitChange}
                      on-add-strategy={this.handleAddStrategy}
                      on-chart-count-change={count => (this.chartCount = count)}
                    />
                  ) : (
                    <RetrievalEmptyShow
                      style='margin-top: 150px;'
                      showType='monitor'
                      queryLoading={this.queryLoading}
                      emptyStatus={this.emptyStatus}
                    />
                  )
                ) : undefined
              }
              {/* <bk-exception style="margin-top: 150px;" type="empty">
                    <span>{this.$t('查无数据')}</span>
                  </bk-exception> */}
              {this.retrievalType === 'event' ? (
                <EventRetrievalView
                  ref='eventRetrievalViewRef'
                  eventMetricParams={this.eventMetricParams}
                  compareValue={this.compareValue}
                  chartInterval={this.eventChartInterval}
                  toolChecked={['screenshot']}
                  chartTitle={this.eventChartTitle}
                  emptyStatus={this.emptyStatus}
                  onTimeRangeChange={this.handleTimeRangeChange}
                  onAddStrategy={this.handleAddEventStrategy}
                  onIntervalChange={this.handleEventChartIntervalChange}
                  onDrillSearch={this.handleDrillSearch}
                ></EventRetrievalView>
              ) : undefined}
            </div>
            {this.retrievalType === 'monitor' && (
              <div
                class={['charts-view-right']}
                v-monitor-drag={{
                  minWidth: 100,
                  maxWidth: 500,
                  defaultWidth: 208,
                  autoHidden: true,
                  theme: 'dotted',
                  placement: 'right',
                  isShow: this.isShowIndex,
                  onHidden: () => (this.isShowIndex = false),
                  onWidthChange: width => (this.indexPanelWidth = width)
                }}
              >
                <div class='charts-view-right-content'>
                  <div class='charts-view-right-title'>
                    <span>{this.$t('索引')}</span>
                    <i
                      class='icon-monitor icon-mc-close'
                      onClick={() => this.handleShowIndexPanel()}
                    ></i>
                  </div>
                  <div class='charts-view-right-list'>
                    {this.indexList.length ? (
                      <IndexList
                        type={this.indexList.some(item => !!item.children) ? 'tree' : 'list'}
                        list={this.indexList}
                        tipsPlacement='left'
                        onSelect={this.handleSelectIndex}
                      />
                    ) : (
                      <bk-exception
                        type='empty'
                        scene='part'
                      >
                        <span>{this.$t('查无数据')}</span>
                      </bk-exception>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }
}
