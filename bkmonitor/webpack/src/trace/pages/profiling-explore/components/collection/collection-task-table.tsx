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
import { type PropType, computed, defineComponent, toRef } from 'vue';

import { useI18n } from 'vue-i18n';

import CommonTable from '../../../alarm-center/components/alarm-table/components/common-table/common-table';
import { useCollectionTaskColumnsRenderer } from '../../composables/use-collection-task-columns-renderer';
import EmptyStatus from '@/components/empty-status/empty-status';

import type { CollectionTask, CollectionTaskTableColumn, ScheduleType } from '../../types/collection';
import type { BkUiSettings, FilterValue } from '@blueking/tdesign-ui';
import type { SlotReturnValue } from 'tdesign-vue-next';

import './collection-task-table.scss';

/** 表头吸顶的滚动容器：工具条内的表格区（引导说明与工具条在容器外，天然常驻），表头贴合容器顶部即可，无需按工具条高度做偏移 */
const taskTableAffixed = { container: '.collection-task-toolbar-content' };

export default defineComponent({
  name: 'CollectionTaskTable',
  props: {
    /** 表格列配置（列名、列宽、固定、排序、筛选、默认/锁定态由外部组装后传入） */
    columns: { type: Array as PropType<CollectionTaskTableColumn[]>, default: () => [] },
    /** 当前页数据 */
    rows: { type: Array as PropType<CollectionTask[]>, default: () => [] },
    /** 过滤后的总条数（分页计数） */
    total: { type: Number, default: 0 },
    /** 表格加载状态 */
    loading: { type: Boolean, default: false },
    /** 是否只读，只读时禁用所有写操作 */
    readonly: { type: Boolean, default: false },
    /** 是否有任务正在执行操作，期间禁用所有行操作 */
    busy: { type: Boolean, default: false },
    /** 表格排序信息 */
    sort: { type: Object as PropType<null | { descending: boolean; sortBy: string }>, default: null },
    /** 执行方式筛选值 */
    scheduleTypes: { type: Array as PropType<ScheduleType[]>, default: () => [] },
    /** 启停状态筛选值 */
    statuses: { type: Array as PropType<string[]>, default: () => [] },
    /** 是否已有查询条件生效，用于空态区分暂无数据与无匹配结果 */
    hasFilters: { type: Boolean, default: false },
    /** 表格列设置（显示列、可配置列、锁定列），由外部持久化后受控传入 */
    tableSettings: { type: Object as PropType<Omit<BkUiSettings, 'hasCheckAll'>>, default: () => ({}) },
    /** 当前页码 */
    page: { type: Number, required: true },
    /** 每页条数 */
    pageSize: { type: Number, required: true },
  },
  emits: {
    /** 显示任务详情 */
    detail: (_row: CollectionTask) => true,
    /** 查看执行记录 */
    history: (_row: CollectionTask) => true,
    /** 编辑任务 */
    edit: (_row: CollectionTask) => true,
    /** 立即执行任务 */
    execute: (_row: CollectionTask) => true,
    /** 删除任务 */
    delete: (_row: CollectionTask) => true,
    /** 切换任务启停状态 */
    toggle: (_row: CollectionTask) => true,
    /** 表头筛选变化 */
    filterChange: (_value: { scheduleTypes: ScheduleType[]; statuses: string[] }) => true,
    /** 排序变化（null 表示取消排序） */
    sortChange: (_value: null | { descending: boolean; sortBy: string }) => true,
    /** 页码变化 */
    pageChange: (_value: number) => true,
    /** 每页条数变化 */
    limitChange: (_value: number) => true,
    /** 显示列字段变化 */
    settingsChange: (_value: string[]) => true,
    /** 列宽拖拽变化（key 为 colKey，value 为列宽） */
    columnResizeChange: (_value: Record<string, number>) => true,
    /** 清空查询条件 */
    resetFilters: () => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    /** 表格设置 */
    const settings = computed<BkUiSettings>(() => ({ ...props.tableSettings, hasCheckAll: true }));
    /** 表格分页配置 */
    const pagination = computed(() => ({ currentPage: props.page, pageSize: props.pageSize, total: props.total }));
    /** 表头筛选受控值 */
    const filterValue = computed<FilterValue>(() => ({
      schedule: props.scheduleTypes,
      task_status: props.statuses,
    }));
    /** 表格排序，转换为 CommonTable 的字符串格式：倒序 => -field；正序 => field */
    const tableSort = computed(() => (props.sort ? `${props.sort.descending ? '-' : ''}${props.sort.sortBy}` : ''));

    /** 任务列渲染器 */
    const { transformColumns } = useCollectionTaskColumnsRenderer({
      busy: toRef(props, 'busy'),
      readonly: toRef(props, 'readonly'),
      onDelete: row => emit('delete', row),
      onDetail: row => emit('detail', row),
      onEdit: row => emit('edit', row),
      onExecute: row => emit('execute', row),
      onHistory: row => emit('history', row),
      onToggle: row => emit('toggle', row),
    });
    /** 转换后的列配置 */
    const transformedColumns = computed(() => transformColumns(props.columns));
    /** 表格渲染数据（CommonTable 的 data 类型为通用记录） */
    const tableData = computed(() => props.rows as unknown as Record<string, unknown>[]);

    /**
     * @description 表格排序变化后回调，将 CommonTable 的字符串排序转换回 { sortBy, descending } 结构
     * @param {string | string[]} sort - 排序规则字符串（倒序以 - 开头），空值表示取消排序
     * @returns {void}
     */
    function handleSortChange(sort: string | string[]) {
      const rule = Array.isArray(sort) ? sort[0] : sort;
      if (!rule) {
        emit('sortChange', null);
        return;
      }
      const descending = rule.startsWith('-');
      emit('sortChange', { sortBy: descending ? rule.slice(1) : rule, descending });
    }

    /**
     * @description 表头筛选变化后回调，将筛选值拆分为执行方式与启停状态两组
     * @param {FilterValue} value - 表头筛选值
     * @returns {void}
     */
    function handleFilterChange(value: FilterValue) {
      emit('filterChange', {
        scheduleTypes: (value.schedule || []) as ScheduleType[],
        statuses: (value.task_status || []) as string[],
      });
    }

    return {
      t,
      filterValue,
      handleFilterChange,
      handleSortChange,
      pagination,
      settings,
      tableSort,
      tableData,
      transformedColumns,
    };
  },
  render() {
    return (
      <div class={['collection-task-table', { 'is-empty': !this.loading && !this.rows.length }]}>
        <CommonTable
          empty={() =>
            (
              <div class='collection-task-empty'>
                <EmptyStatus
                  textMap={{ empty: this.t('暂无定时任务'), 'search-empty': this.t('暂无匹配任务') }}
                  type={this.hasFilters ? 'search-empty' : 'empty'}
                  onOperation={() => this.$emit('resetFilters')}
                />
              </div>
            ) as unknown as SlotReturnValue
          }
          autoFillSpace={!this.rows.length}
          columns={this.transformedColumns}
          data={this.tableData}
          filterValue={this.filterValue}
          headerAffixedTop={taskTableAffixed}
          horizontalScrollAffixedBottom={taskTableAffixed}
          loading={this.loading}
          pagination={this.pagination}
          rowKey='task_id'
          sort={this.tableSort}
          tableSettings={this.settings}
          onColumnResizeChange={context => this.$emit('columnResizeChange', context.columnsWidth)}
          onCurrentPageChange={page => this.$emit('pageChange', page)}
          onDisplayColFieldsChange={fields => this.$emit('settingsChange', fields)}
          onFilterChange={this.handleFilterChange}
          onPageSizeChange={size => this.$emit('limitChange', size)}
          onSortChange={this.handleSortChange}
        />
      </div>
    );
  },
});
