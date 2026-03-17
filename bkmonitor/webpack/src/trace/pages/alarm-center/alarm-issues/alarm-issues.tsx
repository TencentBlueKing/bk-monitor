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

import { useIssuesOperations } from '../composables/use-issues-operations';
import { useIssuesTable } from '../composables/use-issues-table';
import { useAlarmTableColumns } from '../composables/use-table-columns';
import { CONTENT_SCROLL_ELEMENT_CLASS_NAME } from '../typings';
import IssuesAssignDialog from './components/issues-assign-dialog/issues-assign-dialog';
import IssuesTable from './issues-table/issues-table';
import IssuesToolbar from './issues-toolbar/issues-toolbar';

import type { IssueItem } from './typing';

import './alarm-issues.scss';

export default defineComponent({
  name: 'AlarmIssues',
  setup() {
    const { tableColumns } = useAlarmTableColumns();

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

    // ===================== 指派弹窗状态 =====================

    /** 指派弹窗是否可见 */
    const assignDialogVisible = shallowRef(false);
    /** 当前指派目标 Issue */
    const assignTarget = shallowRef<IssueItem | null>(null);

    /**
     * @description 表格点击指派按钮，打开指派弹窗
     * @param _id - Issue ID
     * @param data - 当前 Issue 行数据
     */
    const handleAssignClick = (_id: IssueItem['id'], data: IssueItem) => {
      assignTarget.value = data;
      assignDialogVisible.value = true;
    };

    /**
     * @description 确认指派负责人
     * @param assignee - 负责人列表
     */
    const handleAssignConfirm = (assignee: string[]) => {
      if (!assignTarget.value) return;
      handleAssign(assignTarget.value.id, assignee);
      assignDialogVisible.value = false;
      assignTarget.value = null;
    };

    /**
     * @description 取消指派
     */
    const handleAssignCancel = () => {
      assignDialogVisible.value = false;
      assignTarget.value = null;
    };

    // ===================== 渲染 =====================

    return () => (
      <div class='alarm-issues'>
        <IssuesToolbar selectedRowKeys={selectedRowKeys.value}>
          <IssuesTable
            columns={tableColumns.value}
            data={tableData.value}
            loading={loading.value}
            pagination={pagination.value}
            scrollContainerSelector={`.${CONTENT_SCROLL_ELEMENT_CLASS_NAME}`}
            selectedRowKeys={selectedRowKeys.value}
            sort={sort.value}
            onAssignClick={handleAssignClick}
            onCurrentPageChange={handleCurrentPageChange}
            onMarkResolved={handleMarkResolved}
            onPageSizeChange={handlePageSizeChange}
            onPriorityChange={handlePriorityChange}
            onSelectionChange={handleSelectionChange}
            onShowDetail={handleShowDetail}
            onSortChange={handleSortChange}
          />
        </IssuesToolbar>

        <IssuesAssignDialog
          isShow={assignDialogVisible.value}
          onCancel={handleAssignCancel}
          onConfirm={handleAssignConfirm}
          onUpdate:isShow={(v: boolean) => {
            assignDialogVisible.value = v;
          }}
        />
      </div>
    );
  },
});
