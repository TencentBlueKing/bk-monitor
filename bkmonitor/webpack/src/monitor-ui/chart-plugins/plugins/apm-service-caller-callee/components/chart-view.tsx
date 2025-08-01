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

import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import DashboardPanel from 'monitor-ui/chart-plugins/components/flex-dashboard-panel';

import type { PanelModel, ZrClickEvent } from '../../../typings';

import './chart-view.scss';

interface IChartViewEvent {
  onZrClick?: (event: ZrClickEvent) => void;
}
interface IChartViewProps {
  panelsData: PanelModel[];
}
@Component({
  name: 'ChartView',
  components: {},
})
export default class ChartView extends tsc<IChartViewProps, IChartViewEvent> {
  @Prop({ required: true, type: Array, default: () => [] }) panelsData: PanelModel[];

  @Emit('zrClick')
  handleZrClick(p: ZrClickEvent) {
    return p;
  }
  render() {
    return (
      <div class='caller-callee-chart-view'>
        <DashboardPanel
          id={'caller-callee-chart-view'}
          column={3}
          panels={this.panelsData}
          onZrClick={this.handleZrClick}
        />
      </div>
    );
  }
}
