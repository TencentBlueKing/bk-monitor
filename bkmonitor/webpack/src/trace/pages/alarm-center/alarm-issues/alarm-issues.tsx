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

import { computed, defineComponent, shallowRef } from 'vue';

import { commonPageSizeSet } from 'monitor-common/utils';

import { useAlarmTableColumns } from '../composables/use-table-columns';
import { IssuesService } from '../services/issues-services';
import { AlarmType, CONTENT_SCROLL_ELEMENT_CLASS_NAME } from '../typings';
import { useIssuesImpactScopeDrawer } from './components/issues-impact-scope-drawer/hooks/use-issues-impact-scope-drawer';
import IssuesImpactScopeDrawer from './components/issues-impact-scope-drawer/issues-impact-scope-drawer';
import { useIssuesDialogs } from './components/issues-operation-dialogs/hooks/use-issues-dialogs';
import IssuesOperationDialogs from './components/issues-operation-dialogs/issues-operation-dialogs';
import { IssuesBatchActionEnum } from './constant';
import { useIssuesTable } from './hooks/use-issues-table';
import IssuesTable from './issues-table/issues-table';
import IssuesToolbar from './issues-toolbar/issues-toolbar';

import type { CommonFilterParams } from '../typings/services';
import type { IssueItem } from './typing';

import './alarm-issues.scss';

export default defineComponent({
  name: 'AlarmIssues',
  setup() {
    const { tableColumns } = useAlarmTableColumns();

    /** Issues 独立 service 实例 */
    const issuesService = new IssuesService(AlarmType.ISSUES);

    /** 公共筛选参数占位（后续替换） */
    const commonFilterParams = computed<Partial<CommonFilterParams>>(() => ({}));

    const { data, loading, total, page, pageSize, ordering } = useIssuesTable({
      service: issuesService,
      filterParams: commonFilterParams,
    });

    /** table 选中的 rowKey 数组 */
    const selectedRowKeys = shallowRef<string[]>([]);

    const {
      issuesDialogShow,
      issuesDialogType,
      issuesDialogData,
      issuesDialogParam,
      handleIssuesDialogShow,
      handleIssuesDialogHide,
      handleIssuesDialogSuccess,
    } = useIssuesDialogs(data);

    const { impactScopeDrawerShow, impactScopeResourceKey, impactScopeResource, handleImpactScopeClick } =
      useIssuesImpactScopeDrawer();

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

    /**
     * @description 表格 -- 处理分页变化
     * @param {number} currentPage 当前页码
     */
    const handleCurrentPageChange = (currentPage: number) => {
      page.value = currentPage;
    };

    /**
     * @description 表格 -- 处理分页大小变化
     * @param {number} size 分页大小
     */
    const handlePageSizeChange = (size: number) => {
      pageSize.value = size;
      commonPageSizeSet(size);
      handleCurrentPageChange(1);
    };

    /**
     * @description 表格 -- 处理排序变化
     * @param {string} sort 排序字段
     */
    const handleSortChange = (sort: string) => {
      ordering.value = sort;
      handleCurrentPageChange(1);
    };

    /**
     * @description 表格 -- 处理选中行变化
     * @param {string[]} keys 选中行 key 数组
     */
    const handleSelectionChange = (keys?: string[]) => {
      selectedRowKeys.value = keys ?? [];
    };

    // ===================== 渲染 =====================

    return () => (
      <div class='alarm-issues'>
        <IssuesToolbar
          batchAction={action => handleIssuesDialogShow(action, selectedRowKeys.value)}
          issuesIds={selectedRowKeys.value}
        >
          <IssuesTable
            pagination={{
              currentPage: page.value,
              pageSize: pageSize.value,
              total: total.value,
            }}
            columns={tableColumns.value}
            data={data.value}
            loading={loading.value}
            scrollContainerSelector={`.${CONTENT_SCROLL_ELEMENT_CLASS_NAME}`}
            selectedRowKeys={selectedRowKeys.value}
            sort={ordering.value}
            onAssignClick={handleAssignClick}
            onCurrentPageChange={handleCurrentPageChange}
            onImpactScopeClick={handleImpactScopeClick}
            onMarkResolved={(id: string) => handleIssuesDialogShow(IssuesBatchActionEnum.RESOLVE, id)}
            onPageSizeChange={handlePageSizeChange}
            onPriorityChange={(id: string) => handleIssuesDialogShow(IssuesBatchActionEnum.PRIORITY, id)}
            onSelectionChange={handleSelectionChange}
            onShowDetail={handleShowDetail}
            onSortChange={sort => handleSortChange(sort as string)}
          />
        </IssuesToolbar>

        <IssuesOperationDialogs
          dialogParam={issuesDialogParam.value}
          dialogType={issuesDialogType.value}
          issuesData={issuesDialogData.value}
          show={issuesDialogShow.value}
          onSuccess={handleIssuesDialogSuccess}
          onUpdate:show={(v: boolean) => {
            if (!v) {
              handleIssuesDialogHide();
            }
          }}
        />

        <IssuesImpactScopeDrawer
          resource={impactScopeResource.value}
          resourceKey={impactScopeResourceKey.value}
          show={impactScopeDrawerShow.value}
          onUpdate:show={(v: boolean) => {
            if (v) return;
            handleImpactScopeClick();
          }}
        />
      </div>
    );
  },
});
