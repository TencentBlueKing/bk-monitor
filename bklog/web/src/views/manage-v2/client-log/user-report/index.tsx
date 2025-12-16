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

import { defineComponent, ref, onMounted, watch } from 'vue';

import { t } from '@/hooks/use-locale';
import http from '@/api';
import { BK_LOG_STORAGE } from '@/store/store.type';
import useStore from '@/hooks/use-store';
import ReportTable from './report-table';

import './index.scss';

export default defineComponent({
  name: 'UserReport',
  components: {
    ReportTable,
  },
  emits: ['update-total'],
  setup(props, { emit }) {
    const store = useStore();

    const searchKeyword = ref('');
    const isLoading = ref(false);
    const tableData = ref({
      list: [],
      total: 0,
    });

    // 分页状态
    const pagination = ref({
      current: 1,
      limit: 10,
    });

    // 获取用户上报数据
    const fetchUserReportData = async () => {
      isLoading.value = true;
      try {
        const params = {
          query: {
            bk_biz_id: store.state.storage[BK_LOG_STORAGE.BK_BIZ_ID],
            page: pagination.value.current,
            pagesize: pagination.value.limit,
            ...(searchKeyword.value && { keyword: searchKeyword.value }),
          },
        };

        const response = await http.request('collect/getUserReportList', params);
        tableData.value = {
          list: response.data.list || [],
          total: response.data.total || 0,
        };

        // 通知父组件更新 tab 中的 count
        emit('update-total', tableData.value.total);
      } catch (error) {
        console.error('获取用户上报数据失败:', error);
      } finally {
        isLoading.value = false;
      }
    };

    // 搜索处理
    const handleSearch = (keyword: string) => {
      searchKeyword.value = keyword;
      pagination.value.current = 1;
      fetchUserReportData();
    };

    // 分页变化处理
    const handlePageChange = (current: number) => {
      pagination.value.current = current;
      fetchUserReportData();
    };

    // 分页大小变化处理
    const handlePageLimitChange = (limit: number) => {
      pagination.value.limit = limit;
      pagination.value.current = 1;
      fetchUserReportData();
    };

    // 清洗配置
    const handleCleanConfig = () => {};

    // 搜索框回车事件
    const handleSearchEnter = (keyword: string) => {
      handleSearch(keyword);
    };

    // 搜索图标点击事件
    const handleSearchIconClick = (keyword: string) => {
      handleSearch(keyword);
    };

    // 清空搜索
    const handleClearSearch = () => {
      searchKeyword.value = '';
      handleSearch('');
    };

    // 监听搜索关键词变化，如果为空则自动搜索
    watch(
      () => searchKeyword.value,
      (newVal) => {
        if (!newVal) {
          handleSearch('');
        }
      },
    );

    // 监听 total 变化，通知父组件更新 tab 中的 count
    watch(
      () => tableData.value.total,
      (newTotal) => {
        emit('update-total', newTotal);
      },
    );

    onMounted(() => {
      fetchUserReportData();
    });

    return () => (
      <div class='user-report'>
        {/* Alert 提示 */}
        <bk-alert
          class='alert-info'
          type='info'
          title={t('Alert 文案占位，用于说明如果用 SDK 上报。')}
        ></bk-alert>

        {/* 操作区域 */}
        <div class='operating-area'>
          <bk-button
            onClick={handleCleanConfig}
            style={{ visibility: 'hidden' }}
          >
            {t('清洗配置')}
          </bk-button>
          <div>
            <bk-input
              value={searchKeyword.value}
              placeholder={t('搜索 任务 ID、任务名称、openID、创建方式、任务状态、任务阶段、创建人')}
              clearable
              right-icon='bk-icon icon-search'
              onEnter={handleSearchEnter}
              onRight-icon-click={handleSearchIconClick}
              onClear={handleClearSearch}
            ></bk-input>
          </div>
        </div>

        {/* 表格区域 */}
        <ReportTable
          data={tableData.value.list}
          total={tableData.value.total}
          keyword={searchKeyword.value}
          loading={isLoading.value}
          on-page-change={handlePageChange}
          on-page-limit-change={handlePageLimitChange}
          on-search={handleSearch}
        />
      </div>
    );
  },
});
