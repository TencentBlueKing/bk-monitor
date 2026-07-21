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

import { type PropType, computed, defineComponent, shallowRef, useTemplateRef } from 'vue';

import { type BkUiSettings, type TableSort, PrimaryTable } from '@blueking/tdesign-ui';
import { useResizeObserver } from '@vueuse/core';
import { useI18n } from 'vue-i18n';

import { type IProcessColumnConfig, PROCESS_LIST_COLUMNS } from '../../constants/process';
import { useProcessColumnsRenderer } from './hooks/use-process-columns-renderer';

import type { ProcessItem } from '../../types/process';

import './process-table.scss';

export default defineComponent({
  name: 'ProcessTable',
  props: {
    /** 进程数据 */
    data: {
      type: Array as PropType<ProcessItem[]>,
      default: () => [],
    },
    /** 展示列 id 列表 */
    visibleColumns: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    /** 排序（`-key` 倒序 / `key` 正序） */
    sort: {
      type: String,
      default: '',
    },
  },
  emits: {
    sortChange: (_v: string) => true,
    columnsChange: (_cols: string[]) => true,
    rowClick: (_row: ProcessItem) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const bodyRef = useTemplateRef<HTMLElement>('body');
    /** 表格体最大高度（自适应屏幕，表内滚动） */
    const bodyHeight = shallowRef(400);
    /** 监听容器高度变化，动态调整表格最大高度 */
    useResizeObserver(bodyRef, entries => {
      const height = entries[0]?.contentRect?.height;
      if (height) {
        bodyHeight.value = height;
      }
    });

    /** 排序转换为 tdesign 数组形式 */
    const tableSort = computed<TableSort>(() => {
      if (!props.sort) return [];
      const descending = props.sort.startsWith('-');
      return [{ sortBy: descending ? props.sort.slice(1) : props.sort, descending }];
    });

    /** 字段设置：全部字段 + 当前展示字段 */
    const tableSettings = computed<BkUiSettings>(() => ({
      fields: PROCESS_LIST_COLUMNS.map(column => ({
        label: t(column.name),
        field: column.id,
        disabled: column.disabled,
      })),
      checked: props.visibleColumns,
    }));

    /** 列渲染器 hook（含各列单元格自定义渲染逻辑） */
    const { buildColumn } = useProcessColumnsRenderer({
      onRowClick: row => emit('rowClick', row),
    });

    /** 当前可见列的完整 tdesign 列配置 */
    const tableColumns = computed(() =>
      props.visibleColumns
        .map(id => PROCESS_LIST_COLUMNS.find(column => column.id === id))
        .filter((column): column is IProcessColumnConfig => !!column)
        .map(buildColumn)
    );

    /**
     * @description tdesign 排序变化回调，转换为 `-key` / `key` 字符串格式发出
     * @param {TableSort} sortEvent - 排序事件对象
     */
    const handleSortChange = (sortEvent: TableSort) => {
      const target = Array.isArray(sortEvent) ? sortEvent[0] : sortEvent;
      emit('sortChange', target?.sortBy ? `${target.descending ? '-' : ''}${target.sortBy}` : '');
    };

    return {
      bodyHeight,
      tableSettings,
      tableColumns,
      tableSort,
      handleSortChange,
    };
  },
  render() {
    return (
      <div
        ref='body'
        class='process-table'
      >
        <PrimaryTable
          bkUiSettings={this.tableSettings}
          columns={this.tableColumns}
          data={this.data}
          disableDataPage={true}
          hover={true}
          maxHeight={this.bodyHeight}
          needCustomScroll={false}
          resizable={true}
          rowKey='id'
          showSortColumnBgColor={true}
          size='small'
          sort={this.tableSort}
          tableLayout='fixed'
          // @ts-expect-error
          onDisplayColumnsChange={(cols: string[]) => this.$emit('columnsChange', cols)}
          onSortChange={this.handleSortChange}
        />
      </div>
    );
  },
});
