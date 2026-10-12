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

import { parseToolObservation } from '../utils/parse-tool';
import JsonCodeBlock from './json-code-block';
import JsonView from './json-view';
import ToolDescBar from './tool-desc-bar';

import './tool-panel.scss';

/** Tool Span 观测内容：工具描述、调用参数、返回结果 */
export default defineComponent({
  name: 'LlmToolPanel',
  props: {
    /** Span attributes */
    attributes: {
      type: Object as PropType<Record<string, unknown>>,
      default: () => ({}),
    },
  },
  setup(props) {
    const { t } = useI18n();
    /** 独立查看侧栏当前展示的 JSON */
    const detail = shallowRef<null | { data: unknown; title: string }>(null);
    const observation = computed(() => parseToolObservation(props.attributes));

    /** 关闭独立查看：卸载 Sideslider，避免 teleport 到 body 的 .bk-modal 残留挡点击 */
    const closeDetail = () => {
      detail.value = null;
    };

    return () => (
      <div class='llm-tool-panel'>
        {/* blockId 与 collectToolHits 固定前缀对齐 */}
        <ToolDescBar
          descBlockId='tool:desc'
          description={observation.value.description}
          name={observation.value.name}
          nameBlockId='tool:name'
        />
        <JsonCodeBlock
          bordered={true}
          data={observation.value.arguments}
          searchBlockId='tool:args'
          title={t('调用参数')}
          onViewAlone={(data, title) => {
            detail.value = { data, title };
          }}
        />
        <JsonCodeBlock
          bordered={true}
          data={observation.value.result}
          searchBlockId='tool:result'
          title={t('返回结果')}
          onViewAlone={(data, title) => {
            detail.value = { data, title };
          }}
        />
        {detail.value ? (
          <Sideslider
            width={640}
            extCls='llm-tool-panel-slider'
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
              default: () => (
                <div class='llm-tool-panel-slider-json'>
                  <JsonView
                    data={detail.value?.data}
                    showLineNumber={true}
                  />
                </div>
              ),
            }}
          </Sideslider>
        ) : null}
      </div>
    );
  },
});
