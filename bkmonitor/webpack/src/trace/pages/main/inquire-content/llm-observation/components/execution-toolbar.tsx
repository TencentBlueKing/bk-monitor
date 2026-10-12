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

import { Checkbox, Input, Radio } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import type { LlmExecutionFilter } from '../utils/typings';

import './execution-toolbar.scss';

/** 执行线筛选 Tab 配置（error 使用异常 icon，其余为 Agent/LLM/Tool） */
const FILTER_TABS: { icon?: string; id: LlmExecutionFilter }[] = [
  { id: 'all' },
  { id: 'agent', icon: 'Agent' },
  { id: 'llm', icon: 'LLM' },
  { id: 'tool', icon: 'Tool' },
  { id: 'error', icon: 'yichang' },
];

/** Agent 执行线工具栏：同会话切换、类型筛选、关键字搜索 */
export default defineComponent({
  name: 'LlmExecutionToolbar',
  props: {
    conversationId: {
      type: String,
      default: '',
    },
    counts: {
      type: Object as PropType<Record<LlmExecutionFilter, number>>,
      default: () => ({ all: 0, agent: 0, llm: 0, tool: 0, error: 0 }),
    },
    filter: {
      type: String as PropType<LlmExecutionFilter>,
      default: 'all',
    },
    keyword: {
      type: String,
      default: '',
    },
    showSession: {
      type: Boolean,
      default: false,
    },
  },
  emits: {
    'update:filter': (_value: LlmExecutionFilter) => true,
    'update:keyword': (_value: string) => true,
    'update:showSession': (_value: boolean) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();

    const tabLabel = (id: LlmExecutionFilter) => {
      const labels: Record<LlmExecutionFilter, string> = {
        all: t('全部'),
        agent: 'Agent',
        llm: t('模型'),
        tool: t('工具'),
        error: t('异常'),
      };
      return `${labels[id]} (${props.counts[id] || 0})`;
    };

    const handleFilterChange = (value: LlmExecutionFilter) => {
      if (value === props.filter) return;
      emit('update:filter', value);
    };

    /** 搜索框实时同步 keyword；flatten 在 hook 的 computed 中过滤，无需防抖 */
    const handleKeywordChange = (value: string) => {
      emit('update:keyword', value);
    };

    const renderFilterIcon = (tab: (typeof FILTER_TABS)[number]) => {
      if (tab.icon) {
        return (
          <i
            class={[
              'llm-execution-filter-icon',
              'icon-monitor',
              `icon-${tab.icon}`,
              { 'is-error': tab.id === 'error' },
            ]}
          />
        );
      }
      return null;
    };

    return () => (
      <div class='llm-execution-toolbar'>
        <div class='llm-execution-toolbar-title'>{t('Agent 执行线')}</div>
        <div class='llm-execution-toolbar-row'>
          <div class='llm-execution-toolbar-left'>
            <div
              class={['llm-execution-session', { 'is-disabled': !props.conversationId }]}
              v-bk-tooltips={{
                content: t('当前 Trace 无会话 ID'),
                disabled: Boolean(props.conversationId),
                placement: 'top',
              }}
            >
              <Checkbox
                disabled={!props.conversationId}
                modelValue={props.showSession}
                onChange={(value: boolean) => emit('update:showSession', value)}
              >
                {t('查看同会话的完整时间线')}
              </Checkbox>
            </div>
            <Radio.Group
              class='llm-execution-filters'
              modelValue={props.filter}
              type='capsule'
              onChange={handleFilterChange}
            >
              {FILTER_TABS.map(tab => (
                <Radio.Button
                  key={tab.id}
                  class='llm-execution-filter'
                  label={tab.id}
                >
                  <span class='llm-execution-filter-inner'>
                    {renderFilterIcon(tab)}
                    <span>{tabLabel(tab.id)}</span>
                  </span>
                </Radio.Button>
              ))}
            </Radio.Group>
          </div>
          <Input
            class='llm-execution-search'
            modelValue={props.keyword}
            placeholder={t('搜索 名称、模型、Span ID')}
            type='search'
            clearable
            show-clear-only-hover
            onClear={() => handleKeywordChange('')}
            onEnter={handleKeywordChange}
            onSearch={() => handleKeywordChange(props.keyword)}
            onUpdate:modelValue={handleKeywordChange}
          />
        </div>
      </div>
    );
  },
});
