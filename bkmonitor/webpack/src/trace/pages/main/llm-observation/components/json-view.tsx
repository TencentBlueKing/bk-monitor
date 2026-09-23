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
import HighlightText from './highlight-text';

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
    theme: {
      type: String as PropType<'dark' | 'default'>,
      default: 'default',
    },
    /** 与搜索计数共用的 JSON path 前缀，独立查看侧栏不传 */
    searchBlockId: {
      type: String,
      default: '',
    },
  },
  setup(props) {
    const data = computed(() => beautifyJsonValue(props.data));

    /** 搜索态自己拼引号，避免 HighlightText 替换掉 vue-json-pretty 默认值后丢引号 */
    const renderLeaf = (node: { content?: unknown; path?: string }, defaultValue: unknown) => {
      if (Array.isArray(node.content) || isRecord(node.content)) return defaultValue;
      const text = formatJsonDisplay(node.content);
      if (!props.searchBlockId) {
        return typeof node.content === 'string' && /[\r\n]/.test(text) ? (
          <span class='llm-json-view-text'>{text}</span>
        ) : (
          defaultValue
        );
      }
      const highlighted = (
        <HighlightText
          blockId={`${node.path}:value`}
          text={text}
        />
      );
      if (typeof node.content === 'string' && !/[\r\n]/.test(text)) {
        return (
          <>
            &quot;
            {highlighted}
            &quot;
          </>
        );
      }
      return /[\r\n]/.test(text) ? <span class='llm-json-view-text'>{highlighted}</span> : highlighted;
    };

    const isDark = computed(() => props.theme === 'dark');

    return () => (
      <div class={['llm-json-view', { 'is-dark': isDark.value }]}>
        {Array.isArray(data.value) || isRecord(data.value) ? (
          <VueJsonPretty
            renderNodeKey={({ node, defaultKey }) => {
              if (!props.searchBlockId || node.key == null || node.key === '') return defaultKey;
              return (
                <>
                  &quot;
                  <HighlightText
                    blockId={`${node.path}:key`}
                    text={String(node.key)}
                  />
                  &quot;
                </>
              );
            }}
            renderNodeValue={({ node, defaultValue }) => renderLeaf(node, defaultValue)}
            collapsedOnClickBrackets={false}
            data={data.value}
            deep={20}
            rootPath={props.searchBlockId || 'root'} // 与 collectJsonSearchTexts(rootPath) 对齐，独立查看保持默认 root
            showIcon={false}
            showKeyValueSpace={true}
            showLine={isDark.value}
            showLineNumber={props.showLineNumber}
          />
        ) : props.searchBlockId ? (
          <pre class='llm-json-view-text'>
            <HighlightText
              blockId={`${props.searchBlockId}:value`}
              text={formatJsonDisplay(data.value)}
            />
          </pre>
        ) : (
          <pre class='llm-json-view-text'>{formatJsonDisplay(data.value)}</pre>
        )}
      </div>
    );
  },
});
