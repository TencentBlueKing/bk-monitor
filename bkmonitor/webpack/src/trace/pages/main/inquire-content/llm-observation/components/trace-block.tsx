/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

import { type PropType, defineComponent, onBeforeUnmount, onMounted, shallowRef } from 'vue';

import { Popover } from 'bkui-vue';
import dayjs from 'dayjs';
import { useI18n } from 'vue-i18n';

import { formatDuration } from '../../../../../components/trace-view/utils/date';
import { findSpanRowView } from '../utils/duration-stats';
import { formatCompactToken } from '../utils/transform';
import DurationStatsPanel from './duration-stats-panel';
import { LlmSpanTableSkeleton } from './llm-skeleton';
import SpanRow from './span-row';
import TokenStatsPanel from './token-stats-panel';
import TraceIoPopover from './trace-io-popover';

import type { LlmFlowSpan, LlmSpanRowView, LlmTraceView } from '../utils/typings';

import './trace-block.scss';

/** 单条 Trace 折叠块：头部摘要 + 悬停 I/O Popover + Span 表格（懒加载 flow 时展示骨架屏） */
export default defineComponent({
  name: 'LlmTraceBlock',
  props: {
    expanded: {
      type: Boolean,
      default: false,
    },
    expandedSpanIds: {
      type: Object as PropType<Set<string>>,
      default: () => new Set<string>(),
    },
    flow: {
      type: Array as PropType<LlmFlowSpan[]>,
      default: () => [],
    },
    flowLoading: {
      type: Boolean,
      default: false,
    },
    highlightedSpanId: {
      type: String,
      default: '',
    },
    rows: {
      type: Array as PropType<LlmSpanRowView[]>,
      default: () => [],
    },
    trace: {
      type: Object as PropType<LlmTraceView>,
      required: true,
    },
  },
  emits: {
    'locate-span': (_spanId: string) => true,
    'toggle-span': (_spanId: string) => true,
    'toggle-trace': (_traceId: string) => true,
    'view-detail': (_span: LlmSpanRowView) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const durationPanelShow = shallowRef(false);
    const tokenPanelShow = shallowRef(false);
    const durationPopoverRef = shallowRef<{ hide?: () => void }>();
    const tokenPopoverRef = shallowRef<{ hide?: () => void }>();
    // 触发列元素，用于换算面板可用的最大高度
    let durationTriggerEl: HTMLElement | undefined;
    let tokenTriggerEl: HTMLElement | undefined;
    // 弹出面板最大高度：由触发列底部到可视窗口底部动态计算
    const panelMaxHeight = shallowRef<number | undefined>();

    const updatePanelMaxHeight = (trigger?: HTMLElement) => {
      const el = trigger ?? durationTriggerEl ?? tokenTriggerEl;
      if (!el) return;
      const { bottom } = el.getBoundingClientRect();
      // 预留 popover 与触发元素的间距，以及到底部 Viewport 的安全边距
      panelMaxHeight.value = Math.max(200, window.innerHeight - bottom - 24);
    };

    const handleViewportResize = () => {
      if (!durationPanelShow.value && !tokenPanelShow.value) return;
      updatePanelMaxHeight(durationPanelShow.value ? durationTriggerEl : tokenTriggerEl);
    };

    const closeDurationPanel = () => {
      durationPanelShow.value = false;
      durationPopoverRef.value?.hide?.();
    };

    const closeTokenPanel = () => {
      tokenPanelShow.value = false;
      tokenPopoverRef.value?.hide?.();
    };

    const closeStatsPanels = () => {
      closeDurationPanel();
      closeTokenPanel();
    };

    onMounted(() => {
      window.addEventListener('resize', handleViewportResize);
    });

    onBeforeUnmount(() => {
      window.removeEventListener('resize', handleViewportResize);
    });

    const handleLocateSpan = (spanId: string) => {
      closeStatsPanels();
      emit('locate-span', spanId);
    };

    const handleStatsViewDetail = (spanId: string) => {
      const row = findSpanRowView(props.flow, spanId);
      closeStatsPanels();
      if (row) emit('view-detail', row);
    };

    return () => {
      const { trace } = props;
      const title = trace.title ? `“${trace.title}”` : trace.traceId;

      return (
        <div class={['llm-trace-block', { 'is-current': trace.isCurrent, 'is-collapsed': !props.expanded }]}>
          <div
            class='llm-trace-header'
            onClick={() => emit('toggle-trace', trace.traceId)}
          >
            <div class='llm-trace-header-main'>
              <span class={['llm-trace-bar', { 'is-current': trace.isCurrent }]} />
              <i class={['icon-monitor icon-mc-arrow-down llm-trace-expand', { 'is-collapsed': !props.expanded }]} />
              {/* startTime 为微秒时间戳，与 trace-view 其它模块一致 */}
              <span class='llm-trace-time'>{dayjs(trace.startTime / 1000).format('YYYY-MM-DD HH:mm:ss')}</span>
              <Popover
                width={600}
                extCls='llm-trace-io-popover'
                v-slots={{
                  default: () => <span class='llm-trace-title'>{title}</span>,
                  content: () => <TraceIoPopover trace={trace} />,
                }}
                boundary='body'
                padding={16}
                placement='top'
                popoverDelay={[400, 200]}
                theme='light'
              />
            </div>
            <div class='llm-trace-header-meta'>
              {trace.flowLoaded ? (
                <span class='llm-trace-meta is-span'>
                  <span class='is-label'>Span</span>
                  <span class='is-value'>{trace.spanCount}</span>
                </span>
              ) : null}
              {trace.flowLoaded && trace.errorCount > 0 ? (
                <span class='llm-trace-meta is-error'>
                  <i class='icon-monitor icon-yichang' />
                  {trace.errorCount}
                </span>
              ) : null}
              <span class='llm-trace-meta is-duration'>
                <i class='icon-monitor icon-jishiqi1' />
                {formatDuration(trace.elapsedTime)}
              </span>
              <span class='llm-trace-meta is-token'>
                <span class='is-label'>Tok</span>
                <i class='icon-monitor icon-mc-ai-input' />
                <span class='is-value'>{formatCompactToken(trace.inputTokens)}</span>
                <span class='llm-trace-meta-divider' />
                <i class='icon-monitor icon-mc-ai-output is-output' />
                <span class='is-output'>{formatCompactToken(trace.outputTokens)}</span>
              </span>
              <span class={['llm-trace-badge', { 'is-current': trace.isCurrent }]}>
                <i class={`icon-monitor ${trace.isCurrent ? 'icon-dingwei1' : 'icon-mc-position-tips'}`} />
                {trace.isCurrent ? t('当前 Trace') : t('关联 Trace')}
              </span>
            </div>
          </div>
          {props.expanded ? (
            <div class='llm-trace-table'>
              <div class='llm-trace-table-head'>
                <span class='is-time'>{t('时间')}</span>
                <span class='is-tree'>{t('关系')}</span>
                <span class='is-span'>Span</span>
                <span class='is-io'>{t('输入 → 输出')}</span>
                <span class={['is-duration', { 'is-active': durationPanelShow.value }]}>
                  <Popover
                    ref={durationPopoverRef}
                    extCls='llm-duration-stats-popover'
                    v-slots={{
                      default: () => (
                        <span
                          ref={(el: unknown) => {
                            durationTriggerEl = el as HTMLElement;
                          }}
                          class='llm-duration-stats-trigger'
                          v-bk-tooltips={{ content: t('统计分析'), placement: 'top' }}
                          onClick={() => updatePanelMaxHeight(durationTriggerEl)}
                        >
                          {t('耗时')}
                          <i class='icon-monitor icon-mc-statistical' />
                        </span>
                      ),
                      content: () => (
                        <DurationStatsPanel
                          flow={props.flow}
                          flowLoaded={trace.flowLoaded}
                          flowLoading={props.flowLoading}
                          maxHeight={panelMaxHeight.value}
                          onLocate={handleLocateSpan}
                          onView-detail={handleStatsViewDetail}
                        />
                      ),
                    }}
                    boundary='body'
                    clickContentAutoHide={false}
                    padding={0}
                    placement='bottom-start'
                    theme='light'
                    trigger='click'
                    width={680}
                    onAfter-hidden={() => {
                      durationPanelShow.value = false;
                    }}
                    onAfter-show={() => {
                      closeTokenPanel();
                      durationPanelShow.value = true;
                      updatePanelMaxHeight(durationTriggerEl);
                    }}
                  />
                </span>
                <span class={['is-token', { 'is-active': tokenPanelShow.value }]}>
                  <Popover
                    ref={tokenPopoverRef}
                    extCls='llm-token-stats-popover'
                    v-slots={{
                      default: () => (
                        <span
                          ref={(el: unknown) => {
                            tokenTriggerEl = el as HTMLElement;
                          }}
                          class='llm-token-stats-trigger'
                          v-bk-tooltips={{ content: t('统计分析'), placement: 'top' }}
                          onClick={() => updatePanelMaxHeight(tokenTriggerEl)}
                        >
                          Token
                          <i class='icon-monitor icon-mc-statistical' />
                        </span>
                      ),
                      content: () => (
                        <TokenStatsPanel
                          flow={props.flow}
                          flowLoaded={trace.flowLoaded}
                          flowLoading={props.flowLoading}
                          maxHeight={panelMaxHeight.value}
                          onLocate={handleLocateSpan}
                          onView-detail={handleStatsViewDetail}
                        />
                      ),
                    }}
                    boundary='body'
                    clickContentAutoHide={false}
                    padding={0}
                    placement='bottom-start'
                    theme='light'
                    trigger='click'
                    width={680}
                    onAfter-hidden={() => {
                      tokenPanelShow.value = false;
                    }}
                    onAfter-show={() => {
                      closeDurationPanel();
                      tokenPanelShow.value = true;
                      updatePanelMaxHeight(tokenTriggerEl);
                    }}
                  />
                </span>
                <span class='is-action' />
              </div>
              <div class='llm-trace-table-body'>
                {props.flowLoading ? (
                  <LlmSpanTableSkeleton />
                ) : (
                  props.rows.map(row => (
                    <SpanRow
                      key={row.spanId}
                      expanded={props.expandedSpanIds.has(row.spanId)}
                      highlighted={props.highlightedSpanId === row.spanId}
                      row={row}
                      onToggle-expand={spanId => emit('toggle-span', spanId)}
                      onView-detail={span => emit('view-detail', span)}
                    />
                  ))
                )}
              </div>
            </div>
          ) : null}
        </div>
      );
    };
  },
});
