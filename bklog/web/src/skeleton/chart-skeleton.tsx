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
import { computed, defineComponent, shallowRef, watch } from 'vue';

import './chart-skeleton.scss';

const Y_AXIS_LINES = Array(5).fill(null);

function generateLinePath(length: number, height: number): string {
  const points = [];
  const segmentWidth = 100 / (length - 1);

  for (let i = 0; i < length; i++) {
    const x = i * segmentWidth || 1;
    const y = height * (0.2 + Math.random() * 0.6); // 随机高度（保留边距）
    points.push(`${x} ${y}`);
  }
  return `M ${points.join(' L')}`;
}
export default defineComponent({
  name: 'ChartSkeleton',
  props: {
    type: {
      type: String,
      default: 'line', // 'line' | 'bar'
      validator: (val: string) => ['line', 'bar'].includes(val),
    },
    height: {
      type: Number,
      default: 160,
      validator: (val: number) => val > 0,
    },
    length: {
      type: Number,
      default: 6,
      validator: (val: number) => val > 0,
    },
  },
  setup(props) {
    const maxHeight = props.height - 60;
    // 柱状图高度范围
    const BAR_HEIGHT_RANGE = { min: 30, max: maxHeight };

    // 1. 使用 shallowRef 缓存随机高度（避免 computed 重复计算）
    const barHeights = shallowRef<string[]>([]);

    // 2. 静态标记（非响应式数据）
    const isLineChart = props.type === 'line';

    // 3. 生成柱状图高度（仅在 length 变化时重新计算）
    const updateBarHeights = () => {
      barHeights.value = Array(props.length)
        .fill(0)
        .map(
          () => `${Math.floor(Math.random() * (BAR_HEIGHT_RANGE.max - BAR_HEIGHT_RANGE.min)) + BAR_HEIGHT_RANGE.min}%`,
        );
    };

    const dynamicArray = computed(() => Array(props.length).fill(null));

    watch(
      () => props.length,
      (newVal, oldVal) => {
        if (newVal !== oldVal && !isLineChart) {
          updateBarHeights();
        }
      },
      { immediate: true },
    );

    return () => (
      <div class='bk-log-chart-skeleton'>
        <div
          style={{ height: `${props.height}px` }}
          class='chart-area'
        >
          {/* 网格线 (固定5条) */}
          <div class='chart-grid'>
            {Y_AXIS_LINES.map((_, index) => (
              <div
                key={`grid-${index}`}
                class='grid-line skeleton'
              />
            ))}
          </div>

          <div class='y-axis-labels'>
            {Y_AXIS_LINES.map((_, index) => (
              <div
                key={`y-label-${index}`}
                class='y-label skeleton'
              />
            ))}
          </div>

          <div class='x-axis-labels'>
            {dynamicArray.value.map((_, index) => (
              <div
                key={`x-label-${index}`}
                class='x-label skeleton'
              />
            ))}
          </div>

          {/* 图表内容 */}
          <div class='chart-content'>
            {isLineChart ? (
              // 折线图
              <div class='line-container'>
                <svg
                  width='100%'
                  height='100%'
                  class='line-path'
                >
                  <path
                    d={generateLinePath(props.length, props.height)}
                    fill='none'
                    stroke='#3a84ff'
                  />
                </svg>
                <div class='line-point-box'>
                  {dynamicArray.value.map((_, i) => (
                    <div
                      key={`point-${i}`}
                      class='line-point'
                    >
                      <div class='line-point-shadow'></div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              // 柱状图
              <div class='bar-skeleton'>
                {dynamicArray.value.map((_, i) => (
                  <div
                    key={`bar-${i}`}
                    style={{
                      height: barHeights.value[i],
                    }}
                    class='bar-item'
                  >
                    <div class='bar-item-shadow'></div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  },
});
