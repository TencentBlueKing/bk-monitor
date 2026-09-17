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
import { computed, defineComponent, shallowRef, useTemplateRef } from 'vue';
import type { PropType } from 'vue';

import { useResizeObserver } from '@vueuse/core';
import { useI18n } from 'vue-i18n';

import type { IRumWaterfallMarkerVM, IRumWaterfallRowVM, IRumWaterfallVM } from '../../typings';

/** 标记文案行高，多根竖线靠得很近时按该高度错行摆放 */
const MARKER_LABEL_HEIGHT = 20;
/** 文案与竖线之间的水平间距 */
const MARKER_LABEL_GAP = 6;

/** 健康度图例：良好 / 待改善 / 差三档，颜色与各阶段色块的阈值评级对应 */
const healthList = [
  { label: window.i18n.t('良好'), color: '#21A380' },
  { label: window.i18n.t('待改善'), color: '#F59500' },
  { label: window.i18n.t('差'), color: '#EA3636' },
];

/** 粗估文案宽度（中文 12px、其余字符 7px），够用于判断相邻标记的文案是否互相压盖 */
function estimateLabelWidth(text: string) {
  return Array.from(text).reduce((width, char) => width + (/[\u4e00-\u9fa5]/.test(char) ? 12 : 7), 0);
}

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
    const markersElRef = useTemplateRef<HTMLElement>('markersEl');
    const trackWidth = shallowRef(0);
    useResizeObserver(markersElRef, entries => {
      trackWidth.value = entries[0]?.contentRect?.width || 0;
    });
    /**
     * 标记排版：竖线贯穿整张瀑布图，文案排在竖线右侧顶部；
     * 竖线横坐标由左到右贪心分行，放不下就换到下一行，避免相邻文案重叠。
     */
    const markerLayout = computed(() => {
      const width = trackWidth.value;
      /** 每一行已被占用的最右坐标 */
      const lineEnds: number[] = [];
      const markers = [...(props.data?.markers || [])]
        .sort((a, b) => a.percent - b.percent)
        .map((marker: IRumWaterfallMarkerVM) => {
          let line = 0;
          let labelLeft = 0;
          if (width) {
            labelLeft = (marker.percent / 100) * width + MARKER_LABEL_GAP;
            while (line < lineEnds.length && labelLeft < lineEnds[line]) line += 1;
            lineEnds[line] =
              labelLeft + estimateLabelWidth(`${marker.label} ${marker.durationText}`) + MARKER_LABEL_GAP;
          }
          return { ...marker, labelTop: line * MARKER_LABEL_HEIGHT };
        });
      return { markers, topSpace: markers.length ? Math.max(lineEnds.length, 1) * MARKER_LABEL_HEIGHT : 0 };
    });
    return () => {
      const { data } = props;
      if (!data?.rows?.length) return null;
      /** 时间轴与阶段行共用同一份色块渲染逻辑，保证两侧颜色与位置一一对应 */
      const renderRowBlock = (row: IRumWaterfallRowVM) => (
        <span
          key={row.key}
          style={{ left: `${row.startPercent}%`, width: `${row.durationPercent}%`, backgroundColor: row.color }}
          class='row-block'
        />
      );
      const { markers, topSpace } = markerLayout.value;

      /** 瀑布图主体：汇总时间轴 + TTFB 分解说明 + 阶段行 + 标记层 */
      const rumWaterfallWrap = () => (
        <div
          style={{ paddingTop: `${topSpace ? topSpace : props.spanType === 'view' ? 16 : 0}px` }}
          class='rum-waterfall'
        >
          <div class='waterfall-row waterfall-axis-row'>
            <span class='row-label'>{t('时间轴')}</span>
            <span class='row-duration' />
            <div class='row-track'>{data.rows.map(row => renderRowBlock(row))}</div>
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
              <div class='row-track'>{renderRowBlock(row)}</div>
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
          {markers.length ? (
            <div
              ref={'markersEl'}
              class='waterfall-markers'
            >
              {markers.map(marker => (
                <span
                  key={`line_${marker.key}`}
                  style={{ left: `${marker.percent}%` }}
                  class='marker-line'
                />
              ))}
              {markers.map(marker => (
                <span
                  key={marker.key}
                  style={{ left: `${marker.percent}%`, top: `${marker.labelTop}px` }}
                  class='marker-label'
                >
                  <span class='marker-name'>{marker.label}</span>
                  <span class='marker-value'>{marker.durationText}</span>
                </span>
              ))}
            </div>
          ) : null}
        </div>
      );

      /** view 类 span 额外包一层「页面加载时序」标题与健康度图例，其余类型直接渲染主体 */
      const rumWaterfallRender = () => {
        if (props.spanType === 'view') {
          return (
            <div class='span-type-view-rum-waterfall'>
              <div class='span-type-view-rum-waterfall-head'>
                <span class='left-title'>{t('页面加载时序')}</span>
                <span class='right-tips'>
                  {healthList.map(item => (
                    <>
                      <span
                        style={`background: ${item.color}`}
                        class='point'
                      />
                      <span
                        style={`color: ${item.color}`}
                        class='health-label'
                      >
                        {item.label}
                      </span>
                    </>
                  ))}
                </span>
              </div>
              {rumWaterfallWrap()}
            </div>
          );
        }
        return rumWaterfallWrap();
      };
      return rumWaterfallRender();
    };
  },
});
