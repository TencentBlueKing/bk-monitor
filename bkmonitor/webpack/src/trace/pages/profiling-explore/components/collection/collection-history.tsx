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
import { type PropType, computed, defineComponent, nextTick, shallowRef, watch } from 'vue';

import { type SortInfo, type TableProps, type TableSort, PrimaryTable } from '@blueking/tdesign-ui';
import { Alert, Button, Message } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { useCollectionExecution } from '../../composables/use-collection-execution';
import { useCollectionHistory } from '../../composables/use-collection-history';
import {
  collectionMethodLabels,
  collectionTypeLabels,
  formatCollectionTime,
  scheduleLabels,
} from '../../utils/collection';
import {
  canViewExecution,
  createHistoryFilters,
  executionRowKey,
  executionSelection,
  executionStatusLabels,
  formatExecutionDuration,
  taskColumnMinWidth,
} from '../../utils/collection-history';
import CollectionExecutionAction from './collection-execution-action';
import CollectionExecutionDetail from './collection-execution-detail';
import CollectionExecutionStatus from './collection-execution-status';
import CollectionFilters from './collection-filters';
import EmptyStatus from '@/components/empty-status/empty-status';
import { TraceCellSkeleton } from '@/pages/trace-explore/components/trace-explore-skeleton';

import type { SelectionRange } from '../../types';
import type {
  CollectionExecution,
  CollectionHistoryFilters,
  CollectionResultSelection,
  CollectionTaskColumn,
} from '../../types/collection-history';

import './collection-history.scss';

const skeletonRows = Array.from({ length: 10 }, (_, index) => ({ executionKey: `loading-${index}` }));

/** 表格固定配置项（表头吸顶、横向滚动条吸底），滚动容器为任务历史列表 .collection-history-scroll */
const historyTableAffixed = { container: '.collection-history-scroll' };

// 未下发 task_columns 时回退的默认列，列名在渲染时翻译
const fallbackTaskColumns: CollectionTaskColumn[] = [
  { field: 'task_name', name: '任务名称', type: 'text' },
  { field: 'collection_type', name: '采集进程', type: 'text' },
  { field: 'hosts', name: '目标', type: 'text' },
  { field: 'schedule_type', name: '执行方式', type: 'text' },
  { field: 'started_at', name: '开始时间', type: 'datetime' },
  { field: 'duration_ms', name: '耗时', type: 'duration' },
  { field: 'execution_status', name: '采集结果', type: 'status' },
];

// 有专属插槽的字段，其余字段按列类型渲染；用 Map 避免后端字段命中原型属性
const taskColumnSlots = new Map<string, string>([
  ['execution_status', 'status'],
  ['hosts', 'targets'],
  ['target_count', 'targets'],
  ['task_name', 'name'],
]);

