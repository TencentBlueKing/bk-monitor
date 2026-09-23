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

import { parseInputObservation } from '../utils/parse-input';
import { LLM_OBSERVATION_SEARCH_KEY, LLM_SEARCH_SECTION } from '../utils/search';
import CollapseSection from './collapse-section';
import DetailSlider, { type LlmDetailSliderContent } from './detail-slider';
import HighlightText from './highlight-text';
import JsonCodeBlock from './json-code-block';
import TextContentItem from './text-content-item';
import ToolCallList from './tool-call-list';
import ToolDescBar from './tool-desc-bar';

import type { LlmTextItem, LlmToolDefinition } from '../utils/typings';

import './input-tab.scss';

/** 输入 Tab：用户/模型/系统消息、推理、工具调用记录、可用工具 */
export default defineComponent({
  name: 'LlmInputTab',
  props: {
    /** Span attributes */
    attributes: {
      type: Object as PropType<Record<string, unknown>>,
      default: () => ({}),
    },
  },
  setup(props) {
    const { t } = useI18n();
    const detail = shallowRef<LlmDetailSliderContent | null>(null);
    /** 当前选中的可用工具 */
    const selectedToolName = shallowRef('');
    const search = inject(LLM_OBSERVATION_SEARCH_KEY, null);

    const observation = computed(() => parseInputObservation(props.attributes));
    const selectedTool = computed(
      () =>
        observation.value.availableTools.find(item => item.name === selectedToolName.value) ||
        observation.value.availableTools[0]
    );
    const hasContent = computed(() => {
      const data = observation.value;
      return [
        data.userMessages,
        data.modelMessages,
        data.systemPrompts,
        data.reasoningMessages,
        data.toolCalls,
        data.availableTools,
      ].some(items => items.length > 0);
    });

    watch(
      () => observation.value.availableTools,
      tools => {
        if (!tools.find(item => item.name === selectedToolName.value)) {
          selectedToolName.value = tools[0]?.name || '';
        }
      },
      { immediate: true }
    );

    // 可用工具只渲染当前选中项的描述 / 参数，定位前要先切到命中的那个 tag
    watch(
      () => [search?.activeIndex.value, search?.activeHit.value?.toolName] as const,
      ([, toolName]) => {
        if (toolName && observation.value.availableTools.some(item => item.name === toolName)) {
          selectedToolName.value = toolName;
        }
      }
    );

    /** 打开文本独立查看侧栏 */
    const openTextDetail = (title: string, content: string) => {
      detail.value = { kind: 'text', title, text: content };
    };

    /** 打开 JSON 独立查看侧栏 */
    const openJsonDetail = (data: unknown, title: string) => {
      detail.value = { kind: 'json', title, data };
    };

    /** 关闭独立查看：卸载 Sideslider，避免 teleport 到 body 的 .bk-modal 残留挡点击 */
    const closeDetail = () => {
      detail.value = null;
    };

    /** 渲染文本分区条目；searchPrefix 须与 collectInputHits 的 blockId 前缀一致 */
    const renderTextItems = (items: LlmTextItem[], title: string, searchPrefix: string) =>
      items.map((item, index) => (
        <TextContentItem
          key={item.id}
          content={item.content}
          index={index + 1}
          searchBlockId={`${searchPrefix}:${item.id}`}
          onViewAlone={content => openTextDetail(title, content)}
        />
      ));

    /** 渲染可用工具标签与当前选中工具的参数 */
    const renderAvailableTools = (tools: LlmToolDefinition[]) => (
      <div class='llm-input-tab-tools'>
        <div class='llm-input-tab-tool-tags'>
          {tools.map(tool => (
            <div
              key={tool.name}
              class={['llm-input-tab-tool-tag', { 'is-active': selectedTool.value?.name === tool.name }]}
              onClick={() => {
                selectedToolName.value = tool.name;
              }}
            >
              <HighlightText
                blockId={`input:tool:${tool.name}:name`}
                text={tool.name.trim()}
              />
            </div>
          ))}
        </div>
        {selectedTool.value ? (
          <ToolDescBar
            descBlockId={`input:tool:${selectedTool.value.name}:desc`}
            description={selectedTool.value.description}
          />
        ) : null}
        <JsonCodeBlock
          data={selectedTool.value?.parameters ?? {}}
          searchBlockId={selectedTool.value ? `input:tool:${selectedTool.value.name}:params` : ''}
          title={t('调用参数')}
          onViewAlone={openJsonDetail}
        />
      </div>
    );

    return () => (
      <div class='llm-input-tab'>
        {!hasContent.value ? (
          <div class='llm-input-tab-empty'>{t('暂无数据')}</div>
        ) : (
          <>
            {observation.value.userMessages.length > 0 && (
              <CollapseSection
                count={observation.value.userMessages.length}
                icon='icon-a-chatqipao'
                sectionId={LLM_SEARCH_SECTION.inputUser}
                title={t('用户消息')}
              >
                {renderTextItems(observation.value.userMessages, t('用户消息'), 'input:user')}
              </CollapseSection>
            )}
            {observation.value.modelMessages.length > 0 && (
              <CollapseSection
                count={observation.value.modelMessages.length}
                icon='icon-LLM'
                sectionId={LLM_SEARCH_SECTION.inputModel}
                title={t('模型消息')}
              >
                {renderTextItems(observation.value.modelMessages, t('模型消息'), 'input:model')}
              </CollapseSection>
            )}
            {observation.value.systemPrompts.length > 0 && (
              <CollapseSection
                count={observation.value.systemPrompts.length}
                icon='icon-neizhi'
                sectionId={LLM_SEARCH_SECTION.inputSystem}
                title={t('系统 Prompts')}
              >
                {renderTextItems(observation.value.systemPrompts, t('系统 Prompts'), 'input:system')}
              </CollapseSection>
            )}
            {observation.value.reasoningMessages.length > 0 && (
              <CollapseSection
                count={observation.value.reasoningMessages.length}
                icon='icon-tuiliguocheng'
                sectionId={LLM_SEARCH_SECTION.inputReasoning}
                title={t('推理过程')}
              >
                {renderTextItems(observation.value.reasoningMessages, t('推理过程'), 'input:reasoning')}
              </CollapseSection>
            )}
            {observation.value.toolCalls.length > 0 && (
              <CollapseSection
                count={observation.value.toolCalls.length}
                icon='icon-gongjutiaoyongjilu'
                sectionId={LLM_SEARCH_SECTION.inputToolCalls}
                title={t('工具调用记录')}
              >
                <ToolCallList
                  items={observation.value.toolCalls}
                  searchPrefix='input:toolcall'
                  onViewAlone={openJsonDetail}
                />
              </CollapseSection>
            )}
            {observation.value.availableTools.length > 0 && (
              <CollapseSection
                count={observation.value.availableTools.length}
                icon='icon-Tool'
                sectionId={LLM_SEARCH_SECTION.inputTools}
                title={t('可用工具')}
              >
                {renderAvailableTools(observation.value.availableTools)}
              </CollapseSection>
            )}
          </>
        )}
        <DetailSlider
          detail={detail.value}
          onClose={closeDetail}
        />
      </div>
    );
  },
});
