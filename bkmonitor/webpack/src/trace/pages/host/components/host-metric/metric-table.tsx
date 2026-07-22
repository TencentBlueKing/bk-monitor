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

import { type PropType, computed, defineComponent, shallowRef } from 'vue';

import { PrimaryTable } from '@blueking/tdesign-ui';
import { Switcher } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import GroupSelect from './group-select';

import type { SelectOption } from '../../types/aggregation';
import type { MetricItemModel } from '../../types/metric-group';

import './metric-table.scss';

export default defineComponent({
  name: 'MetricTable',
  props: {
    /** 当前展示行（已按分组 + 关键字过滤） */
    rows: {
      type: Array as PropType<MetricItemModel[]>,
      default: () => [],
    },
    /** 「所属分组」可选项（含未分组） */
    groupOptions: {
      type: Array as PropType<SelectOption[]>,
      default: () => [],
    },
    /** 已选中指标 id */
    selectedIds: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    /** 是否允许拖拽（关键字过滤时禁用，避免顺序歧义） */
    draggable: {
      type: Boolean,
      default: true,
    },
  },
  emits: {
    changeGroup: (_payload: { groupId: string; id: string }) => true,
    dragSort: (_rows: MetricItemModel[]) => true,
    addGroup: (_name: string) => true,
    selectChange: (_ids: string[]) => true,
    toggleHidden: (_payload: { hidden: boolean; id: string }) => true,
  },
  setup(props, { emit, slots }) {
    const { t } = useI18n();

    const tableFilters = shallowRef<Record<string, string[]>>({});

    const displayRows = computed(() => {
      const filters = tableFilters.value;
      const hiddenFilter = filters.hidden;
      if (!hiddenFilter?.length) return props.rows;
      return props.rows.filter(row => {
        if (hiddenFilter.includes('visible') && hiddenFilter.includes('hidden')) return true;
        if (hiddenFilter.includes('visible')) return !row.hidden;
        if (hiddenFilter.includes('hidden')) return row.hidden;
        return true;
      });
    });

    const hasHiddenFilter = computed(() => {
      const hiddenFilter = tableFilters.value.hidden;
      return hiddenFilter?.length > 0;
    });

    const columns = computed(() => [
      { colKey: 'row-select', type: 'multiple', width: 42, fixed: 'left' },
      {
        colKey: 'title',
        title: t('指标名称'),
        cell: (_h: unknown, { row }: { row: MetricItemModel }) => <span class='metric-table__name'>{row.title}</span>,
      },
      {
        colKey: 'groupId',
        title: t('所属分组'),
        width: 200,
        cell: (_h: unknown, { row }: { row: MetricItemModel }) => (
          <GroupSelect
            behavior='simplicity'
            clearable={false}
            groupOptions={props.groupOptions}
            modelValue={row.groupId}
            onAddGroup={(name: string) => emit('addGroup', name)}
            onChange={(v: string) => emit('changeGroup', { groupId: v, id: row.id })}
          />
        ),
      },
      {
        colKey: 'hidden',
        title: t('显示'),
        width: 90,
        filter: {
          type: 'multiple',
          list: [
            { label: t('显示'), value: 'visible' },
            { label: t('隐藏'), value: 'hidden' },
          ],
          resetValue: [],
          showConfirmAndReset: true,
        },
        cell: (_h: unknown, { row }: { row: MetricItemModel }) => (
          <Switcher
            modelValue={!row.hidden}
            size='small'
            theme='primary'
            onChange={(v: boolean) => emit('toggleHidden', { hidden: !v, id: row.id })}
          />
        ),
      },
      { colKey: 'drag', width: 40, cell: () => <i class='icon-monitor icon-mc-tuozhuai metric-list-drag' /> },
    ]);

    const handleFilterChange = (filters: Record<string, string[]>) => {
      tableFilters.value = filters;
    };

    return () => (
      <PrimaryTable
        height='100%'
        class='metric-table'
        columns={columns.value as any}
        data={displayRows.value}
        dragSort={props.draggable && !hasHiddenFilter.value && displayRows.value ? 'row-handler' : undefined}
        rowKey='id'
        scroll={{ type: 'virtual' }}
        selectedRowKeys={props.selectedIds}
        onDragSort={(ctx: any) => emit('dragSort', (ctx as any).newData as MetricItemModel[])}
        onFilterChange={handleFilterChange}
        onSelectChange={(ids: any) => emit('selectChange', ids as string[])}
      >
        {{
          empty: slots.empty,
        }}
      </PrimaryTable>
    );
  },
});
