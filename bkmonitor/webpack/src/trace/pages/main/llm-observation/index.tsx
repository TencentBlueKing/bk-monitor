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
import { type PropType, computed, defineComponent, shallowRef, watch } from 'vue';

import { useI18n } from 'vue-i18n';

import InputTab from './components/input-tab';
import OutputTab from './components/output-tab';
import ToolPanel from './components/tool-panel';
import { formatTokenCount, pickNumber } from './utils/helpers';
import { countInputObservation, parseInputObservation } from './utils/parse-input';
import { countOutputObservation, parseOutputObservation } from './utils/parse-output';

import type { SpanLlmDetail } from '../../../components/trace-view/typings';

import './index.scss';

/** 输入 / 输出页签 */
type IoTabName = 'input' | 'output';

/** Token 统计卡片 */
type LlmStatCard = {
  key: string;
  label: string;
  theme?: 'success';
  value: number;
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
  },
  setup(props) {
    const { t } = useI18n();
    /** 当前激活的输入 / 输出页签 */
    const activeIoTab = shallowRef<IoTabName>('input');

    const attributes = computed(() => props.llmDetail?.attributes ?? {});

    /** 工具走独立面板，Agent / 模型走输入输出页 */
    const isToolSpan = computed(() => props.llmDetail?.span_type === 'TOOL');
    const inputObservation = computed(() => parseInputObservation(attributes.value));
    const outputObservation = computed(() => parseOutputObservation(attributes.value));

    watch(
      () => props.llmDetail,
      () => {
        activeIoTab.value = 'input';
      }
    );

    /** Token / 缓存统计卡片；工具类型没有 Token 消耗 */
    const stats = computed<LlmStatCard[]>(() => {
      if (isToolSpan.value) return [];

      const attrs = attributes.value;
      const inputTokens = pickNumber(attrs, ['gen_ai.usage.input_tokens', 'gen_ai.usage.prompt_tokens']);
      const outputTokens = pickNumber(attrs, ['gen_ai.usage.output_tokens', 'gen_ai.usage.completion_tokens']);
      const totalTokens = pickNumber(attrs, ['gen_ai.usage.total_tokens']) || inputTokens + outputTokens;

      return [
        { key: 'input', label: t('输入 Tokens'), value: inputTokens },
        { key: 'output', label: t('输出 Tokens'), value: outputTokens },
        { key: 'total', label: t('总 Tokens'), value: totalTokens, theme: 'success' },
        {
          key: 'cacheRead',
          label: t('缓存读数'),
          value: pickNumber(attrs, ['gen_ai.usage.cache_read.input_tokens']),
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
      <div class='llm-observation'>
        <div class='llm-observation-main'>
          {stats.value.length > 0 && (
            <div class='llm-observation-stats'>
              {stats.value.map(item => (
                <div
                  key={item.key}
                  class='llm-observation-stat-card'
                >
                  <span class='llm-observation-stat-label'>{item.label}</span>
                  <span class={['llm-observation-stat-value', { 'is-success': item.theme === 'success' }]}>
                    {formatTokenCount(item.value)}
                  </span>
                </div>
              ))}
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
                      onClick={() => {
                        activeIoTab.value = tab.name;
                      }}
                    >
                      <i class={['icon-monitor', tab.icon, 'llm-observation-io-tab-icon']} />
                      <span>{tab.label}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div class='llm-observation-io-content'>
                {activeIoTab.value === 'input' && <InputTab attributes={attributes.value} />}
                {activeIoTab.value === 'output' && <OutputTab attributes={attributes.value} />}
              </div>
            </div>
          )}
        </div>
      </div>
    );
  },
});
