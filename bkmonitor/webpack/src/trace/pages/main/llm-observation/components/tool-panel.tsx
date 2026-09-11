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
import VueJsonPretty from 'vue-json-pretty';

import { toJsonPrettyData } from '../utils/helpers';
import { parseToolObservation } from '../utils/parse-tool';
import JsonCodeBlock from './json-code-block';

import './tool-panel.scss';
import 'vue-json-pretty/lib/styles.css';

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
    const detail = shallowRef<{ data: unknown; title: string } | null>(null);
    const observation = computed(() => parseToolObservation(props.attributes));

    return () => (
      <div class='llm-tool-panel'>
        {observation.value.description ? (
          <div class='llm-tool-panel-desc'>
            <span class='llm-tool-panel-desc-label'>{t('工具描述')}</span>
            <span class='llm-tool-panel-desc-text'>{observation.value.description}</span>
          </div>
        ) : null}
        <JsonCodeBlock
          bordered={true}
          data={observation.value.arguments}
          title={t('调用参数')}
          onViewAlone={(data, title) => {
            detail.value = { data, title };
          }}
        />
        <JsonCodeBlock
          bordered={true}
          data={observation.value.result}
          title={t('返回结果')}
          onViewAlone={(data, title) => {
            detail.value = { data, title };
          }}
        />
        <Sideslider
          width={640}
          extCls='llm-tool-panel-slider'
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
            default: () => (
              <div class='llm-tool-panel-slider-json'>
                <VueJsonPretty
                  collapsedOnClickBrackets={false}
                  data={toJsonPrettyData(detail.value?.data)}
                  deep={20}
                  showIcon={false}
                  showKeyValueSpace={true}
                  showLine={false}
                  showLineNumber={true}
                />
              </div>
            ),
          }}
        </Sideslider>
      </div>
    );
  },
});
