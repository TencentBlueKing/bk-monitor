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

import { type TdPrimaryTableProps, PrimaryTable } from '@blueking/tdesign-ui';
import { useI18n } from 'vue-i18n';

import './notice-status-table.scss';

interface ITableColumn {
  label?: string;
  prop?: string;
}

interface ITableData {
  label?: string;
  target?: string;
  tip?: string;
}

export default defineComponent({
  name: 'NoticeStatusTable',
  props: {
    tableData: {
      type: Array as PropType<ITableData[]>,
      default: () => [],
    },
    tableColumns: {
      type: Array as PropType<ITableColumn[]>,
      default: () => [],
    },
    hasColumns: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
  },
  emits: {},
  setup(props, { emit }) {
    const { t } = useI18n();
    const classMap = {
      失败: 'failed',
      成功: 'success',
    };

    const columns = computed<TdPrimaryTableProps['columns']>(() => {
      const showColumns = props.tableColumns.filter(item => props.hasColumns.includes(item.prop));
      const columns = showColumns.map((item, i) => ({
        colKey: item.prop,
        title: item.label,
        align: 'center',
        cell: (_h, { row }) => (
          <div class='cell'>
            {!Object.keys(classMap).includes(row?.[item.prop]?.label) ? (
              <span
                v-bk-tooltips={{
                  extCls: 'notice-status-tooltips-w200',
                  content: Array.isArray(row[item.prop]?.tip) ? row[item.prop]?.tip.join(',') : row[item.prop]?.tip,
                  placements: ['top'],
                  disabled: !row[item.prop]?.tip,
                }}
              >
                {row?.[item.prop]?.label || '--'}
              </span>
            ) : (
              <span
                class={`notice-${classMap[row[item.prop].label]}`}
                v-bk-tooltips={{
                  allowHtml: false,
                  html: false,
                  allowHTML: false,
                  width: 200,
                  extCls: 'notice-status-tooltips-w200',
                  content: Array.isArray(row[item.prop]?.tip) ? row[item.prop]?.tip.join(',') : row[item.prop]?.tip,
                  placements: ['top'],
                  disabled: !row[item.prop]?.tip,
                }}
              />
            )}
          </div>
        ),
      }));
      return [
        {
          colKey: 'target',
          title: t('通知对象'),
          cell: (_h, { row }) => (
            <div class='cell'>{row.target ? <bk-user-display-name user-id={row.target} /> : '--'}</div>
          ),
        },
        ...columns,
      ];
    });

    return {
      columns,
    };
  },
  render() {
    return (
      <div class='trace-notice-status-table'>
        <PrimaryTable
          bordered={false}
          columns={this.columns}
          data={this.tableData}
        />
      </div>
    );
  },
});
