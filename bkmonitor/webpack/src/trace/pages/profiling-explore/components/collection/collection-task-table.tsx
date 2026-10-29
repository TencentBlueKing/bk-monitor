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
import { type PropType, computed, defineComponent } from 'vue';

import { type TableProps, type TableSort, PrimaryTable } from '@blueking/tdesign-ui';
import { Button, Pagination, Switcher } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import {
  collectionMethodLabels,
  collectionTypeLabels,
  deploymentStatusLabels,
  formatCollectionTime,
  isTaskDeleteBlocked,
  scheduleLabels,
  TASK_OPERATION_FIELD,
} from '../../utils/collection';
import CollectionCrontab from './collection-crontab';
import CollectionSkeleton from './collection-skeleton';
import CommonStatus, { type CommonStatusType } from '@/components/common-detail/common-status/common-status';
import EmptyStatus from '@/components/empty-status/empty-status';

import type { CollectionTask, CollectionTaskTableColumn, ScheduleType } from '../../types/collection';
import type { BkUiSettings } from '@blueking/tdesign-ui';

import './collection-task-table.scss';

// 表头吸顶的滚动容器：工具条内的表格区（引导说明与工具条在容器外，天然常驻），
// 表头贴合容器顶部即可，无需按工具条高度做偏移
const taskTableAffixed = { container: '.collection-task-toolbar-content' };
/** 有专属插槽的字段，其余字段按列类型渲染；用 Map 避免后端字段命中原型属性 */
const taskColumnSlots = new Map<string, string>([
  ['deployment_status', 'deploymentStatus'],
  ['name', 'taskName'],
  ['schedule', 'scheduleType'],
  ['schedule_time', 'scheduleTime'],
  ['task_status', 'taskStatus'],
  [TASK_OPERATION_FIELD, 'operations'],
]);
/** 部署状态对应的状态点样式，与采集结果状态列保持同一套语义 */
const deploymentStatusTypes: Record<string, CommonStatusType> = {
  deploying: 'waiting',
  failed: 'failed',
  outdate: 'disabled',
  success: 'success',
};
/** 分页可选条数 */
const taskPageSizes = [10, 20, 50, 100];

