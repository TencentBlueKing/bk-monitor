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
import { useTableSetting } from '../hooks/use-table-setting';

import { IGrokItem } from './types';

import './grok-table.scss';

export default defineComponent({
  name: 'GrokTable',
  components: {
    EmptyStatus,
  },
  props: {
    data: {
      type: Array as () => IGrokItem[],
      default: () => [],
    },
    total: {
      type: Number,
      default: 0,
    },
    loading: {
      type: Boolean,
      default: false,
    },
    updatedBys: {
      type: Array as () => { text: string; value: string }[],
      default: () => [],
    },
    hasFilter: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['page-change', 'page-limit-change', 'sort-change', 'filter-change', 'edit', 'delete', 'clear-keyword'],
  setup(props, { emit }) {
    const grokTableRef = ref(null);

    // 表格字段配置
    const tableFields = [
      { id: 'name', label: t('名称'), disabled: true },
      { id: 'is_builtin', label: t('来源') },
      { id: 'sample', label: t('样例') },
      { id: 'pattern', label: t('定义') },
      { id: 'description', label: t('描述') },
      { id: 'updated_by', label: t('更新人') },
      { id: 'updated_at', label: t('更新时间') },
    ];

    // 使用表格设置 hook - 默认全部显示
    const { columnSetting, checkFields, handleSettingChange } = useTableSetting({
      cacheKey: 'grokManage',
      fields: tableFields,
      // 不传 defaultSelectedIds，默认全部显示
    });

    // 分页配置
    const pagination = ref({
      current: 1,
      count: props.total,
      limit: 10,
      limitList: [10, 20, 50, 100],
    });

    // 来源筛选选项（固定两种：内置和自定义）
    const originFilterList = [
      { text: t('内置'), value: true },
      { text: t('自定义'), value: false },
    ];

    // 判断是否为内置 Grok
    const isBuiltin = (row: IGrokItem) => row.is_builtin;

    // 分页变化事件处理函数
    const handlePageChange = (current: number) => {
      pagination.value.current = current;
      emit('page-change', current);
    };

    // 分页限制变化事件处理函数
    const handlePageLimitChange = (limit: number) => {
      pagination.value.limit = limit;
      pagination.value.current = 1;
      emit('page-limit-change', limit);
    };

    // 清空过滤条件
    const clearFilters = () => {
      clearTableFilter(grokTableRef.value);
      emit('clear-keyword');
    };

    // 空状态类型
    const emptyType = computed(() => {
      return props.hasFilter ? 'search-empty' : 'empty';
    });

    // 排序变化事件处理函数
    const handleSortChange = (sort: any) => {
      const { prop, order } = sort;
      emit('sort-change', {
        orderField: prop,
        orderType: order,
      });
    };

    // 筛选变化事件处理函数
    const handleFilterChange = (filters: any) => {
      emit('filter-change', filters);
    };

    // 编辑操作
    const handleEdit = (row: IGrokItem) => {
      emit('edit', row);
    };

    // 删除操作
    const handleDelete = (row: IGrokItem) => {
      emit('delete', row);
    };

    // 名称列插槽
    const nameSlot = {
      default: ({ row }: { row: IGrokItem }) => (
        <div
          class='overflow-hidden-text'
          v-bk-overflow-tips
        >
          {row.name}
        </div>
      ),
    };

    // 来源列插槽
    const originSlot = {
      default: ({ row }: { row: IGrokItem }) => (
        <div class='origin-tag-wrapper'>
          {row.is_builtin ? (
            <span class='origin-tag origin-builtin'>{t('内置')}</span>
          ) : (
            <span class='origin-tag origin-custom'>{t('自定义')}</span>
          )}
        </div>
      ),
    };

    // 样例列插槽
    const sampleSlot = {
      default: ({ row }: { row: IGrokItem }) => (
        <div
          class='overflow-hidden-text'
          v-bk-overflow-tips
        >
          {row.sample || '--'}
        </div>
      ),
    };

    // 定义列插槽
    const patternSlot = {
      default: ({ row }: { row: IGrokItem }) => (
        <div
          class='overflow-hidden-text'
          v-bk-overflow-tips
        >
          {row.pattern}
        </div>
      ),
    };

    // 描述列插槽
    const descriptionSlot = {
      default: ({ row }: { row: IGrokItem }) => (
        <div
          class='overflow-hidden-text'
          v-bk-overflow-tips
        >
          {row.description || '--'}
        </div>
      ),
    };

    // 更新人列插槽
    const updatedBySlot = {
      default: ({ row }: { row: IGrokItem }) => <bk-user-display-name user-id={row.updated_by}></bk-user-display-name>,
    };

    // 操作列插槽
    const operateSlot = {
      default: ({ row }: { row: IGrokItem }) => {
        const builtin = isBuiltin(row);
        return (
          <div class='grok-table-operate'>
            <span
              class='king-button'
              v-bk-tooltips={{
                content: t('内置Grok模式不可编辑'),
                disabled: !builtin,
              }}
            >
              <bk-button
                text
                theme='primary'
                disabled={builtin}
                onClick={() => handleEdit(row)}
              >
                {t('编辑')}
              </bk-button>
            </span>
            <span
              class='king-button'
              v-bk-tooltips={{
                content: t('内置Grok模式不可删除'),
                disabled: !builtin,
              }}
            >
              <bk-button
                text
                theme='primary'
                disabled={builtin}
                onClick={() => handleDelete(row)}
              >
                {t('删除')}
              </bk-button>
            </span>
          </div>
        );
      },
    };

    // 监听 total 变化，更新分页配置
    watch(
      () => props.total,
      (newTotal) => {
        pagination.value.count = newTotal;
      },
    );

    return () => (
      <div class='grok-table'>
        <bk-table
          data={props.data}
          pagination={pagination.value}
          ref={grokTableRef}
          v-bkloading={{ isLoading: props.loading }}
          onPage-change={handlePageChange}
          onPage-limit-change={handlePageLimitChange}
          onSort-change={handleSortChange}
          onFilter-change={handleFilterChange}
          scopedSlots={{
            empty: () => (
              <div>
                <EmptyStatus
                  emptyType={emptyType.value}
                  on-operation={clearFilters}
                />
              </div>
            ),
          }}
        >
          <bk-table-column
            key='name'
            class-name='filter-column'
            label={t('名称')}
            prop='name'
            min-width='120'
            scopedSlots={nameSlot}
          />
          {checkFields('is_builtin') && (
            <bk-table-column
              key='is_builtin'
              class-name='filter-column'
              label={t('来源')}
              prop='is_builtin'
              width='100'
              column-key='is_builtin'
              filters={originFilterList}
              filter-multiple={false}
              scopedSlots={originSlot}
            />
          )}
          {checkFields('sample') && (
            <bk-table-column
              key='sample'
              class-name='filter-column'
              label={t('样例')}
              prop='sample'
              min-width='150'
              scopedSlots={sampleSlot}
            />
          )}
          {checkFields('pattern') && (
            <bk-table-column
              key='pattern'
              class-name='filter-column'
              label={t('定义')}
              prop='pattern'
              min-width='200'
              scopedSlots={patternSlot}
            />
          )}
          {checkFields('description') && (
            <bk-table-column
              key='description'
              class-name='filter-column'
              label={t('描述')}
              prop='description'
              min-width='150'
              scopedSlots={descriptionSlot}
            />
          )}
          {checkFields('updated_by') && (
            <bk-table-column
              key='updated_by'
              class-name='filter-column'
              label={t('更新人')}
              prop='updated_by'
              width='120'
              column-key='updated_by'
              filters={props.updatedBys}
              filter-multiple={false}
              filter-searchable
              scopedSlots={updatedBySlot}
            />
          )}
          {checkFields('updated_at') && (
            <bk-table-column
              key='updated_at'
              class-name='filter-column'
              label={t('更新时间')}
              prop='updated_at'
              width='190'
              sortable='custom'
            />
          )}
          <bk-table-column
            label={t('操作')}
            width='120'
            fixed='right'
            scopedSlots={operateSlot}
          />
          <bk-table-column
            type='setting'
            key='setting'
            tippy-options={{ zIndex: 3000 }}
          >
            <bk-table-setting-content
              v-en-style='width: 530px'
              fields={columnSetting.value.fields}
              selected={columnSetting.value.selectedFields}
              on-setting-change={handleSettingChange}
            />
          </bk-table-column>
        </bk-table>
      </div>
    );
  },
});
