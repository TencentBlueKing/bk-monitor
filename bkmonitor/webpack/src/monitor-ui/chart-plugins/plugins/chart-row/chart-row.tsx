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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import type { PanelModel } from '../../typings';

import './chart-row.scss';

interface IChartRowEvent {
  onCollapse: boolean;
}
interface IChartRowProps {
  panel: PanelModel;
}
@Component
export default class ChartRow extends tsc<IChartRowProps, IChartRowEvent> {
  @Prop({ required: true, type: Object }) readonly panel: PanelModel;

  handleCollapsed() {
    if (!this.panel.dragging) {
      this.$emit('collapse', !this.panel.collapsed);
    }
    this.panel.updateDragging(false);
  }
  handleClickIcon(e: MouseEvent) {
    if (this.panel.collapsed && e.target === e.currentTarget) {
      setTimeout(this.handleCollapsed, 20);
    }
  }
  render() {
    return (
      <div
        class={'chart-row'}
        onClick={this.handleCollapsed}
      >
        <i class='bk-icon icon-right-shape chart-row-icon' />
        <div class={`chart-row-content ${this.panel.collapsed ? '' : 'draggable-handle'} `}>
          {this.panel.title}
          <span class='panel-count'>({this.panel.panels?.length || 0})</span>
        </div>
      </div>
    );
  }
}
