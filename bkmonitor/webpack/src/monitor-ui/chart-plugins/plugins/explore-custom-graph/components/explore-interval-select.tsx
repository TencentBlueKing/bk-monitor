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
import { Component, Emit, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { CHART_INTERVAL } from 'monitor-pc/constant/constant';

import type { EventRetrievalViewType, IOption } from 'monitor-pc/pages/data-retrieval/typings';

import './explore-interval-select.scss';

interface ExploreIntervalSelectEvents {
  onChange: (interval: EventRetrievalViewType.intervalType) => void;
}
interface ExploreIntervalSelectProps {
  interval: EventRetrievalViewType.intervalType;
  intervalList?: IOption[];
  selectLabel: string;
}

@Component
export default class ExploreIntervalSelect extends tsc<ExploreIntervalSelectProps, ExploreIntervalSelectEvents> {
  @Prop({ type: String }) selectLabel: string;
  /** 周期列表 */
  @Prop({ default: () => CHART_INTERVAL }) intervalList: IOption[];
  /** 图表汇聚周期 */
  @Prop({ type: [String, Number], default: 'auto' }) interval: EventRetrievalViewType.intervalType;

  @Ref('menu')
  menuRef: any;

  popoverInstance = null;

  get listLabelByIdMap() {
    return this.intervalList.reduce((prev, curr) => {
      prev[curr.id] = curr.name;
      return prev;
    }, {});
  }

  /** 汇聚方法值改变后回调 */
  @Emit('change')
  handleIntervalChange(interval: EventRetrievalViewType.intervalType) {
    if (this.interval === interval) return;
    this.popoverInstance?.hide?.();
    return interval;
  }

  async handleIntervalListShow(e: Event) {
    if (this.popoverInstance) {
      return;
    }
    this.popoverInstance = this.$bkPopover(e.currentTarget, {
      content: this.menuRef,
      trigger: 'click',
      placement: 'bottom',
      theme: 'light common-monitor',
      arrow: false,
      interactive: true,
      followCursor: false,
      boundary: 'viewport',
      distance: 4,
      offset: '-2, 0',
      onHidden: () => {
        this.popoverInstance?.destroy?.();
        this.popoverInstance = null;
      },
    });
    await this.$nextTick();
    this.popoverInstance?.show(100);
  }

  render() {
    return (
      <div class='explore-interval-select'>
        <span class='explore-interval-label'>{this.selectLabel}</span>
        <div
          class={`popover-trigger ${this.popoverInstance ? 'is-active' : ''}`}
          onClick={e => this.handleIntervalListShow(e)}
        >
          <span class='trigger-value'>{this.listLabelByIdMap[this.interval] || '--'}</span>
          <i class='icon-monitor icon-arrow-up' />
        </div>
        <div style='display: none'>
          <ul
            ref='menu'
            class='explore-interval-list-menu'
          >
            {this.intervalList.map(item => (
              <li
                key={item.id}
                class={`menu-item ${this.interval === item.id ? 'is-active' : ''}`}
                onClick={() => this.handleIntervalChange(item.id as EventRetrievalViewType.intervalType)}
              >
                {item.name}
              </li>
            ))}
          </ul>
        </div>
      </div>
    );
  }
}
