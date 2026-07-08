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

import { type PropType, computed, defineComponent, shallowRef } from 'vue';

import ChartLazy from './chart-lazy';
import TimeSeriesCard from './time-series-card';
import MonitorCrossDrag from '@/components/monitor-cross-drag/monitor-cross-drag';

import type { DashboardRow } from '../typings/dashboard';
import type { ScopedVarMap } from '../variables/resolve';

import './dashboard-row.scss';

export default defineComponent({
  name: 'DashboardRow',
  props: {
    /** 分组行数据 */
    row: {
      type: Object as PropType<DashboardRow>,
      required: true,
    },
    /** 列数：1 / 2 / 3 */
    columns: {
      type: Number,
      default: 3,
    },
    height: {
      type: Number,
      default: 240,
    },
    maxHeight: {
      type: Number,
      default: 600,
    },
    minHeight: {
      type: Number,
      default: 240,
    },
    /** 变量取值映射 */
    scopedVars: {
      type: Object as PropType<ScopedVarMap>,
      default: () => ({}),
    },
  },
  emits: ['resize'],
  setup(props, { emit }) {
    /** 分组展开状态，折叠时不挂载图表（避免无谓取数） */
    const expanded = shallowRef(true);

    const gridStyle = computed(() => ({
      gridTemplateColumns: `repeat(${props.columns}, minmax(0, 1fr))`,
    }));

    const toggle = () => {
      expanded.value = !expanded.value;
    };

    const handleCrossResize = (height: number) => {
      console.log(height);
      emit('resize', height);
    };

    return {
      expanded,
      gridStyle,
      toggle,
      handleCrossResize,
    };
  },
  render() {
    return (
      <div class='dashboard-row'>
        <div
          class='dashboard-row__header'
          onClick={this.toggle}
        >
          <i
            class={[
              'icon-monitor',
              'icon-mc-triangle-down',
              'dashboard-row__arrow',
              { 'is-collapsed': !this.expanded },
            ]}
          />
          <span class='dashboard-row__title'>{this.row.title}</span>
          <span class='dashboard-row__count'>({this.row.panels.length})</span>
        </div>
        {this.expanded && (
          <div
            style={this.gridStyle}
            class='dashboard-row__grid'
          >
            {this.row.panels.map(panel => (
              <ChartLazy
                key={panel.id}
                minHeight={this.minHeight}
              >
                <div
                  style={{ height: `${this.height}px` }}
                  class='chart-card'
                >
                  <TimeSeriesCard
                    dashboardId={this.row.id}
                    panel={panel}
                    scopedVars={this.scopedVars}
                  />
                  <MonitorCrossDrag
                    maxHeight={this.maxHeight}
                    minHeight={this.minHeight}
                    onMove={this.handleCrossResize}
                  />
                </div>
              </ChartLazy>
            ))}
          </div>
        )}
      </div>
    );
  },
});
