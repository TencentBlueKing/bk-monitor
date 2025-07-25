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
import { Component, Emit, Inject, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import {
  createAnomalyDimensionTips,
  createGroupAnomalyDimensionTips,
} from 'monitor-common/tips/anomaly-dimension-tips';

import { EventReportType } from './types';

import './correlation-nav.scss';

interface IEvent {
  onActive: (active: number) => number;
}

interface IProps {
  isCorrelationMetrics?: boolean;
  list?: any[];
}

@Component({})
export default class CorrelationNav extends tsc<IProps, IEvent> {
  @Prop({ type: Array, default: () => [] }) list: any[];
  @Prop({ type: Boolean, default: false }) isCorrelationMetrics: boolean;
  @Inject('reportEventLog') reportEventLog: (eventType: string) => void;

  /** 当前选中指标 */
  active: null | string = null;

  /** 展开收起 */
  isCollapse = false;

  @Watch('list', { immediate: true })
  handleChange(val) {
    if (!this.active && val.length > 0 && val[0].metrics?.length > 0) {
      this.active = val[0].metrics[0].metric_name;
    }
  }
  setActive(val) {
    this.active = val;
  }
  /** 指标切换 */
  @Emit('active')
  handleActive(item) {
    this.setActive(item.metric_name);
    return item;
  }
  /** 切换展开收起 */
  handleToggleCollapse(activeAuto = false) {
    if (activeAuto && !this.isCollapse) {
      return;
    }
    this.isCollapse = !this.isCollapse;
  }
  renderClassification(item) {
    return (
      <div class='correlation-nav-classification'>
        <p
          class='classification-title'
          v-bk-tooltips={{
            placement: 'left',
            content: createGroupAnomalyDimensionTips(item, this.isCorrelationMetrics),
          }}
        >
          <i
            class={[
              'bk-icon bk-card-head-icon collapse-icon',
              this.isCollapse ? 'icon-right-shape' : 'icon-down-shape',
            ]}
            onClick={this.handleToggleCollapse.bind(this, false)}
          />
          <span class='classification-text'>{item.result_table_label_name}</span>
          <span class='classification-num'>
            {item?.dimension_anomaly_value_count
              ? [<strong key={'1'}>{item.dimension_anomaly_value_count}</strong>, '/', item.dimension_value_total_count]
              : item.metrics?.length}
          </span>
        </p>
        <bk-transition name='collapse'>
          <ul
            class='classification-list'
            v-show={!this.isCollapse}
          >
            {(item.metrics || []).map(metric => (
              <li
                key={metric.metric_name}
                class={['classification-list-item', { active: this.active === metric.metric_name }]}
                v-bk-tooltips={{
                  content: createAnomalyDimensionTips(metric, this.isCorrelationMetrics),
                  placement: 'left',
                  onShown: () => {
                    this.reportEventLog?.(EventReportType.Tips);
                  },
                }}
                onClick={() => this.handleActive(metric)}
              >
                <span class={{ 'level-icon': !!metric.anomaly_level, [`level-${metric.anomaly_level}`]: true }} />
                <span class='classification-list-item-text'>{metric.metric_name_alias}</span>
                {(metric.totalPanels || []).length > 0 && (
                  <span class='classification-list-item-num'>{metric.totalPanels.length}</span>
                )}
              </li>
            ))}
          </ul>
        </bk-transition>
      </div>
    );
  }
  render() {
    return <div class='correlation-nav'>{this.list.map(item => this.renderClassification(item))}</div>;
  }
}
