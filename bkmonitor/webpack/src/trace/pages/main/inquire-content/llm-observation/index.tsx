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

import { type PropType, defineComponent } from 'vue';

import { Exception } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import ExecutionToolbar from './components/execution-toolbar';
import LlmSkeleton from './components/llm-skeleton';
import StatisticCards from './components/statistic-cards';
import TraceBlock from './components/trace-block';
import type { UseLlmObservationReturn } from './hooks/use-llm-observation';

import './index.scss';

/** Trace 详情侧栏「LLM 观测」面板：统计概览、Agent 执行线与 Span 展开详情 */
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
    showSpanDetail: (_spanId: string) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const handleViewDetail = (spanId: string) => {
      emit('showSpanDetail', spanId);
    };

    return {
      t,
      ...props.observation,
      handleViewDetail,
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
            <StatisticCards cards={this.stats} />
            <div class='trace-llm-observation-timeline'>
              <ExecutionToolbar
                conversationId={this.conversationId}
                counts={this.kindCounts}
                filter={this.filter}
                keyword={this.keyword}
                showSession={this.showSession}
                onUpdate:filter={this.handleFilterChange}
                onUpdate:keyword={this.handleKeywordChange}
                onUpdate:showSession={this.handleSessionChange}
              />
              <div class='trace-llm-observation-list'>
                {this.traceBlocks.map(block => (
                  <TraceBlock
                    key={block.traceId}
                    detailExpandedSpanIds={this.detailExpandedSpanIds}
                    expanded={this.expandedTraceIds.has(block.traceId)}
                    expandedSpanIds={this.expandedSpanIds}
                    flowLoading={block.flowLoading}
                    rows={block.rows}
                    trace={block}
                    onToggle-detail={this.toggleDetail}
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
