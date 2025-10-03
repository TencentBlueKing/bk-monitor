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
import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import SelectWrap from '../../utils/select-wrap';
import MetricContainer from './metric-container';

import type { MetricDetailV2 } from '@/pages/query-template/typings';

import './metric-selector.scss';

export interface IMetricSelectorProps {
  loading: boolean;
  metricDetail?: MetricDetailV2;
  getMetricList?: () => Promise<MetricDetailV2[]>;
}
@Component
export default class MetricSelector extends tsc<IMetricSelectorProps> {
  @Ref('metricSelectorContentRef') metricSelectorContentRef: HTMLElement;
  @Ref('metricSelectorTriggerRef') metricSelectorTriggerRef: { $el: HTMLElement };

  @Prop({ type: Object, default: () => null }) metricDetail: MetricDetailV2;
  @Prop({ type: Function, required: true }) getMetricList: () => Promise<MetricDetailV2[]>;

  show = false;
  loading = false;
  popoverInstance = null;
  metricList: MetricDetailV2[] = [];
  get selectMetricTips() {
    return '';
  }
  @Watch('show', { immediate: true })
  handleShowChange(val: boolean) {
    if (val) {
      this.handleGetMetricList();
    }
  }
  mounted() {}

  handleTriggerClick() {
    this.show = true;
    if (!this.popoverInstance) {
      this.popoverInstance = this.$bkPopover(this.metricSelectorTriggerRef.$el, {
        content: this.metricSelectorContentRef,
        trigger: 'manual',
        placement: 'bottom-start',
        theme: 'light common-monitor',
        arrow: false,
        interactive: true,
        boundary: 'window',
        distance: 20,
        zIndex: 9999,
        animation: 'slide-toggle',
        followCursor: false,
        onHide: (a, b, c) => {
          console.info(a, b, c, '================');
          return true;
        },
        onHidden: () => {
          // this.destroyPopoverInstance();
          // this.handleShowChange(false);
        },
      });
    }
    setTimeout(() => {
      this.popoverInstance?.show?.();
    }, 30);
  }
  async handleGetMetricList() {
    this.loading = true;
    const data = await this.getMetricList();
    this.metricList = data;
    this.loading = false;
  }
  render() {
    return (
      <div class='metric-selector'>
        <div class='metric-selector-trigger'>
          <SelectWrap
            ref='metricSelectorTriggerRef'
            backgroundColor={'#FDF4E8'}
            expanded={this.show}
            minWidth={432}
            tips={this.selectMetricTips}
            tipsPlacements={['right']}
            onClick={() => this.handleTriggerClick()}
          >
            {this.metricDetail ? (
              <span class='metric-name'>{this.metricDetail?.metricAlias || this.metricDetail?.name}</span>
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
            <MetricContainer
              loading={this.loading}
              metricList={this.metricList}
            />
          </div>
        </div>
      </div>
    );
  }
}