export default defineComponent({
  name: 'CollectionTaskTable',
  props: {
    /** 表格列配置：列名、列宽、固定、排序、筛选、默认/锁定态由外部组装后传入 */
    columns: { type: Array as PropType<CollectionTaskTableColumn[]>, default: () => [] },
    /** 当前页数据 */
    rows: { type: Array as PropType<CollectionTask[]>, default: () => [] },
    /** 过滤后的总条数（分页计数） */
    total: { type: Number, default: 0 },
    loading: { type: Boolean, default: false },
    timezone: { type: String, required: true },
    readonly: { type: Boolean, default: false },
    /** 是否有任务正在执行操作，期间禁用所有行操作 */
    busy: { type: Boolean, default: false },
    sort: { type: Object as PropType<null | { descending: boolean; sortBy: string }>, default: null },
    scheduleTypes: { type: Array as PropType<ScheduleType[]>, default: () => [] },
    statuses: { type: Array as PropType<string[]>, default: () => [] },
    /** 是否已有查询条件生效，用于空态区分暂无数据与无匹配结果 */
    hasFilters: { type: Boolean, default: false },
    /** 表格列设置（显示列、可配置列、锁定列），由外部持久化后受控传入 */
    tableSettings: { type: Object as PropType<Omit<BkUiSettings, 'hasCheckAll'>>, default: () => ({}) },
    page: { type: Number, required: true },
    pageSize: { type: Number, required: true },
  },
  emits: {
    detail: (_row: CollectionTask) => true,
    history: (_row: CollectionTask) => true,
    edit: (_row: CollectionTask) => true,
    execute: (_row: CollectionTask) => true,
    delete: (_row: CollectionTask) => true,
    toggle: (_row: CollectionTask) => true,
    filterChange: (_value: { scheduleTypes: ScheduleType[]; statuses: string[] }) => true,
    sortChange: (_value: null | { descending: boolean; sortBy: string }) => true,
    pageChange: (_value: number) => true,
    limitChange: (_value: number) => true,
    settingsChange: (_value: string[]) => true,
    columnResizeChange: (_value: Record<string, number>) => true,
    resetFilters: () => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    /** 空态需要撑满工具条下的剩余高度，避免底部大片留白 */
    const isEmpty = computed(() => !props.loading && !props.rows.length);
    const showPagination = computed(() => !props.loading && !!props.rows.length);

    /** 按列类型兜底渲染单元格，已知业务字段走各自的展示文案 */
    function renderCell(column: CollectionTaskTableColumn, row: CollectionTask) {
      const value = (row as unknown as Record<string, unknown>)[column.colKey];
      if (column.colKey === 'collection_method') return collectionMethodLabels[row.collection_method] || '--';
      if (column.colKey === 'collection_type') return collectionTypeLabels[row.collection_type] || '--';
      if (column.fieldType === 'datetime' || column.fieldType === 'schedule_time')
        return formatCollectionTime(typeof value === 'number' ? value : 0, props.timezone);
      if (column.fieldType === 'status') return value ? deploymentStatusLabels[String(value)] || String(value) : '--';
      return value === null || value === undefined || value === '' ? '--' : String(value);
    }
    /** 列的结构属性由外部给定，这里只补单元格渲染（对齐 IssuesTable 的 transformColumns） */
    const tableColumns = computed<TableProps['columns']>(() => [
      ...props.columns.map<NonNullable<TableProps['columns']>[number]>(column => ({
        ...column,
        cell: taskColumnSlots.get(String(column.colKey)) || ((_, { row }) => renderCell(column, row as CollectionTask)),
      })),
    ]);

    /**
     * @description 处理排序变化
     * @param value 排序信息
     */
    function changeSort(value: TableSort) {
      const info = Array.isArray(value) ? value[0] : value;
      emit('sortChange', info?.sortBy ? { sortBy: info.sortBy, descending: info.descending === true } : null);
    }

    return { t, changeSort, isEmpty, showPagination, tableColumns };
  },
  render() {
    return (
      <>
        <div class={['collection-task-table', { 'is-empty': this.isEmpty }]}>
          {this.loading ? (
            <CollectionSkeleton />
          ) : (
            <PrimaryTable
              v-slots={{
                empty: () => (
                  <div class='collection-task-empty'>
                    <EmptyStatus
                      textMap={{ empty: this.t('暂无定时任务'), 'search-empty': this.t('暂无匹配任务') }}
                      type={this.hasFilters ? 'search-empty' : 'empty'}
                      onOperation={() => this.$emit('resetFilters')}
                    />
                  </div>
                ),
                taskName: ({ row }: { row: CollectionTask }) => (
                  <Button
                    theme='primary'
                    text
                    onClick={() => this.$emit('detail', row)}
                  >
                    {row.name}
                  </Button>
                ),
                scheduleType: ({ row }: { row: CollectionTask }) => this.t(scheduleLabels[row.schedule.type]),
                scheduleTime: ({ row }: { row: CollectionTask }) =>
                  row.schedule.type === 'cron' ? (
                    <CollectionCrontab
                      timezone={row.schedule.timezone}
                      value={row.schedule.cron_expression}
                      readonly
                    />
                  ) : (
                    <span v-tippy={row.schedule.timezone}>
                      {formatCollectionTime(row.schedule.execute_at, row.schedule.timezone)}
                    </span>
                  ),
                taskStatus: ({ row }: { row: CollectionTask }) => (
                  <span
                    v-tippy={{
                      content: this.t('任务已过期，无法切换启停状态'),
                      onShow: () => row.deployment_status === 'outdate',
                    }}
                  >
                    <Switcher
                      // 计划已过期（outdate）的任务保留当前启停状态，但不允许再切换
                      disabled={this.readonly || this.busy || row.deployment_status === 'outdate'}
                      modelValue={row.task_status === 'enabled'}
                      size='small'
                      theme='primary'
                      onChange={() => this.$emit('toggle', row)}
                    />
                  </span>
                ),
                deploymentStatus: ({ row }: { row: CollectionTask }) => (
                  <CommonStatus
                    text={deploymentStatusLabels[row.deployment_status] || row.deployment_status || '--'}
                    type={deploymentStatusTypes[row.deployment_status] || 'disabled'}
                  />
                ),
                operations: ({ row }: { row: CollectionTask }) => (
                  <div class='collection-row-actions'>
                    <Button
                      theme='primary'
                      text
                      onClick={() => this.$emit('history', row)}
                    >
                      {this.t('执行记录')}
                    </Button>
                    <Button
                      disabled={this.readonly || this.busy}
                      theme='primary'
                      text
                      onClick={() => this.$emit('edit', row)}
                    >
                      {this.t('编辑')}
                    </Button>
                    <Button
                      disabled={this.readonly || this.busy}
                      theme='primary'
                      text
                      onClick={() => this.$emit('execute', row)}
                    >
                      {this.t('立即执行')}
                    </Button>
                    <span
                      v-tippy={{
                        content: this.t('请先停用任务后再删除'),
                        onShow: () => isTaskDeleteBlocked(row),
                      }}
                    >
                      <Button
                        disabled={this.readonly || this.busy || isTaskDeleteBlocked(row)}
                        theme='primary'
                        text
                        onClick={() => this.$emit('delete', row)}
                      >
                        {this.t('删除')}
                      </Button>
                    </span>
                  </div>
                ),
              }}
              bkUiSettings={{ ...this.tableSettings, hasCheckAll: true }}
              columns={this.tableColumns}
              data={this.rows}
              filterValue={{ schedule: this.scheduleTypes, task_status: this.statuses }}
              headerAffixedTop={taskTableAffixed}
              needCustomScroll={false}
              rowKey='task_id'
              size='small'
              sort={this.sort || undefined}
              resizable
              onBkUiSettingsChange={value => this.$emit('settingsChange', value.columns)}
              onColumnResizeChange={context => this.$emit('columnResizeChange', context.columnsWidth)}
              onFilterChange={value =>
                this.$emit('filterChange', {
                  scheduleTypes: (value.schedule || []) as ScheduleType[],
                  statuses: (value.task_status || []) as string[],
                })
              }
              onSortChange={this.changeSort}
            />
          )}
        </div>
        {this.showPagination && (
          <Pagination
            class='collection-task-pagination'
            align='right'
            count={this.total}
            layout={['total', 'limit', 'list']}
            limit={this.pageSize}
            limitList={taskPageSizes}
            location='right'
            modelValue={this.page}
            small
            onChange={value => this.$emit('pageChange', value)}
            onLimitChange={value => this.$emit('limitChange', value)}
          />
        )}
      </>
    );
  },
});
