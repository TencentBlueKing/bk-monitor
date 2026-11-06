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
import { type PropType, computed, defineComponent, nextTick, provide, shallowRef, watch } from 'vue';

import { useI18n } from 'vue-i18n';

import ErrorAlert from './components/error-alert';
import InputTab from './components/input-tab';
import OutputTab from './components/output-tab';
import ToolDescBar from './components/tool-desc-bar';
import ToolPanel from './components/tool-panel';
import { formatSecondCount, formatTokenCount, pickNumber, pickOptionalNumber, pickString } from './utils/helpers';
import { formatAgentLabel, parseAgentObservation } from './utils/parse-agent';
import { countInputObservation, parseInputObservation } from './utils/parse-input';
import { countOutputObservation, parseOutputObservation } from './utils/parse-output';
import { collectObservationHits, LLM_OBSERVATION_SEARCH_KEY } from './utils/search';

import type { SpanLlmDetail } from '../../../components/trace-view/typings';

import './index.scss';

/** 输入 / 输出页签 */
type IoTabName = 'input' | 'output';

/** Token / 模型 / 耗时统计卡片 */
type LlmStatCard = {
  extra?: string;
  key: string;
  label: string;
  theme?: 'success';
  unit?: string;
  value: number | string;
};

/**
 * LLM 观测页：按 Span 语义层级展示模型/Agent 输入输出，或 Tool 调用详情
 */
