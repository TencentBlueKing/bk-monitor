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

import { defineComponent, shallowRef, watch } from 'vue';

import { type TdPrimaryTableProps, PrimaryTable } from '@blueking/tdesign-ui';
import EmptyStatus from 'trace/components/empty-status/empty-status';
import TableSkeleton from 'trace/components/skeleton/table-skeleton';

import { useTable } from './hooks/use-table';

import './log-table-new.scss';

export default defineComponent({
  name: 'LogTableNew',
  props: {
    getTableData: {
      type: Function,
      default: () => {},
    },
    getFieldsData: {
      type: Function,
      default: () => {},
    },
    refreshKey: {
      type: String,
      default: '',
    },
  },
  setup(props) {
    console.log(props);
    const loading = shallowRef(false);
    const { tableData, tableColumns, fieldsDataToColumns } = useTable();
    const offset = shallowRef(0);
    const fieldsData = shallowRef(null);
    const expandedRowKeys = shallowRef([]);

    watch(
      () => props.refreshKey,
      async val => {
        loading.value = true;
        if (val) {
          fieldsData.value = await getFieldsData();
          console.log(fieldsData.value);
          fieldsDataToColumns(fieldsData.value?.fields || []);
          const data = await getTableData();
          tableData.value = data?.list || [];
          loading.value = false;
        }
      },
      { immediate: true }
    );

    const getTableData = async () => {
      const res = await props.getTableData({
        offset: offset.value,
      });
      return res;
    };

    const getFieldsData = async () => {
      const res = await props.getFieldsData();
      return res;
    };

    const handleExpandChange = (keys: (number | string)[]) => {
      expandedRowKeys.value = keys;
    };

    const expandedRow = shallowRef<TdPrimaryTableProps['expandedRow']>((_h, { row }): any => {
      return <div class='table-expand-content'>xxxx</div>;
    });

    const expandIcon = shallowRef<TdPrimaryTableProps['expandIcon']>((_h, { _row }): any => {
      return <span class='icon-monitor icon-mc-arrow-right table-expand-icon' />;
    });

    return {
      tableData,
      tableColumns,
      loading,
      offset,
      expandedRowKeys,
      expandedRow,
      expandIcon,
      handleExpandChange,
    };
  },
  render() {
    return (
      <div class='alarm-detail-log-table-new'>
        {this.loading ? (
          <TableSkeleton />
        ) : (
          <PrimaryTable
            class='panel-log-log-table'
            columns={this.tableColumns}
            data={this.tableData}
            expandedRow={this.expandedRow}
            expandedRowKeys={this.expandedRowKeys}
            expandIcon={this.expandIcon}
            expandOnRowClick={true}
            horizontalScrollAffixedBottom={true}
            needCustomScroll={false}
            resizable={true}
            rowKey={'__id__'}
            size={'small'}
            onExpandChange={this.handleExpandChange}
          >
            {{
              empty: () => <EmptyStatus type={'empty'} />,
            }}
          </PrimaryTable>
        )}
      </div>
    );
  },
});
