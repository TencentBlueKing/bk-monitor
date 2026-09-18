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
import { computed, defineComponent } from 'vue';
import type { PropType } from 'vue';

import { useI18n } from 'vue-i18n';

import { RATING_META } from '../../constants';

import type { IRumWaterfallMarkerVM, IRumWaterfallVM } from '../../typings';

import './waterfall-chart.scss';

/**
 * 请求时序瀑布图：左侧阶段名与耗时定宽，右侧轨道按百分比定位色块。
 * 首行为汇总时间轴，把各阶段的色块按同一套 left / width / color 叠加到一条轨道上。
 * DNS / TCP / TLS 被合并成连接复用说明时，在时间轴之后的第一行下方插入一条分隔说明。
 */
export default defineComponent({
  name: 'RumWaterfallChart',
  props: {
    data: {
      type: Object as PropType<IRumWaterfallVM | null>,
      default: null,
    },
    /** span 类型（如 view）：view 时额外包一层标题与健康度图例 */
    spanType: {
      type: String,
      default: null,
    },
  },
  setup(props) {
    const { t } = useI18n();

    const markerColumns = computed(() => {
      const rowCounter = new Map<number, IRumWaterfallMarkerVM[]>();
      let maxRowCount = 1;
      for (const marker of props.data.markers) {
        const column = rowCounter.get(marker.percent) ?? [];
        rowCounter.set(marker.percent, [...column, marker]);
        maxRowCount = Math.max(maxRowCount, column.length + 1);
      }

      return {
        maxRowCount,
        columns: Array.from(rowCounter.entries()),
      };
    });

    const renderWaterfall = () => {
      const { data } = props;
      const { columns, maxRowCount } = markerColumns.value;
      return (
        <div class='rum-waterfall-wrap'>
          {columns.length ? (
            <div
              style={{ height: `${maxRowCount * 20}px` }}
              class='waterfall-markers'
            >
              {columns.map(column => (
                <span
                  key={column[0]}
                  style={{ left: `${column[0]}%` }}
                  class='marker-column'
                >
                  <div class='marker-line' />
                  <div class='marker-list'>
                    {column[1].map(marker => (
                      <div
                        key={marker.key}
                        class='marker-item'
                      >
                        <span class='marker-label'>{marker.label}</span>
                        <span class='marker-duration'>{marker.valueText}</span>
                      </div>
                    ))}
                  </div>
                </span>
              ))}
            </div>
          ) : null}
          <div class='waterfall-row timestamp-row'>
            <span class='row-label'>{t('时间轴')}</span>
            <span class='row-duration'>{data.durationTotalText}</span>
            <div class='row-track'>
              {data.rows.map(row => (
                <span
                  key={row.key}
                  style={{ left: `${row.startPercent}%`, width: `${row.durationPercent}%`, backgroundColor: row.color }}
                  class='row-block'
                />
              ))}
            </div>
          </div>
          {data.ttfbBreakdown ? (
            <div class='waterfall-ttfb-breakdown'>
              {`${t('TTFB 分解（RUM 协议）')} · ${t('子项合计')} ${data.ttfbBreakdown.itemsTotalText} · ${t('与 TTFB 相差')} ${data.ttfbBreakdown.diffText}`}
            </div>
          ) : null}
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
            index === 0 && data.mergedNames?.length ? (
              <div
                key='merged-tip'
                class='waterfall-merged-tip'
              >
                <span class='tip-line' />
                <span class='tip-text'>{`${t('连接复用')}：`}</span>
                <span class='tip-names'>
                  {data.mergedNames.map((name, index) => [
                    index > 0 && <span key={`、${name}`}>、</span>,
                    <span
                      key={`name_${name}`}
                      class='tip-name'
                    >
                      {name}
                    </span>,
                  ])}
                </span>
                <span class='tip-line' />
              </div>
            ) : null,
          ])}
        </div>
      );
    };

    return () => {
      const { data } = props;
      if (!data?.rows?.length) return null;
      return (
        <div
          class={[
            'waterfall-chart',
            { 'complex-behavior': data.behavior === 'complex', 'has-marker': data.markers.length > 0 },
          ]}
        >
          {data.behavior === 'complex' ? (
            <div class='complex-behavior-wrap'>
              <div class='complex-behavior-header'>
                <div class='waterfall-chart-title'>{t('页面加载时序')}</div>
                <div class='waterfall-chart-status'>
                  {Object.entries(RATING_META).map(([key, meta]) => (
                    <div
                      key={key}
                      style={{ '--status-color': meta.color }}
                      class='waterfall-chart-status-item'
                    >
                      {meta.alias}
                    </div>
                  ))}
                </div>
              </div>
              {renderWaterfall()}
            </div>
          ) : (
            renderWaterfall()
          )}
        </div>
      );
    };
  },
});
