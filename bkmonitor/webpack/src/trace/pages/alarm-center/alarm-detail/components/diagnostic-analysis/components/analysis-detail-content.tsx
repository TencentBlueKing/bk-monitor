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
import { type PropType, defineComponent } from 'vue';

import type { IContentItem, ITableItem } from '../typing';

import './analysis-detail-content.scss';

export default defineComponent({
  name: 'AnalysisDetailContent',
  props: {
    tableData: {
      type: Array as PropType<ITableItem[]>,
      default: () => [],
    },
    contentData: {
      type: Array as PropType<IContentItem[]>,
      default: () => [],
    },
  },
  setup() {
    return {};
  },
  render() {
    return (
      <div class='analysis-detail-content'>
        {this.tableData.length > 0 && (
          <div class='detail-table'>
            {this.tableData.map((item, index) => (
              <div
                key={item.name}
                class={['detail-table-item', { even: index % 2 === 0 }]}
              >
                <div class='detail-table-name'>{item.name}</div>
                <div class='detail-table-value'>{item.value}</div>
              </div>
            ))}
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
