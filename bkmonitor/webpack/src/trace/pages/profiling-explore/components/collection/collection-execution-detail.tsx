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
import type { CollectionExecutionHost, CollectionResultSelection } from '../../types/collection-history';

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
    const columns: TableProps['columns'] = [
      { colKey: 'ip', title: this.t('主机 IP'), width: '20%', ellipsis: true },
      { colKey: 'processes', title: this.t('进程名'), width: '20%', cell: 'processes' },
      { colKey: 'status', title: this.t('状态'), width: '20%', cell: 'status', sorter: true },
      { colKey: 'engine', title: this.t('实际引擎'), width: '20%', cell: () => '--' },
      { colKey: 'operations', title: this.t('操作'), width: '20%', cell: 'operations' },
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
                  <Button onClick={c.refresh}>{this.t('重试')}</Button>
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
                        disabled={this.readonly || c.busy.value || !canRetryExecution(detail)}
                        theme='primary'
                        onClick={() => c.requestAction('retry', detail)}
                      >
                        {this.t('仅重试失败项')}
                      </Button>
                      <div class='collection-execution-counts'>
                        <span class='collection-execution-count-all'>{this.t('全部')}</span>
                        {Object.entries(detail.status_summary)
                          .filter(([, count]) => count > 0)
                          .map(([status, count]) => (
                            <span key={status}>
                              <CollectionExecutionStatus status={status} /> ({count})
                            </span>
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
                            type={c.keyword.value ? 'search-empty' : 'empty'}
                            onOperation={() => {
                              c.keyword.value = '';
                            }}
                          />
                        ),
                        processes: ({ row }: { row: CollectionExecutionHost }) =>
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
                          ),
                        status: ({ row }: { row: CollectionExecutionHost }) => (
                          <CollectionExecutionStatus
                            class={{
                              'has-failure-message': !!row.message && ['failed', 'timeout'].includes(row.status),
                            }}
                            message={row.message}
                            status={row.status}
                          />
                        ),
                        operations: ({ row }: { row: CollectionExecutionHost }) =>
                          ['failed', 'timeout'].includes(row.status) ? (
                            <Button
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
