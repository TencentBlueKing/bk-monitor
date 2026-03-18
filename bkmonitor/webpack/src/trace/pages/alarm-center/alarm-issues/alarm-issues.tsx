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

import { useIssuesTable } from '../composables/use-issues-table';
import { useAlarmTableColumns } from '../composables/use-table-columns';
import { CONTENT_SCROLL_ELEMENT_CLASS_NAME } from '../typings';
import { useIssuesDialogs } from './components/issues-operation-dialogs/hooks/use-issues-dialogs';
import IssuesOperationDialogs from './components/issues-operation-dialogs/issues-operation-dialogs';
import { IssuesBatchActionEnum } from './constant';
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

    const {
      issuesDialogShow,
      issuesDialogType,
      issuesDialogIds,
      issuesDialogBizId,
      issuesDialogParam,
      handleIssuesDialogShow,
      handleIssuesDialogHide,
      handleIssuesDialogSuccess,
    } = useIssuesDialogs(allData);

    /**
     * @description 展示 Issue 详情
     * @param {IssueItem['id']} _id - Issue ID
     */
    const handleShowDetail = (_id: IssueItem['id']) => {
      // TODO: 接入详情抽屉逻辑
    };

    /**
     * @description 表格点击指派按钮，打开指派弹窗（单条操作）
     * @param {IssueItem['id']} id - Issue ID
     * @param {IssueItem} data - 当前 Issue 行数据
     */
    const handleAssignClick = (id: IssueItem['id'], data: IssueItem) => {
      handleIssuesDialogShow(IssuesBatchActionEnum.ASSIGN, id, data);
    };

    // ===================== 渲染 =====================

    return () => (
      <div class='alarm-issues'>
        <IssuesToolbar
          batchAction={action => handleIssuesDialogShow(action, selectedRowKeys.value)}
          issuesIds={selectedRowKeys.value}
        >
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
            onMarkResolved={(id: string) => handleIssuesDialogShow(IssuesBatchActionEnum.RESOLVE, id)}
            onPageSizeChange={handlePageSizeChange}
            onPriorityChange={(id: string) => handleIssuesDialogShow(IssuesBatchActionEnum.PRIORITY, id)}
            onSelectionChange={handleSelectionChange}
            onShowDetail={handleShowDetail}
            onSortChange={handleSortChange}
          />
        </IssuesToolbar>

        <IssuesOperationDialogs
          dialogParam={issuesDialogParam.value}
          dialogType={issuesDialogType.value}
          issuesBizId={issuesDialogBizId.value}
          issuesIds={issuesDialogIds.value}
          show={issuesDialogShow.value}
          onSuccess={handleIssuesDialogSuccess}
          onUpdate:show={(v: boolean) => {
            if (!v) {
              handleIssuesDialogHide();
            }
          }}
        />
      </div>
    );
  },
});
