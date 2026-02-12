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

import { type PropType, defineComponent, nextTick, shallowRef, useTemplateRef, watch } from 'vue';

import { random } from 'monitor-common/utils';
import VueEcharts from 'vue-echarts';

import DrillDownOptions from '../components/drill-down-options';
import EmptyStatus from '@/components/empty-status/empty-status';

import type { IGraphDrillDown } from '../../../typing';
import type { TooltipComponentOption } from 'echarts';

import './dimension-tree-map-charts.scss';

export default defineComponent({
  name: 'DimensionTreeMapCharts',
  props: {
    /** 维度列表 */
    dimensionList: {
      type: Array as PropType<{ id: string; name: string }[]>,
      default: () => [],
    },
    /** 图表数据 */
    chartData: {
      type: Array as PropType<IGraphDrillDown[]>,
      default: () => [],
    },
    displayDimensions: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
  },
  emits: ['drillDown'],
  setup(props, { emit }) {
    const showMenu = shallowRef(false);
    const menuInfo = shallowRef({
      x: 0,
      y: 0,
      data: null,
    });
    const menuContainerRef = useTemplateRef<InstanceType<typeof DrillDownOptions>>('menuContainer');

    /** 图表tooltips展示 */
    const tooltipFormatter: TooltipComponentOption['formatter'] = params => {
      return `<div class="monitor-chart-tooltips">
              <ul class="tooltips-content">
              <li class="tooltips-content-item">
                  <span class="item-series"
                   style="background-color:${params.color};">
                  </span>
                  <span class="item-name" style="color: #fafbfd;">${params.name}:</span>
                  <span class="item-value tag" style="color: #fafbfd;">
                   ${params.value}（${params.data?.row_data?.percentage}%）
                  </span>
                  </li>
              </ul>
              </div>`;
    };

    const commonOptions = {
      tooltip: {
        transitionDuration: 0,
        alwaysShowContent: false,
        backgroundColor: 'rgba(54,58,67,.88)',
        borderWidth: 0,
        textStyle: {
          fontSize: 12,
          color: '#BEC0C6',
        },
        extraCssText: 'border-radius: 4px',
        appendToBody: true,
        formatter: tooltipFormatter,
      },
    };

    const options = shallowRef({
      ...commonOptions,
      series: [],
    });

    watch(
      () => props.chartData,
      () => {
        console.log(props.chartData, 'chartData');
        options.value = {
          ...commonOptions,
          series: [
            {
              name: random(8),
              type: 'treemap',
              top: 0,
              left: 8,
              right: 8,
              bottom: 0,
              breadcrumb: {
                show: false,
              },
              itemStyle: {
                gapWidth: 2,
                borderRadius: 2,
              },
              label: {
                overflow: 'break',
              },
              roam: false,
              nodeClick: false,
              data: props.chartData.map(item => ({
                name: props.displayDimensions.map(id => item.dimensions[id]).join(' | '),
                value: item.value,
                itemStyle: {
                  color: item.color,
                },
                row_data: item,
              })),
            },
          ],
        };
      },
      {
        immediate: true,
      }
    );

    /** 图表点击事件 */
    const handleChartClick = params => {
      // 原生 MouseEvent
      const e = params.event.event;
      e.preventDefault();
      e.stopPropagation();
      // 只处理 treemap 的矩形
      if (params.componentType !== 'series' || params.seriesType !== 'treemap') {
        closeTreeMapMenu();
        return;
      }
      showTreeMapMenu(e.clientX + 5, e.clientY, params.data?.row_data);
    };

    /** 展示下钻功能菜单 */
    const showTreeMapMenu = (x: number, y: number, data: any) => {
      showMenu.value = true;
      menuInfo.value = { x, y, data };

      document.addEventListener('click', closeTreeMapMenu);

      nextTick(() => {
        const { width, height } = menuContainerRef.value.$el.getBoundingClientRect();
        if (x + width > window.innerWidth) {
          x = x - width;
        }
        if (y + height > window.innerHeight) {
          y = y - height;
        }
        menuInfo.value = { x, y, data };
      });
    };

    /** 关闭菜单 */
    const closeTreeMapMenu = () => {
      showMenu.value = false;
      menuInfo.value = {
        x: 0,
        y: 0,
        data: null,
      };
      document.removeEventListener('click', closeTreeMapMenu);
    };

    const handleMenuItemClick = (dimension: string) => {
      emit('drillDown', {
        dimension,
        where: props.displayDimensions.map(id => {
          return {
            method: 'eq',
            value: menuInfo.value.data?.dimensions?.[id] || '',
            condition: 'and',
            key: id,
          };
        }),
      });
      closeTreeMapMenu();
    };

    return {
      showMenu,
      menuInfo,
      options,
      handleChartClick,
      closeTreeMapMenu,
      handleMenuItemClick,
    };
  },
  render() {
    return (
      <div class='dimension-tree-map-charts'>
        <div
          ref='chartRef'
          class='echart-container'
        >
          {this.chartData.length ? (
            <VueEcharts
              ref='echart'
              option={this.options}
              autoresize
              onClick={this.handleChartClick}
            />
          ) : (
            <EmptyStatus type='empty' />
          )}

          <DrillDownOptions
            ref='menuContainer'
            style={{
              display: this.showMenu ? 'block' : 'none',
              left: `${this.menuInfo.x}px`,
              top: `${this.menuInfo.y}px`,
            }}
            active={this.displayDimensions?.[0] || ''}
            dimensions={this.dimensionList}
            hasTitle={true}
            isFixed={true}
            onSelect={this.handleMenuItemClick}
          />
        </div>
      </div>
    );
  },
});
