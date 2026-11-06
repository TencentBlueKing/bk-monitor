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
import { type PropType, computed, defineComponent, inject, shallowRef, watch } from 'vue';

import { useI18n } from 'vue-i18n';

import { parseJsonValue, stringifyContent, truncateTipContent } from '../utils/helpers';
import { flattenKvPairs } from '../utils/parse-input';
import { LLM_OBSERVATION_SEARCH_KEY, resolveToolCallExpandId } from '../utils/search';
import HighlightText from './highlight-text';
import JsonCodeBlock from './json-code-block';
import ToolDescBar from './tool-desc-bar';

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
    /** 搜索 path 前缀，实际 block 为 `${prefix}:${item.id}:...` */
    searchPrefix: {
      type: String,
      default: '',
    },
  },
  emits: {
    viewAlone: (_data: unknown, _title: string) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const expandedIds = shallowRef<string[]>([]);
    /** 同一卡片内左右 JSON 共用展开态 */
    const jsonExpandedIds = shallowRef<string[]>([]);
    const search = inject(LLM_OBSERVATION_SEARCH_KEY, null);

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
        jsonExpandedIds.value = [];
      },
      { immediate: true }
    );

    /** 命中折叠卡片内的参数 / 结果时，先把该卡片加进 expandedIds */
    const ensureExpandedForHit = () => {
      const expandId = resolveToolCallExpandId(
        search?.activeHit.value,
        props.searchPrefix,
        props.items.map(item => item.id)
      );
      if (expandId && !expandedIds.value.includes(expandId)) {
        expandedIds.value = [...expandedIds.value, expandId];
      }
    };

    watch(
      () => [search?.activeIndex.value, search?.keyword.value, search?.activeHit.value?.blockId],
      () => {
        ensureExpandedForHit();
      },
      { immediate: true }
    );

    const toggleTool = (id: string) => {
      expandedIds.value = expandedIds.value.includes(id)
        ? expandedIds.value.filter(value => value !== id)
        : [...expandedIds.value, id];
    };

    const setJsonExpanded = (id: string, expanded: boolean) => {
      const has = jsonExpandedIds.value.includes(id);
      if (expanded === has) return;
      jsonExpandedIds.value = expanded
        ? [...jsonExpandedIds.value, id]
        : jsonExpandedIds.value.filter(value => value !== id);
    };

    const renderPairs = (preview: ReturnType<typeof toPreview>, className?: string) => (
      <div
        style={
          preview.pairs.length
            ? { gridTemplateColumns: `repeat(${preview.pairs.length}, max-content minmax(0, max-content))` }
            : undefined
        }
        class={['llm-tool-call-list-pairs', className]}
      >
        {preview.pairs.length ? (
          preview.pairs.map(pair => (
            <span
              key={pair.key}
              class='llm-tool-call-list-kv'
            >
              <span
                class='llm-tool-call-list-kv-key'
                v-overflow-tips={{ content: truncateTipContent(pair.key), placement: 'top' }}
              >
                {pair.key}
              </span>
              <span
                class='llm-tool-call-list-kv-value'
                v-overflow-tips={{ content: truncateTipContent(pair.value), placement: 'top' }}
              >
                :{pair.value}
              </span>
            </span>
          ))
        ) : (
          <span
            class='llm-tool-call-list-pairs-text'
            v-overflow-tips={{ content: truncateTipContent(preview.text), placement: 'top' }}
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
          const searchPrefix = props.searchPrefix ? `${props.searchPrefix}:${item.id}` : '';
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
                    <div class={['llm-tool-call-list-call', { 'has-result': response !== undefined }]}>
                      <span
                        class='llm-tool-call-list-name'
                        v-overflow-tips
                      >
                        {searchPrefix ? (
                          <HighlightText
                            blockId={`${searchPrefix}:name`}
                            text={item.name.trim() || t('未命名工具')}
                          />
                        ) : (
                          item.name || t('未命名工具')
                        )}
                      </span>
                      {renderPairs(argumentsPreview)}
                    </div>
                    {response !== undefined && (
                      <>
                        <i class='icon-monitor icon-next-one llm-tool-call-list-arrow' />
                        {renderPairs(responsePreview, 'llm-tool-call-list-result')}
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
                    <ToolDescBar
                      descBlockId={searchPrefix ? `${searchPrefix}:desc` : ''}
                      description={description}
                    />
                    <div class='llm-tool-call-list-panels'>
                      <JsonCodeBlock
                        data={item.arguments ?? {}}
                        expanded={jsonExpandedIds.value.includes(item.id)}
                        searchBlockId={searchPrefix ? `${searchPrefix}:args` : ''}
                        title={t('调用参数')}
                        onUpdate:expanded={val => setJsonExpanded(item.id, val)}
                        onViewAlone={openJsonDetail}
                      />
                      {response !== undefined && (
                        <JsonCodeBlock
                          data={response}
                          expanded={jsonExpandedIds.value.includes(item.id)}
                          searchBlockId={searchPrefix ? `${searchPrefix}:resp` : ''}
                          title={t('返回结果')}
                          onUpdate:expanded={val => setJsonExpanded(item.id, val)}
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
