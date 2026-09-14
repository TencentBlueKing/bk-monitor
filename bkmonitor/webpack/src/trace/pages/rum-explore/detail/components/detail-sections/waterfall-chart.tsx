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
import { defineComponent } from 'vue';
import type { PropType } from 'vue';

import type { IRumWaterfallVM } from '../../typings';

/**
 * 请求时序瀑布图：左侧阶段名与耗时定宽，右侧轨道按百分比定位色块。
 * DNS / TCP / TLS 被合并成连接复用说明时，在首行之后插入一条分隔说明。
 */
export default defineComponent({
  name: 'RumWaterfallChart',
  props: {
    data: {
      type: Object as PropType<IRumWaterfallVM | null>,
      default: null,
    },
  },
  setup(props) {
    return () => {
      const { data } = props;
      if (!data?.rows?.length) return null;
      return (
        <div class='rum-waterfall'>
          {data.rows.map((row, index) => [
            <div
              key={row.key}
              class='waterfall-row'
            >
              <span class='row-label'>{row.label}</span>
              <span class='row-duration'>{row.durationText}</span>
              <div class='row-track'>
                <span
                  style={{ left: `${row.startPercent}%`, width: `${row.durationPercent}%`, backgroundColor: row.color }}
                  class='row-block'
                />
              </div>
            </div>,
            /** 合并说明紧跟在首行之后，对应「浏览器准备」与「等待 TTFB」之间的连接复用提示 */
            index === 0 && data.mergedTip ? (
              <div
                key='merged-tip'
                class='waterfall-merged-tip'
              >
                <span class='tip-line' />
                <span class='tip-text'>{data.mergedTip}</span>
                <span class='tip-line' />
              </div>
            ) : null,
          ])}
          {data.markers?.length ? (
            <div class='waterfall-markers'>
              {data.markers.map(marker => (
                <span
                  key={marker.key}
                  style={{ left: `${marker.percent}%` }}
                  class='marker-item'
                >
                  {marker.label}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      );
    };
  },
});
