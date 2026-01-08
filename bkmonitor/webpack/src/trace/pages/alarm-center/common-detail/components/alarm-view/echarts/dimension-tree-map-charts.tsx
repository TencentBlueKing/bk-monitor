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

import { defineComponent, nextTick, shallowRef, useTemplateRef } from 'vue';

import VueEcharts from 'vue-echarts';

import './dimension-tree-map-charts.scss';

export default defineComponent({
  name: 'DimensionTreeMapCharts',
  props: {
    dimensionList: {
      type: Array,
      default: () => [],
    },
  },
  emits: ['drillDown'],
  setup(_, { emit }) {
    const showMenu = shallowRef(false);
    const menuInfo = shallowRef({
      x: 0,
      y: 0,
      data: null,
    });
    const menuContainerRef = useTemplateRef<HTMLDivElement>('menuContainer');

    const options = {
      tooltip: {},
      series: [
        {
          name: 'dimension-analysis',
          type: 'treemap',
          breadcrumb: {
            show: false,
          },
          roam: false,
          nodeClick: false,
          data: [
            { name: 'A', value: 10 },
            {
              name: 'B',
              value: 20,
              children: [
                { name: 'B1', value: 5 },
                { name: 'B2', value: 15 },
              ],
            },
          ],
        },
      ],
    };

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
      showTreeMapMenu(e.clientX + 5, e.clientY, {});
    };

    const showTreeMapMenu = (x: number, y: number, data: any) => {
      showMenu.value = true;
      menuInfo.value = { x, y, data };

      document.addEventListener('click', closeTreeMapMenu);

      nextTick(() => {
        const { width, height } = menuContainerRef.value.getBoundingClientRect();
        if (x + width > window.innerWidth) {
          x = x - width;
        }
        if (y + height > window.innerHeight) {
          y = y - height;
        }
        menuInfo.value = { x, y, data };
      });
    };

    const closeTreeMapMenu = () => {
      showMenu.value = false;
      menuInfo.value = {
        x: 0,
        y: 0,
        data: null,
      };
      document.removeEventListener('click', closeTreeMapMenu);
    };

    const handleMenuItemClick = (item: any) => {
      emit('drillDown', item);
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
        <div class='echart-container'>
          <VueEcharts
            ref='echart'
            option={this.options}
            autoresize
            onClick={this.handleChartClick}
          />

          <div
            ref='menuContainer'
            style={{
              display: this.showMenu ? 'block' : 'none',
              left: `${this.menuInfo.x}px`,
              top: `${this.menuInfo.y}px`,
            }}
            class='echarts-menu-container'
          >
            <div class='echarts-menu-title'>下钻至</div>
            <div class='echarts-menu'>
              {this.dimensionList.map(item => (
                <div
                  key={item.name}
                  class='echarts-menu-item'
                  onClick={() => this.handleMenuItemClick(item)}
                >
                  {item.name}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  },
});
