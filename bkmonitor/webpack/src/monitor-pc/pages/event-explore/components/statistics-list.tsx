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

import { Component, Emit, InjectReactive, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { CancelToken } from 'monitor-api/cancel';
import { Debounce, downloadFile } from 'monitor-common/utils';
import loadingIcon from 'monitor-ui/chart-plugins/icons/spinner.svg';

import EmptyStatus from '../../../components/empty-status/empty-status';
import { handleTransformTime } from '../../../components/time-range/utils';
import { APIType, getDownloadTopK, getEventTopK, getTopKStatisticGraph, getTopKStatisticInfo } from '../api-utils';
import { topKColorList } from '../utils';
import DimensionEcharts from './dimension-echarts';

import type { ConditionChangeEvent, DimensionType, IStatisticsInfo, ITopKField } from '../typing';

import './statistics-list.scss';
interface StatisticsListEvents {
  onConditionChange(e: ConditionChangeEvent): void;
  onShowMore(): void;
  onSliderShowChange(sliderShow: boolean): void;
}

interface StatisticsListProps {
  fieldType: string;
  isDimensions?: boolean;
  isShow?: boolean;
  isShowChart?: boolean;
  popoverInstance?: any;
  selectField: string;
  source: APIType;
}

@Component
export default class StatisticsList extends tsc<StatisticsListProps, StatisticsListEvents> {
  @Prop({ type: Boolean, default: false }) isShow: boolean;
  @Prop({ type: String, default: '' }) selectField: string;
  @Prop({ type: String, default: '' }) fieldType: DimensionType;
  @Prop({ type: Boolean, default: false }) isShowChart: boolean;
  @Prop({ type: Boolean, default: false }) isDimensions: boolean;
  @Prop({ type: Object, default: null }) popoverInstance: any;
  /** 来源 */
  @Prop({ type: String, default: APIType.MONITOR }) source: APIType;

  @InjectReactive('timeRange') timeRange;
  @InjectReactive('commonParams') commonParams;

  localField = '';
  infoLoading = true;
  getStatisticsListCount = 0;
  statisticsInfo: IStatisticsInfo = {
    field: '',
    total_count: 0,
    field_count: 0,
    distinct_count: 0,
    field_percent: 0,
  };
  /** 格式化后时间范围文本 */
  timeRangeText = [];
  chartData = [];
  topKInfoCancelFn = null;
  topKChartCancelFn = null;

  sliderShow = false;
  sliderLoading = false;
  sliderLoadMoreLoading = false;

  /** 维度统计列表 */
  statisticsList: ITopKField = { distinct_count: 0, field: '', list: [] };
  /** 侧栏维度列表 */
  sliderDimensionList: ITopKField = { distinct_count: 0, field: '', list: [] };
  slideOverflowPopoverInstance = null;
  /** 侧栏分页 */
  sliderListPage = 1;

  popoverLoading = true;
  downloadLoading = false;

  topKCancel = null;

  /** 渲染TopK字段行 */
  renderTopKField(list: ITopKField['list'], type: 'list' | 'slider') {
    if (!list.length) return <EmptyStatus type='empty' />;

    return (
      <div class='top-k-list'>
        {list.map((item, index) => (
          <div
            key={item.value}
            class='top-k-list-item'
          >
            <div class='filter-tools'>
              <i
                class='icon-monitor icon-a-sousuo'
                v-bk-tooltips={{
                  content: `${this.isDimensions ? 'dimensions.' : ''}${this.localField} = ${item.value || '""'}`,
                }}
                onClick={() => this.handleConditionChange('eq', item)}
              />
              <i
                class='icon-monitor icon-sousuo-'
                v-bk-tooltips={{
                  content: `${this.isDimensions ? 'dimensions.' : ''}${this.localField} != ${item.value || '""'}`,
                }}
                onClick={() => this.handleConditionChange('ne', item)}
              />
            </div>
            <div class='progress-content'>
              <div class='info-text'>
                <span
                  class='field-name'
                  onMouseenter={e => this.topKItemMouseenter(e, item.alias)}
                  onMouseleave={this.topKItemMouseLeave}
                >
                  {item.alias}
                </span>
                <span class='counts'>
                  <span class='total'>{this.$t('{0}条', [item.count])}</span>
                  <span class='progress-count'>{item.proportions}%</span>
                </span>
              </div>
              <bk-progress
                color={this.fieldType === 'integer' || type === 'slider' ? '#5AB8A8' : topKColorList[index]}
                percent={item.proportions / 100}
                show-text={false}
                stroke-width={6}
              />
            </div>
          </div>
        ))}
      </div>
    );
  }

  @Emit('conditionChange')
  handleConditionChange(type: 'eq' | 'ne', item: ITopKField['list'][0]) {
    return {
      key: this.localField,
      method: type,
      value: item.value,
    };
  }

  @Emit('sliderShowChange')
  sliderShowChange() {
    return this.sliderShow;
  }

  @Watch('isShow')
  watchSelectFieldChange(val) {
    if (!val) {
      this.statisticsList = { distinct_count: 0, field: '', list: [] };
      this.infoLoading = true;
    } else {
      this.localField = this.selectField;
      this.timeRangeText = handleTransformTime(this.timeRange);
      this.getStatisticsList();
    }
  }

  @Debounce(200)
  async getStatisticsList() {
    this.infoLoading = true;
    this.getStatisticsListCount += 1;
    const count = this.getStatisticsListCount;
    this.popoverLoading = true;
    this.statisticsList = await this.getFieldTopK({
      limit: 5,
      fields: [this.localField],
    });
    if (count !== this.getStatisticsListCount) return;
    this.popoverLoading = false;
    this.popoverInstance?.popperInstance?.update();
    await this.getStatisticsGraphData();
  }

  @Debounce(200)
  async getStatisticsGraphData() {
    if (!this.isShowChart) return;
    this.topKInfoCancelFn?.();
    const info: IStatisticsInfo = await getTopKStatisticInfo(
      {
        ...this.commonParams,
        field: {
          field_name: this.localField,
          field_type: this.fieldType,
        },
      },
      this.source,
      {
        cancelToken: new CancelToken(c => (this.topKInfoCancelFn = c)),
      }
    ).catch(() => {
      return null;
    });
    if (!info) return;

    this.statisticsInfo = info;

    const { min, max } = this.statisticsInfo.value_analysis || {};
    const values =
      this.fieldType === 'integer'
        ? [min, max, this.statisticsInfo.distinct_count, 10]
        : this.statisticsList.list.map(item => item.value);
    const { query_configs, ...other } = this.commonParams;
    this.topKChartCancelFn?.();
    const data = await getTopKStatisticGraph(
      {
        ...other,
        query_configs: [
          {
            ...query_configs[0],
            group_by: this.fieldType === 'keyword' ? [this.localField] : [],
            metrics: [
              {
                field: '_index',
                method: 'COUNT',
                alias: 'a',
              },
            ],
          },
        ],
        field: {
          field_name: this.localField,
          field_type: this.fieldType,
          values,
        },
        expression: 'a',
      },
      this.source,
      {
        cancelToken: new CancelToken(c => (this.topKChartCancelFn = c)),
      }
    ).catch(() => ({ series: [] }));
    const series = data.series || [];
    this.chartData = series.map(item => {
      const name = item.dimensions?.[this.localField];
      const index = this.statisticsList.list.findIndex(i => name === i.value) || 0;
      return {
        color: this.fieldType === 'integer' ? '#5AB8A8' : topKColorList[index],
        name,
        ...item,
      };
    });

    this.infoLoading = false;
  }

  /** 展示侧栏 */
  async showMore() {
    this.sliderShow = true;
    this.sliderLoading = true;
    this.sliderShowChange();
    this.$emit('showMore');
    await this.loadMore();
    this.sliderLoading = false;
  }

  /** 加载更多 */
  async loadMore() {
    this.sliderLoadMoreLoading = true;
    this.sliderDimensionList = await this.getFieldTopK({
      limit: this.sliderListPage * 100,
      fields: [this.localField],
    });
    this.sliderLoadMoreLoading = false;
    this.sliderListPage += 1;
  }

  handleSliderShowChange(show: boolean) {
    this.sliderShow = show;
    this.sliderShowChange();
    if (!show) {
      this.sliderDimensionList = { distinct_count: 0, field: '', list: [] };
      this.sliderListPage = 1;
    }
  }

  async handleDownload() {
    this.downloadLoading = true;
    const data = await getDownloadTopK(
      {
        limit: this.sliderShow ? this.sliderDimensionList.distinct_count : this.statisticsList?.distinct_count,
        fields: [this.localField],
        ...this.commonParams,
      },
      this.source
    ).finally(() => {
      this.downloadLoading = false;
    });
    try {
      downloadFile(data.data, 'txt', data.filename);
    } catch {}
  }

  async getFieldTopK(params) {
    this.topKCancel?.();
    return getEventTopK(
      {
        ...this.commonParams,
        ...params,
      },
      this.source,
      {
        cancelToken: new CancelToken(c => (this.topKCancel = c)),
      }
    )
      .then(data => data[0] || { distinct_count: 0, field: '', list: [] })
      .catch(() => ({ distinct_count: 0, field: '', list: [] }));
  }

  topKItemMouseenter(e: MouseEvent, content: string) {
    const target = e.target as HTMLElement;
    if (target.offsetWidth < target.scrollWidth) {
      this.slideOverflowPopoverInstance = this.$bkPopover(target, {
        content,
        arrow: true,
        interactive: true,
        theme: 'slide-dimension-filter-overflow-tips',
      });
      this.slideOverflowPopoverInstance?.show(50);
    }
  }

  topKItemMouseLeave() {
    this.slideOverflowPopoverInstance?.hide(0);
    this.slideOverflowPopoverInstance?.destroy();
  }

  renderStatisticsInfo() {
    if (!this.isShowChart) return;
    if (this.infoLoading)
      return (
        <div class='info-skeleton'>
          <div class='total-skeleton'>
            <div class='skeleton-element' />
            <div class='skeleton-element' />
            <div class='skeleton-element' />
          </div>
          {this.fieldType === 'integer' && (
            <div class='info-skeleton'>
              <div class='skeleton-element' />
              <div class='skeleton-element' />
              <div class='skeleton-element' />
              <div class='skeleton-element' />
            </div>
          )}
          <div class='skeleton-element chart' />
        </div>
      );

    return (
      <div class='statistics-info'>
        <div class='top-k-info-header'>
          <div class='label-item'>
            <span class='label'>{this.$t('总行数')}:</span>
            <span class='value'> {this.statisticsInfo.total_count}</span>
          </div>
          <div class='label-item'>
            <span class='label'>{this.$t('出现行数')}:</span>
            <span class='value'> {this.statisticsInfo.field_count}</span>
          </div>
          <div class='label-item'>
            <span class='label'>{this.$t('日志条数')}:</span>
            <span class='value'> {this.statisticsInfo.field_percent}%</span>
          </div>
        </div>

        {this.fieldType === 'integer' && (
          <div class='integer-statics-info'>
            <div class='integer-item'>
              <span class='label'>{this.$t('最大值')}</span>
              <span class='value'>{this.statisticsInfo.value_analysis?.max || 0}</span>
            </div>

            <div class='integer-item'>
              <span class='label'>{this.$t('最小值')}</span>
              <span class='value'>{this.statisticsInfo.value_analysis?.min || 0}</span>
            </div>
            <div class='integer-item'>
              <span class='label'>{this.$t('平均值')}</span>
              <span class='value'>{this.statisticsInfo.value_analysis?.avg || 0}</span>
            </div>
            <div class='integer-item'>
              <span class='label'>{this.$t('中位数')}</span>
              <span class='value'>{this.statisticsInfo.value_analysis?.median || 0}</span>
            </div>
          </div>
        )}

        <div class='top-k-chart-title'>
          <span class='title'>{this.$t(this.fieldType === 'integer' ? '数值分布直方图' : 'TOP 5 时序图')}</span>
          {this.fieldType === 'integer' && (
            <span class='time-range'>
              {this.timeRangeText[0]} ～ {this.timeRangeText[1]}
            </span>
          )}
        </div>

        <DimensionEcharts
          data={this.chartData}
          seriesType={this.fieldType === 'integer' ? 'histogram' : 'line'}
        />
      </div>
    );
  }

  renderSkeleton() {
    return (
      <div class='skeleton-wrap'>
        {new Array(5).fill(null).map((_, index) => (
          <div
            key={index}
            class='skeleton-element'
          />
        ))}
      </div>
    );
  }

  render() {
    return (
      <div style={{ display: 'none' }}>
        <div
          ref='dimensionPopover'
          class='event-retrieval-dimension-filter-content'
        >
          {this.renderStatisticsInfo()}

          <div class='top-k-list-header'>
            <div class='dimension-top-k-title'>
              <span
                class='field-name'
                v-bk-overflow-tips
              >
                {this.localField}
              </span>
              <span class='divider' />
              <span class='desc'>
                {this.$t('去重后的字段统计')} ({this.statisticsList?.distinct_count || 0})
              </span>
            </div>
            {this.downloadLoading || this.popoverLoading ? (
              <img
                class='loading-icon'
                alt=''
                src={loadingIcon}
              />
            ) : (
              <div
                class='download-tool'
                v-bk-tooltips={{ content: this.$t('下载') }}
                onClick={this.handleDownload}
              >
                <i class='icon-monitor icon-xiazai2' />
              </div>
            )}
          </div>
          {this.popoverLoading
            ? this.renderSkeleton()
            : [
                this.renderTopKField(this.statisticsList?.list, 'list'),
                this.statisticsList?.distinct_count > 5 && (
                  <div
                    class='load-more'
                    onClick={this.showMore}
                  >
                    {this.$t('更多')}
                  </div>
                ),
              ]}
        </div>

        <bk-sideslider
          width='480'
          ext-cls='dimension-top-k-slider'
          is-show={this.sliderShow}
          show-mask={false}
          transfer={true}
          quick-close
          {...{ on: { 'update:isShow': this.handleSliderShowChange } }}
        >
          <div
            class='dimension-slider-header'
            slot='header'
          >
            <div class='dimension-top-k-title'>
              <span
                class='field-name'
                v-bk-overflow-tips
              >
                {this.localField}
              </span>
              <span class='divider' />
              <span class='desc'>
                {this.$t('去重后的字段统计')} ({this.sliderDimensionList.distinct_count || 0})
              </span>
            </div>
            {this.downloadLoading || this.sliderLoading ? (
              <img
                class='loading-icon'
                alt=''
                src={loadingIcon}
              />
            ) : (
              <div
                class='download-tool'
                onClick={this.handleDownload}
              >
                <i class='icon-monitor icon-xiazai2' />
                <span class='text'>{this.$t('下载')}</span>
              </div>
            )}
          </div>
          <div
            class='dimension-slider-content'
            slot='content'
          >
            {this.sliderLoading ? this.renderSkeleton() : this.renderTopKField(this.sliderDimensionList.list, 'slider')}
            {this.sliderDimensionList.distinct_count > this.sliderDimensionList.list.length && (
              <div
                class={['slider-load-more', { 'is-loading': this.sliderLoadMoreLoading }]}
                onClick={this.loadMore}
              >
                {this.$t(this.sliderLoadMoreLoading ? '正在加载...' : '加载更多')}
              </div>
            )}
          </div>
        </bk-sideslider>
      </div>
    );
  }
}
