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
import { Component, Emit, Inject, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { toPng } from 'html-to-image';
import { graphUnifyQuery, logQuery } from 'monitor-api/modules/grafana';
import { globalUrlFeatureMap } from 'monitor-common/utils/global-feature-map';
import { Debounce, deepClone, random } from 'monitor-common/utils/utils';
import MonitorEcharts from 'monitor-ui/monitor-echarts/monitor-echarts-new.vue';

import BackTop from '../../../components/back-top/back-top';
import { handleTransformToTimestamp } from '../../../components/time-range/utils';
import { CHART_INTERVAL } from '../../../constant/constant';
import authorityStore from '../../../store/modules/authority';
import { downFile, formatTime } from '../../../utils';
import CollectChart from '../components/collect-chart.vue';
import RetrievalEmptyShow from '../data-retrieval-view/retrieval-empty-show';
import ChartToolsMenu from './chart-more-tool';
import ExpandViewWrapper from './components/expand-view-wrapper';

import type { TimeRangeType } from '../../../components/time-range/time-range';
import type { EventRetrievalViewType, IDataRetrievalView, IFilterCondition, IOption } from '../typings';

import './event-retrieval-view.scss';

const $i18n = window.i18n;

@Component
export default class EventRetrievalView extends tsc<EventRetrievalViewType.IProps, EventRetrievalViewType.IEvent> {
  /** 对比数据 */
  @Prop({ default: () => ({}), type: Object }) compareValue: IDataRetrievalView.ICompareValue;
  /** 图表查询所需数据 */
  @Prop({ type: Object, default: () => ({}) }) eventMetricParams: IFilterCondition.VarParams;
  /** 周期列表 */
  @Prop({ default: () => CHART_INTERVAL }) intervalList: IOption[];
  /** 图表汇聚周期 */
  @Prop({ type: [String, Number], default: 'auto' }) chartInterval: EventRetrievalViewType.intervalType;
  /** 是否展示查询时间提示 */
  @Prop({ default: true }) showTip: boolean;
  /** 类名 */
  @Prop({ default: '', type: String }) extCls: string;
  // /** 记录总的数量 */
  // @Prop({ type: Number, default: 0 }) count: number // 记录条数
  /** 图表标题 */
  @Prop({ type: String, default: '' }) chartTitle: string;
  /** 图表配置 */
  // @Prop({ type: Object }) chartOption: any
  @Prop({ default: () => [], type: Array }) toolChecked: string[];
  @Prop({ default: () => [], type: Array }) moreChecked: string[];
  /** 是否需要展示头部工具栏 */
  @Prop({ default: false, type: Boolean }) needTools: boolean;
  /** 空状态 */
  @Prop({ default: 'empty', type: String }) emptyStatus: EventRetrievalViewType.IProps['emptyStatus'];
  @Ref() backTopRef: BackTop;
  @Ref() chartRef: MonitorEcharts;
  @Inject('authority') authority;
  @Inject('handleShowAuthorityDetail') handleShowAuthorityDetail;
  @Inject('authorityMap') authorityMap;

  /** graphUnifyQuery 接口请求耗时 */
  duration = 0;

  /** 每页加载数量 */
  pageSize = 50;
  /** 表格 第一页为0 */
  page = 0;
  /** 表格全部数据加载完毕标记 */
  isNoMoreData = false;
  /** 表格第一页的loading */
  tableLoading = false;
  noData = false;

  /** 是否滚动到底 */
  isTheEnd = false;
  /** 底部loading */
  loading = false;
  /** 是否是第一次检索 */
  isFirstSearch = true;

  /** 图表刷新key */
  chartKey = '';

  /** 表格数据 */
  tableData = [];

  /** 图表时间范围缓存 */
  chartTimeRangeCache = null;

  /** 收藏数据 */
  collectList = [];
  collectShow = false;

  /** 记录总条数 */
  total = 0;

  /** 渲染图表列 */
  tableColumnList = [
    { label: $i18n.t('时间'), prop: 'time', formatter: row => formatTime(+row.time) },
    { label: $i18n.t('事件名'), prop: 'event_name' },
    { label: $i18n.t('内容'), prop: 'event.content', formatter: row => row['event.content'] },
    { label: $i18n.t('目标'), prop: 'target' },
  ];

  chartMenu = [
    {
      name: this.$t('检索'),
      id: 'explore',
      icon: 'mc-retrieval',
      hasLink: true,
    },
    {
      name: this.$t('添加策略'),
      id: 'strategy',
      icon: 'menu-strategy',
      hasLink: true,
    },
  ];

  needMenu = true;

  get bizId() {
    return this.$store.getters.bizId;
  }

  /** 图表的时间范围 */
  timeRange(timeRange?: TimeRangeType) {
    const [start_time, end_time] = handleTransformToTimestamp(timeRange || this.compareValue.tools.timeRange);
    return {
      start_time,
      end_time,
    };
  }

  mounted() {
    this.$el.addEventListener('scroll', this.handleScrollToEnd);
    this.handleSetNeedMenu();
  }
  beforeDestroy() {
    this.$el.removeEventListener('scroll', this.handleScrollToEnd);
  }

  @Watch('chartInterval')
  @Watch('compareValue.tools.timeRange')
  @Watch('eventMetricParams')
  @Debounce(200)
  handleParamsChange() {
    this.chartTimeRangeCache = this.timeRange();
    this.updateViewData();
  }

  /**
   * @description: 监听滚动到底部
   * @param {Event} evt 滚动事件对象
   * @return {*}
   */
  handleScrollToEnd(evt: Event) {
    const target = evt.target as HTMLElement;
    const { scrollHeight } = target;
    const { scrollTop } = target;
    const { clientHeight } = target;
    const isEnd = !!scrollTop && scrollHeight - Math.ceil(scrollTop) === clientHeight;
    this.isTheEnd = isEnd;
    if (this.isTheEnd && !this.isNoMoreData) {
      this.page += 1;
      this.handleGetTableData().catch(err => {
        console.error(err);
        this.page -= 1;
      });
    }
  }

  /** 获取图表数据 */
  async getSeriesData(startTime, endTime) {
    if (!this.eventMetricParams?.result_table_id) {
      this.tableData = [];
      this.page = 0;
      return Promise.reject();
    }
    const {
      data_source_label,
      data_type_label,
      metric_field,
      where,
      result_table_id,
      group_by: groupBy,
      filter_dict: filterDict,
      method,
      query_string,
    } = this.eventMetricParams;
    const timeRange = startTime && endTime ? [startTime, endTime] : undefined;
    this.isNoMoreData = false;
    this.page = 0;
    this.handleTimeRangeChange(timeRange as [string, string]);
    this.handleGetTableData(timeRange);
    const params = {
      ...this.timeRange(timeRange),
      expression: 'a',
      query_configs: [
        {
          data_source_label,
          data_type_label,
          filter_dict: filterDict || {},
          functions: [],
          group_by: groupBy || [],
          query_string,
          interval: this.chartInterval === 'auto' ? undefined : this.chartInterval,
          where,
          table: result_table_id,
          metrics: [
            {
              field: metric_field || 'event.count',
              method: method || 'COUNT',
              alias: 'a',
            },
          ],
        },
      ],
    };
    const start = +new Date();
    return graphUnifyQuery(params).then(res => {
      this.duration = +new Date() - start;
      return res.series;
    });
  }

  /**
   * @description: 获取表格的数据
   */
  handleGetTableData(timeRange?: any) {
    if (this.loading) return;
    const {
      filter_dict: filterDict,
      data_source_label,
      data_type_label,
      where,
      group_by,
      result_table_id,
      query_string,
    } = this.eventMetricParams;
    const params = {
      ...this.timeRange(timeRange),
      data_source_label,
      data_type_label,
      where: where || [],

      group_by,
      result_table_id,
      query_string,
      filter_dict: filterDict || {},
      limit: this.pageSize,
      offset: this.page * this.pageSize,
    };
    this.page ? (this.loading = true) : (this.tableLoading = true);
    return logQuery(params, { needRes: true })
      .then(({ data = [], meta = { total: 0 } }) => {
        this.total = meta.total;
        this.isNoMoreData = data.length < this.pageSize;
        this.page ? this.tableData.push(...data) : (this.tableData = data);
      })
      .finally(() => {
        this.loading = false;
        this.tableLoading = false;
      });
  }

  /**
   * @description: 更新图表和表格的数据
   */
  async updateViewData() {
    await this.backTopRef?.handleBackTop();
    // this.handleGetTableData()
    this.chartKey = random(8);
    this.noData = false;
    this.isFirstSearch &&
      setTimeout(() => {
        this.isFirstSearch = false;
      }, 500);
  }

  /**
   * @description: 切换汇聚周期
   */
  @Emit('intervalChange')
  handleIntervalChange(interval: number | string) {
    return interval;
  }

  /**
   * @description: 跳转添加策略
   */
  @Emit('addStrategy')
  handleAddStrategy(): IFilterCondition.VarParams {
    return deepClone(this.eventMetricParams);
  }
  /**
   * @description: 跳转数据检索
   */
  @Emit('exportDataRetrieval')
  handleToRetrieval(): IFilterCondition.VarParams {
    return deepClone(this.eventMetricParams);
  }
  /**
   * @description: kv列表检索语句下钻
   */
  @Emit('drillSearch')
  handleDrillSearch(keywords: string) {
    return keywords;
  }

  /**
   * @description: 操作图表切换时间范围 timeRange ["2021-09-04 14:49", "2021-09-04 15:18"]
   */
  @Emit('timeRangeChange')
  handleTimeRangeChange(timeRange: [string, string] | { end_time: number; start_time: number }) {
    let time = null;

    const temp = timeRange as { end_time: number; start_time: number };
    if (timeRange && Array.isArray(timeRange)) {
      // time = handleTimeRange(timeRange);
      time = handleTransformToTimestamp(timeRange || this.compareValue.tools.timeRange);
      return time || undefined;
    }
    if (temp?.start_time) {
      return [temp.start_time, temp.end_time];
    }
  }

  /**
   * @description: 发送needMenu状态
   */
  @Emit('needMenuChange')
  handleNeedMenuChange() {
    return this.needMenu;
  }

  /**
   * @description: needMenu相关处理
   */
  handleSetNeedMenu() {
    this.needMenu = globalUrlFeatureMap.NEED_MENU;
    !this.needMenu && this.handleMergeUrlColumns();
    this.handleNeedMenuChange();
  }

  /**
   * @description: url中的columns并入表格
   */
  handleMergeUrlColumns() {
    const columns = JSON.parse((this.$route.query.columns || '[]') as string);
    if (columns.length) {
      const columnsList = columns.map(item => ({
        label: item.name,
        prop: item.id,
        formatter: row => row[item.id],
      }));
      const defaultColumnLabel = this.tableColumnList.map(item => item.label);
      for (const item of columnsList) {
        // 不同的列名才合并
        if (!defaultColumnLabel.includes(item.label)) {
          this.tableColumnList.push(item);
        }
      }
    }
  }

  /**
   * @description: 处理图表双击
   */
  handleChartDbclick() {
    this.handleTimeRangeChange(this.chartTimeRangeCache);
  }
  handleNoData(v) {
    this.noData = v;
  }

  /**
   * @description: 处理收藏到仪表盘
   */
  handleCollectSingleChart() {
    if (!this.authority.GRAFANA_MANAGE_AUTH) {
      authorityStore.getAuthorityDetail(this.authorityMap.GRAFANA_MANAGE_AUTH);
      return;
    }
    const { data_source_label, data_type_label, group_by, metric_field_cache, method, result_table_id, where } =
      this.eventMetricParams;
    this.collectList = [
      {
        title: this.chartTitle,
        targets: [
          {
            alias: '',
            data: {
              alias: 'a',
              bk_biz_id: this.bizId,
              expression: 'a',
              query_configs: [
                {
                  bk_biz_id: this.bizId,
                  data_source_label,
                  data_type_label,
                  functions: [],

                  group_by: group_by || [],
                  interval: typeof this.chartInterval === 'string' ? 60 : this.chartInterval,
                  metrics: [{ alias: 'a', field: metric_field_cache, method: method || 'SUM' }],
                  table: result_table_id,
                  where,
                },
              ],
            },
          },
        ],
      },
    ];
    this.collectShow = true;
  }

  /**
   * @description: 关闭收藏
   * @param {boolean} v
   */
  handleCloseCollect(v: boolean) {
    this.collectShow = v;
    this.collectList = [];
  }

  /**
   * @description: 截图操作
   */
  handleSavePng() {
    toPng(this.chartRef)
      .then(url => {
        downFile(url, `${this.$t('总趋势')}.png`);
      })
      .catch(err => {
        console.log(err);
      });
  }

  /**
   * @description: 工具栏选择操作
   * @param {*} type
   */
  handleSelectTool(type) {
    const typeMap = {
      screenshot: this.handleSavePng,
      explore: this.handleToRetrieval,
      strategy: this.handleAddStrategy,
    };
    typeMap[type]?.();
  }

  /**
   * @desc: 空检索事件
   * @param {String} eventStr
   */
  handleClickEmptyBtn(eventStr: string) {
    if (eventStr === 'query') this.updateViewData();
  }

  render() {
    const expandScopedSlots = data => (
      <ExpandViewWrapper
        data={data.row}
        onDrillSearch={this.handleDrillSearch}
      />
    );
    return (
      <div class={['event-retrieval-view-wrapper', this.extCls]}>
        <div>{this.$slots.header}</div>
        {this.showTip ? (
          <div class='query-time'>
            {this.needMenu ? (
              <i18n path='查询结果(找到 {0} 条，用时 {1} 毫秒)，将搜索条件 {2}{3}'>
                <span class='query-count'>{this.total}</span>
                <span>{this.duration}</span>
                <span
                  class='add-strategy'
                  onClick={this.handleAddStrategy}
                >
                  {this.$t('添加为监控')}
                </span>
                <i class='icon-monitor icon-mc-link' />
              </i18n>
            ) : (
              <i18n path='查询结果(找到 {0} 条，用时 {1} 毫秒)'>
                <span class='query-count'>{this.total}</span>
                <span>{this.duration}</span>
              </i18n>
            )}
          </div>
        ) : undefined}
        <div class='event-retrieval-view-main'>
          <div
            ref='chartRef'
            class='event-chart-collapse'
          >
            <div class='collapse-header'>
              <span class='header-left'>
                <span class='collapse-title'>{this.$t('总趋势')}</span>
                <span
                  class='interval-wrap'
                  onClick={evt => evt.stopPropagation()}
                >
                  <span class='interval-label'>{this.$t('汇聚周期')}</span>
                  <bk-select
                    class='interval-select'
                    behavior='simplicity'
                    clearable={false}
                    size='small'
                    value={this.chartInterval}
                    onChange={this.handleIntervalChange}
                  >
                    {this.intervalList.map(item => (
                      <bk-option
                        id={item.id}
                        key={item.id}
                        name={item.name}
                      >
                        {item.name}
                      </bk-option>
                    ))}
                  </bk-select>
                </span>
              </span>
              <span class='header-right'>
                <ChartToolsMenu
                  moreChecked={this.moreChecked}
                  toolChecked={['screenshot']}
                  onSelect={this.handleSelectTool}
                />
              </span>
            </div>
            <div class='collapse-content'>
              <div class='chart'>
                {this.chartKey && !this.noData ? (
                  <MonitorEcharts
                    key={this.chartKey}
                    height={164}
                    class='monitor-echarts-metric'
                    chart-type='bar'
                    get-series-data={this.getSeriesData}
                    hasResize={true}
                    refresh-interval={this.compareValue.tools.refreshInterval}
                    on-add-strategy={this.handleAddStrategy}
                    on-export-data-retrieval={this.handleToRetrieval}
                    on-no-data-change={this.handleNoData}
                    onDblclick={this.handleChartDbclick}
                  />
                ) : undefined}
              </div>
            </div>
          </div>
          <bk-table data={!this.tableLoading && this.tableColumnList.length ? this.tableData : []}>
            <bk-table-column
              scopedSlots={{
                default: expandScopedSlots,
              }}
              type='expand'
            />
            <div slot='empty'>
              <RetrievalEmptyShow
                emptyStatus={this.emptyStatus}
                eventMetricParams={this.eventMetricParams}
                queryLoading={false}
                showType={'event'}
                onClickEventBtn={this.handleClickEmptyBtn}
              />
            </div>
            {this.tableColumnList.map((column, index) => (
              <bk-table-column
                key={index}
                {...{
                  props: column,
                }}
              />
            ))}
          </bk-table>
          {/* <div
            class='table-loading-wrap'
            v-bkloading={{ isLoading: this.loading }}
          >
            {!!this.tableData.length && this.isNoMoreData ? (
              <span class='no-more-data-text'>{this.$t('没有更多数据')}</span>
            ) : undefined}
          </div> */}
        </div>
        <CollectChart
          collect-list={this.collectList}
          show={this.collectShow}
          total-count={1}
          is-single
          onClose={this.handleCloseCollect}
        />
        <BackTop
          ref='backTopRef'
          class='back-to-top'
          scrollTop={100}
        >
          <i class='icon-monitor icon-arrow-up' />
        </BackTop>
      </div>
    );
  }
}
