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
import { type MetricSearchTagMode, MetricSearchTagModeMap, MetricSearchTags } from './types';
import EmptyStatus from '@/components/empty-status/empty-status';

import type { EmptyStatusOperationType } from '@/components/empty-status/types';
import type { MetricDetailV2 } from '@/pages/query-template/typings/metric';

import './metric-container.scss';

export interface IMetricSelectorContainerEvents {
  /** 确认选择指标 */
  onConfirm: (metrics: MetricDetailV2[]) => void;
  /** 生成自定义指标 */
  onCreateCustomMetric: (v: string) => void;
  /** 查询指标 */
  onQueryChange: (v: string) => void;
  /** 滚动加载指标 */
  onScrollEnd: (e: Event) => void;
}

export interface IMetricSelectorContainerProps {
  /** 是否loading */
  loading?: boolean;
  /** 是否loading下一页 */
  loadingNextPage?: boolean;
  /** 指标列表 */
  metricList: MetricDetailV2[];
  /** 选中的指标 */
  selectedMetric?: MetricDetailV2;
}
@Component
export default class MetricSelectorContainer extends tsc<
  IMetricSelectorContainerProps,
  IMetricSelectorContainerEvents
> {
  @Ref('searchInputRef') searchInputRef: HTMLInputElement;
  @Ref('metricListRef') metricListRef: HTMLDivElement;

  @Prop({ type: Array, default: () => [] }) metricList: MetricDetailV2[];
  @Prop({ type: Boolean, default: false }) loading: boolean;
  @Prop({ type: Boolean, default: false }) loadingNextPage: boolean;
  @Prop({ type: Object }) selectedMetric: MetricDetailV2;

  /** 数据类型 */
  dataType = 'all';
  /** 监控场景 */
  monitorScenes = 'all';
  /** 是否多选 */
  isMultiple = false;
  /** 本地选中的指标 */
  localSelectedMetrics: MetricDetailV2[] = [];
  /** 搜索值 */
  searchValue = '';
  /** 是否滚动加载 */
  isScrollEnd = false;
  /** 当前聚焦的指标索引 */
  focusIndex = -1;
  /** 是否使用上下键选择指标 */
  isArrowKeySet = false;
  /** 鼠标hover的索引 */
  hoverIndex = -1;
  /** 鼠标hover定时器 */
  hoverTimer = null;
  /** 鼠标hover的popover实例 */
  hoverPopoverInstance = null;

  /** 是否显示左侧标签搜索栏 */
  get showLeftTags() {
    return this.dataType !== 'all' || this.monitorScenes !== 'all';
  }
  /** 是否显示创建自定义指标按钮 */
  get showCreateCustomMetricButton() {
    if (this.searchValue.length > 0 && this.metricList.length === 0 && !this.loading && !this.loadingNextPage) {
      const [resultTableId, metricField] = this.searchValue.split('.');
      if (!resultTableId || !metricField || !/^[_a-zA-Z][a-zA-Z0-9_]*$/.test(metricField)) {
        return false;
      }
      return true;
    }
    return false;
  }
  mounted() {
    this.initFocus();
    document.addEventListener('keydown', this.handleKeyDown);
    document.addEventListener('keyup', this.handleKeyUp);
    this.metricListRef.addEventListener('keydown', this.handleContainerKeyDown);
  }
  beforeDestroy() {
    this.handleMetricMouseleave();
    document.removeEventListener('keydown', this.handleKeyDown);
    document.removeEventListener('keyup', this.handleKeyUp);
    this.metricListRef.removeEventListener('keydown', this.handleContainerKeyDown);
  }
  /** 初始化聚焦输入框 */
  initFocus() {
    setTimeout(() => {
      this.searchInputRef?.focus();
    }, 300); // 300ms 展开动画结束后聚焦
  }
  /** 容器按键事件 */
  handleContainerKeyDown(e: KeyboardEvent) {
    // 回车键确认
    if (['Enter', 'NumpadEnter'].includes(e.code)) {
      const metric = this.metricList[this.focusIndex];
      metric && this.$emit('confirm', [metric]);
    }
  }
  /** 按键事件 */
  handleKeyDown(e: KeyboardEvent) {
    // 上下键选择指标
    if (['ArrowDown', 'ArrowUp'].includes(e.code)) {
      e.preventDefault();
      e.stopPropagation();
      this.metricListRef.focus();
      let index = e.code === 'ArrowUp' ? this.focusIndex - 1 : this.focusIndex + 1;
      if (this.focusIndex === -1) {
        // 第一次按上下键，选中第一个或最后一个
        index = e.code === 'ArrowUp' ? this.metricList.length - 1 : 0;
      } else {
        if (index < 0) {
          index = this.metricList.length - 1;
        } else {
          index = index <= this.metricList.length - 1 ? index : 0;
        }
      }
      this.isArrowKeySet = true;
      const metric = this.metricList[index];
      const metricDom = this.metricListRef.querySelector(`#${metric.metricDomId}`) as HTMLElement;
      metricDom?.focus();
      this.focusIndex = index;
      return;
    }
  }
  /** 按键释放事件 */
  handleKeyUp(e: KeyboardEvent) {
    if (['ArrowDown', 'ArrowUp'].includes(e.code)) {
      this.isArrowKeySet = false;
    }
  }
  /** 选择搜索标签 */
  handleSelectSearchTagChange(mode: MetricSearchTagMode, activeId: string) {
    if (mode === MetricSearchTagModeMap.DataType) {
      this.dataType = activeId;
      return;
    }
    this.monitorScenes = activeId;
  }
  /** 选择指标 */
  handleSelectMetric(metric: MetricDetailV2, selected?: boolean) {
    if (!this.isMultiple) {
      this.$emit('confirm', [metric]);
      return;
    }
    const isSelected = selected ?? !this.localSelectedMetrics.some(item => item.metric_id === metric.metric_id);
    if (isSelected) {
      this.localSelectedMetrics.push(metric);
    } else {
      this.localSelectedMetrics = this.localSelectedMetrics.filter(item => item.metric_id !== metric.metric_id);
    }
  }
  /** 搜索值改变 */
  handleSearchValueChange(value: string) {
    if (value?.trim() === this.searchValue?.trim()) return;
    this.searchValue = value?.trim();
    this.$emit('queryChange', value?.trim());
  }
  /** 指标鼠标移入 */
  handleMetricMouseenter(e: MouseEvent, metric: MetricDetailV2, index: number) {
    this.focusIndex = index;
    this.hoverIndex = index;
    const target = e.target as HTMLElement;
    this.hoverTimer && window.clearTimeout(this.hoverTimer);
    this.hoverTimer = setTimeout(() => {
      if (this.hoverIndex !== index) return;
      this.hoverPopoverInstance = this.$bkPopover(target, {
        content: getMetricTip(metric),
        trigger: 'manual',
        theme: 'tippy-metric',
        arrow: true,
        placement: 'right',
        boundary: 'window',
        allowHTML: true,
      });
      this.hoverPopoverInstance?.show();
    }, 500);
  }
  /** 指标鼠标移出 */
  handleMetricMouseleave() {
    this.hoverIndex = -1;
    this.hoverTimer && window.clearTimeout(this.hoverTimer);
    this.hoverPopoverInstance?.hide();
    this.hoverPopoverInstance?.destroy();
    this.hoverPopoverInstance = null;
  }
  /** 指标列表滚动 */
  handleMetricListScroll(e: Event) {
    // 如果正在使用上下键选择指标，则不触发滚动加载事件
    if (this.isArrowKeySet) return;
    const { scrollHeight, scrollTop, clientHeight } = e.target as HTMLElement;
    const isEnd = scrollHeight - scrollTop === clientHeight && scrollTop;
    if (isEnd) {
      this.$emit('scrollEnd', e);
    }
    this.isScrollEnd = !!isEnd;
  }
  handleClearFilter() {
    this.handleSearchValueChange('');
  }
  handleEmptyOperation(type: EmptyStatusOperationType) {
    if (type === 'clear-filter') {
      this.handleClearFilter();
    }
  }
  /** 获取搜索值对应高亮节点 */
  getSearchNode(str: string) {
    if (!str) return str;
    const len = this.searchValue.length;
    if (!this.searchValue?.trim().length || !str.toLocaleLowerCase().includes(this.searchValue.toLocaleLowerCase()))
      return str;
    const list = [];
    let lastIndex = -1;
    const keyword = this.searchValue.replace(/([.*/]{1})/gim, '\\$1');
    str.replace(new RegExp(`${keyword}`, 'igm'), (key, index) => {
      if (list.length === 0 && index !== 0) {
        list.push(str.slice(0, index));
      } else if (lastIndex >= 0) {
        list.push(str.slice(lastIndex + key.length, index));
      }
      list.push(<span class='is-keyword'>{key}</span>);
      lastIndex = index;
      return key;
    });
    if (lastIndex >= 0) {
      list.push(str.slice(lastIndex + len));
    }
    return list.length ? list : str;
  }
  /** 创建公共标签项 */
  createCommonTagsItem(mode: MetricSearchTagMode, activeId = 'all') {
    return (
      <div class='common-search-tags'>
        {MetricSearchTags[mode]?.name}
        <ul class='tags-list'>
          {MetricSearchTags[mode]?.tags.map(item => (
            <bk-tag
              key={item.id}
              theme={item.id === activeId ? 'info' : ''}
              onClick={() => this.handleSelectSearchTagChange(mode, item.id)}
            >
              {item.name}
            </bk-tag>
          ))}
        </ul>
        {!this.selectedMetric && mode === MetricSearchTagModeMap.DataType && (
          <bk-checkbox
            class='multiple-checkbox'
            checked={this.isMultiple}
            disabled={this.localSelectedMetrics.length > 1}
            size='small'
            onChange={v => {
              this.isMultiple = v;
            }}
          >
            {this.$t('多选数据')}
          </bk-checkbox>
        )}
      </div>
    );
  }
  /** 创建指标项 */
  createMetricItem(metric: MetricDetailV2, index: number) {
    return (
      <div
        id={metric.metricDomId}
        key={metric.metric_id}
        class='metric-list-item'
        tabindex={0}
        onClick={() => this.handleSelectMetric(metric)}
        onMouseenter={e => this.handleMetricMouseenter(e, metric, index)}
        onMouseleave={this.handleMetricMouseleave}
      >
        <div class='item-title'>
          {this.isMultiple && (
            <span onClick={e => e.stopPropagation()}>
              <bk-checkbox
                checked={this.localSelectedMetrics.includes(metric)}
                size='small'
                onChange={(v: boolean) => this.handleSelectMetric(metric, v)}
              />
            </span>
          )}
          <span
            style={{
              marginLeft: this.isMultiple ? '8px' : '0',
            }}
            class='icon-monitor icon-mc-event-chart item-title-icon'
          />
          <span class='item-title-readable-name'>{this.getSearchNode(metric.readable_name)}</span>
          {metric.metric_field_name && metric.metric_field_name !== metric.metric_field && (
            <span class='item-title-alias'>{metric.metric_field_name}</span>
          )}
        </div>
        <div class='item-subtitle'>
          {metric.result_table_label_name} / {metric.data_source_label} / {metric.related_name}
        </div>
      </div>
    );
  }
  createSkeletonItem(index: number) {
    return (
      <div
        key={index}
        class='metric-list-item'
      >
        <div class='item-title'>
          <div class='skeleton-element skeleton-title-icon' />
          <div class='skeleton-element skeleton-title' />
        </div>
        <div class='item-subtitle'>
          <div class='skeleton-element skeleton-subtitle' />
        </div>
      </div>
    );
  }
  render() {
    return (
      <div class='metric-selector-container'>
        <div class='selector-container-tags'>
          {this.createCommonTagsItem(MetricSearchTagModeMap.DataType, this.dataType)}
          {this.createCommonTagsItem(MetricSearchTagModeMap.MonitorScenes, this.monitorScenes)}
        </div>
        <div class='selector-container-search'>
          <bk-input
            ref='searchInputRef'
            class='search-input'
            right-icon='bk-icon icon-search'
            value={this.searchValue}
            clearable
            onChange={this.handleSearchValueChange}
          />
          <div class='search-refresh'>
            <span>{this.$t('搜不到想要的？')}</span>
            <i18n path='{0} 试试'>
              <bk-button
                class='refresh-btn'
                size='small'
                theme='primary'
                text
              >
                {this.$t('刷新')}
              </bk-button>
            </i18n>
          </div>
        </div>
        <div class='selector-container-metrics'>
          <div class='metric-list-wrapper'>
            <div
              ref='metricListRef'
              class='metric-list'
              tabindex={0}
              onScroll={this.handleMetricListScroll}
            >
              {this.loading
                ? [...Array(10)].map((_, index) => this.createSkeletonItem(index))
                : this.metricList.map((item, index) => this.createMetricItem(item, index))}
              {!this.metricList.length && !this.loading && !this.loadingNextPage && (
                <div class='metric-list-empty'>
                  <EmptyStatus
                    type={this.searchValue.length > 0 ? 'search-empty' : 'empty'}
                    onOperation={this.handleEmptyOperation}
                  >
                    {this.showCreateCustomMetricButton && (
                      <div class='search-empty-msg'>
                        <p class='tip-text'>{this.$t('你可以将该搜索内容直接自定义为指标选项')}</p>
                        <bk-button
                          style='margin-right: 10px'
                          title='primary'
                          text
                          onClick={this.$emit('createCustomMetric')}
                        >
                          {this.$t('生成自定义指标')}
                        </bk-button>
                        <bk-button
                          title='primary'
                          text
                          onClick={this.handleClearFilter}
                        >
                          {this.$t('清空筛选条件')}
                        </bk-button>
                      </div>
                    )}
                  </EmptyStatus>
                </div>
              )}
              {this.loadingNextPage && (
                <div class='metric-list-loading'>
                  <bk-loading
                    isLoading={this.loadingNextPage}
                    mode='spin'
                    size='mini'
                    theme='primary'
                  />
                  {this.$t('加载中...')}
                </div>
              )}
            </div>
          </div>
          {this.showLeftTags && <div class='metric-list-tags'>dd</div>}
        </div>
        {this.isMultiple && (
          <div class='selector-container-footer'>
            <span class='selected-title'>{this.$t('已选：')}</span>
            <div class='selected-metrics-wrapper'>
              {this.localSelectedMetrics?.map(item => (
                <bk-tag
                  key={item.metric_id}
                  v-bk-tooltips={{
                    content: getMetricTip(item),
                    placement: 'top-start',
                    delay: [500, 0],
                    theme: 'tippy-metric',
                  }}
                  closable
                  onClose={() => this.handleSelectMetric(item, false)}
                >
                  {item.metric_field_name || item.readable_name}
                </bk-tag>
              ))}
            </div>
            <div class='buttons-wrapper'>
              <bk-button
                class='confirm-btn'
                disabled={this.localSelectedMetrics.length < 1}
                theme='primary'
                onClick={() => this.$emit('confirm', this.localSelectedMetrics)}
              >
                {this.$t('确定')}
              </bk-button>
              <bk-button onClick={() => this.$emit('confirm', this.selectedMetric)}>{this.$t('取消')}</bk-button>
            </div>
          </div>
        )}
      </div>
    );
  }
}