export default defineComponent({
  name: 'LlmObservation',
  props: {
    /** Span 详情接口补充的标准 LLM Span */
    llmDetail: {
      type: Object as PropType<null | SpanLlmDetail>,
      default: null,
    },
    /** 页内搜索词，输入 / 输出两侧一起匹配 */
    searchKeyword: {
      type: String,
      default: '',
    },
    /** 当前命中序号，由搜索框箭头 / Enter 驱动 */
    searchActiveIndex: {
      type: Number,
      default: 0,
    },
  },
  emits: {
    /** 回传命中总数，给搜索框展示 n / total 或「无结果」 */
    matchCount: (_count: number) => true,
    /** 手动切输入 / 输出时，跳到该页签首个命中，搜索框序号同步更新 */
    searchActiveIndex: (_index: number) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    /** 当前激活的输入 / 输出页签 */
    const activeIoTab = shallowRef<IoTabName>('input');
    const rootRef = shallowRef<HTMLElement>();

    const attributes = computed(() => props.llmDetail?.attributes ?? {});

    /** 工具走独立面板，Agent / 模型走输入输出页 */
    const isToolSpan = computed(() => props.llmDetail?.span_type === 'TOOL');
    const isAgentSpan = computed(() => props.llmDetail?.span_type === 'AGENT');
    const isModelSpan = computed(() => props.llmDetail?.span_type === 'LLM');
    const inputObservation = computed(() => parseInputObservation(attributes.value));
    const outputObservation = computed(() => parseOutputObservation(attributes.value));
    const agentObservation = computed(() => parseAgentObservation(attributes.value));
    const agentLabel = computed(() => formatAgentLabel(agentObservation.value.name, agentObservation.value.version));
    /** 名称、版本、描述都空时不占位 */
    const showAgentBar = computed(
      () =>
        isAgentSpan.value &&
        Boolean(agentObservation.value.name || agentObservation.value.version || agentObservation.value.description)
    );

    /** Tool Span 只扫工具面板；Agent 先扫名称条，再输入后输出 */
    const hits = computed(() =>
      collectObservationHits(props.searchKeyword, attributes.value, isToolSpan.value, isAgentSpan.value)
    );
    const activeHit = computed(() => hits.value[props.searchActiveIndex] ?? null);

    provide(LLM_OBSERVATION_SEARCH_KEY, {
      keyword: computed(() => props.searchKeyword),
      activeIndex: computed(() => props.searchActiveIndex),
      hits,
      activeHit,
    });

    watch(
      () => props.llmDetail,
      () => {
        activeIoTab.value = 'input';
      }
    );

    watch(
      hits,
      list => {
        emit('matchCount', list.length);
      },
      { immediate: true }
    );

    /** 切到命中所在 IO 页签，等折叠层展开挂载后再滚到当前高亮 */
    const locateCurrentHit = async (keepTab = false) => {
      const hit = activeHit.value;
      if (!hit) return;
      if (!keepTab && (hit.tab === 'input' || hit.tab === 'output')) {
        activeIoTab.value = hit.tab;
      }
      await nextTick();
      requestAnimationFrame(() => {
        const el = rootRef.value?.querySelector('[data-llm-search-hit="current"]') as HTMLElement | undefined;
        el?.scrollIntoView({ block: 'center', inline: 'nearest' });
      });
    };

    watch(
      () => [props.searchKeyword, props.searchActiveIndex, activeHit.value?.blockId],
      (curr, prev) => {
        const keywordChanged = curr[0] !== prev?.[0];
        // 换词只定位当前页签内的命中，避免手动停在输出时又被拉回输入
        if (keywordChanged) {
          if (isToolSpan.value) {
            locateCurrentHit(true);
            return;
          }
          const firstInTab = hits.value.find(
            hit => hit.tab === activeIoTab.value || (activeIoTab.value === 'input' && hit.tab === 'agent')
          );
          if (!firstInTab) {
            const firstAgent = hits.value.find(hit => hit.tab === 'agent');
            if (!firstAgent) return;
            if (firstAgent.index !== props.searchActiveIndex) {
              emit('searchActiveIndex', firstAgent.index);
              return;
            }
            locateCurrentHit(true);
            return;
          }
          if (firstInTab.index !== props.searchActiveIndex) {
            emit('searchActiveIndex', firstInTab.index);
            return;
          }
          locateCurrentHit(true);
          return;
        }
        locateCurrentHit();
      }
    );

    /** 手动切页签：跳到该侧第一条命中，驱动 n / total 与折叠展开 */
    const handleIoTabClick = (tab: IoTabName) => {
      const alreadyOnTab = activeIoTab.value === tab;
      activeIoTab.value = tab;
      const firstHit = hits.value.find(hit => hit.tab === tab);
      if (!firstHit) return;
      // 已在该页签且当前命中也在这一侧：只重新定位，不把序号打回第一条
      if (alreadyOnTab && activeHit.value?.tab === tab) {
        locateCurrentHit();
        return;
      }
      if (firstHit.index === props.searchActiveIndex) {
        locateCurrentHit();
        return;
      }
      emit('searchActiveIndex', firstHit.index);
    };

    /** Token / 模型 / 耗时统计卡片；工具类型不展示，「模型 & 厂商」「首 Token 耗时」仅模型场景 */
    const stats = computed<LlmStatCard[]>(() => {
      if (isToolSpan.value) return [];

      const attrs = attributes.value;
      const inputTokens = pickNumber(attrs, ['gen_ai.usage.input_tokens', 'gen_ai.usage.prompt_tokens']);
      const outputTokens = pickNumber(attrs, ['gen_ai.usage.output_tokens', 'gen_ai.usage.completion_tokens']);
      const totalTokens = pickNumber(attrs, ['gen_ai.usage.total_tokens']) || inputTokens + outputTokens;
      const cacheReadTokens = pickNumber(attrs, ['gen_ai.usage.cache_read.input_tokens']);
      const cacheHitRate = inputTokens > 0 ? (cacheReadTokens / inputTokens) * 100 : 0;
      const firstChunk = pickOptionalNumber(attrs, ['gen_ai.response.time_to_first_chunk']);
      const modelCards: LlmStatCard[] = isModelSpan.value
        ? [
            {
              extra: pickString(attrs, ['gen_ai.provider.name']),
              key: 'model',
              label: t('模型 & 厂商'),
              value: pickString(attrs, ['gen_ai.request.model']) || '--',
            },
          ]
        : [];
      const firstTokenCards: LlmStatCard[] = isModelSpan.value
        ? [
            {
              key: 'firstToken',
              label: t('首 Token 耗时'),
              unit: firstChunk === undefined ? undefined : 's',
              value: firstChunk === undefined ? '--' : firstChunk,
            },
          ]
        : [];

      return [
        ...modelCards,
        ...firstTokenCards,
        { key: 'total', label: t('总 Tokens'), value: totalTokens, theme: 'success' },
        {
          extra: cacheHitRate > 0 ? t('缓存命中率：{0}%', [Number(cacheHitRate.toFixed(2))]) : undefined,
          key: 'input',
          label: t('输入 Tokens'),
          value: inputTokens,
        },
        { key: 'output', label: t('输出 Tokens'), value: outputTokens },
        {
          key: 'cacheRead',
          label: t('缓存读取'),
          value: cacheReadTokens,
        },
        {
          key: 'cacheWrite',
          label: t('缓存写入'),
          value: pickNumber(attrs, ['gen_ai.usage.cache_write.input_tokens']),
        },
      ];
    });

    const inputCount = computed(() => countInputObservation(inputObservation.value));
    const outputCount = computed(() => countOutputObservation(outputObservation.value));

    /** code=2 才展示错误条；message 空时占位 -- */
    const errorMessage = computed(() => {
      const status = props.llmDetail?.status;
      if (Number(status?.code) !== 2) return '';
      const message = typeof status?.message === 'string' ? status.message.trim() : '';
      return message || '--';
    });

    const ioTabs = computed(() => [
      {
        name: 'input' as const,
        label: t('输入 ({0})', [inputCount.value]),
        icon: 'icon-mc-ai-input',
      },
      {
        name: 'output' as const,
        label: t('输出 ({0})', [outputCount.value]),
        icon: 'icon-mc-ai-output',
      },
    ]);

    return () => (
      <div
        ref={rootRef}
        class='llm-observation'
      >
        <div class='llm-observation-main'>
          {showAgentBar.value ? (
            <ToolDescBar
              class='llm-observation-agent-bar'
              descBlockId='agent:desc'
              description={agentObservation.value.description}
              name={agentLabel.value}
              nameBlockId='agent:name'
              variant='agent'
            />
          ) : null}
          {errorMessage.value ? <ErrorAlert message={errorMessage.value} /> : null}
          {stats.value.length > 0 && (
            <div class='llm-observation-stats'>
              {stats.value.map(item => {
                const displayValue =
                  typeof item.value === 'string'
                    ? item.value
                    : item.unit
                      ? formatSecondCount(item.value)
                      : formatTokenCount(item.value);

                return (
                  <div
                    key={item.key}
                    class='llm-observation-stat-card'
                  >
                    <div class='llm-observation-stat-head'>
                      <span class='llm-observation-stat-label'>{item.label}</span>
                      {item.extra ? (
                        <span
                          class='llm-observation-stat-extra'
                          v-overflow-tips
                        >
                          {item.extra}
                        </span>
                      ) : null}
                    </div>
                    <div class='llm-observation-stat-value-row'>
                      <span
                        class={['llm-observation-stat-value', { 'is-success': item.theme === 'success' }]}
                        v-overflow-tips
                      >
                        {displayValue}
                      </span>
                      {item.unit && typeof item.value === 'number' ? (
                        <span class='llm-observation-stat-unit'>{item.unit}</span>
                      ) : null}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
          {isToolSpan.value ? (
            <ToolPanel attributes={attributes.value} />
          ) : (
            <div class='llm-observation-io'>
              <div class='llm-observation-toolbar'>
                <div class='llm-observation-io-tabs'>
                  {ioTabs.value.map(tab => (
                    <div
                      key={tab.name}
                      class={['llm-observation-io-tab', { 'is-active': activeIoTab.value === tab.name }]}
                      onClick={() => handleIoTabClick(tab.name)}
                    >
                      <i class={['icon-monitor', tab.icon, 'llm-observation-io-tab-icon']} />
                      <span>{tab.label}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div class='llm-observation-io-content'>
                <div class={['llm-observation-io-pane', { 'is-hidden': activeIoTab.value !== 'input' }]}>
                  <InputTab attributes={attributes.value} />
                </div>
                <div class={['llm-observation-io-pane', { 'is-hidden': activeIoTab.value !== 'output' }]}>
                  <OutputTab attributes={attributes.value} />
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  },
});
