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
import { type PropType, computed, defineComponent } from 'vue';

import VueJsonPretty from 'vue-json-pretty';

import { beautifyJsonValue, formatJsonDisplay, isRecord } from '../utils/helpers';

import './json-view.scss';
import 'vue-json-pretty/lib/styles.css';

/** 参数 / 结果在卡片与独立查看中共用的展示层，不改写传入数据。 */
export default defineComponent({
  name: 'LlmJsonView',
  props: {
    data: {
      type: [Object, Array, String, Number, Boolean] as PropType<unknown>,
      default: null,
    },
    showLineNumber: {
      type: Boolean,
      default: false,
    },
  },
  setup(props) {
    const data = computed(() => beautifyJsonValue(props.data));

    return () => (
      <div class='llm-json-view'>
        {Array.isArray(data.value) || isRecord(data.value) ? (
          <VueJsonPretty
            renderNodeValue={({ node, defaultValue }) => {
              if (typeof node.content !== 'string') return defaultValue;
              const text = formatJsonDisplay(node.content);
              return /[\r\n]/.test(text) ? <span class='llm-json-view-text'>{text}</span> : defaultValue;
            }}
            collapsedOnClickBrackets={false}
            data={data.value}
            deep={20}
            showIcon={false}
            showKeyValueSpace={true}
            showLine={false}
            showLineNumber={props.showLineNumber}
          />
        ) : (
          <pre class='llm-json-view-text'>{formatJsonDisplay(data.value)}</pre>
        )}
      </div>
    );
  },
});
