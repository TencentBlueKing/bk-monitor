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
import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { MetricDetail } from '../typings';

import './aiops-monitor-metric-select.scss';

interface IProps {
  value?: string[];
  metrics?: MetricDetail[];
}

@Component
export default class AiopsMonitorMetricSelect extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) value: string[];
  @Prop({ type: Array, default: () => [] }) metrics: MetricDetail[];

  localValue = [];
  tags: MetricDetail[] = [];

  showSelector = false;

  showAll = false;

  @Watch('value', { immediate: true })
  handleWatchValue(value: string[]) {
    if (JSON.stringify(value) !== JSON.stringify(this.localValue)) {
      this.localValue = this.value;
      this.handleGetMetricTag();
    }
  }
  @Watch('metrics', { immediate: true })
  handleWatchMetrics(value) {
    if (value.length) {
      this.handleGetMetricTag();
    }
  }

  /**
   * @description 获取tag数据
   */
  handleGetMetricTag() {
    const metricMap = new Map();
    this.metrics.forEach(item => {
      metricMap.set(item.metric_id, item);
    });
    const tags = [];
    this.localValue.forEach(id => {
      const metric = metricMap.get(id);
      if (metric) {
        tags.push(metric);
      }
    });
    this.tags = tags;
    this.$nextTick(() => {
      this.getOverflowHideCount();
    });
  }

  handleClick() {
    this.showAll = !this.showAll;
  }

  /**
   * @description 获取隐藏的数据
   */
  getOverflowHideCount() {
    const tagsWrap = this.$el.querySelector('.tag-select-wrap');
    const tagsEl = tagsWrap.querySelectorAll('.tag-item');
    for (let i = 0; i < tagsEl.length; i++) {
      const width = tagsEl[i].offsetWidth;
      console.log(width, i);
    }
  }

  render() {
    return (
      <span
        class={['aiops-monitor-metric-select-component', { 'show-all': this.showAll }]}
        onClick={this.handleClick}
      >
        <div class='tag-select-wrap'>
          {this.tags.map(item => (
            <div
              key={item.metric_id}
              class='tag-item'
            >
              <span>{item.name}</span>
              <span class='icon-monitor icon-mc-close'></span>
            </div>
          ))}
        </div>
        <div class='icon-monitor icon-arrow-down'></div>
      </span>
    );
  }
}
