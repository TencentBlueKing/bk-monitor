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

import dayjs from 'dayjs';

export const profilingTraceChartTooltip = {
  position(point: any) {
    // 控制tolltip框的位置
    return [point[0], point[1]]; // 设置为鼠标的位置
  },
  enterable: true, // 可以让鼠标进入tooltip
  formatter: (params: any) => {
    let liHtmls = [];
    const pointTime = dayjs.tz(params[0].axisValue).format('YYYY-MM-DD HH:mm:ss');
    const traceData = params[0].data?.traceData ?? [];

    liHtmls = traceData.map(item => {
      return `<tr>
        <td>${item.time}</td>
        <td>${item.span_id}</td>
      </tr>`;
    });
    if (liHtmls?.length < 1) return '';

    return `<div class="monitor-chart-tooltips">
        <p class="tooltips-header">${pointTime}</p>
        <table class='trace-chart-tips-table'>
          <thead>
            <th>Time</th>
            <th>Span ID</th>
          </thead>
          <tbody>
            ${liHtmls?.join('')}
          </tbody>
        </table>
      </div>`;
  }
};
