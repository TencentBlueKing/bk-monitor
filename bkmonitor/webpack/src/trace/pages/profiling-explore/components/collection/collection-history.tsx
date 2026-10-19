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

import { type TableProps, PrimaryTable } from '@blueking/tdesign-ui';
import { Alert, Button, Message } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { useCollectionExecution } from '../../composables/use-collection-execution';
import { useCollectionHistory } from '../../composables/use-collection-history';
import { collectionTypeLabels, formatCollectionTime, scheduleLabels } from '../../utils/collection';
import {
  canViewExecution,
  createHistoryFilters,
  executionRowKey,
  executionSelection,
  executionStatusLabels,
  formatExecutionDuration,
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
} from '../../types/collection-history';

import './collection-history.scss';

const skeletonRows = Array.from({ length: 10 }, (_, index) => ({ executionKey: `loading-${index}` }));

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
    timezone: { type: String, required: true },
    readonly: { type: Boolean, default: false },
  },
  emits: {
    change: (_value: CollectionHistoryFilters) => true,
    created: () => true,
    result: (_value: CollectionResultSelection, _newPage: boolean) => true,
    busy: (_value: boolean) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const scrollContainer = shallowRef<HTMLElement>();
    const h = useCollectionHistory({
      bizId: computed(() => props.bizId),
      filters: computed(() => props.filters),
      range: computed(() => props.range),
      revision: computed(() => props.revision),
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
    watch([h.loading, h.hasMore], () => nextTick(loadVisiblePage));
    watch([h.loading, c.loading, c.busy], () => emit('busy', h.loading.value || c.loading.value || c.busy.value), {
      immediate: true,
    });
    return { t, h, c, scrollContainer, reset, loadVisiblePage };
  },
  render() {
    const { h, c } = this;
    const showSkeleton = h.loading.value && !h.rows.value.length;
    const columns: TableProps['columns'] = [
      { colKey: 'task_name', title: this.t('任务名称'), minWidth: 220, ellipsis: true, cell: 'name' },
      {
        colKey: 'collection_type',
        title: this.t('采集进程'),
        width: 160,
        cell: (_, { row }) => collectionTypeLabels[row.collection_type] || '--',
      },
      { colKey: 'hosts', title: this.t('目标'), minWidth: 130, cell: 'targets' },
      {
        colKey: 'schedule_type',
        title: this.t('执行方式'),
        width: 140,
        cell: (_, { row }) => this.t(scheduleLabels[row.schedule_type]),
      },
      {
        colKey: 'started_at',
        title: this.t('开始时间'),
        width: 200,
        cell: (_, { row }) => formatCollectionTime(row.started_at, this.timezone),
      },
      {
        colKey: 'duration_ms',
        title: this.t('耗时'),
        width: 100,
        cell: (_, { row }) => formatExecutionDuration(row.duration_ms),
      },
      {
        colKey: 'execution_status',
        title: this.t('采集结果'),
        width: 140,
        cell: 'status',
        filter: {
          type: 'single',
          list: this.statusFilters
            .filter(value => Object.hasOwn(executionStatusLabels, value))
            .map(value => ({ value, label: this.t(executionStatusLabels[value]) })),
        },
      },
      { colKey: 'operations', title: this.t('操作'), width: 180, fixed: 'right', cell: 'operations' },
    ];
    const filtered =
      !!this.filters.task_name ||
      !!this.filters.status ||
      this.filters.ips.length ||
      this.filters.process_names.length ||
      this.filters.process_pids.length;
    return (
      <section class='collection-tab-panel collection-history-panel'>
        <CollectionFilters
          candidates={h.candidates.value}
          filters={this.filters}
          loading={h.candidateLoading.value}
          onChange={value => this.$emit('change', value)}
          onRefresh={h.refresh}
        />
        {h.candidateError.value && (
          <Alert
            theme='warning'
            title={h.candidateError.value}
          >
            <Button
              v-tippy={this.t('重新加载筛选候选项')}
              theme='primary'
              text
              onClick={h.loadCandidates}
            >
              {this.t('重试')}
            </Button>
          </Alert>
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
          <PrimaryTable
            columns={columns.map(column =>
              showSkeleton
                ? {
                    ...column,
                    cell: (render, { rowIndex }) =>
                      render(TraceCellSkeleton, { field: column.colKey, index: rowIndex }),
                  }
                : column
            )}
            data={
              showSkeleton ? skeletonRows : h.rows.value.map(row => ({ ...row, executionKey: executionRowKey(row) }))
            }
            filterValue={{ execution_status: this.filters.status }}
            hover={!showSkeleton}
            rowKey='executionKey'
            size='small'
            onFilterChange={value =>
              this.$emit('change', { ...this.filters, status: String(value.execution_status || '') })
            }
          >
            {{
              empty: () =>
                h.error.value ? null : (
                  <EmptyStatus
                    type={filtered ? 'search-empty' : 'empty'}
                    onOperation={this.reset}
                  />
                ),
              name: ({ row }: { row: CollectionExecution }) => (
                <Button
                  v-tippy={this.t('查看本次任务执行详情')}
                  theme='primary'
                  text
                  onClick={() => c.open(row)}
                >
                  {row.task_name}
                </Button>
              ),
              targets: ({ row }: { row: CollectionExecution }) => (
                <span v-tippy={{ content: row.hosts.map(host => host.ip).join('，'), allowHTML: false }}>
                  {this.t('共 {n} 台主机', { n: row.target_count })}
                </span>
              ),
              status: ({ row }: { row: CollectionExecution }) => (
                <CollectionExecutionStatus status={row.execution_status} />
              ),
              operations: ({ row }: { row: CollectionExecution }) => (
                <div class='collection-row-actions'>
                  <Button
                    v-tippy={this.t(
                      canViewExecution(row) ? '查看本次执行各主机的采集结果' : '本次采集暂无可查看的结果'
                    )}
                    disabled={!canViewExecution(row)}
                    theme='primary'
                    text
                    onClick={() => this.$emit('result', executionSelection(row), false)}
                  >
                    {this.t('查看结果')}
                  </Button>
                  <Button
                    v-tippy={this.t(
                      this.readonly
                        ? '暂无采集操作权限'
                        : row.execution_status === 'running'
                          ? '仅终止本次采集，保留原有执行计划'
                          : '使用历史配置重新执行本次采集'
                    )}
                    disabled={this.readonly || c.busy.value}
                    theme='primary'
                    text
                    onClick={() => c.requestAction(row.execution_status === 'running' ? 'cancel' : 'rerun', row)}
                  >
                    {this.t(row.execution_status === 'running' ? '终止' : '重新执行')}
                  </Button>
                </div>
              ),
            }}
          </PrimaryTable>
          {h.error.value && (
            <div class='collection-history-error'>
              <Alert
                theme='danger'
                title={h.error.value}
              />
              <Button
                v-tippy={this.t('重新加载采集任务历史')}
                onClick={h.rows.value.length ? h.loadMore : h.refresh}
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
            controller={c}
            readonly={this.readonly}
            timezone={this.timezone}
            onResult={value => this.$emit('result', value, true)}
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
