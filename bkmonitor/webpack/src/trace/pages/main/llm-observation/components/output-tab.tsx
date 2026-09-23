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
import { type PropType, computed, defineComponent, shallowRef } from 'vue';

import { Sideslider } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { parseOutputObservation } from '../utils/parse-output';
import { LLM_SEARCH_SECTION } from '../utils/search';
import CollapseSection from './collapse-section';
import JsonCodeBlock from './json-code-block';
import JsonView from './json-view';
import TextContentItem from './text-content-item';
import ToolCallList from './tool-call-list';

import type { LlmTextItem, LlmToolResult } from '../utils/typings';

import './output-tab.scss';

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

/** 输出 Tab：推理过程、模型输出、规划的工具调用、工具结果 */
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
    const observation = computed(() => parseOutputObservation(props.attributes));
    const hasContent = computed(() => {
      const data = observation.value;
      return [data.reasoningMessages, data.plannedToolCalls, data.modelOutputs, data.toolResults].some(
        items => items.length > 0
      );
    });

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

    /** 渲染文本分区条目；searchPrefix 须与 collectOutputHits 的 blockId 前缀一致 */
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

    /** 渲染工具调用结果 JSON 列表 */
    const renderToolResults = (results: LlmToolResult[]) => (
      <div class='llm-output-tab-tools'>
        {results.map(item => (
          <JsonCodeBlock
            key={item.id}
            data={item.result ?? {}}
            searchBlockId={`output:result:${item.id}:json`}
            title={item.name.trim() || t('返回结果')}
            titleBlockId={item.name.trim() ? `output:result:${item.id}:name` : ''}
            onViewAlone={openJsonDetail}
          />
        ))}
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
                icon='icon-tuiliguocheng'
                sectionId={LLM_SEARCH_SECTION.outputReasoning}
                title={t('推理过程')}
              >
                {renderTextItems(observation.value.reasoningMessages, t('推理过程'), 'output:reasoning')}
              </CollapseSection>
            )}
            {observation.value.modelOutputs.length > 0 && (
              <CollapseSection
                count={observation.value.modelOutputs.length}
                icon='icon-LLM'
                sectionId={LLM_SEARCH_SECTION.outputModel}
                title={t('模型输出')}
              >
                {renderTextItems(observation.value.modelOutputs, t('模型输出'), 'output:model')}
              </CollapseSection>
            )}
            {observation.value.plannedToolCalls.length > 0 && (
              <CollapseSection
                count={observation.value.plannedToolCalls.length}
                icon='icon-Tool'
                sectionId={LLM_SEARCH_SECTION.outputPlanned}
                title={t('规划的工具调用')}
              >
                <ToolCallList
                  items={observation.value.plannedToolCalls}
                  searchPrefix='output:planned'
                  onViewAlone={openJsonDetail}
                />
              </CollapseSection>
            )}
            {observation.value.toolResults.length > 0 && (
              <CollapseSection
                count={observation.value.toolResults.length}
                icon='icon-setting'
                sectionId={LLM_SEARCH_SECTION.outputResults}
                title={t('工具调用结果')}
              >
                {renderToolResults(observation.value.toolResults)}
              </CollapseSection>
            )}
          </>
        )}
        {detail.value ? (
          <Sideslider
            width={640}
            extCls='llm-output-tab-slider'
            isShow={true}
            quickClose={true}
            transfer={true}
            onClosed={closeDetail}
            onHidden={closeDetail}
            onUpdate:isShow={(val: boolean) => {
              if (!val) closeDetail();
            }}
          >
            {{
              header: () => <span>{detail.value?.title || ''}</span>,
              default: () =>
                detail.value?.kind === 'json' ? (
                  <div class='llm-output-tab-slider-json'>
                    <JsonView
                      data={detail.value.data}
                      showLineNumber={true}
                    />
                  </div>
                ) : (
                  <pre class='llm-output-tab-slider-text'>{detail.value?.kind === 'text' ? detail.value.text : ''}</pre>
                ),
            }}
          </Sideslider>
        ) : null}
      </div>
    );
  },
});
