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
import { Component, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getMetricTip } from '../../utils/metric-tip';
import SelectWrap from '../../utils/select-wrap';
import MetricContainer from './metric-container';
import { MetricDetailV2 } from '@/pages/query-template/typings';

import type { IGetMetricListData, IGetMetricListParams } from './types';

import './metric-selector.scss';

export interface IMetricSelectorEvents {
  onConfirm: (metrics: MetricDetailV2[]) => void;
}
export interface IMetricSelectorProps {
  /** 选中的指标 */
  selectedMetric?: MetricDetailV2;
  /** 触发对象loading */
  triggerLoading?: boolean;
  /** 获取指标列表 */
  getMetricList?: (params: IGetMetricListParams) => Promise<IGetMetricListData>;
}
@Component
export default class MetricSelector extends tsc<IMetricSelectorProps, IMetricSelectorEvents> {
  @Ref('metricSelectorContentRef') metricSelectorContentRef: HTMLElement;
  @Ref('metricSelectorTriggerRef') metricSelectorTriggerRef: { $el: HTMLElement };

  @Prop({ type: Object, default: () => null }) selectedMetric: MetricDetailV2;
  @Prop({ type: Boolean, default: false }) triggerLoading: boolean;
  @Prop({ type: Function, required: true }) getMetricList: (
    params?: Partial<IGetMetricListParams>
  ) => Promise<IGetMetricListData>;
  /** 是否显示 */
  show = false;
  /** 是否loading */
  loading = false;
  /** 是否滚动加载 */
  loadingNextPage = false;
  /** 弹层实例 */
  popoverInstance = null;
  /** 指标列表 */
  metricList: MetricDetailV2[] = [];
  /** 每页条数 */
  pageSize = 20;
  /** 当前页 */
  page = 1;
  /** 总条数 */
  total = 0;
  /** 搜索值 */
  searchValue = '';
  /** 防抖时间 */
  debounceTimeSeconds = 300;
  /** 防抖定时器 */
  debounceTimer = null;

  get selectMetricTips() {
    /** 选中的指标提示 */
    return getMetricTip(this.selectedMetric);
  }
  get commonParams() {
    return {
      page: this.page,
      page_size: this.pageSize,
      conditions: [
        {
          key: 'query',
          value: this.searchValue,
        },
      ],
    };
  }
  /** 显示弹层 */
  showPopover() {
    this.page = 1;
    this.metricList = [];
    this.total = 0;
    this.show = true;
    this.loadingNextPage = false;
    this.handleGetMetricList();
  }
  /** 隐藏弹层 */
  hidePopover() {
    this.show = false;
    this.popoverInstance?.hide?.();
    this.popoverInstance?.destroy?.();
    this.popoverInstance = null;
  }
  /** 防抖获取指标列表 */
  debounceGetMetricList(): Promise<IGetMetricListData> {
    return new Promise(resolve => {
      if (this.debounceTimer) {
        clearTimeout(this.debounceTimer);
        this.debounceTimer = null;
      }
      this.debounceTimer = setTimeout(() => {
        this.debounceTimer = null;
        this.getMetricListData().then(data => {
          resolve(data);
        });
      }, this.debounceTimeSeconds);
    });
  }
  /** 获取指标列表数据 */
  async getMetricListData(params?: Partial<IGetMetricListParams>) {
    const data = await this.getMetricList({
      ...this.commonParams,
      ...params,
    })
      .then(data => {
        return {
          ...data,
          metric_list: Object.freeze(
            data.metric_list?.map?.(item => new MetricDetailV2(item)) || []
          ) as MetricDetailV2[],
        };
      })
      .catch(() => ({
        metric_list: [],
        count: 0,
        data_source_list: [],
        scenario_list: [],
        tag_list: [],
      }));
    return data;
  }
  /** 触发点击 */
  handleTriggerClick() {
    this.showPopover();
    if (!this.popoverInstance) {
      this.popoverInstance = this.$bkPopover(this.metricSelectorTriggerRef, {
        content: this.metricSelectorContentRef,
        trigger: 'manual',
        placement: 'bottom-start',
        theme: 'light common-monitor',
        arrow: false,
        interactive: true,
        distance: 20,
        zIndex: 9999,
        animation: 'slide-toggle',
        followCursor: false,
        boundary: 'window',
        onHidden: () => {
          this.show = false;
        },
      });
    }
    setTimeout(() => {
      this.popoverInstance?.show?.();
    }, 30);
  }
  /** 获取指标列表 */
  async handleGetMetricList() {
    this.loading = true;
    const data = await this.debounceGetMetricList();
    this.metricList = data.metric_list;
    this.total = data.count;
    this.loading = false;
  }
  /** 滚动加载 */
  async handleScrollEnd() {
    if (this.loadingNextPage || this.page * this.pageSize >= this.total) return;
    this.loadingNextPage = true;
    this.page = this.page + 1;
    const data = await this.debounceGetMetricList();
    this.metricList = [...this.metricList, ...data.metric_list];
    this.total = data.count;
    this.loadingNextPage = false;
  }
  /** 搜索值改变 */
  async handleQueryChange(value: string) {
    if (value?.trim() === this.searchValue?.trim()) return;
    this.loading = true;
    this.searchValue = value?.trim();
    this.page = 1;
    this.metricList = [];
    this.total = 0;
    const data = await this.debounceGetMetricList();
    this.metricList = data.metric_list;
    this.total = data.count;
    this.loading = false;
  }
  /** 确认选择指标 */
  handleConfirm(metrics: MetricDetailV2[]) {
    this.hidePopover();
    this.$emit('confirm', metrics);
  }
  /** 生成自定义指标 */
  handleCreateCustomMetric(value: string) {
    this.$emit('createCustomMetric', value);
  }
  render() {
    return (
      <div class='metric-selector'>
        <div
          ref='metricSelectorTriggerRef'
          class='metric-selector-trigger'
        >
          <SelectWrap
            backgroundColor={'#FDF4E8'}
            expanded={this.show}
            loading={this.triggerLoading}
            minWidth={432}
            tips={this.selectMetricTips}
            tipsPlacements={['right']}
            onClick={() => this.handleTriggerClick()}
          >
            {this.selectedMetric ? (
              <span class='metric-name'>{this.selectedMetric?.metricAlias || this.selectedMetric?.name}</span>
            ) : (
              <span class='metric-placeholder'>{this.$t('点击添加指标')}</span>
            )}
          </SelectWrap>
        </div>
        <div
          style='display:none;'
          hidden
        >
          <div
            ref='metricSelectorContentRef'
            class='metric-selector-content'
          >
            {this.show && (
              <MetricContainer
                loading={this.loading}
                loadingNextPage={this.loadingNextPage}
                metricList={this.metricList}
                onConfirm={this.handleConfirm}
                onCreateCustomMetric={this.handleCreateCustomMetric}
                onQueryChange={this.handleQueryChange}
                onScrollEnd={this.handleScrollEnd}
              />
            )}
          </div>
        </div>
      </div>
    );
  }
}
