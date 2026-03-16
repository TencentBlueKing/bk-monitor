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

import { defineComponent } from 'vue';

import { useIssuesOperations } from '../composables/use-issues-operations';
import { useIssuesTable } from '../composables/use-issues-table';
import IssuesTable from './issues-table/issues-table';

import './alarm-issues.scss';

export default defineComponent({
  name: 'AlarmIssues',
  setup() {
    // ===================== 表格数据管理 =====================

    const {
      allData,
      tableData,
      pagination,
      sort,
      selectedRowKeys,
      loading,
      handleCurrentPageChange,
      handlePageSizeChange,
      handleSortChange,
      handleSelectionChange,
    } = useIssuesTable();

    // ===================== 业务操作 =====================

    const { handleAssign, handleMarkResolved, handlePriorityChange, handleShowDetail } = useIssuesOperations({
      allData,
    });

    // ===================== 渲染 =====================

    return () => (
      <div class='alarm-issues'>
        <IssuesTable
          data={tableData.value}
          loading={loading.value}
          pagination={pagination.value}
          selectedRowKeys={selectedRowKeys.value}
          sort={sort.value}
          onAssign={handleAssign}
          onCurrentPageChange={handleCurrentPageChange}
          onMarkResolved={handleMarkResolved}
          onPageSizeChange={handlePageSizeChange}
          onPriorityChange={handlePriorityChange}
          onSelectionChange={handleSelectionChange}
          onShowDetail={handleShowDetail}
          onSortChange={handleSortChange}
        />
      </div>
    );
  },
});
