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

import { computed, defineComponent, ref, watch } from 'vue';

import { clearTableFilter } from '@/common/util';
import EmptyStatus from '@/components/empty-status/index.vue';

import { t } from '@/hooks/use-locale';

import './index.scss';

export default defineComponent({
  name: 'LogTable',
  components: {
    EmptyStatus,
  },
  props: {
    keyword: {
      type: String,
      default: '',
    },
    total: {
      type: Number,
      default: 0,
    },
    data: {
      type: Array,
      default: () => [],
    },
  },
  emits: ['clear-keyword'],
  setup(props, { emit }) {
    const pagination = ref({
      current: 1,
      count: props.total,
      limit: 10,
      limitList: [10, 20, 50, 100],
    });

    const createTypes = ref([]); // 创建方式
    const createdBys = ref([]); // 创建人
    const logTableRef = ref(null); // 表格引用

    // 任务状态选项
    const taskStatuses = [
      { text: t('待审批'), value: -3 },
      { text: t('审批通过'), value: -2 },
      { text: t('审批拒绝'), value: -1 },
      { text: t('已创建'), value: 0 },
      { text: t('执行中'), value: 1 },
      { text: t('停止'), value: 2 },
      { text: t('执行失败'), value: 3 },
      { text: t('执行完成'), value: 4 },
      { text: t('创建失败'), value: 5 },
      { text: t('认领超时'), value: 6 },
      { text: t('执行超时'), value: 7 },
      { text: t('认领中'), value: 8 },
      { text: t('已删除'), value: 9 },
      { text: t('创建中'), value: 10 },
      { text: t('启动中'), value: 11 },
    ];

    // 任务阶段选项
    const taskScenes = [
      { text: t('登录后'), value: 4 },
      { text: t('登录前'), value: 1 },
    ];

    // 当前筛选条件
    const filterParams = ref({
      create_type: [],
      status: [],
      scene: [],
      created_by: [],
    });

    // 从日志数据中提取去重数据
    const extractUniqueData = () => {
      if (!props.data || props.data.length === 0) {
        return;
      }

      // 提取创建方式
      const types = [...new Set(props.data.map(item => item.create_type))].filter(Boolean);
      createTypes.value = types.map(type => ({ text: type, value: type }));

      // 提取创建人
      const creators = [...new Set(props.data.map(item => item.created_by))].filter(Boolean);
      createdBys.value = creators.map(creator => ({ text: creator, value: creator }));
    };

    // 监听data变化，更新提取的数据
    watch(
      () => props.data,
      () => {
        extractUniqueData();
      },
    );

    watch(
      () => props.total,
      (newTotal) => {
        pagination.value.count = newTotal;
      },
    );

    // 关键词搜索后重置分页
    watch(
      () => props.keyword,
      () => {
        pagination.value.current = 1;
      },
    );

    // 添加分页变化事件处理函数
    const handlePageChange = (current: number) => {
      pagination.value.current = current;
    };

    // 添加分页限制变化事件处理函数
    const handlePageLimitChange = (limit: number) => {
      pagination.value.limit = limit;
      pagination.value.current = 1;
    };

    // 根据过滤参数过滤日志列表
    const filterByParams = (list, params) => {
      return list.filter((item) => {
        return Object.keys(params).every((key) => {
          const paramValue = params[key];
          if (filterIsNotCompared(paramValue)) {
            return true;
          }
          return item[key].toString() === paramValue;
        });
      });
    };

    // 显示的日志列表
    const logShowList = computed(() => {
      let logList = props.data;

      if (isFilterSearch.value) {
        logList = filterByParams(logList, filterParams.value);
      }

      // 关键词搜索
      if (props.keyword) {
        const keywordLower = props.keyword.trim().toLowerCase();
        logList = logList.filter((item) => {
          const searchFields = [
            item.id?.toString() || '',
            item.task_name || '',
            item.openid || '',
            item.create_type || '',
            item.status_name || '',
            item.scene_name || '',
            item.created_by || '',
          ];

          return searchFields.some(field => field.toLowerCase().includes(keywordLower));
        });
      }

      changePagination({ count: logList.length });

      const { current, limit } = pagination.value;
      const startIndex = (current - 1) * limit;
      const endIndex = current * limit;
      return logList.slice(startIndex, endIndex);
    });

    // 空状态类型计算属性
    const emptyType = computed(() => {
      return props.keyword || isFilterSearch.value ? 'search-empty' : 'empty';
    });

    // 是否筛选搜索
    const isFilterSearch = computed(() => {
      return !!Object.values(filterParams.value).some(item => !filterIsNotCompared(item));
    });

    // 过滤器变化事件处理函数
    const handleFilterChange = (filters: any) => {
      // 更新当前过滤条件
      Object.keys(filters).forEach((key) => {
        filterParams.value[key] = filters[key].join('');
      });
      handlePageChange(1);
    };

    // 过滤条件是否为空
    const filterIsNotCompared = (val) => {
      if (typeof val === 'string' && val === '') return true;
      if (typeof val === 'object' && JSON.stringify(val) === '{}') return true;
      if (Array.isArray(val) && !val.length) return true;
      return false;
    };

    // 更新分页信息
    const changePagination = (paginationValue = {}) => {
      Object.assign(pagination.value, paginationValue);
    };

    // 清空过滤条件
    const clearFilters = () => {
      clearTableFilter(logTableRef.value);
      emit('clear-keyword');
    };

    // 任务名称插槽
    const nameSlot = {
      default: ({ row }) => (
        <bk-button
          class='king-button'
          text
          theme='primary'
        >
          {row.task_name}
        </bk-button>
      ),
    };

    // 任务状态插槽
    const statusSlot = {
      default: ({ row }) => (
        <div class='status-row'>
          <div class='status-icon'>
            {row.status === 8 && <bk-spin size='mini'></bk-spin>}
            {row.status === 6 && <div class='claimed-expired'></div>}
          </div>

          {row.status_name}
        </div>
      ),
    };

    // 操作项插槽
    const operateSlot = {
      // eslint-disable-next-line no-empty-pattern
      default: ({}: any) => (
        <div class='log-table-operate'>
          <bk-button
            class='king-button'
            text
            theme='primary'
          >
            {t('克隆')}
          </bk-button>
          <bk-button
            class='king-button'
            text
            theme='primary'
            disabled
          >
            {t('下载文件')}
          </bk-button>
        </div>
      ),
    };

    // 空状态插槽
    const emptySlot = {
      empty: () => (
        <div>
          <EmptyStatus
            emptyType={emptyType.value}
            on-operation={clearFilters}
          />
        </div>
      ),
    };

    return () => (
      <div class='log-table'>
        <bk-table
          data={logShowList.value}
          pagination={pagination.value}
          outer-border={false}
          ref={logTableRef}
          onPage-change={handlePageChange}
          onPage-limit-change={handlePageLimitChange}
          onFilter-change={handleFilterChange}
          scopedSlots={emptySlot}
        >
          <bk-table-column
            class-name='filter-column'
            label={t('任务 ID')}
            prop='id'
            sortable
          ></bk-table-column>
          <bk-table-column
            class-name='filter-column'
            label={t('任务名称')}
            prop='task_name'
            scopedSlots={nameSlot}
            sortable
          ></bk-table-column>
          <bk-table-column
            class-name='filter-column'
            label='openid'
            prop='openid'
            sortable
          ></bk-table-column>
          <bk-table-column
            class-name='filter-column'
            label={t('创建方式')}
            prop='create_type'
            column-key='create_type'
            filters={createTypes}
            filter-multiple={false}
          ></bk-table-column>
          <bk-table-column
            class-name='filter-column'
            label={t('任务状态')}
            prop='status_name'
            column-key='status'
            filters={taskStatuses}
            filter-multiple={false}
            scopedSlots={statusSlot}
          ></bk-table-column>
          <bk-table-column
            class-name='filter-column'
            label={t('任务阶段')}
            prop='scene_name'
            column-key='scene'
            filters={taskScenes}
            filter-multiple={false}
          ></bk-table-column>
          <bk-table-column
            class-name='filter-column'
            label={t('创建人')}
            prop='created_by'
            column-key='created_by'
            filters={createdBys}
            filter-multiple={false}
          ></bk-table-column>
          <bk-table-column
            class-name='filter-column'
            label={t('创建时间')}
            prop='created_at'
            sortable
          ></bk-table-column>
          <bk-table-column
            label={t('操作')}
            scopedSlots={operateSlot}
          ></bk-table-column>
          <bk-table-column type='setting'></bk-table-column>
        </bk-table>
      </div>
    );
  },
});
