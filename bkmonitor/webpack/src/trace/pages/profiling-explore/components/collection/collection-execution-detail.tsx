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
import { type PropType, defineComponent, shallowRef, watch } from 'vue';

import { type TableProps, PrimaryTable } from '@blueking/tdesign-ui';
import { Alert, Button, Dialog, Input, Sideslider, Tab } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { collectionTypeLabels, formatCollectionTime } from '../../utils/collection';
import {
  canRetryExecution,
  canViewExecution,
  executionConfiguration,
  executionSelection,
  formatExecutionDuration,
} from '../../utils/collection-history';
import CollectionConfiguration from './collection-configuration';
import CollectionExecutionSkeleton from './collection-execution-skeleton';
import CollectionExecutionStatus from './collection-execution-status';
import EmptyStatus from '@/components/empty-status/empty-status';

import type { UseCollectionExecutionReturn } from '../../composables/use-collection-execution';
import type {
  CollectionExecutionColumn,
  CollectionExecutionHost,
  CollectionResultSelection,
} from '../../types/collection-history';

// 详情加载完成前先用接口文档的默认列表撑起骨架
const fallbackHostColumns: CollectionExecutionColumn[] = [
  { field: 'ip', name: '目标 IP', type: 'text' },
  { field: 'processes', name: '采集进程', type: 'process_list' },
  { field: 'status', name: '状态', type: 'status' },
  { field: 'message', name: '执行信息', type: 'text' },
  { field: 'started_at', name: '开始时间', type: 'datetime' },
  { field: 'finished_at', name: '结束时间', type: 'datetime' },
  { field: 'duration_ms', name: '耗时', type: 'duration' },
];

// 后端只下发列类型，最小宽度按类型兜底，避免动态列被内容挤压
const hostColumnMinWidths: Record<CollectionExecutionColumn['type'], number> = {
  datetime: 180,
  duration: 100,
  process_list: 200,
  status: 120,
  text: 160,
};

