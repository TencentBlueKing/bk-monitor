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

import { type PropType, computed, defineComponent, shallowRef } from 'vue';

import { Exception } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import StatisticCards from '../../llm-observation/components/statistic-cards';
import ExecutionToolbar from './components/execution-toolbar';
import LlmSkeleton from './components/llm-skeleton';
import TraceBlock from './components/trace-block';
import TrendChart from './components/trend-chart';

import type { UseLlmObservationReturn } from './hooks/use-llm-observation';
import type { LlmTrendSeriesKey, LlmTrendVisible } from './utils/trend-buckets';
import type { LlmSpanRowView } from './utils/typings';

import './index.scss';

/** Trace 详情侧栏「LLM 观测」面板：统计概览、Agent 执行线与 Span 详情入口 */
export default defineComponent({
  name: 'TraceLlmObservation',
  props: {
    observation: {
      type: Object as PropType<UseLlmObservationReturn>,
      required: true,
    },
  },
  emits: {
    /** 跳转 Trace 详情已有 Span 侧栏 */
    showSpanDetail: (_span: LlmSpanRowView) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();

    /** 趋势图序列可见性（图例「只看」） */
    const trendVisible = shallowRef<LlmTrendVisible>({ duration: true, token: true });

    /** 当前切换到的命中 spanId，供当前行醒目标记 */
    const activeSearchSpanId = computed(
      () => props.observation.searchMatchSpanIds.value[props.observation.searchActiveIndex.value] || ''
    );

    const handleViewDetail = (span: LlmSpanRowView) => {
      emit('showSpanDetail', span);
    };

    /** 矩阵工具叶子点击：把工具名填入执行线搜索框，交给页内搜索定位同名工具行 */
    const handleToolSearch = (toolName: string) => {
      if (!toolName) return;
      props.observation.handleKeywordChange(toolName);
    };

    /** 图例点击：仅自己可见时恢复全部，否则只看该项 */
    const handleTrendLegendToggle = (key: LlmTrendSeriesKey) => {
      const current = trendVisible.value;
      const hasOtherVisible = (Object.keys(current) as LlmTrendSeriesKey[]).some(
        item => item !== key && current[item]
      );
      trendVisible.value = hasOtherVisible
        ? { duration: key === 'duration', token: key === 'token' }
        : { duration: true, token: true };
    };

    return {
      t,
      ...props.observation,
      trendVisible,
      activeSearchSpanId,
      handleTrendLegendToggle,
      handleViewDetail,
      handleToolSearch,
    };
  },
  render() {
    return (
      <div class='trace-llm-observation'>
        {/* listFlows 进行中 */}
        {this.loading ? (
          <LlmSkeleton />
        ) : this.traceBlocks.length ? (
          /* 有 Trace 块：统计卡 + 工具栏 + 可折叠 Trace 列表 */
          <div class='trace-llm-observation-main'>
            <StatisticCards
              cards={this.stats}
              matrixLoading={this.ioLoading}
              nodes={this.tokenMatrixNodes}
              onLocate-tool={this.handleToolSearch}
            />
            <div class='trace-llm-observation-timeline'>
              <ExecutionToolbar
                conversationId={this.conversationId}
                counts={this.kindCounts}
                filter={this.filter}
                keyword={this.keyword}
                searchActiveIndex={this.searchActiveIndex}
                searchMatchCount={this.searchMatchCount}
                showSession={this.showSession}
                trendVisible={this.trendVisible}
                onSearch-next={() => this.handleSearchStep(1)}
                onSearch-prev={() => this.handleSearchStep(-1)}
                onUpdate:filter={this.handleFilterChange}
                onUpdate:keyword={this.handleKeywordChange}
                onUpdate:showSession={this.handleSessionChange}
                onToggle-trend={this.handleTrendLegendToggle}
              />
              {/* 耗时、总 Token 趋势图：按已点开的 Trace 累加合并，flow 懒加载到达后逐渐并入，排除 Agent Span */}
              <TrendChart
                flow={this.trendFlow}
                filter={this.filter}
                flowLoading={this.trendLoading}
                range={this.trendRange}
                visible={this.trendVisible}
                onLocate={this.locateMergedSpan}
                onSelect={this.handleTrendSelect}
                onView-detail={this.handleViewDetail}
              />
              <div class='trace-llm-observation-list'>
                {this.traceBlocks.map(block => (
                  <TraceBlock
                    key={block.traceId}
                    activeSearchSpanId={this.activeSearchSpanId}
                    expanded={this.expandedTraceIds.has(block.traceId)}
                    expandedSpanIds={this.expandedSpanIds}
                    flow={block.flow}
                    flowLoading={block.flowLoading}
                    highlightedSpanId={this.highlightedSpanId}
                    rows={block.rows}
                    trace={block}
                    onLocate-span={spanId => this.locateSpan(block.traceId, spanId)}
                    onToggle-span={this.toggleSpan}
                    onToggle-trace={this.toggleTrace}
                    onView-detail={this.handleViewDetail}
                  />
                ))}
              </div>
            </div>
          </div>
        ) : (
          /* 接口成功但 traces 为空，或参数不完整导致未发起请求 */
          <Exception
            class='trace-llm-observation-empty'
            scene='part'
            title={this.t('暂无 LLM 观测数据')}
            type='empty'
          />
        )}
      </div>
    );
  },
});
