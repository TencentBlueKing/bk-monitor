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
import { parseOutputObservation } from '../utils/parse-output';
import CollapseSection from './collapse-section';
import JsonCodeBlock from './json-code-block';
import TextContentItem from './text-content-item';

import type { LlmPlannedToolCall, LlmTextItem, LlmToolResult } from '../utils/typings';

import './output-tab.scss';
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

/** 输出 Tab：推理过程、规划的工具调用、模型输出、工具结果 */
export default defineComponent({
  name: 'LlmOutputTab',
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
    /** 当前选中的规划工具 */
    const selectedToolId = shallowRef('');

    const observation = computed(() => parseOutputObservation(props.attributes));
    const selectedTool = computed(
      () =>
        observation.value.plannedToolCalls.find(item => item.id === selectedToolId.value) ||
        observation.value.plannedToolCalls[0]
    );
    const hasContent = computed(() =>
      Boolean(
        observation.value.reasoningMessages.length ||
        observation.value.plannedToolCalls.length ||
        observation.value.modelOutputs.length ||
        observation.value.toolResults.length
      )
    );

    watch(
      () => observation.value.plannedToolCalls,
      calls => {
        if (!calls.find(item => item.id === selectedToolId.value)) {
          selectedToolId.value = calls[0]?.id || '';
        }
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

    /** 渲染工具调用结果 JSON 列表 */
    const renderToolResults = (results: LlmToolResult[]) => (
      <div class='llm-output-tab-tools'>
        {results.map(item => (
          <JsonCodeBlock
            key={item.id}
            data={item.result ?? {}}
            title={item.name || t('返回结果')}
            onViewAlone={openJsonDetail}
          />
        ))}
      </div>
    );

    /** 渲染规划中的工具调用标签与当前选中工具参数 */
    const renderPlannedTools = (tools: LlmPlannedToolCall[]) => (
      <div class='llm-output-tab-tools'>
        <div class='llm-output-tab-tool-tags'>
          {tools.map(tool => (
            <div
              key={tool.id}
              class={['llm-output-tab-tool-tag', { 'is-active': selectedTool.value?.id === tool.id }]}
              onClick={() => {
                selectedToolId.value = tool.id;
              }}
            >
              {tool.name || t('未命名工具')}
            </div>
          ))}
        </div>
        {selectedTool.value?.description ? (
          <div class='llm-output-tab-tool-desc'>
            <span class='llm-output-tab-tool-desc-label'>{t('工具描述')}</span>
            <span class='llm-output-tab-tool-desc-text'>{selectedTool.value.description}</span>
          </div>
        ) : null}
        <JsonCodeBlock
          data={selectedTool.value?.arguments ?? {}}
          title={t('调用参数')}
          onViewAlone={openJsonDetail}
        />
      </div>
    );

    return () => (
      <div class='llm-output-tab'>
        {!hasContent.value ? (
          <div class='llm-output-tab-empty'>{t('暂无数据')}</div>
        ) : (
          <>
            {observation.value.reasoningMessages.length > 0 && (
              <CollapseSection
                count={observation.value.reasoningMessages.length}
                icon='icon-mind-fill'
                title={t('推理过程')}
              >
                {renderTextItems(observation.value.reasoningMessages, t('推理过程'))}
              </CollapseSection>
            )}
            {observation.value.plannedToolCalls.length > 0 && (
              <CollapseSection
                count={observation.value.plannedToolCalls.length}
                icon='icon-setting'
                title={t('规划的工具调用')}
              >
                {renderPlannedTools(observation.value.plannedToolCalls)}
              </CollapseSection>
            )}
            {observation.value.modelOutputs.length > 0 && (
              <CollapseSection
                count={observation.value.modelOutputs.length}
                icon='icon-mc-robot'
                title={t('模型输出')}
              >
                {renderTextItems(observation.value.modelOutputs, t('模型输出'))}
              </CollapseSection>
            )}
            {observation.value.toolResults.length > 0 && (
              <CollapseSection
                count={observation.value.toolResults.length}
                icon='icon-setting'
                title={t('工具调用结果')}
              >
                {renderToolResults(observation.value.toolResults)}
              </CollapseSection>
            )}
          </>
        )}
        <Sideslider
          width={640}
          extCls='llm-output-tab-slider'
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
                <div class='llm-output-tab-slider-json'>
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
                <pre class='llm-output-tab-slider-text'>{detail.value?.kind === 'text' ? detail.value.text : ''}</pre>
              ),
          }}
        </Sideslider>
      </div>
    );
  },
});
