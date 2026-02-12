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

import { type MaybeRef, type Ref, computed, shallowRef } from 'vue';

import { get } from '@vueuse/core';
import dayjs from 'dayjs';

import type { TooltipComponentOption } from 'echarts';

export const useChartTooltips = (
  chartRef: Ref<Element>,
  {
    isMouseOver,
    hoverAllTooltips,
    options,
  }: {
    hoverAllTooltips: MaybeRef<boolean>;
    isMouseOver: MaybeRef<boolean>;
    options: MaybeRef<any>;
  }
) => {
  const tooltipsSize = shallowRef<number>();
  const tableToolSize = shallowRef<number>();
  const handleSetTooltip: TooltipComponentOption['formatter'] = params => {
    if (!get(isMouseOver) && !get(hoverAllTooltips)) return undefined;
    if (!params || params.length < 1 || params.every(item => item.value === null)) {
      return;
    }
    let liHtmlList = [];
    let ulStyle = '';
    let hasWrapText = false;
    const pointTime = dayjs.tz(+params[0].axisValue).format('YYYY-MM-DD HH:mm:ssZZ');
    liHtmlList = params.map(item => {
      const markColor = 'color: #fafbfd;';
      if (item.value === null) return '';
      const rawData = get(options).series?.[+item.seriesIndex].raw_data;
      const unitFormatter = rawData.unitFormatter || ((v: string) => ({ text: v }));
      const precision =
        !['none', ''].some(val => val === rawData.unit) && +rawData.precision < 1 ? 2 : +rawData.precision;
      const valueObj = unitFormatter(item.value, precision);
      return `<li class="tooltips-content-item">
                  <span class="item-series"
                   style="background-color:${item.color};">
                  </span>
                  <span class="item-name" style="${markColor}">${item.seriesName}:</span>
                  <span class="item-value" style="${markColor}">
                  ${valueObj.text} ${valueObj.suffix || ''}</span>
                  </li>`;
    });
    if (liHtmlList?.length < 1) return '';
    // 如果超出屏幕高度，则分列展示，100为预估预留空间（表头 + tooltip 内边距等），22为每行高度
    const maxLen = Math.ceil((window.innerHeight - 100) / 22);
    // 如果列表项数量超过单列最大行数，且已有 tooltip 尺寸信息
    if (liHtmlList.length > maxLen && get(tooltipsSize)) {
      hasWrapText = true;
      // 计算需要几列
      const cols = Math.ceil(liHtmlList.length / maxLen);
      // 超过1列时禁用文本换行
      if (cols > 1) hasWrapText = false;
      // 记录/更新单列宽度（取最小值避免越来越宽）
      tableToolSize.value = get(tableToolSize)
        ? Math.min(get(tableToolSize), get(tooltipsSize)[0])
        : get(tooltipsSize)[0];
      // 设置 flex 布局，宽度 = 列数 * 单列宽度，但不超过屏幕一半
      ulStyle = `display:flex; flex-wrap:wrap; width: ${Math.min(5 + cols * get(tableToolSize), window.innerWidth / 2 - 20)}px;`;
    }
    return `<div class="monitor-chart-tooltips">
              <p class="tooltips-header">
                  ${pointTime}
              </p>
              <ul class="tooltips-content ${hasWrapText ? 'wrap-text' : ''}" style="${ulStyle}">
                  ${liHtmlList?.join('')}
              </ul>
              </div>`;
  };
  const tooltipsOptions = computed(() => ({
    show: true,
    // trigger: 'axis',
    // axisPointer: {
    //   type: 'line',
    //   label: {
    //     backgroundColor: '#6a7985',
    //   },
    // },
    transitionDuration: 0,
    alwaysShowContent: false,
    backgroundColor: 'rgba(54,58,67,.88)',
    borderWidth: 0,
    textStyle: {
      fontSize: 12,
      color: '#BEC0C6',
    },
    extraCssText: 'border-radius: 4px',
    axisPointer: {
      type: 'cross',
      axis: 'auto',
      label: {
        show: false,
        // formatter: (params: any) => {
        //   if (params.axisDimension === 'y') {
        //     curPoint.value.yAxis = params.value;
        //   } else {
        //     curPoint.value.xAxis = params.value;
        //     curPoint.value.dataIndex = params.seriesData?.length ? params.seriesData[0].dataIndex : -1;
        //   }
        // },
      },
      crossStyle: {
        color: 'transparent',
        opacity: 0,
        width: 0,
      },
    },
    appendToBody: true,
    trigger: 'axis',
    formatter: handleSetTooltip,
    position: (pos: (number | string)[], _params: any, _domm: any, _rect: any, size: any) => {
      const { contentSize } = size;
      const chartRect = chartRef.value?.getBoundingClientRect();
      const posRect = {
        x: chartRect.x + +pos[0],
        y: chartRect.y + +pos[1],
      };
      const position = {
        left: 0,
        top: 0,
      };
      const canSetBottom = window.innerHeight - posRect.y - contentSize[1];
      if (canSetBottom > 0) {
        position.top = +pos[1] - Math.min(20, canSetBottom);
      } else {
        position.top = +pos[1] + canSetBottom - 20;
      }
      const canSetLeft = window.innerWidth - posRect.x - contentSize[0];
      if (canSetLeft > 0) {
        position.left = +pos[0] + Math.min(20, canSetLeft);
      } else {
        position.left = +pos[0] - contentSize[0] - 20;
      }
      if (contentSize[0]) tooltipsSize.value = contentSize;
      return position;
    },
  }));

  return {
    tooltipsSize,
    tooltipsOptions,
  };
};
