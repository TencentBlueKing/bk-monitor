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

import { type TableProps, PrimaryTable } from '@blueking/tdesign-ui';
import { useI18n } from 'vue-i18n';

import { TraceCellSkeleton } from '@/pages/trace-explore/components/trace-explore-skeleton';

// 骨架屏复用采集配置详情的结构类名，因此显式引入其样式
import './collection-configuration.scss';

const skeletonRows = Array.from({ length: 8 }, (_, index) => ({ id: index }));

export default defineComponent({
  name: 'CollectionExecutionSkeleton',
  props: {
    columns: { type: Array as PropType<TableProps['columns']>, required: true },
    snapshot: { type: Boolean, default: false },
  },
  setup() {
    return { t: useI18n().t };
  },
  render() {
    if (this.snapshot) {
      return (
        <div
          class='collection-config-body collection-execution-skeleton'
          aria-busy='true'
        >
          {[
            { title: '任务信息', rows: 2 },
            { title: '采集配置', rows: 6 },
            { title: '执行计划', rows: 3 },
          ].map(section => (
            <section key={section.title}>
              <h3>{this.t(section.title)}</h3>
              <dl>
                {Array.from({ length: section.rows }, (_, index) => (
                  <div
                    key={index}
                    class='collection-config-row'
                  >
                    <dt>
                      <i class='collection-execution-placeholder' />
                    </dt>
                    <dd>
                      <i
                        style={{ width: `${[48, 72, 32][index % 3]}%` }}
                        class='collection-execution-placeholder'
                      />
                    </dd>
                  </div>
                ))}
              </dl>
            </section>
          ))}
        </div>
      );
    }
    return (
      <div
        class='collection-execution-content collection-execution-skeleton'
        aria-busy='true'
      >
        <dl class='collection-execution-summary'>
          {['执行时间', '采集配置', '实际引擎'].map((label, index) => (
            <div key={label}>
              <dt>{this.t(label)}：</dt>
              <dd>
                <i
                  style={{ width: `${[64, 42, 32][index]}%` }}
                  class='collection-execution-placeholder'
                />
              </dd>
            </div>
          ))}
        </dl>
        <div
          class='collection-execution-toolbar'
          aria-hidden='true'
        >
          <i class='collection-execution-placeholder skeleton-retry' />
          <i class='collection-execution-placeholder collection-execution-counts' />
          <i class='collection-execution-placeholder collection-execution-search' />
        </div>
        <PrimaryTable
          columns={this.columns.map(column => ({
            ...column,
            sorter: false,
            cell: (render, { rowIndex }) => render(TraceCellSkeleton, { field: column.colKey, index: rowIndex }),
          }))}
          data={skeletonRows}
          hover={false}
          rowKey='id'
          size='small'
        />
      </div>
    );
  },
});
