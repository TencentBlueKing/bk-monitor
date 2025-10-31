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

import { type PropType, defineComponent, shallowRef } from 'vue';

import { type TdPrimaryTableProps, PrimaryTable } from '@blueking/tdesign-ui';

import './link-table.scss';

export default defineComponent({
  name: 'LinkTable',
  props: {
    id: String as PropType<string>,
  },
  setup(props) {
    console.log(props.id);

    const columns = shallowRef<TdPrimaryTableProps['columns']>([
      {
        colKey: 'trace_id',
        title: 'Trace',
        width: 173,
        className: 'cell-trace-id',
        ellipsis: {
          theme: 'light',
          placement: 'bottom',
        },
        cell: (_h, { row }) => {
          return (
            <span class='link'>
              {'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'}
              {row.id}
            </span>
          ) as any;
        },
      },
      {
        colKey: 'start_time',
        title: '开始时间',
        width: 145,
        cell: (_h, { row }) => {
          return row.start_time as any;
        },
      },
      {
        colKey: 'span_id',
        title: '根span',
        width: 100,
        cell: _h => {
          return (<span class='link'>{'xxxxxxxxspan'}</span>) as any;
        },
      },
      {
        colKey: 'service',
        title: '入口服务',
        width: 100,
        ellipsis: {
          theme: 'light',
          placement: 'bottom',
        },
        cell: (_h, { row }) => {
          return (
            <span class='service-wrap'>
              <span class='service-status'>
                <span class='icon-monitor icon-mind-fill' />
              </span>
              <span class='link'>bkbkbkbkbkbkbk</span>
            </span>
          ) as any;
        },
      },
      {
        colKey: 'interface',
        title: '入口接口',
        width: 100,
        ellipsis: {
          theme: 'light',
          placement: 'bottom',
        },
        cell: (_h, { row }) => {
          return (<span class='link'>{'/api/v1/xxxx/xxxx'}</span>) as any;
        },
      },
      {
        colKey: 'error',
        title: '错误信息',
        ellipsis: {
          theme: 'light',
          placement: 'bottom',
        },
        cell: (_h, { row }) => {
          return (
            <span class='err-info'>
              {'错误信息错误信息错误信息错误信息错误信息错误信息错误信息错误信息错误信息错误信息错误信息'}
            </span>
          ) as any;
        },
      },
    ]);
    const tableData = shallowRef<TdPrimaryTableProps['data']>([
      { id: '1', name: 'link1', start_time: '2023-01-01 00:00:00' },
      { id: '2', name: 'link2', start_time: '2023-01-01 00:00:00' },
      { id: '3', name: 'link3', start_time: '2023-01-01 00:00:00' },
    ]);

    return {
      columns,
      tableData,
    };
  },
  render() {
    return (
      <PrimaryTable
        class='alarm-center-detail-panel-link-table'
        columns={this.columns}
        data={this.tableData}
        size={'small'}
      />
    );
  },
});
