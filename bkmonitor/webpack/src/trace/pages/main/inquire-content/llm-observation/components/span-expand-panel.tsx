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

import { type PropType, computed, defineComponent, shallowRef } from 'vue';

import { Switcher } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import DetailSlider, { type LlmDetailSliderContent } from '../../../llm-observation/components/detail-slider';
import ErrorAlert from '../../../llm-observation/components/error-alert';
import InputTab from '../../../llm-observation/components/input-tab';
import JsonCodeBlock from '../../../llm-observation/components/json-code-block';
import JsonView from '../../../llm-observation/components/json-view';
import OutputTab from '../../../llm-observation/components/output-tab';
import ToolDescBar from '../../../llm-observation/components/tool-desc-bar';
import { countInputObservation, parseInputObservation } from '../../../llm-observation/utils/parse-input';
import { countOutputObservation, parseOutputObservation } from '../../../llm-observation/utils/parse-output';
import { formatAgentLabel, parseAgentObservation } from '../../../llm-observation/utils/parse-agent';
import { parseToolObservation } from '../../../llm-observation/utils/parse-tool';

import type { LlmSpanRowView } from '../utils/typings';

import './span-expand-panel.scss';

/** 非 Tool Span：输入 / 输出 Tab；Tool 走双列 JsonCodeBlock */
type IoTabName = 'input' | 'output';

/** Span 行展开区：错误提示、Agent/Tool 描述、输入输出 Tab 或 Tool JSON、原始 Span 切换 */
export default defineComponent({
  name: 'LlmSpanExpandPanel',
  props: {
    row: {
      type: Object as PropType<LlmSpanRowView>,
      required: true,
    },
  },
  emits: {
    'view-detail': (_spanId: string) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const activeIoTab = shallowRef<IoTabName>('input');
    const showRawJson = shallowRef(false);
    const toolJsonExpanded = shallowRef(false);
    /** Tool 参数/结果 JsonCodeBlock「单独查看」时打开的侧栏内容 */
    const jsonDetail = shallowRef<LlmDetailSliderContent | null>(null);

    const isTool = computed(() => props.row.kind === 'TOOL');
    const agentObservation = computed(() => parseAgentObservation(props.row.attributes));
    const agentLabel = computed(() => formatAgentLabel(agentObservation.value.name, agentObservation.value.version));
    const showAgentDescBar = computed(
      () =>
        props.row.kind === 'AGENT' &&
        Boolean(agentObservation.value.name || agentObservation.value.version || agentObservation.value.description)
    );
    const toolObservation = computed(() => parseToolObservation(props.row.attributes));
    const inputCount = computed(() => countInputObservation(parseInputObservation(props.row.attributes)));
    const outputCount = computed(() => countOutputObservation(parseOutputObservation(props.row.attributes)));
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

    const renderDescription = () => {
      if (props.row.kind === 'LLM') return null;
      if (props.row.kind === 'AGENT') {
        if (!showAgentDescBar.value) return null;
        return (
          <ToolDescBar
            descBlockId='agent:desc'
            description={agentObservation.value.description}
            name={agentLabel.value}
            nameBlockId='agent:name'
            variant='agent'
          />
        );
      }
      if (props.row.kind === 'TOOL') {
        return (
          <ToolDescBar
            descBlockId='tool:desc'
            description={toolObservation.value.description}
            name={toolObservation.value.name}
            nameBlockId='tool:name'
          />
        );
      }
      return null;
    };

    /** flush：Tool 布局下操作条与内容区对齐（无 Tab 行） */
    const renderActions = (flush = false) => (
      <div class={['llm-span-expand-actions', { 'is-flush': flush }]}>
        <div class='llm-span-expand-switch'>
          <Switcher
            modelValue={showRawJson.value}
            size='small'
            theme='primary'
            onChange={(val: boolean) => {
              showRawJson.value = val;
            }}
          />
          <span class='llm-span-expand-switch-text'>{t('查看原始 Span JSON')}</span>
        </div>
        <div
          class='llm-span-expand-detail-link'
          onClick={() => emit('view-detail', props.row.spanId)}
        >
          <span>{t('查看 Span 详情')}</span>
          <i class='icon-monitor icon-mc-goto' />
        </div>
      </div>
    );

    const renderJson = () => (
      <div class='llm-span-expand-json is-dark'>
        <JsonView
          data={props.row.rawSpan}
          showLineNumber={true}
          theme='dark'
        />
      </div>
    );

    const renderToolContent = () => (
      <div class='llm-span-expand-tool'>
        <div class='llm-span-expand-tool-col'>
          <JsonCodeBlock
            data={toolObservation.value.arguments}
            expanded={toolJsonExpanded.value}
            title={t('调用参数')}
            onUpdate:expanded={val => {
              toolJsonExpanded.value = val;
            }}
            onViewAlone={(data, title) => {
              jsonDetail.value = { kind: 'json', data, title };
            }}
          />
        </div>
        <div class='llm-span-expand-tool-col'>
          <JsonCodeBlock
            data={toolObservation.value.result}
            expanded={toolJsonExpanded.value}
            title={t('返回结果')}
            onUpdate:expanded={val => {
              toolJsonExpanded.value = val;
            }}
            onViewAlone={(data, title) => {
              jsonDetail.value = { kind: 'json', data, title };
            }}
          />
        </div>
      </div>
    );

    const renderIoContent = () => (
      <div class='llm-span-expand-io'>
        <div class='llm-span-expand-toolbar'>
          <div class='llm-span-expand-tabs'>
            {ioTabs.value.map(tab => (
              <div
                key={tab.name}
                class={['llm-span-expand-tab', { 'is-active': activeIoTab.value === tab.name }]}
                onClick={() => {
                  activeIoTab.value = tab.name;
                }}
              >
                <i class={['icon-monitor', tab.icon, 'llm-span-expand-tab-icon']} />
                <span>{tab.label}</span>
              </div>
            ))}
          </div>
          {renderActions()}
        </div>
        <div class={['llm-span-expand-content', { 'is-raw-json': showRawJson.value }]}>
          {showRawJson.value ? (
            renderJson()
          ) : activeIoTab.value === 'input' ? (
            <InputTab attributes={props.row.attributes} />
          ) : (
            <OutputTab attributes={props.row.attributes} />
          )}
        </div>
      </div>
    );

    const renderErrorAlert = () => {
      if (!props.row.isError) return null;
      return <ErrorAlert message={props.row.errorMessage || '--'} />;
    };

    return () => (
      <div
        class='llm-span-expand'
        onClick={e => e.stopPropagation()}
      >
        {renderErrorAlert()}
        {renderDescription()}
        {isTool.value ? (
          <>
            <div class='llm-span-expand-toolbar is-tool'>{renderActions(true)}</div>
            {showRawJson.value ? renderJson() : renderToolContent()}
          </>
        ) : (
          renderIoContent()
        )}
        <DetailSlider
          detail={jsonDetail.value}
          width={640}
          onClose={() => {
            jsonDetail.value = null;
          }}
        />
      </div>
    );
  },
});
