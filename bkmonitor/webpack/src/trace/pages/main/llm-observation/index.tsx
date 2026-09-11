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
import { type PropType, computed, defineComponent, onBeforeUnmount, shallowRef, watch } from 'vue';

import { Loading } from 'bkui-vue';
import { CancelToken } from 'monitor-api/cancel';
import { listSpans } from 'monitor-api/modules/llm_web';
import { useI18n } from 'vue-i18n';

import InputTab from './components/input-tab';
import OutputTab from './components/output-tab';
import ToolPanel from './components/tool-panel';
import { formatTokenCount, getObservationKind, getSpanAttributes, pickNumber } from './utils/helpers';
import { countInputObservation, parseInputObservation } from './utils/parse-input';
import { countOutputObservation, parseOutputObservation } from './utils/parse-output';

import type { ILlmSpan, ILlmSpanListData } from './utils/typings';

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
 * LLM 观测页：按 operation.name 展示模型/Agent 输入输出，或 Tool 调用详情
 */
export default defineComponent({
  name: 'LlmObservation',
  props: {
    /** APM 应用名 */
    appName: {
      type: String,
      default: '',
    },
    bkBizId: {
      type: Number,
      default: 0,
    },
    /** Span 详情侧栏已有的原始数据，接口未返回时作为兜底 attributes */
    originalData: {
      type: Object as PropType<null | Record<string, unknown>>,
      default: null,
    },
    spanId: {
      type: String,
      default: '',
    },
  },
  setup(props) {
    const { t } = useI18n();
    /** 当前激活的输入 / 输出页签 */
    const activeIoTab = shallowRef<IoTabName>('input');
    const loading = shallowRef(false);
    /** list_llm_spans 返回的当前 Span */
    const llmSpan = shallowRef<ILlmSpan | null>(null);
    let cancelRequest: (() => void) | null = null;
    /** 用于丢弃过期请求回包 */
    let requestSeq = 0;

    /** 优先使用接口 Span，否则回落到侧栏 originalData */
    const attributes = computed(() => {
      if (llmSpan.value) return getSpanAttributes(llmSpan.value);
      return getSpanAttributes(props.originalData);
    });

    /** 模型 / Agent 走输入输出页，Tool 走独立面板 */
    const observationKind = computed(() => getObservationKind(attributes.value));
    const inputObservation = computed(() => parseInputObservation(attributes.value));
    const outputObservation = computed(() => parseOutputObservation(attributes.value));

    /**
     * @description 拉取当前 Span 的 LLM 观测数据；切换查询条件时取消上一次请求
     */
    const fetchSpan = async () => {
      cancelRequest?.();
      cancelRequest = null;
      const seq = ++requestSeq;
      if (!props.appName || !props.spanId) {
        llmSpan.value = null;
        loading.value = false;
        return;
      }
      loading.value = true;
      const data: ILlmSpanListData = await listSpans(
        {
          app_name: props.appName,
          bk_biz_id: props.bkBizId,
          span_id: props.spanId,
        },
        {
          cancelToken: new CancelToken((cancel: () => void) => {
            cancelRequest = cancel;
          }),
        }
      ).catch(() => null);
      if (seq !== requestSeq) return;
      llmSpan.value = data?.spans?.[0] ?? null;
      loading.value = false;
      cancelRequest = null;
    };

    watch(
      () => [props.appName, props.bkBizId, props.spanId],
      () => {
        activeIoTab.value = 'input';
        fetchSpan();
      },
      { immediate: true }
    );

    onBeforeUnmount(() => {
      requestSeq += 1;
      cancelRequest?.();
      cancelRequest = null;
    });

    /** Token / 缓存统计卡片；Tool 页只展示缓存读写 */
    const stats = computed<LlmStatCard[]>(() => {
      const attrs = attributes.value;
      const inputTokens = pickNumber(attrs, ['gen_ai.usage.input_tokens', 'gen_ai.usage.prompt_tokens']);
      const outputTokens = pickNumber(attrs, ['gen_ai.usage.output_tokens', 'gen_ai.usage.completion_tokens']);
      const totalTokens = pickNumber(attrs, ['gen_ai.usage.total_tokens']) || inputTokens + outputTokens;
      const cacheRead = pickNumber(attrs, [
        'gen_ai.usage.cache_read.input_tokens',
        'gen_ai.usage.cache_read_input_tokens',
      ]);
      const cacheWrite = pickNumber(attrs, [
        'gen_ai.usage.cache_creation.input_tokens',
        'gen_ai.usage.cache_write.input_tokens',
        'gen_ai.usage.cache_creation_input_tokens',
      ]);

      const cacheCards: LlmStatCard[] = [
        { key: 'cacheRead', label: t('缓存读数'), value: cacheRead },
        { key: 'cacheWrite', label: t('缓存写入'), value: cacheWrite },
      ];
      if (observationKind.value === 'tool') return cacheCards;

      return [
        { key: 'input', label: t('输入 Tokens'), value: inputTokens },
        { key: 'output', label: t('输出 Tokens'), value: outputTokens },
        { key: 'total', label: t('总 Tokens'), value: totalTokens, theme: 'success' },
        ...cacheCards,
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
        <Loading
          class='llm-observation-loading'
          loading={loading.value}
        >
          <div class={['llm-observation-main', `is-${observationKind.value}`]}>
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
            {observationKind.value === 'tool' ? (
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
        </Loading>
      </div>
    );
  },
});
