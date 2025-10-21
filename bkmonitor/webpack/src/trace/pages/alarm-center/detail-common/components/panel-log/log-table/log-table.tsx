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

import { defineComponent, shallowRef } from 'vue';

import { type TdPrimaryTableProps, PrimaryTable } from '@blueking/tdesign-ui';
import { useI18n } from 'vue-i18n';
import JsonPretty from 'vue-json-pretty';

import './log-table.scss';
import 'vue-json-pretty/lib/styles.css';
export default defineComponent({
  name: 'LogTable',
  setup() {
    const { t } = useI18n();

    const columns = shallowRef([
      {
        colKey: 'date',
        title: '时间',
        width: 200,
      },
      {
        colKey: 'log',
        title: '日志内容',
      },
    ]);
    const data = shallowRef([
      {
        date: '2025-10-21 15:00:29',
        source: {
          __ext: {
            host: {
              bk_cpu_module: 'fasdfasdfasdfasdfasdfasdf',
              bk_os_bit: '64-bit',
              bk_os_name: 'linux centos',
              bk_os_version: '7.8.2003000',
            },
          },
          path: '/tmp/bkccc.log',
          cloudId: 0,
          time: '1761033089000',
          log: 'asdfasdfasdfasdfasdfasdfasdfasdfasdfasdfas',
          serverIp: '10.0.60.30006',
          dtEventTimeStamp: '1761033089000',
          iterationIndex: 0,
          bk_host_id: 3139,
          gseIndex: 48711119,
        },
        log: "{'__ext': {'host': {'bk_cpu_module': 'Aasdfasdfasdf', 'bk_os_bit': '64-bit', 'bk_os_name': 'linux centos', 'bk_os_version': '7.8.0000'}}, 'path': '/tmp/bkc.log', 'cloudId': 0, 'time': '1761033089000', 'log': '20251021-155127 INFsdfO|75|loasdfasdf-agent ...', 'serverIp': '10.0.6.36', 'dtEventTimeStamp': '1761033089000', 'iterationIndex': 0, 'bk_host_id': 300039, 'gseIndex': 487100019}",
      },
    ]);
    const expandedRowKeys = shallowRef([]);
    const expandedRow = shallowRef<TdPrimaryTableProps['expandedRow']>((_h, { row }): any => {
      return (
        <div>
          <JsonPretty data={row.source} />
        </div>
      );
    });
    const expandIcon = shallowRef<TdPrimaryTableProps['expandIcon']>((_h, { row }): any => {
      return <div>{'>'}</div>;
    });

    function handleExpandChange(keys: (number | string)[]) {
      console.log(keys);
      expandedRowKeys.value = keys;
    }

    return {
      columns,
      data,
      expandedRowKeys,
      expandIcon,
      expandedRow,
      t,
      handleExpandChange,
    };
  },
  render() {
    return (
      <PrimaryTable
        class='panel-log-log-table'
        columns={this.columns}
        data={this.data}
        expandedRow={this.expandedRow}
        expandedRowKeys={this.expandedRowKeys}
        expandIcon={this.expandIcon}
        expandOnRowClick={true}
        rowKey={'date'}
        onExpandChange={this.handleExpandChange}
      />
    );
  },
});