export default defineComponent({
  name: 'CollectionHistory',
  props: {
    bizId: { type: Number, required: true },
    filters: { type: Object as PropType<CollectionHistoryFilters>, required: true },
    range: { type: Array as unknown as PropType<SelectionRange>, required: true },
    statusFilters: {
      type: Array as PropType<string[]>,
      default: () => Object.keys(executionStatusLabels).filter(status => status !== 'outdate'),
    },
    rangeError: { type: String, default: '' },
    revision: { type: Number, required: true },
    // 每次查询重新解析时间表达式，使「近 N 分钟/小时」取最新边界
    resolveRange: { type: Function as PropType<() => SelectionRange>, default: undefined },
    timezone: { type: String, required: true },
    readonly: { type: Boolean, default: false },
  },
  emits: {
    change: (_value: CollectionHistoryFilters) => true,
    created: () => true,
    result: (_value: CollectionResultSelection, _newPage: boolean) => true,
    busy: (_value: boolean) => true,
    share: (_value?: CollectionResultSelection | null) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const scrollContainer = shallowRef<HTMLElement>();
    const h = useCollectionHistory({
      bizId: computed(() => props.bizId),
      filters: computed(() => props.filters),
      range: computed(() => props.range),
      revision: computed(() => props.revision),
      resolveRange: () => props.resolveRange?.(),
    });
    const c = useCollectionExecution({
      bizId: computed(() => props.bizId),
      readonly: computed(() => props.readonly),
      revision: computed(() => props.revision),
      onUpdated: () => {
        Message({ theme: 'success', message: t('终止请求已提交') });
        h.refresh();
      },
      onCreated: () => {
        Message({ theme: 'success', message: t('采集任务已创建') });
        emit('created');
      },
    });
    function reset() {
      emit('change', createHistoryFilters());
    }
    function loadVisiblePage() {
      const element = scrollContainer.value;
      if (element && !h.error.value && element.scrollHeight - element.scrollTop - element.clientHeight < 80)
        h.loadMore();
    }
    // 自动补页只在本页有进展时继续，避免重复页空转；用户滚动与「加载更多」不受此限制
    watch([h.loading, h.hasMore], async () => {
      await nextTick();
      if (h.canAutoFill.value) loadVisiblePage();
    });
    watch([h.loading, c.loading, c.busy], () => emit('busy', h.loading.value || c.loading.value || c.busy.value), {
      immediate: true,
    });
    // 面板与表格列任一筛选生效时，空态区分无匹配结果与暂无数据
    const filtered = computed(
      () =>
        !!props.filters.task_name ||
        !!props.filters.status ||
        props.filters.schedule_types.length ||
        props.filters.ips.length ||
        props.filters.process_names.length ||
        props.filters.process_pids.length
    );
    // tdesign 的 sorter: true 只负责图标与事件，本地排序需自行按 sortInfo 排序
    const sortInfo = shallowRef<null | SortInfo>(null);
    const tableRows = computed(() => {
      const rows = h.rows.value.map(row => ({ ...row, executionKey: executionRowKey(row) }));
      const info = sortInfo.value;
      const field = info?.sortBy;
      if (field !== 'started_at' && field !== 'finished_at') return rows;
      // 执行中的结束时间为 null，空值不参与数值比较、固定排在末尾
      return rows.sort((a, b) => {
        const av = typeof a[field] === 'number' ? a[field] : null;
        const bv = typeof b[field] === 'number' ? b[field] : null;
        if (av === null || bv === null) return av === bv ? 0 : av === null ? 1 : -1;
        return info?.descending ? bv - av : av - bv;
      });
    });
    function changeSort(value: TableSort) {
      const info = Array.isArray(value) ? value[0] : value;
      sortInfo.value = info?.sortBy ? info : null;
    }
    return {
      t,
      h,
      c,
      filtered,
      scrollContainer,
      tableRows,
      reset,
      loadVisiblePage,
      changeSort,
    };
  },
  render() {
    const { h, c } = this;
    const showSkeleton = h.loading.value && !h.rows.value.length;
    // 结果为空时由 empty 插槽接管；否则 tdesign 会注入筛选结果行，导致空态不渲染
    const emptyResult = !showSkeleton && !h.rows.value.length;
    // 列定义优先取后端下发的 task_columns，缺失时回退默认列并翻译列名
    const seenFields = new Set<string>();
    const taskColumns = (
      h.taskColumns.value.length
        ? h.taskColumns.value
        : fallbackTaskColumns.map(column => ({ ...column, name: this.t(column.name) }))
    ).filter(column => {
      if (!column.field || column.field === 'operations' || seenFields.has(column.field)) return false;
      seenFields.add(column.field);
      return true;
    });
    // 已知业务字段保留原有渲染形态，其余按列类型兜底
    const renderTaskCell = (column: CollectionTaskColumn, row: CollectionExecution) => {
      const value = (row as unknown as Record<string, unknown>)[column.field];
      if (column.field === 'collection_type') return collectionTypeLabels[row.collection_type] || '--';
      if (column.field === 'collection_method') return collectionMethodLabels[row.collection_method] || '--';
      if (column.field === 'schedule_type') return this.t(scheduleLabels[row.schedule_type]);
      if (column.type === 'datetime') return formatCollectionTime(typeof value === 'number' ? value : 0, this.timezone);
      if (column.type === 'duration') return formatExecutionDuration(typeof value === 'number' ? value : null);
      return value === null || value === undefined || value === '' ? '--' : String(value);
    };
    const columns: TableProps['columns'] = [
      ...taskColumns.map<NonNullable<TableProps['columns']>[number]>(column => {
        // 初始列宽决定拖拽起点，minWidth 作为拖拽下限
        const width = taskColumnMinWidth(column);
        return {
          colKey: column.field,
          title: column.name || column.field,
          width,
          minWidth: width,
          resizable: true,
          ellipsis: column.type === 'text',
          cell:
            taskColumnSlots.get(column.field) || ((_, { row }) => renderTaskCell(column, row as CollectionExecution)),
          ...(column.field === 'schedule_type'
            ? {
                filter: {
                  type: 'multiple',
                  resetValue: [],
                  showConfirmAndReset: true,
                  list: Object.keys(scheduleLabels).map(value => ({ value, label: this.t(scheduleLabels[value]) })),
                },
              }
            : {}),
          ...(column.field === 'started_at' || column.field === 'finished_at' ? { sorter: true } : {}),
          ...(column.field === 'execution_status'
            ? {
                filter: {
                  type: 'single',
                  list: this.statusFilters
                    .filter(value => Object.hasOwn(executionStatusLabels, value))
                    .map(value => ({ value, label: this.t(executionStatusLabels[value]) })),
                },
              }
            : {}),
        };
      }),
      {
        colKey: 'operations',
        title: this.t('操作'),
        width: 180,
        fixed: 'right',
        resizable: false,
        cell: 'operations',
      },
    ];
    return (
      <section class='collection-tab-panel collection-history-panel'>
        <CollectionFilters
          candidates={h.candidates.value}
          filters={this.filters}
          loading={h.candidateLoading.value}
          autoQuery
          onChange={value => this.$emit('change', value)}
          onRefresh={h.refresh}
        />
        {h.candidateError.value && (
          <Alert
            v-slots={{
              title: () => (
                <i18n-t
                  v-slots={{
                    retry: () => (
                      <Button
                        v-tippy={this.t('重新加载筛选候选项')}
                        theme='primary'
                        text
                        onClick={h.loadCandidates}
                      >
                        {this.t('重试')}
                      </Button>
                    ),
                  }}
                  keypath='部分筛选候选加载失败，可手动输入条件或 {retry}'
                />
              ),
            }}
            theme='warning'
          />
        )}
        {this.rangeError && (
          <Alert
            theme='danger'
            title={this.rangeError}
          />
        )}
        <div
          ref='scrollContainer'
          class='collection-history-scroll'
          aria-busy={h.loading.value}
          onScroll={this.loadVisiblePage}
        >
          {/* 表格内置的列筛选与外部 filters 保持同步，任一列变更都整体回传 */}
          <PrimaryTable
            v-slots={{
              // 请求失败与筛选无结果统一在空态中展示
              empty: () => {
                const error = h.error.value;
                return (
                  <EmptyStatus
                    textMap={{ 500: error || this.t('数据获取异常') }}
                    type={error ? '500' : this.filtered ? 'search-empty' : 'empty'}
                    onOperation={error ? h.refresh : this.reset}
                  />
                );
              },
              name: ({ row }: { row: CollectionExecution }) => (
                <span
                  class='collection-history-task-name'
                  onClick={() => c.open(row)}
                >
                  <span v-tippy={this.t('查看本次任务执行详情')}>{row.task_name}</span>
                </span>
              ),
              targets: ({ row }: { row: CollectionExecution }) => (
                <span v-tippy={{ content: (row.hosts || []).map(host => host.ip).join('，'), allowHTML: false }}>
                  {this.t('共 {n} 台主机', { n: row.target_count ?? row.hosts?.length ?? 0 })}
                </span>
              ),
              status: ({ row }: { row: CollectionExecution }) => (
                <CollectionExecutionStatus status={row.execution_status} />
              ),
              operations: ({ row }: { row: CollectionExecution }) => (
                <div class='collection-row-actions'>
                  {/* 禁用按钮不派发鼠标事件，tooltip 需挂在外层元素上 */}
                  <span
                    v-tippy={this.t(
                      canViewExecution(row) ? '查看本次执行各主机的采集结果' : '本次采集暂无可查看的结果'
                    )}
                  >
                    <Button
                      disabled={!canViewExecution(row)}
                      theme='primary'
                      text
                      onClick={() => this.$emit('result', executionSelection(row), false)}
                    >
                      {this.t('查看结果')}
                    </Button>
                  </span>
                  <span
                    v-tippy={this.t(
                      this.readonly
                        ? '暂无采集操作权限'
                        : row.execution_status === 'running'
                          ? '仅终止本次采集，保留原有执行计划'
                          : '使用历史配置重新执行本次采集'
                    )}
                  >
                    <Button
                      disabled={this.readonly || c.busy.value}
                      theme='primary'
                      text
                      onClick={() => c.requestAction(row.execution_status === 'running' ? 'cancel' : 'rerun', row)}
                    >
                      {this.t(row.execution_status === 'running' ? '终止' : '重新执行')}
                    </Button>
                  </span>
                </div>
              ),
            }}
            bkUiSettings={{
              disabled: columns.some(column => column.colKey === 'task_name') ? ['task_name'] : [],
              rowSize: 'mini',
            }}
            columns={columns.map(column =>
              showSkeleton
                ? {
                    ...column,
                    cell: (render, { rowIndex }) =>
                      render(TraceCellSkeleton, { field: column.colKey, index: rowIndex }),
                  }
                : column
            )}
            filterValue={{
              execution_status: this.filters.status,
              schedule_type: this.filters.schedule_types,
            }}
            data={showSkeleton ? skeletonRows : this.tableRows}
            filterRow={emptyResult ? () => null : undefined}
            headerAffixedTop={historyTableAffixed}
            horizontalScrollAffixedBottom={historyTableAffixed}
            hover={!showSkeleton}
            needCustomScroll={false}
            resizable={true}
            rowKey='executionKey'
            size='small'
            onFilterChange={value =>
              this.$emit('change', {
                ...this.filters,
                status: String(value.execution_status || ''),
                schedule_types: (value.schedule_type || []) as string[],
              })
            }
            onSortChange={this.changeSort}
          />
          {/* 已有数据时追加加载失败，表格保留数据，仅保留重试入口 */}
          {!!h.error.value && !!h.rows.value.length && (
            <div class='collection-history-error'>
              <Button
                v-tippy={this.t('重新加载采集任务历史')}
                onClick={h.loadMore}
              >
                {this.t('重试')}
              </Button>
            </div>
          )}
          {!!h.rows.value.length && (
            <div class='collection-history-more'>
              {h.hasMore.value ? (
                <Button
                  v-tippy={this.t('加载下一批任务执行记录')}
                  loading={h.loading.value}
                  theme='primary'
                  text
                  onClick={h.loadMore}
                >
                  {this.t('加载更多')}
                </Button>
              ) : (
                this.t('已加载全部记录')
              )}
            </div>
          )}
        </div>
        {c.selected.value && (
          <CollectionExecutionDetail
            bizId={this.bizId}
            controller={c}
            readonly={this.readonly}
            timezone={this.timezone}
            onCreated={() => this.$emit('created')}
            onResult={value => this.$emit('result', value, true)}
            onShare={value => this.$emit('share', value)}
          />
        )}
        <CollectionExecutionAction
          controller={c}
          readonly={this.readonly}
        />
      </section>
    );
  },
});
