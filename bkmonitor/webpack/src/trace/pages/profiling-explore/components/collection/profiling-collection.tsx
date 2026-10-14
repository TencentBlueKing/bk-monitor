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

import { type TableProps, PrimaryTable } from '@blueking/tdesign-ui';
import { Alert, Button, Dialog, Input, Pagination, Switcher, Tab } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { useProfilingCollection } from '../../composables/use-profiling-collection';
import { formatCollectionTime, scheduleLabels } from '../../utils/collection';
import CollectionCrontab from './collection-crontab';
import CollectionOnboarding from './collection-onboarding';
import CollectionSkeleton from './collection-skeleton';
import CollectionTaskDetail from './collection-task-detail';
import CollectionTaskForm from './collection-task-form';
import EmptyStatus from '@/components/empty-status/empty-status';
import { useAppStore } from '@/store/modules/app';

import type { CollectionQueryState, CollectionTask, ScheduleType } from '../../types/collection';

import './profiling-collection.scss';

export default defineComponent({
  name: 'ProfilingCollection',
  props: {
    state: { type: Object as PropType<CollectionQueryState>, required: true },
    timezone: { type: String, required: true },
  },
  emits: { change: (_value: Partial<CollectionQueryState>) => true },
  setup(props, { emit }) {
    const { t } = useI18n();
    const store = useAppStore();
    const bizId = computed(() => Number(store.bizId));
    const patch = (value: Partial<CollectionQueryState>) => emit('change', value);
    const collection = useProfilingCollection(
      bizId,
      computed(() => props.state),
      patch
    );
    return { t, bizId, patch, collection };
  },
  render() {
    const c = this.collection;
    const state = this.state;
    if (!c.meta.value) {
      return (
        <section class='profiling-collection'>
          <div
            class={['collection-meta-state', { 'is-loading': c.loading.value }]}
            aria-busy={c.loading.value}
          >
            {c.loading.value ? (
              <CollectionSkeleton variant='page' />
            ) : (
              c.error.value && (
                <div class='collection-meta-error'>
                  <Alert
                    theme='danger'
                    title={c.error.value}
                  />
                  <Button
                    loading={c.loading.value}
                    onClick={c.refresh}
                  >
                    {this.t('重试')}
                  </Button>
                </div>
              )
            )}
          </div>
        </section>
      );
    }
    const columns: TableProps['columns'] = [
      { colKey: 'name', title: this.t('定时任务名称'), minWidth: 240, sorter: true, ellipsis: true, cell: 'taskName' },
      {
        colKey: 'schedule_type',
        title: this.t('定时类型'),
        width: 160,
        filter: {
          type: 'multiple' as const,
          list: ['once_at', 'cron'].map(value => ({ value, label: this.t(scheduleLabels[value]) })),
        },
        cell: (_, { row }) => this.t(scheduleLabels[row.schedule.type]),
      },
      { colKey: 'schedule', title: this.t('执行时间'), minWidth: 220, sorter: true, cell: 'schedule' },
      {
        colKey: 'task_status',
        title: this.t('启/停'),
        width: 100,
        filter: {
          type: 'multiple' as const,
          list: [
            { value: 'enabled', label: this.t('启用') },
            { value: 'disabled', label: this.t('停用') },
          ],
        },
        cell: 'taskStatus',
      },
      { colKey: 'operations', title: this.t('操作'), width: 295, fixed: 'right', cell: 'operations' },
    ];
    const tableSlots = {
      empty: () => (
        <EmptyStatus
          textMap={{ empty: this.t('暂无定时任务'), 'search-empty': this.t('暂无匹配任务') }}
          type={state.keyword || state.scheduleTypes.length || state.statuses.length ? 'search-empty' : 'empty'}
          onOperation={() => this.patch({ keyword: '', scheduleTypes: [], statuses: [] })}
        />
      ),
      taskName: ({ row }: { row: CollectionTask }) => (
        <Button
          theme='primary'
          text
          onClick={() => {
            c.detailId.value = row.task_id;
          }}
        >
          {row.name}
        </Button>
      ),
      schedule: ({ row }: { row: CollectionTask }) =>
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
        <Switcher
          disabled={c.readonly || !!c.busy.value}
          modelValue={row.task_status === 'enabled'}
          size='small'
          onChange={() => c.runAction(row, 'switch')}
        />
      ),
      operations: ({ row }: { row: CollectionTask }) => (
        <div class='collection-row-actions'>
          <span v-tippy={{ content: this.t('指定时间无执行记录'), onShow: () => row.schedule.type !== 'cron' }}>
            <Button
              disabled={row.schedule.type !== 'cron'}
              theme='primary'
              text
              onClick={() => c.openHistory(row)}
            >
              {this.t('执行记录')}
            </Button>
          </span>
          <Button
            disabled={c.readonly || !!c.busy.value || !c.meta.value}
            theme='primary'
            text
            onClick={() => c.openEditor(row)}
          >
            {this.t('编辑')}
          </Button>
          <Button
            disabled={c.readonly || !!c.busy.value}
            theme='primary'
            text
            onClick={() => {
              c.executing.value = row;
            }}
          >
            {this.t('立即执行')}
          </Button>
          <span v-tippy={{ content: this.t('请先停用任务后再删除'), onShow: () => row.task_status !== 'disabled' }}>
            <Button
              disabled={c.readonly || !!c.busy.value || row.task_status !== 'disabled'}
              theme='primary'
              text
              onClick={() => {
                c.deleting.value = row;
              }}
            >
              {this.t('删除')}
            </Button>
          </span>
        </div>
      ),
    };
    return (
      <section class='profiling-collection'>
        {!c.meta.value.enabled ? (
          <CollectionOnboarding
            disabled={c.readonly || c.loading.value}
            loading={c.loading.value}
            onStart={() => c.openEditor()}
          />
        ) : (
          <>
            <Tab
              active={state.tab}
              type='unborder-card'
              onChange={tab => this.patch({ tab: tab as CollectionQueryState['tab'] })}
            >
              <Tab.TabPanel
                label={this.t('Profiling 结果')}
                name='results'
              />
              <Tab.TabPanel
                label={this.t('采集任务历史')}
                name='history'
              />
              <Tab.TabPanel
                label={this.t('任务管理')}
                name='tasks'
              />
            </Tab>
            {state.tab === 'tasks' ? (
              <div class='collection-task-panel'>
                <Alert
                  class='collection-task-guide'
                  title={this.t(
                    '新建任务：选择「立即执行」后进入采集任务历史；选择「指定时间 / 周期执行」后进入下方的定时任务列表。'
                  )}
                  theme='info'
                />
                <div class='collection-task-toolbar'>
                  <Button
                    disabled={c.readonly || !c.meta.value}
                    theme='primary'
                    onClick={() => c.openEditor()}
                  >
                    {this.t('新建任务')}
                  </Button>
                  <Input
                    class='collection-task-search'
                    modelValue={state.keyword}
                    placeholder={this.t('搜索任务名称')}
                    type='search'
                    clearable
                    onInput={keyword => this.patch({ keyword })}
                  />
                  <Button
                    loading={c.loading.value}
                    onClick={c.refresh}
                  >
                    {this.t('刷新')}
                  </Button>
                </div>
                {c.error.value && (
                  <Alert
                    class='collection-inline-alert'
                    theme='danger'
                    title={c.error.value}
                  />
                )}
                {c.loading.value ? (
                  <CollectionSkeleton />
                ) : (
                  <>
                    <PrimaryTable
                      v-slots={tableSlots}
                      columns={columns}
                      data={c.rows.value}
                      filterValue={{ schedule_type: state.scheduleTypes, task_status: state.statuses }}
                      rowKey='task_id'
                      size='small'
                      sort={state.sort || undefined}
                      onFilterChange={value =>
                        this.patch({
                          scheduleTypes: (value.schedule_type || []) as ScheduleType[],
                          statuses: (value.task_status || []) as string[],
                        })
                      }
                      onSortChange={sort => this.patch({ sort: (Array.isArray(sort) ? sort[0] : sort) || null })}
                    />
                    <Pagination
                      class='collection-task-pagination'
                      align='right'
                      count={c.filtered.value.length}
                      layout={['total', 'limit', 'list']}
                      limit={c.pageSize.value}
                      limitList={[10, 20, 50, 100]}
                      modelValue={c.page.value}
                      onChange={value => {
                        c.page.value = value;
                      }}
                      onLimitChange={value => {
                        c.pageSize.value = value;
                      }}
                    />
                  </>
                )}
              </div>
            ) : (
              <div
                class={`collection-${state.tab}-placeholder`}
                data-task-id={state.historyTaskId || undefined}
              />
            )}
          </>
        )}
        {c.editorOpen.value && c.meta.value && (
          <CollectionTaskForm
            key={`${this.bizId}:${c.editing.value?.task_id || 'new'}`}
            bizId={this.bizId}
            meta={c.meta.value}
            task={c.editing.value}
            timezone={this.timezone}
            onClose={() => {
              c.editorOpen.value = false;
            }}
            onSaved={c.saved}
          />
        )}
        {c.detail.value && (
          <CollectionTaskDetail
            busy={!!c.busy.value}
            hostError={c.detailHostError.value}
            hostLoading={c.detailHostLoading.value}
            hosts={c.detailHosts.value}
            readonly={c.readonly}
            task={c.detail.value}
            onClose={() => {
              c.detailId.value = undefined;
            }}
            onDelete={() => {
              c.deleting.value = c.detail.value;
            }}
            onEdit={() => c.openEditor(c.detail.value)}
            onHistory={() => c.openHistory(c.detail.value)}
            onRetryHosts={c.loadDetailHosts}
          />
        )}
        <Dialog
          beforeClose={() => !c.busy.value}
          isShow={!!c.deleting.value}
          quickClose={false}
          title={this.t('确认删除任务？')}
          transfer={false}
          onClosed={() => {
            if (!c.busy.value) c.deleting.value = undefined;
          }}
        >
          {{
            default: () => <p>{c.deleting.value?.name}</p>,
            footer: () => (
              <>
                <Button
                  loading={!!c.busy.value}
                  theme='danger'
                  onClick={() => c.runAction(c.deleting.value, 'delete')}
                >
                  {this.t('删除')}
                </Button>
                <Button
                  disabled={!!c.busy.value}
                  onClick={() => {
                    c.deleting.value = undefined;
                  }}
                >
                  {this.t('取消')}
                </Button>
              </>
            ),
          }}
        </Dialog>
        <Dialog
          beforeClose={() => !c.busy.value}
          isShow={!!c.executing.value}
          quickClose={false}
          title={this.t('确认立即执行任务？')}
          transfer={false}
          onClosed={() => {
            if (!c.busy.value) c.executing.value = undefined;
          }}
        >
          {{
            default: () => (
              <>
                <p>{c.executing.value?.name}</p>
                <p>{this.t('将使用当前配置发起一次采集，原有执行计划保持不变。')}</p>
                <p>{this.t('立即执行仅支持 Linux 主机，提交后可在采集任务历史查看进度')}</p>
              </>
            ),
            footer: () => (
              <>
                <Button
                  loading={!!c.busy.value}
                  theme='primary'
                  onClick={() => c.runAction(c.executing.value, 'execute')}
                >
                  {this.t('确定')}
                </Button>
                <Button
                  disabled={!!c.busy.value}
                  onClick={() => {
                    c.executing.value = undefined;
                  }}
                >
                  {this.t('取消')}
                </Button>
              </>
            ),
          }}
        </Dialog>
      </section>
    );
  },
});
