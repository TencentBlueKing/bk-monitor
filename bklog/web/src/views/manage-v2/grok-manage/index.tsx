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

import { defineComponent, onBeforeUnmount, onMounted, ref, computed } from 'vue';

import { InfoBox, bkMessage } from 'bk-magic-vue';
import { debounce } from 'lodash-es';

import http from '@/api';
import { t } from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import useUtils from '@/hooks/use-utils';
import { BK_LOG_STORAGE } from '@/store/store.type';
import { tenantManager, UserInfoLoadedEventData } from '@/views/retrieve-core/tenant-manager';

import GrokDialog from './grok-dialog';
import GrokTable from './grok-table';
import { IGrokItem } from './types';

import './index.scss';

export default defineComponent({
  name: 'GrokManage',
  components: {
    GrokTable,
    GrokDialog,
  },
  setup() {
    const store = useStore();
    const { formatResponseListTimeZoneString } = useUtils();

    const searchKeyword = ref('');
    const isLoading = ref(false);
    const tableData = ref<{
      list: IGrokItem[];
      total: number;
    }>({
      list: [],
      total: 0,
    });

    // 更新人列表
    const updatedBys = ref<{ text: string; value: string }[]>([]);

    // 分页状态
    const pagination = ref({
      current: 1,
      limit: 10,
    });

    // 排序状态
    const sortParams = ref({
      ordering: '',
    });

    // 筛选状态
    const filterParams = ref<{
      is_builtin?: boolean;
      updated_by?: string;
    }>({
      is_builtin: undefined,
      updated_by: undefined,
    });

    // 是否有过滤条件
    const hasFilter = computed(() => {
      return !!(searchKeyword.value || filterParams.value.is_builtin !== undefined || filterParams.value.updated_by);
    });

    // 弹窗状态
    const dialogVisible = ref(false);
    const dialogLoading = ref(false);
    const isEditMode = ref(false);
    const editGrokData = ref<IGrokItem | null>(null);

    // 获取更新人列表
    const fetchUpdatedByList = async () => {
      try {
        const response = await http.request('grok/getUpdatedByList', {
          query: {
            bk_biz_id: store.state.storage[BK_LOG_STORAGE.BK_BIZ_ID],
          },
        });
        // 将接口返回的数据转换为过滤器所需的格式
        updatedBys.value = response.data.map((username: string) => ({
          text: username,
          value: username,
        }));
        // 批量获取用户信息，用于更新 text 为 display_name
        tenantManager.batchGetUserDisplayInfo(response.data);
      } catch (error) {
        console.warn('获取更新人列表失败:', error);
      }
    };

    // 处理用户信息更新事件
    const handleUserInfoUpdate = (data: UserInfoLoadedEventData) => {
      const userInfo = data.userInfo;

      // 更新 updatedBys 中的 text 为 display_name
      updatedBys.value = updatedBys.value.map((item) => {
        const info = userInfo.get(item.value);
        if (info && info.display_name) {
          return {
            ...item,
            text: info.display_name,
          };
        }
        return item;
      });
    };

    // 获取 Grok 列表数据
    const fetchGrokData = async () => {
      isLoading.value = true;
      try {
        const params = {
          query: {
            bk_biz_id: store.state.storage[BK_LOG_STORAGE.BK_BIZ_ID],
            page: pagination.value.current,
            pagesize: pagination.value.limit,
            ...(searchKeyword.value && { keyword: searchKeyword.value }),
            ...(sortParams.value.ordering && {
              ordering: sortParams.value.ordering,
            }),
            ...(filterParams.value.is_builtin !== undefined && {
              is_builtin: filterParams.value.is_builtin,
            }),
            ...(filterParams.value.updated_by && {
              updated_by: filterParams.value.updated_by,
            }),
          },
        };
        const response = await http.request('grok/getGrokList', params);
        const formattedList = formatResponseListTimeZoneString(response.data.list || [], {}, [
          'updated_at',
          'created_at',
        ]);
        tableData.value = {
          list: formattedList,
          total: response.data.total || 0,
        };
      } catch (error) {
        console.warn('获取 Grok 数据失败:', error);
      } finally {
        isLoading.value = false;
      }
    };

    // 防抖版本的请求数据
    const fetchGrokDataDebounced = debounce(fetchGrokData, 300);

    // 搜索处理
    const handleSearch = () => {
      pagination.value.current = 1;
      fetchGrokData();
    };

    // 分页变化处理
    const handlePageChange = (current: number) => {
      pagination.value.current = current;
      fetchGrokData();
    };

    // 分页大小变化处理
    const handlePageLimitChange = (limit: number) => {
      pagination.value.limit = limit;
      pagination.value.current = 1;
      fetchGrokData();
    };

    // 排序变化处理
    const handleSortChange = (sortData: { orderField: string; orderType: string }) => {
      const { orderField, orderType } = sortData;
      if (orderField && orderType) {
        // 转换为接口需要的格式：updated_at / -updated_at
        sortParams.value.ordering = orderType === 'descending' ? `-${orderField}` : orderField;
      } else {
        sortParams.value.ordering = '';
      }
      fetchGrokData();
    };

    // 筛选变化处理
    const handleFilterChange = (filters: { is_builtin?: boolean[]; updated_by?: string[] }) => {
      Object.keys(filters).forEach((key) => {
        filterParams.value[key] = filters[key]?.[0];
      });
      pagination.value.current = 1;
      fetchGrokDataDebounced(); // 使用防抖版本
    };

    // 新建 Grok
    const handleCreate = () => {
      isEditMode.value = false;
      editGrokData.value = null;
      dialogVisible.value = true;
    };

    // 编辑 Grok
    const handleEdit = (row: IGrokItem) => {
      isEditMode.value = true;
      editGrokData.value = row;
      dialogVisible.value = true;
    };

    // 删除 Grok
    const handleDelete = (row: IGrokItem) => {
      InfoBox({
        type: 'warning',
        subTitle: t('当前Grok名称为{n}，确认要删除？', { n: row.name }),
        confirmFn: () => requestDeleteGrok(row),
      });
    };

    // 执行删除请求
    const requestDeleteGrok = async (row: IGrokItem) => {
      try {
        await http.request('grok/deleteGrok', {
          params: { id: row.id },
        });
        bkMessage({
          theme: 'success',
          message: t('Grok 模式删除成功'),
        });
        fetchGrokData();
        fetchUpdatedByList();
      } catch (error) {
        console.warn('删除 Grok 失败:', error);
      }
    };

    // 弹窗确认
    const handleDialogConfirm = async (formData: {
      name: string;
      description: string;
      pattern: string;
      id?: number;
    }) => {
      dialogLoading.value = true;
      try {
        if (isEditMode.value && formData.id) {
          // 更新
          await http.request('grok/updateGrok', {
            params: { id: formData.id },
            data: {
              bk_biz_id: store.state.storage[BK_LOG_STORAGE.BK_BIZ_ID],
              pattern: formData.pattern,
              sample: '',
              description: formData.description,
            },
          });
          bkMessage({
            theme: 'success',
            message: t('Grok 模式更新成功'),
          });
        } else {
          // 创建
          await http.request('grok/createGrok', {
            data: {
              bk_biz_id: store.state.storage[BK_LOG_STORAGE.BK_BIZ_ID],
              name: formData.name,
              pattern: formData.pattern,
              sample: '',
              description: formData.description,
            },
          });
          bkMessage({
            theme: 'success',
            message: t('Grok 模式创建成功'),
          });
        }
        dialogVisible.value = false;
        fetchGrokData();
        fetchUpdatedByList();
      } catch (error) {
        console.warn(isEditMode.value ? '更新 Grok 失败:' : '创建 Grok 失败:', error);
      } finally {
        dialogLoading.value = false;
      }
    };

    // 弹窗取消
    const handleDialogCancel = () => {
      dialogVisible.value = false;
    };

    // 清空搜索
    const handleClearSearch = () => {
      fetchGrokDataDebounced.cancel(); // 取消防抖请求
      searchKeyword.value = '';
      handleSearch();
    };

    // 处理输入框内容改变事件
    const handleInputChange = (value: string) => {
      searchKeyword.value = value;
      setTimeout(() => {
        if (searchKeyword.value === '' && !isLoading.value) {
          handleSearch();
        }
      });
    };

    onMounted(() => {
      fetchGrokData();
      fetchUpdatedByList();

      // 监听用户信息更新事件
      tenantManager.on('userInfoUpdated', handleUserInfoUpdate);
    });

    onBeforeUnmount(() => {
      // 清理防抖函数
      fetchGrokDataDebounced.cancel();

      // 清理事件监听
      tenantManager.off('userInfoUpdated', handleUserInfoUpdate);
    });

    return () => (
      <div class='grok-manage'>
        {/* 操作区域 */}
        <div class='operating-area'>
          <div class='operating-left'>
            <bk-button
              theme='primary'
              disabled={isLoading.value}
              onClick={handleCreate}
            >
              {t('新建')}
            </bk-button>
          </div>
          <div class='operating-right'>
            <bk-input
              value={searchKeyword.value}
              placeholder={t('搜索 名称、描述、更新人、定义')}
              clearable
              right-icon='bk-icon icon-search'
              onEnter={handleSearch}
              onRight-icon-click={handleSearch}
              onClear={handleClearSearch}
              onChange={handleInputChange}
            ></bk-input>
          </div>
        </div>

        {/* 表格区域 */}
        <GrokTable
          data={tableData.value.list}
          total={tableData.value.total}
          loading={isLoading.value}
          updatedBys={updatedBys.value}
          hasFilter={hasFilter.value}
          on-page-change={handlePageChange}
          on-page-limit-change={handlePageLimitChange}
          on-sort-change={handleSortChange}
          on-filter-change={handleFilterChange}
          on-clear-keyword={handleClearSearch}
          on-edit={handleEdit}
          on-delete={handleDelete}
        />

        {/* 新建/编辑弹窗 */}
        <GrokDialog
          isShow={dialogVisible.value}
          isEdit={isEditMode.value}
          editData={editGrokData.value}
          loading={dialogLoading.value}
          on-confirm={handleDialogConfirm}
          on-cancel={handleDialogCancel}
        />
      </div>
    );
  },
});
