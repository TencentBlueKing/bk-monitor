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

import { Sideslider } from 'bkui-vue';
import { useI18n } from 'vue-i18n';
import VueJsonPretty from 'vue-json-pretty';

import { toJsonPrettyData } from '../utils/helpers';
import { flattenKvPairs, parseInputObservation } from '../utils/parse-input';
import CollapseSection from './collapse-section';
import JsonCodeBlock from './json-code-block';
import TextContentItem from './text-content-item';

import type { LlmTextItem, LlmToolCallRecord, LlmToolDefinition } from '../utils/typings';

import './input-tab.scss';
import 'vue-json-pretty/lib/styles.css';

/** 独立查看侧栏内容：文本或 JSON */
type DetailState =
  | null
  | {
      data: unknown;
      kind: 'json';
      title: string;
    }
  | {
      kind: 'text';
      text: string;
      title: string;
    };

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
    const detail = shallowRef<DetailState>(null);
    /** 当前选中的可用工具 */
    const selectedToolName = shallowRef('');
    /** 已展开的工具调用记录 id */
    const expandedToolIds = shallowRef<string[]>([]);

    const observation = computed(() => parseInputObservation(props.attributes));
    const selectedTool = computed(
      () =>
        observation.value.availableTools.find(item => item.name === selectedToolName.value) ||
        observation.value.availableTools[0]
    );
    const hasContent = computed(() => {
      const data = observation.value;
      return Boolean(
        data.userMessages.length ||
        data.modelMessages.length ||
        data.systemPrompts.length ||
        data.reasoningMessages.length ||
        data.toolCalls.length ||
        data.availableTools.length
      );
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

    watch(
      () => observation.value.toolCalls,
      records => {
        expandedToolIds.value = records[0] ? [records[0].id] : [];
      },
      { immediate: true }
    );

    /** 打开文本独立查看侧栏 */
    const openTextDetail = (title: string, content: string) => {
      detail.value = { kind: 'text', title, text: content };
    };

    /** 打开 JSON 独立查看侧栏 */
    const openJsonDetail = (data: unknown, title: string) => {
      detail.value = { kind: 'json', title, data };
    };

    /** 展开 / 收起单条工具调用记录 */
    const toggleTool = (id: string) => {
      expandedToolIds.value = expandedToolIds.value.includes(id)
        ? expandedToolIds.value.filter(item => item !== id)
        : [...expandedToolIds.value, id];
    };

    /** 渲染文本分区条目 */
    const renderTextItems = (items: LlmTextItem[], title: string) =>
      items.map((item, index) => (
        <TextContentItem
          key={item.id}
          content={item.content}
          index={index + 1}
          onViewAlone={content => openTextDetail(title, content)}
        />
      ));

    /** 渲染工具调用预览 KV */
    const renderKvPairs = (value: unknown) =>
      flattenKvPairs(value).map(pair => (
        <span
          key={`${pair.key}-${pair.value}`}
          class='llm-input-tab-kv'
        >
          <span class='llm-input-tab-kv-key' v-overflow-tips>{pair.key}</span>
          <span class='llm-input-tab-kv-value' v-overflow-tips>:{pair.value}</span>
        </span>
      ));

    /** 渲染单条工具调用记录（折叠预览 + 展开 JSON） */
    const renderToolCall = (item: LlmToolCallRecord, index: number) => {
      const expanded = expandedToolIds.value.includes(item.id);
      const argPairs = flattenKvPairs(item.arguments);
      const resultPairs = flattenKvPairs(item.response);
      return (
        <div
          key={item.id}
          class={['llm-input-tab-tool-call', { 'is-expanded': expanded }]}
        >
          <span class='llm-text-content-index'>[{index + 1}]</span>
          <div class='llm-input-tab-tool-card'>
            <div
              class='llm-input-tab-tool-header'
              onClick={() => toggleTool(item.id)}
            >
              <div class='llm-input-tab-tool-header-main'>
                <span class='llm-input-tab-tool-name'>{item.name || t('未命名工具')}</span>
                {(argPairs.length > 0 || resultPairs.length > 0) && (
                  <div class='llm-input-tab-tool-preview'>
                    {argPairs.length > 0 && (
                      <div class='llm-input-tab-kv-list'>{renderKvPairs(item.arguments)}</div>
                    )}
                    {resultPairs.length > 0 && (
                      <>
                        <i class='icon-monitor icon-arrow-right llm-input-tab-tool-arrow' />
                        <div class='llm-input-tab-kv-list is-result'>{renderKvPairs(item.response)}</div>
                      </>
                    )}
                  </div>
                )}
              </div>
              <i
                class={[
                  'icon-monitor',
                  expanded ? 'icon-arrow-down' : 'icon-arrow-right',
                  'llm-input-tab-tool-toggle',
                ]}
              />
            </div>
            {expanded && (
              <div class='llm-input-tab-tool-panels'>
                <JsonCodeBlock
                  data={item.arguments ?? {}}
                  title={t('调用参数')}
                  onViewAlone={openJsonDetail}
                />
                {item.response !== undefined && (
                  <JsonCodeBlock
                    data={item.response}
                    title={t('返回结果')}
                    onViewAlone={openJsonDetail}
                  />
                )}
              </div>
            )}
          </div>
        </div>
      );
    };

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
              {tool.name}
            </div>
          ))}
        </div>
        {selectedTool.value?.description ? (
          <div class='llm-input-tab-tool-desc'>
            <span class='llm-input-tab-tool-desc-label'>{t('工具描述')}</span>
            <span class='llm-input-tab-tool-desc-text'>{selectedTool.value.description}</span>
          </div>
        ) : null}
        <JsonCodeBlock
          data={selectedTool.value?.parameters ?? {}}
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
                icon='icon-xiaoxi'
                title={t('用户消息')}
              >
                {renderTextItems(observation.value.userMessages, t('用户消息'))}
              </CollapseSection>
            )}
            {observation.value.modelMessages.length > 0 && (
              <CollapseSection
                count={observation.value.modelMessages.length}
                icon='icon-mc-robot'
                title={t('模型消息')}
              >
                {renderTextItems(observation.value.modelMessages, t('模型消息'))}
              </CollapseSection>
            )}
            {observation.value.systemPrompts.length > 0 && (
              <CollapseSection
                count={observation.value.systemPrompts.length}
                icon='icon-setting'
                title={t('系统 Prompts')}
              >
                {renderTextItems(observation.value.systemPrompts, t('系统 Prompts'))}
              </CollapseSection>
            )}
            {observation.value.reasoningMessages.length > 0 && (
              <CollapseSection
                count={observation.value.reasoningMessages.length}
                icon='icon-mind-fill'
                title={t('推理过程')}
              >
                {renderTextItems(observation.value.reasoningMessages, t('推理过程'))}
              </CollapseSection>
            )}
            {observation.value.toolCalls.length > 0 && (
              <CollapseSection
                count={observation.value.toolCalls.length}
                icon='icon-setting'
                title={t('工具调用记录')}
              >
                <div class='llm-input-tab-tool-calls'>
                  {observation.value.toolCalls.map((item, index) => renderToolCall(item, index))}
                </div>
              </CollapseSection>
            )}
            {observation.value.availableTools.length > 0 && (
              <CollapseSection
                count={observation.value.availableTools.length}
                icon='icon-setting'
                title={t('可用工具')}
              >
                {renderAvailableTools(observation.value.availableTools)}
              </CollapseSection>
            )}
          </>
        )}
        <Sideslider
          width={640}
          extCls='llm-input-tab-slider'
          isShow={Boolean(detail.value)}
          quickClose={true}
          transfer={true}
          onClosed={() => {
            detail.value = null;
          }}
          onUpdate:isShow={(val: boolean) => {
            if (!val) detail.value = null;
          }}
        >
          {{
            header: () => <span>{detail.value?.title || ''}</span>,
            default: () =>
              detail.value?.kind === 'json' ? (
                <div class='llm-input-tab-slider-json'>
                  <VueJsonPretty
                    collapsedOnClickBrackets={false}
                    data={toJsonPrettyData(detail.value.data)}
                    deep={20}
                    showIcon={false}
                    showKeyValueSpace={true}
                    showLine={false}
                    showLineNumber={true}
                  />
                </div>
              ) : (
                <pre class='llm-input-tab-slider-text'>{detail.value?.kind === 'text' ? detail.value.text : ''}</pre>
              ),
          }}
        </Sideslider>
      </div>
    );
  },
});
