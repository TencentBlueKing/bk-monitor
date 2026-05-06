/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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

import { defineComponent, ref } from 'vue';

import SearchBar from './search-bar';
import UserInfoCard from './user-info-card';
import TaskListPanel from './task-list-panel';
import LogDetailPanel from './log-detail-panel';
import type { SearchParams, LogItem, UserReportStats } from './types';

import './index.scss';

/** 左侧任务面板展开宽度 */
const TASK_PANEL_WIDTH = 360;

export default defineComponent({
  name: 'ClientLogSearch',
  components: {
    SearchBar,
    UserInfoCard,
    TaskListPanel,
    LogDetailPanel,
  },
  setup() {
    /** 是否收起左侧任务列表面板 */
    const isTaskListCollapsed = ref(false);

    /** 当前选中的日志条目 */
    const selectedLogItem = ref<LogItem | null>(null);

    /** 当前用户累计上报统计 */
    const userReportStats = ref<UserReportStats | null>(null);

    /**
     * 搜索回调
     */
    const handleSearch = (params: SearchParams) => {
    };

    /** 切换任务列表收起状态 */
    const handleToggleTaskList = (collapsed: boolean) => {
      isTaskListCollapsed.value = collapsed;
    };

    /** 展开任务列表（从 LogDetailPanel 触发） */
    const handleExpandTaskList = () => {
      isTaskListCollapsed.value = false;
    };

    /** 点击日志条目 */
    const handleLogItemSelect = (item: LogItem) => {
      selectedLogItem.value = item;
    };

    return () => (
      <div class='client-log-search-root'>
        {/* 搜索区域 */}
        <SearchBar on-search={handleSearch} />

        {/* 用户信息展示区域 */}
        <UserInfoCard userInfo={selectedLogItem.value} userReportStats={userReportStats.value} />

        {/* 任务内容区域 */}
        <div class='task-content-area'>
          {/* 左侧：任务列表 */}
          <TaskListPanel
            collapsed={isTaskListCollapsed.value}
            on-toggle={handleToggleTaskList}
            on-log-item-select={handleLogItemSelect}
          />

          {/* 右侧：日志详情 */}
          <LogDetailPanel
            isTaskListCollapsed={isTaskListCollapsed.value}
            selectedLogItem={selectedLogItem.value}
            on-expand={handleExpandTaskList}
          />
        </div>
      </div>
    );
  },
});