export default defineComponent({
  name: 'CollectionExecutionDetail',
  props: {
    controller: { type: Object as PropType<UseCollectionExecutionReturn>, required: true },
    readonly: { type: Boolean, default: false },
    timezone: { type: String, required: true },
  },
  emits: { result: (_value: CollectionResultSelection) => true },
  setup(props) {
    const diagnosis = shallowRef<CollectionExecutionHost | null>(null);
    watch(
      () => props.controller.selected.value,
      () => {
        diagnosis.value = null;
      }
    );
    return { t: useI18n().t, diagnosis };
  },
  render() {
    const c = this.controller;
    const detail = c.detail.value;
    const execution = detail || c.selected.value;
    // 优先使用后端下发的列定义，旧接口无该字段时回退默认列并翻译列名
    const hostColumns = detail?.host_columns?.length
      ? detail.host_columns
      : fallbackHostColumns.map(column => ({ ...column, name: this.t(column.name) }));
    const renderHostProcesses = (row: CollectionExecutionHost) =>
      row.processes.length ? (
        <div class='collection-execution-processes'>
          {row.processes.map(process => (
            <span
              key={`${process.pid}:${process.process_name}`}
              title={`${process.process_name} (${process.pid})`}
            >
              {process.process_name} ({process.pid})
            </span>
          ))}
        </div>
      ) : (
        '--'
      );
    // 按后端声明的列类型渲染单元格，未知类型统一按文本处理
    const renderHostCell = (column: CollectionExecutionColumn, row: CollectionExecutionHost) => {
      const value = (row as unknown as Record<string, unknown>)[column.field];
      if (column.type === 'process_list') return renderHostProcesses(row);
      if (column.type === 'status')
        return (
          <CollectionExecutionStatus
            class={{ 'has-failure-message': !!row.message && ['failed', 'timeout'].includes(row.status) }}
            message={row.message}
            status={String(value ?? '')}
          />
        );
      if (column.type === 'datetime') return value ? formatCollectionTime(value as number, this.timezone) : '--';
      if (column.type === 'duration') return formatExecutionDuration(typeof value === 'number' ? value : null);
      return value ? String(value) : '--';
    };
    const columns: TableProps['columns'] = [
      ...hostColumns.map<NonNullable<TableProps['columns']>[number]>(column => ({
        colKey: column.field,
        title: column.name,
        minWidth: hostColumnMinWidths[column.type],
        cell: (_, { row }) => renderHostCell(column, row as CollectionExecutionHost),
        ...(column.type === 'status' ? { sorter: true } : {}),
        ...(column.type === 'text' ? { ellipsis: true } : {}),
      })),
      { colKey: 'operations', title: this.t('操作'), width: 120, fixed: 'right', cell: 'operations' },
    ];
    return (
      <Sideslider
        width='min(960px, 100vw)'
        class='collection-execution-detail'
        beforeClose={() => !c.busy.value}
        isShow={true}
        transfer={false}
        onClosed={c.close}
      >
        {{
          header: () => (
            <div class='collection-detail-header'>
              <span>{this.t('任务执行详情')}</span>
              <span
                class='collection-execution-title-divider'
                aria-hidden='true'
              />
              <span
                class='collection-detail-name'
                title={execution.task_name}
              >
                {execution.task_name}
              </span>
              <CollectionExecutionStatus
                status={execution.execution_status}
                tag
              />
              <div class='collection-detail-actions'>
                <Button
                  class='collection-execution-result-action'
                  v-tippy={this.t('查看本次执行各主机的采集结果')}
                  disabled={!detail || c.loading.value || !!c.error.value || !canViewExecution(detail)}
                  text
                  onClick={() => this.$emit('result', executionSelection(detail))}
                >
                  <span class='collection-execution-result-label'>
                    <span
                      class='collection-execution-profiling-icon'
                      aria-hidden='true'
                    >
                      <i />
                    </span>
                    {this.t('查看全部结果')}
                  </span>
                </Button>
              </div>
            </div>
          ),
          default: () => (
            <>
              <Tab
                class='collection-execution-tabs'
                active={c.tab.value}
                labelHeight={40}
                type='card-grid'
                onChange={value => {
                  c.tab.value = String(value);
                }}
              >
                <Tab.TabPanel
                  label={() => (
                    <span class='collection-execution-tab-label'>
                      <i
                        class='collection-execution-icon is-results'
                        aria-hidden='true'
                      />
                      {this.t('执行结果')}
                    </span>
                  )}
                  name='results'
                />
                <Tab.TabPanel
                  label={() => (
                    <span class='collection-execution-tab-label'>
                      <i
                        class='collection-execution-icon is-snapshot'
                        aria-hidden='true'
                      />
                      {this.t('配置快照')}
                    </span>
                  )}
                  name='snapshot'
                />
              </Tab>
              {c.error.value ? (
                <div class='collection-execution-content'>
                  <Alert
                    theme='danger'
                    title={c.error.value}
                  />
                  <Button
                    v-tippy={this.t('重新加载任务执行详情')}
                    onClick={c.refresh}
                  >
                    {this.t('重试')}
                  </Button>
                </div>
              ) : c.loading.value ? (
                <CollectionExecutionSkeleton
                  columns={columns}
                  snapshot={c.tab.value === 'snapshot'}
                />
              ) : (
                detail &&
                (c.tab.value === 'snapshot' ? (
                  <CollectionConfiguration
                    hosts={detail.hosts.map(host => ({ host_id: host.bk_host_id, ip: host.ip }))}
                    task={executionConfiguration(detail)}
                    snapshot
                  />
                ) : (
                  <div class='collection-execution-content'>
                    <dl class='collection-execution-summary'>
                      <div>
                        <dt>{this.t('执行时间')}：</dt>
                        <dd>
                          {formatCollectionTime(detail.started_at, this.timezone)} ～{' '}
                          {formatCollectionTime(detail.finished_at, this.timezone)}{' '}
                          <span class='collection-execution-duration'>
                            <i
                              class='collection-execution-icon is-duration'
                              aria-hidden='true'
                            />
                            {formatExecutionDuration(detail.duration_ms)}
                          </span>
                        </dd>
                      </div>
                      <div>
                        <dt>{this.t('采集配置')}：</dt>
                        <dd>
                          {collectionTypeLabels[detail.collection_type]}
                          {detail.config.collector_config.frequency_hz !== undefined &&
                            ` · ${detail.config.collector_config.frequency_hz} Hz`}
                          {detail.config.collector_config.stack_unwind &&
                            ` · ${detail.config.collector_config.stack_unwind}`}
                        </dd>
                      </div>
                      <div>
                        <dt>{this.t('实际引擎')}：</dt>
                        <dd>-- · {this.t('安全替代')}：--</dd>
                      </div>
                    </dl>
                    <div class='collection-execution-toolbar'>
                      <Button
                        v-tippy={this.t(
                          this.readonly
                            ? '暂无采集操作权限'
                            : detail.execution_status === 'running'
                              ? '采集中，暂不能重试失败项'
                              : canRetryExecution(detail)
                                ? '仅重新采集失败和超时主机'
                                : '没有可重试的失败主机'
                        )}
                        disabled={this.readonly || c.busy.value || !canRetryExecution(detail)}
                        theme='primary'
                        onClick={() => c.requestAction('retry', detail)}
                      >
                        {this.t('仅重试失败项')}
                      </Button>
                      {/* 状态计数条：点击按主机状态过滤下方表格 */}
                      <div class='collection-execution-counts'>
                        <button
                          class={['collection-execution-count-all', { 'is-active': !c.hostStatus.value }]}
                          type='button'
                          onClick={() => {
                            c.hostStatus.value = '';
                          }}
                        >
                          {this.t('全部')}
                        </button>
                        {Object.entries(detail.status_summary)
                          .filter(([, count]) => count > 0)
                          .map(([status, count]) => (
                            <button
                              key={status}
                              class={{ 'is-active': c.hostStatus.value === status }}
                              type='button'
                              onClick={() => {
                                c.hostStatus.value = c.hostStatus.value === status ? '' : status;
                              }}
                            >
                              <CollectionExecutionStatus status={status} /> ({count})
                            </button>
                          ))}
                      </div>
                      <Input
                        class='collection-execution-search'
                        aria-label={this.t('搜索 IP、进程名或 PID')}
                        modelValue={c.keyword.value}
                        placeholder={this.t('搜索')}
                        clearable
                        onChange={value => {
                          c.keyword.value = String(value);
                        }}
                      >
                        {{
                          suffix: () => (
                            <i
                              style={{ color: '#979ba5', margin: 'auto 6px' }}
                              class='collection-execution-icon is-search'
                              aria-hidden='true'
                            />
                          ),
                        }}
                      </Input>
                    </div>
                    <PrimaryTable
                      columns={columns}
                      data={c.hosts.value}
                      rowKey='bk_host_id'
                      size='small'
                      sort={c.hostSort.value ? { sortBy: 'status', descending: c.hostSort.value === 'desc' } : null}
                      onSortChange={value => {
                        const sort = Array.isArray(value) ? value[0] : value;
                        c.hostSort.value = sort?.sortBy ? (sort.descending ? 'desc' : 'asc') : '';
                      }}
                    >
                      {{
                        empty: () => (
                          <EmptyStatus
                            type={c.keyword.value || c.hostStatus.value ? 'search-empty' : 'empty'}
                            onOperation={() => {
                              c.keyword.value = '';
                              c.hostStatus.value = '';
                            }}
                          />
                        ),
                        operations: ({ row }: { row: CollectionExecutionHost }) =>
                          ['failed', 'timeout'].includes(row.status) ? (
                            <Button
                              v-tippy={this.t('查看当前主机的采集失败信息')}
                              theme='primary'
                              text
                              onClick={() => {
                                this.diagnosis = row;
                              }}
                            >
                              {this.t('诊断')}
                            </Button>
                          ) : (
                            <Button
                              v-tippy={this.t(
                                row.status === 'succeed' && row.started_at != null && row.finished_at != null
                                  ? '查看当前主机的采集结果'
                                  : '本次采集暂无可查看的结果'
                              )}
                              disabled={row.status !== 'succeed' || row.started_at == null || row.finished_at == null}
                              theme='primary'
                              text
                              onClick={() => this.$emit('result', executionSelection(detail, row))}
                            >
                              {this.t('查看结果')}
                            </Button>
                          ),
                      }}
                    </PrimaryTable>
                  </div>
                ))
              )}
              <Dialog
                width={640}
                isShow={!!this.diagnosis}
                title={this.t('失败信息')}
                transfer={false}
                onClosed={() => {
                  this.diagnosis = null;
                }}
              >
                {{
                  default: () => (
                    <>
                      <p>{this.diagnosis?.ip}</p>
                      <pre class='collection-execution-message'>{this.diagnosis?.message || '--'}</pre>
                    </>
                  ),
                  footer: () => (
                    <Button
                      v-tippy={this.t('关闭失败信息')}
                      onClick={() => {
                        this.diagnosis = null;
                      }}
                    >
                      {this.t('关闭')}
                    </Button>
                  ),
                }}
              </Dialog>
            </>
          ),
        }}
      </Sideslider>
    );
  },
});
