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
import { type PropType, computed, defineComponent, shallowRef, watch } from 'vue';

import { useI18n } from 'vue-i18n';

import { parseJsonValue, stringifyContent } from '../utils/helpers';
import { flattenKvPairs } from '../utils/parse-input';
import JsonCodeBlock from './json-code-block';

import type { LlmPlannedToolCall, LlmToolCallRecord } from '../utils/typings';

import './tool-call-list.scss';

/** 输入侧调用记录与输出侧规划调用共用卡片；规划调用没有 response。 */
type ToolCallItem = LlmPlannedToolCall | LlmToolCallRecord;

export default defineComponent({
  name: 'LlmToolCallList',
  props: {
    items: {
      type: Array as PropType<ToolCallItem[]>,
      default: () => [],
    },
  },
  emits: {
    viewAlone: (_data: unknown, _title: string) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const expandedIds = shallowRef<string[]>([]);

    /** 预览只在数据变化时计算，收展卡片时复用。 */
    const records = computed(() =>
      props.items.map(item => {
        const response = 'response' in item ? item.response : undefined;
        return {
          item,
          response,
          description: 'description' in item ? item.description : '',
          argumentsPreview: toPreview(item.arguments),
          responsePreview: toPreview(response),
        };
      })
    );

    watch(
      () => props.items,
      items => {
        expandedIds.value = items[0] ? [items[0].id] : [];
      },
      { immediate: true }
    );

    const toggleTool = (id: string) => {
      expandedIds.value = expandedIds.value.includes(id)
        ? expandedIds.value.filter(value => value !== id)
        : [...expandedIds.value, id];
    };

    const renderPreview = (preview: ReturnType<typeof toPreview>) => (
      <div
        style={{
          gridTemplateColumns: preview.pairs.length
            ? `repeat(${preview.pairs.length}, max-content minmax(0, max-content))`
            : undefined,
        }}
        class='llm-tool-call-list-preview-value'
      >
        {preview.pairs.length ? (
          preview.pairs.map(pair => (
            <span
              key={pair.key}
              class='llm-tool-call-list-kv'
            >
              <span
                class='llm-tool-call-list-kv-key'
                v-overflow-tips
              >
                {pair.key}
              </span>
              <span
                class='llm-tool-call-list-kv-value'
                v-overflow-tips
              >
                :{pair.value}
              </span>
            </span>
          ))
        ) : (
          <span
            class='llm-tool-call-list-preview-text'
            v-overflow-tips
          >
            {preview.text}
          </span>
        )}
      </div>
    );

    const openJsonDetail = (data: unknown, title: string) => emit('viewAlone', data, title);

    return () => (
      <div class='llm-tool-call-list'>
        {records.value.map(({ item, response, description, argumentsPreview, responsePreview }, index) => {
          const expanded = expandedIds.value.includes(item.id);
          return (
            <div
              key={item.id}
              class={['llm-tool-call-list-item', { 'is-expanded': expanded }]}
            >
              <span class='llm-tool-call-list-index'>[{index + 1}]</span>
              <div class='llm-tool-call-list-card'>
                <div
                  class='llm-tool-call-list-header'
                  onClick={() => toggleTool(item.id)}
                >
                  <div class='llm-tool-call-list-header-main'>
                    <div class='llm-tool-call-list-preview'>
                      <span
                        class='llm-tool-call-list-name'
                        v-overflow-tips
                      >
                        {item.name || t('未命名工具')}
                      </span>
                      {renderPreview(argumentsPreview)}
                    </div>
                    {response !== undefined && (
                      <>
                        <i class='icon-monitor icon-next-one llm-tool-call-list-arrow' />
                        {renderPreview(responsePreview)}
                      </>
                    )}
                  </div>
                  <i
                    class={[
                      'icon-monitor',
                      expanded ? 'icon-arrow-down' : 'icon-arrow-right',
                      'llm-tool-call-list-toggle',
                    ]}
                  />
                </div>
                {expanded && (
                  <div class='llm-tool-call-list-content'>
                    {description && (
                      <div class='llm-tool-call-list-desc'>
                        <span class='llm-tool-call-list-desc-label'>{t('工具描述')}</span>
                        <span class='llm-tool-call-list-desc-text'>{description}</span>
                      </div>
                    )}
                    <div class='llm-tool-call-list-panels'>
                      <JsonCodeBlock
                        data={item.arguments ?? {}}
                        title={t('调用参数')}
                        onViewAlone={openJsonDetail}
                      />
                      {response !== undefined && (
                        <JsonCodeBlock
                          data={response}
                          title={t('返回结果')}
                          onViewAlone={openJsonDetail}
                        />
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    );
  },
});

/** 对象保留 KV；数组、文本及其他标量使用单行文本，由 CSS 按可用宽度省略。 */
function toPreview(value: unknown) {
  const parsed = parseJsonValue(value);
  const pairs = flattenKvPairs(parsed);
  return {
    pairs,
    text: pairs.length ? '' : (parsed === null ? 'null' : stringifyContent(parsed)).replace(/\s+/g, ' ').trim() || '--',
  };
}
