/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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
import { type PropType, defineComponent } from 'vue';

import type { IContentItem, IPatternBlock, ITableItem } from '../typing';

import './analysis-detail-content.scss';

function formatBlockValue(value: string, kind?: IPatternBlock['kind']) {
  if (kind !== 'json') return value;
  try {
    return JSON.stringify(JSON.parse(value), null, 2);
  } catch {
    return value;
  }
}

export default defineComponent({
  name: 'AnalysisDetailContent',
  props: {
    tableData: {
      type: Array as PropType<ITableItem[]>,
      default: () => [],
    },
    tableTitle: {
      type: String,
      default: '',
    },
    contentData: {
      type: Array as PropType<IContentItem[]>,
      default: () => [],
    },
    blocks: {
      type: Array as PropType<IPatternBlock[]>,
      default: () => [],
    },
    /** 引用归类名（板块名），明细项 hover「添加至聊天」时带上 */
    chatCategory: {
      type: String,
      default: '',
    },
  },
  render() {
    return (
      <div class='analysis-detail-content'>
        {this.blocks.length > 0 && (
          <div class='detail-pattern-blocks'>
            {this.blocks.map(item => (
              <div
                key={item.title}
                class='pattern-block'
              >
                <div class='pattern-block-title'>
                  <span>{item.title}</span>
                </div>
                <div
                  class={['pattern-block-value', { 'is-json': item.kind === 'json' }]}
                  data-chat-category={this.chatCategory}
                  data-chat-label={String(item.title).replace(/[:：]$/, '')}
                  data-chat-text={item.value}
                >
                  {formatBlockValue(item.value, item.kind)}
                </div>
              </div>
            ))}
          </div>
        )}
        {(this.tableTitle || this.tableData.length > 0) && (
          <div class='detail-table-wrap'>
            {this.tableTitle ? <div class='detail-table-title'>{this.tableTitle}</div> : undefined}
            {this.tableData.length > 0 && (
              <div class='detail-table'>
                {this.tableData.map((item, index) => (
                  <div
                    key={item.name}
                    class={['detail-table-item', { even: index % 2 === 1 }]}
                  >
                    <div class='detail-table-name'>{item.name}</div>
                    <div
                      class='detail-table-value'
                      data-chat-category={this.chatCategory}
                      data-chat-label={item.name}
                      data-chat-text={item.value}
                    >
                      {item.value}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
        {this.contentData.length > 0 && (
          <div class='detail-text-content'>
            {this.contentData.map(item => (
              <div
                key={item.title}
                class='detail-text-item'
              >
                <div class='detail-text-item-name'>{item.title}</div>
                {item.value.map((value, idx) => (
                  <div
                    key={`${item.title}-${idx}`}
                    class='detail-text-item-value'
                  >
                    {value}
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>
    );
  },
});
